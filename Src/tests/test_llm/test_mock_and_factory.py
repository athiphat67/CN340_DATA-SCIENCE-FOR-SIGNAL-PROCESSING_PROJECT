"""
test_mock_and_factory.py — LLM Regression Tests สำหรับ MockClient + LLMClientFactory

ทดสอบ:
  1. MockClient         — response_map, fallback, LLMResponse structure
  2. LLMClient contract — _build_prompt_text, is_available, __repr__
  3. LLMClientFactory   — create, available_providers, register, error handling
  4. DEFAULT_MOCK_RESPONSES — ค่า default ครบ

Strategy: ไม่ใช้ API จริง — ใช้ MockClient เท่านั้น
  - Deterministic 100%
  - รันได้ทุก commit, ไม่เสียเงิน
"""

import json
import pytest

from agent_core.core.prompt import PromptPackage
from agent_core.llm.client import (
    MockClient,
    LLMClient,
    LLMResponse,
    LLMClientFactory,
    LLMProviderError,
    LLMUnavailableError,
    DEFAULT_MOCK_RESPONSES,
)


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _prompt(
    step_label: str = "THOUGHT_1",
    system: str = "You are a trader.",
    user: str = "Analyze gold.",
):
    """สร้าง PromptPackage สำหรับ test"""
    return PromptPackage(system=system, user=user, step_label=step_label)


# ══════════════════════════════════════════════════════════════════
# 1. MockClient — ทดสอบ mock LLM client
# ══════════════════════════════════════════════════════════════════


class TestMockClient:
    """ทดสอบ MockClient — LLM client สำหรับ testing"""

    def test_returns_llm_response(self):
        """call() ต้องคืน LLMResponse"""
        client = MockClient()
        result = client.call(_prompt())
        assert isinstance(result, LLMResponse)

    def test_provider_is_mock(self):
        """provider ต้องเป็น 'mock'"""
        client = MockClient()
        result = client.call(_prompt())
        assert result.provider == "mock"

    def test_model_is_mock(self):
        """model ต้องเป็น 'mock'"""
        client = MockClient()
        result = client.call(_prompt())
        assert result.model == "mock"

    def test_token_counts_are_zero(self):
        """token counts ต้องเป็น 0 ทั้งหมด"""
        client = MockClient()
        result = client.call(_prompt())
        assert result.token_input == 0
        assert result.token_output == 0
        assert result.token_total == 0

    def test_uses_default_response_map(self):
        """ไม่ระบุ response_map → ใช้ DEFAULT_MOCK_RESPONSES"""
        client = MockClient()
        result = client.call(_prompt("THOUGHT_1"))
        parsed = json.loads(result.text)
        assert parsed["action"] == "CALL_TOOL"
        assert parsed["tool"] == "get_news"

    def test_uses_custom_response_map(self):
        """ระบุ response_map เอง → ใช้ตามนั้น"""
        custom = {"MY_STEP": '{"signal": "BUY", "confidence": 0.95}'}
        client = MockClient(response_map=custom)
        result = client.call(_prompt("MY_STEP"))
        parsed = json.loads(result.text)
        assert parsed["signal"] == "BUY"
        assert parsed["confidence"] == 0.95

    def test_fallback_when_key_missing(self):
        """step_label ไม่มีใน response_map → fallback HOLD"""
        client = MockClient()
        result = client.call(_prompt("NONEXISTENT_STEP"))
        parsed = json.loads(result.text)
        assert parsed["action"] == "FINAL_DECISION"
        assert parsed["signal"] == "HOLD"
        assert parsed["confidence"] == 0.5

    def test_empty_response_map(self):
        """response_map = {} → ทุก step ใช้ fallback"""
        client = MockClient(response_map={})
        result = client.call(_prompt("THOUGHT_1"))
        parsed = json.loads(result.text)
        assert parsed["signal"] == "HOLD"

    def test_is_available_always_true(self):
        """MockClient พร้อมใช้งานเสมอ"""
        client = MockClient()
        assert client.is_available() is True

    def test_prompt_text_built_correctly(self):
        """prompt_text ต้องมี SYSTEM: + USER:"""
        client = MockClient()
        result = client.call(_prompt(system="SYS_PROMPT", user="USER_PROMPT"))
        assert "SYSTEM:" in result.prompt_text
        assert "SYS_PROMPT" in result.prompt_text
        assert "USER:" in result.prompt_text
        assert "USER_PROMPT" in result.prompt_text

    def test_different_steps_different_responses(self):
        """step_label ต่างกัน → response ต่างกัน"""
        client = MockClient()
        r1 = client.call(_prompt("THOUGHT_1"))
        r3 = client.call(_prompt("THOUGHT_3"))
        assert r1.text != r3.text

    def test_same_step_same_response(self):
        """step_label เดียวกัน → response เหมือนกันทุกครั้ง (deterministic)"""
        client = MockClient()
        r1 = client.call(_prompt("THOUGHT_1"))
        r2 = client.call(_prompt("THOUGHT_1"))
        assert r1.text == r2.text

    def test_repr(self):
        """__repr__ ต้องมีชื่อ class และ available"""
        client = MockClient()
        r = repr(client)
        assert "MockClient" in r
        assert "available=True" in r


# ══════════════════════════════════════════════════════════════════
# 2. DEFAULT_MOCK_RESPONSES — ค่า default
# ══════════════════════════════════════════════════════════════════


class TestDefaultMockResponses:
    """ทดสอบ DEFAULT_MOCK_RESPONSES มี key ที่คาดหวัง"""

    def test_has_thought_keys(self):
        """ต้องมี THOUGHT_1, THOUGHT_2, THOUGHT_3"""
        assert "THOUGHT_1" in DEFAULT_MOCK_RESPONSES
        assert "THOUGHT_2" in DEFAULT_MOCK_RESPONSES
        assert "THOUGHT_3" in DEFAULT_MOCK_RESPONSES

    def test_has_final_key(self):
        """ต้องมี THOUGHT_FINAL"""
        assert "THOUGHT_FINAL" in DEFAULT_MOCK_RESPONSES

    def test_all_values_are_valid_json(self):
        """ทุก value ต้อง parse เป็น JSON ได้"""
        for key, value in DEFAULT_MOCK_RESPONSES.items():
            parsed = json.loads(value)
            assert isinstance(parsed, dict), f"{key} is not a dict"

    def test_thought_1_calls_tool(self):
        """THOUGHT_1 ต้อง CALL_TOOL"""
        parsed = json.loads(DEFAULT_MOCK_RESPONSES["THOUGHT_1"])
        assert parsed["action"] == "CALL_TOOL"

    def test_thought_final_is_final_decision(self):
        """THOUGHT_FINAL ต้อง FINAL_DECISION"""
        parsed = json.loads(DEFAULT_MOCK_RESPONSES["THOUGHT_FINAL"])
        assert parsed["action"] == "FINAL_DECISION"
        assert parsed["signal"] in ("BUY", "SELL", "HOLD")


# ══════════════════════════════════════════════════════════════════
# 3. LLMClient._build_prompt_text — static method
# ══════════════════════════════════════════════════════════════════


class TestBuildPromptText:
    """ทดสอบ _build_prompt_text() static method"""

    def test_format(self):
        """output = SYSTEM:\\n{system}\\n\\nUSER:\\n{user}"""
        pp = PromptPackage(system="Be a trader", user="Analyze XAUUSD")
        result = LLMClient._build_prompt_text(pp)
        assert result == "SYSTEM:\nBe a trader\n\nUSER:\nAnalyze XAUUSD"

    def test_empty_strings(self):
        """system + user ว่าง → ยัง format ถูก"""
        pp = PromptPackage(system="", user="")
        result = LLMClient._build_prompt_text(pp)
        assert result == "SYSTEM:\n\n\nUSER:\n"

    def test_multiline_content(self):
        """content หลายบรรทัด"""
        pp = PromptPackage(system="Line1\nLine2", user="Q1\nQ2")
        result = LLMClient._build_prompt_text(pp)
        assert "Line1\nLine2" in result
        assert "Q1\nQ2" in result


# ══════════════════════════════════════════════════════════════════
# 4. LLMClientFactory — factory pattern
# ══════════════════════════════════════════════════════════════════


class TestLLMClientFactory:
    """ทดสอบ LLMClientFactory — สร้าง LLM client ตาม provider name"""

    def test_create_mock(self):
        """create('mock') → MockClient"""
        client = LLMClientFactory.create("mock")
        assert isinstance(client, MockClient)
        assert client.is_available() is True

    def test_create_mock_with_response_map(self):
        """create('mock', response_map={...}) → MockClient พร้อม custom map"""
        custom = {"STEP": '{"signal": "SELL"}'}
        client = LLMClientFactory.create("mock", response_map=custom)
        result = client.call(_prompt("STEP"))
        assert '"SELL"' in result.text

    def test_create_unknown_raises(self):
        """provider ไม่รู้จัก → ValueError"""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClientFactory.create("unknown_provider_xyz")

    def test_case_insensitive(self):
        """'Mock', 'MOCK', 'mock' → สร้างได้หมด"""
        c1 = LLMClientFactory.create("Mock")
        c2 = LLMClientFactory.create("MOCK")
        c3 = LLMClientFactory.create("mock")
        assert isinstance(c1, MockClient)
        assert isinstance(c2, MockClient)
        assert isinstance(c3, MockClient)

    def test_strip_whitespace(self):
        """' mock ' → สร้างได้"""
        client = LLMClientFactory.create("  mock  ")
        assert isinstance(client, MockClient)

    def test_available_providers_list(self):
        """available_providers() คืน list ของ provider names"""
        providers = LLMClientFactory.available_providers()
        assert isinstance(providers, list)
        assert "mock" in providers
        assert "gemini" in providers
        assert "groq" in providers

    def test_available_providers_has_all(self):
        """ต้องมี providers ครบ 8 ตัว"""
        providers = LLMClientFactory.available_providers()
        expected = {
            "gemini",
            "openai",
            "claude",
            "mock",
            "groq",
            "deepseek",
            "ollama",
            "openrouter",
        }
        assert expected.issubset(set(providers))

    def test_register_custom_provider(self):
        """register() เพิ่ม provider ใหม่ได้"""

        class CustomClient(LLMClient):
            PROVIDER_NAME = "custom"

            def call(self, prompt_package):
                return LLMResponse(
                    text="custom", prompt_text="", model="custom", provider="custom"
                )

            def is_available(self):
                return True

        LLMClientFactory.register("custom_test", CustomClient)
        assert "custom_test" in LLMClientFactory.available_providers()

        client = LLMClientFactory.create("custom_test")
        assert isinstance(client, CustomClient)

        # cleanup — ลบ provider ที่เพิ่มมา
        del LLMClientFactory._REGISTRY["custom_test"]

    def test_register_non_llmclient_raises(self):
        """register class ที่ไม่ใช่ LLMClient → TypeError"""
        with pytest.raises(TypeError):
            LLMClientFactory.register("bad", dict)

    def test_error_message_shows_available(self):
        """error message ต้องแสดง providers ที่มี"""
        with pytest.raises(ValueError) as exc_info:
            LLMClientFactory.create("nonexistent")
        assert "Available:" in str(exc_info.value)
        assert "gemini" in str(exc_info.value)
