# 📖 Src_V2 — นักขุดทอง v2.1 (XGBoost-based Gold Trading Signal System)

## 1. ภาพรวม (Overview)

`Src_V2` คือระบบ **สร้างสัญญาณซื้อ-ขายทองคำไทย** แบบอัตโนมัติ ที่ขับเคลื่อนด้วย **Dual-Model XGBoost** (ไม่ใช่ Generative AI / LLM)
โดยทำงานเป็น loop ต่อเนื่องทุก 15 นาที ดึงข้อมูลตลาดแบบ real-time แล้วให้โมเดล ML ตัดสินใจว่าควร **BUY**, **SELL** หรือ **HOLD**

### สิ่งที่ระบบทำ (High-Level)
1. **ดึงข้อมูลตลาด** — ราคาทองไทย (ฮั่วเซ่งเฮง/Intergold), ราคา Spot Gold (XAU/USD), อัตราแลกเปลี่ยน USD/THB, OHLCV, ข่าวสาร
2. **คำนวณ Technical Indicators** — RSI, MACD, Bollinger Bands, ATR, EMA/Trend
3. **สกัด Feature Vector** → 26 ตัวแปร ตาม schema `models/feature_columns.json`
4. **XGBoost Dual-Model Predict** → `model_buy.pkl` + `model_sell.pkl` ทำนาย probability → ตัดสิน BUY/SELL/HOLD
5. **Gates (Risk + Session)** — กรองสัญญาณผ่าน RiskManager + SessionGate แบบ concurrent
6. **แจ้งเตือน + บันทึก** — ส่ง Discord/Telegram (ถ้า ALL PASS) และบันทึกทุกรอบลง PostgreSQL

---

## 2. สถาปัตยกรรม (Architecture)

```
                          ┌─────────────────────────────┐
                          │         main.py              │
                          │    (Orchestration Loop)      │
                          └──────────┬──────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
   ┌─────────────────┐    ┌──────────────────┐     ┌──────────────────┐
   │   data_engine/   │    │    ml_core/       │     │     core.py      │
   │   orchestrator   │    │    signal.py      │     │  (CoreDecision)  │
   │                  │    │  (XGBoostPredictor)│     │  fan-out/fan-in  │
   └────────┬────────┘    └────────┬─────────┘     └───────┬──────────┘
            │                      │                       │
   ┌────────┴────────┐             │              ┌────────┴────────┐
   │  fetcher.py     │             │              │  risk.py        │
   │  indicators.py  │             │              │  session_gate.py│
   │  newsfetcher.py │             │              └─────────────────┘
   │  ohlcv_fetcher  │             │
   │  interceptor    │             │
   │  extract_features│            │
   └─────────────────┘             │
                                   │
                     ┌─────────────┴──────────────┐
                     │        notification/        │
                     │  discord_notifier.py        │
                     │  telegram_notifier.py       │
                     └─────────────────────────────┘
                                   │
                     ┌─────────────┴──────────────┐
                     │        database/            │
                     │  database.py (PostgreSQL)   │
                     └─────────────────────────────┘
```

---

## 3. Pipeline Flow (ขั้นตอนการทำงานต่อ 1 รอบ)

```
market_state → 26-feature vector → XGBoost predict → CoreDecision → notify + persist
```

| Step | Module | รายละเอียด |
|------|--------|------------|
| **1. Data Fetch** | `data_engine/orchestrator.py` | ดึงราคาทอง, forex, OHLCV (yfinance/TwelveData), ข่าว (RSS + yfinance + FinBERT sentiment) |
| **2. Feature Extract** | `data_engine/extract_features.py` | `get_xgboost_feature_v2()` สกัด 26 features (candle OHLC, returns, RSI, MACD, BB, ATR, EMA, candle shape, cyclic time) |
| **3. Signal Predict** | `ml_core/signal.py` | `XGBoostPredictor` โหลด 2 โมเดล (buy/sell) ทำ `predict_proba` แล้วเทียบ threshold (0.60) |
| **4. Core Decision** | `core.py` | รัน `RiskManager` + `SessionGate` แบบ concurrent (ThreadPoolExecutor 2 workers) |
| **5. Notify + Persist** | `notification/` + `database/` | ส่ง Discord/Telegram ถ้า ALL PASS, บันทึกลง PostgreSQL ทุกรอบ |

---

## 4. โครงสร้างไดเรกทอรี (Directory Structure)

```
Src_V2/
├── main.py                     # Entry point — orchestration loop
├── core.py                     # CoreDecision (fan-out gates → fan-in)
├── .env                        # Environment variables (API keys, DB URL)
├── requirements.txt            # Python dependencies
│
├── data_engine/                # === Data Layer ===
│   ├── orchestrator.py         # GoldTradingOrchestrator — conductor หลัก
│   ├── fetcher.py              # GoldDataFetcher — ดึงราคา spot, forex, ทองไทย
│   ├── ohlcv_fetcher.py        # OHLCVFetcher — ดึงกราฟแท่งเทียน (yfinance → TwelveData fallback)
│   ├── indicators.py           # TechnicalIndicators — RSI, MACD, BB, ATR, EMA
│   ├── extract_features.py     # สกัด 26/37 features สำหรับ XGBoost
│   ├── newsfetcher.py          # GoldNewsFetcher — ดึงข่าว + FinBERT sentiment (sync/async)
│   ├── gold_interceptor_lite.py# WebSocket interceptor — ดึงราคาทองไทย real-time
│   ├── thailand_timestamp.py   # Timezone helper (Asia/Bangkok)
│   ├── tools/                  # Tool registry (fetch_price, fetch_indicators, fetch_news)
│   │   ├── tool_registry.py
│   │   ├── fetch_price.py
│   │   ├── fetch_indicators.py
│   │   ├── fetch_news.py
│   │   ├── interceptor_manager.py
│   │   ├── schema_validator.py
│   │   └── tool_result_scorer.py
│   ├── analysis_tools/         # Fundamental + Technical analysis tools
│   │   ├── fundamental_tools.py
│   │   ├── technical_tools.py
│   │   └── pre_fetch.py
│   └── pipeline_flow/          # Pipeline flow documentation
│
├── ml_core/                    # === ML / Decision Layer ===
│   ├── signal.py               # XGBoostPredictor — dual-model (buy/sell) predict
│   ├── risk.py                 # RiskManager — confidence filter, SL/TP, position sizing
│   └── session_gate.py         # SessionGate — ตรวจช่วงเวลาเทรด (เวลาไทย)
│
├── models/                     # === Trained Models ===
│   ├── model_buy.pkl           # XGBoost binary classifier สำหรับ BUY (2.7 MB)
│   └── model_sell.pkl          # XGBoost binary classifier สำหรับ SELL (4.9 MB)
│
├── database/                   # === Persistence Layer ===
│   ├── database.py             # RunDatabase — PostgreSQL (connection pool, CRUD)
│   ├── import_backtest.py      # Import backtest data
│   └── migrate_data.py         # Schema migration
│
├── notification/               # === Notification Layer ===
│   ├── discord_notifier.py     # DiscordNotifier — Webhook embed
│   └── telegram_notifier.py    # TelegramNotifier — HTML message
│
├── watch_engine/               # === Event-Driven Watcher ===
│   ├── watcher.py              # WatcherEngine — market monitoring + trailing stop
│   └── indicators.py           # Indicators สำหรับ watcher (ซ้ำกับ data_engine แต่แยก context)
│
└── logs/                       # === Logging ===
    ├── logger_setup.py         # sys_logger configuration
    └── api_logger.py           # Trade log API sender
```

---

## 5. รายละเอียดแต่ละ Module

### 5.1 `main.py` — Entry Point

- **ชื่อโปรแกรม**: นักขุดทอง v2.1
- **ทุนเริ่มต้น**: ฿1,500 (Aom NOW platform)
- **Default interval**: 900 วินาที (15 นาที)
- **Runtime container**: `Runtime` dataclass รวม dependency ทั้งหมด
- **Graceful shutdown**: ดักจับ SIGINT/SIGTERM
- **CLI arguments**: `--interval`, `--model-buy`, `--model-sell`, `--skip-fetch`, `--no-save`, `--no-notify`, `--once`

```bash
python -m Src_V2.main                # default (loop ทุก 15 นาที)
python Src_V2/main.py --once         # รันรอบเดียว
python Src_V2/main.py --no-save      # dry-run ไม่บันทึก DB
```

### 5.2 `core.py` — CoreDecision (Fan-Out → Fan-In)

รับ signal จาก XGBoost แล้วกระจายไปตรวจ 2 gates พร้อมกัน:

| Gate | Module | หน้าที่ |
|------|--------|---------|
| **Risk Gate** | `ml_core/risk.py` | ตรวจ confidence, capital, position sizing, SL/TP, daily loss limit |
| **Session Gate** | `ml_core/session_gate.py` | ตรวจช่วงเวลาเทรด (Asian/London/NY), dead zone, minimum confidence |

- **ALL PASS** → คงสัญญาณเดิม + `notify=True`
- **any REJECT** → บังคับเป็น HOLD + `notify=False`
- ถ้า model บอก HOLD → bypass gates ทั้งสอง (fast path)

### 5.3 `data_engine/` — Data Layer

#### `orchestrator.py` — GoldTradingOrchestrator
- Conductor หลักที่เรียก tools ตามลำดับ: `fetch_price` → `fetch_indicators` → `fetch_news`
- ทำ **Data Stitching** — แพตช์ราคา real-time เข้ากราฟ OHLCV ที่ delay
- ดึงราคาทองไทยจาก **MTS Gold TradingView API** เป็น primary, fallback ไป Interceptor
- คำนวณ spread coverage, edge score, price trend
- สร้าง `market_state` payload ที่มีข้อมูลครบถ้วน

#### `fetcher.py` — GoldDataFetcher
- ดึงราคา Spot Gold แบบ **Waterfall**: TwelveData → yfinance → Gold-API
- ดึง USD/THB แบบ **4-Layer Fallback**: Interceptor → yfinance → TwelveData → exchangerate-api
- อ่านราคาทองไทยจากไฟล์ `latest_gold_price.json` (สร้างโดย interceptor)

#### `gold_interceptor_lite.py` — Real-Time Gold Price Interceptor
- ดึงราคาทองคำไทย real-time จาก **ฮั่วเซ่งเฮง API** (primary)
- Fallback ไป **Intergold WebSocket** ถ้า HSH ล่ม
- อัปเดตไฟล์ `latest_gold_price.json` เมื่อราคาเปลี่ยน
- รันเป็น background thread

#### `indicators.py` — TechnicalIndicators
- คำนวณ Technical Indicators แบบ vectorized (pandas):
  - **RSI-14** (Wilder's smoothing)
  - **MACD** (12, 26, 9) — รวม crossover detection (bullish_cross, bearish_zone, etc.)
  - **Bollinger Bands** (20, 2σ) — %B, bandwidth
  - **ATR-14** — รองรับแปลงหน่วย THB/บาททอง
  - **EMA** (20, 50, 200) + trend label

#### `extract_features.py` — Feature Extraction
- **`get_xgboost_feature_v2()`** — สกัด **26 features** สำหรับ Dual-Model XGBoost:

| กลุ่ม | Features | จำนวน |
|-------|----------|-------|
| Candle OHLC | xauusd_open/high/low/close | 4 |
| Returns | xauusd_ret1, xauusd_ret3, usdthb_ret1 | 3 |
| MACD/EMA Distance | xau_macd_delta1, dist_ema21, dist_ema50, usdthb_dist_ema21, trend_regime | 5 |
| Oscillators | xauusd_rsi14, xau_rsi_delta1, xauusd_macd_hist | 3 |
| Volatility | xauusd_atr_norm, xauusd_bb_width, atr_rank50 | 3 |
| Candle Shape | wick_bias, body_strength | 2 |
| Cyclic Time | hour_sin/cos, minute_sin/cos, session_progress, day_of_week | 6 |
| **Total** | | **26** |

- **`get_xgboost_feature()`** (legacy) — สกัด 37 features (เดิม, ยังมีโค้ดอื่นใช้)

#### `newsfetcher.py` — GoldNewsFetcher
- ดึงข่าวจาก 8 หมวดหมู่ที่ส่งผลต่อทองคำ (gold_price, usd_thb, fed_policy, inflation, geopolitics, dollar_index, thai_economy, thai_gold_market)
- แหล่งข้อมูล: **yfinance ticker news** + **RSS feeds** (Kitco, Reuters, FXStreet, Bangkok Post)
- Sentiment analysis: **FinBERT** ผ่าน Hugging Face API (รองรับทั้ง sync และ async)
- Smart caching ทุก 12 ชั่วโมง + token budget control (3,000 tokens)

### 5.4 `ml_core/` — ML / Decision Layer

#### `signal.py` — XGBoostPredictor (Dual-Model)
- โหลด 2 โมเดล binary classifier จาก pickle:
  - `model_buy.pkl` → `predict_proba()[0][1]` = ความน่าจะเป็น BUY
  - `model_sell.pkl` → `predict_proba()[0][1]` = ความน่าจะเป็น SELL
- **Decision Rule** (unified threshold = 0.60):
  ```
  if buy_proba > 0.60 && buy_proba >= sell_proba  →  BUY  (conf = buy_proba)
  elif sell_proba > 0.60 && sell_proba > buy_proba →  SELL (conf = sell_proba)
  else                                             →  HOLD (conf = max)
  ```
- Feature schema: 26 features ตาม `models/feature_columns.json` (exact name + order)

#### `risk.py` — RiskManager (V5 WinRate Focus)
- **Gate 0a**: Session Guard — block BUY ใน Dead Zone
- **Gate 0b**: Trailing Stop + TP/SL Hard Override — TP hit หรือ Trailing SL hit → auto SELL
- **Gate 1**: Confidence Filter — BUY ≥ 0.60, SELL ≥ 0.60
- **Gate 1.5**: Capital Protection — daily quota (6 trades/day), HTF trend check, spread edge check
- **Gate 2**: Daily Loss Limit — block BUY ถ้าขาดทุนสะสม ≥ ฿500/วัน
- **Gate 3**: Position Sizing — คำนวณ SL/TP จาก ATR × multiplier, dynamic sizing ตาม confidence
- **พารามิเตอร์หลัก**:
  - `atr_multiplier = 2.5`, `risk_reward_ratio = 1.5`
  - `min_trade_thb = 1,400`, `max_daily_loss_thb = 500`
  - `max_trade_risk_pct = 0.20`, Trailing Stop เริ่มหลัง 1.0× ATR

#### `session_gate.py` — SessionGate
- กำหนดช่วงเวลาเทรด (เวลาไทย UTC+7):

| Session | เวลา | Mode |
|---------|------|------|
| Night | 00:00–01:59 | Edge |
| Morning | 06:15–11:59 | Edge |
| Noon | 12:00–17:59 | Edge |
| Evening | 18:00–23:59 | Edge |
| Weekend | 09:30–17:30 | Edge |

- **Edge mode**: ปกติ, แนะนำ confidence ≥ 0.62
- **Quota mode**: ใกล้ปิด session (≤ 15 นาที), แนะนำ confidence ≥ 0.58
- นอกช่วง session → `apply_gate=False` → ไม่เทรด

### 5.5 `models/` — Trained Models

| ไฟล์ | ขนาด | หน้าที่ |
|------|-------|---------|
| `model_buy.pkl` | 2.7 MB | Binary classifier — ทำนายความน่าจะเป็น BUY |
| `model_sell.pkl` | 4.9 MB | Binary classifier — ทำนายความน่าจะเป็น SELL |

- Format: scikit-learn compatible (XGBClassifier wrapped) — โหลดผ่าน `joblib.load()`
- ใช้ 26 features ตาม schema `models/feature_columns.json`

### 5.6 `database/` — Persistence Layer

#### `database.py` — RunDatabase
- ใช้ **PostgreSQL** ผ่าน `psycopg2` + `ThreadedConnectionPool` (1–5 connections)
- Tables:

| Table | หน้าที่ |
|-------|---------|
| `runs` | บันทึกผลวิเคราะห์ทุกรอบ (signal, confidence, SL/TP, market snapshot) |
| `portfolio` | สถานะพอร์ต (cash, gold_grams, unrealized PnL) — 1 row เสมอ |
| `trade_log` | ประวัติ BUY/SELL ทุกครั้งที่ execute จริง |
| `llm_logs` | เก็บ trace ของ LLM (legacy จาก v1, ยังรองรับ) |
| `gold_prices_ig` | เก็บราคาทอง historical (Intergold) |

### 5.7 `notification/` — Notification Layer

#### `discord_notifier.py` — DiscordNotifier
- ส่ง embed ผ่าน Discord Webhook
- แสดง: Signal, Confidence bar, Entry/SL/TP, Market Data, Rationale
- config ผ่าน env: `DISCORD_WEBHOOK_URL`, `DISCORD_NOTIFY_ENABLED`, `DISCORD_NOTIFY_HOLD`

#### `telegram_notifier.py` — TelegramNotifier
- ส่งข้อความ HTML ผ่าน Telegram Bot API
- เนื้อหาเหมือน Discord แต่ format เป็น HTML
- config ผ่าน env: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

### 5.8 `watch_engine/` — Event-Driven Watcher

#### `watcher.py` — WatcherEngine
- **ทำงานแยกจาก main loop** — monitor ตลาดแบบ event-driven
- ใช้ **Pydantic** validate config ตอน init
- **TriggerState**: cooldown + price step gate ป้องกันการเรียก AI ถี่เกินไป
- **Strategy 3 Cases**:
  1. ถือทอง + ราคา < SL → ตรวจว่า fake swing หรือ real reversal
  2. ถือทอง + RSI overbought → ปลุก AI take profit
  3. ไม่ถือทอง + RSI oversold → ปลุก AI buy
- **Trailing Stop**: เลื่อน SL อัตโนมัติเมื่อกำไร, persist ลง DB ป้องกันหายหลัง restart
- **Signal Filters**: Fake Swing Detection + Real Reversal Scoring (6-point system)

### 5.9 `logs/` — Logging

- `logger_setup.py` — ตั้งค่า `sys_logger` สำหรับระบบทั้งหมด
- `api_logger.py` — ส่ง trade log ไป external API (TEAM_API_KEY)

---

## 6. Data Sources (แหล่งข้อมูล)

| ข้อมูล | Primary Source | Fallback |
|--------|---------------|----------|
| ราคาทองไทย (THB) | MTS Gold TradingView API | ฮั่วเซ่งเฮง API → Intergold WebSocket |
| Spot Gold (XAU/USD) | TwelveData | yfinance (GC=F) → Gold-API |
| USD/THB | Interceptor (Yahoo Finance) | yfinance → TwelveData → exchangerate-api |
| OHLCV | yfinance (GC=F) | TwelveData (XAU/USD) |
| ข่าว | yfinance ticker news + RSS | Cache (12 ชม.) |
| Sentiment | FinBERT via Hugging Face API | คืน 0.0 |

---

## 7. Environment Variables (.env)

| Variable | ใช้ใน | หน้าที่ |
|----------|-------|---------|
| `DATABASE_URL` | database.py | PostgreSQL connection string |
| `DISCORD_WEBHOOK_URL` | discord_notifier.py | Discord Webhook URL |
| `TELEGRAM_BOT_TOKEN` | telegram_notifier.py | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | telegram_notifier.py | Telegram Chat ID |
| `HF_TOKEN` | newsfetcher.py | Hugging Face API Token (FinBERT) |
| `TWELVEDATA_API_KEY` | fetcher.py, ohlcv_fetcher.py | TwelveData API Key |
| `TEAM_API_KEY` | api_logger.py | Trade log external API key |

---

## 8. Key Design Decisions

1. **Dual-Model แทน Multi-Class** — แยกโมเดล BUY/SELL เป็น 2 binary classifiers เพื่อ threshold tuning อิสระ
2. **Concurrent Gates** — Risk + Session gate รันขนานกันผ่าน ThreadPoolExecutor ลดเวลา latency
3. **Database-First** — บันทึกทุกรอบ (ทั้ง HOLD และ BUY/SELL) เพื่อ audit trail
4. **Fail-Safe Mock** — ถ้าโหลด XGBoost ไม่ได้ ใช้ MockPredictor ที่คืน HOLD เสมอ (ปลอดภัย)
5. **Multi-Layer Fallback** — ทุก data source มี fallback อย่างน้อย 2 ชั้น
6. **Data Stitching** — แพตช์ราคา real-time ลงแท่งเทียนล่าสุดเพื่อลด lag
7. **Trailing Stop V5** — เริ่มหลังราคาขึ้น 1.0× ATR จาก entry (ไม่ตัดกำไรก่อนเวลา)

---

## 9. ความแตกต่างจาก Src (v1)

| หัวข้อ | Src (v1) | Src_V2 (v2.1) |
|--------|----------|---------------|
| Decision Engine | LLM-based (Gemini/GPT) | Pure ML (XGBoost) |
| Feature Count | ไม่ fixed | 26 features (fixed schema) |
| Model | Generative AI | 2 × Binary Classifier (.pkl) |
| Gate System | Sequential | Concurrent (ThreadPoolExecutor) |
| Risk Management | Basic | V5 WinRate Focus (trailing stop, ATR-based SL/TP) |
| News Sentiment | LLM-interpreted | FinBERT (async-capable) |
| Provider Tag | `gemini` / `openrouter` | `xgboost-v2` |
