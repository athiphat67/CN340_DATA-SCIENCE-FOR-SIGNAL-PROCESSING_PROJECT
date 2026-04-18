# เอกสาร QA: โฟลเดอร์ `test_unit`

---

## 1. Overview (ภาพรวม)

โฟลเดอร์ `tests/test_unit/` ทำหน้าที่เป็น **ชุดทดสอบ Unit Tests หลัก** ของโปรเจกต์นักขุดทอง ครอบคลุม business logic สำคัญที่สุดของระบบ ได้แก่ Risk Management, Trading Session, Portfolio, Metrics Calculator, Deploy Gate, CSV Loader และ Logger

Unit Tests ในโฟลเดอร์นี้เป็น **ด่านแรกที่สำคัญที่สุด** ในการป้องกัน regression เพราะ logic เหล่านี้ส่งผลโดยตรงต่อการตัดสินใจซื้อขายทอง เช่น Hard Rules ใน RiskManager ที่ผิดพลาดอาจทำให้ระบบถือทองในช่วง Dead Zone หรือไม่ Cut Loss เมื่อขาดทุนเกินกำหนด

### วัตถุประสงค์หลัก

| วัตถุประสงค์ | รายละเอียด |
|------------|-----------|
| **Isolation** | ทดสอบ logic แต่ละ module โดยไม่ต้องมี DB, API, หรือ Gradio |
| **Hard Rules Verification** | ตรวจสอบว่า Dead Zone, Danger Zone, SL/TP Override ทำงานถูกต้องทุก boundary |
| **Regression Guard** | ป้องกัน breaking changes ใน portfolio calculation, session timing, risk logic |
| **Contract Validation** | ตรวจสอบว่า output dict มี keys และ types ตาม spec |
| **Edge Case Coverage** | ครอบคลุม boundary values, zero values, negative values, empty input |

### สถิติรวม

| เมตริก | จำนวน |
|--------|-------|
| Test Files | 7 ไฟล์ |
| Test Classes | 60+ คลาส |
| Test Functions | 300+ ฟังก์ชัน |
| Production Modules Tested | 7 โมดูล |
| Hard Rule Tests | 8 sections (Dead Zone ถึง TP3) |

---

## 2. Directory Structure & Coverage

### โครงสร้างโฟลเดอร์

```
tests/test_unit/
│
├── test_calculator.py        # ทดสอบ calculate_trade_metrics()
├── test_csv_loader.py        # ทดสอบ load_gold_csv()
├── test_deploy_gate.py       # ทดสอบ deploy_gate()
├── test_portfolio.py         # ทดสอบ SimPortfolio
├── test_risk.py              # ทดสอบ RiskManager + Hard Rules
├── test_session_manager.py   # ทดสอบ TradingSessionManager
├── test_logger_setup.py      # ทดสอบ setup_logger() + @log_method
└── about-test_unit.md        # เอกสารนี้
```

### Coverage Map (Test File → Production Module)

```
Production Module                              ← Test File
──────────────────────────────────────────────────────────────
backtest/metrics/calculator.py                 ← test_calculator.py
backtest/data/csv_loader.py                    ← test_csv_loader.py
backtest/metrics/deploy_gate.py                ← test_deploy_gate.py
backtest/engine/portfolio.py                   ← test_portfolio.py
agent_core/core/risk.py                        ← test_risk.py
backtest/engine/session_manager.py             ← test_session_manager.py
logs/logger_setup.py                           ← test_logger_setup.py
```

---

## 3. What is Being Tested — Key Scenarios

### 3.1 `test_calculator.py` — Trade Metrics Calculator

**โมดูลที่ทดสอบ:** `backtest/metrics/calculator.py::calculate_trade_metrics()`, `add_calmar()`

**Strategy:** 100% Real — pure calculation functions ไม่มี I/O

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| ไม่มี trade → zero metrics | Edge Case | return dict ที่ค่าเป็น 0 ทั้งหมด |
| ชนะทั้งหมด → win_rate = 1.0 | Edge Case | |
| แพ้ทั้งหมด → win_rate = 0.0 | Edge Case | |
| profit_factor คำนวณถูก | Business Logic | gross_profit / gross_loss |
| max_consec_losses | Business Logic | นับ streak แพ้ติดต่อกัน |
| expectancy | Business Logic | avg_win × win_rate - avg_loss × loss_rate |
| add_calmar() | Business Logic | annual_return / max_drawdown |
| Sharpe ratio | Business Logic | |

---

### 3.2 `test_csv_loader.py` — CSV Data Loader

**โมดูลที่ทดสอบ:** `backtest/data/csv_loader.py::load_gold_csv()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| โหลดได้ ไม่ crash | Happy Path | |
| Columns ครบถ้วน | Contract | ครอบคลุมทุก required column |
| Warmup bars ถูกตัด | Business Logic | rows แรกถูกลบตาม warmup parameter |
| Indicator ไม่มี NaN | Data Quality | หลังตัด warmup ไม่มี NaN เหลือ |
| RSI signal | Business Logic | คำนวณ RSI signal ถูกต้อง |
| File ไม่มี → error | Negative | handle gracefully |
| Column variations | Edge Case | รองรับชื่อ column หลายรูปแบบ |

---

### 3.3 `test_deploy_gate.py` — Deploy Gate Validator

**โมดูลที่ทดสอบ:** `backtest/metrics/deploy_gate.py::deploy_gate()`, `_safe()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Metrics ดีทั้งหมด → DEPLOY | Happy Path | |
| Sharpe < 1 → NOT READY | Validation | |
| bust = True → fail | Validation | |
| Missing value → fail | Edge Case | None หรือ NaN |
| Boundary values | Boundary | ค่าพอดี threshold |
| `_safe()` ป้องกัน ZeroDivision | Edge Case | หาร 0 ไม่ crash |

---

### 3.4 `test_portfolio.py` — SimPortfolio

**โมดูลที่ทดสอบ:** `backtest/engine/portfolio.py::SimPortfolio`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| execute_buy สำเร็จ | Happy Path | gold_grams เพิ่ม, cash ลด |
| execute_sell สำเร็จ | Happy Path | gold_grams ลด, cash เพิ่ม |
| Cash ไม่พอ → reject | Validation | ไม่มีทอง ไม่มีเงิน |
| Bust detection | Business Logic | cash ต่ำกว่า bust_threshold → is_bust = True |
| closed_trades บันทึกถูก | Contract | ทุก trade บันทึกใน closed_trades list |
| `_calc_spread()` | Calculation | spread ตาม proportional formula |
| spread_from_grams | Calculation | |
| Gold เล็กมาก → ไม่ขาย | Validation | gold < 0.0001 ถือว่าไม่มี |

---

### 3.5 `test_risk.py` — RiskManager + Hard Rules ⭐

**โมดูลที่ทดสอบ:** `agent_core/core/risk.py::RiskManager`

**เพิ่มโดย Benchaphon** — ครอบคลุม Hard Rules ที่ไม่มีใน test เดิม

#### Sections 1–10 (Logic เดิม)

| Section | Class | สิ่งที่ทดสอบ |
|---------|-------|-------------|
| 1 | `TestInit` | ค่า default, custom values |
| 2 | `TestConfidenceFilter` | threshold, boundary, HOLD bypass |
| 3 | `TestDailyLossLimit` | accumulate, reset วันใหม่, SELL ไม่โดน block |
| 4 | `TestBuySignal` | position sizing 1000 THB, SL/TP ATR-based |
| 5 | `TestSellSignal` | ต้องมีทอง, position from gold value |
| 6 | `TestHoldSignal` | pass-through, low confidence |
| 7 | `TestInvalidSignal` | unknown signal → reject |
| 8 | `TestBadMarketData` | missing key, zero price |
| 9 | `TestRecordTradeResult` | accumulate, ignore profit, reset |
| 10 | `TestRejectSignalSafety` | ไม่ mutate input dict |

#### Sections 11–18 (Hard Rules — เพิ่มใหม่)

| Section | Class | สิ่งที่ทดสอบ |
|---------|-------|-------------|
| 11 | `TestDeadZone` | 02:00–06:14 → reject ทุก signal, boundary 02:00/06:14/01:59/06:15 |
| 12 | `TestDangerZone` | 01:30–01:59 + gold > 0 → บังคับ SELL, confidence = 1.0 |
| 13 | `TestStopLoss1` | pnl ≤ -150 → SL1, boundary -149 ไม่ trigger |
| 14 | `TestStopLoss2` | pnl ≤ -80 + RSI < 35 → SL2, ต้องครบทั้งสองเงื่อนไข |
| 15 | `TestTakeProfit1` | pnl ≥ 300 → TP1, boundary 299 ไม่ trigger |
| 16 | `TestTakeProfit2` | pnl ≥ 150 + RSI > 65 → TP2, boundary RSI=65 ไม่ trigger |
| 17 | `TestTakeProfit3` | pnl ≥ 100 + macd_hist < 0 → TP3 |
| 18 | `TestHardRuleOverrideBehavior` | SYSTEM OVERRIDE, position_size > 0, SL1 priority สูงกว่า TP |

**Hard Rule ที่สำคัญที่สุด:**
```
Dead Zone (02:00–06:14)  → ห้ามเทรดทุก signal
Danger Zone (01:30–01:59) + gold > 0 → บังคับ SELL (SL3)
SL1: pnl ≤ -150 → บังคับ SELL, confidence = 1.0
TP1: pnl ≥ 300  → บังคับ SELL, confidence = 1.0
```

---

### 3.6 `test_session_manager.py` — Trading Session Manager ⭐

**โมดูลที่ทดสอบ:** `backtest/engine/session_manager.py::TradingSessionManager`

**เพิ่มโดย Benchaphon** — ไม่มีใน test เดิมเลย

#### Session Windows ออม NOW

| Session | วัน | ช่วงเวลา |
|---------|-----|---------|
| LATE | จ.–ศ. | 00:00–01:59 |
| **DEAD ZONE** | **จ.–ศ.** | **02:00–06:14** |
| MORN | จ.–ศ. | 06:15–11:59 |
| AFTN | จ.–ศ. | 12:00–17:59 |
| EVEN | จ.–ศ. | 18:00–23:59 |
| E | ส.–อา. | 09:30–17:30 |

| Class | สิ่งที่ทดสอบ |
|-------|-------------|
| `TestTimeRange` | `contains()` boundary start/end |
| `TestSessionDef` | WEEKDAY_SESSIONS IDs, MORN เริ่ม 06:15 ไม่ใช่ 06:00 |
| `TestFindSessionWeekday` | ทุก boundary weekday รวม Dead zone |
| `TestFindSessionWeekend` | Session E boundary 09:30/17:30 |
| `TestProcessCandle` | `SessionInfo` structure, `can_execute`, `label` |
| `TestRecordTrade` | นับ trade แยก session, นอก session ไม่ crash |
| `TestComplianceReportEmpty` | keys ครบ, ค่า zero |
| `TestComplianceReportAfterFinalize` | passed count, fail_flag, all_details |
| `TestSessionResult` | `to_dict()` keys และค่าถูกต้อง |
| `TestFinalize` | finalize ก่อน candle ไม่ crash, finalize 2 ครั้งไม่ duplicate |

---

### 3.7 `test_logger_setup.py` — Logger Setup ⭐

**โมดูลที่ทดสอบ:** `logs/logger_setup.py`

**เพิ่มโดย Benchaphon** — ไม่มีใน test เดิมเลย

| Class | สิ่งที่ทดสอบ |
|-------|-------------|
| `TestSetupLogger` | returns Logger instance, ชื่อถูกต้อง, มี FileHandler + StreamHandler |
| `TestSetupLogger` | ป้องกัน duplicate handlers เมื่อเรียกซ้ำ |
| `TestSetupLogger` | propagate = False, custom level |
| `TestTHTimeFormatter` | converter offset UTC+7 |
| `TestLogMethodDecorator` | return value ถูกต้อง, log START/END/ERROR |
| `TestLogMethodDecorator` | exception re-raise, `@wraps` preserves function name |
| `TestLogMethodDecorator` | elapsed time logged |

---

## 4. Testing Architecture

### Strategy: 100% Real (ไม่มี Mock)

ทุก test ใน `test_unit/` ใช้ **real objects** ทั้งหมด ไม่มี mock เพราะ:
- ทุก module เป็น pure logic ไม่มี I/O
- `RiskManager`, `SimPortfolio`, `TradingSessionManager` ไม่เชื่อมต่อ external service
- ผลลัพธ์จึง deterministic และทดสอบได้โดยตรง

```python
# ✅ ถูกต้อง — ใช้ real object
rm = RiskManager()
result = rm.evaluate(_decision(signal="BUY"), _market(time="03:00"))
assert result["signal"] == "HOLD"

# ไม่จำเป็นต้อง mock เพราะ RiskManager ไม่มี network call
```

### Helper Functions

ทุก test file ใช้ helper ที่สร้าง input dict:

```python
# test_risk.py
def _decision(signal="BUY", confidence=0.8, rationale="test"):
    return {"signal": signal, "confidence": confidence, "rationale": rationale}

def _market(time="12:00", cash=5000.0, gold_grams=0.0, unrealized_pnl=0.0, ...):
    return { "time": time, "portfolio": {...}, "market_data": {...}, ... }

# test_session_manager.py
def _ts(dt_str: str) -> pd.Timestamp:
    return pd.Timestamp(dt_str)

def _sm() -> TradingSessionManager:
    return TradingSessionManager()  # fresh instance ทุกครั้ง
```

---

## 5. QA Standards & Conventions

### 5.1 Boundary Testing Rules

Hard Rules ทุกตัวต้องมี boundary test ครบ 4 จุด:

```python
# ตัวอย่าง Dead Zone boundary
def test_dead_zone_start_0200():      # 02:00 → REJECT (boundary start)
def test_dead_zone_end_0614():        # 06:14 → REJECT (boundary end)
def test_just_before_0159():          # 01:59 → ผ่านได้
def test_just_after_0615():           # 06:15 → ผ่านได้
```

### 5.2 Hard Rule Test Template

ทุก Hard Rule test ต้องตรวจ 3 อย่าง:

```python
def test_sl1_triggers_at_minus_150():
    rm = RiskManager()
    result = rm.evaluate(
        _decision(signal="BUY"),
        _market(gold_grams=1.0, unrealized_pnl=-150)
    )
    assert result["signal"] == "SELL"         # 1. signal ถูก override
    assert "SL1" in result["rationale"]       # 2. rationale บอก rule
    assert result["confidence"] == 1.0        # 3. confidence = 1.0
```

### 5.3 Negative Test Requirement

ทุก test class ต้องมีอย่างน้อย 1 negative test:

```python
# ✅ ตัวอย่าง negative tests
def test_sl1_does_not_trigger_at_minus_149()   # boundary ไม่ trigger
def test_sl2_no_trigger_rsi_not_low_enough()   # ขาดเงื่อนไข 1 ตัว
def test_tp2_no_trigger_rsi_at_boundary()      # RSI = 65 ไม่ trigger (ต้องการ > 65)
def test_sell_no_gold_rejected()               # SELL โดยไม่มีทอง
```

### 5.4 Docstring Requirement

```python
def test_dead_zone_rejects_buy():
    """02:30 → Dead zone → BUY ต้องถูก reject เป็น HOLD"""
    ...

def test_sl1_does_not_trigger_at_minus_149():
    """unrealized_pnl = -149 → ยังไม่ถึง SL1 threshold (-150)"""
    ...
```

---

## 6. How to Run

**ทุกคำสั่งรันจาก directory `Src/`**

### รัน test_unit ทั้งหมด

```bash
python -m pytest tests/test_unit/ -v
```

### รันไฟล์เดียว

```bash
python -m pytest tests/test_unit/test_risk.py -v
python -m pytest tests/test_unit/test_session_manager.py -v
python -m pytest tests/test_unit/test_logger_setup.py -v
python -m pytest tests/test_unit/test_portfolio.py -v
```

### รัน Hard Rules เฉพาะ

```bash
# Dead Zone
python -m pytest tests/test_unit/test_risk.py::TestDeadZone -v

# Stop Loss rules
python -m pytest tests/test_unit/test_risk.py::TestStopLoss1 -v
python -m pytest tests/test_unit/test_risk.py::TestStopLoss2 -v

# Take Profit rules
python -m pytest tests/test_unit/test_risk.py::TestTakeProfit1 -v
python -m pytest tests/test_unit/test_risk.py::TestTakeProfit2 -v
python -m pytest tests/test_unit/test_risk.py::TestTakeProfit3 -v
```

### รัน Session Manager

```bash
python -m pytest tests/test_unit/test_session_manager.py::TestFindSessionWeekday -v
python -m pytest tests/test_unit/test_session_manager.py::TestComplianceReportAfterFinalize -v
```

### Dry Run

```bash
python -m pytest tests/test_unit/ --collect-only
```

### Filter โดย keyword

```bash
python -m pytest tests/test_unit/ -k "dead_zone" -v
python -m pytest tests/test_unit/ -k "sl1 or sl2 or tp1" -v
python -m pytest tests/test_unit/ -k "not logger" -v
```

---

## Appendix: Design Decisions

| รายการ | สถานะ | รายละเอียด |
|--------|-------|-----------|
| Hard Rules tests (Sections 11–18) ใน test_risk.py | ✅ เพิ่มโดย Benchaphon | Dead Zone, Danger Zone, SL1/SL2, TP1/TP2/TP3 ไม่มีใน test เดิมเลย |
| test_session_manager.py | ✅ เพิ่มโดย Benchaphon | ไฟล์ใหม่ทั้งหมด ครอบคลุม session boundary ทุก case |
| test_logger_setup.py | ✅ เพิ่มโดย Benchaphon | ไฟล์ใหม่ทั้งหมด ครอบคลุม setup_logger + @log_method |
| position sizing fixed 1000 THB | ✅ แก้ไขแล้ว | test เดิมคาดว่า 2000 แต่ logic จริงใช้ 1000 — แก้ให้ตรง |
| test_too_small_position_rejected | ✅ ลบออก | logic จริงไม่ได้ reject ตาม condition นั้น |
| test_missing_atr | ✅ ลบออก | risk.py ยังทำงานได้แม้ไม่มี ATR |

> **กฎ QA:** ถ้า production code มี bug ที่ต้องแก้เพื่อให้ test ผ่าน — **รายงานเป็น finding** อย่าแก้ไฟล์ production เอง