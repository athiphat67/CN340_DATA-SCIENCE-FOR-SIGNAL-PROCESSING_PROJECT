# STRATEGY.md — Gold Trading Agent
## เอกสาร Reference สำหรับทีม: เงื่อนไขการเทรด, Logic, Tool Analysis และ Data Flow

---

## สารบัญ

- [ภาพรวม Architecture](#ภาพรวม-architecture)
- [Signal Logic: BUY / SELL / HOLD](#signal-logic-buy--sell--hold)
- [Hard Rules (Override System)](#hard-rules-override-system)
- [Session Rules](#session-rules)
- [Confidence Threshold](#confidence-threshold)
- [TP / SL Logic](#tp--sl-logic)
- [Technical Analysis Tools](#technical-analysis-tools)
- [Fundamental Analysis Tools](#fundamental-analysis-tools)
- [Internal Tools (Orchestrator)](#internal-tools-orchestrator)
- [Tool Scoring System](#tool-scoring-system)
- [Tool Pipeline & Data Flow](#tool-pipeline--data-flow)
- [Data Quality Handling](#data-quality-handling)

---

## ภาพรวม Architecture

```
Market Data (fetch_price + fetch_indicators + fetch_news)
        ↓
   market_state (dict รวม)
        ↓
  ReAct LLM Loop — เรียก analysis_tools ตามต้องการ
        ↓
   RiskManager.evaluate()  ← Hard Rules อยู่ที่นี่
        ↓
  final_decision (signal, confidence, entry, SL, TP)
        ↓
  Dashboard + Notification (Discord / Telegram)
```

---

## Signal Logic: BUY / SELL / HOLD

### สัญญาณ BUY
LLM ประเมินจากหลายเงื่อนไขพร้อมกัน ไม่ใช่ข้อใดข้อหนึ่ง:

| เงื่อนไข | ค่า | Tool ที่ใช้ตรวจ |
|---|---|---|
| RSI | < 35 (Oversold) | `fetch_indicators` |
| MACD Histogram | เปลี่ยนจากลบเป็นบวก | `fetch_indicators` |
| Bollinger Band | ราคาต่ำกว่า Lower Band | `check_bb_rsi_combo` |
| HTF Trend | Bullish (ราคา > EMA200) | `get_htf_trend` |
| Breakout | Confirmed Upward | `detect_breakout_confirmation` |
| RSI Divergence | Bullish Divergence | `detect_rsi_divergence` |
| Swing Low | Setup + Confirmation | `detect_swing_low` |
| Economic Calendar | risk_level = low/medium | `check_upcoming_economic_calendar` |
| Intermarket | Gold-DXY สวนทางปกติ | `get_intermarket_correlation` |
| ETF Flow | SPDR inflow | `get_gold_etf_flow` |

### สัญญาณ SELL
| เงื่อนไข | ค่า | Tool ที่ใช้ตรวจ |
|---|---|---|
| RSI | > 65 (Overbought) | `fetch_indicators` |
| MACD Histogram | เปลี่ยนจากบวกเป็นลบ | `fetch_indicators` |
| Bollinger Band | ราคาสูงกว่า Upper Band | `fetch_indicators` |
| HTF Trend | Bearish (ราคา < EMA200) | `get_htf_trend` |
| Spot-THB | Strong Bearish | `check_spot_thb_alignment` |
| Economic Calendar | risk_level = critical/high | `check_upcoming_economic_calendar` |
| ETF Flow | SPDR outflow | `get_gold_etf_flow` |

### สัญญาณ HOLD
เกิดขึ้นเมื่อ:
- Indicators ขัดแย้งกัน (ไม่ consensus)
- Confidence < 0.6
- อยู่ใน Dead Zone (02:00–06:14)
- Economic Calendar risk_level = critical
- Weighted Score รวม < 0.4

---

## Hard Rules (Override System)

Hard Rules มีอำนาจสูงสุด — **override คำสั่ง LLM ทันที**

### ด่าน 0 — Hard Rules (ตรวจก่อนทุกอย่าง)

| Rule | เงื่อนไข | Action | Confidence |
|---|---|---|---|
| **Dead Zone** | `02:00 ≤ time ≤ 06:14` | REJECT ทุก signal | — |
| **Danger Zone (SL3)** | `01:30 ≤ time ≤ 01:59` + gold > 0 | บังคับ SELL | 1.0 |
| **SL1** | pnl ≤ -150 THB + gold > 0 | บังคับ SELL | 1.0 |
| **SL2** | pnl ≤ -80 THB + RSI < 35 + gold > 0 | บังคับ SELL | 1.0 |
| **TP1** | pnl ≥ 300 THB + gold > 0 | บังคับ SELL | 1.0 |
| **TP2** | pnl ≥ 150 THB + RSI > 65 + gold > 0 | บังคับ SELL | 1.0 |
| **TP3** | pnl ≥ 100 THB + MACD hist < 0 + gold > 0 | บังคับ SELL | 1.0 |

### ด่าน 1 — Confidence Filter
- signal ≠ HOLD และ confidence < 0.6 → reject เป็น HOLD

### ด่าน 2 — Daily Loss Limit
- `daily_loss ≥ 500 THB` → block BUY เท่านั้น (SELL ยังผ่าน)

### ด่าน 3 — Signal Execution
- **HOLD** → pass-through
- **SELL** → ต้องมี gold_grams > 0.0001
- **BUY** → ต้องมี cash ≥ 1,000 THB

---

## Session Rules

### วันจันทร์–ศุกร์ (ออม NOW)

| Session | เวลา | เทรดได้ | min_trades |
|---|---|---|---|
| LATE | 00:00–01:59 | ✅ | 1 |
| **DEAD ZONE** | **02:00–06:14** | **❌** | — |
| MORN | 06:15–11:59 | ✅ | 2 |
| AFTN | 12:00–17:59 | ✅ | 2 |
| EVEN | 18:00–23:59 | ✅ | 2 |

> ⚠️ **06:15 เท่านั้น** ถึงเปิด — 06:14 ยังเป็น Dead Zone

### วันเสาร์–อาทิตย์

| Session | เวลา | เทรดได้ | min_trades |
|---|---|---|---|
| E | 09:30–17:30 | ✅ | 2 |
| นอกเวลา | อื่นๆ | ❌ | — |

---

## Confidence Threshold

| ระดับ | ค่า | ความหมาย |
|---|---|---|
| ต่ำกว่า threshold | < 0.60 | Reject → HOLD |
| Moderate | 0.60–0.74 | เทรดได้ position เล็ก |
| Strong | 0.75–0.84 | Signal ชัดเจน |
| Very Strong | ≥ 0.85 | Signal แข็งมาก |
| Hard Rule Override | 1.00 | ระบบบังคับ |

### Weighted Voting
```
weighted_score(signal) = Σ(confidence × weight) / total_weight
max weighted_score < 0.4 → HOLD อัตโนมัติ
```

| Interval | Weight | หมายเหตุ |
|---|---|---|
| 1m | 3% | Noisy |
| 5m | 5% | Day trading |
| 15m | 10% | Decent |
| 30m | 15% | Good |
| 1h | 22% | Sweet spot |
| 4h | 30% | Strong |
| 1d | 12% | Trend |
| 1w | 3% | Long-term |

---

## TP / SL Logic

### ATR-Based (BUY ปกติ)
```
SL  = entry - (ATR × 2.0)
TP  = entry + (ATR × 2.0 × 1.5)

ตัวอย่าง: entry=45,000 ATR=150
  SL = 44,700 | TP = 45,450
```

### Hard Rule TP/SL (Override ราคา THB)

| Rule | Trigger | หมายเหตุ |
|---|---|---|
| SL1 | pnl ≤ -150 | Cut loss ทันที |
| SL2 | pnl ≤ -80 + RSI < 35 | Momentum breakdown |
| SL3 | Danger Zone + มีทอง | ปิดก่อนตลาดหยุด |
| TP1 | pnl ≥ 300 | Take profit เต็ม |
| TP2 | pnl ≥ 150 + RSI > 65 | Overbought |
| TP3 | pnl ≥ 100 + MACD hist < 0 | Momentum reverse |

---

## Technical Analysis Tools

### การใช้งานร่วมกัน (Suggested Flow)
```
1. get_htf_trend              → กำหนด Bias หลัก (Bullish/Bearish)
2. check_spot_thb_alignment   → เช็ก Macro Alignment เสริมหรือหักล้าง
3. get_support_resistance_zones → หาโซนสำคัญ
4. detect_swing_low           → ยืนยัน Structure กลับตัว
   + detect_rsi_divergence    → ยืนยัน Momentum ซ้ำ
5. check_bb_rsi_combo         → เช็ก Oversold Entry
   + calculate_ema_distance   → ยืนยันไม่ Overextended
6. detect_breakout_confirmation → กรอง Fakeout ตอนราคาทะลุโซน
```

---

### 1. `get_htf_trend`

**วิเคราะห์อะไร:**
ตรวจสอบ **เทรนด์หลัก (Macro Bias)** ของตลาดโดยเทียบราคาปิดล่าสุดกับ EMA-200 ใน Timeframe ใหญ่ (`1h`, `4h`, `1d`)

**Logic:**
```
trend = "Bullish"  → close > EMA_200
trend = "Bearish"  → close < EMA_200
distance_pct = ((close - EMA_200) / EMA_200) × 100
```

**สัญญาณที่ได้:**

| Output | ความหมาย | Action ที่แนะนำ |
|---|---|---|
| `Bullish` + distance ≥ 1.5% | เทรนด์ขาขึ้นชัดเจน | เน้นหา BUY setup เท่านั้น |
| `Bullish` + distance < 1.5% | ขาขึ้นแต่ใกล้ EMA อาจ consolidate | รอยืนยันจาก tool อื่น |
| `Bearish` + distance ≥ 1.5% | เทรนด์ขาลงชัดเจน | เน้นหา SELL หรืองดเทรด BUY |
| `Bearish` + distance < 1.5% | ขาลงแต่ใกล้ EMA อาจกลับตัว | รอยืนยัน |

> ⚡ **Cache 30 นาที** ต่อ timeframe — ลด API calls ใน ReAct loop
> ⚠️ ต้องการ ≥ 200 candles: `1h` ใช้ 15 วัน, `4h` ใช้ 45 วัน, `1d` ใช้ 300 วัน

**Parameters:** `timeframe` (`"1h"`, `"4h"`, `"1d"`), `history_days`, `ohlcv_df`

---

### 2. `check_spot_thb_alignment`

**วิเคราะห์อะไร:**
เปรียบเทียบทิศทาง **XAU/USD (ทองโลก)** กับ **USD/THB (อัตราแลกเปลี่ยน)** พร้อมกัน เพราะราคาทองไทย = XAU/USD × USD/THB

**Logic:**
```
คำนวณ % Change ย้อนหลัง lookback_candles แท่ง:
  ทองโลก ↑ + USD/THB ↑ (บาทอ่อน) → "Strong Bullish"
  ทองโลก ↓ + USD/THB ↓ (บาทแข็ง) → "Strong Bearish"
  ทองโลก ↑ + USD/THB ↓            → "Neutral (Spot Leading)"
  ทองโลก ↓ + USD/THB ↑            → "Neutral (THB Leading)"
```

**สัญญาณที่ได้:**

| alignment | ความหมาย | ผลต่อทองไทย |
|---|---|---|
| `Strong Bullish` | แรงดันขึ้น 2 ทาง | โอกาสทะลุแนวต้านสูง เหมาะ BUY |
| `Strong Bearish` | แรงกดลง 2 ทาง | โอกาสหลุดแนวรับสูง เหมาะ SELL |
| `Neutral (Spot Leading)` | ทองขึ้นแต่บาทแข็งหักล้าง | ราคาไทยขึ้นช้า ระวัง False Signal |
| `Neutral (THB Leading)` | บาทอ่อนแต่ทองลงหักล้าง | ราคาไทยไม่ชัด รอ Alignment |

**Parameters:** `interval`, `lookback_candles` (default 4), `df_spot`, `df_thb`

---

### 3. `get_support_resistance_zones`

**วิเคราะห์อะไร:**
ค้นหาโซนแนวรับ-แนวต้านที่ **มีนัยสำคัญทางสถิติ** ด้วย DBSCAN Clustering บน Swing Highs/Lows

**Logic:**
```
1. คำนวณ ATR-14 → ค่าความผันผวนปัจจุบัน
2. Adaptive EPS = ATR × 0.7  (clamp: ATR×0.3 ถึง ATR×3.0)
3. หา Swing Highs/Lows ด้วย find_peaks + prominence = ATR×1.5
4. DBSCAN Clustering → รวมจุดใกล้กันเป็นโซน
5. แบ่งประเภทโซนตามตำแหน่งเทียบกับราคาปัจจุบัน
```

**สัญญาณที่ได้:**

| zone type | ความหมาย | Action |
|---|---|---|
| `Resistance` | โซนอยู่ **เหนือ** ราคา | เฝ้าระวังการทะลุ ถ้าทะลุ → BUY breakout |
| `Support` | โซนอยู่ **ใต้** ราคา | เฝ้าระวังการหลุด ถ้าหลุด → SELL breakdown |
| `In-Range (Testing Zone)` | ราคากำลัง **อยู่ในโซน** | รอดูทิศทางก่อน ไม่ควรเปิดออเดอร์ |

| strength | touches | ความน่าเชื่อถือ |
|---|---|---|
| `High` | ≥ 4 | แนวรับ/ต้านแข็งแกร่งมาก |
| `Medium` | 3 | น่าเชื่อถือพอสมควร |
| `Low` | 2 | อ่อนแอ ควรใช้ร่วม tool อื่น |

> Adaptive EPS ทำให้โซนยืดหยุ่นตามตลาด ช่วงผันผวนสูงโซนจะกว้างขึ้นตามธรรมชาติ

**Parameters:** `interval`, `history_days` (default 5), `ohlcv_df`

---

### 4. `detect_swing_low`

**วิเคราะห์อะไร:**
สแกนย้อนหลังเพื่อหาโครงสร้าง **V-shape Reversal** ที่ได้รับการยืนยันแล้ว — ราคาทำจุดต่ำสุด แล้วพุ่งทะลุ High ของแท่ง Swing นั้น

**Logic:**
```
สแกนจากปัจจุบันย้อนอดีต:
  1. หาแท่ง i ที่: low[i] < low[i-1]  AND  low[i] < low[i+1]  → Swing Low
  2. หาแท่ง j (j > i) ที่: close[j] > high[i]                 → Confirmation
  3. เจอคู่แรก (ใกล้ปัจจุบันที่สุด) → หยุดสแกน
```

**สัญญาณที่ได้:**

| setup_detected | ความหมาย | Action |
|---|---|---|
| `true` | มีโครงสร้าง Bullish Reversal ชัดเจน | เป็น Entry BUY ที่มีคุณภาพ ควรยืนยันด้วย S/R zone |
| `false` | ยังไม่มีโครงสร้างกลับตัว | รอต่อ อย่าเร่งเข้า |

> ใช้คู่กับ `get_support_resistance_zones` เพื่อยืนยันว่า Swing Low เกิดบนแนวรับจริง
> และ `detect_rsi_divergence` เพื่อยืนยัน Momentum ซ้ำ

**Parameters:** `interval`, `history_days` (default 3), `lookback_candles` (default 15), `ohlcv_df`

---

### 5. `detect_rsi_divergence`

**วิเคราะห์อะไร:**
ตรวจหา **RSI Bullish Divergence** — ราคาทำ Low ใหม่แต่ RSI ยกตัวขึ้น แสดงว่าแรงขายกำลังอ่อนลง

**Logic:**
```
หา Trough 2 จุดล่าสุดด้วย find_peaks(-low, prominence=ATR×1.0):
  idx1 = ก้นเหวอดีต  (Low1, RSI1)
  idx2 = ก้นเหวปัจจุบัน (Low2, RSI2)

Bullish Divergence = Low2 < Low1  AND  RSI2 > RSI1
(ราคาต่ำกว่า แต่ RSI สูงกว่า = momentum ถดถอย)
```

**สัญญาณที่ได้:**

| divergence_detected | logic | ความหมาย |
|---|---|---|
| `true` | "Price lower but RSI higher" | แรงขายหมด Early Warning กลับตัว |
| `false` | "Price and RSI aligned" | ไม่มีสัญญาณพิเศษ ให้ดู tool อื่น |

> สัญญาณนี้มักปรากฏ **ก่อน** Swing Low จะ Confirm 1–3 แท่ง — เป็น Early Warning
> ควรใช้คู่กับ `detect_swing_low` เพื่อยืนยันซ้อนกัน 2 ชั้น

**Parameters:** `interval`, `history_days` (default 5), `lookback_candles` (default 30), `ohlcv_df`

---

### 6. `check_bb_rsi_combo`

**วิเคราะห์อะไร:**
ตรวจว่าเกิด **Oversold Triple Combo** พร้อมกันทั้ง 3 เงื่อนไขหรือไม่

**Logic:**
```
is_price_low    = close < lower_bb                          (ราคาต่ำกว่า BB ล่าง)
is_rsi_oversold = rsi_14 < 35.0                             (RSI Oversold)
is_macd_flatten = |macd_hist| < (ATR × 0.05)               (MACD กำลังแบน)
                  OR macd_hist กำลังเพิ่มขึ้น              (Momentum กำลังกลับ)

combo_detected = ทั้งสาม True พร้อมกัน
```

**สัญญาณที่ได้:**

| combo_detected | ความหมาย | Action |
|---|---|---|
| `true` | Oversold หนักพร้อม Momentum ชะลอ | Setup BUY ที่ดี ควรหา Entry |
| `false` | ยังไม่ครบทุกเงื่อนไข | รอหรือใช้ tool อื่นแทน |

> ⚠️ ไม่ควรใช้คนเดียว ควรตรวจ `get_support_resistance_zones` ว่าราคาอยู่บนแนวรับจริงด้วย

**Parameters:** `interval`, `history_days` (default 5), `ohlcv_df`

---

### 7. `calculate_ema_distance`

**วิเคราะห์อะไร:**
วัดว่าราคา **ห่างจาก EMA-20 มากแค่ไหน** โดย normalize ด้วย ATR เพื่อให้เทียบได้ข้ามช่วงเวลา

**Logic:**
```
distance = (close - EMA_20) / ATR_14

is_overextended = |distance| > 5.0
```

**สัญญาณที่ได้:**

| distance_atr_ratio | ความหมาย | Action |
|---|---|---|
| บวกสูง > +5 | ราคาสูงกว่า EMA มากผิดปกติ (แพงเกิน) | ระวัง Mean Reversion ลง ไม่เพิ่ม BUY |
| ลบสูง < -5 | ราคาต่ำกว่า EMA มากผิดปกติ (ถูกเกิน) | โอกาส BUY แต่รอยืนยัน |
| ใกล้ 0 (±2) | ราคาใกล้ EMA ปกติ | ไม่มีสัญญาณ Mean Reversion |
| `is_overextended: true` | ห่าง EMA > 5 ATR | อย่าตามราคา รอดีดกลับ |

**Parameters:** `interval`, `history_days` (default 5), `ohlcv_df`

---

### 8. `detect_breakout_confirmation`

**วิเคราะห์อะไร:**
รับ Zone (บน-ล่าง) แล้ววิเคราะห์ว่าการทะลุโซนนั้น **จริง (Confirmed)** หรือ **หลอก (Fakeout)** ดูจากสัดส่วนแท่งเทียน

**Logic:**
```
body_pct = |close - open| / (high - low) × 100

Confirmed Breakout ขาขึ้น:
  - close > zone_top
  - body_pct ≥ 50%  (แท่งแรง ไม่ใช่ไส้ยาว)
  - upper_wick ≤ body_size  (ไม่โดนตบลง)

Confirmed Breakdown ขาลง:
  - close < zone_bottom
  - body_pct ≥ 50%
  - lower_wick ≤ body_size  (ไม่โดนงัดขึ้น)

Doji สมบูรณ์ (high == low) → is_confirmed_breakout: false ทันที
```

**สัญญาณที่ได้:**

| is_confirmed_breakout | breakout_direction | Action |
|---|---|---|
| `true` | `Upward (Resistance Breakout)` | BUY breakout ได้ (ไม่ใช่ Fakeout) |
| `true` | `Downward (Support Breakdown)` | SELL breakdown ได้ |
| `false` | — | Fakeout หรือยังอยู่ในโซน รอต่อ |

> ทองไทยมัก Fakeout บ่อยช่วงตลาดบาง (เช้าก่อนยุโรปเปิด) tool นี้ช่วยกรอง

**Parameters:** `zone_top`, `zone_bottom`, `interval`, `history_days` (default 3), `ohlcv_df`

---

## Fundamental Analysis Tools

### 9. `get_deep_news_by_category`

**วิเคราะห์อะไร:**
ดึงข่าวและ sentiment ตามหมวดหมู่ที่สนใจ เพื่อให้ LLM เข้าใจ **ว่าทำไม** ราคาถึงขยับ

**Logic:**
```
เรียก fetch_news(category=..., detail_level="deep")
→ กรองข่าวตาม category
→ คำนวณ sentiment_score (-1.0 ถึง +1.0) ต่อบทความ
→ เฉลี่ย sentiment ต่อ category
```

**สัญญาณที่ได้:**

| count | score ของ scorer | ความหมาย |
|---|---|---|
| 0 บทความ | 0.2 (floor) | ไม่มีข้อมูล ข้ามหมวดนี้ไป |
| 1–2 บทความ | 0.5 | น้อย ข้อมูลอาจไม่ครบ |
| 3–4 บทความ | 0.7 | พอใช้ |
| ≥ 5 บทความ | 0.85 | ครบถ้วน ใช้ประกอบการตัดสินใจได้ดี |

**หมวดหมู่ที่รองรับ:**

| category | ใช้เมื่อ |
|---|---|
| `gold_price` | ต้องการข่าวราคาทองโดยตรง |
| `fed_policy` | ใกล้ประชุม FOMC หรือ Fed speaker |
| `inflation` | ใกล้ประกาศ CPI / PCE |
| `geopolitics` | มีเหตุการณ์ความไม่สงบโลก |
| `dollar_index` | DXY เคลื่อนไหวผิดปกติ |
| `usd_thb` | ค่าเงินบาทผันผวน |
| `thai_gold_market` | ต้องการ context ตลาดทองไทยโดยเฉพาะ |
| `thai_economy` | ข่าวเศรษฐกิจไทยกระทบบาท |

> ⚠️ ดึงได้เฉพาะข่าว **ปัจจุบัน** เท่านั้น ไม่สามารถดึงข่าวย้อนหลังได้

**Parameters:** `category` (string จากรายการด้านบน)

---

### 10. `check_upcoming_economic_calendar`

**วิเคราะห์อะไร:**
เช็คปฏิทินเศรษฐกิจล่วงหน้าจาก ForexFactory เพื่อหา **ข่าวกล่องแดง (High Impact)** ที่จะทำให้ตลาดสวิงรุนแรง

**Logic:**
```
ดึง ForexFactory JSON → กรองสกุลเงิน (USD, EUR, GBP, JPY, CNY, CHF)
→ กรองเฉพาะ events ภายใน hours_ahead ชั่วโมง
→ จัดระดับ risk:

  critical: High USD ≤ 2 ชม.    → ห้ามเทรด!
  high:     High USD ใน window   → ลด/งด position
  medium:   Medium หรือ High อื่น → ระวัง volatility
  low:      ไม่มีข่าวสำคัญ       → เทรดตาม technical ได้
```

**สัญญาณที่ได้:**

| risk_level | score | Action |
|---|---|---|
| `critical` | 1.0 | **ห้ามเทรด** ปิดออเดอร์ที่มีก่อนข่าวออก |
| `high` | 0.8 | งดเปิดออเดอร์ใหม่ หรือใช้ SL แน่นขึ้น |
| `medium` | 0.5 | เทรดได้แต่ลด position size |
| `low` | 0.2 | ปลอดภัย เทรดตาม technical ตามปกติ |

**ข่าวสำคัญที่ต้องระวัง:** NFP, CPI, PCE, FOMC Meeting, GDP, Retail Sales

**Parameters:** `hours_ahead` (default 24)

---

### 11. `get_intermarket_correlation`

**วิเคราะห์อะไร:**
ตรวจความสัมพันธ์ระหว่าง Gold, DXY และ US10Y เพื่อหา **Divergence ที่ผิดปกติ** ซึ่งกราฟทองอย่างเดียวบอกไม่ได้

**Logic:**
```
ดึง yfinance: GC=F (Gold), DX-Y.NYB (DXY), ^TNX (US10Y)
→ คำนวณ % Change 1d และ 5d
→ คำนวณ Pearson Correlation 20 วัน (daily % return)
→ ตรวจ Divergence:

  ปกติ  : Gold ↑ + DXY ↓ (สวนทาง)   → "normal"
  ผิดปกติ: Gold ↑ + DXY ↑ (ทิศเดียว) → "bearish_warning"
  ผิดปกติ: Gold ↓ + DXY ↓ (ทิศเดียว) → "bullish_warning"
```

**สัญญาณที่ได้:**

| divergence status | correlation | ความหมาย | Action |
|---|---|---|---|
| `bearish_warning` | > +0.3 | ทองขึ้นผิดปกติ ไม่มีพื้นฐานรองรับ | ระวัง Reversal ลง ลด BUY |
| `bullish_warning` | > +0.3 | ทองลงผิดปกติ อาจเกิด Short Squeeze | โอกาส Reversal ขึ้น |
| `normal` | -0.3 ถึง -0.8 | สวนทางตามทฤษฎี | Intermarket สนับสนุนเทรนด์ |
| `flat` | ใกล้ 0 | ทั้งคู่นิ่ง ตลาดไม่มีทิศ | รอ Catalyst |

**Parameters:** ไม่มี (ดึงข้อมูลอัตโนมัติ)

---

### 12. `get_gold_etf_flow`

**วิเคราะห์อะไร:**
ดูว่า **สถาบันการเงินใหญ่** กำลังสะสมหรือเทขายทองผ่าน SPDR Gold Trust (GLD) — กองทุนทองที่ใหญ่ที่สุดในโลก (~1,050 ตัน)

**Logic:**
```
Layer 1 (Primary): SPDR XLSX
  → ดู Total Ounces in Trust เปลี่ยนแปลงรายวัน
  → oz_change > +1,000  → "inflow" (สถาบันสะสม)
  → oz_change < -1,000  → "outflow" (สถาบันเทขาย)
  → |oz_change| ≤ 1,000 → "flat" (neutral)

Layer 2 (Fallback): yfinance GLD
  → Volume ratio = today / avg_10d
  → Volume > 2x + ราคาขึ้น → "likely_inflow"
  → Volume > 2x + ราคาลง  → "likely_outflow"
```

**สัญญาณที่ได้:**

| flow_direction | institutional_signal | ความหมาย | Action |
|---|---|---|---|
| `inflow` | `accumulating` | สถาบันสะสมทอง | Bullish ระยะกลาง-ยาว เสริม BUY |
| `outflow` | `distributing` | สถาบันเทขาย | Bearish ระวัง SELL pressure |
| `flat` | `neutral` | ไม่มีการเคลื่อนไหวสถาบัน | ใช้ technical เป็นหลัก |
| `likely_inflow` (fallback) | `likely_accumulating` | Volume spike + ราคาขึ้น | น่าจะมี inflow แต่ไม่ยืนยัน |

> Cache XLSX 12 ชั่วโมง — ข้อมูลอัปเดตรายวัน ถือเป็น Medium-term signal

**Parameters:** ไม่มี (ดึงข้อมูลอัตโนมัติ)

---

## Internal Tools (Orchestrator)

Tools เหล่านี้ **LLM ไม่เห็น** — ใช้โดย Orchestrator เพื่อสร้าง `market_state`

### `fetch_price`
```
Input:  history_days (default 90), interval (default "5m")
Output: spot_price_usd, thai_gold_thb, recent_price_action (5 แท่งล่าสุด),
        ohlcv_df (ส่งต่อให้ fetch_indicators ได้)
```

### `fetch_indicators`
```
Input:  interval, days, ohlcv_df (รับจาก fetch_price ได้)
Output: indicators {rsi, macd, bollinger, atr, trend, ema},
        data_quality {quality_score, warnings, llm_instruction}
```

### `fetch_news`
```
Input:  max_per_category, category_filter, detail_level
Output: by_category {articles[], sentiment_scores}
```

---

## Tool Scoring System

`ToolResultScorer` ประเมินคุณภาพ tool output ก่อนส่งเข้า LLM

| Tool | Score เต็ม | เงื่อนไข |
|---|---|---|
| `detect_breakout_confirmation` | 0.85–0.95 | confirmed = True, body ≥ 70% → +0.10 |
| `check_bb_rsi_combo` | 0.85 | combo_detected = True |
| `detect_rsi_divergence` | 0.85 | divergence = True |
| `get_support_resistance_zones` | 0.6–0.9 | ราคาใกล้ zone ± 1 ATR |
| `get_htf_trend` | 0.5–0.75 | distance ≥ 1.5% → 0.75, < 1.5% → 0.5 |
| `check_spot_thb_alignment` | 0.85 | Strong Bullish/Bearish |
| `check_upcoming_economic_calendar` | 1.0/0.8/0.5/0.2 | ตาม risk_level |
| `get_deep_news_by_category` | 0.2–0.85 | ตามจำนวน articles |
| `get_intermarket_correlation` | 0.75–1.0 | ตาม divergence warnings |
| ทุก tool (error) | 0.0 | status = "error" |
| ทุก tool (ไม่มี signal) | 0.2 | FLOOR_SCORE |

### Proceed Threshold
```
avg_score ≥ 0.6  → should_proceed = True  → ส่ง LLM
avg_score < 0.6  → Retry Loop (max 3 rounds) → call tools เพิ่มตาม recommendations
```

---

## Tool Pipeline & Data Flow

### ohlcv_df Pass-Through (ประหยัด API calls)
```
fetch_price()
  └─ ohlcv_df → fetch_indicators(ohlcv_df=...)
              └─ ohlcv_df → ทุก Group A tools (detect_breakout, get_sr_zones, ฯลฯ)
```
> ⚡ ถ้าไม่ส่ง ohlcv_df แต่ละ tool จะ fetch ใหม่เองทำให้ช้าและใช้ quota มาก

### market_state (Input ของ RiskManager)
```python
{
  "time": "HH:MM",
  "date": "YYYY-MM-DD",
  "portfolio": {
    "cash_balance": float,
    "gold_grams": float,
    "unrealized_pnl": float,
  },
  "market_data": {
    "thai_gold_thb": {
      "sell_price_thb": float,   # ร้านขายให้เรา (เราซื้อ)
      "buy_price_thb": float,    # ร้านรับซื้อจากเรา (เราขาย)
    },
    "forex": {"usd_thb": float},
    "spot_price_usd": {"price_usd_per_oz": float},
  },
  "technical_indicators": {
    "rsi":      {"value": float},
    "macd":     {"histogram": float},
    "atr":      {"value": float, "unit": "THB"},
    "bollinger":{"pct_b": float, "bandwidth": float},
    "trend":    {"trend": str, "ema_20": float, "sma_200": float},
  },
  "news": {"by_category": {...}}
}
```

### final_decision (Output ของ RiskManager)
```python
{
  "signal":            "BUY" | "SELL" | "HOLD",
  "confidence":        float,        # 0.0–1.0
  "entry_price":       float,        # THB
  "stop_loss":         float,        # THB
  "take_profit":       float,        # THB
  "position_size_thb": float,        # 1000 สำหรับ BUY
  "rationale":         str,
  "rejection_reason":  str | None,
}
```

---

## Data Quality Handling

| Level | ความหมาย | LLM Instruction |
|---|---|---|
| `good` | ข้อมูลครบถ้วน | Use standard technical analysis |
| `degraded` | ข้อมูลบางส่วนขาด | เพิ่ม weight ข้อมูลที่มี |
| Weekend | ตลาดปิด เสาร์-อาทิตย์ | Weigh news higher than short-term indicators |

### Fallback Chain

```
fetch_price / fetch_indicators:
  Yahoo Finance → TwelveData → error (degraded)

get_gold_etf_flow:
  SPDR XLSX (cache 12h) → yfinance GLD → error

check_upcoming_economic_calendar:
  ForexFactory JSON → error (ไม่มี fallback)

LLM Provider:
  Primary → FallbackChainClient (ตาม chain) → mock
```

---

## Tools ที่ยังไม่ Implement

| Tool | เหตุผล |
|---|---|
| `check_fed_speakers_schedule` | ไม่มี free API real-time, ข้อมูลมีใน `get_deep_news_by_category("fed_policy")` แล้ว |
| `get_institutional_positioning` | COT Report ออกรายสัปดาห์ ช้าเกินไป ใช้ `get_gold_etf_flow` แทนได้ |
| `check_volatility` | return ค่า hardcoded รอ implement จริง |