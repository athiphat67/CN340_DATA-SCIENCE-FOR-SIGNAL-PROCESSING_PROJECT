"""
test_fallback.py — LLM Regression Tests สำหรับ FallbackChainClient

ทดสอบ:
  1. First provider success     — ใช้ตัวแรกเลย
  2. Fallback to second         — ตัวแรก fail → ใช้ตัวที่สอง
  3. All fail                   — ทุกตัว fail → raise LLMProviderError
  4. Skip unavailable           — provider ที่ is_available()=False ถูกข้าม
  5. Empty chain                — ไม่มี provider → raise ValueError
  6. active_provider tracking   — เก็บชื่อ provider ที่ใช้จริง
  7. errors list                — เก็บ error log ครบทุกตัวที่ fail
  8. is_available()             — True ถ้ามีอย่างน้อย 1 provider พร้อม
  9. Mixed scenarios            — บาง provider available บาง fail

Strategy: ใช้ MockClient + stub clients ที่ raise exception
  - ไม่ใช้ API จริง
  - Deterministic 100%
"""

import pytest

from agent_core.core.prompt import PromptPackage
from agent_core.llm.client import (
    LLMClient,
    LLMResponse,
    MockClient,
    FallbackChainClient,
    LLMProviderError,
    LLMUnavailableError,
)


# ══════════════════════════════════════════════════════════════════
# Helpers — Stub clients สำหรับ simulate failure
# ══════════════════════════════════════════════════════════════════


def _prompt(step_label: str = "THOUGHT_1"):
    """สร้าง PromptPackage สำหรับ test"""
    return PromptPackage(system="sys", user="usr", step_label=step_label)


class FailingClient(LLMClient):
    """Client ที่ fail ทุกครั้ง — raise LLMProviderError"""

    PROVIDER_NAME = "failing"

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        raise LLMProviderError("Simulated API failure")

    def is_available(self) -> bool:
        return True


class UnavailableClient(LLMClient):
    """Client ที่ไม่พร้อมใช้งาน — is_available() = False"""

    PROVIDER_NAME = "unavailable"

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        raise LLMUnavailableError("No API key")

    def is_available(self) -> bool:
        return False


class UnexpectedErrorClient(LLMClient):
    """Client ที่เกิด unexpected error (ไม่ใช่ LLMException)"""

    PROVIDER_NAME = "unexpected"

    def call(self, prompt_package: PromptPackage) -> LLMResponse:
        raise RuntimeError("Unexpected crash")

    def is_available(self) -> bool:
        return True


# ══════════════════════════════════════════════════════════════════
# 1. Constructor
# ══════════════════════════════════════════════════════════════════


class TestFallbackInit:
    """ทดสอบ FallbackChainClient constructor"""

    def test_empty_chain_raises(self):
        """ไม่มี provider → ValueError"""
        with pytest.raises(ValueError, match="at least one client"):
            FallbackChainClient([])

    def test_single_provider(self):
        """provider เดียว → สร้างได้"""
        chain = FallbackChainClient([("mock", MockClient())])
        assert chain.active_provider == "mock"

    def test_multiple_providers(self):
        """หลาย providers → active_provider = ตัวแรก"""
        chain = FallbackChainClient(
            [
                ("primary", MockClient()),
                ("backup", MockClient()),
            ]
        )
        assert chain.active_provider == "primary"

    def test_errors_initially_empty(self):
        """errors ต้องว่างตอนเริ่มต้น"""
        chain = FallbackChainClient([("mock", MockClient())])
        assert chain.errors == []


# ══════════════════════════════════════════════════════════════════
# 2. First Provider Success
# ══════════════════════════════════════════════════════════════════


class TestFirstProviderSuccess:
    """ตัวแรกสำเร็จ → ใช้เลย ไม่ต้อง fallback"""

    def test_returns_response(self):
        """call() คืน LLMResponse จาก provider แรก"""
        chain = FallbackChainClient(
            [
                ("mock", MockClient()),
                ("backup", MockClient()),
            ]
        )
        result = chain.call(_prompt())
        assert isinstance(result, LLMResponse)

    def test_active_provider_is_first(self):
        """active_provider = ตัวแรก"""
        chain = FallbackChainClient(
            [
                ("primary", MockClient()),
                ("backup", MockClient()),
            ]
        )
        chain.call(_prompt())
        assert chain.active_provider == "primary"

    def test_no_errors_logged(self):
        """ไม่มี error เพราะตัวแรกสำเร็จ"""
        chain = FallbackChainClient(
            [
                ("mock", MockClient()),
            ]
        )
        chain.call(_prompt())
        assert chain.errors == []

    def test_response_content(self):
        """response text ต้องมาจาก MockClient"""
        custom = {"STEP_X": '{"signal": "BUY"}'}
        chain = FallbackChainClient(
            [
                ("mock", MockClient(response_map=custom)),
            ]
        )
        result = chain.call(_prompt("STEP_X"))
        assert '"BUY"' in result.text


# ══════════════════════════════════════════════════════════════════
# 3. Fallback to Second Provider
# ══════════════════════════════════════════════════════════════════


class TestFallbackToSecond:
    """ตัวแรก fail → fallback ไปตัวที่สอง"""

    def test_fallback_success(self):
        """ตัวแรก fail → ตัวสอง (mock) สำเร็จ"""
        chain = FallbackChainClient(
            [
                ("failing", FailingClient()),
                ("mock", MockClient()),
            ]
        )
        result = chain.call(_prompt())
        assert isinstance(result, LLMResponse)
        assert result.provider == "mock"

    def test_active_provider_updated(self):
        """active_provider ต้องเป็นตัวที่สำเร็จ"""
        chain = FallbackChainClient(
            [
                ("failing", FailingClient()),
                ("backup", MockClient()),
            ]
        )
        chain.call(_prompt())
        assert chain.active_provider == "backup"

    def test_first_error_logged(self):
        """error จากตัวแรกต้องถูกเก็บใน errors"""
        chain = FallbackChainClient(
            [
                ("failing", FailingClient()),
                ("mock", MockClient()),
            ]
        )
        chain.call(_prompt())
        assert len(chain.errors) == 1
        assert chain.errors[0]["provider"] == "failing"
        assert chain.errors[0]["skipped"] is False

    def test_multiple_failures_before_success(self):
        """fail 2 ตัว → ตัวที่ 3 สำเร็จ"""
        chain = FallbackChainClient(
            [
                ("fail1", FailingClient()),
                ("fail2", FailingClient()),
                ("mock", MockClient()),
            ]
        )
        result = chain.call(_prompt())
        assert result.provider == "mock"
        assert chain.active_provider == "mock"
        assert len(chain.errors) == 2


# ══════════════════════════════════════════════════════════════════
# 4. All Providers Fail
# ══════════════════════════════════════════════════════════════════


class TestAllProvidersFail:
    """ทุกตัว fail → raise LLMProviderError"""

    def test_raises_provider_error(self):
        """ทุกตัว fail → LLMProviderError"""
        chain = FallbackChainClient(
            [
                ("fail1", FailingClient()),
                ("fail2", FailingClient()),
            ]
        )
        with pytest.raises(LLMProviderError, match="All providers"):
            chain.call(_prompt())

    def test_all_errors_logged(self):
        """error จากทุกตัวถูกเก็บ"""
        chain = FallbackChainClient(
            [
                ("fail1", FailingClient()),
                ("fail2", FailingClient()),
                ("fail3", FailingClient()),
            ]
        )
        with pytest.raises(LLMProviderError):
            chain.call(_prompt())
        assert len(chain.errors) == 3

    def test_error_message_has_summary(self):
        """error message ต้องมีชื่อ provider ทุกตัว"""
        chain = FallbackChainClient(
            [
                ("gemini", FailingClient()),
                ("groq", FailingClient()),
            ]
        )
        with pytest.raises(LLMProviderError) as exc_info:
            chain.call(_prompt())
        msg = str(exc_info.value)
        assert "gemini" in msg
        assert "groq" in msg


# ══════════════════════════════════════════════════════════════════
# 5. Skip Unavailable Providers
# ══════════════════════════════════════════════════════════════════


class TestSkipUnavailable:
    """provider ที่ is_available()=False ถูกข้าม"""

    def test_skip_to_available(self):
        """ข้ามตัวที่ unavailable → ใช้ตัวที่พร้อม"""
        chain = FallbackChainClient(
            [
                ("no_key", UnavailableClient()),
                ("mock", MockClient()),
            ]
        )
        result = chain.call(_prompt())
        assert result.provider == "mock"
        assert chain.active_provider == "mock"

    def test_unavailable_logged_as_skipped(self):
        """unavailable ต้อง log เป็น skipped=True"""
        chain = FallbackChainClient(
            [
                ("no_key", UnavailableClient()),
                ("mock", MockClient()),
            ]
        )
        chain.call(_prompt())
        assert len(chain.errors) == 1
        assert chain.errors[0]["provider"] == "no_key"
        assert chain.errors[0]["skipped"] is True

    def test_all_unavailable_raises(self):
        """ทุกตัว unavailable → raise LLMProviderError"""
        chain = FallbackChainClient(
            [
                ("no_key1", UnavailableClient()),
                ("no_key2", UnavailableClient()),
            ]
        )
        with pytest.raises(LLMProviderError, match="All providers"):
            chain.call(_prompt())


# ══════════════════════════════════════════════════════════════════
# 6. Unexpected Errors
# ══════════════════════════════════════════════════════════════════


class TestUnexpectedErrors:
    """unexpected exceptions (ไม่ใช่ LLMException) ถูก handle"""

    def test_unexpected_error_fallback(self):
        """RuntimeError → fallback ไปตัวถัดไป"""
        chain = FallbackChainClient(
            [
                ("crash", UnexpectedErrorClient()),
                ("mock", MockClient()),
            ]
        )
        result = chain.call(_prompt())
        assert result.provider == "mock"

    def test_unexpected_error_logged(self):
        """unexpected error ถูกเก็บใน errors"""
        chain = FallbackChainClient(
            [
                ("crash", UnexpectedErrorClient()),
                ("mock", MockClient()),
            ]
        )
        chain.call(_prompt())
        assert len(chain.errors) == 1
        assert "RuntimeError" in chain.errors[0]["error"]


# ══════════════════════════════════════════════════════════════════
# 7. is_available()
# ══════════════════════════════════════════════════════════════════


class TestIsAvailable:
    """ทดสอบ is_available() ของ FallbackChainClient"""

    def test_true_if_any_available(self):
        """มีอย่างน้อย 1 ตัวพร้อม → True"""
        chain = FallbackChainClient(
            [
                ("no_key", UnavailableClient()),
                ("mock", MockClient()),
            ]
        )
        assert chain.is_available() is True

    def test_false_if_none_available(self):
        """ทุกตัวไม่พร้อม → False"""
        chain = FallbackChainClient(
            [
                ("no_key1", UnavailableClient()),
                ("no_key2", UnavailableClient()),
            ]
        )
        assert chain.is_available() is False

    def test_all_available(self):
        """ทุกตัวพร้อม → True"""
        chain = FallbackChainClient(
            [
                ("m1", MockClient()),
                ("m2", MockClient()),
            ]
        )
        assert chain.is_available() is True


# ══════════════════════════════════════════════════════════════════
# 8. errors reset between calls
# ══════════════════════════════════════════════════════════════════


class TestErrorsReset:
    """errors ต้อง reset ทุกครั้งที่ call()"""

    def test_errors_reset_on_new_call(self):
        """call ครั้งที่ 2 → errors reset"""
        chain = FallbackChainClient(
            [
                ("fail", FailingClient()),
                ("mock", MockClient()),
            ]
        )

        # call ครั้งแรก — มี 1 error
        chain.call(_prompt())
        assert len(chain.errors) == 1

        # call ครั้งที่ 2 — errors reset
        chain.call(_prompt())
        assert len(chain.errors) == 1  # ไม่สะสม เป็น 1 ใหม่


# ══════════════════════════════════════════════════════════════════
# 9. Mixed Scenarios
# ══════════════════════════════════════════════════════════════════


class TestMixedScenarios:
    """สถานการณ์ผสม — unavailable + fail + success"""

    def test_unavailable_then_fail_then_success(self):
        """unavailable → fail → mock สำเร็จ"""
        chain = FallbackChainClient(
            [
                ("no_key", UnavailableClient()),
                ("failing", FailingClient()),
                ("mock", MockClient()),
            ]
        )
        result = chain.call(_prompt())
        assert result.provider == "mock"
        assert chain.active_provider == "mock"
        assert len(chain.errors) == 2
        assert chain.errors[0]["skipped"] is True  # unavailable
        assert chain.errors[1]["skipped"] is False  # failing

    def test_fail_then_unavailable_then_success(self):
        """fail → unavailable → mock สำเร็จ"""
        chain = FallbackChainClient(
            [
                ("failing", FailingClient()),
                ("no_key", UnavailableClient()),
                ("mock", MockClient()),
            ]
        )
        result = chain.call(_prompt())
        assert result.provider == "mock"
        assert len(chain.errors) == 2

    def test_repr(self):
        """__repr__ ต้องมีข้อมูลครบ"""
        chain = FallbackChainClient(
            [
                ("gemini", MockClient()),
                ("groq", MockClient()),
            ]
        )
        r = repr(chain)
        assert "FallbackChainClient" in r
        assert "gemini" in r
        assert "groq" in r
        assert "available=" in r

    def test_provider_name_is_fallback_chain(self):
        """PROVIDER_NAME = 'fallback_chain'"""
        chain = FallbackChainClient([("mock", MockClient())])
        assert chain.PROVIDER_NAME == "fallback_chain"
