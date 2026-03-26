# GoldTrader — Agent Architecture Documentation

---

## 1. Overview

**GoldTrader** คือ ReAct+LLM trading agent สำหรับวิเคราะห์ตลาดทองคำ โดยใช้การผสมผสานระหว่าง Technical Indicators และ AI Reasoning แบบ multi-step

- **Agent Type**: ReAct (Reasoning + Acting) Loop
- **Data Source**: yfinance (OHLCV), News Fetcher
- **LLM Support**: Gemini, Claude, OpenAI, Groq, DeepSeek, Mock
- **UI**: Gradio Dashboard (3-panel display)
- **Database**: PostgreSQL (`database.py`)

---

## 2. Project Structure

```
Src/
├── agent_core/
│   ├── config/
│   │   ├── roles.json          # Role definitions (analyst, risk_manager, etc.)
│   │   └── skills.json         # Skill & tool registry
│   ├── core/
│   │   ├── __init__.py
│   │   ├── prompt.py           # PromptBuilder, SkillRegistry, RoleRegistry
│   │   └── react.py            # ReactOrchestrator, ReactState, ReactConfig
│   ├── data/
│   │   ├── latest.json         # Cached market state (auto-updated)
│   │   └── payload_*.json      # Historical payloads
│   └── llm/
│       ├── __init__.py
│       ├── client.py           # All LLM clients + LLMClientFactory
│       └── test_client.py
├── data_engine/
│   ├── fetcher.py              # GoldDataFetcher (yfinance)
│   ├── indicators.py           # TechnicalIndicators (RSI, MACD, etc.)
│   ├── newsfetcher.py          # GoldNewsFetcher
│   └── orchestrator.py        # GoldTradingOrchestrator
├── Output/
│   └── result_output.json      # Agent output
├── dashboard.py                # Gradio UI entry point
├── database.py                 # PostgreSQL handler (RunDatabase)
├── main.py                     # CLI entry point
└── requirements.txt
```

---

## 3. Full Flow Diagram

# GoldTrader — Full Flow Diagram (Class & Method Level)

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         GOLDTRADER EXECUTION FLOW                              ║
║                    (Class-level · Method-level · Data-level)                   ║
╚══════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────┐     ┌──────────────────────────────────────┐
│         dashboard.py            │     │              main.py                 │
│  (Gradio UI — 3 panel display)  │     │  argparse: --provider, --iterations  │
│                                 │     │            --skip-fetch, --output    │
│  gr.Dropdown: provider          │     └──────────────────┬───────────────────┘
│  gr.Dropdown: period            │                        │
│  gr.Dropdown: interval          │                        │ (skip_fetch=False)
└───────────────┬─────────────────┘                        │
                │                                          ▼
                │                  ┌───────────────────────────────────────────┐
                │                  │        GoldTradingOrchestrator            │
                │                  │            orchestrator.py                │
                │                  │                                           │
                │                  │  __init__(history_days, interval,         │
                │                  │           max_news_per_cat, output_dir)   │
                │                  │    self.price_fetcher = GoldDataFetcher() │
                │                  │    self.news_fetcher  = GoldNewsFetcher() │
                │                  │                                           │
                │                  │  .run(save_to_file=True)                  │
                └──────────────────►    │                                      │
                                   │   ├─ Step 1: price_fetcher.fetch_all()   │
                                   │   │    ├── .fetch_gold_spot_usd()        │
                                   │   │    │     GET gold-api.com/price/XAU  │
                                   │   │    │     → { price_usd_per_oz }      │
                                   │   │    │                                  │
                                   │   │    ├── .fetch_usd_thb_rate()         │
                                   │   │    │     GET exchangerate-api.com    │
                                   │   │    │     → { usd_thb }               │
                                   │   │    │                                  │
                                   │   │    ├── .calc_thai_gold_price()       │
                                   │   │    │     GET intergold.co.th (scrape)│
                                   │   │    │     BeautifulSoup → buy/sell    │
                                   │   │    │     [Fallback: formula calc]    │
                                   │   │    │     → { sell_price_thb,        │
                                   │   │    │         buy_price_thb, spread } │
                                   │   │    │                                  │
                                   │   │    └── .fetch_historical_ohlcv()     │
                                   │   │          yf.Ticker("GC=F")           │
                                   │   │          .history(period, interval)  │
                                   │   │          → pd.DataFrame              │
                                   │   │            [open,high,low,close,vol] │
                                   │   │                                       │
                                   │   ├─ Step 2: TechnicalIndicators(ohlcv_df)
                                   │   │    .to_dict() → .compute_all()       │
                                   │   │    │                                  │
                                   │   │    ├── .rsi(period=14)               │
                                   │   │    │     Wilder EWM smoothing        │
                                   │   │    │     → RSIResult(value, signal,  │
                                   │   │    │                 period)         │
                                   │   │    │                                  │
                                   │   │    ├── .macd(fast=12,slow=26,sig=9)  │
                                   │   │    │     EMA fast/slow → macd_line   │
                                   │   │    │     → MACDResult(macd_line,     │
                                   │   │    │       signal_line, histogram,   │
                                   │   │    │       crossover)                │
                                   │   │    │                                  │
                                   │   │    ├── .bollinger_bands(period=20)   │
                                   │   │    │     SMA ± 2σ                    │
                                   │   │    │     → BollingerResult(upper,    │
                                   │   │    │       middle, lower, pct_b)     │
                                   │   │    │                                  │
                                   │   │    ├── .atr(period=14)               │
                                   │   │    │     True Range EWM              │
                                   │   │    │     → ATRResult(value,          │
                                   │   │    │       volatility_level)         │
                                   │   │    │                                  │
                                   │   │    └── .trend()                      │
                                   │   │          EMA20, EMA50, SMA200        │
                                   │   │          → TrendResult(ema_20,       │
                                   │   │            ema_50, sma_200, trend,   │
                                   │   │            golden_cross, death_cross)│
                                   │   │                                       │
                                   │   ├─ Step 3: news_fetcher.to_dict()      │
                                   │   │    GoldNewsFetcher (yfinance-based)  │
                                   │   │    → { by_category, total_articles } │
                                   │   │                                       │
                                   │   └─ Step 4+5: Assemble + Save JSON      │
                                   │        → agent_core/data/latest.json     │
                                   │        → agent_core/data/payload_*.json  │
                                   └───────────────────┬───────────────────────┘
                                                       │
                                          market_state dict:
                                          { meta, market_data,
                                            technical_indicators, news }
                                                       │
                                                       ▼
                              ┌────────────────────────────────────────────┐
                              │            ReactOrchestrator               │
                              │                react.py                    │
                              │                                            │
                              │  __init__(llm_client, prompt_builder,      │
                              │           tool_registry, config)           │
                              │                                            │
                              │  .run(market_state)                        │
                              │    │                                       │
                              │    ├─ [IF max_tool_calls == 0]  ◄── default│
                              │    │   (Fast path — no loop)               │
                              │    │   prompt_builder                      │
                              │    │     .build_final_decision(            │
                              │    │        market_state, [])              │
                              │    │     → PromptPackage(system, user,     │
                              │    │                     "THOUGHT_FINAL")  │
                              │    │   llm.call(prompt) → raw str          │
                              │    │   extract_json(raw) → parsed dict     │
                              │    │   _build_decision(parsed) → result    │
                              │    │                                       │
                              │    └─ [IF max_tool_calls > 0]              │
                              │        ReactState(market_state,            │
                              │                  tool_results=[],          │
                              │                  iteration=0)              │
                              │        │                                   │
                              │        └─► LOOP (while iter < max_iter)   │
                              │              │                             │
                              │              ├─ THOUGHT ─────────────────►│
                              │              │   prompt_builder            │
                              │              │     .build_thought(         │
                              │              │        market_state,        │
                              │              │        tool_results,        │
                              │              │        iteration)           │
                              │              │     → PromptPackage         │
                              │              │       ("THOUGHT_N")         │
                              │              │   llm.call(prompt) → raw    │
                              │              │   extract_json(raw)→thought │
                              │              │   state.react_trace.append()│
                              │              │                             │
                              │              ├─ ACTION: FINAL_DECISION ──►│
                              │              │   _build_decision(thought)  │
                              │              │   break                     │
                              │              │                             │
                              │              ├─ ACTION: CALL_TOOL ───────►│
                              │              │   _execute_tool(            │
                              │              │     tool_name, tool_args)   │
                              │              │     → ToolResult(tool_name, │
                              │              │       status, data, error)  │
                              │              │   state.tool_results +=     │
                              │              │   state.tool_call_count++   │
                              │              │   continue                  │
                              │              │                             │
                              │              └─ MAX ITER / UNKNOWN ──────►│
                              │                  prompt_builder            │
                              │                    .build_final_decision() │
                              │                  llm.call() → forced HOLD  │
                              │                  [fallback_decision()]     │
                              └──────────────────────┬─────────────────────┘
                                                     │
                                          ┌──────────┴──────────┐
                                          ▼                     ▼
                              ┌─────────────────────┐  ┌──────────────────────┐
                              │   final_decision     │  │    react_trace       │
                              │   {                  │  │    [                 │
                              │    signal: BUY|      │  │     { step,          │
                              │            SELL|HOLD │  │       iteration,     │
                              │    confidence: 0–1   │  │       response }     │
                              │    entry_price       │  │    ]                 │
                              │    stop_loss         │  │    iterations_used   │
                              │    take_profit       │  │    tool_calls_used   │
                              │    rationale         │  └──────────────────────┘
                              │   }                  │
                              └──────────┬───────────┘
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                   ┌──────────────────┐  ┌──────────────────────┐
                   │  dashboard.py    │  │  Output JSON file    │
                   │  Panel 1: Market │  │  (--output path)     │
                   │    price/RSI/MACD│  │                      │
                   │  Panel 2: Trace  │  │  RunDatabase         │
                   │    react_trace   │  │  .save_run(          │
                   │  Panel 3: Signal │  │    provider, result, │
                   │    BUY/SELL/HOLD │  │    market_state)     │
                   │    confidence    │  │  → PostgreSQL INSERT │
                   └──────────────────┘  └──────────────────────┘
```

---

## PromptBuilder Internal Flow

```
PromptBuilder.__init__(role_registry, AIRole.ANALYST)
│
├── .build_final_decision(market_state, tool_results)
│     │
│     ├── _require_role() → RoleRegistry.get(AIRole.ANALYST)
│     │     → RoleDefinition(name, title, system_prompt_template,
│     │                      available_skills)
│     │
│     ├── system = "You are a {title}. Output FINAL_DECISION JSON..."
│     │
│     ├── user = _format_market_state(market_state)
│     │           ├── spot price, RSI, MACD (compact 1-line each)
│     │           └── top-sentiment news per category
│     │           + _format_tool_results(tool_results)
│     │
│     └── → PromptPackage(system, user, step_label="THOUGHT_FINAL")
│
└── .build_thought(market_state, tool_results, iteration)
      │
      ├── _require_role() + get_tools_for_skills()
      │     SkillRegistry.get_tools_for_skills(available_skills)
      │     → list[tool_name]
      │
      ├── user = f"## Iteration {N}\n{market_state}\n{tool_results}\n
      │           Instructions: respond JSON with action=CALL_TOOL|FINAL_DECISION"
      │
      └── → PromptPackage(system, user, step_label=f"THOUGHT_{N}")
```

---

## LLMClient Dispatch

```
LLMClientFactory.create(provider: str)
  ├── "gemini"   → GeminiClient(api_key, model="gemini-2.5-flash")
  ├── "claude"   → ClaudeClient(api_key, model="claude-opus-4-1")
  ├── "openai"   → OpenAIClient(api_key, model="gpt-4o-mini")
  ├── "groq"     → GroqClient(api_key, model="llama-3.3-70b-versatile")
  ├── "deepseek" → DeepSeekClient(api_key, model="deepseek-chat")
  └── "mock"     → MockClient()

client.call(PromptPackage) → raw: str
  (each client wraps provider SDK, returns text only)
```

---

## extract_json() Safety Flow

```
extract_json(raw: str) → dict
  ├── Strip markdown fences  (```json ... ```)
  ├── re.search r"\{.*\}"    → json.loads()
  ├── fallback: json.loads(cleaned)
  └── fallback: { "_parse_error": True, "_raw": raw[:500] }
      → ReactOrchestrator._fallback_decision("parse error")
         → { signal: "HOLD", confidence: 0.0, ... }
```

## 4. How to Install and Run

### Requirements

```bash
cd Src
pip install -r requirements.txt
```

### Environment Variables

สร้างไฟล์ `.env` ใน `Src/` หรือ export ตัวแปรต่อไปนี้:

```bash
export GEMINI_API_KEY="..."
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GROQ_API_KEY="..."
export DEEPSEEK_API_KEY="..."
export DATABASE_URL="postgresql://user:password@host:port/dbname"
```

### Run CLI

```bash
# Fetch fresh data + run agent
python main.py --provider gemini

# Use cached data (skip fetch)
python main.py --provider groq --skip-fetch

# Custom iterations + output path
python main.py --provider claude --iterations 7 --output Output/my_result.json

# Test without API call
python main.py --provider mock
```

### Run Dashboard (Gradio UI)

```bash
python dashboard.py
```

เปิดเบราว์เซอร์ที่ `http://localhost:7860`

---

## 5. Key Components

### LLM Clients (`agent_core/llm/client.py`)

| Provider  | Model Default           | Speed    | Cost |
|-----------|------------------------|----------|------|
| Gemini    | gemini-2.5-flash       | ⚡⚡⚡   | $    |
| Claude    | claude-opus-4-1        | ⚡⚡     | $$   |
| OpenAI    | gpt-4o-mini            | ⚡⚡     | $    |
| Groq      | llama-3.3-70b-versatile| ⚡⚡⚡   | $    |
| DeepSeek  | deepseek-chat          | ⚡⚡⚡   | $    |
| Mock      | —                      | ⚡⚡⚡⚡ | Free |

```python
client = LLMClientFactory.create("gemini")  # or "claude", "openai", "groq", "mock"
response = client.call(PromptPackage(system="...", user="...", step_label="THOUGHT_1"))
```

### ReactOrchestrator (`agent_core/core/react.py`)

ReAct loop: **Thought → Action → Observation → repeat**

```python
ReactConfig(
    max_iterations=5,     # จำนวน Thought steps สูงสุด
    max_tool_calls=0,     # 0 = data pre-loaded (ไม่เรียก tools)
    timeout_seconds=None
)
```

### PromptBuilder (`agent_core/core/prompt.py`)

สร้าง prompt 2 แบบ:
- **Thought prompt**: step-by-step reasoning → JSON action
- **Final Decision prompt**: BUY/SELL/HOLD พร้อม confidence, entry, stop_loss, take_profit

โหลด role/skill จาก `roles.json` และ `skills.json`

### Database (`database.py`)

PostgreSQL handler สำหรับบันทึกผล agent แต่ละ run

```python
db = RunDatabase()
run_id = db.save_run(provider, result, market_state, interval_tf, period)
rows   = db.get_recent_runs(limit=50)
detail = db.get_run_detail(run_id)
stats  = db.get_signal_stats()  # total, buy/sell/hold count, avg confidence
```

---

## 6. Data Models

```python
# Input to Agent
PromptPackage(system: str, user: str, step_label: str)

# Agent Output
{
  "final_decision": {
    "signal": "BUY|SELL|HOLD",
    "confidence": 0.0–1.0,
    "entry_price": float | null,
    "stop_loss": float | null,
    "take_profit": float | null,
    "rationale": str
  },
  "react_trace": [{"step": str, "iteration": int, "response": dict}],
  "iterations_used": int,
  "tool_calls_used": int
}
```

---

## 7. Configuration

**`agent_core/config/roles.json`** — กำหนด role และ system prompt template

**`agent_core/config/skills.json`** — กำหนด tools และ constraints ต่อ skill

```json
// roles.json
{ "name": "analyst", "available_skills": ["market_analysis"], "system_prompt_template": "..." }

// skills.json
{ "name": "market_analysis", "tools": ["get_news", "run_calculator"], "constraints": {"max_calls": 2} }
```

---

## 8. Error Handling

| ประเภท | รายละเอียด |
|--------|-----------|
| `LLMProviderError` | API call ล้มเหลว |
| `LLMUnavailableError` | API key หายหรือ package ไม่ติดตั้ง |
| JSON parse fail | `extract_json()` จัดการ markdown fences และ fallback เป็น HOLD |
| DB not configured | `RunDatabase` raise `ValueError` ถ้าไม่มี `DATABASE_URL` |

---

## 9. Design Principles

1. **Dependency Injection** — ทุก component inject ได้ → testable & swappable
2. **Token Efficiency** — data pre-loaded ใน prompt (max_tool_calls=0)
3. **Multi-Provider** — เปลี่ยน LLM provider ได้ด้วย 1 parameter
4. **Stateless Prompts** — แต่ละ prompt self-contained ไม่มี conversation history
5. **Deterministic Parsing** — `extract_json()` robust ต่อ noisy LLM output