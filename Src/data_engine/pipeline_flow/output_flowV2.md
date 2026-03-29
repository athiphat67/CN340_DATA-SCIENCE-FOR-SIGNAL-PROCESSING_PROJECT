# Output Flow — Gold Trading Agent (Data Engine)

เอกสารนี้อธิบาย output ทั้งหมดที่ Data Engine ผลิตออกมา เพื่อให้ทีม Agent Core รับรู้ว่ามีข้อมูลอะไรบ้าง ควรนำไปใช้อย่างไร และต้องระวังจุดใด

---

## 1. โครงสร้าง Pipeline

```
conJSON.py  (entry point)
    └── GoldTradingOrchestrator (orchestrator.py)
            ├── GoldDataFetcher (fetcher.py)
            │       └── OHLCVFetcher (ohlcv_fetcher.py)
            ├── TechnicalIndicators (indicators.py)
            └── GoldNewsFetcher (newsfetcher.py)
                        └── FinBERT via HuggingFace API
```

---

## 2. Output Files

### 2.1 JSON Payload (หลัก)

| Path | คำอธิบาย |
|---|---|
| `output/gold_data_{YYYYMMDD_HHMMSS}.json` | Payload ประจำ run นั้น (timestamp ชัดเจน) |
| `output/latest.json` | Payload ล่าสุดเสมอ (overwrite ทุก run) — **Agent Core ควรอ่านไฟล์นี้** |

> **หมายเหตุ:** `conJSON.py` บันทึกเฉพาะ timestamped file และ **ไม่** บันทึก `latest.json` (เพราะเรียก `save_to_file=False`) ส่วน `orchestrator.py` เมื่อรัน CLI จะบันทึกทั้งสองไฟล์

### 2.2 OHLCV Cache

| Path | คำอธิบาย |
|---|---|
| `data_engine/cache/ohlcv_XAU_USD_{interval}.csv` | แท่งเทียน OHLCV ที่ cache ไว้ ใช้ลด API call ในรอบถัดไป |

Cache จะถูก merge + update อัตโนมัติทุก run ไม่ต้องลบทิ้ง

---

## 3. โครงสร้าง JSON Payload

```
{
  meta                          ← ข้อมูล run นี้
  data_quality                  ← ⚠️ สำคัญมาก: คุณภาพข้อมูล + คำแนะนำสำหรับ LLM
  data_sources                  ← แหล่งที่มาของแต่ละข้อมูล
  market_data
    ├── spot_price_usd          ← ราคาทอง XAUUSD
    ├── forex                   ← อัตราแลกเปลี่ยน USD/THB
    ├── thai_gold_thb           ← ราคาทองไทย (บาท/บาทน้ำหนัก)
    └── recent_price_action     ← 5 แท่งเทียนล่าสุด
  technical_indicators          ← RSI, MACD, Bollinger, ATR, Trend
  news
    ├── summary                 ← ภาพรวม sentiment + จำนวนข่าว
    └── by_category             ← ข่าวแยกตามหมวด
}
```

---

## 4. รายละเอียด Field สำคัญ

### 4.1 `data_quality` — ⚠️ Agent Core ต้องอ่านก่อนเสมอ

```json
"data_quality": {
    "quality_score": "degraded" | "good",
    "is_weekend": true | false,
    "market_session": "closed" | "open",
    "warnings": ["...", "..."],
    "llm_instruction": "⚠️ DATA QUALITY DEGRADED: ..."
}
```

| Field | วิธีใช้งาน |
|---|---|
| `quality_score` | ถ้า `"degraded"` → ลด confidence ของ signal ลง, เพิ่มน้ำหนักข่าวแทน indicators |
| `is_weekend` | ถ้า `true` → ตลาด COMEX ปิด ราคาอาจ stale |
| `market_session` | `"closed"` = ห้ามส่ง signal ที่ต้องการ execution ทันที |
| `warnings` | list ของปัญหาทั้งหมด ควร log ไว้ใน trace |
| `llm_instruction` | **ใส่ตรงๆ ใน system prompt ได้เลย** |

**วิธีใช้ใน Prompt Builder:**
```python
data_quality = market_state.get("data_quality", {})
quality_warning = data_quality.get("llm_instruction", "Data quality normal.")
# นำ quality_warning ไปใส่ใน [DATA QUALITY NOTICE] section ของ system prompt
```

---

### 4.2 `market_data.spot_price_usd`

```json
{
    "source": "twelvedata" | "gold-api" | "yfinance",
    "price_usd_per_oz": 4507.71,
    "timestamp": "2026-03-29T06:03:07+07:00",
    "confidence": 0.972
}
```

| Field | วิธีใช้งาน |
|---|---|
| `confidence` | ≥ 0.9 = เชื่อถือได้, < 0.7 = ระวัง, = 0.0 = ห้ามใช้เทรด |
| `source` | `"yfinance"` คือ fallback สุดท้าย ความ real-time ต่ำกว่า |

---

### 4.3 `market_data.thai_gold_thb`

```json
{
    "source": "intergold.co.th" | "calculated (c=0.473)",
    "price_thb_per_baht_weight": 70417.75,
    "sell_price_thb": 70450,
    "buy_price_thb": 70350,
    "spread_thb": 100
}
```

| Field | วิธีใช้งาน |
|---|---|
| `source` | `"intergold.co.th"` = ราคาตลาดจริง (ดีกว่า), `"calculated"` = คำนวณจากสูตร (fallback) |
| `sell_price_thb` | ราคาที่ผู้ซื้อต้องจ่าย (entry point ถ้า BUY) |
| `buy_price_thb` | ราคาที่ผู้ขายได้รับ (entry point ถ้า SELL) |
| `spread_thb` | ปกติ 100 บาท ถ้ามากกว่านี้มากผิดปกติ |

---

### 4.4 `market_data.recent_price_action`

5 แท่งเทียนล่าสุด (เวลา timezone ไทย) ใช้ดู price action ระยะสั้นมาก

> **ข้อควรระวัง:** ถ้า `data_quality.warnings` มี "open เท่ากันทุกแท่ง" → ข้อมูลชุดนี้ stale ไม่ควรนำมาวิเคราะห์ momentum

---

### 4.5 `technical_indicators`

```json
{
    "rsi":       { "value": 46.82, "signal": "neutral"|"overbought"|"oversold", "period": 14 },
    "macd":      { "macd_line": -0.006, "signal_line": -0.001, "histogram": -0.005,
                   "crossover": "none"|"bullish_cross"|"bearish_cross" },
    "bollinger": { "upper": 4507.84, "middle": 4507.75, "lower": 4507.65,
                   "bandwidth": 0.000043, "pct_b": 0.24,
                   "signal": "inside"|"above_upper"|"below_lower" },
    "atr":       { "value": 0.21, "volatility_level": "low"|"normal"|"high" },
    "trend":     { "ema_20": 4507.74, "ema_50": 4507.74, "sma_200": 4507.74,
                   "trend": "uptrend"|"downtrend"|"sideways",
                   "golden_cross": false, "death_cross": false },
    "latest_close": 4507.69
}
```

**จุดสำคัญสำหรับ LLM:**

| Indicator | Signal ที่มีนัยสำคัญ | ข้อควรระวัง |
|---|---|---|
| RSI | ≥70 = overbought (พิจารณา SELL), ≤30 = oversold (พิจารณา BUY) | บน interval 5m มี noise สูง |
| MACD crossover | `bullish_cross` / `bearish_cross` = signal แรง | `"none"` คือไม่มี signal ใหม่ |
| Bollinger pct_b | <0 = ต่ำกว่า lower band, >1 = สูงกว่า upper band | bandwidth ต่ำมาก = ตลาด sideways |
| ATR | `"low"` = volatility ต่ำ ระวัง breakout หลอก | บน interval สั้นปกติจะ low |
| trend | `golden_cross=true` = long-term bullish | ถ้า EMA ทั้งหมดเท่ากัน → ดู `data_quality.warnings` |

> ⚠️ ถ้า `data_quality.warnings` มี "SMA200 คำนวณจากแท่งสั้น" → `trend` field ไม่ควรนำมาใช้ตัดสิน long-term direction

---

### 4.6 `news`

```json
"news": {
    "summary": {
        "total_articles": 5,
        "overall_sentiment": 0.0085,   // -1.0 (negative) ถึง +1.0 (positive)
        "token_estimate": 386,
        "errors": []
    },
    "by_category": {
        "geopolitics":    { "impact": "high",   "count": 2, "articles": [...] },
        "fed_policy":     { "impact": "high",   "count": 0, "articles": [] },
        "inflation":      { "impact": "high",   "count": 0, "articles": [] },
        "gold_price":     { "impact": "direct", "count": 2, "articles": [...] },
        "dollar_index":   { "impact": "medium", "count": 1, "articles": [...] },
        "usd_thb":        { "impact": "direct", "count": 0, "articles": [] },
        "thai_economy":   { "impact": "medium", "count": 0, "articles": [] },
        "thai_gold_market": { "impact": "direct", "count": 0, "articles": [] }
    }
}
```

**ลำดับความสำคัญของ impact:**
```
direct > high > medium
```

**วิธีอ่าน sentiment_score ต่อบทความ:**
- `+0.5 ถึง +1.0` = bullish สำหรับทอง
- `-0.5 ถึง -1.0` = bearish สำหรับทอง
- `0.0` = HuggingFace API timeout หรือ neutral จริงๆ — ดู `errors` ใน summary

> ⚠️ `sentiment_score = 0.0` ไม่ได้แปลว่า neutral เสมอไป อาจเกิดจาก API timeout ให้ดูที่ `news.summary.errors` ด้วย

---

## 5. สิ่งที่ควรนำไปทำต่อ (สำหรับ Agent Core)

### ✅ ทำได้เลย

1. **อ่าน `data_quality.llm_instruction`** → ใส่เข้า system prompt ใน `[DATA QUALITY NOTICE]` section
2. **ตรวจ `data_quality.quality_score`** → ถ้า `"degraded"` ให้ลด weight ของ technical indicators ลง และเพิ่ม weight ของ `news.summary.overall_sentiment` แทน
3. **ใช้ `spot_price_usd.confidence`** → กำหนด threshold เช่น ถ้า < 0.7 ให้ output confidence ของ signal ลดลงด้วย
4. **ใช้ `thai_gold_thb.sell_price_thb` / `buy_price_thb`** → เป็น entry price ที่ตรงกับตลาดไทยจริง

### ⚠️ ต้องระวัง

| สถานการณ์ | วิธีจัดการ |
|---|---|
| `is_weekend: true` | ลด confidence ของทุก signal ลง, แจ้ง user ว่าตลาดปิด |
| `volume = 0` ทุกแท่ง | ห้ามใช้ volume ในการตัดสินใจทุกกรณี |
| `news.summary.errors` ไม่ว่าง | บอก LLM ว่า sentiment อาจไม่สมบูรณ์ |
| `spot_price_usd.confidence = 0.0` | ห้าม execute signal จริง |
| `thai_gold_thb.source = "calculated"` | ราคาเป็นการประมาณ ไม่ใช่ราคาตลาดจริง |

---

## 6. ตัวอย่าง System Prompt Integration (สำหรับเพื่อน)

```python
# ใน PromptBuilder หรือที่ build system prompt
data_quality  = market_state.get("data_quality", {})
spot          = market_state.get("market_data", {}).get("spot_price_usd", {})
thai_gold     = market_state.get("market_data", {}).get("thai_gold_thb", {})

quality_notice = data_quality.get("llm_instruction", "Data quality normal.")
is_degraded    = data_quality.get("quality_score") == "degraded"
confidence_cap = 0.6 if is_degraded else 1.0  # cap confidence ถ้าข้อมูลแย่

system_prompt = f"""
คุณคือ AI Gold Trading Analyst วิเคราะห์ตลาดทองคำสำหรับนักลงทุนไทย

[DATA QUALITY NOTICE]
{quality_notice}
{"- ให้น้ำหนัก News/Fundamentals มากกว่า Technical Indicators ในการตัดสิน" if is_degraded else ""}
{"- ห้ามใช้ volume ในการวิเคราะห์" if "volume" in quality_notice else ""}

[PRICE REFERENCE]
ราคาทองไทยปัจจุบัน: ซื้อ ฿{thai_gold.get('buy_price_thb', 'N/A'):,} | ขาย ฿{thai_gold.get('sell_price_thb', 'N/A'):,}
ที่มาราคา: {thai_gold.get('source', 'unknown')} ({"ราคาตลาดจริง" if "intergold" in str(thai_gold.get('source','')) else "ราคาประมาณการ"})

[OUTPUT FORMAT]
...
"""
```

---

## 7. Dependency Summary

```
conJSON.py
    requires: orchestrator.py, thailand_timestamp.py
    output:   output/gold_data_{timestamp}.json

orchestrator.py
    requires: fetcher.py, indicators.py, newsfetcher.py, thailand_timestamp.py
    env vars: TWELVEDATA_API_KEY, HF_TOKEN
    output:   payload dict (JSON-serializable)

fetcher.py
    requires: ohlcv_fetcher.py, thailand_timestamp.py
    env vars: TWELVEDATA_API_KEY
    fallbacks: twelvedata → gold-api → yfinance (spot)
               exchangerate-api → yfinance (forex)
               intergold scraping → formula (thai gold)

ohlcv_fetcher.py
    requires: -
    env vars: TWELVEDATA_API_KEY
    fallbacks: TwelveData → yfinance → cache
    cache:    ./cache/ohlcv_XAU_USD_{interval}.csv

newsfetcher.py
    requires: thailand_timestamp.py
    env vars: HF_TOKEN
    fallbacks: yfinance metadata → RSS feeds
               HuggingFace API (FinBERT sentiment, อาจ timeout)
```

---

*อัปเดตล่าสุด: 2026-03-29 | Data Engine v1.1.0*
