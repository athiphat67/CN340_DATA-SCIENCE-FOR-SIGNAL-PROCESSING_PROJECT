"""
test_token_usage.py — Token Usage Tracking Tests

Strategy: เรียก API จริง + ตรวจว่า token usage ถูกรายงานอย่างถูกต้อง
- token_input  > 0  (prompt ต้องมี tokens)
- token_output > 0  (response ต้องมี tokens)
- token_total  ≥ token_input + token_output
- token_total  อยู่ในช่วงที่สมเหตุสมผล (ไม่เกิน 10,000 สำหรับ prompt สั้น)

วิธีรัน:
  # รันเฉพาะ token usage tests
  python -m pytest tests/test_llm_with_api/test_llm_contract.py -v -k groq
  ถ้าไม่ได้ให้ใส่ด้านล่างแทน
  set GROQ_API_KEY=xxx&& python -m pytest tests/test_llm_with_api/test_token_usage.py -v -k groq
    #xxx คือ API KEY ปล.ต้องใส่&&ตามท้ายด้วย

  # รันได้เสมอ (MockClient + infrastructure tests)
  pytest tests/test_llm_with_api/test_token_usage.py -v -k "Mock or Sanity or Infrastructure"

ค่าใช้จ่าย: ~1 API call per provider per test
ความถี่: ก่อน deploy, หลังเปลี่ยน model/prompt, หลังอัพเดท SDK
"""

import os
import time
import pytest

from agent_core.core.prompt import PromptPackage
from agent_core.llm.client import LLMResponse


# ══════════════════════════════════════════════════════════════════
# Config
# ══════════════════════════════════════════════════════════════════

# Prompt สั้น — ใช้ tokens น้อยที่สุดเพื่อประหยัดค่าใช้จ่าย
TOKEN_TEST_SYSTEM = """You are a gold trading analyst.
Respond ONLY with a single JSON object.
Format: {"signal": "BUY"|"SELL"|"HOLD", "confidence": 0.0-1.0, "rationale": "brief reason"}"""

TOKEN_TEST_USER = """Gold price: 45,000 THB. RSI: 50. Trend: sideways.
What is your trading decision? Respond with JSON only."""

TOKEN_TEST_PROMPT = PromptPackage(
    system=TOKEN_TEST_SYSTEM,
    user=TOKEN_TEST_USER,
    step_label="THOUGHT_FINAL",
)

# Prompt ยาวขึ้น — เพื่อทดสอบว่า token count เพิ่มตามขนาด prompt
LONG_TOKEN_TEST_USER = """Current Thai gold market analysis:
- Price: ฿45,000/baht weight (equivalent to ~$2,400/oz)
- RSI(14): 55 (neutral zone)
- MACD: bullish crossover with histogram at +8.5
- Trend: EMA20 = 45,200, EMA50 = 44,800 → uptrend confirmed
- Bollinger Bands: price near middle band, bandwidth contracting
- ATR(14): 120 THB — moderate volatility
- News sentiment: +0.3 (slightly bullish, Fed minutes positive)
- Portfolio: ฿50,000 cash, 0 gold held
- Time: 10:30 AM (market active hours)

Additional context:
- The Thai gold market follows LBMA pricing closely
- USD/THB exchange rate is 34.5 (relatively stable)
- No major economic data releases expected today
- Previous trading session was sideways with low volume
- Support level at ฿44,500, resistance at ฿45,500

What is your trading decision? Respond with JSON only."""

LONG_TOKEN_TEST_PROMPT = PromptPackage(
    system=TOKEN_TEST_SYSTEM,
    user=LONG_TOKEN_TEST_USER,
    step_label="THOUGHT_FINAL",
)

# สำหรับทดสอบ multiple calls
MULTI_CALL_PROMPTS = [
    PromptPackage(
        system=TOKEN_TEST_SYSTEM,
        user="Gold RSI=25, oversold. Decision?",
        step_label="THOUGHT_1",
    ),
    PromptPackage(
        system=TOKEN_TEST_SYSTEM,
        user="Gold RSI=75, overbought. Decision?",
        step_label="THOUGHT_2",
    ),
    PromptPackage(
        system=TOKEN_TEST_SYSTEM,
        user="Gold RSI=50, neutral. Final decision?",
        step_label="THOUGHT_FINAL",
    ),
]

# Thresholds
MAX_TOKENS_SHORT_PROMPT = 10_000  # prompt สั้น ไม่ควรเกิน 10k tokens
MIN_INPUT_TOKENS = 10  # prompt ต้องใช้อย่างน้อย 10 tokens
MIN_OUTPUT_TOKENS = 5  # response ต้องมีอย่างน้อย 5 tokens


# ══════════════════════════════════════════════════════════════════
# Helper
# ══════════════════════════════════════════════════════════════════


def _validate_token_usage(response: LLMResponse, provider_name: str):
    """
    ตรวจ token usage ของ response

    Checks:
      1. token_input  > 0
      2. token_output > 0
      3. token_total  ≥ token_input + token_output
      4. token_total  ≤ MAX_TOKENS_SHORT_PROMPT
      5. ค่า token เป็น int ทั้งหมด
    """
    # 1. types ต้องเป็น int
    assert isinstance(response.token_input, int), (
        f"[{provider_name}] token_input type={type(response.token_input)} — expected int"
    )
    assert isinstance(response.token_output, int), (
        f"[{provider_name}] token_output type={type(response.token_output)} — expected int"
    )
    assert isinstance(response.token_total, int), (
        f"[{provider_name}] token_total type={type(response.token_total)} — expected int"
    )

    # 2. input tokens > 0 (prompt ต้องมี tokens)
    assert response.token_input > 0, (
        f"[{provider_name}] token_input={response.token_input} — expected > 0. "
        f"Provider may not be reporting input tokens."
    )

    # 3. output tokens > 0 (response ต้องมี tokens)
    assert response.token_output > 0, (
        f"[{provider_name}] token_output={response.token_output} — expected > 0. "
        f"Provider may not be reporting output tokens."
    )

    # 4. total ≥ input + output
    assert response.token_total >= response.token_input + response.token_output, (
        f"[{provider_name}] token_total={response.token_total} < "
        f"token_input({response.token_input}) + token_output({response.token_output})"
    )

    # 5. ไม่เกิน threshold ที่สมเหตุสมผล
    assert response.token_total <= MAX_TOKENS_SHORT_PROMPT, (
        f"[{provider_name}] token_total={response.token_total} — "
        f"exceeds {MAX_TOKENS_SHORT_PROMPT} for short prompt"
    )

    return {
        "input": response.token_input,
        "output": response.token_output,
        "total": response.token_total,
    }


# ══════════════════════════════════════════════════════════════════
# Gemini Token Usage Tests
# ══════════════════════════════════════════════════════════════════


HAS_GEMINI_KEY = bool(os.environ.get("GEMINI_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="GEMINI_API_KEY not set")
class TestGeminiTokenUsage:
    """Token usage: Gemini รายงาน token counts ถูกต้อง"""

    @pytest.fixture(scope="class")
    def gemini_client(self):
        from agent_core.llm.client import GeminiClient

        return GeminiClient()

    def test_basic_token_reporting(self, gemini_client):
        """Gemini ต้องรายงาน token_input, token_output, token_total > 0"""
        response = gemini_client.call(TOKEN_TEST_PROMPT)
        usage = _validate_token_usage(response, "gemini")
        assert usage["input"] >= MIN_INPUT_TOKENS, (
            f"Gemini input tokens {usage['input']} < {MIN_INPUT_TOKENS}"
        )
        assert usage["output"] >= MIN_OUTPUT_TOKENS, (
            f"Gemini output tokens {usage['output']} < {MIN_OUTPUT_TOKENS}"
        )

    def test_longer_prompt_more_input_tokens(self, gemini_client):
        """Prompt ยาวขึ้น → input tokens ต้องมากขึ้น"""
        short_resp = gemini_client.call(TOKEN_TEST_PROMPT)
        time.sleep(0.5)
        long_resp = gemini_client.call(LONG_TOKEN_TEST_PROMPT)

        assert long_resp.token_input > short_resp.token_input, (
            f"Gemini: longer prompt ({long_resp.token_input} input tokens) "
            f"should have more than short prompt ({short_resp.token_input})"
        )

    def test_token_usage_across_multiple_calls(self, gemini_client):
        """หลาย calls ต้องรายงาน tokens ทุกครั้ง"""
        for prompt in MULTI_CALL_PROMPTS:
            response = gemini_client.call(prompt)
            _validate_token_usage(response, f"gemini/{prompt.step_label}")
            time.sleep(0.5)


# ══════════════════════════════════════════════════════════════════
# OpenAI Token Usage Tests
# ══════════════════════════════════════════════════════════════════


HAS_OPENAI_KEY = bool(os.environ.get("OPENAI_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_OPENAI_KEY, reason="OPENAI_API_KEY not set")
class TestOpenAITokenUsage:
    """Token usage: OpenAI รายงาน token counts ถูกต้อง"""

    @pytest.fixture(scope="class")
    def openai_client(self):
        from agent_core.llm.client import OpenAIClient

        return OpenAIClient()

    def test_basic_token_reporting(self, openai_client):
        """OpenAI ต้องรายงาน token counts ครบ"""
        response = openai_client.call(TOKEN_TEST_PROMPT)
        _validate_token_usage(response, "openai")

    def test_longer_prompt_more_input_tokens(self, openai_client):
        """Prompt ยาวขึ้น → input tokens ต้องมากขึ้น"""
        short_resp = openai_client.call(TOKEN_TEST_PROMPT)
        time.sleep(0.5)
        long_resp = openai_client.call(LONG_TOKEN_TEST_PROMPT)

        assert long_resp.token_input > short_resp.token_input


# ══════════════════════════════════════════════════════════════════
# Claude Token Usage Tests
# ══════════════════════════════════════════════════════════════════


HAS_CLAUDE_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_CLAUDE_KEY, reason="ANTHROPIC_API_KEY not set")
class TestClaudeTokenUsage:
    """Token usage: Claude รายงาน token counts ถูกต้อง"""

    @pytest.fixture(scope="class")
    def claude_client(self):
        from agent_core.llm.client import ClaudeClient

        return ClaudeClient()

    def test_basic_token_reporting(self, claude_client):
        """Claude ต้องรายงาน token counts ครบ"""
        response = claude_client.call(TOKEN_TEST_PROMPT)
        _validate_token_usage(response, "claude")

    def test_longer_prompt_more_input_tokens(self, claude_client):
        """Prompt ยาวขึ้น → input tokens ต้องมากขึ้น"""
        short_resp = claude_client.call(TOKEN_TEST_PROMPT)
        time.sleep(0.5)
        long_resp = claude_client.call(LONG_TOKEN_TEST_PROMPT)

        assert long_resp.token_input > short_resp.token_input


# ══════════════════════════════════════════════════════════════════
# Groq Token Usage Tests
# ══════════════════════════════════════════════════════════════════


HAS_GROQ_KEY = bool(os.environ.get("GROQ_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_GROQ_KEY, reason="GROQ_API_KEY not set")
class TestGroqTokenUsage:
    """Token usage: Groq รายงาน token counts ถูกต้อง"""

    @pytest.fixture(scope="class")
    def groq_client(self):
        from agent_core.llm.client import GroqClient

        return GroqClient()

    def test_basic_token_reporting(self, groq_client):
        """Groq ต้องรายงาน token counts ครบ"""
        response = groq_client.call(TOKEN_TEST_PROMPT)
        _validate_token_usage(response, "groq")

    def test_longer_prompt_more_input_tokens(self, groq_client):
        """Prompt ยาวขึ้น → input tokens ต้องมากขึ้น"""
        short_resp = groq_client.call(TOKEN_TEST_PROMPT)
        time.sleep(0.5)
        long_resp = groq_client.call(LONG_TOKEN_TEST_PROMPT)

        assert long_resp.token_input > short_resp.token_input


# ══════════════════════════════════════════════════════════════════
# DeepSeek Token Usage Tests
# ══════════════════════════════════════════════════════════════════


HAS_DEEPSEEK_KEY = bool(os.environ.get("DEEPSEEK_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_DEEPSEEK_KEY, reason="DEEPSEEK_API_KEY not set")
class TestDeepSeekTokenUsage:
    """Token usage: DeepSeek รายงาน token counts ถูกต้อง"""

    @pytest.fixture(scope="class")
    def deepseek_client(self):
        from agent_core.llm.client import DeepSeekClient

        return DeepSeekClient()

    def test_basic_token_reporting(self, deepseek_client):
        """DeepSeek ต้องรายงาน token counts ครบ"""
        response = deepseek_client.call(TOKEN_TEST_PROMPT)
        _validate_token_usage(response, "deepseek")


# ══════════════════════════════════════════════════════════════════
# OpenRouter Token Usage Tests
# ══════════════════════════════════════════════════════════════════


HAS_OPENROUTER_KEY = bool(os.environ.get("OPENROUTER_API_KEY"))


@pytest.mark.api
@pytest.mark.skipif(not HAS_OPENROUTER_KEY, reason="OPENROUTER_API_KEY not set")
class TestOpenRouterTokenUsage:
    """Token usage: OpenRouter รายงาน token counts ถูกต้อง"""

    @pytest.fixture(scope="class")
    def openrouter_client(self):
        from agent_core.llm.client import OpenRouterClient

        return OpenRouterClient()

    def test_basic_token_reporting(self, openrouter_client):
        """OpenRouter ต้องรายงาน token counts ครบ"""
        response = openrouter_client.call(TOKEN_TEST_PROMPT)
        _validate_token_usage(response, "openrouter")


# ══════════════════════════════════════════════════════════════════
# Ollama Token Usage Tests (Local)
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
class TestOllamaTokenUsage:
    """Token usage: Ollama รายงาน token counts ถูกต้อง (local inference)"""

    @pytest.fixture(scope="class")
    def ollama_client(self):
        from agent_core.llm.client import OllamaClient

        return OllamaClient()

    def test_basic_token_reporting(self, ollama_client):
        """Ollama ต้องรายงาน prompt_eval_count + eval_count > 0"""
        response = ollama_client.call(TOKEN_TEST_PROMPT)
        _validate_token_usage(response, "ollama")

    def test_longer_prompt_more_input_tokens(self, ollama_client):
        """Prompt ยาวขึ้น → input tokens ต้องมากขึ้น"""
        short_resp = ollama_client.call(TOKEN_TEST_PROMPT)
        time.sleep(0.5)
        long_resp = ollama_client.call(LONG_TOKEN_TEST_PROMPT)

        assert long_resp.token_input > short_resp.token_input


# ══════════════════════════════════════════════════════════════════
# MockClient Token Usage Tests (รันได้เสมอ — ไม่ต้อง API key)
# ══════════════════════════════════════════════════════════════════


class TestMockClientTokenUsage:
    """
    MockClient token usage — รันได้เสมอ ไม่ mark api
    MockClient returns token_input=0, token_output=0, token_total=0
    ใช้ตรวจว่า LLMResponse structure ถูกต้อง
    """

    def test_mock_returns_zero_tokens(self):
        """MockClient ต้อง return token counts = 0 (ไม่ใช้ API จริง)"""
        from agent_core.llm.client import MockClient

        client = MockClient()
        response = client.call(TOKEN_TEST_PROMPT)

        assert response.token_input == 0, (
            f"MockClient token_input={response.token_input} — expected 0"
        )
        assert response.token_output == 0, (
            f"MockClient token_output={response.token_output} — expected 0"
        )
        assert response.token_total == 0, (
            f"MockClient token_total={response.token_total} — expected 0"
        )

    def test_mock_token_types_are_int(self):
        """token fields ต้องเป็น int เสมอ"""
        from agent_core.llm.client import MockClient

        client = MockClient()
        response = client.call(TOKEN_TEST_PROMPT)

        assert isinstance(response.token_input, int)
        assert isinstance(response.token_output, int)
        assert isinstance(response.token_total, int)

    def test_mock_has_all_response_fields(self):
        """MockClient ต้องมี field ครบตาม LLMResponse dataclass"""
        from agent_core.llm.client import MockClient

        client = MockClient()
        response = client.call(TOKEN_TEST_PROMPT)

        assert hasattr(response, "text")
        assert hasattr(response, "prompt_text")
        assert hasattr(response, "token_input")
        assert hasattr(response, "token_output")
        assert hasattr(response, "token_total")
        assert hasattr(response, "model")
        assert hasattr(response, "provider")

    def test_mock_multiple_calls_consistent(self):
        """หลาย calls ต้อง return tokens = 0 ทุกครั้ง"""
        from agent_core.llm.client import MockClient

        client = MockClient()
        for prompt in MULTI_CALL_PROMPTS:
            response = client.call(prompt)
            assert response.token_total == 0
            assert response.provider == "mock"


# ══════════════════════════════════════════════════════════════════
# LLMResponse Dataclass Sanity Tests (ไม่เรียก API)
# ══════════════════════════════════════════════════════════════════


class TestLLMResponseSanity:
    """ตรวจว่า LLMResponse dataclass ทำงานถูกต้อง — ไม่ต้องเรียก API"""

    def test_default_values(self):
        """LLMResponse default ต้องมี token counts = 0"""
        resp = LLMResponse(
            text='{"signal": "HOLD"}',
            prompt_text="test prompt",
        )
        assert resp.token_input == 0
        assert resp.token_output == 0
        assert resp.token_total == 0
        assert resp.model == ""
        assert resp.provider == ""

    def test_custom_values(self):
        """LLMResponse ต้องเก็บค่า token ที่ระบุได้"""
        resp = LLMResponse(
            text='{"signal": "BUY"}',
            prompt_text="test prompt",
            token_input=150,
            token_output=50,
            token_total=200,
            model="gemini-2.5-flash-lite",
            provider="gemini",
        )
        assert resp.token_input == 150
        assert resp.token_output == 50
        assert resp.token_total == 200
        assert resp.model == "gemini-2.5-flash-lite"
        assert resp.provider == "gemini"

    def test_token_total_can_exceed_sum(self):
        """token_total อาจมากกว่า input+output (บาง provider นับ overhead)"""
        resp = LLMResponse(
            text="test",
            prompt_text="test",
            token_input=100,
            token_output=50,
            token_total=160,  # > 100+50 (e.g. system tokens counted separately)
        )
        assert resp.token_total >= resp.token_input + resp.token_output

    def test_prompt_text_stored(self):
        """prompt_text ต้องเก็บ full prompt ที่ส่งไป"""
        resp = LLMResponse(
            text="result",
            prompt_text="SYSTEM:\nYou are...\n\nUSER:\nGold price...",
            token_input=100,
            token_output=20,
            token_total=120,
        )
        assert "SYSTEM:" in resp.prompt_text
        assert "USER:" in resp.prompt_text


# ══════════════════════════════════════════════════════════════════
# Cross-Provider Token Usage Comparison (เมื่อมีหลาย key)
# ══════════════════════════════════════════════════════════════════


@pytest.mark.api
@pytest.mark.skipif(
    sum([HAS_GEMINI_KEY, HAS_OPENAI_KEY, HAS_CLAUDE_KEY, HAS_GROQ_KEY]) < 2,
    reason="Need at least 2 API keys for cross-provider token test",
)
class TestCrossProviderTokenUsage:
    """เปรียบเทียบ token usage ข้าม providers — ตรวจว่าทุกตัวรายงานได้"""

    def test_all_providers_report_tokens(self):
        """ทุก provider ที่มี key ต้องรายงาน token_total > 0"""
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
            response = client.call(TOKEN_TEST_PROMPT)

            assert response.token_total > 0, f"{provider} returned token_total=0"

            results[provider] = {
                "input": response.token_input,
                "output": response.token_output,
                "total": response.token_total,
            }
            time.sleep(0.5)

        # ── Print summary for debugging ──
        print("\n═══ Cross-Provider Token Usage Summary ═══")
        for provider, usage in results.items():
            print(
                f"  {provider:>12}: input={usage['input']:>5} | "
                f"output={usage['output']:>5} | total={usage['total']:>5}"
            )
        print("═══════════════════════════════════════════")

    def test_same_prompt_similar_input_tokens(self):
        """
        ส่ง prompt เดียวกัน → input tokens ของแต่ละ provider ไม่ควรต่างกันเกิน 5x
        (tokenizer ต่างกัน แต่ order of magnitude ควรใกล้กัน)
        """
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

        input_tokens = {}
        for provider in providers_with_keys:
            client = LLMClientFactory.create(provider)
            response = client.call(TOKEN_TEST_PROMPT)
            input_tokens[provider] = response.token_input
            time.sleep(0.5)

        if len(input_tokens) >= 2:
            min_tokens = min(input_tokens.values())
            max_tokens = max(input_tokens.values())
            # ไม่ควรต่างกันเกิน 5 เท่า
            assert max_tokens <= min_tokens * 5, (
                f"Input token counts vary too much across providers: {input_tokens}\n"
                f"  min={min_tokens}, max={max_tokens}, ratio={max_tokens / min_tokens:.1f}x"
            )


# ══════════════════════════════════════════════════════════════════
# Token Usage Infrastructure Tests (ไม่เรียก API)
# ══════════════════════════════════════════════════════════════════


class TestTokenUsageInfrastructure:
    """ตรวจว่า token tracking infrastructure ทำงาน — ไม่ต้องเรียก API"""

    def test_llm_response_fields_exist(self):
        """LLMResponse dataclass ต้องมี token fields ครบ"""
        import dataclasses

        field_names = [f.name for f in dataclasses.fields(LLMResponse)]

        assert "token_input" in field_names, "Missing token_input field"
        assert "token_output" in field_names, "Missing token_output field"
        assert "token_total" in field_names, "Missing token_total field"

    def test_llm_response_token_defaults(self):
        """token defaults ต้องเป็น 0"""
        import dataclasses

        fields = {f.name: f for f in dataclasses.fields(LLMResponse)}

        assert fields["token_input"].default == 0
        assert fields["token_output"].default == 0
        assert fields["token_total"].default == 0

    def test_validate_helper_passes_valid_response(self):
        """_validate_token_usage ต้องผ่านเมื่อ token values ถูกต้อง"""
        resp = LLMResponse(
            text="test",
            prompt_text="test",
            token_input=100,
            token_output=50,
            token_total=150,
            provider="test",
        )
        result = _validate_token_usage(resp, "test")
        assert result["input"] == 100
        assert result["output"] == 50
        assert result["total"] == 150

    def test_validate_helper_fails_zero_input(self):
        """_validate_token_usage ต้อง fail เมื่อ token_input=0"""
        resp = LLMResponse(
            text="test",
            prompt_text="test",
            token_input=0,
            token_output=50,
            token_total=50,
        )
        with pytest.raises(AssertionError, match="token_input=0"):
            _validate_token_usage(resp, "test")

    def test_validate_helper_fails_zero_output(self):
        """_validate_token_usage ต้อง fail เมื่อ token_output=0"""
        resp = LLMResponse(
            text="test",
            prompt_text="test",
            token_input=100,
            token_output=0,
            token_total=100,
        )
        with pytest.raises(AssertionError, match="token_output=0"):
            _validate_token_usage(resp, "test")

    def test_validate_helper_fails_inconsistent_total(self):
        """_validate_token_usage ต้อง fail เมื่อ total < input + output"""
        resp = LLMResponse(
            text="test",
            prompt_text="test",
            token_input=100,
            token_output=50,
            token_total=100,  # < 100+50
        )
        with pytest.raises(AssertionError, match="token_total"):
            _validate_token_usage(resp, "test")

    def test_validate_helper_fails_excessive_tokens(self):
        """_validate_token_usage ต้อง fail เมื่อ total เกิน threshold"""
        resp = LLMResponse(
            text="test",
            prompt_text="test",
            token_input=5000,
            token_output=6000,
            token_total=11000,
        )
        with pytest.raises(AssertionError, match="exceeds"):
            _validate_token_usage(resp, "test")

    def test_all_providers_have_provider_name(self):
        """ทุก provider class ต้องมี PROVIDER_NAME"""
        from agent_core.llm.client import (
            GeminiClient,
            OpenAIClient,
            ClaudeClient,
            GroqClient,
            DeepSeekClient,
            OllamaClient,
            OpenRouterClient,
            MockClient,
        )

        provider_classes = [
            GeminiClient,
            OpenAIClient,
            ClaudeClient,
            GroqClient,
            DeepSeekClient,
            OllamaClient,
            OpenRouterClient,
            MockClient,
        ]

        for cls in provider_classes:
            assert hasattr(cls, "PROVIDER_NAME"), (
                f"{cls.__name__} missing PROVIDER_NAME"
            )
            assert isinstance(cls.PROVIDER_NAME, str), (
                f"{cls.__name__}.PROVIDER_NAME is not str"
            )
            assert len(cls.PROVIDER_NAME) > 0, f"{cls.__name__}.PROVIDER_NAME is empty"

    def test_prompt_package_creates_correctly(self):
        """PromptPackage ที่ใช้ใน token tests ต้องสร้างได้"""
        assert len(TOKEN_TEST_PROMPT.system) > 0
        assert len(TOKEN_TEST_PROMPT.user) > 0
        assert TOKEN_TEST_PROMPT.step_label == "THOUGHT_FINAL"

        assert len(LONG_TOKEN_TEST_PROMPT.user) > len(TOKEN_TEST_PROMPT.user), (
            "Long prompt should be longer than short prompt"
        )
