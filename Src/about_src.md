# GoldTrader — Agent Architecture Documentation

---

## 1. Overview

**GoldTrader** คือ ReAct+LLM trading agent สำหรับวิเคราะห์ตลาดทองคำ โดยใช้การผสมผสานระหว่าง Technical Indicators และ AI Reasoning แบบ multi-step

- **Agent Type**: ReAct (Reasoning + Acting) Loop
- **Data Source**: yfinance (OHLCV), News Fetcher
- **LLM Support**: Gemini, Claude, OpenAI, Groq, DeepSeek, Mock
- **UI**: Gradio Dashboard (4-panel display + Portfolio Tab)
- **Database**: PostgreSQL (`database.py`) — เก็บทั้ง run history และ portfolio
- **Platform**: ออม NOW (Hua Seng Heng) — ซื้อขายทองคำหน่วยกรัม ขั้นต่ำ ฿1,000

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
├── dashboard.py                # Gradio UI entry point (v3)
├── database.py                 # PostgreSQL handler (RunDatabase) — runs + portfolio
├── main.py                     # CLI entry point
└── requirements.txt
```

---

## 3. Full Flow Diagram

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                         GOLDTRADER EXECUTION FLOW  (v3)                        ║
║              (Class-level · Method-level · Data-level · Portfolio)             ║
╚══════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────┐     ┌──────────────────────────────────────┐
│         dashboard.py            │     │              main.py                 │
│  (Gradio UI — 4 tabs)           │     │  argparse: --provider, --iterations  │
│                                 │     │            --skip-fetch, --output    │
│  Tab 1: 📊 Live Analysis        │     └──────────────────┬───────────────────┘
│  Tab 2: 📜 Run History          │                        │
│  Tab 3: 💼 Portfolio  ◄── NEW   │                        │ (skip_fetch=False)
│                                 │                        │
│  gr.Dropdown: provider          │                        ▼
│  gr.Dropdown: period            │
│  gr.CheckboxGroup: intervals    │
└───────────────┬─────────────────┘
                │
                │ [Tab 3: Portfolio Form]
                │   gr.Number: cash_balance
                │   gr.Number: gold_grams
                │   gr.Number: cost_basis_thb
                │   gr.Number: current_value_thb
                │   gr.Number: unrealized_pnl
                │   gr.Number: trades_today
                │   [บันทึก] → db.save_portfolio()
                │
                │ [Run Analysis]
                ▼
┌───────────────────────────────────────────┐
│        GoldTradingOrchestrator            │
│            orchestrator.py               │
│  .run() → market_state dict              │
│    Step 1: price_fetcher.fetch_all()     │
│    Step 2: TechnicalIndicators.to_dict() │
│    Step 3: news_fetcher.to_dict()        │
│    Step 4+5: Assemble + Save JSON        │
└───────────────────┬───────────────────────┘
                    │
                    │ market_state dict
                    ▼
        ┌───────────────────────────┐
        │  [NEW] Merge Portfolio    │
        │  portfolio = db.get_      │
        │    portfolio()            │
        │  market_state["portfolio"]│
        │    = portfolio            │
        └───────────────┬───────────┘
                        │
                        │ market_state (with portfolio)
                        ▼
        ┌────────────────────────────────────────────┐
        │            ReactOrchestrator               │
        │                react.py                    │
        │  .run(market_state)                        │
        │    → prompt_builder.build_final_decision() │
        │      includes portfolio in prompt          │
        │    → llm.call(prompt) → parsed dict        │
        │    → _build_decision(parsed) → result      │
        └──────────────────┬─────────────────────────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
   ┌─────────────────────┐  ┌──────────────────────┐
   │   final_decision     │  │    react_trace       │
   │   {                  │  │  + portfolio snapshot│
   │    signal: BUY|      │  │    shown in verdict  │
   │            SELL|HOLD │  └──────────────────────┘
   │    confidence: 0–1   │
   │    entry_price (THB) │
   │    stop_loss  (THB)  │
   │    take_profit(THB)  │
   │    rationale         │
   │   }                  │
   └──────────┬───────────┘
              │
   ┌──────────┴──────────┐
   ▼                     ▼
┌──────────────────┐  ┌──────────────────────┐
│  dashboard.py    │  │  RunDatabase         │
│  Tab1: Market    │  │  .save_run(...)      │
│  Tab1: Trace     │  │  → PostgreSQL runs   │
│  Tab1: Signal    │  │                      │
│  Tab1: Explain   │  │  .save_portfolio()/  │
│  Tab2: History   │  │  .get_portfolio()    │
│  Tab3: Portfolio │  │  → PostgreSQL        │
└──────────────────┘  │    portfolio table   │
                      └──────────────────────┘
```

---

## 4. Portfolio Data Flow (NEW in v3)

```
User (ออม NOW app)
  └─► กรอกข้อมูลใน Tab "💼 Portfolio"
        cash_balance, gold_grams,
        cost_basis_thb, current_value_thb,
        unrealized_pnl, trades_today
          │
          ▼
      db.save_portfolio()
        → PostgreSQL table: portfolio (id=1, UPSERT)
          │
          ▼ (เมื่อกด Run Analysis)
      db.get_portfolio()
        → portfolio dict
          │
          ▼
      market_state["portfolio"] = portfolio
          │
          ▼
      PromptBuilder._format_market_state()
        → เพิ่ม section:
          ── Portfolio ──
            Cash:       ฿1,500.00
            Gold:       0.0000 g
            Cost basis: ฿0.00
            Cur. value: ฿0.00
            Unreal PnL: ฿0.00
            Trades today: 0
            can_buy:  YES / NO (cash < ฿1000)
            can_sell: YES / NO (no gold)
          ── End Portfolio ──
          │
          ▼
      LLM เห็น portfolio → ตัดสินใจตาม constraints จริง
```

---

## 5. PromptBuilder Internal Flow (Updated)

```
PromptBuilder._format_market_state(market_state)
│
├── market_data   → spot price
├── indicators    → RSI, MACD, Trend
├── news          → top sentiment per category
└── portfolio     → [NEW] cash, gold, PnL, can_buy, can_sell
```

---

## 6. Database Schema (Updated)

```sql
-- ตารางเดิม: บันทึกผลการ run แต่ละครั้ง
CREATE TABLE runs (
    id, run_at, provider, interval_tf, period,
    signal, confidence, entry_price, stop_loss, take_profit,
    rationale, iterations_used, tool_calls_used,
    gold_price, rsi, macd_line, signal_line, trend,
    react_trace, market_snapshot
);

-- [NEW] ตารางใหม่: เก็บ portfolio ของ user (มีแค่ 1 row เสมอ id=1)
CREATE TABLE portfolio (
    id                SERIAL PRIMARY KEY,  -- always 1
    cash_balance      REAL,   -- เงินสดคงเหลือ (฿)
    gold_grams        REAL,   -- ทองคำคงเหลือ (กรัม)
    cost_basis_thb    REAL,   -- มูลค่าต้นทุน (฿)
    current_value_thb REAL,   -- มูลค่าปัจจุบัน (฿)
    unrealized_pnl    REAL,   -- กำไร/ขาดทุนที่ยังไม่ realise (฿)
    trades_today      INTEGER,-- จำนวน trade วันนี้
    updated_at        TEXT    -- timestamp UTC
);
```

```python
# API ใหม่ใน RunDatabase
db.save_portfolio(data: dict)   # UPSERT row id=1
db.get_portfolio() -> dict      # SELECT id=1, return default ถ้าไม่มีข้อมูล
```

---

## 7. Trading Constraints (roles.json)

กฎที่ LLM ต้องปฏิบัติตาม (ระบุใน system prompt):

| กฎ | รายละเอียด |
|----|-----------|
| Minimum buy | ฿1,000 ต่อครั้ง (ออม NOW) |
| can_buy check | ถ้า cash < ฿1,000 → ห้าม BUY |
| can_sell check | ถ้า gold_grams = 0 → ห้าม SELL |
| Daily trade | ต้องเทรดอย่างน้อย 1 ครั้งต่อวัน |
| HOLD condition | HOLD ได้เฉพาะเมื่อ can_buy=NO และ can_sell=NO |
| Starting capital | ฿1,500 |
| Price unit | entry_price, stop_loss, take_profit เป็น THB (ไม่ใช่ USD) |

---

## 8. How to Install and Run

### Requirements

```bash
cd Src
pip install -r requirements.txt
```

### Environment Variables

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
python main.py --provider gemini
python main.py --provider groq --skip-fetch
python main.py --provider claude --iterations 7 --output Output/my_result.json
python main.py --provider mock
```

### Run Dashboard (Gradio UI)

```bash
python dashboard.py
```

เปิดเบราว์เซอร์ที่ `http://localhost:10000`

**workflow การใช้งาน:**
1. ไปที่ Tab **💼 Portfolio** → กรอกข้อมูลจากแอพ ออม NOW → กด **บันทึก**
2. กลับมาที่ Tab **📊 Live Analysis** → เลือก Provider / Period / Interval
3. กด **▶ Run Analysis** → LLM จะวิเคราะห์โดยรวม portfolio ด้วย
4. อ่านสัญญาณ BUY/SELL/HOLD จาก Final Decision
5. หลังเทรดจริง → กลับไปอัปเดต Portfolio อีกครั้ง

---

## 9. Key Components

### LLM Clients (`agent_core/llm/client.py`)

| Provider  | Model Default            | Speed    | Cost |
|-----------|-------------------------|----------|------|
| Gemini    | gemini-2.5-flash        | ⚡⚡⚡   | $    |
| Claude    | claude-opus-4-1         | ⚡⚡     | $$   |
| OpenAI    | gpt-4o-mini             | ⚡⚡     | $    |
| Groq      | llama-3.3-70b-versatile | ⚡⚡⚡   | $    |
| DeepSeek  | deepseek-chat           | ⚡⚡⚡   | $    |
| Mock      | —                       | ⚡⚡⚡⚡ | Free |

### ReactOrchestrator (`agent_core/core/react.py`)

```python
ReactConfig(
    max_iterations=5,
    max_tool_calls=0,   # 0 = data pre-loaded
    timeout_seconds=None
)
```

### PromptBuilder (`agent_core/core/prompt.py`)

สร้าง prompt 2 แบบ พร้อม **portfolio section** (NEW):
- **Thought prompt**: step-by-step reasoning → JSON action
- **Final Decision prompt**: BUY/SELL/HOLD + portfolio-aware constraints

### Database (`database.py`)

```python
# Run history
db.save_run(provider, result, market_state, interval_tf, period)
db.get_recent_runs(limit=50)
db.get_run_detail(run_id)
db.get_signal_stats()

# Portfolio (NEW)
db.save_portfolio(data)   # UPSERT — มีแค่ 1 row เสมอ
db.get_portfolio()        # GET — return default ถ้ายังไม่กรอก
```

---

## 10. Data Models

```python
# Portfolio dict (NEW)
{
  "cash_balance":      float,   # เงินสดคงเหลือ (฿)
  "gold_grams":        float,   # ทองคำคงเหลือ (กรัม)
  "cost_basis_thb":    float,   # ต้นทุนรวม (฿)
  "current_value_thb": float,   # มูลค่าปัจจุบัน (฿)
  "unrealized_pnl":    float,   # กำไร/ขาดทุน (฿)
  "trades_today":      int,     # ไม้ที่เทรดวันนี้
  "updated_at":        str,     # ISO timestamp UTC
}

# market_state dict (เพิ่ม portfolio key)
{
  "market_data":           {...},
  "technical_indicators":  {...},
  "news":                  {...},
  "portfolio":             {...},   # NEW — merged ก่อนส่ง agent
}

# Agent Output (ไม่เปลี่ยน)
{
  "final_decision": {
    "signal":      "BUY|SELL|HOLD",
    "confidence":  0.0–1.0,
    "entry_price": float | null,   # THB
    "stop_loss":   float | null,   # THB
    "take_profit": float | null,   # THB
    "rationale":   str
  },
  "react_trace":     [...],
  "iterations_used": int,
  "tool_calls_used": int
}
```

---

## 11. Error Handling

| ประเภท | รายละเอียด |
|--------|-----------|
| `LLMProviderError` | API call ล้มเหลว |
| `LLMUnavailableError` | API key หายหรือ package ไม่ติดตั้ง |
| JSON parse fail | `extract_json()` fallback เป็น HOLD |
| DB not configured | `RunDatabase` raise `ValueError` ถ้าไม่มี `DATABASE_URL` |
| Portfolio not set | `get_portfolio()` return default (cash=1500, gold=0) |

---

## 12. Design Principles

1. **Dependency Injection** — ทุก component inject ได้ → testable & swappable
2. **Token Efficiency** — data pre-loaded ใน prompt (max_tool_calls=0)
3. **Multi-Provider** — เปลี่ยน LLM provider ได้ด้วย 1 parameter
4. **Stateless Prompts** — แต่ละ prompt self-contained ไม่มี conversation history
5. **Deterministic Parsing** — `extract_json()` robust ต่อ noisy LLM output
6. **Portfolio-Aware** — LLM เห็น cash/gold/PnL/constraints ก่อนตัดสินใจ (NEW)