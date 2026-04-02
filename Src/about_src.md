# GoldTrader — Complete Agent Architecture Documentation v3.3

---

## 1. Overview & Goal

**GoldTrader** คือ production-grade **ReAct + LLM trading agent** สำหรับวิเคราะห์และตัดสินใจเทรดทองคำบนแพลตฟอร์ม **ออม NOW** (Hua Seng Heng)

### 1.1 Mission

ผสมผสาน multi-step AI reasoning เข้ากับ real-time technical indicators และ news sentiment เพื่อ generate สัญญาณ **BUY / SELL / HOLD** ที่มีความน่าเชื่อถือสูง

### 1.2 Why LLM for Gold Trading?

อัลกอริทึมธรรมดา (Rule-based) สามารถอ่าน RSI หรือ MACD ได้ แต่ไม่สามารถ **"อ่านบริบท"** ได้ เช่น geopolitical risk, sentiment จากข่าว หรือ pattern ที่ต้องใช้การ reasoning หลายขั้นตอน

### 1.3 Core Components Summary

| Layer | ไฟล์หลัก | หน้าที่ |
|-------|----------|---------|
| **Agent Core** | `agent_core/core/react.py` | ReAct loop — Thought → Action → Observation |
| **Prompt** | `agent_core/core/prompt.py` | PromptBuilder, SkillRegistry, RoleRegistry |
| **Risk** | `agent_core/core/risk.py` | RiskManager — validate + size position |
| **LLM Client** | `agent_core/llm/client.py` | Factory + 8 providers (Gemini, Groq, Claude, ...) |
| **Data Engine** | `data_engine/` | OHLCV, indicators, news, Thai gold price |
| **Services** | `ui/core/services.py` | AnalysisService, PortfolioService, HistoryService |
| **UI** | `ui/dashboard.py` + `ui/navbar/` | Gradio 5-tab dashboard |
| **Database** | `database/database.py` | PostgreSQL — runs, portfolio, llm_logs |
| **Backtest** | `backtest/` | Ollama local + SimPortfolio |
| **Notification** | `notification/discord_notifier.py` | Discord webhook alert |

### 1.4 Changelog v3.3 — Data Engine Hardening

| ด้าน | v3.2 (เดิม) | v3.3 (ใหม่) |
|------|------------|------------|
| **ราคาทอง Spot** | yfinance เดียว | Multi-source: TwelveData + gold-api + yfinance + confidence score |
| **ราคาทองไทย** | คำนวณสูตร fallback | Playwright WebSocket scrape intergold.co.th → fallback สูตร |
| **OHLCV** | fetch ใหม่ทุกครั้ง | TwelveData → yfinance fallback + CSV cache + smart incremental fetch |
| **ATR Signal** | Fixed threshold | Dynamic threshold เทียบ avg 50 แท่ง |
| **News Sentiment** | Simple average | Weighted avg ตาม impact (direct/high/medium) |
| **LLM Logs** | ไม่มี | บันทึก prompt/response/token ลง `llm_logs` table ทุก call |
| **Discord Notify** | ไม่มี | ส่ง embed ก่อน DB save ทุก run |
| **Provider Fallback** | ไม่มี | FallbackChainClient — เปลี่ยน provider อัตโนมัติ |

---

## 2. Project Structure

```
Src/
│
├── about_src.md                        # เอกสารนี้
│
├── agent_core/                         # 🧠 ส่วนมันสมองของ AI
│   ├── config/
│   │   ├── roles.json                  # Role definitions (analyst, risk_manager)
│   │   └── skills.json                 # Skill + tool registry
│   ├── core/
│   │   ├── prompt.py                   # PromptBuilder, SkillRegistry, RoleRegistry, AIRole
│   │   ├── react.py                    # ReactOrchestrator — ReAct loop หลัก
│   │   └── risk.py                     # RiskManager — validate + SL/TP + position sizing
│   └── llm/
│       └── client.py                   # LLMClientFactory + 8 providers
│
├── backtest/                           # 🔬 ทดสอบย้อนหลัง
│   ├── backtest_main_pipeline.py       # MainPipelineBacktest class + SimPortfolio
│   └── run_main_backtest.py            # Entry point — CLI runner
│
├── data_engine/                        # 📡 เชื่อมต่อข้อมูลภายนอก
│   ├── interceptor/
│   │   └── fetcher.py                  # GoldDataFetcher (spot price + forex + Thai gold)
│   ├── indicators.py                   # TechnicalIndicators (RSI, MACD, BB, ATR, EMA)
│   ├── newsfetcher.py                  # GoldNewsFetcher + FinBERT sentiment
│   ├── ohlcv_fetcher.py                # OHLCVFetcher — TwelveData / yfinance / CSV cache
│   ├── orchestrator.py                 # GoldTradingOrchestrator — รวมทุกแหล่งข้อมูล
│   └── thailand_timestamp.py           # UTC → Bangkok timezone helper
│
├── cache/                              # 💾 CSV cache สำหรับ OHLCV
│   └── ohlcv_XAU_USD_{interval}.csv
│
├── database/
│   └── database.py                     # RunDatabase — PostgreSQL (runs, portfolio, llm_logs)
│
├── logs/
│   └── logger_setup.py                 # sys_logger, llm_logger, log_method decorator
│
├── notification/
│   └── discord_notifier.py             # DiscordNotifier — webhook embed builder + sender
│
├── ui/                                 # 🖥 Frontend / Dashboard
│   ├── dashboard.py                    # Gradio entry point — init + launch
│   ├── core/
│   │   ├── config.py                   # PROVIDER_CHOICES, INTERVAL_WEIGHTS, PERIOD_CHOICES, ...
│   │   ├── services.py                 # AnalysisService, PortfolioService, HistoryService
│   │   ├── utils.py                    # calculate_weighted_vote(), format helpers
│   │   ├── renderers.py                # TraceRenderer, HistoryRenderer, PortfolioRenderer, ...
│   │   ├── chart_renderer.py           # ChartTabRenderer — TradingView widget + price card
│   │   ├── chart_service.py            # ChartService — goldapi.io fetcher
│   │   └── dashboard_css.py            # DASHBOARD_CSS — design tokens + component overrides
│   └── navbar/
│       ├── __init__.py                 # Export NavbarBuilder, AppContext
│       ├── base.py                     # PageBase, PageComponents, @navbar_page decorator
│       ├── homepage.py                 # 🏠 Home tab — KPI cards + overview
│       ├── analysis_page.py            # 📊 Live Analysis tab — run + trace + LLM logs
│       ├── chart_page.py               # 📈 Live Chart tab — TradingView + price card
│       ├── history_page.py             # 📜 Run History tab — table + run detail + LLM logs
│       └── portfolio_page.py           # 💼 Portfolio tab — form + summary
│
├── main.py                             # 🖥 CLI Entry point
└── requirements.txt
```

---

## 3. Architecture Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      UI Layer                                           │
│   ui/dashboard.py  +  ui/navbar/*.py  (Gradio Blocks + Tab pages)      │
│   ❌ No business logic   ❌ No direct DB calls   ❌ No LLM calls         │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ calls
┌──────────────────────────────▼──────────────────────────────────────────┐
│                   Services Layer  (ui/core/services.py)                  │
│                                                                         │
│   AnalysisService              PortfolioService      HistoryService     │
│   run_analysis()               save_portfolio()      get_recent_runs()  │
│   _run_single_interval()       load_portfolio()      get_statistics()   │
│   _validate_inputs()                                 get_run_detail()   │
│                                                      get_llm_logs()     │
│                                                                         │
│   Config: ui/core/config.py                                             │
│   Utils:  ui/core/utils.py    (calculate_weighted_vote)                 │
│   Render: ui/core/renderers.py                                          │
└──────────┬────────────────────┬────────────────────┬───────────────────┘
           │                    │                    │
  ┌────────▼─────────┐  ┌───────▼────────┐  ┌───────▼──────────┐
  │   Data Engine    │  │   Agent Core   │  │    Database      │
  │                  │  │                │  │                  │
  │ GoldTradingOrch. │  │ ReactOrchest.  │  │ RunDatabase      │
  │ GoldDataFetcher  │  │ PromptBuilder  │  │ PostgreSQL       │
  │ OHLCVFetcher     │  │ LLMClientFact. │  │ tables:          │
  │ TechIndicators   │  │ FallbackChain  │  │  runs            │
  │ GoldNewsFetcher  │  │ RiskManager    │  │  portfolio       │
  └──────────────────┘  └───────┬────────┘  │  llm_logs        │
                                │           └──────────────────┘
                        ┌───────▼────────┐
                        │  Notification  │
                        │ DiscordNotifier│
                        └────────────────┘
```

### Dependency Injection Map

```
ui/dashboard.py
  └── init_services(skill_registry, role_registry, orchestrator, db)
        ├── AnalysisService(skill_registry, role_registry, orchestrator, db, notifier)
        ├── PortfolioService(db)
        ├── HistoryService(db)
        └── DiscordNotifier()  ← singleton

GoldTradingOrchestrator
  ├── GoldDataFetcher
  │     └── OHLCVFetcher(session=shared requests.Session)
  ├── TechnicalIndicators(ohlcv_df)
  └── GoldNewsFetcher()

AnalysisService._run_single_interval()
  └── FallbackChainClient([(p1, client1), (p2, client2), ...])
        └── ReactOrchestrator(llm_client, prompt_builder, tool_registry, config)
              └── RiskManager(atr_multiplier, rr_ratio, min_confidence)
```

---

## 4. Configuration Reference (ui/core/config.py)

### Provider Choices & Fallback Chain

```python
PROVIDER_CHOICES = [
    ("Gemini 3.1 Flash Lite",           "gemini"),
    ("Groq llama 3.3 70b versatile",    "groq"),
    ("Mock",                             "mock"),
]

PROVIDER_FALLBACK_CHAIN = {
    "gemini":   ["gemini", "groq", "mock"],
    "groq":     ["groq", "gemini", "mock"],
    "claude":   ["claude", "gemini", "mock"],
    "ollama":   ["ollama", "gemini", "mock"],
    # openrouter_xxx → ["gemini", "openrouter_xxx", "groq", "mock"]
}
```

### Interval Weights (Weighted Voting)

```python
INTERVAL_WEIGHTS = {
    "1m":  0.03,   # Scalping — very noisy
    "5m":  0.05,
    "15m": 0.10,
    "30m": 0.15,
    "1h":  0.22,   # ★ Sweet spot
    "4h":  0.30,   # ★ Strongest signal
    "1d":  0.12,   # Trend confirmation
    "1w":  0.03,
}  # sum = 1.0 (validated at import)
```

---

## 5. Main Flow Diagrams

### 5.1 Web Dashboard Flow (Overview)

```
Browser: กด ▶ Run Analysis
  │
  ▼
[ui/navbar/analysis_page.py]  handle_run_analysis(provider, period, interval)
  │
  ├── PHASE 1: Data Collection ──────────────────────────────────────────────
  │     GoldTradingOrchestrator.run(history_days, interval)
  │       → market_state: dict
  │
  ├── PHASE 2: LLM Analysis Loop (per interval) ─────────────────────────────
  │     for interval in [intervals]:
  │       AnalysisService._run_single_interval(provider, market_state, interval)
  │         → interval_result: dict (signal, confidence, trace, tokens, ...)
  │
  ├── PHASE 3: Weighted Voting ────────────────────────────────────────────────
  │     calculate_weighted_vote(interval_results)
  │       → voting_result: { final_signal, weighted_confidence, voting_breakdown }
  │
  ├── PHASE 4: Notification ──────────────────────────────────────────────────
  │     DiscordNotifier.notify(voting_result, interval_results, market_state)
  │
  ├── PHASE 5: Persistence ───────────────────────────────────────────────────
  │     RunDatabase.save_run(provider, voting_result, market_state)   → run_id
  │     RunDatabase.save_llm_logs_batch(run_id, llm_logs_pending)     → [log_ids]
  │
  └── PHASE 6: Render UI ─────────────────────────────────────────────────────
        TraceRenderer.format_trace_html(trace)
        HistoryRenderer.format_history_html(rows)
        StatsRenderer.format_stats_html(stats)
        → return 9 Gradio output components
```

### 5.2 Backtest Flow (Overview)

```
CLI: python backtest/run_main_backtest.py --model qwen3:8b --timeframe 1h
  │
  ▼
MainPipelineBacktest.__init__()
  │
  ├── OllamaClient(model="qwen3:8b")
  ├── CandleCache(cache_dir)        ← JSON per candle (resume ได้)
  ├── HistoricalNewsLoader(csv)     ← nearest-match window 4h
  └── SimPortfolio()
  │
  ▼
bt.run()
  ├── load_and_aggregate(csv)       ← resample + ensure indicators
  └── for row in candles:
        ├── CandleCache.get(ts)     → HIT: skip LLM
        ├── build_market_state(row, portfolio, news, interval)
        ├── ReactOrchestrator.run(market_state)   ← SAME as production
        ├── _apply_to_portfolio(result)            ← SimPortfolio
        └── CandleCache.set(ts, result)
  │
  ▼
bt.calculate_metrics()  →  Sharpe, Sortino, MDD, Win Rate, Profit Factor
bt.export_csv()
```

---

## 6. Phase Detail: Data Collection (Phase 1)

```
GoldTradingOrchestrator.run(history_days=N, interval=X, save_to_file=True)
│
├── Step 1.1 — Spot Price (Multi-Source)
│   GoldDataFetcher.fetch_gold_spot_usd()
│   │
│   ├── ① TwelveData  → GET https://api.twelvedata.com/price?symbol=XAU/USD
│   ├── ② gold-api    → GET https://api.gold-api.com/price/XAU
│   └── ③ yfinance    → yf.Ticker("GC=F").history(period="1d")
│   │
│   ├── compute_confidence(prices):
│   │     max_diff = max deviation จาก median ของทั้ง 3 แหล่ง
│   │     confidence = max(0.0, 1.0 - max_diff × 10)
│   │
│   ├── Priority selection:
│   │     1. กรอง source ที่ราคาห่าง median > 0.5% ออก
│   │     2. TwelveData → gold-api → yfinance
│   │     3. Extreme case → บังคับ yfinance, confidence = 0.0
│   │
│   └── Output: { source, price_usd_per_oz, timestamp, confidence }
│
├── Step 1.2 — Forex Rate
│   fetch_usd_thb_rate()
│   GET https://api.exchangerate-api.com/v4/latest/USD
│   Output: { source, usd_thb, timestamp }
│
├── Step 1.3 — Thai Gold Price (ออม NOW reference)
│   calc_thai_gold_price(price_usd_per_oz, usd_thb)
│   │
│   ├── Primary: Playwright WebSocket scrape intergold.co.th
│   │     browser.launch(headless=True) + stealth_sync
│   │     page.goto("https://www.intergold.co.th/curr-price/")
│   │     รอ WebSocket event "updateGoldRateData" (socket.io, timeout 20s)
│   │       → bidPrice96 + offerPrice96 (ราคาทอง 96.5%)
│   │       → price_thb_per_baht_weight = (bid + ask) / 2
│   │
│   └── Fallback (ถ้า Playwright พัง):
│         price_thb_per_gram    = price_usd_per_oz × usd_thb / 31.1034768
│         price_thb_per_baht    = price_thb_per_gram × 15.244 × 0.965
│         sell_price = round((price_thb_per_baht + 50) / 50) × 50
│         buy_price  = round((price_thb_per_baht - 50) / 50) × 50
│
│   Output: { source, price_thb_per_baht_weight, sell_price_thb,
│              buy_price_thb, spread_thb }
│
├── Step 1.4 — OHLCV (OHLCVFetcher)
│   OHLCVFetcher.fetch_historical_ohlcv(days, interval, use_cache=True)
│   │
│   ├── 1. Load CSV Cache
│   │     cache/ohlcv_XAU_USD_{interval}.csv → _ensure_utc_index() → cached_df
│   │
│   ├── 2. _calculate_fetch_days(cached_df, days, interval)
│   │     cache < 50 แถว  → fetch เต็ม days
│   │     cache เก่า      → fetch ส่วนที่ขาด (max 2 วัน)
│   │     cache ครบ       → fetch เต็ม (update)
│   │
│   ├── 3. Fetch Primary: TwelveData (ถ้ามี API key)
│   │     _estimate_candles(interval, fetch_days) → output_size
│   │     GET https://api.twelvedata.com/time_series
│   │       ?symbol=XAU/USD&interval={td_interval}&outputsize={N}&timezone=UTC
│   │
│   ├── 4. Fallback: yfinance
│   │     yf.Ticker("GC=F").history(period=f"{safe_days}d", interval=interval)
│   │     YF_MAX_DAYS = {1m:7, 5m:60, 15m:60, 30m:60, 1h:730, 4h:730}
│   │
│   ├── 5. Merge + Validate
│   │     _ensure_utc_index(df_api)
│   │     _validate_ohlcv():
│   │       to_numeric(errors="coerce") → ลบ NaN rows
│   │       filter: high >= low, ทุกราคา > 0
│   │     concat([cached_df, df_api]) → dedup (keep="last") → sort_index
│   │     cutoff = now - timedelta(days=days) → ตัดข้อมูลเก่าออก
│   │
│   └── 6. Save Cache + Return
│         df.to_csv(cache_file)
│         Output: pd.DataFrame (UTC index, columns: open/high/low/close/volume)
│
├── Step 1.5 — Technical Indicators
│   TechnicalIndicators(ohlcv_df).to_dict()
│   Input : pd.DataFrame (N candles)
│   │
│   ├── RSI(14)  → { value, period, signal: "oversold|neutral|overbought" }
│   ├── MACD     → { macd_line, signal_line, histogram, crossover }
│   ├── Bollinger Bands → { upper, middle, lower, bandwidth, pct_b, signal }
│   ├── ATR(14)  → { value, period, volatility_level, unit: "THB" }
│   └── Trend    → { ema_20, ema_50, trend, golden_cross, death_cross }
│   │
│   Output: { rsi, macd, bollinger, atr, trend, latest_close, calculated_at }
│
├── Step 1.6 — News Sentiment (Parallel)
│   GoldNewsFetcher.to_dict(max_per_category=5, token_budget=3000)
│   │
│   ├── ThreadPoolExecutor(max_workers=10)
│   │     └── fetch_category(cat_key) × 8 categories (parallel)
│   │           ├── _fetch_yfinance_raw(symbol)  → NewsArticle list
│   │           └── _fetch_rss(url, keywords)    → NewsArticle list
│   │
│   ├── Global dedup: ตัด URL ซ้ำข้าม category
│   ├── _apply_global_limit() — Greedy Packing by token_budget=3000
│   │
│   ├── score_sentiment_batch([titles]) — FinBERT via HuggingFace API
│   │     positive → +confidence
│   │     negative → -confidence
│   │     neutral  → 0.0
│   │
│   └── overall_sentiment (weighted avg ตาม impact):
│         direct=1.5, high=1.2, medium=1.0
│   │
│   Output: { total_articles, token_estimate, overall_sentiment,
│              by_category: { cat_key: { label, count, articles[] } } }
│
└── Step 1.7 — Assemble & Save
    payload = { meta, data_quality, market_data, technical_indicators, news }
    → save: agent_core/data/latest.json
    → save: agent_core/data/payload_{timestamp}.json
    Output: market_state dict
```

**market_state schema**

```python
market_state = {
  "meta":         { "agent": "gold-trading-agent", "version": "3.3", ... },
  "data_quality": { "quality_score": "good|degraded", "is_weekend": bool,
                    "llm_instruction": str, "warnings": [...] },
  "market_data": {
    "spot_price_usd": { "price_usd_per_oz": 3115.50, "confidence": 0.97, "source": "twelvedata" },
    "forex":          { "usd_thb": 33.50 },
    "thai_gold_thb":  { "sell_price_thb": 169000, "buy_price_thb": 168900, "source": "intergold" },
    "recent_price_action": [ {open, high, low, close, volume} × 5 candles ]
  },
  "technical_indicators": {
    "rsi":       { "value": 58.5, "period": 14, "signal": "neutral" },
    "macd":      { "macd_line": 26.15, "signal_line": 17.80, "histogram": 8.35 },
    "trend":     { "ema_20": 168500, "ema_50": 167200, "trend": "uptrend" },
    "bollinger": { "upper": 170000, "lower": 166000, "mid": 168000 },
    "atr":       { "value": 800.0, "unit": "THB" }
  },
  "news": {
    "summary":     { "total_articles": 15, "overall_sentiment": 0.23 },
    "by_category": { "gold_price": {...}, "geopolitics": {...}, ... }
  },
  "portfolio": { "cash_balance": 1500.0, "gold_grams": 0.0, ... }   # ← merge ก่อนส่ง LLM
}
```

---

## 7. Phase Detail: LLM Analysis Loop (Phase 2)

```
AnalysisService._run_single_interval(provider, market_state, interval)
│
├── 1. Build FallbackChainClient
│   from PROVIDER_FALLBACK_CHAIN.get(provider) → fallback_order
│   for p in fallback_order:
│     LLMClientFactory.create(p) → client
│   FallbackChainClient(chain_clients)
│     ├── ลอง provider แรกก่อน
│     ├── LLMProviderError → skip → ลอง provider ถัดไป
│     └── ทุกตัว fail → raise LLMProviderError
│
├── 2. Build PromptBuilder + ReactConfig
│   PromptBuilder(role_registry, AIRole.ANALYST)
│   ReactConfig(max_iterations=3, max_tool_calls=0)
│   ReactOrchestrator(llm_client, prompt_builder, tool_registry={}, config)
│
└── 3. ReactOrchestrator.run(market_state)
      │
      ├── Fast Path (max_tool_calls=0) ─────────────────────────────────────
      │     prompt   = PromptBuilder.build_final_decision(market_state, [])
      │     llm_resp = llm.call(prompt)          ← 1 LLM call เท่านั้น
      │     parsed   = extract_json(llm_resp.text)
      │     decision = _build_decision(parsed)
      │     adjusted = RiskManager.evaluate(decision, market_state)
      │     return { final_decision, react_trace, token_*, prompt_text, ... }
      │
      └── Full ReAct Loop (max_tool_calls > 0) ──────────────────────────────
            while iteration < max_iterations:
              iteration += 1
              │
              ├── THOUGHT ──────────────────────────────────────────────────
              │     prompt   = build_thought(market_state, tool_results, iter)
              │     llm_resp = llm.call(prompt)
              │     thought  = extract_json(llm_resp.text)
              │     → append to react_trace
              │
              ├── ACTION: FINAL_DECISION ────────────────────────────────────
              │     break → adjusted by RiskManager
              │
              ├── ACTION: CALL_TOOL ─────────────────────────────────────────
              │     tool_count >= max_tool_calls → force final decision
              │     else: _execute_tool(tool_name, tool_args)
              │           → ToolResult → append observation to trace
              │
              └── UNKNOWN ACTION → fallback HOLD, break
```

### LLM Prompt Structure

```
PromptBuilder.build_final_decision(market_state, tool_results)

System prompt (from roles.json — analyst):
  /no_think
  You are a professional Gold Market Analyst for ออม NOW platform.
  STRATEGY RULES: CURRENCY=THB, Min BUY=1,000฿, No shorting, ...
  OUTPUT FORMAT: single JSON { action, signal, confidence, entry_price_thb, ... }

User message:
  ## MARKET STATE
    Gold (USD): $3115.50/oz | USD/THB: 33.50
    Gold (THB/gram): ฿169,000 sell / ฿168,900 buy
    RSI(14): 58.5 [neutral]
    MACD: 26.15/17.80 hist:8.35
    Trend: EMA20=168500 EMA50=167200 [uptrend]
    News Highlights: [ top article per category × 8 ]
    ── Portfolio ──
      Cash: ฿1,500.00 | Gold: 0.0000g
      can_buy: YES | can_sell: NO
  ## INSTRUCTIONS: Respond with a single JSON object...
```

### LLMClientFactory Registry

```python
_REGISTRY = {
  "gemini":      GeminiClient,      # Production default
  "groq":        GroqClient,        # Fast inference
  "claude":      ClaudeClient,      # Anthropic
  "openai":      OpenAIClient,
  "deepseek":    DeepSeekClient,
  "ollama":      OllamaClient,      # Backtest local
  "openrouter":  OpenRouterClient,  # Multi-model gateway
  "mock":        MockClient,        # Testing
}
```

### LLMResponse Schema

```python
@dataclass
class LLMResponse:
    text:         str    # raw JSON response
    prompt_text:  str    # full prompt (system+user) สำหรับ logging
    token_input:  int    # input tokens
    token_output: int    # output tokens
    token_total:  int    # total
    model:        str    # e.g. "gemini-3.1-flash-lite-preview"
    provider:     str    # e.g. "gemini"
```

---

## 8. Phase Detail: RiskManager (ภายใน Phase 2)

```
RiskManager.evaluate(llm_decision, market_state)
│
├── ด่านที่ 1 — Confidence Filter
│     signal != HOLD AND confidence < min_confidence (default 0.5)
│     → REJECT → HOLD
│
├── ด่านที่ 2 — Daily Loss Limit
│     _daily_loss_accumulated >= max_daily_loss_thb (default ฿500)
│     → REJECT → หยุดเทรดวันนี้
│
├── ด่านที่ 3 — Signal Routing
│   │
│   ├── HOLD → return as-is
│   │
│   ├── SELL
│   │     gold_grams <= 1e-4 → REJECT (No Shorting)
│   │     gold_value_thb = gold_grams × (sell_price_thb / 15.244)
│   │     → Approved
│   │
│   └── BUY
│         ├── ด่านที่ 4 — Position Sizing
│         │     cash < micro_port_threshold (2,000฿):
│         │       investment = min_trade_thb (1,000฿)  [micro-port fixed]
│         │     cash >= 2,000฿:
│         │       investment = cash × 0.5 × confidence
│         │     investment = min(investment, cash)
│         │     investment < min_trade_thb → REJECT
│         │
│         └── ด่านที่ 5 — ATR-based SL/TP
│               sl_distance = atr_value × atr_multiplier (2.0)
│               tp_distance = sl_distance × rr_ratio (1.5)
│               stop_loss   = buy_price_thb - sl_distance
│               take_profit = buy_price_thb + tp_distance
│               → Approved
│
Output: final_decision dict
  {
    signal, confidence, entry_price (THB/baht),
    stop_loss (THB/baht), take_profit (THB/baht),
    position_size_thb, rationale, rejection_reason
  }
```

---

## 9. Phase Detail: Weighted Voting (Phase 3)

```
calculate_weighted_vote(interval_results)
│
│   interval_results = {
│     "1h": { signal: "BUY",  confidence: 0.85 },
│     "4h": { signal: "BUY",  confidence: 0.90 },
│     "1d": { signal: "SELL", confidence: 0.60 },
│   }
│
├── Step 1: Collect votes
│     for interval, result in interval_results:
│       weight = INTERVAL_WEIGHTS.get(interval)
│       signal_votes[signal].append({ confidence, weight, interval })
│       total_weight += weight
│
├── Step 2: Calculate weighted scores
│     for signal in [BUY, SELL, HOLD]:
│       avg_conf       = mean(v.confidence for v in votes)
│       weighted_score = Σ(v.confidence × v.weight) / total_weight
│
├── Step 3: Select final signal
│     final_signal = argmax(weighted_score)
│     IF max_weighted_score < 0.40 → final_signal = "HOLD"
│
└── Output: {
      final_signal:        "BUY",
      weighted_confidence: 0.714,
      voting_breakdown: {
        "BUY":  { count:2, avg_conf:0.875, weighted_score:0.601 },
        "SELL": { count:1, avg_conf:0.600, weighted_score:0.113 },
        "HOLD": { count:0, ... }
      },
      interval_details: [
        { interval:"1h", signal:"BUY",  confidence:0.85, weight:0.22 },
        { interval:"4h", signal:"BUY",  confidence:0.90, weight:0.30 },
        { interval:"1d", signal:"SELL", confidence:0.60, weight:0.12 },
      ]
    }
```

---

## 10. Phase Detail: Notification + Persistence (Phase 4–5)

```
PHASE 4 — Discord Notification (BEFORE DB save)
  DiscordNotifier.notify(voting_result, interval_results, market_state, provider, period)
  │
  ├── Guard checks:
  │     enabled=False                → skip
  │     DISCORD_WEBHOOK_URL not set  → skip
  │     signal=HOLD AND notify_hold=False → skip
  │     confidence < min_conf        → skip
  │
  ├── build_embed() → Discord Rich Embed:
  │     Row 1: Signal emoji + Confidence bar
  │     Row 2: Entry / Stop Loss / Take Profit (จาก best interval)
  │     Row 3: ออม NOW sell/buy prices + USD/THB
  │     Row 4: Per-interval breakdown + Voting summary
  │     Row 5: Rationale (truncated 900 chars) + Meta
  │
  └── httpx.post(webhook_url, json=payload, timeout=10)

PHASE 5 — Persistence (AFTER notification)
  RunDatabase.save_run(provider, result, market_state, interval_tf, period)
  │
  ├── INSERT INTO runs (...) RETURNING id → run_id
  │     fields: signal, confidence, entry/sl/tp (THB/baht),
  │             gold_price (USD), gold_price_thb, rsi, macd_line,
  │             react_trace (JSON), market_snapshot (JSON)
  │
  └── save_llm_logs_batch(run_id, llm_logs_pending)
        for each interval_log:
          INSERT INTO llm_logs (run_id, interval_tf, step_type,
            signal, confidence, rationale, entry/sl/tp,
            full_prompt, full_response, trace_json,
            token_input, token_output, token_total, elapsed_ms,
            iterations_used, tool_calls_used, is_fallback, fallback_from)
```

---

## 11. Phase Detail: UI Render (Phase 6)

```
analysis_page.py  AnalysisPage._handle_run(ctx) → _run(provider, period, interval)
│
├── result = services["analysis"].run_analysis(provider, period, [interval])
│
├── Outputs (9 Gradio components):
│   ① market_box     ← str(market_state)[:1000]
│   ② trace_box      ← f"Trace from {best_iv} ({N} steps)"
│   ③ verdict_box    ← voting_summary + per-interval details
│   ④ explain_html   ← TraceRenderer.format_trace_html(best_trace)
│   ⑤ history_html   ← HistoryRenderer.format_history_html(recent 20)
│   ⑥ stats_html     ← StatsRenderer.format_stats_html(stats)
│   ⑦ multi_summary  ← HTML summary card
│   ⑧ auto_status    ← StatusRenderer badge
│   ⑨ llm_logs_html  ← _render_llm_logs_from_trace(best_trace)
│                         (แสดง prompt/response/token ทุก step)
│
└── Renderer classes (ui/core/renderers.py):
      TraceRenderer    → dark terminal — macOS chrome, blink cursor
      HistoryRenderer  → light editorial table — alternating rows
      PortfolioRenderer→ 5-card grid + allocation bar + constraint badges
      StatsRenderer    → compact inline pill badges
      StatusRenderer   → glass-panel colored badges (success/error/info)
      LlmLogRenderer   → dark terminal + collapsible prompt/response
```

---

## 12. Backtest Architecture

### 12.1 Production vs Backtest Mapping

| ส่วนประกอบ | Production | Backtest |
|-----------|-----------|---------|
| LLM | Gemini / Groq / Claude | Ollama (Qwen3:8b local) |
| ราคา | Live yfinance / TwelveData | CSV — thai_gold_1m_dataset.csv |
| ข่าว | Live RSS + FinBERT | Pre-processed finnhub_news.csv |
| Portfolio | PostgreSQL | SimPortfolio (in-memory) |
| Cache | ไม่มี | JSON per candle (resume ได้) |
| ReactOrchestrator | เหมือนกันทุกอย่าง | เหมือนกันทุกอย่าง |

### 12.2 SimPortfolio Logic

```python
# BUY
total_cost     = investment_thb + SPREAD_THB(30) + COMMISSION_THB(3)
grams_bought   = (investment_thb / price_thb_per_baht) × 15.244
cash_balance  -= total_cost

# SELL (close entire position)
proceeds       = (gold_grams / 15.244) × price_thb_per_baht
net_proceeds   = proceeds - SPREAD_THB(30) - COMMISSION_THB(3)
cash_balance  += net_proceeds
```

### 12.3 Backtest Results (90 days, 1h candles)

| Model | Dir. Accuracy | Sensitivity | Total Signals | Avg Net PnL (THB) |
|-------|:-----------:|:-----------:|:------------:|:-----------------:|
| qwen2.5:7b  | 54.94% | 10.64% | 162 | **-39.72** |
| qwen2.5:14b | 42.11% | 1.25%  | 19  | **+162.80** |
| qwen3:8b    | 50.00% | 5.91%  | 90  | **+139.71** |

---

## 13. Database Schema

```sql
-- Run history
CREATE TABLE runs (
    id               SERIAL PRIMARY KEY,
    run_at           TEXT    NOT NULL,        -- UTC ISO
    provider         TEXT    NOT NULL,        -- "gemini", "groq", ...
    interval_tf      TEXT,                    -- "1h,4h,1d"
    period           TEXT,                    -- "1mo", "3mo"
    signal           TEXT,                    -- "BUY"|"SELL"|"HOLD"
    confidence       REAL,
    entry_price      REAL,                    -- THB/baht (ออม NOW unit)
    stop_loss        REAL,
    take_profit      REAL,
    entry_price_thb  REAL,                    -- alias (backward compat)
    stop_loss_thb    REAL,
    take_profit_thb  REAL,
    usd_thb_rate     REAL,
    gold_price       REAL,                    -- USD/oz
    gold_price_thb   REAL,                    -- THB/baht sell price
    rsi              REAL,
    macd_line        REAL,
    signal_line      REAL,
    trend            TEXT,
    rationale        TEXT,
    iterations_used  INTEGER,
    tool_calls_used  INTEGER,
    react_trace      TEXT,                    -- JSON array
    market_snapshot  TEXT                     -- JSON
);

-- LLM thinking logs (1 row per interval per run)
CREATE TABLE llm_logs (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    logged_at       TEXT    NOT NULL,
    interval_tf     TEXT,
    step_type       TEXT,                     -- "THOUGHT_FINAL"
    iteration       INTEGER DEFAULT 0,
    provider        TEXT,
    signal          TEXT,
    confidence      REAL,
    rationale       TEXT,
    entry_price     REAL,
    stop_loss       REAL,
    take_profit     REAL,
    full_prompt     TEXT,                     -- ← expose จาก react.py
    full_response   TEXT,
    trace_json      TEXT,
    token_input     INTEGER,
    token_output    INTEGER,
    token_total     INTEGER,
    elapsed_ms      INTEGER,
    iterations_used INTEGER DEFAULT 0,
    tool_calls_used INTEGER DEFAULT 0,
    is_fallback     BOOLEAN DEFAULT FALSE,
    fallback_from   TEXT
);

-- Portfolio snapshot (UPSERT, id=1 เสมอ)
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

---

## 14. Trading Constraints

### Hard Constraints (enforced in System Prompt + RiskManager)

| Rule | Logic | ผล |
|------|-------|-----|
| Minimum Buy | `cash < ฿1,000` → `can_buy = NO` | LLM + RiskManager ห้าม BUY |
| No Short Selling | `gold_grams == 0` → `can_sell = NO` | REJECT → HOLD |
| Min Confidence | `confidence < 0.50` | REJECT → HOLD |
| Daily Loss Limit | `daily_loss >= ฿500` | REJECT ทั้งวัน |
| Position Cap | micro (<฿2,000): fixed ฿1,000 | ป้องกัน oversize |
| Position Cap | normal: `cash × 0.5 × confidence` | max 50% per trade |
| Platform Unit | Entry/SL/TP ต้องเป็น THB/baht | ระบุใน system prompt |

### Soft Constraints (LLM reasoning)

- RSI > 70 = overbought → หลีกเลี่ยง BUY
- RSI < 30 = oversold → หลีกเลี่ยง SELL
- MACD histogram ขยาย = momentum แรง → เพิ่ม confidence
- EMA20 > EMA50 = uptrend → prefer BUY
- `data_quality = "degraded"` → ลด weight technical, เพิ่ม weight news

---

## 15. Environment Setup

### Required Environment Variables (.env)

```bash
# ── LLM API Keys (ต้องมีอย่างน้อย 1 ตัว) ──────────────────────
GEMINI_API_KEY="your-gemini-api-key"
GROQ_API_KEY="your-groq-api-key"
OPENAI_API_KEY="your-openai-api-key"
ANTHROPIC_API_KEY="your-anthropic-api-key"

# ── Market Data ────────────────────────────────────────────────
TWELVEDATA_API_KEY="your-twelvedata-api-key"   # optional แต่แนะนำ

# ── Sentiment Analysis ─────────────────────────────────────────
HF_TOKEN="your-huggingface-token"

# ── Database ───────────────────────────────────────────────────
DATABASE_URL="postgresql://user:pass@localhost:5432/goldtrader"

# ── Notifications ──────────────────────────────────────────────
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
DISCORD_NOTIFY_ENABLED="true"
DISCORD_NOTIFY_HOLD="true"
DISCORD_NOTIFY_MIN_CONF="0.0"

# ── Backtest (Ollama) ──────────────────────────────────────────
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3:8b"

# ── Server ────────────────────────────────────────────────────
PORT=10000
LOG_LEVEL="INFO"
```

### How to Run

```bash
# Dashboard (แนะนำ)
cd Src/
source venv/bin/activate
python ui/dashboard.py
# เปิด http://localhost:10000

# CLI
python main.py --provider gemini
python main.py --provider groq --iterations 7
python main.py --provider gemini --skip-fetch   # ใช้ cache

# Backtest
python backtest/run_main_backtest.py \
  --gold-csv backtest/data_XAU_THB/thai_gold_1m_dataset.csv \
  --news-csv backtest/data_XAU_THB/finnhub_3month_news_ready_v2.csv \
  --timeframe 1h --days 90 --model qwen3:8b

# Resume หลัง crash
python backtest/run_main_backtest.py --model qwen3:8b --cache-dir backtest_cache_main
```

---

## 16. Extensibility

### เพิ่ม LLM Provider ใหม่

```python
# 1. สร้าง class ใน agent_core/llm/client.py
class MyLLMClient(LLMClient):
    PROVIDER_NAME = "myprovider"
    def call(self, prompt_package: PromptPackage) -> LLMResponse: ...
    def is_available(self) -> bool: ...

# 2. Register
LLMClientFactory.register("myprovider", MyLLMClient)

# 3. เพิ่มใน ui/core/config.py
PROVIDER_CHOICES.append(("My Model", "myprovider"))
PROVIDER_FALLBACK_CHAIN["myprovider"] = ["myprovider", "gemini", "mock"]
```

### เพิ่ม Technical Indicator

```python
# ใน data_engine/indicators.py
def calculate_roc(self) -> dict:
    roc = self.df['close'].pct_change(periods=12) * 100
    return { "value": roc.iloc[-1], "signal": "positive" if roc.iloc[-1] > 0 else "negative" }

def to_dict(self) -> dict:
    return { **existing_indicators, "roc": self.calculate_roc() }
```

### เพิ่ม OHLCV Source

```python
# ใน data_engine/ohlcv_fetcher.py — fetch_historical_ohlcv()
# หลัง TwelveData block, ก่อน yfinance fallback
if df_api.empty:
    # ใส่ logic ดึงจาก source ใหม่ตรงนี้
    pass
```

### เพิ่ม Navbar Tab ใหม่

```python
# สร้างไฟล์ใหม่ใน ui/navbar/my_page.py
from .base import PageBase, PageComponents, AppContext, navbar_page
import gradio as gr

@navbar_page("🆕 My Tab")
class MyPage(PageBase):
    def build(self, ctx: AppContext) -> PageComponents:
        pc = PageComponents()
        pc.register("my_output", gr.HTML())
        return pc

    def wire(self, demo, ctx, pc):
        pass  # เพิ่ม event hooks

# แล้ว import ใน ui/navbar/__init__.py
```

---

## 17. Risk Matrix

### Data Quality Risks

| ความเสี่ยง | ผลกระทบ | Mitigation |
|-----------|---------|-----------|
| Price mismatch — ออม NOW vs yfinance | Backtest PnL ไม่ตรงจริง | Playwright scrape intergold.co.th เป็น primary |
| Look-ahead bias — rolling indicators | Backtest accuracy สูงเกินจริง | `.shift(1)` ก่อน label |
| News timestamp mismatch | Signal ได้รับ news ผิดเวลา | nearest-match window 4h |
| FinBERT API timeout | sentiment_score = 0.0 | Retry × 3, fallback neutral |

### Model & AI Risks

| ความเสี่ยง | Mitigation |
|-----------|-----------|
| JSON parse failure | `_strip_think()` + `_extract_json_block()` + `extract_json()` fallback |
| Confidence calibration สูงเกินจริง | Calibrate min_confidence จาก backtest |
| HOLD bias (qwen2.5:14b ไม่เคย SELL) | ตรวจ signal distribution ก่อน production |
| Provider rate limit | FallbackChainClient + exponential backoff |

### Portfolio & Execution Risks

| ความเสี่ยง | Mitigation |
|-----------|-----------|
| Minimum trade constraint — ฿1,500 ทุน | Hard limit 50% max per trade ใน RiskManager |
| Spread erosion — ฿33/trade | Signal sensitivity check: > 10% → flag overtrading |
| Portfolio state drift (SimPortfolio vs PostgreSQL) | Manual sync ผ่าน Portfolio tab |

---

*Documentation maintained by: PM Team*
*Version: 3.3 | Updated: 2026-04-02*