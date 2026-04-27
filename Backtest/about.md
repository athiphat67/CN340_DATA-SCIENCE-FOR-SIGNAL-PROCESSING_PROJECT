# Backtest Module — Walk-Forward Backtest
> **อัปเดต:** 2026-04-25

---

## 1. ภาพรวม

Walk-Forward Backtest สำหรับระบบ **Nakkhutthong Framework** — ทดสอบประสิทธิภาพของ AI Trading Signal ย้อนหลังตั้งแต่ **ม.ค. 2568 ถึงปัจจุบัน** โดยแบ่งการทดสอบออกเป็น 4 รอบตามที่อาจารย์กำหนด

```
CSV ราคาทอง (5m) → คำนวณ Indicators → Signal Engine (Rule/Mistral)
→ SimPortfolio จำลองการซื้อขาย → คำนวณ Metrics → วิเคราะห์ Variation
```

---

## 2. โครงสร้างไฟล์

```
Backtest/
├── walk_forward_backtest.py   ← Script หลัก
├── output/
│   └── walk_forward_results.json  ← ผลลัพธ์ทั้ง 4 รอบ
└── about.md                   ← เอกสารนี้
```

---

## 3. Walk-Forward Windows (Expanding Window)

| รอบ | Train | Test | ฤดูกาล |
|-----|-------|------|--------|
| 1 | ม.ค.68 – ธ.ค.68 | **ม.ค. 69** | ต้นปี นักลงทุนเปิด position ใหม่ |
| 2 | ม.ค.68 – ม.ค.69 | **ก.พ. 69** | วาเลนไทน์ / ทองคำเป็นของขวัญ |
| 3 | ม.ค.68 – ก.พ.69 | **มี.ค. 69** | ปิดเทอม / สิ้นไตรมาส |
| 4 | ม.ค.68 – มี.ค.69 | **เม.ย. 69** | สงกรานต์ / เปิดเทอม |

**วิธี Expanding Window** — Train data ขยายขึ้นทุกรอบ เพื่อลด gap ระหว่าง Train กับ Test และสอดคล้องกับระบบที่เรียนรู้สะสมไปเรื่อย ๆ

---

## 4. Data Leak Prevention

ป้องกัน Look-ahead bias ด้วยการ `shift(1)` ทุก indicator ก่อนใช้งาน

```python
# ทุก indicator ถูก shift(1) — candle ปัจจุบันรู้ได้เฉพาะข้อมูลที่ผ่านมา
indicator_cols = ["rsi", "macd_line", "macd_hist", "ema_20", "ema_50", ...]
for col in indicator_cols:
    df[col] = df[col].shift(1)
```

นอกจากนี้ยังแบ่ง Train/Test อย่างเคร่งครัด — Scaler และ Indicator ถูก fit บน Train data เท่านั้น

---

## 5. Signal Engine — 3 Modes

```bash
# Rule-based อย่างเดียว (เร็ว เหมาะทดสอบ pipeline)
python walk_forward_backtest.py --mode rule

# Rule กรองก่อน แล้วส่งให้ Mistral API ตัดสินใจ (แนะนำ)
python walk_forward_backtest.py --mode smart

# เรียก Mistral API ทุก candle (ช้า แต่ใช้ AI จริงทั้งหมด)
python walk_forward_backtest.py --mode api
```

### Rule-based Logic
| สัญญาณ | เงื่อนไข (3 ใน 4 ต้องเป็นจริง) |
|--------|-------------------------------|
| BUY | RSI < 45, MACD Hist > 0, Close > EMA20, EMA20 > EMA50 |
| SELL | RSI > 55, MACD Hist < 0, Close < EMA20, EMA20 < EMA50 |
| HOLD | ไม่ผ่านเงื่อนไขข้างต้น |

### Mistral API (Smart Mode)
- Rule-based กรอง candle ที่น่าสนใจก่อน
- เฉพาะ BUY_CANDIDATE / SELL_CANDIDATE เท่านั้นที่ส่งให้ Mistral ตัดสินใจขั้นสุดท้าย
- Fallback เป็น Rule hint อัตโนมัติถ้า API timeout

---

## 6. SimPortfolio

จำลองการซื้อขายทองตามระบบจริงของโปรเจค

| ค่าคงที่ | ค่า | ความหมาย |
|---------|-----|----------|
| `INITIAL_CASH` | 1,500 THB | เงินเริ่มต้น (ตามที่อาจารย์กำหนด) |
| `BUST_THRESHOLD` | 1,000 THB | ต่ำกว่านี้หยุดทันที |
| `SPREAD_THB` | 0 THB | ฮั่วเซ่งเฮงออกให้ |
| `COMMISSION_THB` | 0 THB | SCB EASY ฟรี |
| `GOLD_GRAM_PER_BAHT` | 15.244 g | กรัมต่อ 1 บาทน้ำหนัก |

---

## 7. Metrics ที่คำนวณ

ครอบคลุมทุก Parameter ที่อาจารย์กำหนด:

| Metric | คำอธิบาย |
|--------|---------|
| Total Closed Trade | จำนวนดีลที่ปิดแล้ว |
| Win Rate (%) | สัดส่วนดีลที่กำไร |
| Total Profit (THB) | กำไรรวมทั้งหมด |
| Average Win/Loss (THB) | เฉลี่ยกำไร/ขาดทุนต่อดีล |
| Expectancy per Trade | คาดหวังกำไรต่อดีล |
| Profit Factor | กำไรรวม / ขาดทุนรวม |
| Best/Worst/Median Annualized | ผลตอบแทนรายปีแต่ละดีล |
| XIRR | Internal Rate of Return แบบ irregular cashflow |
| Max Drawdown (%) | การขาดทุนสูงสุดจากจุดสูงสุด |
| Sharpe Ratio | ผลตอบแทนเทียบความเสี่ยง |
| Calmar Ratio | Annualized Return / MDD |

---

## 8. ผลลัพธ์ที่ได้ (Rule Mode)

| เดือน | Trades | Win Rate | กำไร/ขาดทุน | MDD |
|-------|--------|----------|------------|-----|
| ม.ค. 69 | 131 | 35.11% | **+64.28 THB** ✅ | -3.05% |
| ก.พ. 69 | 124 | 34.68% | **+24.17 THB** ✅ | -3.62% |
| มี.ค. 69 | 136 | 27.21% | **-69.59 THB** ❌ | -7.08% |
| เม.ย. 69 | 65 | 32.31% | **-11.03 THB** ❌ | -2.28% |

### การวิเคราะห์ Variation
- **Variation = 133.87 THB** (8.9% ของเงินต้น)
- **ม.ค.–ก.พ. กำไร** — ตลาดต้นปีมีทิศทางชัดเจน
- **มี.ค. ขาดทุนสูงสุด** — Win Rate ตกจาก 35% → 27% ช่วงปิดเทอม/สิ้นไตรมาส ตลาดผันผวน
- **เม.ย. Trade น้อยลงครึ่งนึง** — ช่วงสงกรานต์ตลาดเบาบาง

---

## 9. ข้อมูลที่ใช้

| ไฟล์ | รายละเอียด |
|------|-----------|
| `GLD965_5m_20250101_to_20260416.csv` | ราคาทอง 96.5% ระดับ 5 นาที ตั้งแต่ ม.ค.68 – เม.ย.69 |

---

## 10. วิธีรัน

```bash
cd Backtest

# ทดสอบด้วย Rule-based (เร็ว)
python walk_forward_backtest.py --mode rule

# ทดสอบด้วย Mistral AI (แนะนำ)
python walk_forward_backtest.py --mode smart

# กำหนด CSV และ output เอง
python walk_forward_backtest.py \
  --csv ../Src/backtest/data/MarketState_data/GLD965_5m_20250101_to_20260416.csv \
  --output output/ \
  --mode rule
```
