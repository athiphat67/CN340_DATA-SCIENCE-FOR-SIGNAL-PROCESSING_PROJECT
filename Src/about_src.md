# about_src.md — GoldTrader Agent · ภาพรวมซอร์สโค้ด

> เวอร์ชัน: v3.4 | แพลตฟอร์ม: ออม NOW (Hua Seng Heng) | งบต้น: ฿1,500 THB

---

## สารบัญ

1. [ภาพรวมระบบ](#1-ภาพรวมระบบ)
2. [Architecture Diagram](#2-architecture-diagram)
3. [รายละเอียดไฟล์ทีละตัว](#3-รายละเอียดไฟล์ทีละตัว)
4. [Data Flow — Live Trading](#4-data-flow--live-trading)
5. [Data Flow — Backtest](#5-data-flow--backtest)
6. [ReAct Loop อธิบายละเอียด](#6-react-loop-อธิบายละเอียด)
7. [Risk Management Rules](#7-risk-management-rules)
8. [LLM Clients ที่รองรับ](#8-llm-clients-ที่รองรับ)
9. [Database Schema](#9-database-schema)
10. [Environment Variables](#10-environment-variables)
11. [การรันระบบ](#11-การรันระบบ)

---

## 1. ภาพรวมระบบ

GoldTrader เป็น **AI Trading Agent** สำหรับซื้อขายทองคำบนแพลตฟอร์ม ออม NOW (Hua Seng Heng) โดยใช้ **ReAct Loop** (Reasoning + Acting) เชื่อมกับ LLM หลายตัว ระบบวิเคราะห์ตัวชี้วัดทางเทคนิค (RSI, MACD, EMA, Bollinger Bands, ATR) ประกอบกับ Sentiment ของข่าว แล้วตัดสินใจ BUY / SELL / HOLD

**ข้อจำกัดหลัก (Hard Rules)**

| กฎ | ค่า |
|---|---|
| เงินต้น | ฿1,500 THB |
| ขนาด Order | ฿1,000 THB ต่อครั้ง (คงที่) |
| ซื้อได้เมื่อ | Cash ≥ ฿1,000 และไม่มีทองอยู่ในมือ |
| Dead Zone (ห้ามเทรด) | 02:00–06:14 น. (ตลาดปิด) |
| Confidence ขั้นต่ำ | 0.60 (LLM) / 0.75 (BUY signal) |

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        Entry Points                         │
│   main.py (CLI loop)        dashboard.py (Gradio Web UI)    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    services.py
                    AnalysisService
                           │
          ┌────────────────┼────────────────┐
          │                │                │
    orchestrator.py    prompt.py        client.py
    (Market Data)     (PromptBuilder)  (LLMClient)
          │                │                │
    ┌─────┴──────┐   ┌─────┴──────┐   ┌────┴─────────────┐
    │ fetcher.py │   │  react.py  │   │ Gemini/OpenAI/   │
    │newsfetcher │   │ (ReAct Loop│   │ Claude/Groq/     │
    │            │   │ + extract) │   │ Ollama/DeepSeek  │
    └─────┬──────┘   └─────┬──────┘   └──────────────────┘
          │                │
          │          risk.py
          │          (RiskManager — TP/SL/Dead Zone)
          │
    ┌─────┴──────────────────────┐
    │     database.py            │
    │  runs / llm_logs / portfolio│
    └────────────────────────────┘
          │
    ┌─────┴──────────────────────┐
    │   Notifications            │
    │  discord_notifier.py       │
    │  telegram_notifier.py      │
    └────────────────────────────┘
```

---

## 3. รายละเอียดไฟล์ทีละตัว

### 🔵 Core Layer

#### `prompt.py` — Part C: Prompt System

สร้าง `PromptPackage` ที่ส่งระหว่าง PromptBuilder → LLMClient

**คลาสหลัก:**

| คลาส | หน้าที่ |
|---|---|
| `PromptPackage` | Data container: `system`, `user`, `step_label` |
| `AIRole` (Enum) | `ANALYST` / `RISK_MANAGER` / `TRADER` |
| `Skill` | ชื่อ + description + tools list |
| `SkillRegistry` | โหลด/ลงทะเบียน Skills จาก `skills.json` |
| `RoleDefinition` | System prompt template + available skills |
| `RoleRegistry` | โหลด/ลงทะเบียน Roles จาก `roles.json` |
| `PromptBuilder` | สร้าง prompt สำหรับ THOUGHT step และ FINAL_DECISION step |

**Method สำคัญ:**

- `build_thought(market_state, tool_results, iteration)` — สร้าง prompt สำหรับแต่ละ iteration ของ ReAct
- `build_final_decision(market_state, tool_results)` — สร้าง prompt สำหรับ force final decision เมื่อ iteration เต็ม
- `_format_market_state(state)` — แปลง market state dict เป็น text สำหรับ LLM รวมถึง Dead Zone warning และ Portfolio PnL status

---

#### `react.py` — Part B: ReAct Orchestration Loop

ควบคุม Thought → Action → Observation → FINAL_DECISION

**คลาสหลัก:**

| คลาส | หน้าที่ |
|---|---|
| `ReactConfig` | `max_iterations`, `max_tool_calls`, `timeout_seconds` |
| `ToolResult` | ผลจาก tool: `tool_name`, `status`, `data`, `error` |
| `ReactState` | State ระหว่าง loop: `market_state`, `tool_results`, `iteration` |
| `ReactOrchestrator` | Run loop หลัก + dependency injection |

**Fast Path (max_tool_calls = 0):** ข้าม loop ไปเรียก LLM ครั้งเดียวทันที — ใช้ในระบบ production ปัจจุบัน

**Full ReAct Path:** วนลูปจนถึง max_iterations หรือ LLM ส่ง `"action": "FINAL_DECISION"` กลับมา

**Helper functions:**
- `extract_json(raw)` — parse JSON จาก LLM response แบบ fault-tolerant (รองรับ markdown fence)
- `_check_parse_error(parsed)` — ตรวจ parse error แล้ว fallback เป็น HOLD
- `_make_llm_log(step, iteration, llm_resp, parsed)` — สร้าง trace entry พร้อม token metadata

---

#### `risk.py` — RiskManager

ทำหน้าที่ "ยามเฝ้าประตู" ก่อนส่ง signal ออกไปจริง

**ด่านตรวจ (ตามลำดับ):**

```
ด่าน 0: Hard Rules
  → Dead Zone 02:00-06:14 → REJECT ทันที
  → TP/SL Price Hit (check_price vs tp_price/sl_price) → OVERRIDE เป็น SELL

ด่าน 1: Confidence Filter
  → confidence < min_confidence (0.60) → REJECT

ด่าน 2: Daily Loss Limit
  → accumulated loss ≥ max_daily_loss_thb (500 THB) → REJECT BUY

ด่าน 3: Signal Processing
  → BUY: คำนวณ SL/TP จาก ATR × multiplier (default 2.0 / RR 1.5)
  → SELL: คำนวณ gold_value จาก gold_grams × sell_price
  → HOLD: ผ่านตรง
```

**Parameters:**

| Parameter | Default | ความหมาย |
|---|---|---|
| `atr_multiplier` | 2.0 | ATR × 2 = ระยะ Stop Loss |
| `risk_reward_ratio` | 1.5 | SL distance × 1.5 = ระยะ Take Profit |
| `min_confidence` | 0.60 | Confidence ขั้นต่ำ |
| `max_daily_loss_thb` | 500.0 | ขาดทุนสะสมสูงสุดต่อวัน |

---

#### `client.py` — LLM Client Layer

Abstract base class + concrete implementations สำหรับ LLM ทุกตัว

**Return type:** ทุก client คืน `LLMResponse` ที่มี:

```python
text          # raw text response (JSON string)
prompt_text   # full prompt ที่ส่งไป
token_input   # จำนวน input tokens
token_output  # จำนวน output tokens  
token_total   # รวม
model         # model name
provider      # provider name
```

**Clients ที่รองรับ:**

| Class | Provider |
|---|---|
| `GeminiClient` | Google Gemini (default: `gemini-2.5-flash-lite`) |
| `OpenAIClient` | OpenAI GPT (default: `gpt-4o-mini`) |
| `ClaudeClient` | Anthropic Claude (default: `claude-opus-4-1`) |
| `GroqClient` | Groq LPU (default: `llama-3.3-70b-versatile`) |
| `DeepSeekClient` | DeepSeek (default: `deepseek-chat`) |
| `OllamaClient` | Ollama local (default: `qwen3.5:9b`) |
| `OpenRouterClient` | OpenRouter |
| `MockClient` | Testing only |
| `FallbackChainClient` | Wrapper รวม providers เป็น fallback chain |

---

### 🟢 Data Layer

#### `fetcher.py` — GoldDataFetcher

ดึงราคาทองและ Forex จาก API หลายแหล่งพร้อม consensus logic

**แหล่งข้อมูล:**

| ข้อมูล | แหล่งหลัก | Fallback |
|---|---|---|
| Gold Spot (USD) | TwelveData API | yfinance → gold-api.com |
| USD/THB | exchangerate-api.com | — |
| ราคาทองไทย (THB) | `latest_gold_price.json` (WebSocket) | คำนวณจากสูตร |

**Confidence Score:** คำนวณจาก deviation ระหว่างแหล่งข้อมูล ถ้า deviation > 0.5% → confidence ลด

---

#### `newsfetcher.py` — GoldNewsFetcher

ดึงและวิเคราะห์ sentiment ข่าวทองคำ

**8 หมวดหมู่ข่าว:**

| Category | Impact | แหล่งที่มา |
|---|---|---|
| `gold_price` | direct | Kitco RSS, yfinance GC=F |
| `usd_thb` | direct | FXStreet RSS, yfinance THB=X |
| `fed_policy` | high | Reuters RSS |
| `inflation` | high | Reuters RSS |
| `geopolitics` | high | Kitco + Reuters |
| `dollar_index` | medium | FXStreet |
| `thai_economy` | medium | Bangkok Post RSS |
| `thai_gold_market` | direct | Kitco + Bangkok Post |

**Sentiment:** FinBERT via Hugging Face API (ProsusAI/finbert)

**Smart Cache:** บันทึก `news_cache.json` แบ่งรอบ 00:00-11:59 / 12:00-23:59 — ไม่ดึงซ้ำในรอบเดิม

---

#### `orchestrator.py` — GoldTradingOrchestrator

รวม Fetcher + Indicators + NewsFetcher แล้ว output เป็น JSON Payload

**โครงสร้าง Payload:**

```json
{
  "meta": { ... },
  "data_quality": { "quality_score": "good|degraded", "warnings": [] },
  "market_data": {
    "spot_price_usd": { "price_usd_per_oz": ..., "confidence": ... },
    "forex": { "usd_thb": ... },
    "thai_gold_thb": { "sell_price_thb": ..., "buy_price_thb": ... },
    "recent_price_action": [ { "datetime", "open", "high", "low", "close", "volume" } ]
  },
  "technical_indicators": {
    "rsi": { "value": ..., "signal": "oversold|neutral|overbought" },
    "macd": { "macd_line", "signal_line", "histogram", "signal" },
    "trend": { "ema_20", "ema_50", "trend": "uptrend|downtrend|sideways" },
    "bollinger": { "upper", "lower", "mid" },
    "atr": { "value": ... }
  },
  "news": { "summary": { ... }, "by_category": { ... } }
}
```

**Background Thread:** เปิด WebSocket (`gold_interceptor_lite`) ดึงราคาทองไทยแบบ real-time ทันทีที่ class นี้ถูกสร้าง

---

### 🟡 Service Layer

#### `services.py` — Business Logic Layer

**3 Services หลัก:**

**`AnalysisService`** — หัวใจหลักของระบบ

```
1. Normalize provider name (gemini_2.5_flash → gemini)
2. Validate inputs (provider / period / intervals)
3. Check Thailand market hours (warn only)
4. Fetch market data via orchestrator
5. Attach portfolio state จาก DB
6. Run _run_single_interval() → ReAct loop
7. Build voting_result (single-interval passthrough)
8. Save to DB (runs + llm_logs)
9. Send Discord + Telegram notification
```

**`PortfolioService`** — CRUD portfolio ใน DB

**`HistoryService`** — ดึง run history + LLM logs + statistics

---

### 🔴 Notification Layer

#### `discord_notifier.py` — Discord Webhook

ส่ง Embed message พร้อม:
- Signal + Confidence bar
- Entry / SL / TP levels
- ราคา ออม NOW (THB)
- Per-interval breakdown
- Voting summary
- Rationale

#### `telegram_notifier.py` — Telegram Bot API

ส่ง HTML-formatted message เนื้อหาเดียวกับ Discord

**Toggle:** `DISCORD_NOTIFY_HOLD` / `TELEGRAM_NOTIFY_HOLD` ควบคุมว่าจะแจ้ง HOLD หรือไม่

---

### 🟤 Backtest

#### `run_main_backtest.py` — MainPipelineBacktest

รัน full pipeline (Fetcher + ReAct + RiskManager) บน historical CSV data

**Components:**

| Class | หน้าที่ |
|---|---|
| `CandleCache` | Cache ผล LLM ต่อ candle ลง JSON file |
| `TimeEstimator` | คาดเดา ETA จาก rolling average |
| `MainPipelineBacktest` | Main class: load → run → metrics → export |

**Metrics ที่คำนวณ:**

- Directional Accuracy, Signal Sensitivity
- Win Rate, Profit Factor, Expectancy
- **MDD** (Maximum Drawdown)
- **Sharpe Ratio** (annualized)
- **Sortino Ratio** (downside-adjusted)
- Calmar Ratio
- Session Compliance %

---

### 🔧 Support Files

#### `database.py` — RunDatabase (PostgreSQL)

Connection pool (min=1, max=5) สำหรับ Render free tier

**3 Tables:**

| Table | เก็บอะไร |
|---|---|
| `runs` | ผล analysis ทุกครั้ง: signal, confidence, price levels, market snapshot |
| `llm_logs` | กระบวนการคิดทั้งหมด: full prompt, response, token usage, elapsed ms |
| `portfolio` | สถานะ portfolio ปัจจุบัน (1 row, UPSERT) |

#### `logger_setup.py`

- `sys_logger` → `system.log` (INFO)
- `llm_logger` → `llm_trace.log` (DEBUG)
- RotatingFileHandler (5MB × 3 backup)
- TH Time formatter (UTC+7)
- `@log_method(logger)` decorator จับเวลาอัตโนมัติ

#### `api_logger.py`

ส่ง trade log ไปยัง external API (`goldtrade-logs-api.poonnatuch.workers.dev`) ทุกครั้งที่มี signal

#### `technical_tools.py` / `fundamental_tools.py`

Tools สำหรับ ReAct loop ที่ LLM สามารถเรียกใช้ได้ (ส่วนใหญ่ยัง `not_implemented`)

---

## 4. Data Flow — Live Trading

```
main.py หรือ dashboard.py
    │
    ▼
AnalysisService.run_analysis()
    │
    ├─ GoldTradingOrchestrator.run()
    │      ├─ GoldDataFetcher.fetch_all()
    │      │      ├─ fetch_gold_spot_usd()  [TwelveData + yfinance + gold-api]
    │      │      ├─ fetch_usd_thb_rate()   [exchangerate-api.com]
    │      │      └─ calc_thai_gold_price() [latest_gold_price.json / fallback]
    │      ├─ TechnicalIndicators(ohlcv_df)
    │      └─ GoldNewsFetcher.to_dict()     [Cache / FinBERT]
    │
    ├─ PromptBuilder.build_final_decision(market_state)
    │
    ├─ LLMClient.call(prompt)               [Gemini / Groq / ...]
    │
    ├─ ReactOrchestrator.run(market_state)
    │      └─ extract_json(raw) → _build_decision()
    │
    ├─ RiskManager.evaluate(llm_decision, market_state)
    │      ├─ Dead Zone check
    │      ├─ TP/SL override
    │      ├─ Confidence filter
    │      └─ ATR-based SL/TP calculation
    │
    ├─ RunDatabase.save_run() + save_llm_logs_batch()
    │
    └─ DiscordNotifier + TelegramNotifier
```

---

## 5. Data Flow — Backtest

```
run_main_backtest.py (CLI)
    │
    ├─ load_gold_csv() → aggregate to timeframe
    │
    └─ for each candle:
           ├─ TradingSessionManager.process_candle()  [Dead Zone / Session check]
           ├─ CandleCache.get()                        [Skip LLM ถ้า cached]
           ├─ MarketStateBuilder.build()               [สร้าง market_state]
           ├─ ReactOrchestrator.run(market_state)      [LLM → signal]
           ├─ RiskManager.evaluate()                   [Filter]
           ├─ SimPortfolio.execute_buy/sell()          [Simulate trades]
           └─ CandleCache.set()                        [บันทึก result]
```

---

## 6. ReAct Loop อธิบายละเอียด

```
Fast Path (max_tool_calls = 0) — ใช้ในระบบปัจจุบัน:
    build_final_decision() → LLM call → extract_json() → RiskManager → done

Full Path (ถ้าเปิด tools):
    THOUGHT_1
        │
        ├── action = "FINAL_DECISION" → exit
        ├── action = "CALL_TOOL" → execute tool → OBSERVATION → THOUGHT_2
        └── unknown → fallback HOLD

    ... (repeat จนถึง max_iterations)

    THOUGHT_FINAL (forced) → extract_json() → RiskManager → done
```

**JSON format ที่ LLM ต้อง output:**

```json
{
  "action": "FINAL_DECISION",
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0,
  "entry_price": null,
  "stop_loss": null,
  "take_profit": null,
  "position_size_thb": 1000,
  "rationale": "..."
}
```

---

## 7. Risk Management Rules

### BUY Conditions (ใน roles.json + risk.py)

| เงื่อนไข | ค่า |
|---|---|
| Cash available | ≥ ฿1,000 |
| Gold held | = 0 gram |
| Bullish signals | ≥ 3 จาก (RSI < 35, MACD Hist > 0, Price > EMA20, Bounce from Lower BB) |
| LLM Confidence | ≥ 0.75 |
| Dead Zone | ไม่อยู่ใน 02:00–06:14 |
| Daily loss | < ฿500 accumulated |

### SELL Conditions

| เงื่อนไข | ประเภท |
|---|---|
| TP price hit (check_price ≥ tp_price) | Hard Override |
| SL price hit (check_price ≤ sl_price) | Hard Override |
| RSI > 70 | LLM Technical |
| MACD Histogram < 0 | LLM Technical |
| Price breaks below EMA20 | LLM Technical |
| Trend switches to downtrend/sideways | LLM Technical |
| Time 01:30–01:59 (pre-close) | Warning to LLM |

---

## 8. LLM Clients ที่รองรับ

```python
from agent_core.llm.client import LLMClientFactory

client = LLMClientFactory.create("gemini")
client = LLMClientFactory.create("groq")
client = LLMClientFactory.create("claude")
client = LLMClientFactory.create("openai", model="gpt-4o")
client = LLMClientFactory.create("ollama", model="qwen3.5:9b")
client = LLMClientFactory.create("deepseek")
client = LLMClientFactory.create("openrouter", model="meta-llama/llama-3-8b-instruct")
client = LLMClientFactory.create("mock")  # Testing
```

**Fallback Chain:**

```python
from agent_core.llm.client import FallbackChainClient

chain = FallbackChainClient([
    ("gemini", GeminiClient()),
    ("groq",   GroqClient()),
    ("mock",   MockClient()),
])
result = chain.call(prompt_package)
print(chain.active_provider)  # provider ที่ใช้จริง
```

---

## 9. Database Schema

```sql
-- ผล analysis
runs (
    id, run_at, provider, interval_tf, period,
    signal, confidence,
    entry_price, stop_loss, take_profit,   -- THB/gram
    usd_thb_rate, gold_price_thb,
    rationale, iterations_used, tool_calls_used,
    gold_price, rsi, macd_line, signal_line, trend,
    react_trace,      -- JSON array
    market_snapshot   -- JSON
)

-- กระบวนการคิดของ LLM
llm_logs (
    id, run_id, logged_at, interval_tf,
    step_type, iteration, provider,
    signal, confidence, rationale,
    entry_price, stop_loss, take_profit,
    full_prompt, full_response, trace_json,
    token_input, token_output, token_total,
    elapsed_ms, iterations_used, tool_calls_used,
    is_fallback, fallback_from
)

-- สถานะ Portfolio (1 row)
portfolio (
    id, cash_balance, gold_grams,
    cost_basis_thb, current_value_thb,
    unrealized_pnl, trades_today, updated_at
)
```

---

## 10. Environment Variables

| Variable | ใช้ใน | ความหมาย |
|---|---|---|
| `DATABASE_URL` | database.py | PostgreSQL connection string |
| `GEMINI_API_KEY` | client.py | Google Gemini API key |
| `OPENAI_API_KEY` | client.py | OpenAI API key |
| `ANTHROPIC_API_KEY` | client.py | Claude API key |
| `GROQ_API_KEY` | client.py | Groq API key |
| `DEEPSEEK_API_KEY` | client.py | DeepSeek API key |
| `OPENROUTER_API_KEY` | client.py | OpenRouter API key |
| `TWELVEDATA_API_KEY` | fetcher.py | TwelveData price API |
| `HF_TOKEN` | newsfetcher.py | Hugging Face (FinBERT) |
| `DISCORD_WEBHOOK_URL` | discord_notifier.py | Discord Webhook URL |
| `DISCORD_NOTIFY_ENABLED` | discord_notifier.py | `true` / `false` |
| `DISCORD_NOTIFY_HOLD` | discord_notifier.py | แจ้งสัญญาณ HOLD ด้วยหรือไม่ |
| `TELEGRAM_BOT_TOKEN` | telegram_notifier.py | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | telegram_notifier.py | Chat ID เป้าหมาย |
| `TEAM_API_KEY` | main.py, dashboard.py | GoldTrade Logs API key |
| `OLLAMA_BASE_URL` | client.py | Ollama server URL (default: localhost:11434) |
| `OLLAMA_MODEL` | client.py | Ollama default model |
| `DASHBOARD_USER` | dashboard.py | Basic auth username |
| `DASHBOARD_PASS` | dashboard.py | Basic auth password |
| `PORT` | dashboard.py | Port สำหรับ Gradio server |

---

## 11. การรันระบบ

### Live Trading (CLI)

```bash
# รันด้วย Gemini (default)
python main.py --provider gemini

# เลือก interval
python main.py --provider gemini --intervals 1h

# ข้าม fetch ใช้ข้อมูลเดิม
python main.py --provider gemini --skip-fetch

# ไม่บันทึก DB
python main.py --provider groq --no-save
```

### Live Trading (Dashboard)

```bash
python dashboard.py
# เปิด browser: http://localhost:7860
```

### Backtest

```bash
python run_main_backtest.py \
  --gold-csv data/premium_hsh/Mock_HSH_OHLC.csv \
  --timeframe 5m \
  --days 1 \
  --provider gemini \
  --react-iter 5
```

### Orchestrator เดี่ยว (ดึงข้อมูลอย่างเดียว)

```bash
python orchestrator.py --history 30 --interval 5m
```

---

## หมายเหตุสำคัญสำหรับ Developer

- **ราคาใน DB เป็น THB/gram เสมอ** ไม่ใช่ USD/oz — อย่าแปลงซ้ำ
- **ATR จาก orchestrator มีหน่วย USD/oz** ต้องแปลงเป็น THB/baht_weight ก่อนส่ง RiskManager (ดู services.py บรรทัด ATR conversion)
- **Fast Path เท่านั้นที่ใช้ใน production** (`max_tool_calls = 0`) — full ReAct loop ยังอยู่ระหว่างพัฒนา
- **FallbackChainClient** จะ skip provider ที่ `is_available() = False` โดยอัตโนมัติ ไม่ crash
- **Dead Zone** ถูก enforce ทั้งใน RiskManager (hard reject) และใน prompt (warning ให้ LLM รู้ล่วงหน้า)
- **news_cache.json** refresh ทุกครึ่งวัน ถ้าต้องการ force refresh ให้ลบไฟล์ออก