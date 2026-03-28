# Data Engine — Output Pipeline Flow

## Overview

```
APIs → fetcher/ohlcv_fetcher/newsfetcher → orchestrator → JSON → extract_features → CSV
```

---

## Outputs

### 1. `cache/ohlcv_XAU_USD_{interval}.csv`
**จาก:** `ohlcv_fetcher.py`  
**คืออะไร:** แท่งเทียนย้อนหลัง (OHLCV) เก็บ cache ไว้เพื่อลด API call ครั้งต่อไป  
**ใช้ต่อ:** ไม่ต้องใช้โดยตรง — `orchestrator.py` โหลดอัตโนมัติ

---

### 2. `output/payload_{timestamp}.json` + `output/latest.json`
**จาก:** `orchestrator.py` (เรียกผ่าน `conJSON.py`)  
**คืออะไร:** JSON หลักของระบบ รวมทุกอย่างไว้ในที่เดียว

```
latest.json
├── meta             — version, timestamp, interval
├── market_data
│   ├── spot_price_usd    — ราคาทอง XAU/USD (+ confidence score)
│   ├── forex             — USD/THB rate
│   ├── thai_gold_thb     — ราคาทองไทย buy/sell
│   └── recent_price_action — 5 แท่งเทียนล่าสุด
├── technical_indicators
│   ├── rsi, macd, bollinger, atr
│   └── trend (ema_20, ema_50, sma_200, death_cross)
└── news.by_category  — headline + sentiment_score ต่อหมวด
```

**ใช้ต่อ:**
- **LLM Agent** → ส่ง JSON นี้เป็น context ตรงๆ ได้เลย
- **extract_features.py** → อ่านไฟล์นี้เพื่อสกัด features

---

### 3. `Data/features_master.csv`
**จาก:** `extract_features.py`  
**คืออะไร:** ตาราง ML-ready แบบ append — แต่ละครั้งที่รันจะเพิ่ม 1 แถวใหม่

| กลุ่ม | Columns |
|---|---|
| Time | `datetime`, `hour`, `day_of_week`, `is_asian/london/ny_session` |
| Price | `spot_price`, `usd_thb`, `thai_gold_sell` |
| Indicators | `rsi`, `macd_hist`, `bollinger_pct_b`, `bollinger_bw`, `atr`, `trend_encoded`, `ema_20`, `sma_200` |
| Sentiment | `sentiment_thai_gold_market`, `sentiment_gold_price`, `sentiment_geopolitics`, `sentiment_dollar_index`, `sentiment_fed_policy` |

**ใช้ต่อ:** โหลดเข้า `scikit-learn` / XGBoost / Random Forest เพื่อ train model โดยตรง

---

## Run Order

```bash
# 1. สร้าง JSON (ทำทุกครั้ง)
python conJSON.py

# 2. สกัด features ลง CSV (ทำทุกครั้งหลัง step 1)
python extract_features.py
```

---

## ตัวอย่าง Data ล่าสุด (2026-03-28)

| Field | Value |
|---|---|
| Spot Price | $4,507.71 / oz |
| USD/THB | 32.87 |
| Thai Gold (sell) | ฿70,150 |
| RSI | 36.3 (neutral) |
| Trend | Downtrend (Death Cross) |
| Overall Sentiment | Negative (ส่วนใหญ่ −0.9x) |
