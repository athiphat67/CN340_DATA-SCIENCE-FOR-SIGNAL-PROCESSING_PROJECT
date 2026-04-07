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
│   └── test_risk.py                    #   risk management
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
python -m pytest tests/test_data_engine/test_indicators.py
python -m pytest tests/test_integration/test_backtest_pipeline.py
```

### รันเฉพาะ test class หรือ function

```bash
# รันเฉพาะ class
python -m pytest tests/test_unit/test_portfolio.py::TestBuyExecution

# รันเฉพาะ function
python -m pytest tests/test_unit/test_portfolio.py::TestBuyExecution::test_buy_success
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
| `test_risk.py` | `backtest.engine.risk` | Risk management — position sizing, stop loss |

```bash
python -m pytest tests/test_unit/
```

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
| `portfolio()` | test_backtest_pipeline | SimPortfolio พร้อมค่า default |
| `neutral_news()` | test_backtest_pipeline | NullNewsProvider สำหรับ neutral sentiment |
| `sample_row()` | test_backtest_pipeline | 1 candle row ปกติ |
| `overbought_row()` | test_backtest_pipeline | Candle ที่ RSI overbought |
| `market_state()` | test_notification | Market state dict มาตรฐาน |
| `market_state_minimal()` | test_notification | Market state ไม่มี optional fields |

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
python -m pytest tests/test_data_engine/test_indicators.py

# รันเฉพาะ test
python -m pytest tests/test_unit/test_portfolio.py::TestBuyExecution::test_buy_success

# Dry-run
python -m pytest --co

# รันเฉพาะ test ที่ fail ครั้งล่าสุด
python -m pytest --lf

# รัน LLM tests (ใช้ API จริง)
python -m pytest -m llm -o "addopts="
```
