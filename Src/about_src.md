# GoldTrader — Complete Agent Architecture Documentation v3.3

---

## Executive Summary

**GoldTrader** คือ production-grade **ReAct+LLM trading agent** สำหรับวิเคราะห์ตลาดทองคำบน platform ออม NOW (Hua Seng Heng)  
ผสมผสาน multi-step AI reasoning, real-time technical indicators และ portfolio-aware constraints เพื่อ generate สัญญาณ BUY/SELL/HOLD

**v3.3 — Data Engine Hardening**

| ด้าน | v3.2 (เดิม) | v3.3 (ใหม่) |
|------|-------------|-------------|
| **โครงสร้าง** | แยก UI / Services / Config / Utils ชัดเจน | เพิ่ม `ohlcv_fetcher.py` แยก OHLCV logic ออกจาก fetcher |
| **ราคาทอง Spot** | yfinance wrapper เดียว | Multi-source (TwelveData + gold-api + yfinance) พร้อม confidence score |
| **ราคาทองไทย** | คำนวณจากสูตร (fallback เท่านั้น) | Playwright WebSocket scrape Intergold.co.th → fallback สูตร |
| **OHLCV** | yfinance fetch ใหม่ทุกครั้ง | yfinance → TwelveData fallback + CSV cache + smart incremental fetch |
| **ATR Signal** | Fixed threshold | Dynamic threshold เทียบกับค่าเฉลี่ย 50 แท่ง |
| **News Sentiment** | Simple average | Weighted average ตาม impact level (direct/high/medium) |

- **LLM Engines**: Gemini, Claude, OpenAI, Groq, DeepSeek (pluggable via Factory)
- **Data**: Live OHLCV (TwelveData + yfinance) + Technical Indicators + RSS News + FinBERT Sentiment
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
├── data_engine/                         ✏️ อัปเดต v3.3 — Market Data Collection
│   ├── fetcher.py                       GoldDataFetcher — multi-source spot price + Playwright Thai gold
│   ├── ohlcv_fetcher.py                 ✨ NEW — OHLCVFetcher (TwelveData → yfinance fallback + CSV cache)
│   ├── indicators.py                    TechnicalIndicators (RSI, MACD, EMA, Bollinger, ATR dynamic)
│   ├── newsfetcher.py                   GoldNewsFetcher — RSS + yfinance + FinBERT (weighted sentiment)
│   ├── orchestrator.py                  GoldTradingOrchestrator — รวม fetcher+indicators+news+recent candles
│   └── thailand_timestamp.py            Timezone helper (UTC+7)
│
├── cache/                               ✨ NEW — OHLCV CSV Cache (auto-created)
│   └── ohlcv_XAU_USD_{interval}.csv    Cached OHLCV per symbol/interval
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
     │ OHLCVFetcher│   │ LLMClientFact. │  │             │
     │ Indicators  │   │ RiskManager    │  │             │
     │ NewsFetcher │   │                │  │             │
     └─────────────┘   └────────────────┘  └─────────────┘
```

### Dependency Injection Map

```
dashboard.py
  └── init_services(skill_registry, role_registry, orchestrator, db)
        ├── AnalysisService(skill_registry, role_registry, orchestrator, db)
        ├── PortfolioService(db)
        └── HistoryService(db)

GoldDataFetcher
  └── OHLCVFetcher(session=self.session)   ← inject shared requests.Session
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
  │       └── GoldTradingOrchestrator.run(history_days=N, interval=X)
  │             ├── GoldDataFetcher.fetch_all(history_days, interval)
  │             │     ├── fetch_gold_spot_usd()     [3 sources + confidence]
  │             │     ├── fetch_usd_thb_rate()
  │             │     ├── calc_thai_gold_price()    [Playwright → fallback]
  │             │     └── OHLCVFetcher.fetch_historical_ohlcv()
  │             │           └── TwelveData → yfinance fallback + CSV cache
  │             ├── TechnicalIndicators(df).to_dict()
  │             ├── recent_price_action (5 candles, Thai TZ)
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
GoldTradingOrchestrator.run(history_days=N, interval=X, save_to_file=True)
│
│   Note: history_days อาจส่งมาตอนเรียก run() เพื่อ override ค่าจาก __init__
│
├── Step 1.1 — Price Data
│   GoldDataFetcher.fetch_all(history_days=N, interval=X)
│
│   ┌── fetch_gold_spot_usd() — Multi-Source Spot Price ─────────────────
│   │   ดึงราคาจาก 3 แหล่งพร้อมกัน:
│   │     ① TwelveData  → GET https://api.twelvedata.com/price?symbol=XAU/USD
│   │     ② gold-api    → GET https://api.gold-api.com/price/XAU
│   │     ③ yfinance    → yf.Ticker("GC=F").history(period="1d")
│   │
│   │   compute_confidence(prices) — คำนวณความน่าเชื่อถือ:
│   │     max_diff = max deviation จาก median ของทั้ง 3 แหล่ง
│   │     confidence = max(0.0, 1.0 - max_diff × 10)
│   │     (ถ้า 3 แหล่งให้ราคาใกล้กัน confidence ≈ 1.0)
│   │
│   │   เลือก source ตามลำดับ priority:
│   │     1. กรองแหล่งที่ราคาห่าง median > 0.5% ออก
│   │     2. TwelveData → gold-api → yfinance (ตามลำดับ)
│   │     3. Extreme case (ทุกแหล่งเกิน deviation) → บังคับใช้ yfinance,
│   │        confidence = 0.0 (แจ้งเตือนบอทไม่ให้เทรดหนัก)
│   │
│   │   Output: {source, price_usd_per_oz, timestamp, confidence}
│   │
│   ├── fetch_usd_thb_rate()
│   │   GET https://api.exchangerate-api.com/v4/latest/USD
│   │   Output: {source, usd_thb, timestamp}
│   │
│   ├── calc_thai_gold_price(price_usd_per_oz, usd_thb) — Intergold WebSocket
│   │   ① Playwright (Primary):
│   │       browser.launch(headless=True) + stealth_sync (bypass bot detection)
│   │       page.goto("https://www.intergold.co.th/curr-price/")
│   │       รอ WebSocket event "updateGoldRateData" (socket.io, timeout 20s)
│   │         → ดึง bidPrice96 + offerPrice96 (ราคาทอง 96.5%)
│   │         → price_thb_per_baht_weight = (bid + ask) / 2
│   │   ② Fallback (ถ้า Playwright พัง):
│   │       price_thb_per_gram    = price_usd_per_oz × usd_thb / 31.1034768
│   │       price_thb_per_baht    = price_thb_per_gram × 15.244 × 0.965
│   │       sell_price = round((price_thb_per_baht + 50) / 50) × 50
│   │       buy_price  = round((price_thb_per_baht - 50) / 50) × 50
│   │   Output: {source, price_thb_per_baht_weight, sell_price_thb,
│   │            buy_price_thb, spread_thb}
│   │
│   └── OHLCVFetcher.fetch_historical_ohlcv(days=N, interval=X)
│         [รายละเอียดใน Step 1.1b ด้านล่าง]
│         Output: pd.DataFrame[open,high,low,close,volume]
│
├── Step 1.1b — OHLCV (OHLCVFetcher)
│   OHLCVFetcher.fetch_historical_ohlcv(days, interval,
│       twelvedata_symbol="XAU/USD", yf_symbol="GC=F", use_cache=True)
│   │
│   ├── 1. Load CSV Cache
│   │     cache/ohlcv_XAU_USD_{interval}.csv
│   │     → _ensure_utc_index() → cached_df
│   │
│   ├── 2. _calculate_fetch_days(cached_df, days, interval)
│   │     ถ้า cache มี < 50 แถว        → fetch เต็ม days
│   │     ถ้า cache เก่า < days วัน    → fetch เฉพาะส่วนที่ขาด (max 2 วัน)
│   │     ถ้า cache ครบ                → fetch เต็ม days (เพื่อ update)
│   │
│   ├── 3. Fetch from TwelveData (ถ้ามี TWELVEDATA_API_KEY)
│   │     _estimate_candles(interval, fetch_days) → output_size
│   │     _retry_request(session, TWELVEDATA_TS_URL, params, retries=3)
│   │       GET https://api.twelvedata.com/time_series
│   │         ?symbol=XAU/USD&interval={td_interval}&outputsize={N}&timezone=UTC
│   │     → df_api: DataFrame[open,high,low,close,volume]
│   │
│   ├── 4. Fallback: yfinance (ถ้า TwelveData ว่าง/พัง)
│   │     yf.Ticker("GC=F").history(period=f"{safe_days}d", interval=interval)
│   │     YF_MAX_DAYS = {1m:7, 5m:60, 15m:60, 30m:60, 1h:730, 4h:730}
│   │
│   ├── 5. Merge + Validate
│   │     _ensure_utc_index(df_api)
│   │     _validate_ohlcv(df_api):
│   │       - to_numeric(errors="coerce") → NaN rows ลบออก
│   │       - filter: high >= low, ทุกราคา > 0
│   │     concat([cached_df, df_api]) → dedup (keep="last") → sort_index
│   │     cutoff = now - timedelta(days=days) → ตัดข้อมูลเก่าออก
│   │
│   └── 6. Save Cache + Return
│         df.to_csv(cache_file)
│         Output: pd.DataFrame (UTC index)
│
├── Step 1.2 — Technical Indicators
│   TechnicalIndicators(ohlcv_df).to_dict()
│     Input : pd.DataFrame (N candles)
│     Output: {
│               rsi:       {value: 58.5, period: 14, signal: "neutral"},
│               macd:      {macd_line, signal_line, histogram, crossover},
│               bollinger: {upper, middle, lower, bandwidth, pct_b, signal},
│               atr:       {value, period: 14, volatility_level},
│               trend:     {ema_20, ema_50, sma_200, trend, golden_cross, death_cross},
│               latest_close, calculated_at
│             }
│
├── Step 1.3 — News (Parallel)
│   GoldNewsFetcher.to_dict()
│     ThreadPoolExecutor(max_workers=10)
│       └── fetch_category(cat_key) × 8 categories (parallel)
│             ├── _fetch_yfinance_raw(symbol)  → NewsArticle list
│             └── _fetch_rss(url, keywords)    → NewsArticle list
│     → Global dedup: ตัด URL ซ้ำข้าม category ออก
│     → _apply_global_limit()  [Greedy Packing by token_budget]
│     → score_sentiment_batch([titles]) FinBERT วิเคราะห์ข่าวที่เหลือทั้งหมด
│         positive → +confidence
│         negative → -confidence
│         neutral  → 0.0
│     → overall_sentiment (weighted avg ตาม impact):
│         direct=1.5, high=1.2, medium=1.0
│     Input : max_per_category=5, token_budget=3000
│     Output: {
│               total_articles: int,
│               token_estimate: int,
│               overall_sentiment: float,  ← weighted by impact level
│               by_category: {cat_key: {label, count, articles[]}},
│               errors: []
│             }
│
├── Step 1.4 — Recent Price Action (5 candles)
│   ohlcv_df.tail(5) → convert_index_to_thai_tz() → list of:
│   {datetime (ISO, UTC+7), open, high, low, close, volume}
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
├── detail_box    ← TraceRenderer.format_trace_html(trace)
│                    ReAct steps (THOUGHT → ACTION → OBSERVATION)
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
    "history_days": 30, "interval": "5m"
  },
  "market_data": {
    "spot_price_usd": {
      "price_usd_per_oz": 4495.0,
      "source": "twelvedata",
      "confidence": 0.982         # ← ใหม่ v3.3: ความน่าเชื่อถือของราคา
    },
    "forex": {"usd_thb": 35.8, "source": "exchangerate-api.com"},
    "thai_gold_thb": {
      "source": "intergold.co.th",    # ← ใหม่ v3.3: Playwright scrape
      "price_thb_per_baht_weight": 47250.0,
      "sell_price_thb": 47300,
      "buy_price_thb": 47200,
      "spread_thb": 100
    },
    "recent_price_action": [
      {"datetime": "2026-03-29T15:00:00+07:00", "open": 4490, "high": 4500,
       "low": 4488, "close": 4495, "volume": 12000},
      ...   # 5 candles (Thai TZ)
    ]
  },
  "technical_indicators": {
    "rsi":       {"value": 58.5, "period": 14, "signal": "neutral"},
    "macd":      {"macd_line": 26.15, "signal_line": 17.80,
                  "histogram": 8.35, "crossover": "bullish_cross"},
    "bollinger": {"upper": 4510.0, "middle": 4490.0, "lower": 4470.0,
                  "bandwidth": 0.0089, "pct_b": 0.625, "signal": "inside"},
    "atr":       {"value": 12.5, "period": 14,
                  "volatility_level": "normal"},  # ← dynamic threshold v3.3
    "trend":     {"ema_20": 4490.56, "ema_50": 4473.93, "sma_200": 4420.0,
                  "trend": "uptrend", "golden_cross": true, "death_cross": false},
    "latest_close": 4495.0,
    "calculated_at": "2026-03-29T17:45:00+07:00"
  },
  "news": {
    "summary": {
      "total_articles": 15, "token_estimate": 2800,
      "overall_sentiment": 0.312    # ← weighted by impact level v3.3
    },
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

### GoldDataFetcher — Multi-Source Price + Confidence
```python
class GoldDataFetcher:
    def __init__(self):
        self.session = requests.Session()
        self.ohlcv_fetcher = OHLCVFetcher(session=self.session)  # inject session

    def compute_confidence(self, prices: dict) -> float:
        # penalty = max deviation จาก median × 10
        # confidence = max(0.0, 1.0 - penalty)
        # ตัวอย่าง: ถ้า 3 แหล่งห่างกัน 0.3% → confidence = 0.97
        ...

    def fetch_all(self, history_days=90, interval="1d") -> dict:
        spot  = self.fetch_gold_spot_usd()      # 3 sources + confidence
        forex = self.fetch_usd_thb_rate()
        thai  = self.calc_thai_gold_price(...)   # Playwright → fallback
        ohlcv = self.ohlcv_fetcher.fetch_historical_ohlcv(
                    days=history_days, interval=interval)
        return {"spot_price": spot, "forex": forex,
                "thai_gold": thai, "ohlcv_df": ohlcv, ...}
```

### OHLCVFetcher — Smart Cache + Dual Source
```python
class OHLCVFetcher:
    def fetch_historical_ohlcv(self, days, interval,
            twelvedata_symbol="XAU/USD", yf_symbol="GC=F",
            use_cache=True, cache_dir=BASE_DIR/"cache") -> pd.DataFrame:

        # 1. Load CSV cache
        # 2. _calculate_fetch_days() — ลด fetch range ถ้า cache ยังใหม่
        # 3. TwelveData: _retry_request(retries=3, backoff=2)
        #    interval map: "5m" → "5min", "1h" → "1h", "1d" → "1day"
        # 4. yfinance fallback (ถ้า TD ว่าง/พัง)
        # 5. merge + _validate_ohlcv() + save cache
        ...

# ตัวแปรสภาพแวดล้อมที่ต้องใช้:
TWELVEDATA_API_KEY = os.getenv("TWELVEDATA_API_KEY")  # optional; ถ้าไม่มี = yfinance only
```

### TechnicalIndicators — ATR Dynamic Threshold (v3.3)
```python
def atr(self) -> ATRResult:
    val = float(self.df["atr_14"].iloc[-1])

    # Dynamic threshold: เทียบกับค่าเฉลี่ย ATR ย้อนหลัง 50 แท่ง
    atr_sma = self.df["atr_14"].rolling(50).mean()
    avg_val = float(atr_sma.iloc[-1]) if len(atr_sma.dropna()) > 0 else val

    if val < avg_val * 0.8:    volatility_level = "low"
    elif val > avg_val * 1.5:  volatility_level = "high"
    else:                      volatility_level = "normal"

    return ATRResult(value=round(val, 2), period=14,
                     volatility_level=volatility_level)

# v3.2 (เดิม): ใช้ fixed absolute threshold
# v3.3 (ใหม่): dynamic relative threshold → อ่านค่า volatility ถูกต้องกว่า
#               ในทุก timeframe และทุกช่วงราคา
```

### TechnicalIndicators — get_reliability_warnings() (v3.3)
```python
def get_reliability_warnings(self, interval: str) -> list[str]:
    """แจ้งเตือนเมื่อ indicator signal อาจไม่น่าเชื่อถือ"""
    warnings = []
    t = self.trend()

    # ตรวจ MA convergence (EMA20/50/SMA200 อยู่ใกล้กันมาก = sideways)
    ma_range = max(t.ema_20, t.ema_50, t.sma_200) \
             - min(t.ema_20, t.ema_50, t.sma_200)
    if ma_range < 1.0:
        warnings.append(
            f"EMA20/50/SMA200 ห่างกันแค่ {ma_range:.4f} — "
            f"trend signal '{t.trend}' ไม่น่าเชื่อถือ ตลาดอาจ sideways"
        )

    # แจ้งเตือน interval สั้น (SMA200 ไม่ใช่ long-term trend จริงๆ)
    if interval in ("1m", "5m", "15m"):
        warnings.append(
            f"Interval {interval}: SMA200 คำนวณจากแท่งสั้น "
            f"ไม่ใช่ long-term trend"
        )

    return warnings
```

### GoldNewsFetcher — Weighted Sentiment + Global Dedup (v3.3)
```python
# Global dedup ข้าม category (ก่อนส่งเข้า token budget)
global_seen_urls = set()
for cat_key, articles in by_category_raw.items():
    unique = [a for a in articles if a.url not in global_seen_urls]
    global_seen_urls.update(a.url for a in unique)
    by_category_raw[cat_key] = unique

# Weighted overall_sentiment ตาม impact level (v3.3)
impact_weights = {"direct": 1.5, "high": 1.2, "medium": 1.0}
weighted_sum   = sum(a.sentiment_score * impact_weights.get(a.impact_level, 1.0)
                     for a in surviving_articles)
overall_sentiment = round(weighted_sum / total_weight, 4)

# v3.2 (เดิม): simple mean ของทุก article
# v3.3 (ใหม่): ข่าว impact=direct (ราคาทอง, USD/THB) มีน้ำหนัก 1.5x
#               ข่าว impact=high (Fed, เงินเฟ้อ, ภูมิรัฐศาสตร์) มีน้ำหนัก 1.2x
```

### GoldTradingOrchestrator — Interval Parameter + History Override (v3.3)
```python
class GoldTradingOrchestrator:
    def __init__(self, history_days=90, interval="1d",   # ← interval param
                 max_news_per_cat=5, output_dir=None):
        self.interval = interval   # เก็บไว้ใช้ใน run()
        ...

    def run(self, save_to_file=True,
            history_days=None) -> dict:   # ← optional override
        # ถ้าส่ง history_days มาตอน run() → ใช้ค่านั้น
        # ไม่ส่ง → ใช้ self.history_days จาก __init__
        effective_days = history_days if history_days is not None \
                         else self.history_days
        ...
        # Step 2.5: recent_price_action
        recent = ohlcv_df.tail(5).copy()
        recent.index = convert_index_to_thai_tz(recent.index)
        recent_price_action = [
            {"datetime": idx.isoformat(), "open": ..., "close": ...}
            for idx, row in recent.iterrows()
        ]
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
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
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
- ATR volatility_level = "high" → ระวัง stop loss กว้างขึ้น
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
- **Playwright**: ต้องติดตั้ง browser (`playwright install chromium`) สำหรับ Thai gold price

### 9.2 Clone & Virtual Environment
```bash
cd Src/

python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# หรือ
venv\Scripts\activate             # Windows

which python    # ควรเห็น .../venv/bin/python
```

### 9.3 Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt

# ติดตั้ง Playwright browser (สำหรับ Thai gold price)
playwright install chromium
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
playwright>=1.40.0
playwright-stealth>=1.0.0
beautifulsoup4>=4.12.0
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

# ── Market Data ────────────────────────────────────────────
TWELVEDATA_API_KEY="your-twelvedata-api-key"   # ← ใหม่ v3.3 (optional แต่แนะนำ)
# ถ้าไม่มี TWELVEDATA_API_KEY จะ fallback ไปใช้ yfinance อย่างเดียว

# ── Sentiment Analysis (FinBERT) ───────────────────────────
HF_TOKEN="your-huggingface-token"
# สมัครได้ที่: https://huggingface.co/settings/tokens

# ── Database ───────────────────────────────────────────────
DATABASE_URL="postgresql://username:password@localhost:5432/goldtrader"

# ── Optional ───────────────────────────────────────────────
LOG_LEVEL="INFO"    # DEBUG | INFO | WARNING | ERROR
PORT=10000          # Gradio dashboard port
```

### 9.5 Database Initialization
```bash
psql -U postgres -c "CREATE DATABASE goldtrader;"
# Tables สร้างอัตโนมัติตอน RunDatabase.__init__() ถูกเรียก
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

python main.py
python main.py --provider gemini
python main.py --provider groq
python main.py --provider mock      # ทดสอบ ไม่เรียก API จริง
python main.py --provider gemini --skip-fetch

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

### 10.3 Export JSON (conJSON.py)
```bash
cd Src/data_engine/
python conJSON.py
# → บันทึก output/gold_data_{timestamp}.json
# ใช้ config: history_days=30, interval="5m", max_news_per_cat=5
```

### 10.4 ตรวจสอบ Logs
```bash
tail -f logs/system.log
tail -f logs/llm_trace.log
grep "ERROR" logs/system.log
grep "final_signal=BUY" logs/system.log | wc -l
```

### 10.5 Enable Debug Logging
```bash
export LOG_LEVEL="DEBUG"
python ui/dashboard.py
```

---

## 11. Extensibility

### เพิ่ม LLM Provider ใหม่
```python
class MyLLMClient(LLMClient):
    def call(self, prompt_package: PromptPackage) -> str: ...
    def is_available(self) -> bool: return self._client is not None

LLMClientFactory.register("myprovider", MyLLMClient)
PROVIDER_CHOICES.append(("my-model-name", "myprovider"))
```

### เพิ่ม Technical Indicator ใหม่
```python
# ใน data_engine/indicators.py
def calculate_roc(self) -> dict:
    roc = self.df['close'].pct_change(periods=12) * 100
    return {"value": roc.iloc[-1],
            "signal": "positive" if roc.iloc[-1] > 0 else "negative"}

def to_dict(self) -> dict:
    return {**existing, "roc": self.calculate_roc()}
```

### เพิ่มแหล่งข้อมูล OHLCV ใหม่
```python
# ใน data_engine/ohlcv_fetcher.py — เพิ่ม source ใน fetch_historical_ohlcv()
# หลัง TwelveData block และก่อน yfinance fallback block
if df_api.empty:
    # ใส่ logic ดึงจาก source ใหม่ตรงนี้
    ...
```

### ปรับ Interval Weights
```python
# ใน core/config.py
INTERVAL_WEIGHTS = {
    "1h": 0.40,
    "4h": 0.40,
    "1d": 0.20,
}
```

---

**Last Updated**: 2026-03-31
**Version**: 3.3
**Author**: PM Team