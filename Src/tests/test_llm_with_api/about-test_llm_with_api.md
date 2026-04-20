# เอกสาร QA: โฟลเดอร์ `test_llm_with_api`

---

## 1. Overview (ภาพรวม)

โฟลเดอร์ `tests/test_llm_with_api/` คือชุดทดสอบประเภทพิเศษที่ **แตกต่างจาก unit tests และ integration tests โดยสิ้นเชิง** เนื่องจากทุก test ที่มี `@pytest.mark.api` หรือ `@pytest.mark.eval` จะ **ส่ง network request จริงไปยัง LLM API ภายนอก** ในทุกครั้งที่รัน

### ทำไม test_llm_with_api ถึงมีอยู่?

ชุดทดสอบที่ mock ทั้งหมด (unit/integration) ตรวจสอบได้แค่ว่า **โค้ดเรียก API ถูกวิธี** แต่ไม่สามารถตรวจได้ว่า:
- API ยัง **ออนไลน์และยืนยันตัวตนได้** จริงหรือไม่
- LLM ยังตอบ **JSON format ที่ถูกต้อง** หลังจาก provider อัปเดต model
- LLM สามารถ **ตัดสินใจเทรดได้ถูกต้อง** ตาม trading rules ที่กำหนด
- Provider รายงาน **token usage ครบถ้วนและถูกต้อง** ตาม SDK version ล่าสุด

### สิ่งที่ทำให้ต่างจาก test ประเภทอื่น

| มิติ | Unit / Integration Tests | `test_llm_with_api` |
|------|--------------------------|---------------------|
| **Network calls** | ไม่มี — mock ทั้งหมด | **มี** — เรียก Gemini, Groq, OpenAI, Claude จริง |
| **API keys** | ไม่ต้องการ | **ต้องการ** — ขาดแล้ว test skip อัตโนมัติ |
| **ค่าใช้จ่าย** | ฟรี | **มีค่าใช้จ่าย** ต่อ API call |
| **ความเร็ว** | milliseconds | **หลายวินาที** ต่อ call (Gemini ~5s, Groq ~1s) |
| **Determinism** | 100% reproducible | **Non-deterministic** — LLM ตอบต่างกันทุกครั้ง |
| **ความถี่รัน** | ทุก commit | **สัปดาห์ละครั้ง** หรือก่อน deploy เท่านั้น |
| **จุดที่ตรวจสอบ** | Algorithm, logic, SQL | **API connectivity, JSON schema, LLM reasoning quality** |

### วัตถุประสงค์หลัก 3 ประการ

| วัตถุประสงค์ | คำถามที่ตอบ |
|-------------|-----------|
| **Contract Verification** | "LLM provider ยังตอบกลับมา และ JSON format ถูกต้องไหม?" |
| **Quality Evaluation** | "LLM ตัดสินใจเทรดได้ดีแค่ไหนเมื่อเทียบกับ golden dataset?" |
| **Token Accounting** | "Provider รายงาน token usage ถูกต้องและครบถ้วนไหม?" |

### Provider ที่รองรับ

ทดสอบครอบคลุม **8 providers** ผ่าน `agent_core/llm/client.py`:

```
Gemini (Google)   |  OpenAI (GPT)    |  Claude (Anthropic)  |  Groq (LPU)
DeepSeek          |  OpenRouter (proxy — รองรับ 15+ models)  |  Ollama (local)
MockClient        ← รันได้เสมอ ไม่ต้อง API key (ใช้เป็น baseline)
```

### สถิติรวม

| เมตริก | จำนวน |
|--------|-------|
| Test Files | 3 ไฟล์ |
| Test Classes | 27+ คลาส |
| Test Functions | 95+ ฟังก์ชัน |
| Live API Tests (`@api`, `@eval`) | ขึ้นกับ key ที่มี — auto-skip เมื่อไม่มี |
| Non-API Tests (MockClient + Infrastructure) | รันได้เสมอ ไม่ต้อง key |
| API Calls ต่อ Full Run | ~50-80 calls (ถ้ามีครบทุก key) |

---

## 2. Directory Structure & Coverage (โครงสร้างและ Coverage Map)

### โครงสร้างโฟลเดอร์

```
tests/test_llm_with_api/
│
├── test_llm_contract.py        # Contract tests — ตรวจ JSON schema + provider connectivity
├── test_llm_eval.py            # Eval tests — ตรวจคุณภาพการตัดสินใจด้วย golden dataset
├── test_token_usage.py         # Token tests — ตรวจ token reporting + LLMResponse dataclass
└── about-test_llm_with_api.md  # เอกสารนี้
```

### Coverage Map (Test File → Production Code)

```
Production Code                                ← Test File
──────────────────────────────────────────────────────────────────────────────
agent_core/llm/client.py::LLMResponse         ← test_token_usage.py
agent_core/llm/client.py::LLMClient           ← test_llm_contract.py (via subclasses)
agent_core/llm/client.py::GeminiClient        ← test_llm_contract.py, test_llm_eval.py,
                                                 test_token_usage.py
agent_core/llm/client.py::OpenAIClient        ← test_llm_contract.py, test_llm_eval.py,
                                                 test_token_usage.py
agent_core/llm/client.py::ClaudeClient        ← test_llm_contract.py, test_token_usage.py
agent_core/llm/client.py::GroqClient          ← test_llm_contract.py, test_llm_eval.py,
                                                 test_token_usage.py
agent_core/llm/client.py::DeepSeekClient      ← test_llm_contract.py, test_token_usage.py
agent_core/llm/client.py::OpenRouterClient    ← test_llm_contract.py, test_token_usage.py
agent_core/llm/client.py::OllamaClient        ← test_llm_contract.py, test_token_usage.py
agent_core/llm/client.py::MockClient          ← ทุก test file (baseline sanity)
agent_core/llm/client.py::LLMClientFactory    ← test_llm_contract.py, test_token_usage.py
agent_core/core/prompt.py::PromptPackage      ← ทุก test file (สร้าง prompt สำหรับ call)
```

### Provider × Test File Matrix

| Provider | ENV Key Required | Contract | Eval | Token |
|----------|-----------------|:--------:|:----:|:-----:|
| Gemini | `GEMINI_API_KEY` | ✅ | ✅ | ✅ |
| OpenAI | `OPENAI_API_KEY` | ✅ | ✅ | ✅ |
| Claude | `ANTHROPIC_API_KEY` | ✅ | — | ✅ |
| Groq | `GROQ_API_KEY` | ✅ | ✅ | ✅ |
| DeepSeek | `DEEPSEEK_API_KEY` | ✅ | — | ✅ |
| OpenRouter | `OPENROUTER_API_KEY` | ✅ | — | ✅ |
| Ollama (local) | daemon ที่ `localhost:11434` | ✅ | — | ✅ |
| MockClient | **ไม่ต้อง** | ✅ | ✅ | ✅ |

---

## 3. Key Scenarios (สิ่งที่ทดสอบ — สถานการณ์สำคัญ)

### 3.1 `test_llm_contract.py` — Contract Tests

**เป้าหมาย:** ตรวจว่า LLM API ยังเปิดใช้งานได้ และ response format ตรงตาม contract

**Core validation function** `_validate_contract()`:

```python
# 7 checks ที่รันทุก provider
1. response.text ไม่ว่าง และยาวกว่า 2 characters
2. response.provider == provider_name  (PROVIDER_NAME ของ client class)
3. JSON parse ได้ (รองรับ ```json fence, bare {}, และ markdown)
4. มี "signal" field ใน parsed JSON
5. signal ∈ {"BUY", "SELL", "HOLD"}
6. confidence ∈ [0.0, 1.0]  (ถ้ามี field นี้)
7. token_total > 0
```

> **หมายเหตุ:** `response.provider` ตรวจสอบกับ `client.PROVIDER_NAME` ซึ่ง GeminiClient ใช้ค่า  
> `"gemini-3.1-flash-lite-preview"` ไม่ใช่แค่ `"gemini"` — ทุก provider มี PROVIDER_NAME ของตัวเอง

| Class | Provider | Skip Condition | Timeout |
|-------|----------|---------------|---------|
| `TestGeminiContract` | Gemini | `GEMINI_API_KEY` ไม่มี | 30s |
| `TestOpenAIContract` | OpenAI | `OPENAI_API_KEY` ไม่มี | 30s |
| `TestClaudeContract` | Claude | `ANTHROPIC_API_KEY` ไม่มี | 30s |
| `TestGroqContract` | Groq | `GROQ_API_KEY` ไม่มี | **10s** (LPU เร็วกว่า — SLA) |
| `TestDeepSeekContract` | DeepSeek | `DEEPSEEK_API_KEY` ไม่มี | 30s |
| `TestOpenRouterContract` | OpenRouter | `OPENROUTER_API_KEY` ไม่มี | 30s |
| `TestOllamaContract` | Ollama local | `localhost:11434` ไม่ตอบ | 60s |
| `TestMockClientContract` | Mock | **ไม่มี skip** — รันได้เสมอ | — |
| `TestCrossProviderConsistency` | หลาย providers | มี key น้อยกว่า 2 | 30s ×N |

**Test scenarios เพิ่มเติมใน Contract:**

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Response latency | Performance | ตรวจว่าตอบภายใน timeout (Gemini < 30s, Groq < 10s) |
| Model name ไม่ว่าง | Contract | `response.model` ต้องไม่เป็น empty string |
| Rationale optional | Soft assert | ถ้าไม่มี rationale → `pytest.skip` ไม่ใช่ fail |
| MockClient custom response_map | Unit | `response_map` override ทำงาน: signal="BUY", confidence=0.95 |
| MockClient is_available() | Unit | ต้อง return True เสมอ ไม่ขึ้นกับ environment |
| Cross-provider field consistency | Contract | ทุก provider ที่มี key ต้องมี "signal" field ใน JSON |

---

### 3.2 `test_llm_eval.py` — Quality Evaluation Tests

**เป้าหมาย:** วัดว่า LLM "ตัดสินใจเทรดได้ดีแค่ไหน" โดยเทียบกับ golden dataset ที่มี expected answers

#### Golden Dataset — 8 Scenarios

แต่ละ scenario ประกอบด้วย market data ครบ 11 fields: `price`, `rsi`, `rsi_signal`, `macd`, `macd_hist`, `trend`, `ema20`, `ema50`, `bb_signal`, `atr`, `news_sentiment`

| ชื่อ Scenario | Expected | Acceptable | เหตุผล |
|---------------|----------|-----------|--------|
| RSI oversold (28) + uptrend + bullish MACD | **BUY** | {BUY} | Classic buy signal — ทุกตัวชี้ขึ้น |
| Moderate uptrend + positive news | **BUY** | {BUY, HOLD} | HOLD ก็โอเคเพราะสัญญาณไม่ strong |
| RSI overbought (82) + downtrend + bearish MACD | **SELL** | {SELL} | Strong sell — ทุกตัวชี้ลง |
| Death cross + negative sentiment | **SELL** | {SELL, HOLD} | Ambiguous — bearish แต่ไม่ extreme |
| Sideways + neutral RSI (50) + no MACD signal | **HOLD** | {HOLD} | ไม่มีทิศทางชัดเจน |
| Mixed signals — RSI 68 + uptrend | **HOLD** | {HOLD, BUY} | Approaching overbought แต่ trend ยังขึ้น |
| Extreme overbought — RSI 92 + bearish ทุกอย่าง | **SELL** | {SELL} | Must sell — ไม่มีข้อโต้แย้ง |
| Extreme oversold — RSI 15 + strong bullish reversal | **BUY** | {BUY} | Must buy — ไม่มีข้อโต้แย้ง |

#### Rule Scenarios — 2 Hard Behavioral Rules

```python
# Hard rules ที่ LLM ต้องไม่ฝ่า
1. Never BUY when RSI > 80  →  forbidden_signal = "BUY"
   (scenario: RSI=85, bullish MACD, uptrend, positive news)
   
2. Never SELL when RSI < 20  →  forbidden_signal = "SELL"
   (scenario: RSI=18, bearish MACD, downtrend, negative news)
```

#### Threshold-Based Assertions

```python
# Exact accuracy ≥ 50%   — ดีกว่า random 33%
assert eval_results["accuracy_pct"] >= 50

# Acceptable accuracy ≥ 70%  — รวม alternative ที่โอเค
assert eval_results["acceptable_pct"] >= 70

# Rule compliance ≤ 30% violation rate
assert rule_result["violation_rate"] <= 30

# ไม่ hard fail สำหรับ confidence correlation — ใช้ pytest.skip แทน
if avg_correct <= avg_wrong:
    pytest.skip("Confidence not correlated (acceptable for LLMs)")
```

| Class | Provider | Marker | Tests |
|-------|----------|--------|-------|
| `TestGeminiEval` | Gemini | `@eval` | accuracy, acceptable, parse errors, JSON format, rule compliance, confidence correlation |
| `TestGroqEval` | Groq | `@eval` | accuracy, acceptable, parse errors |
| `TestOpenAIEval` | OpenAI | `@eval` | accuracy, acceptable, parse errors |
| `TestMockClientEval` | Mock | ไม่มี marker | infrastructure sanity (MockClient คืน HOLD → ตรงแค่ HOLD scenarios) |
| `TestGoldenDatasetSanity` | ไม่ต้อง API | ไม่มี marker | dataset integrity: required fields, expected ∈ acceptable, balanced BUY/SELL/HOLD |

---

### 3.3 `test_token_usage.py` — Token Usage Tracking Tests

**เป้าหมาย:** ตรวจว่า `LLMResponse` dataclass รายงาน `token_input`, `token_output`, `token_total` ถูกต้อง และสม่ำเสมอ

**Core validation function** `_validate_token_usage()`:

```python
# 7 checks ต่อทุก response
1. isinstance(token_input, int)                      # type check
2. isinstance(token_output, int)
3. isinstance(token_total, int)
4. token_input >= 10                                 # prompt ต้องมี tokens
5. token_output >= 5                                 # response ต้องมี tokens
6. token_total >= token_input + token_output         # math consistency
7. token_total <= 10,000                             # sanity: prompt สั้นไม่ควรเกิน
```

**Prompts ที่ใช้ทดสอบ:**

| Prompt | ขนาด | วัตถุประสงค์ |
|--------|------|-----------|
| `TOKEN_TEST_PROMPT` | สั้น (~100 tokens) | baseline token count |
| `LONG_TOKEN_TEST_PROMPT` | ยาว (~250 tokens) | ตรวจว่า input tokens เพิ่มตามขนาด |
| `MULTI_CALL_PROMPTS` | 3 prompts ต่างกัน | ตรวจว่าทุก call รายงาน tokens |

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Basic token reporting | Contract | input, output, total > 0 |
| Longer prompt → more input tokens | Proportionality | `LONG_PROMPT.token_input > SHORT_PROMPT.token_input` |
| Token consistency across 3 calls | Reliability | ทุก call รายงาน tokens สม่ำเสมอ |
| MockClient returns zeros | Baseline | token_input=0, output=0, total=0 (ไม่ใช้ API จริง) |
| token_total can exceed input+output | Edge Case | บาง provider นับ system overhead แยก |
| Cross-provider token ratio | Comparison | max ≤ min × 5 (tokenizer ต่างกันแต่ order of magnitude ใกล้กัน) |

**Infrastructure tests (ไม่เรียก API):**

| Test Class | วัตถุประสงค์ |
|-----------|-----------|
| `TestLLMResponseSanity` | `LLMResponse` dataclass: default values, custom values, prompt_text stored |
| `TestMockClientTokenUsage` | MockClient: token=0, type=int, fields ครบ |
| `TestTokenUsageInfrastructure` | validate helper: pass valid, fail zero input, fail zero output, fail inconsistent total, fail excessive tokens, ทุก provider มี `PROVIDER_NAME` |

---

## 4. Testing Flow — Live API Architecture (สถาปัตยกรรมการทดสอบ)

### Lifecycle ของ 1 Live API Test

```mermaid
flowchart TD
    A[pytest runner] --> B{HAS_XXX_KEY?}

    B -->|False| C[⏭️ pytest.mark.skipif\nAuto-skip — no failure in CI]
    B -->|True| D[โหลด API key\nจาก os.environ]

    D --> E{Provider type?}
    E -->|Cloud API| F[สร้าง Client instance\nเช่น GeminiClient]
    E -->|Ollama local| G[_ollama_running\nHTTP GET localhost:11434/api/tags]

    G -->|ไม่ตอบ| H[⏭️ skipif — skip gracefully]
    G -->|ตอบ 200| F

    F --> I[client.call\nPromptPackage]
    I --> J[HTTPS Request\nไปยัง external API]

    J -->|Success| K[LLMResponse\ntext + tokens + model + provider]
    J -->|Timeout / 4xx / 5xx| L[@with_retry decorator\nmax_attempts=3, exponential backoff]
    L -->|All 3 fail| M[LLMProviderError raised\n→ test fails with clear message]
    L -->|Retry success| K

    K --> N[_validate_contract\nหรือ _validate_token_usage\nAssert SCHEMA ไม่ใช่ exact string]
    N --> O{Pass?}
    O -->|Yes| P[✅ Provider contract verified]
    O -->|No| Q[❌ Report finding\nProvider broken or format changed]
```

### การโหลด API Keys อย่างปลอดภัย

Keys ถูกโหลดจาก environment variables เท่านั้น — ผ่าน 2 ช่องทาง:

```
1. Src/.env file → โหลดโดย python-dotenv ที่ app startup
2. os.environ โดยตรง → ใช้ตอนรัน test จาก CLI (set KEY=xxx && pytest)
```

```python
# Pattern ใน agent_core/llm/client.py — ไม่ hardcode key ใน code
self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
# ^ raise KeyError ถ้าไม่มี — fail fast ที่ client creation ไม่ใช่ตอน call

# Pattern ใน test files — ตรวจก่อน skip
HAS_GEMINI_KEY = bool(os.environ.get("GEMINI_API_KEY"))  # ไม่ raise

@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="GEMINI_API_KEY not set")
class TestGeminiContract:
    ...
```

> **ความแตกต่างสำคัญ:**  
> `os.environ.get()` → ใช้ใน test files (ไม่ raise, คืน None)  
> `os.environ["KEY"]` → ใช้ใน client.py (raise KeyError เมื่อไม่มี key)

### Non-Deterministic Assertions — หลักการสำคัญที่สุด

เนื่องจาก LLM ตอบต่างกันทุกครั้ง test ต้องยึดหลัก **"assert schema, not string"**:

```python
# ❌ ผิด — exact string match จะ fail ใน run ถัดไปเสมอ
assert response.text == '{"signal": "BUY", "confidence": 0.82, "rationale": "RSI oversold bounce"}'

# ❌ ผิด — exact float
assert data["confidence"] == 0.82

# ❌ ผิด — reasoning field
assert data["rationale"] == "RSI oversold bounce near support"

# ✅ ถูกต้อง — assert enum (finite set)
assert data["signal"] in ("BUY", "SELL", "HOLD")

# ✅ ถูกต้อง — assert range
assert 0.0 <= float(data["confidence"]) <= 1.0

# ✅ ถูกต้อง — assert type
assert isinstance(response.token_total, int)

# ✅ ถูกต้อง — assert key presence
assert "signal" in data

# ✅ ถูกต้อง — assert threshold
assert eval_results["accuracy_pct"] >= 50   # "ดีกว่า random 33%" ไม่ใช่ "ถูกทุก case"

# ✅ ถูกต้อง — pytest.skip สำหรับ soft assertion
if "rationale" not in data:
    pytest.skip("Gemini did not include rationale (acceptable)")
```

**Acceptable Sets — สำหรับ scenario ที่ ambiguous:**

```python
# ✅ ออกแบบให้รับหลายคำตอบที่สมเหตุสมผล
{
    "name": "Moderate uptrend + positive news",
    "expected": "BUY",             # คำตอบที่ดีที่สุด
    "acceptable": {"BUY", "HOLD"}, # HOLD ก็โอเค — สัญญาณไม่ strong พอ
}
```

### Retry Architecture — 2 ชั้น

Production code มี 2 ชั้นการ retry ที่ test จะกระทบถ้า API มีปัญหา:

```
ชั้นที่ 1: @with_retry(max_attempts=3, delay=2s)
  → Decorator บน call() ของทุก provider (GeminiClient, ClaudeClient, GroqClient, ฯลฯ)
  → Exponential backoff: attempt 1 → sleep 2s, attempt 2 → sleep 4s
  → Retry เมื่อ: LLMProviderError (network error, 5xx, timeout)
  → ไม่ retry เมื่อ: 401 Unauthorized, 400 Bad Request

ชั้นที่ 2: FallbackChainClient (production use)
  → ลอง provider ตามลำดับ: gemini → groq → mock
  → Failure Domain: ถ้า gemini-3.1 fail → domain="google" marked failed
                    → gemini-2.5, gemini-2.0 ถูก skip ทันที (ลด latency)
  → is_available() ตรวจก่อน call — skip provider ที่ไม่พร้อมโดยไม่ต้อง try
```

> **หมายเหตุ:** `FallbackChainClient` ครอบคลุมโดย `test_llm/test_fallback.py` (authoritative, 9 classes, ~40 tests)  
> `@with_retry` ครอบคลุมโดย `test_llm/test_llm_client_errors.py::TestWithRetry` (6 tests, mock sleep)  
> ทั้งคู่ไม่ต้องซ้ำใน test_llm_with_api/ — folder นี้เน้น contract tests กับ API จริงเท่านั้น

### JSON Parsing Pipeline

LLM บางตัวใส่ markdown fence แม้ถูกบอกไม่ให้ใส่ — production code และ test helper ต้องรองรับ:

```python
# Production: agent_core/llm/client.py::_extract_json_block()
def _extract_json_block(text: str) -> str:
    # 1. ```json { ... } ``` fence
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return fence.group(1)
    # 2. bare { ... } (first occurrence)
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return brace.group(0)
    return text  # fallback — ให้ caller จัดการ

# Production: agent_core/llm/client.py::_strip_think()
# ใช้ใน GroqClient, OllamaClient (Qwen3.5 model มี <think> blocks)
def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

# Test helper: _parse_llm_json() ใน test_llm_contract.py และ test_llm_eval.py
def _parse_llm_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    return json.loads(match.group() if match else cleaned)
```

---

## 5. QA Standards & Conventions (มาตรฐาน QA สำหรับ Live LLM Tests)

### 5.1 Marker Rules — ใช้ marker ที่ถูกต้องเสมอ

```python
# ตารางสรุป markers ที่ใช้จริงใน test_llm_with_api/
@pytest.mark.api    # ใน test_llm_contract.py, test_token_usage.py
                    # → Live API calls → ต้องมี key → excluded from default run
@pytest.mark.eval   # ใน test_llm_eval.py
                    # → Quality evaluation → expensive (~15-30 calls/run)
# (no marker)       # MockClient + Infrastructure tests → รันได้เสมอ ไม่ต้อง key
```

```python
# ✅ ถูกต้อง — live API test class ต้องมี marker + skipif คู่กันเสมอ
@pytest.mark.api
@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="GEMINI_API_KEY not set")
class TestGeminiContract:
    ...

# ✅ ถูกต้อง — eval marker สำหรับ golden dataset
@pytest.mark.eval
@pytest.mark.skipif(not HAS_GROQ_KEY, reason="GROQ_API_KEY not set")
class TestGroqEval:
    ...

# ✅ ถูกต้อง — ไม่มี marker สำหรับ MockClient (รันได้เสมอ)
class TestMockClientContract:
    ...

# ✅ ถูกต้อง — local service ใช้ function check แทน env var check
@pytest.mark.skipif(not _ollama_running(), reason="Ollama not running at localhost:11434")
class TestOllamaContract:
    ...
```

### 5.2 Cost & Speed Constraint — ประหยัด tokens เสมอ

LLM API มีค่าใช้จ่ายจริง — ทุก test ต้องใช้ **prompt ที่สั้นที่สุด** ที่ยังทดสอบ contract ได้

```python
# ✅ ถูกต้อง — contract prompt สั้น (<150 tokens)
CONTRACT_USER_PROMPT = """Current gold market:
- Price: 45,000 THB/baht (฿72,000/gram)
- RSI(14): 55 (neutral)
- MACD: bullish crossover
What is your trading decision? Respond with JSON only."""

# ✅ ถูกต้อง — rate limit protection ระหว่าง consecutive calls
time.sleep(0.5)

# ✅ ถูกต้อง — scope="class" เพื่อรัน golden dataset ครั้งเดียว
@pytest.fixture(scope="class")
def eval_results(self, gemini_client):
    """รัน 8 API calls ครั้งเดียว — share ผลกับทุก test method ใน class"""
    return _run_eval_suite(gemini_client, GOLDEN_SCENARIOS, "gemini")

# ❌ ผิด — scope="function" จะรัน 8 calls × จำนวน test methods
@pytest.fixture  # default = function scope
def eval_results(self, client):  # ❌ รัน 8 calls ทุกครั้ง
    ...
```

**ค่าใช้จ่ายโดยประมาณต่อ full run (provider เดียว):**

| Test File | API Calls | ความถี่แนะนำ |
|-----------|----------|-------------|
| `test_llm_contract.py` | ~1-3 calls | สัปดาห์ละครั้ง |
| `test_llm_eval.py` | ~10 calls (8 golden + 2 rules) | ก่อน deploy / เปลี่ยน prompt |
| `test_token_usage.py` | ~5 calls | ก่อน deploy / หลังอัพเดท SDK |

### 5.3 Non-Deterministic Assertions — กฎการ assert

**หลักสำคัญ:** NEVER assert exact strings สำหรับ LLM reasoning fields

| Assert Type | ✅ ทำได้ | ❌ ห้ามทำ |
|-------------|---------|---------|
| Enum | `signal in ("BUY", "SELL", "HOLD")` | `signal == "BUY"` |
| Range | `0 <= confidence <= 1` | `confidence == 0.82` |
| Type | `isinstance(token_total, int)` | — |
| Key presence | `"signal" in data` | — |
| Threshold | `accuracy_pct >= 50` | `accuracy_pct == 75` |
| Latency | `elapsed < 30` | — |
| Soft assertion | `pytest.skip("...")` | `pytest.fail("...")` สำหรับ subjective fields |
| Exact string | — | `response.text == '{"signal":...'` |
| Exact rationale | — | `data["rationale"] == "RSI oversold"` |

### 5.4 Environment Requirement — Skip อย่างถูกต้อง

```python
# ✅ ถูกต้อง — ตรวจ key ที่ module level (ครั้งเดียวตอน import)
HAS_GEMINI_KEY = bool(os.environ.get("GEMINI_API_KEY"))

# ✅ ถูกต้อง — skipif ที่ class level (skip ทั้ง class เลย)
@pytest.mark.skipif(not HAS_GEMINI_KEY, reason="GEMINI_API_KEY not set")
class TestGeminiContract:
    ...

# ✅ ถูกต้อง — local service check แบบ function call
def _ollama_running() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

# ❌ ผิด — ให้ test fail เมื่อไม่มี key (ทำให้ CI fail ทุกคน ที่ไม่มี key)
def test_gemini_live():
    client = GeminiClient()  # ❌ raise LLMUnavailableError ถ้าไม่มี GEMINI_API_KEY
```

### 5.5 Fixture Scope สำหรับ Live Tests

| Scope | ใช้เมื่อ | ตัวอย่างใน codebase |
|-------|---------|------------------|
| `scope="class"` | Client instance + eval results — expensive, stateless | `gemini_client`, `eval_results` |
| ใน test method เอง | MockClient, LLMResponse construct ตรงๆ | `TestMockClientTokenUsage` |
| `scope="function"` (default) | ไม่มีใน test_llm_with_api — ทุก fixture เป็น class scope | — |

### 5.6 MockClient — Baseline Sanity Rule

ทุก test file ต้องมี MockClient test ที่ **รันได้เสมอโดยไม่ต้อง API key**:

```
ถ้า MockClient contract fail → test infrastructure พัง (ไม่ใช่ provider พัง)
ถ้า MockClient ผ่านแต่ GeminiClient fail → Gemini API มีปัญหา
```

```python
# MockClient behavior ที่ test ตรวจสอบ
- call() คืน LLMResponse เสมอ (ไม่ raise)
- provider = "mock"
- token_input = 0, token_output = 0, token_total = 0
- is_available() = True เสมอ
- response_map inject ได้ — สำหรับ test ที่ต้องการ response เฉพาะ
- DEFAULT_MOCK_RESPONSES: HOLD สำหรับ THOUGHT_FINAL
```

### 5.7 Rate Limiting Protection

```python
# ✅ ถูกต้อง — sleep ระหว่าง consecutive calls ใน eval loop
for scenario in scenarios:
    response = client.call(prompt)
    ...
    time.sleep(0.5)   # rate limit safety — Groq เป็นพิเศษที่ strict

# ✅ ถูกต้อง — scope="class" ป้องกัน redundant calls
@pytest.fixture(scope="class")
def gemini_client(self):
    return GeminiClient()   # สร้าง client ครั้งเดียว share ทั้ง class
```

---

## 6. How to Run (วิธีรัน)

> ⚠️ **คำเตือน:** ทุก test ที่มี `@pytest.mark.api` หรือ `@pytest.mark.eval` ส่ง network call จริงและมีค่าใช้จ่าย — **ไม่รันในทุก commit**

**ทุกคำสั่งรันจาก directory `Src/`**

### ตรวจสอบ API Keys ก่อนรัน

```bash
# Unix/Mac — ตรวจว่า key พร้อม
echo "Gemini:     ${GEMINI_API_KEY:+✅ set}"
echo "Groq:       ${GROQ_API_KEY:+✅ set}"
echo "OpenAI:     ${OPENAI_API_KEY:+✅ set}"
echo "Claude:     ${ANTHROPIC_API_KEY:+✅ set}"
echo "DeepSeek:   ${DEEPSEEK_API_KEY:+✅ set}"
echo "OpenRouter: ${OPENROUTER_API_KEY:+✅ set}"

# Windows — set key แบบ one-shot (&&ต้องติดกัน ไม่มีช่องว่าง)
set GROQ_API_KEY=gsk_xxx&& python -m pytest tests/test_llm_with_api/ -v -k groq
```

### รัน Contract Tests (ตรวจ connectivity)

```bash
cd Src

# รัน contract tests ทุก provider (skip อัตโนมัติถ้าไม่มี key)
pytest tests/test_llm_with_api/test_llm_contract.py -m api -v

# รันเฉพาะ provider ที่ต้องการ
pytest tests/test_llm_with_api/test_llm_contract.py -v -m api -k groq
pytest tests/test_llm_with_api/test_llm_contract.py -v -m api -k gemini
pytest tests/test_llm_with_api/test_llm_contract.py -v -m api -k claude

# รันเฉพาะ MockClient (ไม่ต้อง key, รันได้เสมอ)
pytest tests/test_llm_with_api/test_llm_contract.py -v -k "Mock"

# รัน cross-provider consistency (ต้องมีอย่างน้อย 2 keys)
pytest tests/test_llm_with_api/test_llm_contract.py::TestCrossProviderConsistency -v
```

### รัน Eval Tests (ตรวจคุณภาพ — expensive)

```bash
# รัน eval ทั้งหมด (~10 API calls ต่อ provider)
pytest tests/test_llm_with_api/test_llm_eval.py -m eval -v

# รัน eval เฉพาะ provider
pytest tests/test_llm_with_api/test_llm_eval.py -v -k "Gemini"
pytest tests/test_llm_with_api/test_llm_eval.py -v -k "Groq"

# รัน MockClient baseline + golden dataset sanity (ไม่ต้อง key)
pytest tests/test_llm_with_api/test_llm_eval.py -v -k "Mock or Sanity"

# รัน dataset validation เท่านั้น (ไม่เรียก API เลย)
pytest tests/test_llm_with_api/test_llm_eval.py::TestGoldenDatasetSanity -v
```

### รัน Token Usage Tests

```bash
# รัน token tests ทุก provider
pytest tests/test_llm_with_api/test_token_usage.py -m api -v

# รัน Mock + Infrastructure เท่านั้น (ไม่ต้อง key)
pytest tests/test_llm_with_api/test_token_usage.py -v -k "Mock or Sanity or Infrastructure"

# รัน LLMResponse dataclass sanity
pytest tests/test_llm_with_api/test_token_usage.py::TestLLMResponseSanity -v
pytest tests/test_llm_with_api/test_token_usage.py::TestTokenUsageInfrastructure -v
```

### รันทั้งโฟลเดอร์

```bash
# รัน test_llm_with_api ทั้งหมด (skip provider ที่ไม่มี key อัตโนมัติ)
pytest tests/test_llm_with_api/ -v

# รันเฉพาะ live tests (api + eval markers)
pytest tests/test_llm_with_api/ -m "api or eval" -v

# Dry run — ดู test list โดยไม่รัน
pytest tests/test_llm_with_api/ --collect-only -q

# ดูว่า test ไหนจะถูก skip
pytest tests/test_llm_with_api/ -m api --collect-only -v 2>&1 | grep -E "SKIP|selected"
```

### ยืนยัน Default pytest ไม่รัน live tests

```bash
# รัน default (ต้องไม่รวม api/eval)
cd Src && pytest

# ตรวจ pyproject.toml ว่า addopts exclude ถูกต้อง
# ควรเป็น: addopts = "-m 'not llm and not slow and not api and not eval'"
```

---

## Appendix: QA Notes & Design Decisions

| รายการ | ไฟล์ | สถานะ | รายละเอียด |
|--------|------|-------|-----------|
| Marker mismatch | ทุกไฟล์ | ✅ แก้แล้ว | `pyproject.toml` อัปเดต `addopts` เป็น `not llm and not slow and not api and not eval` — default `pytest` ไม่รัน live tests อีกต่อไป |
| ไม่มี `pytestmark` module-level | ทุกไฟล์ | By Design | ใช้ `@pytest.mark.skipif` ที่ class level แทน — ทำให้ MockClient (ไม่มี marker) รันได้เสมอ ซึ่งเป็น intentional baseline behavior |
| `FallbackChainClient` test | test_llm_contract.py | ✅ Consolidated | Authoritative tests อยู่ใน `test_llm/test_fallback.py` (9 classes, ~40 tests) — ไม่ต้องซ้ำใน test_llm_with_api/ |
| `@with_retry` test | test_llm_contract.py | ✅ Consolidated | Authoritative tests อยู่ใน `test_llm/test_llm_client_errors.py::TestWithRetry` (6 tests, mock sleep) — ไม่ต้องซ้ำใน test_llm_with_api/ |
| Groq timeout = 10s (strict) | test_llm_contract.py | Intentional | Groq LPU inference ควรเร็วกว่า cloud API — 10s เป็น performance SLA ไม่ใช่แค่ sanity check |
| `GeminiClient.PROVIDER_NAME` ≠ "gemini" | test_llm_contract.py | Known | PROVIDER_NAME = "gemini-3.1-flash-lite-preview" — contract test ตรวจกับ `client.PROVIDER_NAME` ไม่ใช่ hardcoded "gemini" |
| `_strip_think()` ใน Groq/Ollama | client.py | By Design | Groq ใช้ Llama3.3-70b ซึ่งไม่มี thinking blocks, แต่ OllamaClient ใช้ Qwen3.5 ที่มี `<think>` blocks — strip ก่อน _extract_json_block() |

> **กฎ QA:** ถ้า provider เปลี่ยน response format → รายงานเป็น finding ก่อน อย่าแก้ test เพื่อ "ปรับตาม" response ใหม่โดยไม่ตรวจสอบว่า production รองรับแล้ว

---


