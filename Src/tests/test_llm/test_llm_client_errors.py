"""
test_llm_client_errors.py — Tests สำหรับ LLM client error handling

ครอบคลุม (ส่วนที่ test_helpers.py / test_fallback.py ยังไม่ได้ test):
  1. with_retry()       — retry ครบ max_attempts, sleep ระหว่าง attempt, raise หลัง exhaustion
  2. GeminiClient       — missing API key → LLMUnavailableError, missing package → LLMUnavailableError
  3. OllamaClient       — server ไม่ตอบ → LLMUnavailableError ตอน init
                          ConnectionError, Timeout, HTTPError, empty content ตอน call()
  4. LLMClientFactory   — provider ไม่รู้จัก → ValueError (ทดสอบ error message ด้วย)

Strategy: mock requests + google.genai + time.sleep — ไม่ใช้ API จริง
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, call

# ── pre-mock optional packages ──────────────────────────────────
for _mod in ("logs", "logs.logger_setup"):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from agent_core.core.prompt import PromptPackage
from agent_core.llm.client import (
    LLMProviderError,
    LLMUnavailableError,
    MockClient,
    LLMClientFactory,
    with_retry,
)


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _prompt(step: str = "THOUGHT_1") -> PromptPackage:
    return PromptPackage(system="sys", user="usr", step_label=step)


# ══════════════════════════════════════════════════════════════════
# 1. with_retry() decorator
# ══════════════════════════════════════════════════════════════════


class TestWithRetry:
    """with_retry() ควรลองซ้ำเมื่อ LLMProviderError และ raise หลัง exhaustion"""

    def test_success_on_first_attempt(self):
        """ถ้า function ผ่านตั้งแต่ attempt แรก ไม่ต้อง retry"""
        counter = {"calls": 0}

        @with_retry(max_attempts=3, delay=0)
        def fn():
            counter["calls"] += 1
            return "ok"

        result = fn()
        assert result == "ok"
        assert counter["calls"] == 1

    @patch("agent_core.llm.client.time.sleep")
    def test_retries_on_provider_error(self, mock_sleep):
        """fail 2 ครั้งแล้วสำเร็จ → ควรเรียก sleep 2 ครั้ง"""
        counter = {"calls": 0}

        @with_retry(max_attempts=3, delay=1.0)
        def fn():
            counter["calls"] += 1
            if counter["calls"] < 3:
                raise LLMProviderError("API error")
            return "ok"

        result = fn()
        assert result == "ok"
        assert counter["calls"] == 3
        assert mock_sleep.call_count == 2

    @patch("agent_core.llm.client.time.sleep")
    def test_raises_after_max_attempts(self, mock_sleep):
        """fail ทุก attempt → raise LLMProviderError หลัง exhaustion"""

        @with_retry(max_attempts=3, delay=1.0)
        def fn():
            raise LLMProviderError("always fails")

        with pytest.raises(LLMProviderError, match="always fails"):
            fn()

        assert mock_sleep.call_count == 2  # sleep 2 ครั้ง (ไม่ sleep หลัง attempt สุดท้าย)

    @patch("agent_core.llm.client.time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        """delay ควรเพิ่มขึ้นแบบ attempt+1 (delay*1, delay*2)"""

        @with_retry(max_attempts=3, delay=2.0)
        def fn():
            raise LLMProviderError("fail")

        with pytest.raises(LLMProviderError):
            fn()

        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [2.0, 4.0]  # delay * (attempt+1)

    @patch("agent_core.llm.client.time.sleep")
    def test_does_not_retry_non_provider_errors(self, mock_sleep):
        """Exception ทั่วไป (ไม่ใช่ LLMProviderError) → raise ทันทีไม่ retry"""

        @with_retry(max_attempts=3, delay=1.0)
        def fn():
            raise ValueError("unexpected error")

        with pytest.raises(ValueError, match="unexpected error"):
            fn()

        mock_sleep.assert_not_called()

    @patch("agent_core.llm.client.time.sleep")
    def test_max_attempts_one_no_sleep(self, mock_sleep):
        """max_attempts=1 → fail ทันทีไม่ sleep"""

        @with_retry(max_attempts=1, delay=1.0)
        def fn():
            raise LLMProviderError("fail")

        with pytest.raises(LLMProviderError):
            fn()

        mock_sleep.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# 2. GeminiClient — constructor errors
# ══════════════════════════════════════════════════════════════════


class TestGeminiClientInit:
    """GeminiClient ควร raise LLMUnavailableError ถ้า key หรือ package ขาด"""

    def test_missing_api_key_raises(self):
        """ไม่มี GEMINI_API_KEY env var → LLMUnavailableError"""
        import os
        from agent_core.llm.client import GeminiClient

        env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}

        mock_genai = MagicMock()
        mock_genai.Client.side_effect = KeyError("GEMINI_API_KEY")

        with patch.dict(os.environ, env_without_key, clear=True):
            with patch.dict(
                sys.modules, {"google": MagicMock(), "google.genai": mock_genai}
            ):
                # environment ไม่มี key → KeyError → LLMUnavailableError
                with pytest.raises((LLMUnavailableError, KeyError)):
                    GeminiClient(api_key=None)

    def test_explicit_api_key_does_not_raise(self):
        """ส่ง api_key ตรงๆ → mock genai สำเร็จ"""
        from agent_core.llm.client import GeminiClient

        mock_genai = MagicMock()
        with patch.dict(
            sys.modules, {"google": MagicMock(), "google.genai": mock_genai}
        ):
            # ไม่ควร raise ถ้า api_key ส่งมาตรงๆ
            client = GeminiClient(api_key="fake-key-for-test")
            assert client.is_available()

    def test_mock_mode_skips_init(self):
        """use_mock=True → ไม่ต้องการ API key เลย"""
        from agent_core.llm.client import GeminiClient

        client = GeminiClient(use_mock=True)
        assert client.is_available() is True


# ══════════════════════════════════════════════════════════════════
# 2b. GeminiClient — call() success + error paths
# ══════════════════════════════════════════════════════════════════


class TestGeminiClientCall:
    """GeminiClient.call() ทั้ง success path และ error — mock genai ไม่ใช้ API จริง"""

    @pytest.fixture
    def gemini_client(self):
        """สร้าง GeminiClient ที่ mock google.genai ให้ init ผ่าน"""
        from agent_core.llm.client import GeminiClient

        mock_genai = MagicMock()
        with patch.dict(
            sys.modules, {"google": MagicMock(), "google.genai": mock_genai}
        ):
            client = GeminiClient(api_key="fake-key-for-test")
        return client

    def test_successful_call_returns_llm_response(self, gemini_client):
        """call() สำเร็จ → คืน LLMResponse ที่มีข้อมูลครบ"""
        from agent_core.llm.client import LLMResponse

        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 15
        mock_usage.candidates_token_count = 8
        mock_usage.total_token_count = 23

        mock_response = MagicMock()
        mock_response.text = '{"signal": "BUY", "confidence": 0.9}'
        mock_response.usage_metadata = mock_usage

        gemini_client._client.models.generate_content.return_value = mock_response

        result = gemini_client.call(_prompt())

        assert isinstance(result, LLMResponse)
        assert result.text == '{"signal": "BUY", "confidence": 0.9}'
        assert result.token_input == 15
        assert result.token_output == 8
        assert result.token_total == 23
        assert result.model == gemini_client.model
        assert result.provider == gemini_client.PROVIDER_NAME

    def test_token_usage_without_metadata(self, gemini_client):
        """response ไม่มี usage_metadata → token counts = 0"""
        from agent_core.llm.client import LLMResponse

        mock_response = MagicMock()
        mock_response.text = '{"signal": "HOLD"}'
        mock_response.usage_metadata = None

        gemini_client._client.models.generate_content.return_value = mock_response

        result = gemini_client.call(_prompt())

        assert isinstance(result, LLMResponse)
        assert result.token_input == 0
        assert result.token_output == 0
        assert result.token_total == 0

    def test_api_error_raises_provider_error(self, gemini_client):
        """generate_content raise Exception → LLMProviderError"""
        gemini_client._client.models.generate_content.side_effect = Exception(
            "quota exceeded"
        )

        with pytest.raises(LLMProviderError, match="Gemini API error"):
            gemini_client.call(_prompt())

    def test_mock_mode_returns_default_response(self):
        """use_mock=True → คืน mock response โดยไม่เรียก API"""
        from agent_core.llm.client import GeminiClient, LLMResponse

        client = GeminiClient(use_mock=True)
        result = client.call(_prompt())

        assert isinstance(result, LLMResponse)
        assert result.provider == client.PROVIDER_NAME
        assert result.token_input == 0

    def test_uninitialized_client_raises_unavailable(self):
        """_client=None → LLMUnavailableError"""
        from agent_core.llm.client import GeminiClient

        mock_genai = MagicMock()
        with patch.dict(
            sys.modules, {"google": MagicMock(), "google.genai": mock_genai}
        ):
            client = GeminiClient(api_key="fake-key")
        client._client = None

        with pytest.raises(LLMUnavailableError, match="not initialized"):
            client.call(_prompt())

    def test_prompt_text_included_in_response(self, gemini_client):
        """LLMResponse.prompt_text ต้องมี system + user prompt"""
        mock_response = MagicMock()
        mock_response.text = '{"signal": "SELL"}'
        mock_response.usage_metadata = None

        gemini_client._client.models.generate_content.return_value = mock_response

        result = gemini_client.call(_prompt())

        assert "sys" in result.prompt_text
        assert "usr" in result.prompt_text


# ══════════════════════════════════════════════════════════════════
# 3. OllamaClient — server errors
# ══════════════════════════════════════════════════════════════════


class TestOllamaClientInit:
    """OllamaClient ควร raise LLMUnavailableError ถ้า server ไม่ตอบสนอง"""

    def test_server_down_raises_on_init(self):
        """_ping() fail → LLMUnavailableError ตอน __init__"""
        from agent_core.llm.client import OllamaClient
        import requests as req

        with patch("agent_core.llm.client.requests.get") as mock_get:
            mock_get.side_effect = req.exceptions.ConnectionError("refused")
            with pytest.raises(LLMUnavailableError, match="Ollama"):
                OllamaClient()

    def test_server_returns_non_200_raises(self):
        """_ping() คืน status 503 → LLMUnavailableError"""
        from agent_core.llm.client import OllamaClient

        with patch("agent_core.llm.client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 503
            mock_get.return_value = mock_resp
            with pytest.raises(LLMUnavailableError, match="Ollama"):
                OllamaClient()


class TestOllamaClientCall:
    """OllamaClient.call() error paths"""

    @pytest.fixture
    def ollama_client(self):
        """สร้าง OllamaClient ที่ mock _ping() ให้ผ่าน"""
        from agent_core.llm.client import OllamaClient

        with patch("agent_core.llm.client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            client = OllamaClient(model="test-model", timeout=5)
        return client

    def test_connection_error_raises_unavailable(self, ollama_client):
        """requests.post ConnectionError → LLMUnavailableError"""
        import requests as req

        with patch("agent_core.llm.client.requests.post") as mock_post:
            mock_post.side_effect = req.exceptions.ConnectionError("refused")
            with pytest.raises(LLMUnavailableError, match="Ollama"):
                ollama_client.call(_prompt())

    def test_timeout_raises_provider_error(self, ollama_client):
        """requests.post Timeout → LLMProviderError"""
        import requests as req

        with patch("agent_core.llm.client.requests.post") as mock_post:
            mock_post.side_effect = req.exceptions.Timeout("timed out")
            with pytest.raises(LLMProviderError, match="timeout"):
                ollama_client.call(_prompt())

    def test_http_error_raises_provider_error(self, ollama_client):
        """HTTP 4xx/5xx → LLMProviderError"""
        import requests as req

        with patch("agent_core.llm.client.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError("404")
            mock_post.return_value = mock_resp
            with pytest.raises(LLMProviderError, match="HTTP"):
                ollama_client.call(_prompt())

    def test_empty_content_raises_provider_error(self, ollama_client):
        """Ollama คืน empty content → LLMProviderError"""
        with patch("agent_core.llm.client.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {"message": {"content": ""}}
            mock_post.return_value = mock_resp
            with pytest.raises(LLMProviderError, match="empty"):
                ollama_client.call(_prompt())

    def test_successful_call_returns_llm_response(self, ollama_client):
        """call() สำเร็จ → คืน LLMResponse ที่มีข้อมูลครบ"""
        from agent_core.llm.client import LLMResponse

        with patch("agent_core.llm.client.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "message": {"content": '{"signal": "HOLD"}'},
                "prompt_eval_count": 10,
                "eval_count": 5,
            }
            mock_post.return_value = mock_resp
            result = ollama_client.call(_prompt())

        assert isinstance(result, LLMResponse)
        assert result.provider == "ollama"
        assert result.token_input == 10
        assert result.token_output == 5
        assert result.token_total == 15

    def test_think_block_stripped_from_response(self, ollama_client):
        """OllamaClient ต้อง strip <think>...</think> จาก response"""
        with patch("agent_core.llm.client.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.json.return_value = {
                "message": {"content": '<think>thinking...</think>{"signal": "BUY"}'},
                "prompt_eval_count": 0,
                "eval_count": 0,
            }
            mock_post.return_value = mock_resp
            result = ollama_client.call(_prompt())

        assert "<think>" not in result.text
        assert '"BUY"' in result.text

    def test_is_available_pings_server(self, ollama_client):
        """is_available() เรียก _ping() จริง"""
        with patch("agent_core.llm.client.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp
            assert ollama_client.is_available() is True

    def test_is_available_false_when_server_down(self, ollama_client):
        """is_available() คืน False ถ้า server down"""
        import requests as req

        with patch("agent_core.llm.client.requests.get") as mock_get:
            mock_get.side_effect = req.exceptions.ConnectionError("down")
            assert ollama_client.is_available() is False


# ══════════════════════════════════════════════════════════════════
# 4. LLMClientFactory — error paths
# ══════════════════════════════════════════════════════════════════


class TestLLMClientFactoryErrors:
    """LLMClientFactory ควร raise ValueError สำหรับ provider ที่ไม่รู้จัก"""

    def test_unknown_provider_raises_value_error(self):
        """provider ไม่รู้จัก → ValueError"""
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClientFactory.create("nonexistent_provider")

    def test_error_message_includes_provider_name(self):
        """error message ต้องระบุชื่อ provider ที่ผิด"""
        with pytest.raises(ValueError, match="bad_name"):
            LLMClientFactory.create("bad_name")

    def test_error_message_includes_available_providers(self):
        """error message ต้องบอกรายชื่อ provider ที่รองรับ"""
        with pytest.raises(ValueError, match="gemini"):
            LLMClientFactory.create("unknown")

    def test_case_insensitive_provider_name(self):
        """provider name เป็น case-insensitive"""
        client = LLMClientFactory.create("MOCK")
        assert isinstance(client, MockClient)

    def test_create_mock_no_kwargs(self):
        """create('mock') สำเร็จโดยไม่ต้องมี API key"""
        client = LLMClientFactory.create("mock")
        assert client.is_available() is True

    def test_available_providers_contains_all_known(self):
        """available_providers() ต้องมี provider มาตรฐานทั้งหมด"""
        providers = LLMClientFactory.available_providers()
        for expected in ["gemini", "openai", "groq", "mock", "ollama"]:
            assert expected in providers
