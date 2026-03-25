# SKILL.md — Gold Trading Agent Tool Registry
# อ่านไฟล์นี้ก่อนทุกครั้งที่ต้องการข้อมูลเพิ่มเติม
# LLM จะเห็นไฟล์นี้เมื่อ orchestrator ตัดสินใจว่าต้องใช้ tool

---

## วิธีใช้ไฟล์นี้
เมื่อคุณต้องการเรียกใช้ tool ใด ๆ ให้ตอบกลับเป็น JSON ในรูปแบบนี้เท่านั้น:

```json
{
  "thought": "อธิบายว่าทำไมถึงต้องการ tool นี้",
  "action": "CALL_TOOL",
  "tool_name": "<ชื่อ tool>",
  "tool_args": { "<key>": "<value>" }
}
```

ห้ามคำนวณตัวเลขด้วยตัวเอง ให้สั่ง tool เสมอ

---

## รายการ Tools ที่ใช้ได้

---

### tool: get_news
**วัตถุประสงค์**: ดึงพาดหัวข่าวล่าสุดที่เกี่ยวกับทองคำ, เศรษฐกิจ, หรือนโยบายการเงิน
**ไฟล์ที่รัน**: `get_news.py`

**Arguments**:
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|-----------|
| keywords | list[str] | ✅ | คำค้นหา เช่น ["gold", "FED", "inflation"] |
| max_results | int | ❌ | จำนวนข่าวสูงสุด (default: 5) |
| language | str | ❌ | ภาษา: "en" หรือ "th" (default: "en") |

**ตัวอย่างการเรียกใช้**:
```json
{
  "thought": "RSI ต่ำแต่ไม่รู้ว่าข่าว macro เป็นยังไง ต้องเช็คก่อนตัดสินใจ",
  "action": "CALL_TOOL",
  "tool_name": "get_news",
  "tool_args": {
    "keywords": ["FED interest rate", "gold price", "inflation"],
    "max_results": 5,
    "language": "en"
  }
}
```

**Output ที่จะได้รับ**:
```json
{
  "tool": "get_news",
  "status": "success",
  "results": [
    {
      "headline": "Fed signals rate cut in Q3 2025",
      "source": "Reuters",
      "sentiment": "bullish",
      "published_at": "2025-03-25T06:30:00Z"
    }
  ],
  "composite_sentiment": 0.72,
  "dominant_theme": "monetary_policy"
}
```

---

### tool: get_macro_indicators
**วัตถุประสงค์**: ดึงตัวเลขเศรษฐกิจมหภาค เช่น DXY, US10Y Yield, CPI
**ไฟล์ที่รัน**: `get_macro.py` *(Phase 1 tool)*

**Arguments**:
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|-----------|
| indicators | list[str] | ✅ | เช่น ["DXY", "US10Y", "CPI", "VIX"] |

**ตัวอย่าง**:
```json
{
  "thought": "ต้องเช็ค DXY และ yield ก่อน เพราะทองแพงขึ้นผิดปกติ",
  "action": "CALL_TOOL",
  "tool_name": "get_macro_indicators",
  "tool_args": {
    "indicators": ["DXY", "US10Y", "VIX"]
  }
}
```

---

### tool: get_gold_price
**วัตถุประสงค์**: ดึงราคาทองล่าสุด พร้อม RSI, MACD, Bollinger
**ไฟล์ที่รัน**: `get_price.py` *(Phase 1 tool)*

**Arguments**:
| ชื่อ | ประเภท | บังคับ | คำอธิบาย |
|------|--------|--------|-----------|
| timeframe | str | ❌ | "1h", "4h", "1d" (default: "1h") |
| indicators | list[str] | ❌ | ["RSI", "MACD", "BB"] |

**ตัวอย่าง**:
```json
{
  "thought": "ต้องการ RSI กรอบ 4 ชั่วโมงเพื่อยืนยัน signal",
  "action": "CALL_TOOL",
  "tool_name": "get_gold_price",
  "tool_args": {
    "timeframe": "4h",
    "indicators": ["RSI", "MACD"]
  }
}
```

---

## กฎการตัดสินใจขั้นสุดท้าย (Final Decision Rules)

เมื่อข้อมูลครบแล้ว ให้ตอบกลับในรูปแบบนี้เท่านั้น:

```json
{
  "thought": "สรุปเหตุผลการตัดสินใจ",
  "action": "FINAL_DECISION",
  "signal": "BUY | SELL | HOLD",
  "confidence": 0.0,
  "entry_price": 0.0,
  "stop_loss": 0.0,
  "take_profit": 0.0,
  "rationale": "อธิบายเป็นภาษาที่อ่านง่าย",
  "key_factors": ["factor1", "factor2"]
}
```

**เงื่อนไขบังคับ**:
- `confidence` ต้องอยู่ระหว่าง 0.0 ถึง 1.0
- `signal` ต้องเป็นหนึ่งใน: `BUY`, `SELL`, `HOLD` เท่านั้น
- `entry_price`, `stop_loss`, `take_profit` ต้องเป็นตัวเลขเสมอ (ใส่ 0 ถ้า HOLD)
- ห้ามใส่ข้อความอื่นนอกจาก JSON

---

## ลำดับความสำคัญของสัญญาณ

| ลำดับ | สัญญาณ | น้ำหนัก |
|-------|--------|---------|
| 1 | ข่าว FED / นโยบายการเงิน | สูงมาก |
| 2 | DXY (ค่าเงินดอลลาร์) | สูง |
| 3 | RSI + MACD | ปานกลาง |
| 4 | VIX (ความผันผวน) | ปานกลาง |
| 5 | ข่าวภูมิรัฐศาสตร์ | ปานกลาง |
| 6 | Bollinger Bands | ต่ำ |