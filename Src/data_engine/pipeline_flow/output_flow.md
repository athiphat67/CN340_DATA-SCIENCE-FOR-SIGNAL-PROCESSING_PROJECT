# 📦 Data Engine Team — Output Pipeline Flow

> สิ่งที่ฝั่ง Data Engine ส่งออกมา และใช้ต่ออย่างไร

---

## 🗺️ ภาพรวม Pipeline

```
External APIs
    │
    ├── Gold Price API (twelvedata / gold-api / yfinance)
    ├── Forex API (exchangerate-api.com)
    ├── Thai Gold (intergold.co.th / calculated)
    └── News (yfinance + RSS)
    │
    ▼
[fetcher.py + ohlcv_fetcher.py + newsfetcher.py]
    │
    ▼
[indicators.py]  ← คำนวณ RSI, MACD, Bollinger, ATR, Trend
    │
    ▼
[orchestrator.py]  ← รวมทุกอย่างเป็น payload เดียว
    │
    ├── OUTPUT 1 → output/latest.json          (ทับทุกครั้ง)
    ├── OUTPUT 1 → output/payload_{ts}.json    (เก็บประวัติ)
    └── [cache/ ohlcv_*.csv]                   (internal cache)
    │
    ▼
[extract_features.py]
    │
    └── OUTPUT 2 → Data/features_master.csv    (append ต่อเรื่อยๆ)
```

---

## 📁 Output ที่ส่งต่อได้

### Output 1 — `output/latest.json`

**ใครสร้าง:** `orchestrator.py` (เรียกผ่าน `conJSON.py`)  
**รูปแบบ:** JSON nested หลายชั้น  
**Refresh:** ทุกครั้งที่รัน pipeline (ล่าสุดทับของเก่า)

**โครงสร้างข้อมูล:**

```
latest.json
├── meta
│   ├── generated_at        เวลาที่สร้าง (Thai timezone)
│   ├── history_days        ข้อมูลย้อนหลังกี่วัน
│   └── interval            timeframe ที่ใช้ (เช่น "1d", "5m")
│
├── market_data
│   ├── spot_price_usd
│   │   ├── price_usd_per_oz    ราคาทอง XAU/USD ปัจจุบัน
│   │   ├── source              แหล่งข้อมูล (twelvedata / gold-api / yfinance)
│   │   └── confidence          ความน่าเชื่อถือ 0.0–1.0
│   ├── forex
│   │   └── usd_thb             อัตราแลกเปลี่ยน USD/THB
│   ├── thai_gold_thb
│   │   ├── sell_price_thb      ราคาขาย (บาท/บาท)
│   │   ├── buy_price_thb       ราคารับซื้อ
│   │   └── spread_thb          ส่วนต่าง (ปกติ 100 บาท)
│   └── recent_price_action     5 แท่งเทียนล่าสุด [open, high, low, close, volume]
│
├── technical_indicators
│   ├── rsi          { value, signal, period }
│   ├── macd         { macd_line, signal_line, histogram, crossover }
│   ├── bollinger    { upper, middle, lower, bandwidth, pct_b, signal }
│   ├── atr          { value, period, volatility_level }
│   └── trend        { ema_20, ema_50, sma_200, trend, golden_cross, death_cross }
│
└── news.by_category
    ├── thai_gold_market    ข่าวทองไทย
    ├── gold_price          ราคาทองโลก
    ├── geopolitics         ภูมิรัฐศาสตร์ / Safe Haven
    ├── dollar_index        ค่าเงินดอลลาร์ (DXY)
    ├── fed_policy          นโยบาย Fed
    └── usd_thb             ค่าเงิน USD/THB
        └── articles[]
            ├── title
            ├── url
            ├── published_at
            └── sentiment_score   (-1.0 ถึง +1.0)
```

**ใช้ต่ออย่างไร:**

| ผู้ใช้ | วิธีใช้ |
|---|---|
| **LLM Agent / Trading Bot** | โหลด `latest.json` ส่งเป็น context ให้ LLM ตัดสินใจ Buy/Sell/Hold ได้ทันที |
| **Dashboard / Monitoring** | อ่าน JSON แสดงผล real-time ราคา + indicator + news |
| **Backtesting** | ใช้ `payload_{timestamp}.json` ที่เก็บประวัติแต่ละ snapshot |

---

### Output 2 — `Data/features_master.csv`

**ใครสร้าง:** `extract_features.py` (อ่านจาก `latest.json`)  
**รูปแบบ:** CSV ตาราง flat (ML-ready)  
**Refresh:** Append 1 แถวต่อการรัน 1 ครั้ง ไม่ลบข้อมูลเก่า

**Columns:**

| กลุ่ม | Column | คำอธิบาย |
|---|---|---|
| **Time** | `datetime` | timestamp ที่เก็บข้อมูล |
| | `hour` | ชั่วโมง (0–23) |
| | `day_of_week` | 0=จันทร์, 6=อาทิตย์ |
| | `is_asian_session` | 1 ถ้าช่วง 07:00–15:00 ICT |
| | `is_london_session` | 1 ถ้าช่วง 15:00–23:00 ICT |
| | `is_ny_session` | 1 ถ้าช่วง 20:00–04:00 ICT |
| **Price** | `spot_price` | XAU/USD ราคา Spot |
| | `usd_thb` | อัตรา USD/THB |
| | `thai_gold_sell` | ราคาขายทองไทย (บาท) |
| **Indicators** | `rsi` | RSI-14 |
| | `macd_hist` | MACD Histogram |
| | `bollinger_pct_b` | %B ตำแหน่งในแถบ Bollinger |
| | `bollinger_bw` | Bandwidth ความกว้างแถบ |
| | `atr` | ATR-14 ความผันผวน |
| | `trend_encoded` | Uptrend=1, Sideways=0, Downtrend=-1 |
| | `ema_20` | EMA 20 วัน |
| | `sma_200` | SMA 200 วัน |
| **Sentiment** | `sentiment_thai_gold_market` | ค่าเฉลี่ย sentiment หมวดทองไทย |
| | `sentiment_gold_price` | หมวดราคาทองโลก |
| | `sentiment_geopolitics` | หมวดภูมิรัฐศาสตร์ |
| | `sentiment_dollar_index` | หมวดค่าเงินดอลลาร์ |
| | `sentiment_fed_policy` | หมวดนโยบาย Fed |

**ใช้ต่ออย่างไร:**

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

df = pd.read_csv("Data/features_master.csv")

X = df.drop(columns=["datetime", "target"])  # features ทั้งหมด
y = df["target"]                              # label ที่ทีม ML กำหนดเอง

model = RandomForestClassifier()
model.fit(X, y)
```

> **หมายเหตุ:** คอลัมน์ `target` (Buy/Sell/Hold) ยังไม่มีใน CSV — ทีม ML ต้องสร้างเองตาม logic ที่กำหนด

---

### Internal Cache — `cache/ohlcv_XAU_USD_{interval}.csv`

**ใครสร้าง:** `ohlcv_fetcher.py`  
**วัตถุประสงค์:** ลด API call ซ้ำ — โหลดครั้งต่อไปจะดึงแค่ข้อมูลที่หายไป  
**ใช้ต่อ:** ไม่ต้องแตะโดยตรง — `orchestrator.py` จัดการเอง

---

## ▶️ วิธีรัน

```bash
# รันทุกอย่างตามลำดับ
python conJSON.py          # → สร้าง latest.json + payload_{ts}.json
python extract_features.py # → append แถวใหม่ใน features_master.csv
```

**ตัวเลือกเพิ่มเติม (orchestrator โดยตรง):**

```bash
python orchestrator.py --interval 5m --history 30 --max-news 5
```

| Flag | Default | คำอธิบาย |
|---|---|---|
| `--interval` | `1d` | timeframe: 1m, 5m, 15m, 1h, 4h, 1d |
| `--history` | `90` | ย้อนหลังกี่วัน |
| `--max-news` | `5` | ข่าวสูงสุดต่อ category |

---

## 📊 ตัวอย่างข้อมูลล่าสุด (snapshot 2026-03-28 21:46 ICT)

| Field | Value | สถานะ |
|---|---|---|
| Spot Price | $4,507.71 / oz | — |
| USD/THB | 32.87 | — |
| Thai Gold (ขาย) | ฿70,150 | — |
| RSI-14 | 36.3 | Neutral |
| Trend | Downtrend | ⚠️ Death Cross |
| ATR | 138.81 | High Volatility |
| Sentiment (avg) | ~−0.85 | Negative |
| ข่าวทั้งหมด | 14 บทความ | — |

---

*สร้างโดย: Data Engine Team · อัปเดตล่าสุด 2026-03-28*
