# GoldTrader — Complete Agent Architecture Documentation v3.4

---

## 1. Overview & Goal

**GoldTrader** คือ production-grade **ReAct + LLM trading agent** สำหรับวิเคราะห์และตัดสินใจเทรดทองคำบนแพลตฟอร์ม **ออม NOW** (Hua Seng Heng)

### 1.1 Mission

ผสมผสาน multi-step AI reasoning เข้ากับ real-time technical indicators และ news sentiment เพื่อ generate สัญญาณ **BUY / SELL / HOLD** พร้อม rule-based TP/SL ที่ตรงกับ platform จริง

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
| **CSV Orchestrator** | `data_engine/csv_orchestrator.py` | Drop-in CSV mode แทน live fetch |
| **Services** | `ui/core/services.py` | AnalysisService, PortfolioService, HistoryService |
| **UI** | `ui/dashboard.py` + `ui/navbar/` | Gradio 5-tab dashboard |
| **Database** | `database/database.py` | PostgreSQL — runs, portfolio, llm_logs |
| **Backtest** | `backtest/` | run_main_backtest.py + SimPortfolio v2.1 |
| **Notification** | `notification/discord_notifier.py` | Discord webhook alert |

### 1.4 Changelog v3.4 — Rule-Based TP/SL & Portfolio Hardening

| ด้าน | v3.3 (เดิม) | v3.4 (ใหม่) |
|------|------------|------------|
| **TP/SL Rules** | ATR-based (RiskManager คำนวณ) | Rule-based ใน system prompt: TP1/TP2/TP3, SL1/SL2/SL3 |
| **Position Size** | proportional (50% × cash × conf) | Fixed ฿1,000 เสมอ (ออม NOW minimum) |
| **Spread Model** | Flat SPREAD_THB per trade | Proportional SPREAD_PER_BAHT (120 THB/บาทน้ำหนัก) |
| **Session Hours** | Approximate (06:00 open) | ถูกต้อง: Mon–Fri 06:15→02:00 / Sat–Sun 09:30→17:30 |
| **Session IDs** | AB/C/D/E | LATE/MORN/AFTN/EVEN (weekday) + E (weekend) |
| **Backtest Metrics** | Directional accuracy only | + MDD, Sharpe, Sortino, Calmar, Win Rate, Profit Factor |
| **Deploy Gate** | ไม่มี | 7-check gate: Sharpe/WinRate/MDD/PF/Compliance/Bust/Calmar |
| **CSV Orchestrator** | ไม่มี | CSVOrchestrator — drop-in แทน live data |
| **LLM Defaults** | gemini-3.1-flash-lite | gemini-2.5-flash-lite |

---

## 2. Project Structure

```
Src/
│
├── about_src.md                        # เอกสารนี้
│
├── agent_core/                         # 🧠 ส่วนมันสมองของ AI
│   ├── config/
│   │   ├── roles.json                  # Role definitions — trading rules + TP/SL logic
│   │   └── skills.json                 # Skill + tool registry
│   ├── core/
│   │   ├── prompt.py                   # PromptBuilder, SkillRegistry, RoleRegistry, AIRole
│   │   ├── react.py                    # ReactOrchestrator — ReAct loop หลัก
│   │   └── risk.py                     # RiskManager — validate + daily loss limit
│   └── llm/
│       └── client.py                   # LLMClientFactory + 8 providers
│
├── backtest/                           # 🔬 ทดสอบย้อนหลัง
│   ├── data/
│   │   └── csv_loader.py               # load CSV + คำนวณ indicators (anti-lookahead)
│   ├── engine/
│   │   ├── news_provider.py            # NewsProvider interface (Null/CSV/Live)
│   │   ├── portfolio.py                # SimPortfolio v2.1 — proportional spread
│   │   └── session_manager.py         # TradingSessionManager v2.1 — ออม NOW hours
│   ├── metrics/
│   │   ├── calculator.py               # Win Rate, Profit Factor, Calmar
│   │   └── deploy_gate.py              # 7-check PASS/FAIL verdict
│   ├── backtest_main_pipeline.py       # ⚠️ DEPRECATED — ใช้ run_main_backtest.py แทน
│   └── run_main_backtest.py            # ✅ Entry point หลัก — MDD/Sharpe/Sortino/Gate
│
├── data_engine/                        # 📡 เชื่อมต่อข้อมูลภายนอก
│   ├── interceptor/
│   │   └── fetcher.py                  # GoldDataFetcher (spot price + forex + Thai gold)
│   ├── csv_orchestrator.py             # CSVOrchestrator — drop-in CSV mode
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
│   _normalize_provider()                              get_llm_logs()     │
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
  │ CSVOrchestrator  │  │ PromptBuilder  │  │ PostgreSQL       │
  │ GoldDataFetcher  │  │ LLMClientFact. │  │ tables:          │
  │ OHLCVFetcher     │  │ FallbackChain  │  │  runs            │
  │ TechIndicators   │  │ RiskManager    │  │  portfolio       │
  │ GoldNewsFetcher  │  └───────┬────────┘  │  llm_logs        │
  └──────────────────┘          │           └──────────────────┘
                                │
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

GoldTradingOrchestrator  (หรือ CSVOrchestrator — drop-in)
  ├── GoldDataFetcher
  │     └── OHLCVFetcher(session=shared requests.Session)
  ├── TechnicalIndicators(ohlcv_df)
  └── GoldNewsFetcher()

CSVOrchestrator (CSV mode)
  ├── load_gold_csv()   ← backtest.data.csv_loader
  ├── merge external CSV (gold_spot_usd, usd_thb_rate)  ← optional
  └── CSVNewsProvider / NullNewsProvider

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
  │     GoldTradingOrchestrator.run(history_days, interval)  ← หรือ CSVOrchestrator
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
CLI: python backtest/run_main_backtest.py --provider gemini --timeframe 1h --days 30
  │
  ▼
MainPipelineBacktest.__init__()
  ├── _create_llm_client(provider)   ← OllamaClient local OR LLMClientFactory
  ├── CandleCache(cache_dir)         ← JSON per candle (resume ได้)
  ├── NewsProvider (null/csv/live)   ← plug-in news
  ├── TradingSessionManager v2.1     ← session compliance tracking
  └── SimPortfolio v2.1              ← proportional spread
  │
  ▼
bt.run()
  ├── load_and_aggregate(csv)        ← resample + ensure indicators + merge external
  └── for row in candles:
        ├── session_manager.process_candle(ts) → SessionInfo(can_execute)
        ├── CandleCache.get(ts)       → HIT: skip LLM
        ├── build_market_state(row, portfolio, news, interval)
        ├── ReactOrchestrator.run(market_state)   ← SAME as production
        ├── _apply_to_portfolio(result)            ← SimPortfolio v2.1
        └── CandleCache.set(ts, result)
  │
  ├── calculate_metrics()
  │     ├── Directional accuracy (llm + final prefix)
  │     ├── _compute_risk_metrics() → MDD, Sharpe, Sortino, Calmar
  │     ├── session_manager.compliance_report()
  │     └── calculate_trade_metrics(portfolio.closed_trades)
  │
  ├── export_csv()
  └── deploy_gate(metrics) → ✅ DEPLOY / ❌ NOT READY
```

---

## 6. Phase Detail: Data Collection (Phase 1)

```
GoldTradingOrchestrator.run(history_days=N, interval=X, save_to_file=True)
│
├── Step 1.1 — Spot Price (Multi-Source)
│   GoldDataFetcher.fetch_gold_spot_usd()
│   ① TwelveData → ② gold-api → ③ yfinance
│   compute_confidence(prices) → { source, price_usd_per_oz, confidence }
│
├── Step 1.2 — Forex Rate
│   fetch_usd_thb_rate() → GET exchangerate-api.com
│
├── Step 1.3 — Thai Gold Price (ออม NOW reference)
│   Primary: Playwright WebSocket scrape intergold.co.th
│   Fallback: formula price_thb_per_gram = price_usd × usd_thb / 31.1034768
│
├── Step 1.4 — OHLCV (OHLCVFetcher)
│   CSV Cache → TwelveData → yfinance fallback
│   _validate_ohlcv() → _merge_cache() → save
│
├── Step 1.5 — Technical Indicators
│   TechnicalIndicators(ohlcv_df).to_dict(interval)
│   RSI(14), MACD(12/26/9), Bollinger, ATR(14), Trend(EMA20/EMA50)
│
├── Step 1.6 — News Sentiment (Parallel)
│   GoldNewsFetcher → ThreadPoolExecutor × 8 categories
│   FinBERT via HuggingFace API → weighted avg (direct=1.5/high=1.2/medium=1.0)
│
└── Step 1.7 — Assemble & Save
    payload → agent_core/data/latest.json
```

**CSVOrchestrator (drop-in สำหรับ CSV mode)**

```python
orchestrator = CSVOrchestrator(
    gold_csv="backtest/data/Final_Merged_HSH_M5.csv",
    external_csv="...",   # optional: gold_spot_usd, usd_thb_rate
    news_csv="...",       # optional: overall_sentiment, news_count
    interval="5m",
)
payload = orchestrator.run(history_days=90)
# payload structure เหมือน GoldTradingOrchestrator.run() ทุกอย่าง
# → ใช้กับ AnalysisService ได้โดยไม่แก้โค้ด
```

---

## 7. Phase Detail: LLM Analysis Loop (Phase 2)

```
AnalysisService._run_single_interval(provider, market_state, interval)
│
├── 1. Build FallbackChainClient
│   PROVIDER_FALLBACK_CHAIN.get(provider) → fallback_order
│   for p in fallback_order: LLMClientFactory.create(p) → client
│   FallbackChainClient(chain_clients)
│
├── 2. Build PromptBuilder + ReactConfig
│   PromptBuilder(role_registry, AIRole.ANALYST)
│   ReactConfig(max_iterations=3, max_tool_calls=0)
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
      └── Full ReAct Loop (max_tool_calls > 0) ← ถ้าเปิด tool mode
```

### LLM Prompt Structure (roles.json → AIRole.ANALYST)

```
SYSTEM:
You are an expert gold trader for the Aom NOW platform.
Your ONLY job is to analyze technical indicators and market structure to provide BUY, SELL, or HOLD signals.

## CRITICAL RULES
1. You manage a FIXED capital of ฿1,500 THB.
2. Do NOT calculate or worry about Take-Profit (TP) or Stop-Loss (SL) levels. The external RiskManager system is hard-coded to enforce TP/SL and Danger/Dead zones automatically.
3. Position size is ALWAYS exactly ฿1000 THB.

## BUY CONDITIONS (Focus on Technicals)
Recommend BUY only if:
- cash >= 1010 THB
- You see at least 2 strong bullish signals (e.g., RSI < 35 for bounce, MACD histogram > 0, Price > EMA20)
- Confidence is >= 0.60

## SELL CONDITIONS (Technical Exits)
Recommend SELL only based on technical breakdowns (e.g., bearish divergence, MACD crossing down, RSI overbought > 70). Do not attempt to calculate profit or loss. Your goal is to exit a bad technical setup before the hard constraints of the RiskManager are forced to trigger.

## OUTPUT FORMAT
Respond with ONLY a single JSON object. No markdown.
{
  "action": "FINAL_DECISION",
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "entry_price": null,
  "stop_loss": null,
  "take_profit": null,
  "position_size_thb": 1000,
  "rationale": "Short technical reason (max 40 words)"
}
```

### LLMClientFactory Registry

```python
_REGISTRY = {
    "gemini":     GeminiClient,      # DEFAULT_MODEL = "gemini-2.5-flash-lite"
    "groq":       GroqClient,        # DEFAULT_MODEL = "llama-3.3-70b-versatile"
    "claude":     ClaudeClient,      # DEFAULT_MODEL = "claude-opus-4-1"
    "openai":     OpenAIClient,      # DEFAULT_MODEL = "gpt-4o-mini"
    "deepseek":   DeepSeekClient,    # DEFAULT_MODEL = "deepseek-chat"
    "ollama":     OllamaClient,      # default via OLLAMA_MODEL env
    "openrouter": OpenRouterClient,
    "mock":       MockClient,        # Testing
}
```

---

## 8. Phase Detail: RiskManager (ภายใน Phase 2)

```
RiskManager.evaluate(llm_decision, market_state)
│
├── ด่านที่ 1 — Confidence Filter
│     signal != HOLD AND confidence < min_confidence (default 0.6)
│     → REJECT → HOLD
│
├── ด่านที่ 2 — Daily Loss Limit
│     _daily_loss_accumulated >= max_daily_loss_thb (default ฿500)
│     → REJECT → หยุดเทรดวันนี้
│
├── ด่านที่ 3 — Signal Routing
│   ├── HOLD → return as-is
│   │
│   ├── SELL
│   │     gold_grams <= 1e-4 → REJECT (No Shorting)
│   │     gold_value_thb = gold_grams × (sell_price_thb / 15.244)
│   │     → Approved
│   │
│   └── BUY
│         ├── ด่านที่ 4 — Position Sizing
│         │     cash < micro_port_threshold (2,000฿): investment = min_trade_thb (1,000฿)
│         │     cash >= 2,000฿: investment = cash × 0.5 × confidence
│         │     investment < min_trade_thb → REJECT
│         │
│         └── ด่านที่ 5 — ATR-based SL/TP (fallback ถ้า LLM ไม่ได้กำหนด)
│               sl_distance = atr_value × atr_multiplier (2.0)
│               tp_distance = sl_distance × rr_ratio (1.5)
│
└── Output: final_decision dict
    { signal, confidence, entry_price (THB), stop_loss, take_profit,
      position_size_thb, rationale, rejection_reason }
```


---

## 9. Phase Detail: Weighted Voting (Phase 3) ** เอาออกแล้ว **

---

## 10. Phase Detail: Notification + Persistence (Phase 4–5)

```
PHASE 4 — Discord Notification 
  DiscordNotifier.notify(voting_result, interval_results, market_state, ...)
  Guards: enabled / webhook_set / HOLD filter / min_conf
  build_embed() → Discord Rich Embed → httpx.post(webhook_url)

PHASE 5 — Persistence (AFTER notification)
  RunDatabase.save_run(provider, result, market_state, interval_tf, period)
    → INSERT INTO runs → run_id
  RunDatabase.save_llm_logs_batch(run_id, llm_logs_pending)
    → INSERT INTO llm_logs (prompt, response, tokens, elapsed_ms, ...)
```

---

## 11. Backtest Architecture

### 11.1 Production vs Backtest Mapping

| ส่วนประกอบ | Production | Backtest |
|-----------|-----------|---------|
| LLM | Gemini / Groq / | Ollama (local) หรือ Gemini/Groq ผ่าน API |
| ราคา | Live TwelveData / yfinance | CSV — Final_Merged_HSH_M5.csv |
| ข่าว | Live RSS + FinBERT | NullNewsProvider (default) / CSVNewsProvider |
| Portfolio | PostgreSQL | SimPortfolio v2.1 (in-memory) |
| Cache | ไม่มี | JSON per candle (resume ได้ถ้า crash) |
| ReactOrchestrator | เหมือนกัน | เหมือนกัน |
| Spread Model | proportional (production logic) | proportional SPREAD_PER_BAHT = 120 |

### 11.2 SimPortfolio v2.1 Logic

```python
# spread = proportional (ไม่ใช่ flat แล้ว)
SPREAD_PER_BAHT = 120.0   # THB / 1 บาทน้ำหนัก
COMMISSION_THB  = 3.0     # THB per trade

# BUY
baht_weight    = position_thb / price_per_baht
spread_cost    = baht_weight × SPREAD_PER_BAHT          # ≈ ฿1.67 สำหรับ ฿1,000 @ ฿71,950
total_cost     = position_thb + spread_cost + COMMISSION_THB
grams_bought   = (position_thb / price_per_baht) × 15.244
cash_balance  -= total_cost

# SELL (close entire position)
baht_weight    = gold_grams / GOLD_GRAM_PER_BAHT
spread_cost    = baht_weight × SPREAD_PER_BAHT
proceeds       = (gold_grams / 15.244) × price_per_baht
net_proceeds   = proceeds - spread_cost - COMMISSION_THB
cash_balance  += net_proceeds

# Break-even price move (round trip) ≈ ฿650/บาทน้ำหนัก
# ต้นทุน % ≈ 0.9% ของ position (เทียบกับ version เก่า = 24% — ผิด!)
```

### 11.3 TradingSessionManager v2.1

```
ออม NOW จริง (อัปเดต 2026):
  จันทร์–ศุกร์: 06:15 → 02:00 น. (ข้ามคืน)
  เสาร์–อาทิตย์: 09:30 → 17:30 น.
  Dead zone: 02:00–06:14 (ตลาดปิด — ห้ามส่งคำสั่ง)

Session IDs (weekday):
  LATE  : 00:00–01:59   ← ต่อเนื่องจากคืนก่อน (min_trades=1)
  MORN  : 06:15–11:59   ← เช้า                 (min_trades=2)
  AFTN  : 12:00–17:59   ← บ่าย                 (min_trades=2)
  EVEN  : 18:00–23:59   ← เย็น-ดึก             (min_trades=2)

Session IDs (weekend):
  E     : 09:30–17:30   ←                       (min_trades=2)

compliance_pct = passed_sessions / eligible_sessions × 100
  (no_data sessions ไม่นับ fail)
```

### 11.4 Backtest Metrics (calculator.py + risk_metrics)

```
_compute_risk_metrics(df):
  equity   = portfolio_total_value ต่อ candle
  returns  = pct_change(equity)
  ppy      = periods per year ตาม timeframe (1h = 6,048)
  rf_rate  = 0.02 / ppy   (2% ต่อปี)
  
  MDD         = min((equity - cummax) / cummax)
  Sharpe      = mean(excess) / std(excess) × √ppy
  Sortino     = mean(excess) / downside_std × √ppy
  ann_return  = (1 + mean_return)^ppy - 1
  Calmar      = ann_return_pct / abs(mdd_pct)

calculate_trade_metrics(closed_trades):
  win_rate_pct    = wins / total × 100
  profit_factor   = sum(winning_pnl) / abs(sum(losing_pnl))
  avg_win/loss    = mean PnL per side
  expectancy      = (WR × avg_win) + ((1-WR) × avg_loss)
  max_consec_loss = losing streak ยาวสุด
```

### 11.5 Deploy Gate (deploy_gate.py)

| Check | Threshold | ดึงจาก |
|-------|-----------|-------|
| sharpe_ratio | > 1.0 | risk metrics |
| win_rate_pct | > 50% | trade metrics |
| mdd_pct_abs | < 20% | risk metrics |
| profit_factor | > 1.2 | trade metrics |
| session_compliance | > 80% | session_manager |
| portfolio_not_bust | = True | portfolio.bust_flag |
| calmar_ratio | > 1.0 | trade metrics |

ทั้ง 7 ต้องผ่านพร้อมกัน → **✅ DEPLOY** มิฉะนั้น → **❌ NOT READY**

---

## 12. Trading Rules (roles.json v3.4)

### Hard Rules — ตรวจสอบใน System Prompt ก่อน output ทุก call

| Rule | เงื่อนไข | Action |
|------|---------|--------|
| **TP1** | PnL ≥ +฿300 | SELL ทันที — Lock profit |
| **TP2** | PnL ≥ +฿150 AND RSI > 65 | SELL — Overbought |
| **TP3** | PnL ≥ +฿100 AND MACD hist < 0 | SELL — Momentum fading |
| **SL1** | PnL ≤ -฿150 | SELL ทันที — No exceptions |
| **SL2** | PnL ≤ -฿80 AND RSI < 35 | SELL — Breakdown confirmed |
| **SL3** | time 01:30–01:59 + holding | SELL ก่อนตลาดปิด 02:00 |
| **No Cash** | cash < ฿1,010 | HOLD — ห้าม BUY |
| **Position** | BUY ต้องการ cash ≥ ฿1,010 | position_size_thb = 1,000 เสมอ |

### BUY Conditions (ALL ต้องผ่าน)

1. cash ≥ ฿1,010
2. gold_grams = 0 (ไม่ถือทองอยู่)
3. Time NOT 01:30–06:14
4. อย่างน้อย 2/3 bullish signals: RSI 40–60 หรือ <35 / MACD hist > 0 / price > EMA20
5. confidence ≥ 0.65

### Platform Info

- **Trading hours:** Mon–Fri 06:15–02:00 (next day) | Sat–Sun 09:30–17:30
- **Dead zone:** 02:00–06:14 (ห้ามส่งคำสั่งโดยสิ้นเชิง)
- **Round-trip cost:** ~฿9 total (~0.9% ของ ฿1,000 position)
- **Break-even move:** ~฿650/บาทน้ำหนัก

---

## 13. Database Schema

```sql
CREATE TABLE runs (
    id               SERIAL PRIMARY KEY,
    run_at           TEXT,
    provider         TEXT,
    interval_tf      TEXT,        -- "1h,4h,1d"
    period           TEXT,        -- "1mo"
    signal           TEXT,        -- "BUY"|"SELL"|"HOLD"
    confidence       REAL,
    entry_price      REAL,        -- THB/บาทน้ำหนัก
    stop_loss        REAL,
    take_profit      REAL,
    entry_price_thb  REAL,        -- alias (backward compat)
    stop_loss_thb    REAL,
    take_profit_thb  REAL,
    usd_thb_rate     REAL,
    gold_price       REAL,        -- USD/oz
    gold_price_thb   REAL,        -- THB/บาทน้ำหนัก sell price
    rsi              REAL,
    macd_line        REAL,
    signal_line      REAL,
    trend            TEXT,
    rationale        TEXT,
    iterations_used  INTEGER,
    tool_calls_used  INTEGER,
    react_trace      TEXT,        -- JSON array
    market_snapshot  TEXT         -- JSON
);

CREATE TABLE llm_logs (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER REFERENCES runs(id) ON DELETE CASCADE,
    logged_at       TEXT,
    interval_tf     TEXT,
    step_type       TEXT,         -- "THOUGHT_FINAL"
    iteration       INTEGER,
    provider        TEXT,
    signal          TEXT,
    confidence      REAL,
    rationale       TEXT,
    entry_price     REAL,
    stop_loss       REAL,
    take_profit     REAL,
    full_prompt     TEXT,         -- ← expose จาก react.py
    full_response   TEXT,
    trace_json      TEXT,
    token_input     INTEGER,
    token_output    INTEGER,
    token_total     INTEGER,
    elapsed_ms      INTEGER,
    iterations_used INTEGER,
    tool_calls_used INTEGER,
    is_fallback     BOOLEAN,
    fallback_from   TEXT
);

CREATE TABLE portfolio (
    id                SERIAL PRIMARY KEY,
    cash_balance      REAL    DEFAULT 1500.0,
    gold_grams        REAL    DEFAULT 0.0,
    cost_basis_thb    REAL    DEFAULT 0.0,
    current_value_thb REAL    DEFAULT 0.0,
    unrealized_pnl    REAL    DEFAULT 0.0,
    trades_today      INTEGER DEFAULT 0,
    updated_at        TEXT
);
```

---

## 14. Environment Setup

### Required Environment Variables (.env)

```bash
# ── LLM API Keys ────────────────────────────────────────────────
GEMINI_API_KEY="your-gemini-api-key"
GROQ_API_KEY="your-groq-api-key"
OPENAI_API_KEY="your-openai-api-key"
ANTHROPIC_API_KEY="your-anthropic-api-key"

# ── Market Data ─────────────────────────────────────────────────
TWELVEDATA_API_KEY="your-twelvedata-api-key"   # optional แต่แนะนำ

# ── Sentiment Analysis ──────────────────────────────────────────
HF_TOKEN="your-huggingface-token"

# ── Database ────────────────────────────────────────────────────
DATABASE_URL="postgresql://user:pass@localhost:5432/goldtrader"

# ── Notifications ───────────────────────────────────────────────
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
DISCORD_NOTIFY_ENABLED="true"
DISCORD_NOTIFY_HOLD="true"
DISCORD_NOTIFY_MIN_CONF="0.0"

# ── Backtest (Ollama) ───────────────────────────────────────────
OLLAMA_BASE_URL="http://localhost:11434"
OLLAMA_MODEL="qwen3:8b"

# ── Server ──────────────────────────────────────────────────────
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

# Backtest — Gemini (production LLM)
python backtest/run_main_backtest.py \
  --gold-csv backtest/data/Final_Merged_HSH_M5.csv \
  --provider gemini \
  --timeframe 1h \
  --days 30

# Backtest — Ollama local
python backtest/run_main_backtest.py \
  --gold-csv backtest/data/Final_Merged_HSH_M5.csv \
  --provider ollama \
  --model qwen3:8b \
  --ollama-url http://localhost:11434 \
  --timeframe 5m \
  --days 7

# Backtest — Mock (test pipeline, no API)
python backtest/run_main_backtest.py \
  --gold-csv backtest/data/Final_Merged_HSH_M5.csv \
  --provider mock \
  --timeframe 1h \
  --days 7

# Resume หลัง crash (cache ยังอยู่)
python backtest/run_main_backtest.py \
  --gold-csv backtest/data/Final_Merged_HSH_M5.csv \
  --provider gemini \
  --cache-dir backtest_cache_main \
  --timeframe 1h
```

---

## 15. Extensibility

### เพิ่ม LLM Provider ใหม่

```python
# 1. สร้าง class ใน agent_core/llm/client.py
class MyLLMClient(LLMClient):
    PROVIDER_NAME = "myprovider"
    DEFAULT_MODEL = "my-model-name"
    def call(self, prompt_package: PromptPackage) -> LLMResponse: ...
    def is_available(self) -> bool: ...

# 2. Register
LLMClientFactory.register("myprovider", MyLLMClient)

# 3. เพิ่มใน ui/core/config.py
PROVIDER_CHOICES.append(("My Model", "myprovider"))
PROVIDER_FALLBACK_CHAIN["myprovider"] = ["myprovider", "gemini", "mock"]
```

### สลับ Data Source เป็น CSV

```python
# ใน ui/dashboard.py — เปลี่ยนจาก GoldTradingOrchestrator
# from data_engine.orchestrator import GoldTradingOrchestrator
# orchestrator = GoldTradingOrchestrator()

# เป็น CSVOrchestrator
from data_engine.csv_orchestrator import CSVOrchestrator
orchestrator = CSVOrchestrator(
    gold_csv="backtest/data/Final_Merged_HSH_M5.csv",
    interval="5m",
)
# ไม่ต้องแก้ services.py เลย
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

### เพิ่ม TP/SL Rule ใหม่

แก้ `agent_core/config/roles.json` → `system_prompt` → section `### Take-Profit` / `### Stop-Loss`

ตัวอย่าง: เพิ่ม TP4 — trailing stop
```
- TP4: Unrealized PnL ≥ +฿200 AND price dropped 0.3% from intraday high → SELL. Trailing stop.
```

---

## 16. Risk Matrix

### Data Quality Risks

| ความเสี่ยง | Mitigation |
|-----------|-----------|
| Price mismatch ออม NOW vs yfinance | Playwright scrape intergold.co.th + HSH CSV |
| Look-ahead bias — rolling indicators | `.shift(1)` ทุก indicator ใน csv_loader.py |
| News timestamp mismatch | nearest-match window 4h |
| FinBERT API timeout | sentiment_score = 0.0 (neutral fallback) |

### Model & AI Risks

| ความเสี่ยง | Mitigation |
|-----------|-----------|
| JSON parse failure | `_strip_think()` + `_extract_json_block()` + `extract_json()` fallback |
| LLM ignores TP/SL rules | Inject rule checklist + PnL status label ใน user prompt ทุก call |
| HOLD bias | ตรวจ signal distribution ก่อน production — deploy_gate win_rate > 50% |
| Provider rate limit | FallbackChainClient + exponential backoff (×3) |

### Portfolio & Execution Risks

| ความเสี่ยง | Mitigation |
|-----------|-----------|
| Bust threshold ฿1,000 | Hard limit cash < ฿1,010 → HOLD; SimPortfolio PortfolioBustException |
| Spread erosion | proportional spread model → ~฿9 round trip (0.9%) แทน flat ฿246 (24%) |
| Dead zone trades | SessionManager can_execute=False → skip execution |
| Portfolio drift | Manual sync ผ่าน Portfolio tab + portfolio.to_market_state_dict() ทุก candle |

### Backtest-Specific Risks

| ความเสี่ยง | Mitigation |
|-----------|-----------|
| Annualized return จาก data สั้น | แสดง `annualized_reliable=False` ถ้า < 60 วัน |
| Survivorship bias | ใช้ CSV ราคาจริง HSH — ไม่ filter |
| LLM randomness ข้าม run | CandleCache JSON — ผลเหมือนเดิมทุก resume |

---

## 17. Constants Reference

| Constant | ค่า | ที่มา | ความหมาย |
|----------|-----|------|---------|
| `GOLD_GRAM_PER_BAHT` | 15.244 g | portfolio.py | กรัมต่อ 1 บาทน้ำหนัก |
| `SPREAD_PER_BAHT` | 120.0 THB | portfolio.py | spread ต่อ 1 บาทน้ำหนัก (proportional) |
| `SPREAD_THB` | 120.0 THB | portfolio.py | alias เพื่อ backward compat |
| `COMMISSION_THB` | 3.0 THB | portfolio.py | commission คงที่ต่อ trade |
| `DEFAULT_CASH` | 1,500.0 THB | portfolio.py | ทุนเริ่มต้น |
| `BUST_THRESHOLD` | 1,000.0 THB | portfolio.py | ต่ำกว่านี้ = bust |
| `WIN_THRESHOLD` | 1,500.0 THB | portfolio.py | สูงกว่านี้ = winner |
| `MIN_CONFIDENCE` | 0.65 | roles.json | confidence ขั้นต่ำสำหรับ BUY |
| `max_daily_loss_thb` | 500.0 THB | risk.py | daily loss limit |

---

*Documentation maintained by: PM Team*  
*Version: 3.4 | Updated: 2026-04-05*