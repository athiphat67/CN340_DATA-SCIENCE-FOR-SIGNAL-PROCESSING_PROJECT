# GoldTrader — Complete Agent Architecture Documentation v3.2

---

## Executive Summary

**GoldTrader** คือ production-grade **ReAct+LLM trading agent** สำหรับวิเคราะห์ตลาดทองคำบน platform ออม NOW (Hua Seng Heng)  
ผสมผสาน multi-step AI reasoning, real-time technical indicators และ portfolio-aware constraints เพื่อ generate สัญญาณ BUY/SELL/HOLD

**v3.2 — Layered Architecture Refactor**

| ด้าน | v3.1 (เดิม) | v3.2 (ใหม่) |
|------|-------------|-------------|
| **โครงสร้าง** | Business logic ปนอยู่ใน dashboard.py | แยก UI / Services / Config / Utils ชัดเจน |
| **Testability** | ทดสอบยาก (UI entangled) | Services inject-able, ทดสอบแยกได้ |
| **Reusability** | ใช้ได้แค่ใน Gradio | Services ใช้ได้จาก CLI / backtest ด้วย |
| **Multi-interval** | Single interval per run | Weighted voting จากหลาย interval พร้อมกัน |

- **LLM Engines**: Gemini, Claude, OpenAI, Groq, DeepSeek (pluggable via Factory)
- **Data**: Live OHLCV (yfinance) + Technical Indicators + RSS News + FinBERT Sentiment
- **UI**: Gradio Dashboard — 3 tabs (Analysis, History, Portfolio)
- **Persistence**: PostgreSQL (runs + portfolio snapshot)
- **Platform**: ออม NOW (minimum buy ฿1,000, ซื้อขายหน่วยกรัม)

---

## 1. Project Structure

```
Src/
│
├── core/                                ✨ NEW — Business Logic Layer
│   ├── __init__.py                      re-export: init_services, constants
│   ├── config.py                        Global config (providers, intervals, weights, calendar)
│   ├── services.py                      Business logic: AnalysisService, PortfolioService, HistoryService
│   ├── renderers.py                     HTML formatters: TraceRenderer, HistoryRenderer, PortfolioRenderer
│   └── utils.py                         Weighted voting logic + helper functions
│
├── ui/                                  ✨ NEW — UI Layer (pure Gradio)
│   ├── __init__.py
│   └── dashboard.py                     Gradio component definitions + event wiring (callbacks only)
│
├── agent_core/                          ✓ ไม่เปลี่ยน — AI Agent Core
│   ├── config/
│   │   ├── roles.json                   Role definitions (analyst, risk_manager)
│   │   └── skills.json                  Skill → Tool registry
│   │
│   ├── core/
│   │   ├── prompt.py                    PromptBuilder, RoleRegistry, SkillRegistry
│   │   ├── react.py                     ReactOrchestrator (Thought → Action → Observation loop)
│   │   └── risk_manager.py              RiskManager — validate & adjust final decision
│   │
│   ├── data/
│   │   ├── latest.json                  Market snapshot ล่าสุด (auto-updated)
│   │   └── payload_*.json               Historical data dumps
│   │
│   └── llm/
│       └── client.py                    6 LLMClient implementations + LLMClientFactory
│
├── data_engine/                         ✓ ไม่เปลี่ยน — Market Data Collection
│   ├── fetcher.py                       GoldDataFetcher (yfinance wrapper)
│   ├── indicators.py                    TechnicalIndicators (RSI, MACD, EMA, Bollinger)
│   ├── newsfetcher.py                   GoldNewsFetcher — RSS + yfinance + FinBERT sentiment
│   ├── orchestrator.py                  GoldTradingOrchestrator — รวม fetcher+indicators+news
│   └── thailand_timestamp.py            Timezone helper (UTC+7)
│
├── logs/
│   ├── system.log                       Application events
│   └── llm_trace.log                    LLM request/response pairs (verbose)
│
├── database.py                          ✓ ไม่เปลี่ยน — RunDatabase (PostgreSQL ORM)
├── main.py                              ✓ ไม่เปลี่ยน — CLI entry point
├── logger_setup.py                      ✓ ไม่เปลี่ยน — THTimeFormatter + log_method decorator
└── requirements.txt
```

---

## 2. Architecture Layers

```
┌──────────────────────────────────────────────────────────────────┐
│                     UI Layer  (ui/dashboard.py)                   │
│   Gradio components + event wiring (handle_run_analysis, etc.)   │
│   ❌ No business logic   ❌ No HTML formatting                    │
└─────────────────────────────┬────────────────────────────────────┘
                              │ calls
┌─────────────────────────────▼────────────────────────────────────┐
│              Services Layer  (core/services.py)                   │
│                                                                   │
│   AnalysisService          PortfolioService     HistoryService    │
│   - run_analysis()         - save_portfolio()   - get_recent()   │
│   - _run_single_interval() - load_portfolio()   - get_stats()    │
│   - _validate_inputs()                          - get_detail()   │
│                                                                   │
│   Config: core/config.py        Utils: core/utils.py             │
│   Renderers: core/renderers.py                                   │
└──────────┬───────────────────┬──────────────────┬───────────────┘
           │                   │                  │
     ┌─────▼──────┐   ┌────────▼───────┐  ┌──────▼──────┐
     │ Data Engine │   │  Agent Core    │  │  Database   │
     │             │   │                │  │             │
     │ Orchestrator│   │ ReactOrchest.  │  │ RunDatabase │
     │ GoldFetcher │   │ PromptBuilder  │  │ PostgreSQL  │
     │ Indicators  │   │ LLMClientFact. │  │             │
     │ NewsFetcher │   │ RiskManager    │  │             │
     └─────────────┘   └────────────────┘  └─────────────┘
```

### Dependency Injection Map

```
dashboard.py
  └── init_services(skill_registry, role_registry, orchestrator, db)
        ├── AnalysisService(skill_registry, role_registry, orchestrator, db)
        ├── PortfolioService(db)
        └── HistoryService(db)
```

ทุก service รับ dependencies ผ่าน constructor → testable, swappable

---

## 3. Configuration (core/config.py)

### Provider Choices
```python
PROVIDER_CHOICES = [
    ("gemini-2.5-flash",      "gemini"),
    ("llama-3.3-70b-versatile","groq"),
    ("mock",                   "mock"),
]
```

### Interval Weights (Weighted Voting)
```python
INTERVAL_WEIGHTS = {
    "1m":  0.03,   # Scalping — noisy มาก
    "5m":  0.05,   # Day trading
    "15m": 0.10,
    "30m": 0.15,
    "1h":  0.22,   # Sweet spot — balanced
    "4h":  0.30,   # Strong signal — น้อย noise
    "1d":  0.12,   # Trend confirmation
    "1w":  0.03,   # Long-term — อาจ outdated
}
# sum = 1.0 (validated at import time)
```

### Other Constants
| Key | Value | ใช้ที่ |
|-----|-------|--------|
| `VALIDATION["min_cash_for_buy"]` | 1000 | PortfolioService |
| `SERVICE_CONFIG["max_retries"]` | 3 | AnalysisService retry loop |
| `SERVICE_CONFIG["retry_delay"]` | 2 | exponential backoff base |
| `DEFAULT_PORTFOLIO` | cash=1500, gold=0 | fallback เมื่อ DB ว่าง |
| `UI_CONFIG["port"]` | 10000 (env: PORT) | dashboard.launch() |

---

## 4. End-to-End Data Flow (Method-Level)

### Full Flow Overview

```
User กด ▶ Run Analysis
  │
  ▼
handle_run_analysis(provider, period, intervals)          [dashboard.py]
  │
  ├─── PHASE 1: Data Collection ──────────────────────────────────────
  │     AnalysisService.run_analysis()
  │       └── GoldTradingOrchestrator.run(history_days=N)
  │             ├── GoldDataFetcher.fetch_all()
  │             ├── TechnicalIndicators(df).to_dict()
  │             ├── GoldNewsFetcher.to_dict()
  │             └── returns market_state dict
  │
  ├─── PHASE 2: Multi-Interval LLM Loop ──────────────────────────────
  │     for interval in intervals:
  │       _run_single_interval(provider, market_state, interval)
  │         ├── LLMClientFactory.create(provider)
  │         ├── PromptBuilder.build_final_decision(market_state, [])
  │         │     └── _format_market_state(state)
  │         ├── LLMClient.call(prompt_pkg)
  │         └── ReactOrchestrator.run(market_state)
  │               └── extract_json(raw_response)
  │
  ├─── PHASE 3: Weighted Voting ───────────────────────────────────────
  │     calculate_weighted_vote(interval_results)
  │       └── returns voting_result
  │
  ├─── PHASE 4: Persistence ───────────────────────────────────────────
  │     RunDatabase.save_run(provider, voting_result, market_state)
  │       └── returns run_id
  │
  └─── PHASE 5: Render UI ─────────────────────────────────────────────
        TraceRenderer.format_trace_html(trace)
        HistoryRenderer.format_history_html(rows)
        StatsRenderer.format_stats_html(stats)
```

---

### PHASE 1: Data Collection

```
GoldTradingOrchestrator.run(history_days=N, save_to_file=True)
│
├── Step 1.1 — Price Data
│   GoldDataFetcher.fetch_all(history_days=N, interval="1h")
│     └── yfinance.download('GC=F', period='Nd', interval='1h')
│           Input : history_days: int, interval: str
│           Output: {
│                     spot_price: {price_usd_per_oz, timestamp, source},
│                     forex:      {USDTHB, timestamp, source},
│                     thai_gold:  {spot_price_thb, source},
│                     ohlcv_df:   pd.DataFrame[open,high,low,close,volume]
│                   }
│
├── Step 1.2 — Technical Indicators
│   TechnicalIndicators(ohlcv_df).to_dict()
│     Input : pd.DataFrame (N candles)
│     Output: {
│               rsi:  {value: 58.5, period: 14, signal: "neutral"},
│               macd: {macd_line, signal_line, histogram, signal},
│               trend:{ema_20, ema_50, trend: "uptrend|downtrend|neutral"},
│               bollinger: {upper, lower, mid}
│             }
│
├── Step 1.3 — News (Parallel)
│   GoldNewsFetcher.to_dict()
│     ThreadPoolExecutor(max_workers=10)
│       └── fetch_category(cat_key) × 8 categories (parallel)
│             ├── _fetch_yfinance_raw(symbol)  → NewsArticle list
│             └── _fetch_rss(url, keywords)    → NewsArticle list
│     → _apply_global_limit()  [Greedy Packing by token_budget]
│     → score_sentiment_batch([titles])
│           └── HuggingFace FinBERT API (per-item, retry×3)
│                 positive → +confidence
│                 negative → -confidence
│                 neutral  → 0.0
│     Input : max_per_category=5, token_budget=3000
│     Output: {
│               total_articles: int,
│               token_estimate: int,
│               by_category: {cat_key: {label, count, articles[]}},
│               errors: []
│             }
│
├── Step 1.4 — Recent Price Action (5 candles)
│   ohlcv_df.tail(5) → convert TZ → list of {datetime, open, high, low, close, volume}
│
└── Step 1.5 — Assemble & Save
    payload = {meta, data_sources, market_data, technical_indicators, news}
    → save: agent_core/data/latest.json
    → save: agent_core/data/payload_{timestamp}.json
    Output: market_state dict
```

**Input/Output — Phase 1**

| | |
|---|---|
| **Input** | `history_days: int`, `interval: str` |
| **Output** | `market_state: dict` (meta + market_data + technical_indicators + news) |

---

### PHASE 2: Multi-Interval LLM Loop

```
AnalysisService._run_single_interval(provider, market_state, interval)
│
├── LLMClientFactory.create(provider)
│     Registry lookup: "gemini" → GeminiClient(**kwargs)
│     Output: LLMClient instance
│
├── PromptBuilder(role_registry, AIRole.ANALYST)
│     .build_final_decision(market_state, tool_results=[])
│     │
│     ├── _get_system()                            [cached]
│     │     role_def = RoleRegistry.get(AIRole.ANALYST)
│     │     tools = SkillRegistry.get_tools_for_skills(["market_analysis"])
│     │     → role_def.get_system_prompt({role_title, available_tools})
│     │     Output: system prompt str (~300 tokens)
│     │
│     └── _format_market_state(market_state)
│           ├── spot_price, RSI(period/value/signal)
│           ├── MACD (macd_line / signal_line / histogram)
│           ├── Trend (ema_20, ema_50, trend label)
│           ├── News — top-1 article per category (max |sentiment_score|)
│           ├── [optional] price_trend section (backtest)
│           └── Portfolio section:
│                 cash_balance, gold_grams, cost_basis_thb
│                 current_value_thb, unrealized_pnl, trades_today
│                 can_buy  = "YES" | "NO (cash ฿X < ฿1000 minimum)"
│                 can_sell = "YES" | "NO (gold_grams = 0)"
│           Output: formatted user context str (~200 tokens)
│
│     Returns: PromptPackage(system, user, step_label="THOUGHT_FINAL")
│
├── ReactOrchestrator.run(market_state)
│     [max_tool_calls=0 → fast path]
│     │
│     ├── prompt_builder.build_final_decision(market_state, [])
│     ├── llm.call(prompt_package)           → raw str (JSON expected)
│     │     GeminiClient:
│     │       @with_retry(max_attempts=3, delay=2.0)
│     │       genai.Client.models.generate_content(
│     │         model="gemini-2.5-flash",
│     │         contents=prompt.user,
│     │         config={system_instruction: prompt.system}
│     │       )
│     │       → logs: llm_trace.log (REQUEST + RESPONSE)
│     │
│     └── extract_json(raw_response)
│           1. strip markdown fences: ```json ... ```
│           2. regex search r"\{.*\}" (DOTALL)
│           3. json.loads(match)
│           4. fallback → {"_parse_error": True, "_raw": raw[:500]}
│           Output: parsed dict
│
│     Returns: {
│       "final_decision": {signal, confidence, entry_price,
│                          stop_loss, take_profit, rationale},
│       "react_trace":    [{step, iteration, response}],
│       "iterations_used": 1,
│       "tool_calls_used": 0
│     }
│
└── Returns interval_result: {
      signal:      "BUY" | "SELL" | "HOLD",
      confidence:  0.0–1.0,
      reasoning:   str,
      entry_price: float | None,
      stop_loss:   float | None,
      take_profit: float | None,
      trace:       list
    }
```

**Input/Output — Phase 2**

| | |
|---|---|
| **Input** | `provider: str`, `market_state: dict`, `interval: str` |
| **Output** | `interval_result: dict` (signal, confidence, trace per interval) |
| **Token usage** | System ~300 + User ~200 + Response ~150 = ~650 tokens/call |

---

### PHASE 3: Weighted Voting

```
calculate_weighted_vote(interval_results)    [core/utils.py]
│
│   interval_results = {
│     "1h":  {"signal": "BUY",  "confidence": 0.85},
│     "4h":  {"signal": "BUY",  "confidence": 0.90},
│     "1d":  {"signal": "SELL", "confidence": 0.60},
│   }
│
├── Step 3.1 — Collect votes with weights
│     for interval, result in interval_results.items():
│       weight = INTERVAL_WEIGHTS.get(interval, 0.0)
│       signal_votes[signal].append({confidence, weight, interval})
│       total_weight += weight
│
├── Step 3.2 — Calculate weighted score per signal
│     for signal in ["BUY", "SELL", "HOLD"]:
│       avg_conf        = mean(v.confidence for v in votes)
│       total_sig_wt    = sum(v.weight for v in votes)
│       weighted_score  = sum(v.confidence × v.weight) / total_weight
│
│     Example:
│       BUY  score = (0.85×0.22 + 0.90×0.30) / (0.22+0.30+0.12)
│                  = (0.187 + 0.270) / 0.64 = 0.714
│       SELL score = (0.60×0.12) / 0.64     = 0.113
│
├── Step 3.3 — Determine final signal
│     final_signal = argmax(weighted_score)
│     if max_weighted_score < 0.40:
│       final_signal = "HOLD"    ← confidence threshold
│
└── Returns: {
      "final_signal":        "BUY",
      "weighted_confidence": 0.714,
      "voting_breakdown": {
        "BUY":  {count, avg_conf, total_weight, weighted_score, intervals},
        "SELL": {...},
        "HOLD": {...}
      },
      "interval_details": [
        {interval, signal, confidence, weight}, ...
      ]
    }
```

**Input/Output — Phase 3**

| | |
|---|---|
| **Input** | `interval_results: dict[str, dict]` |
| **Output** | `voting_result: dict` (final_signal, weighted_confidence, breakdown) |
| **Edge case** | ไม่มี interval หรือ weight=0 → return HOLD, confidence=0.0 |

---

### PHASE 4: Persistence

```
RunDatabase.save_run(provider, result, market_state, interval_tf, period)
│
│   result = {
│     "signal":            voting_result["final_signal"],
│     "confidence":        voting_result["weighted_confidence"],
│     "voting_breakdown":  {...}
│   }
│
├── Extract fields:
│     gold_price  ← market_state.market_data.spot_price_usd.price_usd_per_oz
│     rsi         ← market_state.technical_indicators.rsi.value
│     macd_line   ← market_state.technical_indicators.macd.macd_line
│     signal_line ← market_state.technical_indicators.macd.signal_line
│     trend       ← market_state.technical_indicators.trend.trend
│
├── INSERT INTO runs (
│     run_at, provider, interval_tf, period,
│     signal, confidence,
│     entry_price=None, stop_loss=None, take_profit=None,
│     rationale, iterations_used, tool_calls_used,
│     gold_price, rsi, macd_line, signal_line, trend,
│     react_trace (JSON str), market_snapshot (JSON str)
│   ) RETURNING id
│
└── Returns: run_id: int
```

**Portfolio UPSERT (เมื่อ user save จาก Tab Portfolio)**

```
PortfolioService.save_portfolio(cash, gold_grams, cost_basis, ...)
│
├── validate_portfolio_update(None, new_data)
│     ├── ตรวจ NaN / None
│     ├── cash_balance >= 0
│     └── gold_grams >= 0
│
└── RunDatabase.save_portfolio(data)
      INSERT INTO portfolio (id=1, ...) 
      ON CONFLICT (id) DO UPDATE SET ...   ← UPSERT เสมอ 1 row
```

**Input/Output — Phase 4**

| | |
|---|---|
| **Input** | `provider: str`, `result: dict`, `market_state: dict` |
| **Output** | `run_id: int` |

---

### PHASE 5: Render UI

```
handle_run_analysis() → returns 8 Gradio outputs:
│
├── market_box    ← str(market_state)[:1000]
├── trace_box     ← f"Trace from {best_interval} ({N} steps)"
│                    best_interval = argmax(confidence) across intervals
├── verdict_box   ← format_voting_summary(voting_result)
│                    + per-interval signal table
├── explain_html  ← TraceRenderer.format_trace_html(trace)
│                    ├── per step: color-coded card (Blue=THOUGHT, Gold=TOOL, Green=FINAL)
│                    ├── action, thought, signal+confidence
│                    └── observation (ถ้ามี tool call)
│
├── history_html  ← HistoryRenderer.format_history_html(rows)
│                    ├── HTML table: ID, Time(TH), Provider, Intervals
│                    │              Signal, Confidence, Price, RSI, Iter
│                    └── timestamp convert UTC → UTC+7
│
├── stats_html    ← StatsRenderer.format_stats_html(stats)
│                    badge: total runs, BUY%, SELL%, HOLD%, avg_conf, avg_price
│
├── multi_summary ← HTML card summary ของ weighted voting
│
└── auto_status   ← StatusRenderer.success_badge("Analysis complete - {signal}")
```

---

## 5. Data Models แต่ละ Phase

### market_state (output of Phase 1)
```python
{
  "meta": {
    "agent": "gold-trading-agent", "version": "1.1.0",
    "generated_at": "2026-03-29T17:45:00+07:00",
    "history_days": 30, "interval": "1h"
  },
  "market_data": {
    "spot_price_usd": {"price_usd_per_oz": 4495.0, "source": "yfinance"},
    "forex":          {"USDTHB": 35.8},
    "thai_gold_thb":  {"spot_price_thb": 160_000},
    "recent_price_action": [
      {"datetime": "2026-03-29 15:00:00", "open": 4490, "high": 4500,
       "low": 4488, "close": 4495, "volume": 12000},
      ...   # 5 candles
    ]
  },
  "technical_indicators": {
    "rsi":  {"value": 58.5, "period": 14, "signal": "neutral"},
    "macd": {"macd_line": 26.15, "signal_line": 17.80,
             "histogram": 8.35, "signal": "bullish_cross"},
    "trend":{"ema_20": 4490.56, "ema_50": 4473.93, "trend": "uptrend"}
  },
  "news": {
    "summary": {"total_articles": 15, "token_estimate": 2800},
    "by_category": {
      "gold_price": {"articles": [{"title": "...", "sentiment_score": 0.85}]},
      ...
    }
  },
  "portfolio": { ... }   # merge เข้ามาก่อนส่ง LLM
}
```

### portfolio (merged ก่อน LLM call)
```python
{
  "cash_balance":      1500.00,   # ฿
  "gold_grams":        0.0,       # g
  "cost_basis_thb":    0.00,      # ฿
  "current_value_thb": 0.00,      # ฿
  "unrealized_pnl":    0.00,      # ฿
  "trades_today":      0,
  "updated_at":        "2026-03-29T10:00:00Z"
}
```

### PromptPackage (input to LLMClient)
```python
PromptPackage(
  system = "You are a Gold Market Analyst. You MUST output a final trading "
           "decision as a single JSON object...",
  user   = """### MARKET STATE
Gold: $4495.0 | RSI(14): 58.5 [neutral]
MACD: 26.1483/17.8031 hist:8.3452
Trend: EMA20=4490.56 EMA50=4473.93 [uptrend]
News Highlights:
  [gold_price] Gold hits record high (sentiment: 0.89)
── Portfolio ──
  Cash: ฿1,500.00 | Gold: 0.0000 g
  can_buy: YES | can_sell: NO (gold_grams = 0)
── End Portfolio ──""",
  step_label = "THOUGHT_FINAL"
)
```

### final_decision (output of LLMClient + extract_json)
```python
{
  "action":      "FINAL_DECISION",
  "signal":      "BUY",
  "confidence":  0.85,
  "entry_price": 4495.0,    # THB ไม่ใช่ USD
  "stop_loss":   4485.0,
  "take_profit": 4520.0,
  "rationale":   "Clear uptrend: EMA20 > EMA50, MACD bullish cross..."
}
```

### voting_result (output of Phase 3)
```python
{
  "final_signal":        "BUY",
  "weighted_confidence": 0.714,
  "voting_breakdown": {
    "BUY":  {"count": 2, "avg_conf": 0.875, "total_weight": 0.52,
             "weighted_score": 0.714, "intervals": ["1h", "4h"]},
    "SELL": {"count": 1, "avg_conf": 0.600, "total_weight": 0.12,
             "weighted_score": 0.113, "intervals": ["1d"]},
    "HOLD": {"count": 0, ...}
  },
  "interval_details": [
    {"interval": "1h", "signal": "BUY",  "confidence": 0.85, "weight": 0.22},
    {"interval": "4h", "signal": "BUY",  "confidence": 0.90, "weight": 0.30},
    {"interval": "1d", "signal": "SELL", "confidence": 0.60, "weight": 0.12},
  ]
}
```

---

## 6. Core Components สำคัญ

### AnalysisService — retry loop
```python
for attempt in range(1, max_retries + 1):   # default max_retries=3
    try:
        market_state = orchestrator.run(history_days=N, save_to_file=True)
        interval_results = {}
        for interval in intervals:
            interval_results[interval] = _run_single_interval(...)
        voting_result = calculate_weighted_vote(interval_results)
        run_id = db.save_run(...)
        return {"status": "success", ...}
    except ValueError:
        return {"status": "error", "error_type": "validation"}  # ไม่ retry
    except Exception:
        time.sleep(retry_delay ** attempt)   # exponential backoff: 2s, 4s
        continue
```

### LLMClientFactory — Registry Pattern
```python
_REGISTRY = {
  "gemini":   GeminiClient,
  "openai":   OpenAIClient,
  "claude":   ClaudeClient,
  "groq":     GroqClient,
  "deepseek": DeepSeekClient,
  "mock":     MockClient,
}

# เพิ่ม provider ใหม่:
LLMClientFactory.register("myprovider", MyLLMClient)
```

### ReactOrchestrator — Fast Path (max_tool_calls=0)
```python
if self.config.max_tool_calls == 0:
    # ข้ามทั้ง loop → call LLM ครั้งเดียว
    prompt = prompt_builder.build_final_decision(market_state, [])
    raw    = llm.call(prompt)
    parsed = extract_json(raw)
    return {
        "final_decision": _build_decision(parsed),
        "react_trace":    [{"step": "THOUGHT_FINAL", "iteration": 1}],
        "iterations_used": 1,
        "tool_calls_used": 0
    }
```

### extract_json — JSON Parsing Safety Net
```python
def extract_json(raw: str) -> dict:
    # 1. strip: ```json\n...\n```
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    # 2. หา JSON object แรก
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())

    # 3. fallback
    return {"_parse_error": True, "_raw": raw[:500]}
    # → ReactOrchestrator._build_decision() จะ default signal="HOLD", confidence=0.0
```

---

## 7. Trading Constraints

### Hard Constraints (enforce ใน System Prompt)

| Rule | Logic | ผล |
|------|-------|-----|
| Minimum Buy | `cash < 1000` → `can_buy = NO` | LLM ห้าม signal BUY |
| No Short Sell | `gold_grams == 0` → `can_sell = NO` | LLM ห้าม signal SELL |
| Starting Capital | ฿1,500 initial (default portfolio) | — |
| Price Unit | entry/stop/take ต้องเป็น THB ไม่ใช่ USD | ระบุใน system prompt |
| Capital Preservation | ห้าม risk > 50% ต่อ trade | ระบุใน system prompt |
| Daily Activity | ≥1 trade/day (BUY หรือ SELL) | HOLD ได้แค่เมื่อ can_buy=NO AND can_sell=NO |

### Soft Constraints (LLM Reasoning)
- uptrend → prefer BUY, downtrend → prefer SELL
- RSI > 70 = overbought (หลีกเลี่ยง BUY), RSI < 30 = oversold (หลีกเลี่ยง SELL)
- MACD histogram ขยาย = momentum แรง
- Risk/Reward: (take_profit - entry) > (entry - stop_loss)

---

## 8. Database Schema

```sql
-- Run history
CREATE TABLE runs (
    id               SERIAL PRIMARY KEY,
    run_at           TEXT NOT NULL,        -- UTC ISO timestamp
    provider         TEXT NOT NULL,        -- "gemini", "groq", ...
    interval_tf      TEXT,                 -- "1h,4h,1d" (comma-separated intervals)
    period           TEXT,                 -- "1mo", "3mo"
    signal           TEXT,                 -- "BUY" | "SELL" | "HOLD"
    confidence       REAL,                 -- 0.0–1.0
    entry_price      REAL,                 -- THB (nullable)
    stop_loss        REAL,                 -- THB (nullable)
    take_profit      REAL,                 -- THB (nullable)
    rationale        TEXT,
    iterations_used  INTEGER,
    tool_calls_used  INTEGER,
    gold_price       REAL,                 -- USD/oz
    rsi              REAL,
    macd_line        REAL,
    signal_line      REAL,
    trend            TEXT,
    react_trace      TEXT,                 -- JSON array (stringified)
    market_snapshot  TEXT                  -- full market_state (stringified)
);

-- Portfolio snapshot (1 row เสมอ, id=1)
CREATE TABLE portfolio (
    id                SERIAL PRIMARY KEY,
    cash_balance      REAL NOT NULL DEFAULT 1500.0,
    gold_grams        REAL NOT NULL DEFAULT 0.0,
    cost_basis_thb    REAL NOT NULL DEFAULT 0.0,
    current_value_thb REAL NOT NULL DEFAULT 0.0,
    unrealized_pnl    REAL NOT NULL DEFAULT 0.0,
    trades_today      INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT NOT NULL
);
```

**Recommended Indexes**
```sql
CREATE INDEX idx_runs_provider ON runs(provider);
CREATE INDEX idx_runs_signal   ON runs(signal);
CREATE INDEX idx_runs_run_at   ON runs(run_at DESC);
```

---

## 9. Environment Setup

### 9.1 Prerequisites
- **Python**: 3.9+
- **PostgreSQL**: 12+ (local หรือ Render/cloud)
- **API Keys**: อย่างน้อย 1 LLM key + HF_TOKEN (สำหรับ FinBERT)

### 9.2 Clone & Virtual Environment
```bash
cd Src/

# สร้าง virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate          # macOS / Linux
# หรือ
venv\Scripts\activate             # Windows

# Verify
which python    # ควรเห็น .../venv/bin/python
```

### 9.3 Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

requirements.txt หลัก:
```
yfinance>=0.2.28
pandas>=1.5.0
numpy>=1.23.0
feedparser>=6.0.10
requests>=2.31.0
tiktoken>=0.6.0
gradio>=4.0.0
psycopg2-binary>=2.9.0
python-dotenv>=0.21.0
google-genai>=0.3.0
openai>=1.0.0
anthropic>=0.7.0
groq>=0.4.0
```
> **Note**: ไม่ต้องติดตั้ง `torch` หรือ `transformers` — FinBERT รันผ่าน HuggingFace Inference API

### 9.4 Environment Variables
สร้างไฟล์ `.env` ใน `Src/`:
```bash
# ── LLM API Keys (ต้องมีอย่างน้อย 1 ตัว) ──────────────────
GEMINI_API_KEY="your-gemini-api-key"
GROQ_API_KEY="your-groq-api-key"
OPENAI_API_KEY="your-openai-api-key"
ANTHROPIC_API_KEY="your-anthropic-api-key"
DEEPSEEK_API_KEY="your-deepseek-api-key"

# ── Sentiment Analysis (FinBERT) ───────────────────────────
HF_TOKEN="your-huggingface-token"
# สมัครได้ที่: https://huggingface.co/settings/tokens

# ── Database ───────────────────────────────────────────────
DATABASE_URL="postgresql://username:password@localhost:5432/goldtrader"
# Render example: postgresql://user:pass@dpg-xxx.singapore-postgres.render.com/goldtrader

# ── Optional ───────────────────────────────────────────────
LOG_LEVEL="INFO"    # DEBUG | INFO | WARNING | ERROR
PORT=10000          # Gradio dashboard port
```

### 9.5 Database Initialization
```bash
# สร้าง database (local PostgreSQL)
psql -U postgres -c "CREATE DATABASE goldtrader;"

# Tables สร้างอัตโนมัติตอน RunDatabase.__init__() ถูกเรียก
# ไม่ต้องรัน migration script เพิ่ม
```

---

## 10. How to Run

### 10.1 Dashboard Mode (แนะนำ)
```bash
cd Src/
source venv/bin/activate
python ui/dashboard.py
```
เปิด browser: **http://localhost:10000**

**Tab 1: 📊 Live Analysis**
1. เลือก **Provider** (Gemini / Groq / Mock)
2. เลือก **Period** (1d, 5d, 1mo, 3mo, ...)
3. เลือก **Candle Intervals** (checkbox หลายตัวพร้อมกันได้)
4. กด **▶ Run Analysis**
5. ดูผล: Weighted Voting Summary + Per-interval details + ReAct Trace

**Tab 2: 📜 Run History**
- ตารางแสดง 50 runs ล่าสุด พร้อม stats (BUY/SELL/HOLD %)
- กรอก Run ID → โหลด trace + decision รายละเอียด

**Tab 3: 💼 Portfolio**
- กรอก cash/gold/cost/value/pnl/trades จากแอพ ออม NOW
- กด **Save** → บันทึก → LLM รู้ constraint can_buy/can_sell ใน run ถัดไป

### 10.2 CLI Mode
```bash
cd Src/
source venv/bin/activate

# Basic run (Gemini, fetch ข้อมูลใหม่)
python main.py

# เลือก provider
python main.py --provider gemini
python main.py --provider groq
python main.py --provider mock      # ทดสอบ ไม่เรียก API จริง

# ใช้ข้อมูล cache (ไม่ fetch ใหม่ — เร็วกว่า)
python main.py --provider gemini --skip-fetch

# ตั้งค่าเพิ่มเติม
python main.py \
    --provider gemini \
    --iterations 7 \
    --period 90d \
    --interval 1h \
    --output Output/my_result.json
```

**CLI Arguments**

| Argument | Default | Description |
|----------|---------|-------------|
| `--provider` | `gemini` | LLM provider |
| `--iterations` | `5` | Max ReAct iterations |
| `--skip-fetch` | `False` | ใช้ latest.json แทนการ fetch ใหม่ |
| `--output` | `Output/result_output.json` | path บันทึก JSON |
| `--period` | `90d` | yfinance period |
| `--interval` | `1d` | Candle timeframe |

### 10.3 ตรวจสอบ Logs
```bash
# System log (real-time)
tail -f logs/system.log

# LLM trace (prompt + response ทุก call)
tail -f logs/llm_trace.log

# ดู errors
grep "ERROR" logs/system.log

# นับ BUY signals
grep "final_signal=BUY" logs/system.log | wc -l
```

### 10.4 Enable Debug Logging
```bash
export LOG_LEVEL="DEBUG"
python ui/dashboard.py
```

---

## 11. Extensibility

### เพิ่ม LLM Provider ใหม่
```python
# 1. สร้าง class ใน agent_core/llm/client.py
class MyLLMClient(LLMClient):
    def call(self, prompt_package: PromptPackage) -> str:
        ...
    def is_available(self) -> bool:
        return self._client is not None

# 2. Register
LLMClientFactory.register("myprovider", MyLLMClient)

# 3. เพิ่มใน config.py
PROVIDER_CHOICES.append(("my-model-name", "myprovider"))
```

### เพิ่ม Technical Indicator ใหม่
```python
# ใน data_engine/indicators.py
def calculate_roc(self) -> dict:
    roc = self.df['close'].pct_change(periods=12) * 100
    return {"value": roc.iloc[-1],
            "signal": "positive" if roc.iloc[-1] > 0 else "negative"}

# เพิ่มใน to_dict()
def to_dict(self) -> dict:
    return {**existing, "roc": self.calculate_roc()}
```

### ปรับ Interval Weights
```python
# ใน core/config.py — เปลี่ยน weight โดยไม่แตะ business logic
INTERVAL_WEIGHTS = {
    "1h": 0.40,   # เพิ่ม weight 1h
    "4h": 0.40,   # เพิ่ม weight 4h
    "1d": 0.20,   # ลด long-term
    # อื่นๆ = 0 จะถูก skip อัตโนมัติ
}
```

---

**Last Updated**: 2026-03-29
**Version**: 3.2
**Author**: PM Team