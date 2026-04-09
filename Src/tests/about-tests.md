# About Tests — Gold Trading Agent

## สารบัญ

- [โครงสร้างไฟล์ Test](#โครงสร้างไฟล์-test)
- [วิธีรัน Tests](#วิธีรัน-tests)
- [รายละเอียดแต่ละ Test Directory](#รายละเอียดแต่ละ-test-directory)
  - [test_unit/](#1-test_unit--unit-tests)
  - [test_data_engine/](#2-test_data_engine--data-engine-tests)
  - [test_integration/](#3-test_integration--integration-tests)
  - [test_llm/](#4-test_llm--llm-tests-mock)
  - [test_llm_with_api/](#5-test_llm_with_api--llm-tests-real-api)
- [ไฟล์สนับสนุน](#ไฟล์สนับสนุน)
- [HTML Report](#html-report)
- [Markers](#markers)

---

## โครงสร้างไฟล์ Test

```
Src/tests/
├── conftest.py                         # Common fixtures + sys.path setup
├── run_test_report.py                  # Script สร้าง test report
├── about-tests.md                      # เอกสารนี้
│
├── test_unit/                          # Unit tests — pure logic
│   ├── test_calculator.py              #   คำนวณ trade metrics
│   ├── test_csv_loader.py              #   โหลด CSV data
│   ├── test_deploy_gate.py             #   deploy gate validation
│   ├── test_portfolio.py               #   SimPortfolio buy/sell/bust
│   ├── test_risk.py                    #   risk management + Hard Rules (Dead Zone, SL/TP override)
│   ├── test_session_manager.py         #   trading session windows ออม NOW (ใหม่)
│   └── test_logger_setup.py            #   logger setup + @log_method decorator (ใหม่)
│
├── test_data_engine/                   # Data engine tests
│   ├── test_indicators.py              #   Technical indicators (RSI, MACD, BB, ATR)
│   ├── test_thailand_timestamp.py      #   Timezone utilities
│   ├── test_extract_features.py        #   ML feature engineering
│   ├── test_fetcher.py                 #   Gold price + forex fetching
│   ├── test_ohlcv_fetcher.py           #   OHLCV data + cache
│   ├── test_newsfetcher.py             #   News + sentiment analysis
│   ├── test_orchestrator.py            #   Data pipeline orchestration
│   ├── test_gold_interceptor.py        #   WebSocket parsing logic
│   └── test_conJSON.py                 #   JSON export utility
│
├── test_integration/                   # Integration tests
│   ├── test_backtest_pipeline.py       #   Backtest pipeline end-to-end
│   ├── test_database.py                #   Database integration
│   ├── test_notification.py            #   Discord notification (unit helpers + integration pipeline)
│   └── test_react.py                   #   ReAct agent flow
│
├── test_llm/                           # LLM tests (mock, ไม่ใช้ API จริง)
│   ├── test_mock_and_factory.py        #   Mock LLM + factory pattern
│   ├── test_helpers.py                 #   LLM helper functions
│   └── test_fallback.py                #   Fallback strategy
│
└── test_llm_with_api/                  # LLM tests (ใช้ API จริง, ต้องมี key)
    ├── test_llm_contract.py            #   LLM contract validation
    ├── test_llm_eval.py                #   LLM evaluation
    └── test_token_usage.py             #   Token usage tracking
```

---

## วิธีรัน Tests

> **หมายเหตุ:** ทุกคำสั่งรันจาก directory `Src/`

### รันทั้งหมด (ยกเว้น llm + slow)

```bash
python -m pytest
```

ค่า default ใน `pyproject.toml` จะข้าม tests ที่มี marker `llm` และ `slow` อัตโนมัติ
และสร้าง HTML report ที่ `test_reports/report.html` ทุกครั้ง

### รันเฉพาะ directory

```bash
# Unit tests ทั้งหมด
python -m pytest tests/test_unit/

# Data engine tests ทั้งหมด
python -m pytest tests/test_data_engine/

# Integration tests ทั้งหมด
python -m pytest tests/test_integration/

# LLM tests (mock)
python -m pytest tests/test_llm/

# LLM tests (real API — ต้องมี API key ใน .env)
python -m pytest tests/test_llm_with_api/ -m llm
```

### รันเฉพาะไฟล์เดียว

```bash
python -m pytest tests/test_unit/test_portfolio.py
python -m pytest tests/test_unit/test_risk.py
python -m pytest tests/test_unit/test_session_manager.py
python -m pytest tests/test_unit/test_logger_setup.py
python -m pytest tests/test_data_engine/test_indicators.py
python -m pytest tests/test_integration/test_backtest_pipeline.py
```

### รันเฉพาะ test class หรือ function

```bash
# รันเฉพาะ class
python -m pytest tests/test_unit/test_portfolio.py::TestBuyExecution
python -m pytest tests/test_unit/test_risk.py::TestDeadZone
python -m pytest tests/test_unit/test_risk.py::TestStopLoss1
python -m pytest tests/test_unit/test_session_manager.py::TestFindSessionWeekday

# รันเฉพาะ function
python -m pytest tests/test_unit/test_portfolio.py::TestBuyExecution::test_buy_success
python -m pytest tests/test_unit/test_risk.py::TestDeadZone::test_dead_zone_rejects_buy
```

### รันตาม marker

```bash
python -m pytest -m unit            # เฉพาะ unit tests
python -m pytest -m data_engine     # เฉพาะ data engine tests
python -m pytest -m integration     # เฉพาะ integration tests
python -m pytest -m llm             # เฉพาะ LLM tests (ใช้ API จริง)
python -m pytest -m slow            # เฉพาะ slow tests
python -m pytest -m "not llm"       # ทุกอย่างยกเว้น LLM
```

### ตัวเลือกที่มีประโยชน์

```bash
python -m pytest --co               # Dry-run: แสดง test ที่จะรัน (ไม่รันจริง)
python -m pytest -v --tb=long       # Verbose + traceback ยาว
python -m pytest -x                 # หยุดทันทีเมื่อ test แรก fail
python -m pytest --lf               # รันเฉพาะ test ที่ fail ครั้งล่าสุด
python -m pytest -k "confidence"    # รันเฉพาะ test ที่ชื่อมี "confidence"
python -m pytest -k "dead_zone or sl1 or tp1"  # รันหลาย keyword
```

---

## รายละเอียดแต่ละ Test Directory

### 1. `test_unit/` — Unit Tests

ทดสอบ logic เพียวๆ ไม่มี I/O หรือ API call

| ไฟล์ | Source Module | ทดสอบอะไร |
|------|--------------|-----------|
| `test_calculator.py` | `backtest.metrics.calculator` | `calculate_trade_metrics()`, `add_calmar()` — คำนวณ Sharpe, win rate, drawdown |
| `test_csv_loader.py` | `backtest.data.csv_loader` | โหลด CSV, validate columns, handle missing data |
| `test_deploy_gate.py` | `backtest.metrics.deploy_gate` | `deploy_gate()`, `_safe()` — ตรวจ metrics ก่อน deploy |
| `test_portfolio.py` | `backtest.engine.portfolio` | `SimPortfolio` — buy/sell execution, bust detection, spread calculation |
| `test_risk.py` | `agent_core.core.risk` | Risk management ครบทุก Layer: confidence filter, daily loss, position sizing, **Dead Zone, Danger Zone, Hard Rule Override (SL1/SL2/TP1/TP2/TP3)** |
| `test_session_manager.py` ⭐ | `backtest.engine.session_manager` | `TradingSessionManager` — session windows ออม NOW (LATE/MORN/AFTN/EVEN/E), Dead zone boundaries, `record_trade()`, `compliance_report()`, `finalize()` |
| `test_logger_setup.py` ⭐ | `logs.logger_setup` | `setup_logger()`, duplicate handler prevention, `THTimeFormatter` (UTC+7), `@log_method` decorator |

> ⭐ = ไฟล์ที่เพิ่มใหม่โดย Benchaphon

```bash
python -m pytest tests/test_unit/
```

#### รายละเอียด test_risk.py (18 sections)

| Section | Class | สิ่งที่ทดสอบ |
|---------|-------|-------------|
| 1 | `TestInit` | ค่า default, custom values |
| 2 | `TestConfidenceFilter` | threshold, boundary, HOLD bypass |
| 3 | `TestDailyLossLimit` | accumulate, reset วันใหม่, SELL ไม่โดน block |
| 4 | `TestBuySignal` | position sizing fixed 1000 THB, SL/TP ATR-based |
| 5 | `TestSellSignal` | ต้องมีทอง, position from gold value |
| 6 | `TestHoldSignal` | pass-through, low confidence |
| 7 | `TestInvalidSignal` | unknown signal → reject |
| 8 | `TestBadMarketData` | missing key, zero price |
| 9 | `TestRecordTradeResult` | accumulate, ignore profit, reset |
| 10 | `TestRejectSignalSafety` | ไม่ mutate input dict |
| **11** | **`TestDeadZone`** | **02:00–06:14 → reject ทุก signal, boundary 02:00 / 06:14 / 01:59 / 06:15** |
| **12** | **`TestDangerZone`** | **01:30–01:59 + gold > 0 → บังคับ SELL, confidence = 1.0** |
| **13** | **`TestStopLoss1`** | **pnl ≤ -150 → SL1, boundary -149 ไม่ trigger** |
| **14** | **`TestStopLoss2`** | **pnl ≤ -80 + RSI < 35 → SL2, ต้องครบทั้งสองเงื่อนไข** |
| **15** | **`TestTakeProfit1`** | **pnl ≥ 300 → TP1, boundary 299 ไม่ trigger** |
| **16** | **`TestTakeProfit2`** | **pnl ≥ 150 + RSI > 65 → TP2, boundary RSI=65 ไม่ trigger** |
| **17** | **`TestTakeProfit3`** | **pnl ≥ 100 + macd_hist < 0 → TP3** |
| **18** | **`TestHardRuleOverrideBehavior`** | **SYSTEM OVERRIDE, position_size > 0, SL1 priority** |

#### รายละเอียด test_session_manager.py

| Class | สิ่งที่ทดสอบ |
|-------|-------------|
| `TestTimeRange` | `contains()` boundary start/end, inside/outside |
| `TestSessionDef` | WEEKDAY_SESSIONS IDs, MORN เริ่ม 06:15 (ไม่ใช่ 06:00) |
| `TestFindSessionWeekday` | boundary ครบ: LATE(00:00–01:59), Dead zone(02:00–06:14), MORN(06:15–11:59), AFTN(12:00–17:59), EVEN(18:00–23:59) |
| `TestFindSessionWeekend` | E(09:30–17:30), before/after boundary |
| `TestProcessCandle` | `SessionInfo` structure, `can_execute`, `session_id`, `label` |
| `TestRecordTrade` | นับ trade ใน session, แยก MORN/AFTN, นอก session ไม่ crash |
| `TestComplianceReportEmpty` | keys ครบ, ค่า zero, list ว่าง |
| `TestComplianceReportAfterFinalize` | passed count, compliance_pct, fail_flag, `all_details` structure |
| `TestSessionResult` | `to_dict()` keys ครบ, ค่าถูกต้อง |
| `TestFinalize` | finalize ก่อน candle ไม่ crash, finalize สองครั้งไม่ duplicate |

---

### 2. `test_data_engine/` — Data Engine Tests

ทดสอบ data fetching, feature engineering, indicators

| ไฟล์ | Source Module | ทดสอบอะไร |
|------|--------------|-----------|
| `test_indicators.py` | `data_engine.indicators` | RSI, MACD, Bollinger Bands, ATR, EMA, trend detection |
| `test_thailand_timestamp.py` | `data_engine.thailand_timestamp` | `get_thai_time()`, `convert_index_to_thai_tz()`, `to_thai_time()` — timezone ไทย |
| `test_extract_features.py` | `data_engine.extract_features` | `build_feature_dataset()` — สร้าง ML features จาก JSON, session encoding, trend mapping |
| `test_fetcher.py` | `data_engine.fetcher` | `GoldDataFetcher` — `compute_confidence()`, `calc_thai_gold_price()`, `fetch_gold_spot_usd()` |
| `test_ohlcv_fetcher.py` | `data_engine.ohlcv_fetcher` | `_ensure_utc_index()`, `_validate_ohlcv()`, `_retry_request()`, `_estimate_candles()` |
| `test_newsfetcher.py` | `data_engine.newsfetcher` | `NewsArticle`, `score_sentiment_batch()`, `_apply_global_limit()`, NEWS_CATEGORIES config |
| `test_orchestrator.py` | `data_engine.orchestrator` | `GoldTradingOrchestrator` — payload structure, save JSON, history_days override |
| `test_gold_interceptor.py` | `data_engine.gold_interceptor` | WebSocket "42" message parsing, gold rate extraction, payload structure |
| `test_conJSON.py` | `data_engine.conJSON` | JSON export — filename format, UTF-8 encoding, directory creation |

```bash
python -m pytest tests/test_data_engine/
```

> **หมายเหตุ:** `test_fetcher.py`, `test_ohlcv_fetcher.py`, `test_newsfetcher.py`, `test_orchestrator.py`
> ใช้ `unittest.mock` เพื่อ mock external APIs — ไม่เรียก API จริง

### 3. `test_integration/` — Integration Tests

ทดสอบการทำงานร่วมกันระหว่าง modules

| ไฟล์ | ทดสอบอะไร |
|------|-----------|
| `test_backtest_pipeline.py` | `MainPipelineBacktest` — pipeline ทั้งหมดตั้งแต่ signal → portfolio → metrics → export |
| `test_database.py` | Database connection + CRUD operations |
| `test_notification.py` | Discord Notification — unit helpers (`_confidence_bar`, `_fmt_price`, `_fmt_usd`, signal constants) + integration pipeline (config → build_embed → notify → webhook), guard chain, error recovery, runtime toggles |
| `test_react.py` | ReAct agent flow — reasoning + action loop |

```bash
python -m pytest tests/test_integration/
```

### 4. `test_llm/` — LLM Tests (Mock)

ทดสอบ LLM-related logic โดยไม่ใช้ API จริง

| ไฟล์ | ทดสอบอะไร |
|------|-----------|
| `test_mock_and_factory.py` | Mock LLM provider, factory pattern, PromptPackage |
| `test_helpers.py` | LLM helper functions — token counting, prompt formatting |
| `test_fallback.py` | Fallback strategy เมื่อ LLM ไม่ตอบ |

```bash
python -m pytest tests/test_llm/
```

### 5. `test_llm_with_api/` — LLM Tests (Real API)

ทดสอบด้วย API จริง — **ต้องตั้งค่า API key ใน `.env`**

| ไฟล์ | ทดสอบอะไร | ต้องการ |
|------|-----------|---------|
| `test_llm_contract.py` | LLM response structure validation | `OPENAI_API_KEY` หรือ `GEMINI_API_KEY` |
| `test_llm_eval.py` | LLM output quality evaluation | `OPENAI_API_KEY` หรือ `GEMINI_API_KEY` |
| `test_token_usage.py` | Token usage tracking + budget control | `OPENAI_API_KEY` หรือ `GEMINI_API_KEY` |

```bash
# ต้องใช้ -m llm เพื่อ override default marker filter
python -m pytest tests/test_llm_with_api/ -m llm -o "addopts="
```

> **คำเตือน:** การรัน tests เหล่านี้จะใช้ API credits จริง

---

## ไฟล์สนับสนุน

### `conftest.py`

ไฟล์กลางสำหรับ:
- **`sys.path` setup** — เพิ่ม `Src/` เข้า path เพื่อให้ import modules ได้
- **Common fixtures** — ใช้ร่วมกันทุกไฟล์:

| Fixture | ใช้ใน | คำอธิบาย |
|---------|-------|----------|
| `ohlcv_df` | test_indicators, test_csv_loader | fake OHLCV DataFrame 300 rows, seed=42 |
| `ohlcv_200_df` | test_indicators, test_session_manager | fake OHLCV DataFrame 200 rows |
| `uptrend_df` / `downtrend_df` / `flat_df` | test_indicators | OHLCV สำหรับ trend scenarios |
| `winning_trade` / `losing_trade` | test_calculator | mock ClosedTrade object |
| `mixed_trades` | test_calculator | 5 trades ผสม (3W/2L) |
| `portfolio()` | test_backtest_pipeline | SimPortfolio พร้อมค่า default |
| `rich_portfolio()` | test_portfolio | SimPortfolio 100,000 THB |
| `neutral_news()` | test_backtest_pipeline | NullNewsProvider สำหรับ neutral sentiment |
| `sample_row()` | test_backtest_pipeline | 1 candle row ปกติ (RSI=55) |
| `overbought_row()` | test_backtest_pipeline | Candle ที่ RSI overbought (RSI=75) |
| `oversold_row()` | test_backtest_pipeline | Candle ที่ RSI oversold (RSI=25) |
| `market_state()` | test_notification, test_risk | Market state dict มาตรฐาน |
| `market_state_with_gold()` | test_risk | Market state ที่กำลังถือทองอยู่ |
| `market_state_minimal()` | test_notification | Market state ไม่มี optional fields |
| `sample_json_payload()` | test_orchestrator, test_extract_features | mock JSON payload (bullish) |
| `sample_json_payload_bearish()` | test_orchestrator | mock JSON payload (bearish) |

### `run_test_report.py`

Script สำหรับรัน tests ทั้งหมดแล้วสร้าง Markdown report:

```bash
python tests/run_test_report.py
```

---

## HTML Report

ทุกครั้งที่รัน `pytest` จะสร้าง HTML report อัตโนมัติที่:

```
Src/test_reports/report.html
```

เปิดไฟล์ใน browser เพื่อดู:
- **Summary** — จำนวน tests passed/failed/error
- **Results table** — รายละเอียดทุก test พร้อม duration
- **Filters** — กรองดูเฉพาะ passed/failed
- **Sort** — เรียงตาม result/name/duration

---

## Markers

กำหนดใน `pyproject.toml`:

| Marker | คำอธิบาย | ความถี่การรัน |
|--------|----------|---------------|
| `unit` | Unit tests — pure logic, no I/O | ทุก commit |
| `data_engine` | Data engine tests — indicators, features | ทุก commit |
| `integration` | Integration tests — cross-module | ทุก commit |
| `llm` | LLM tests ที่ใช้ API จริง | สัปดาห์ละครั้ง |
| `slow` | Tests ที่ใช้เวลานาน > 5 วินาที | ก่อน release |
| `smoke` | Smoke tests — ตรวจว่าระบบไม่พัง | ก่อน deploy |
| `api` | Tests ที่ต้องเรียก external API | ตามต้องการ |
| `eval` | LLM Evaluation tests | ตามต้องการ |

---

## Quick Reference

```bash
# รันทั้งหมด (default: ยกเว้น llm + slow)
python -m pytest

# รันเฉพาะ directory
python -m pytest tests/test_unit/
python -m pytest tests/test_data_engine/
python -m pytest tests/test_integration/

# รันเฉพาะไฟล์
python -m pytest tests/test_unit/test_risk.py
python -m pytest tests/test_unit/test_session_manager.py
python -m pytest tests/test_unit/test_logger_setup.py

# รันเฉพาะ Hard Rules ใน risk
python -m pytest tests/test_unit/test_risk.py::TestDeadZone
python -m pytest tests/test_unit/test_risk.py::TestStopLoss1
python -m pytest tests/test_unit/test_risk.py::TestTakeProfit1

# Dry-run
python -m pytest --co

# รันเฉพาะ test ที่ fail ครั้งล่าสุด
python -m pytest --lf

# รัน LLM tests (ใช้ API จริง)
python -m pytest -m llm -o "addopts="
```