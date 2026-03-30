# GoldTrader — Complete Agent Architecture Documentation v3.3

---

## 1. Overview & Goal

**GoldTrader** คือ production-grade **ReAct + LLM trading agent** สำหรับวิเคราะห์และตัดสินใจเทรดทองคำบนแพลตฟอร์ม **ออม NOW** (Hua Seng Heng)

### 1.1 Mission

ผสมผสาน multi-step AI reasoning เข้ากับ real-time technical indicators และ news sentiment เพื่อ generate สัญญาณ **BUY / SELL / HOLD** ที่มีความน่าเชื่อถือสูง

### 1.2 Why LLM for Gold Trading?

อัลกอริทึมธรรมดา (Rule-based) สามารถอ่าน RSI หรือ MACD ได้ แต่ไม่สามารถ **"อ่านบริบท"** ได้ เช่น

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

## 2. Evaluation Metrics

### 2.1 Directional Accuracy

วัดว่า LLM ทายทิศทางราคาถูกหรือเปล่า

```
Directional Accuracy = (Correct Signals) / (Total Non-HOLD Signals) × 100%
```

- `BUY` ถูก = ราคา candle ถัดไปขึ้น (UP)
- `SELL` ถูก = ราคา candle ถัดไปลง (DOWN)
- `HOLD` ถูก = ราคาไม่เปลี่ยน (FLAT)

### 2.2 Signal Sensitivity

```
Sensitivity = (Total Non-HOLD Signals) / (Total Candles) × 100%
```

วัดว่า agent เทรดบ่อยแค่ไหน — สูงเกินไป = overtrading, ต่ำเกินไป = missed opportunities

### 2.3 Average Net PnL per Correct Signal

```
Avg Net PnL = mean(price_change - spread - commission)  for correct signals only
```

### 2.4 Financial Risk Metrics (Forward-Looking)

เมื่อมี equity curve จากการรัน backtest เต็ม จะคำนวณ:

| Metric | สูตร | เป้าหมาย |
|--------|------|----------|
| **Sharpe Ratio** | `(mean_return - risk_free) / std_return × √252` | > 1.0 = acceptable, > 2.0 = good |
| **Sortino Ratio** | `mean_return / downside_std × √252` | > 1.5 = good (penalize downside only) |
| **Max Drawdown (MDD)** | `max(peak - trough) / peak × 100%` | < 20% = acceptable |
| **Win Rate** | `profitable_trades / total_trades × 100%` | > 50% |
| **Profit Factor** | `gross_profit / gross_loss` | > 1.5 = good |

> **หมายเหตุ:** Sharpe/Sortino/MDD ต้องคำนวณจาก equity curve (portfolio value ต่อ candle) ซึ่งต้องรัน `SimPortfolio` simulation เต็มรูปแบบ ไม่ใช่แค่ directional accuracy

---

## 3. Project Structure

```
Src/
│
├── agent_core/                          ← AI Agent Core (ไม่เปลี่ยนใน v3.2)
│   ├── config/
│   │   ├── roles.json                   Role definitions (analyst, risk_manager)
│   │   └── skills.json                  Skill → Tool registry
│   │
│   ├── core/
│   │   ├── prompt.py                    PromptBuilder, RoleRegistry, SkillRegistry
│   │   ├── react.py                     ReactOrchestrator (Thought→Action→Observation loop)
│   │   └── risk.py                      RiskManager — validate & adjust final decision
│   │
│   ├── data/
│   │   ├── latest.json                  Market snapshot ล่าสุด (auto-updated)
│   │   └── payload_*.json               Historical data dumps
│   │
│   └── llm/
│       └── client.py                    6 LLMClient + OllamaClient + LLMClientFactory
│
├── data_engine/   
│   ├── interceptor_xauthb_fetch/
│   │   └── interceptor.py                  ✏️ อัปเดต v3.3 — Market Data Collection
│   |                                     GoldDataFetcher — multi-source spot 
│   |                                    ✨ NEW — OHLCVFetcher (TwelveData →
|   |                                      yfinance fallback + CSV cache)
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
├── database.py                          RunDatabase (PostgreSQL ORM)
├── main.py                              CLI entry point (production)
├── logger_setup.py                      THTimeFormatter + log_method decorator
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

---

## 5. Main Full Flow Diagram (Method Level)

# Web Dashboard

```
User กด ▶ Run Analysis
  │
  ▼
handle_run_analysis(provider, period, intervals)           [ui/dashboard.py]
  │
  ├─── PHASE 1: Data Collection ─────────────────────────────────────────
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
  │             │     ├── ThreadPoolExecutor(8 categories, parallel)
  │             │     ├── FinBERT via HuggingFace API (sentiment)
  │             │     └── Greedy packing by token_budget (3000 tokens)
  │             └── returns market_state dict
  │
  ├─── PHASE 2: Multi-Interval LLM Loop ─────────────────────────────────
  │     for interval in intervals:
  │       _run_single_interval(provider, market_state, interval)
  │         ├── LLMClientFactory.create(provider)
  │         ├── PromptBuilder(role_registry, AIRole.ANALYST)
  │         │     ├── _get_system()           → system prompt (~300 tokens)
  │         │     └── _format_market_state()  → user context (~200 tokens)
  │         └── ReactOrchestrator.run(market_state)
  │               ├── [max_tool_calls=0 → fast path]
  │               ├── llm.call(prompt_package)  → raw JSON string
  │               ├── extract_json(raw)          → parsed dict
  │               ├── _build_decision(parsed)    → final_decision dict
  │               └── RiskManager.evaluate()     → adjusted_decision
  │
  ├─── PHASE 3: Weighted Voting ──────────────────────────────────────────
  │     calculate_weighted_vote(interval_results)
  │       ├── INTERVAL_WEIGHTS.get(interval)   → weight per interval
  │       ├── weighted_score = Σ(confidence × weight) / total_weight
  │       └── final_signal = argmax(weighted_score) if score ≥ 0.40
  │
  ├─── PHASE 4: Persistence ──────────────────────────────────────────────
  │     RunDatabase.save_run(provider, voting_result, market_state)
  │       └── INSERT INTO runs (...) RETURNING id
  │
  └─── PHASE 5: Render UI ────────────────────────────────────────────────
        TraceRenderer.format_trace_html(trace)
        HistoryRenderer.format_history_html(rows)
        StatsRenderer.format_stats_html(stats)
        → returns 8 Gradio output components
```

# Run Backtest On Main

```
main()  [Entry Point]
 └── run_main_backtest()
      ├── 1. MainPipelineBacktest() [Initialization]
      │
      ├── 2. bt.run() [Core Execution]
      │    ├── load_and_aggregate()
      │    │    └── _ensure_indicators()
      │    ├── _load_main_components()
      │    │
      │    ├── [For loop: วนลูปทีละ Candle]
      │    │    ├── _run_candle(row)
      │    │    │    ├── cache.get()
      │    │    │    ├── HistoricalNewsLoader.get()
      │    │    │    ├── build_market_state()
      │    │    │    ├── ReactOrchestrator.run()  <-- วิ่งเข้า Core Logic ของจริง
      │    │    │    └── cache.set()
      │    │    │
      │    │    └── _apply_to_portfolio(result)
      │    │         └── SimPortfolio.execute_buy() / execute_sell()
      │    │
      │    └── _add_validation()
      │
      ├── 3. bt.calculate_metrics()
      │
      └── 4. bt.export_csv()
```

---

## 6. Input / Output per Phase

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
│               trend:     {ema_20, ema_50, trend, golden_cross, death_cross},
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
| **Output** | `market_state: dict` |

```python
market_state = {
  "meta": { "agent": "gold-trading-agent", "version": "1.1.0", ... },
  "data_quality": { "quality_score": "good|degraded", "is_weekend": bool,
                    "llm_instruction": str, "warnings": [...] },
  "market_data": {
    "spot_price_usd": { "price_usd_per_oz": 3115.50, "confidence": 0.97 },
    "forex":          { "USDTHB": 33.50 },
    "thai_gold_thb":  { "sell_price_thb": 169000, "buy_price_thb": 168900 },
    "recent_price_action": [ {open,high,low,close,volume} × 5 candles ]
  },
  "technical_indicators": {
    "rsi":       { "value": 58.5, "period": 14, "signal": "neutral" },
    "macd":      { "macd_line": 26.15, "signal_line": 17.80, "histogram": 8.35 },
    "trend":     { "ema_20": 168500, "ema_50": 167200, "trend": "uptrend" },
    "bollinger": { "upper": 170000, "lower": 166000, "mid": 168000 },
    "atr":       { "value": 800.0 }
  },
  "news": {
    "summary": { "total_articles": 15, "overall_sentiment": 0.23 },
    "by_category": { "gold_price": {...}, "geopolitics": {...}, ... }
  }
}
```

### Phase 2 — LLM Inference

| | |
|---|---|
| **Input** | `provider: str`, `market_state: dict`, `interval: str` |
| **Output** | `interval_result: dict` |
| **Token usage** | ~650 tokens/call (System ~300 + User ~200 + Response ~150) |

```python
interval_result = {
  "signal":      "BUY",
  "confidence":  0.85,
  "reasoning":   "EMA20 > EMA50, MACD bullish, news positive...",
  "entry_price": 169000.0,   # THB
  "stop_loss":   167400.0,   # THB
  "take_profit": 171200.0,   # THB
  "trace": [...]
}
```

### Phase 3 — Weighted Voting

| | |
|---|---|
| **Input** | `interval_results: dict[str, dict]` |
| **Output** | `voting_result: dict` |

```python
voting_result = {
  "final_signal":        "BUY",
  "weighted_confidence": 0.714,
  "voting_breakdown": {
    "BUY":  { "count": 2, "avg_conf": 0.875, "weighted_score": 0.601 },
    "SELL": { "count": 1, "avg_conf": 0.600, "weighted_score": 0.113 },
    "HOLD": { "count": 0, ... }
  },
  "interval_details": [
    { "interval": "1h", "signal": "BUY",  "confidence": 0.85, "weight": 0.22 },
    { "interval": "4h", "signal": "BUY",  "confidence": 0.90, "weight": 0.30 },
    { "interval": "1d", "signal": "SELL", "confidence": 0.60, "weight": 0.12 },
  ]
}
```

### Phase 4 — Persistence

| | |
|---|---|
| **Input** | `provider: str`, `voting_result: dict`, `market_state: dict` |
| **Output** | `run_id: int` |

### Phase 5 — UI Render

| | |
|---|---|
| **Input** | `voting_result`, `interval_results`, `market_state` |
| **Output** | 8 Gradio components (HTML + Textbox) |

---

## 7. Backtest Architecture

### 7.1 ทำไมต้องมี Backtest แยก?

Gemini API มี rate limit ที่ไม่รองรับการรัน React loop 1,500+ ครั้ง (เช่น backtest 1h × 90 วัน = 1,524 candles) จึงต้องใช้ **Ollama local server** รัน open-source model แทน

### 7.2 Production vs Backtest Mapping

| ส่วนประกอบ | Production (main.py) | Backtest (run_main_backtest.py) |
|---|---|---|
| LLM | Gemini / Groq / Claude | Ollama (Qwen2.5 / Qwen3) |
| ข้อมูลราคา | Live yfinance | Historical CSV (thai_gold_1m_dataset.csv) |
| ข้อมูลข่าว | Live RSS + FinBERT | Pre-processed CSV (finnhub news) |
| Portfolio | PostgreSQL | SimPortfolio (in-memory dataclass) |
| Cache | ไม่มี | JSON per candle (resume หลัง crash ได้) |

### 7.3 Backtest Flow

```
run_main_backtest.py
  │
  ├── MainPipelineBacktest.__init__()
  │     ├── OllamaClient(model="qwen3:8b")
  │     ├── CandleCache(cache_dir)          ← JSON cache per candle
  │     ├── HistoricalNewsLoader(news_csv)   ← nearest-match window 4h
  │     └── SimPortfolio()                  ← stateful portfolio
  │
  ├── load_and_aggregate()
  │     ├── pd.read_csv(gold_csv)
  │     ├── resample(freq)                  ← "1h", "4h", "1d"
  │     └── _ensure_indicators()            ← คำนวณ RSI/MACD/EMA ถ้าไม่มีใน CSV
  │
  └── run()  [per candle loop]
        ├── CandleCache.get(ts)             ← ถ้า hit → skip LLM call
        ├── HistoricalNewsLoader.get(ts)    ← nearest news ภายใน 4h window
        ├── build_market_state(row, portfolio, news, interval)
        ├── ReactOrchestrator.run(market_state)   ← SAME as production
        ├── _apply_to_portfolio(result)     ← SimPortfolio.execute_buy/sell
        └── CandleCache.set(ts, result)     ← save for resume
```

### 7.4 SimPortfolio Logic

```python
# BUY
total_cost = position_thb + SPREAD_THB(30) + COMMISSION_THB(3)
grams = (position_thb / price_thb_per_baht) × 15.244
cash_balance -= total_cost

# SELL (close entire position)
proceeds = (gold_grams / 15.244) × price_thb_per_baht
net_proceeds = proceeds - SPREAD_THB - COMMISSION_THB
cash_balance += net_proceeds
```

---

## 8. Results & Performance

### 8.1 Backtest Configuration

| Parameter | Value |
|---|---|
| Timeframe | 1-hour candles |
| Period | 90 days (ธ.ค. 2025 – มี.ค. 2026) |
| Total candles | ~1,524 |
| Initial capital | ฿1,500 |
| Spread | ฿30 / trade |
| Commission | ฿3 / trade |

### 8.2 Model Comparison

| Model | Dir. Accuracy | Sensitivity | Total Signals | BUY | SELL | Avg Net PnL (THB) | Avg Confidence |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **qwen2.5:7b** | 54.94% | 10.64% | 162 | 53 | 109 | **-39.72** | 0.791 |
| **qwen2.5:14b** | 42.11% | 1.25% | 19 | 19 | 0 | **+162.80** | 0.789 |
| **qwen3:8b** | 50.00% | 5.91% | 90 | 77 | 13 | **+139.71** | 0.622 |

### 8.3 Key Observations

**qwen2.5:7b**
- Aggressive trader — signal ทุก 10 candles
- SELL bias สูง (109 SELL vs 53 BUY) → อาจ overfit ต่อ downtrend ใน dataset
- Avg PnL ติดลบ = overtrading ทำให้ spread+commission กิน profit

**qwen2.5:14b**
- Conservative มาก — signal แค่ 1.25% ของ candles ทั้งหมด
- ไม่เคย SELL เลย → อาจ bias หรือ prompt ไม่ trigger SELL ได้
- เมื่อ signal → กำไรเฉลี่ยดีที่สุด (+162.80 THB) แต่ sample เล็กมาก (n=19)

**qwen3:8b**
- Middle ground ที่สมดุลที่สุด
- Dir. accuracy 50% (random chance baseline) แต่ PnL บวก → timing ดีกว่า random
- RiskManager reject 1 signal → validation ทำงาน

### 8.4 Forward-Looking Metrics (To Be Computed)

เมื่อรัน equity curve simulation เต็มรูปแบบ จะคำนวณ:

```
Sharpe Ratio  = (portfolio_daily_return_mean - 0) / daily_std × √252
Sortino Ratio = portfolio_daily_return_mean / downside_std × √252
MDD           = max((peak_equity - trough_equity) / peak_equity) × 100%
```

> เป้าหมาย: Sharpe > 1.0, MDD < 20% สำหรับพอร์ต ฿1,500

---

## 9. Core Components

### 9.1 ReactOrchestrator (react.py)

```
ReAct Loop:
  THOUGHT → [CALL_TOOL | FINAL_DECISION]
     ↓              ↓
  OBSERVATION    return

Fast Path (max_tool_calls=0):
  prompt → llm.call() → extract_json() → RiskManager.evaluate() → return
  [1 LLM call ต่อ candle, ไม่มี tool loop]
```

### 9.2 PromptBuilder (prompt.py)

สร้าง `PromptPackage` 2 แบบ:

| Method | ใช้เมื่อ | Token (approx) |
|--------|---------|----------------|
| `build_thought()` | iteration 1..N | ~500 |
| `build_final_decision()` | forced final / fast path | ~450 |

### 9.3 RiskManager (risk.py)

ด่านกรอง 4 ชั้นก่อน execute:

```
1. Confidence check    → ต้อง > 0.70 (min_confidence)
2. Signal validation   → SELL ต้องมีทองในพอร์ต, BUY ต้องมีเงิน ≥ ฿1,000
3. Position sizing     → cash < ฿2,000: all-in | cash ≥ ฿2,000: 50% × confidence
4. SL/TP calculation   → SL = price - ATR×2.0 | TP = price + ATR×3.0
```

### 9.4 LLMClientFactory (client.py)

Registry pattern รองรับ 7 providers:

```python
_REGISTRY = {
  "gemini":   GeminiClient,     # Production default
  "groq":     GroqClient,       # Fast inference
  "claude":   ClaudeClient,
  "openai":   OpenAIClient,
  "deepseek": DeepSeekClient,
  "ollama":   OllamaClient,     # Backtest default (local)
  "mock":     MockClient,       # Testing
}
```

### 9.5 Interval Weights

```python
INTERVAL_WEIGHTS = {
  "1m":  0.03,   # Scalping (very noisy)
  "5m":  0.05,
  "15m": 0.10,
  "30m": 0.15,
  "1h":  0.22,   # Sweet spot
  "4h":  0.30,   # Strongest signal
  "1d":  0.12,   # Trend confirmation
  "1w":  0.03,
}  # sum = 1.0 (validated at import)
```

### 9.6 AnalysisService Retry Logic

```python
for attempt in range(1, max_retries + 1):  # default = 3
    try:
        ...
        return {"status": "success"}
    except ValueError:
        return {"status": "error", "error_type": "validation"}  # ไม่ retry
    except Exception:
        time.sleep(retry_delay ** attempt)  # 2s, 4s exponential backoff
```

---

## 10. Trading Constraints

### 10.1 Hard Constraints (enforced in System Prompt + RiskManager)

| Rule | Logic | ผล |
|------|-------|-----|
| Minimum Buy | `cash < ฿1,000` → `can_buy = NO` | LLM / RiskManager ห้าม BUY |
| No Short Selling | `gold_grams == 0` → `can_sell = NO` | LLM / RiskManager ห้าม SELL |
| Capital Preservation | `risk > 50%` ต่อ trade | RiskManager ปรับ position size |
| Min Confidence | `confidence ≤ 0.70` | RiskManager reject → HOLD |
| Platform Unit | Entry/SL/TP ต้องเป็น **THB** ไม่ใช่ USD | ระบุใน system prompt |

### 10.2 Soft Constraints (LLM Reasoning)

- RSI > 70 = overbought → หลีกเลี่ยง BUY
- RSI < 30 = oversold → หลีกเลี่ยง SELL
- MACD histogram ขยาย = momentum แรง → เพิ่ม confidence
- EMA20 > EMA50 = uptrend → prefer BUY
- `data_quality = "degraded"` → ลด weight technical, เพิ่ม weight news

---

## 11. Database Schema

```sql
-- Run history
CREATE TABLE runs (
    id               SERIAL PRIMARY KEY,
    run_at           TEXT    NOT NULL,        -- UTC ISO timestamp
    provider         TEXT    NOT NULL,        -- "gemini", "groq", "ollama", ...
    interval_tf      TEXT,                    -- "1h,4h,1d" (comma-separated)
    period           TEXT,                    -- "1mo", "3mo"
    signal           TEXT,                    -- "BUY" | "SELL" | "HOLD"
    confidence       REAL,                    -- 0.0 – 1.0
    entry_price      REAL,                    -- USD/oz (nullable)
    stop_loss        REAL,                    -- USD/oz (nullable)
    take_profit      REAL,                    -- USD/oz (nullable)
    entry_price_thb  REAL,                    -- THB (calculated)
    stop_loss_thb    REAL,
    take_profit_thb  REAL,
    usd_thb_rate     REAL,
    rationale        TEXT,
    iterations_used  INTEGER,
    tool_calls_used  INTEGER,
    gold_price       REAL,                    -- USD/oz at run time
    gold_price_thb   REAL,
    rsi              REAL,
    macd_line        REAL,
    signal_line      REAL,
    trend            TEXT,
    react_trace      TEXT,                    -- JSON array (stringified)
    market_snapshot  TEXT                     -- full market_state (stringified)
);

-- Portfolio snapshot (1 row เสมอ, id=1 — UPSERT)
CREATE TABLE portfolio (
    id                SERIAL PRIMARY KEY,
    cash_balance      REAL    NOT NULL DEFAULT 1500.0,
    gold_grams        REAL    NOT NULL DEFAULT 0.0,
    cost_basis_thb    REAL    NOT NULL DEFAULT 0.0,
    current_value_thb REAL    NOT NULL DEFAULT 0.0,
    unrealized_pnl    REAL    NOT NULL DEFAULT 0.0,
    trades_today      INTEGER NOT NULL DEFAULT 0,
    updated_at        TEXT    NOT NULL
);
```

**Recommended Indexes**

```sql
CREATE INDEX idx_runs_provider ON runs(provider);
CREATE INDEX idx_runs_signal   ON runs(signal);
CREATE INDEX idx_runs_run_at   ON runs(run_at DESC);
```

---

## 12. Environment Setup

### 12.1 Prerequisites

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.9+ | Tested on 3.11 |
| OS | macOS / Windows | macOS ใช้ path `/Users/<name>/...` |
| RAM | ≥ 16 GB | สำหรับ qwen3:8b ใช้ ~9 GB, qwen2.5:14b ใช้ ~12 GB |
| PostgreSQL | 12+ | local หรือ cloud (Render) |
| Ollama | latest | สำหรับ backtest เท่านั้น |

### 12.2 Clone & Virtual Environment

```bash
cd Src/

python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# หรือ
venv\Scripts\activate             # Windows

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# ติดตั้ง Playwright browser (สำหรับ Thai gold price)
playwright install chromium
```

### 12.3 Environment Variables (.env)

```bash
# ── LLM API Keys (ต้องมีอย่างน้อย 1 ตัว) ──────────────
GEMINI_API_KEY="your-gemini-api-key"
GROQ_API_KEY="your-groq-api-key"
OPENAI_API_KEY="your-openai-api-key"
ANTHROPIC_API_KEY="your-anthropic-api-key"

# ── Market Data ────────────────────────────────────────────
TWELVEDATA_API_KEY="your-twelvedata-api-key"   # ← ใหม่ v3.3 (optional แต่แนะนำ)
# ถ้าไม่มี TWELVEDATA_API_KEY จะ fallback ไปใช้ yfinance อย่างเดียว

# ── Sentiment Analysis (FinBERT) ───────────────────────────
HF_TOKEN="your-huggingface-token"

# ── Database ────────────────────────────────────────────
DATABASE_URL="postgresql://user:pass@localhost:5432/goldtrader"

# ── Optional ────────────────────────────────────────────
LOG_LEVEL="INFO"     # DEBUG | INFO | WARNING | ERROR
PORT=10000           # Gradio dashboard port

# ── Ollama (Backtest) ───────────────────────────────────
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3:8b"
```

### 12.4 Ollama Setup (Backtest Only)

```bash
# Install Ollama: https://ollama.com/download

# Start server
ollama serve

# Pull model (ต้องเลือกตาม RAM)
ollama pull qwen3:8b        # ~9 GB RAM
ollama pull qwen2.5:7b      # ~5 GB RAM
ollama pull qwen2.5:14b     # ~12 GB RAM
```

### 12.5 Database Initialization

```bash
psql -U postgres -c "CREATE DATABASE goldtrader;"
# Tables สร้างอัตโนมัติตอน RunDatabase.__init__() ถูกเรียก
```

---

## 13. How to Run

### 13.1 Dashboard Mode (แนะนำ)

```bash
cd Src/
source venv/bin/activate
python ui/dashboard.py
```

เปิด browser: **http://localhost:10000**

**Tab 1: 📊 Live Analysis**
1. เลือก Provider (Gemini / Groq / Ollama / Mock)
2. เลือก Period (1d, 5d, 1mo, 3mo, ...)
3. เลือก Intervals (checkbox หลายตัวพร้อมกัน)
4. กด **▶ Run Analysis**
5. ดูผล: Weighted Voting Summary + Per-interval + ReAct Trace

**Tab 2: 📜 Run History** — ตาราง 50 runs ล่าสุด

**Tab 3: 💼 Portfolio** — กรอกข้อมูลจาก ออม NOW → Save

### 13.2 CLI Mode (Production)

```bash
cd Src/
source venv/bin/activate

python main.py --provider gemini
python main.py --provider groq --iterations 7
python main.py --provider gemini --skip-fetch   # ใช้ data cache
python main.py --provider mock                  # ทดสอบ ไม่เรียก API
```

### 13.3 Backtest Mode

```bash
cd Src/
source venv/bin/activate

# Basic: 1h candles, 90 วัน, qwen3:8b
python run_main_backtest.py \
  --gold-csv backtest/data_XAU_THB/thai_gold_1m_dataset.csv \
  --news-csv backtest/data_XAU_THB/finnhub_3month_news_ready_v2.csv \
  --timeframe 1h \
  --days 90 \
  --model qwen3:8b

# Resume หลัง crash (ใช้ cache)
python run_main_backtest.py --model qwen3:8b --cache-dir backtest_cache_main
```

### 13.4 Monitoring Logs

```bash
tail -f logs/system.log       # Events ทั่วไป
tail -f logs/llm_trace.log    # Prompt + Response ทุก call
grep "ERROR" logs/system.log
grep "BUY" logs/system.log | wc -l
```

---

## 14. Extensibility

### 14.1 เพิ่ม LLM Provider ใหม่

```python
class MyLLMClient(LLMClient):
    def call(self, prompt_package: PromptPackage) -> str: ...
    def is_available(self) -> bool: ...

LLMClientFactory.register("myprovider", MyLLMClient)

# 3. เพิ่มใน core/config.py
PROVIDER_CHOICES.append(("my-model-name", "myprovider"))
```

### 14.2 เพิ่ม Technical Indicator ใหม่

```python
# ใน data_engine/indicators.py
def calculate_roc(self) -> dict:
    roc = self.df['close'].pct_change(periods=12) * 100
    return {"value": roc.iloc[-1], "signal": "positive" if roc.iloc[-1] > 0 else "negative"}

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

### 14.4 เพิ่ม News Category ใหม่

```python
# ใน data_engine/newsfetcher.py
NEWS_CATEGORIES["crypto"] = {
    "label": "Crypto Market",
    "impact": "medium",
    "keywords": ["bitcoin", "crypto", "digital asset"],
    "rss_urls": [...]
}
```

---

## 15. Risks, Challenges & Mitigation

### 15.1 Data Quality Risks

| ความเสี่ยง | ผลกระทบ | Mitigation |
|-----------|---------|-----------|
| **Price mismatch** — ราคาใน ออม NOW ต่างจาก dataset (yfinance GC=F) เพราะแต่ละแหล่งใช้ราคา reference ต่างกัน | Backtest PnL ไม่ตรงกับการเทรดจริง | ใช้ intergold.co.th scraping เป็น primary, คำนวณ slippage factor |
| **Look-ahead bias** — rolling indicators คำนวณจากข้อมูลที่ยัง "ไม่เกิดขึ้น" ใน candle นั้น | Backtest accuracy สูงเกินจริง | ใช้ `.shift(1)` ก่อน label หรือ forward-fill อย่างระมัดระวัง |
| **News timestamp mismatch** — news CSV กับ candle timestamp ไม่ sync | Signal ได้รับ news ผิดเวลา | ใช้ nearest-match window 4 ชั่วโมงก่อน candle close |
| **FinBERT API timeout** | `sentiment_score = 0.0` ทั้งหมด | Retry × 3, fallback เป็น neutral sentiment |

### 15.2 Model & AI Risks

| ความเสี่ยง | ผลกระทบ | Mitigation |
|-----------|---------|-----------|
| **JSON parse failure** — LLM ส่ง markdown fence, `<think>` block, หรือ plain text | System crash / HOLD fallback | `_strip_think()`, `_extract_json_block()`, `extract_json()` fallback |
| **Qwen vs Gemini behavior gap** — model ต่างกัน → signal pattern ต่างกัน | Backtest ไม่ตรงกับ production จริง | ระบุใน doc ว่าเป็น known limitation, ใช้ mock test cross-validate |
| **Confidence calibration** — model อาจ output confidence สูงเกินจริง | RiskManager ผ่านสัญญาณที่ไม่ดี | Calibrate threshold จาก backtest หลายรอบ |
| **HOLD bias** — Qwen2.5:14b ไม่เคย SELL เลย | Missed profit / one-sided exposure | ตรวจ signal distribution ก่อน production |

### 15.3 Resource Risks

| ความเสี่ยง | ผลกระทบ | Mitigation |
|-----------|---------|-----------|
| **RAM limitation** — qwen2.5:14b ต้องการ ~12 GB, qwen3:8b ~9 GB | เครื่องบางเครื่องรันไม่ได้ | fallback ไปใช้ qwen2.5:7b (5 GB) หรือ Gemini API |
| **Backtest time** — 1,500 candles × 30-60s/call = 12-25 ชั่วโมง | ไม่ทันเวลา | `CandleCache` resume ได้, batch ด้วย `--days 30` ก่อน |
| **Gemini rate limit** — free tier จำกัด requests/min | Production analysis ล้มเหลว | Retry + backoff, fallback ไป Groq |

### 15.4 Portfolio & Execution Risks

| ความเสี่ยง | ผลกระทบ | Mitigation |
|-----------|---------|-----------|
| **Portfolio state drift** — `SimPortfolio` กับ PostgreSQL อาจ desync ถ้า crash ระหว่างทาง | Backtest portfolio ไม่ตรงกับ production | Manual sync ผ่าน Tab Portfolio ใน Dashboard |
| **Minimum trade constraint** — ฿1,500 ทุน, ซื้อขั้นต่ำ ฿1,000 = margin เล็กมาก | 1 trade ผิดพลาด = หมดเงิน 67% | Hard limit ใน RiskManager: max 50% ต่อ trade |
| **Spread erosion** — ฿30 spread + ฿3 commission ต่อ trade | Overtrading ทำลาย portfolio | Signal sensitivity check: Sensitivity > 10% → flag as overtrading |

### 15.5 Summary Risk Matrix

```
            Low Impact          High Impact
High Prob  | API timeout       | Price mismatch    |
           | JSON parse fail   | RAM limitation    |
           |-------------------|-------------------|
Low Prob   | Confidence bias   | Look-ahead bias   |
           | HOLD bias         | Portfolio drift   |
```

---

*Documentation maintained by: PM Team*  
*Version: 3.2 | Updated: 2026-03-30*
