"""
test_llm_contract.py — Contract Tests สำหรับ LLM Providers จริง

Strategy: เรียก API จริง — ตรวจแค่ "รูปแบบ" ไม่ตรวจ "ความถูกต้อง"
- ตรวจว่า API ยังตอบกลับมา
- ตรวจว่า response เป็น JSON ที่ parse ได้
- ตรวจว่ามี field signal ∈ {BUY, SELL, HOLD}
- ตรวจว่า token_count > 0
- ไม่ตรวจว่า signal "ถูก" หรือ "ผิด" ตาม market condition

วิธีรัน:
  # รันเฉพาะ provider ที่มี key
  python -m pytest tests/test_llm_with_api/test_llm_contract.py -v -k groq
  ถ้าไม่ได้ให้ใส่ด้านล่างแทน
  set GROQ_API_KEY=xxx&& python -m pytest tests/test_llm_with_api/test_llm_contract.py -v -k groq
    #xxx คือ API KEY ปล.ต้องใส่&&ตามท้ายด้วย
  # ข้าม contract tests ตอนรัน unit tests ปกติ
  pytest -m tests/ --ignore=tests/test_llm_contract.py

ค่าใช้จ่าย: ~1-3 API calls per provider per run
ความถี่: สัปดาห์ละครั้ง หรือหลังเปลี่ยน model/prompt
"""

import os
import json
import time
import pytest
from dataclasses import dataclass

from agent_core.core.prompt import PromptPackage


# ══════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════

# Prompt ที่ใช้ test — สั้น, ชัดเจน, บังคับ JSON output
CONTRACT_SYSTEM_PROMPT = """You are a gold trading analyst.
Respond ONLY with a single JSON object. No markdown, no explanation.
Format: {"signal": "BUY"|"SELL"|"HOLD", "confidence": 0.0-1.0, "rationale": "brief reason"}"""

CONTRACT_USER_PROMPT = """Current gold market:
- Price: 45,000 THB/baht (฿72,000/gram)
- RSI(14): 55 (neutral)
- MACD: bullish crossover
- Trend: EMA20 > EMA50 (uptrend)
- ATR: 150 THB

What is your trading decision? Respond with JSON only."""

CONTRACT_PROMPT = PromptPackage(
    system=CONTRACT_SYSTEM_PROMPT,
    user=CONTRACT_USER_PROMPT,
    step_label="THOUGHT_FINAL",
)

# Timeout สำหรับ API call (วินาที)
API_TIMEOUT = 30


# ══════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════


def _parse_llm_json(text: str) -> dict:
    """Parse JSON จาก LLM response (รองรับ ```json fences)"""
    import re

    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(cleaned)


def _validate_contract(response, provider_name: str):
    """
    ตรวจ contract ทั้งหมดในที่เดียว — ใช้ร่วมกันทุก provider

    Checks:
      1. response.text ไม่ว่าง
      2. response.provider ตรง
      3. JSON parse ได้
      4. มี field "signal"
      5. signal ∈ {BUY, SELL, HOLD}
      6. มี confidence ∈ [0, 1]
      7. token_total > 0
    """
    # 1. ไม่ว่าง
    assert response.text, f"[{provider_name}] response.text is empty"
    assert len(response.text.strip()) > 2, f"[{provider_name}] response too short"

    # 2. provider ตรง
    assert response.provider == provider_name, (
        f"Expected provider '{provider_name}', got '{response.provider}'"
    )

    # 3. JSON parse ได้
    try:
        data = _parse_llm_json(response.text)
    except (json.JSONDecodeError, ValueError) as e:
        pytest.fail(
            f"[{provider_name}] Cannot parse JSON from response:\n"
            f"  error: {e}\n"
            f"  raw (first 300 chars): {response.text[:300]}"
        )

    # 4. มี signal
    assert "signal" in data, (
        f"[{provider_name}] Missing 'signal' field in response:\n  {data}"
    )

    # 5. signal valid
    assert data["signal"] in ("BUY", "SELL", "HOLD"), (
        f"[{provider_name}] Invalid signal '{data['signal']}' — expected BUY/SELL/HOLD"
    )

    # 6. confidence valid
    if "confidence" in data:
        conf = float(data["confidence"])
        assert 0 <= conf <= 1, (
            f"[{provider_name}] Confidence {conf} out of range [0, 1]"
        )

    # 7. tokens
    assert response.token_total > 0, (
        f"[{provider_name}] token_total={response.token_total} — expected > 0"
    )

    return data  # คืน parsed data สำหรับ test เพิ่มเติม


# ══════════════════════════════════════════════════════════════════
# Gemini Contract Tests
# ══════════════════════════════════════════════════════════════════


HAS_GEMINI_KEY = bool(os.environ.get("GEMINI_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="GEMINI_API_KEY not set")
class TestGeminiContract:
    """Contract test: Gemini API ยังทำงาน + response format ถูกต้อง"""

    @pytest.fixture(scope="class")
    def gemini_client(self):
        from agent_core.llm.client import GeminiClient

        return GeminiClient()

    def test_gemini_responds_with_valid_json(self, gemini_client):
        """Gemini ตอบ JSON ที่มี signal field ถูกต้อง"""
        start = time.time()
        response = gemini_client.call(CONTRACT_PROMPT)
        elapsed = time.time() - start

        data = _validate_contract(response, "gemini")

        # response time ต้องไม่เกิน timeout
        assert elapsed < API_TIMEOUT, (
            f"Gemini took {elapsed:.1f}s — exceeds {API_TIMEOUT}s timeout"
        )

    def test_gemini_model_name(self, gemini_client):
        """model name ต้องไม่ว่าง"""
        response = gemini_client.call(CONTRACT_PROMPT)
        assert response.model, "Gemini model name is empty"

    def test_gemini_has_rationale(self, gemini_client):
        """response ควรมี rationale (ไม่บังคับ แค่ตรวจ)"""
        response = gemini_client.call(CONTRACT_PROMPT)
        data = _parse_llm_json(response.text)
        # ไม่ assert fail — แค่ log warning
        if "rationale" not in data:
            pytest.skip("Gemini did not include rationale (acceptable)")


# ══════════════════════════════════════════════════════════════════
# OpenAI Contract Tests
# ══════════════════════════════════════════════════════════════════


HAS_OPENAI_KEY = bool(os.environ.get("OPENAI_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
class TestOpenAIContract:
    """Contract test: OpenAI API"""

    @pytest.fixture(scope="class")
    def openai_client(self):
        from agent_core.llm.client import OpenAIClient

        return OpenAIClient()

    def test_openai_responds_with_valid_json(self, openai_client):
        start = time.time()
        response = openai_client.call(CONTRACT_PROMPT)
        elapsed = time.time() - start

        _validate_contract(response, "openai")
        assert elapsed < API_TIMEOUT


# ══════════════════════════════════════════════════════════════════
# Claude Contract Tests
# ══════════════════════════════════════════════════════════════════


HAS_CLAUDE_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_CLAUDE_KEY, reason="ANTHROPIC_API_KEY not set")
class TestClaudeContract:
    """Contract test: Anthropic Claude API"""

    @pytest.fixture(scope="class")
    def claude_client(self):
        from agent_core.llm.client import ClaudeClient

        return ClaudeClient()

    def test_claude_responds_with_valid_json(self, claude_client):
        start = time.time()
        response = claude_client.call(CONTRACT_PROMPT)
        elapsed = time.time() - start

        _validate_contract(response, "claude")
        assert elapsed < API_TIMEOUT


# ══════════════════════════════════════════════════════════════════
# Groq Contract Tests
# ══════════════════════════════════════════════════════════════════


HAS_GROQ_KEY = bool(os.environ.get("GROQ_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_GROQ_KEY, reason="GROQ_API_KEY not set")
class TestGroqContract:
    """Contract test: Groq API (LPU inference — ควรเร็วมาก)"""

    @pytest.fixture(scope="class")
    def groq_client(self):
        from agent_core.llm.client import GroqClient

        return GroqClient()

    def test_groq_responds_with_valid_json(self, groq_client):
        start = time.time()
        response = groq_client.call(CONTRACT_PROMPT)
        elapsed = time.time() - start

        _validate_contract(response, "groq")
        # Groq ควรเร็วกว่า 10 วินาที
        assert elapsed < 10, f"Groq took {elapsed:.1f}s — expected < 10s"


# ══════════════════════════════════════════════════════════════════
# DeepSeek Contract Tests
# ══════════════════════════════════════════════════════════════════


HAS_DEEPSEEK_KEY = bool(os.environ.get("DEEPSEEK_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_DEEPSEEK_KEY, reason="DEEPSEEK_API_KEY not set")
class TestDeepSeekContract:
    @pytest.fixture(scope="class")
    def deepseek_client(self):
        from agent_core.llm.client import DeepSeekClient

        return DeepSeekClient()

    def test_deepseek_responds_with_valid_json(self, deepseek_client):
        start = time.time()
        response = deepseek_client.call(CONTRACT_PROMPT)
        elapsed = time.time() - start

        _validate_contract(response, "deepseek")
        assert elapsed < API_TIMEOUT


# ══════════════════════════════════════════════════════════════════
# OpenRouter Contract Tests
# ══════════════════════════════════════════════════════════════════


HAS_OPENROUTER_KEY = bool(os.environ.get("OPENROUTER_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_OPENROUTER_KEY, reason="OPENROUTER_API_KEY not set")
class TestOpenRouterContract:
    @pytest.fixture(scope="class")
    def openrouter_client(self):
        from agent_core.llm.client import OpenRouterClient

        return OpenRouterClient()

    def test_openrouter_responds_with_valid_json(self, openrouter_client):
        start = time.time()
        response = openrouter_client.call(CONTRACT_PROMPT)
        elapsed = time.time() - start

        _validate_contract(response, "openrouter")
        assert elapsed < API_TIMEOUT


# ══════════════════════════════════════════════════════════════════
# Ollama Contract Tests (Local)
# ══════════════════════════════════════════════════════════════════


def _ollama_running():
    """ตรวจว่า Ollama daemon รันอยู่"""
    try:
        import requests

        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


HAS_OLLAMA = _ollama_running()


@pytest.mark.api
@pytest.mark.skipif(not HAS_OLLAMA, reason="Ollama not running at localhost:11434")
class TestOllamaContract:
    """Contract test: Ollama local inference"""

    @pytest.fixture(scope="class")
    def ollama_client(self):
        from agent_core.llm.client import OllamaClient

        return OllamaClient()

    def test_ollama_responds_with_valid_json(self, ollama_client):
        start = time.time()
        response = ollama_client.call(CONTRACT_PROMPT)
        elapsed = time.time() - start

        _validate_contract(response, "ollama")
        # Ollama local ควรตอบภายใน 60 วินาที
        assert elapsed < 60, f"Ollama took {elapsed:.1f}s"


# ══════════════════════════════════════════════════════════════════
# MockClient Contract Tests (ทำงานเสมอ — ไม่ต้อง API key)
# ══════════════════════════════════════════════════════════════════


class TestMockClientContract:
    """
    Contract test สำหรับ MockClient — รันได้เสมอ ไม่ mark api
    ใช้เป็น baseline: ถ้า MockClient contract fail แปลว่า test infra พัง
    """

    @pytest.fixture
    def mock_client(self):
        from agent_core.llm.client import MockClient

        return MockClient()

    def test_mock_returns_llm_response(self, mock_client):
        response = mock_client.call(CONTRACT_PROMPT)
        assert response.text != ""
        assert response.provider == "mock"

    def test_mock_returns_parseable_json(self, mock_client):
        response = mock_client.call(CONTRACT_PROMPT)
        data = _parse_llm_json(response.text)
        assert "signal" in data or "action" in data

    def test_mock_is_always_available(self, mock_client):
        assert mock_client.is_available() is True

    def test_mock_custom_response_map(self):
        from agent_core.llm.client import MockClient

        custom = MockClient(
            response_map={
                "THOUGHT_FINAL": '{"signal": "BUY", "confidence": 0.95, "rationale": "Custom"}'
            }
        )
        response = custom.call(CONTRACT_PROMPT)
        data = json.loads(response.text)
        assert data["signal"] == "BUY"
        assert data["confidence"] == 0.95


# ══════════════════════════════════════════════════════════════════
# Multi-Provider Consistency (เมื่อมีหลาย key)
# ══════════════════════════════════════════════════════════════════


@pytest.mark.api
@pytest.mark.skipif(
    sum([HAS_GEMINI_KEY, HAS_OPENAI_KEY, HAS_CLAUDE_KEY, HAS_GROQ_KEY]) < 2,
    reason="Need at least 2 API keys for cross-provider test",
)
class TestCrossProviderConsistency:
    """ตรวจว่าทุก provider ที่มี key ตอบ JSON format เดียวกัน"""

    def test_all_providers_return_same_fields(self):
        from agent_core.llm.client import LLMClientFactory

        providers_with_keys = []
        if HAS_GEMINI_KEY:
            providers_with_keys.append("gemini")
        if HAS_OPENAI_KEY:
            providers_with_keys.append("openai")
        if HAS_CLAUDE_KEY:
            providers_with_keys.append("claude")
        if HAS_GROQ_KEY:
            providers_with_keys.append("groq")
        if HAS_DEEPSEEK_KEY:
            providers_with_keys.append("deepseek")

        results = {}
        for provider in providers_with_keys:
            client = LLMClientFactory.create(provider)
            response = client.call(CONTRACT_PROMPT)
            data = _parse_llm_json(response.text)
            results[provider] = set(data.keys())

        # ทุก provider ต้องมี "signal" field
        for provider, keys in results.items():
            assert "signal" in keys, f"{provider} missing 'signal' — keys: {keys}"
