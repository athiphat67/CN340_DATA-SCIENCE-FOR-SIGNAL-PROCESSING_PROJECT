# เอกสาร QA: โฟลเดอร์ `test_ui`

---

## 1. Overview (ภาพรวม)

โฟลเดอร์ `tests/test_ui/` ทำหน้าที่เป็น **ชุดทดสอบของชั้น UI Layer** ในโปรเจกต์นักขุดทอง ครอบคลุม Services, Renderers, และ Utility functions ที่ Dashboard Gradio ใช้งาน

ชั้น UI Layer แบ่งออกเป็น 3 ส่วนหลัก ได้แก่ **Services** (business logic สำหรับ UI), **Renderers** (สร้าง HTML output), และ **Utils** (helper functions) โดยทั้งหมดถูกออกแบบให้ **ไม่มี business logic อยู่ใน Gradio component โดยตรง** ทำให้ทดสอบได้โดยไม่ต้อง launch Gradio จริง

### วัตถุประสงค์หลัก

| วัตถุประสงค์ | รายละเอียด |
|------------|-----------|
| **Isolation** | ทดสอบ Services/Renderers/Utils โดยไม่ต้อง launch Gradio หรือเชื่อมต่อ DB จริง |
| **Contract Validation** | ตรวจสอบว่า HTML output มี content ที่ถูกต้อง และ Service return dict ตาม structure ที่คาดหวัง |
| **Regression Guard** | ป้องกัน breaking changes ใน `_normalize_provider()`, `calculate_weighted_vote()`, portfolio validation |
| **Edge Case Coverage** | ครอบคลุมกรณี empty input, DB error, None value, negative values |
| **Mock Strategy** | ใช้ `MagicMock` สำหรับ DB — ไม่มี network call หรือ DB call จริงในชุดทดสอบ |

### สถิติรวม

| เมตริก | จำนวน |
|--------|-------|
| Test Files | 3 ไฟล์ |
| Test Classes | 25 คลาส |
| Test Functions | 168 ฟังก์ชัน |
| Production Modules Tested | 3 โมดูล (`services.py`, `renderers.py`, `utils.py`) |
| Mock Instances | DB mock ทุก test ใน services |

---

## 2. Directory Structure & Coverage

### โครงสร้างโฟลเดอร์

```
tests/test_ui/
│
├── test_ui_utils.py       # ทดสอบ pure functions ใน ui/core/utils.py
├── test_ui_renderers.py   # ทดสอบ HTML renderer classes ใน ui/core/renderers.py
├── test_ui_services.py    # ทดสอบ Services layer ใน ui/core/services.py
└── about-test_ui.md       # เอกสารนี้
```

### Coverage Map (Test File → Production Module)

```
Production Module                     ← Test File
────────────────────────────────────────────────────────
ui/core/utils.py                      ← test_ui_utils.py
ui/core/renderers.py                  ← test_ui_renderers.py
ui/core/services.py                   ← test_ui_services.py
```

---

## 3. What is Being Tested — Key Scenarios

### 3.1 `test_ui_utils.py` — Pure Utility Functions

**โมดูลที่ทดสอบ:** `ui/core/utils.py`

**Strategy:** 100% Real — ไม่มี mock เพราะทุก function เป็น pure function (รับ input → คืน output ตรงๆ ไม่มี side effects)

#### `calculate_weighted_vote()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Input ว่าง → HOLD | Edge Case | return HOLD + error key |
| Single BUY interval | Happy Path | final = BUY |
| Majority BUY wins | Business Logic | weighted score BUY สูงสุด → BUY |
| Low confidence → HOLD | Business Logic | weighted score < 0.4 → HOLD |
| Keys ครบใน output | Contract | final_signal, weighted_confidence, voting_breakdown, interval_details |
| voting_breakdown มีครบ 3 signals | Contract | BUY, SELL, HOLD keys ต้องมีทุกตัว |
| Unknown interval ถูกข้าม | Edge Case | ไม่ crash, ไม่นับ weight |
| confidence อยู่ 0-1 | Boundary | weighted_confidence ไม่เกิน 1.0 |
| count นับถูกต้อง | Business Logic | BUY 2 intervals → count = 2 |
| Only unknown intervals | Edge Case | total_weight = 0 → error |

#### `format_voting_summary()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Return string | Contract | ต้องเป็น str |
| มี final signal | Contract | BUY/SELL/HOLD ปรากฏใน output |
| มี confidence | Contract | ตัวเลข % ปรากฏ |
| มี interval details | Contract | ชื่อ interval ปรากฏ |
| Vote Tally section | Format | มี header "Vote Tally" หรือ "VOTING" |
| Empty breakdown ไม่ crash | Edge Case | dict ว่าง → ไม่ crash |

#### `format_error_message()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| validation error | Format | มีคำว่า "Validation" + error message |
| api_failure | Format | มีคำว่า "API" หรือ "Attempt" + attempt number |
| general error | Format | มีคำว่า "Error" + message |
| Missing error_type → general | Fallback | default เป็น general |

#### `strength_indicator()` / `confidence_bar()` / `signal_recommendation()`

| Function | Scenario | รายละเอียด |
|----------|----------|-----------|
| `strength_indicator` | 0.9+ → Very Strong | boundary ถูกต้อง |
| `strength_indicator` | 0.75–0.89 → Strong | |
| `confidence_bar` | มี % | "70%" ปรากฏใน output |
| `confidence_bar` | มี bar characters | █ หรือ ░ |
| `signal_recommendation` | BUY ≥ 0.8 → Strong BUY | |
| `signal_recommendation` | HOLD → มีคำ HOLD | |

#### `calculate_portfolio_metrics()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Keys ครบ | Contract | total_value, cash/gold %, roi, can_buy, can_sell |
| total_value = cash + cur_val | Calculation | |
| can_buy: cash ≥ 1000 | Business Logic | |
| can_sell: gold > 0 | Business Logic | |
| ROI = (cur-cost)/cost × 100 | Calculation | |
| Zero total ไม่ crash | Edge Case | หาร 0 → return 0 |

#### `validate_portfolio_update()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Valid → (True, '') | Happy Path | |
| cash < 0 → False | Validation | |
| gold < 0 → False | Validation | |
| cost < 0 → False | Validation | |
| cur_val < 0 → False | Validation | |
| None → False | Validation | |
| pnl < 0 → True | Business Logic | ขาดทุนได้ปกติ |
| Return tuple (bool, str) | Contract | |

---

### 3.2 `test_ui_renderers.py` — HTML Renderer Classes

**โมดูลที่ทดสอบ:** `ui/core/renderers.py`

**Strategy:** ทดสอบ HTML output ที่ renderer คืนกลับมา — ตรวจว่ามี content ที่ถูกต้อง ไม่ crash กรณี edge case

#### `StatusRenderer`

| Method | Scenario | รายละเอียด |
|--------|----------|-----------|
| `error_badge()` | Return HTML string | มี `<div` |
| `error_badge()` | มี message | error message ปรากฏใน output |
| `error_badge()` | is_validation ต่างกัน | style แตกต่างกัน |
| `error_badge()` | Empty message ไม่ crash | |
| `success_badge()` | มี checkmark | ✓ หรือ "check" ปรากฏ |
| `success_badge()` | มี message | message ปรากฏ |
| `info_badge()` | Return HTML | มี `<div` + message |
| `signal_decision_card()` | มี signal | BUY/SELL/HOLD ปรากฏ |
| `signal_decision_card()` | มี confidence | % ปรากฏ |
| `signal_decision_card()` | มี price levels | entry/sl/tp ปรากฏเมื่อส่งเข้า |
| `signal_decision_card()` | confidence ≥ 0.85 → STRONG | label เปลี่ยนเป็น STRONG |

#### `TraceRenderer`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Return HTML | Contract | เป็น string |
| Empty trace ไม่ crash | Edge Case | คืน HTML ที่บอกว่าไม่มีข้อมูล |
| มี step count | Content | จำนวน steps ปรากฏ |
| มี thought text | Content | ข้อความ thought ปรากฏ |
| มี signal | Content | BUY ปรากฏใน FINAL_DECISION |
| HTML structure | Contract | มี `<div` |
| Single step ไม่ crash | Edge Case | |

#### `HistoryRenderer`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Return HTML | Contract | เป็น string |
| Empty rows ไม่ crash | Edge Case | คืน HTML ที่บอกว่าไม่มีข้อมูล |
| มี signal | Content | BUY/SELL ปรากฏ |
| มี run ID | Content | ID ปรากฏ |
| มี provider | Content | "openai" ปรากฏ |
| มี `<table` | Structure | HTML table structure |
| มีราคา | Content | gold price ปรากฏ |

#### `StatsRenderer`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| total = 0 ไม่ crash | Edge Case | คืน string สั้นๆ |
| มี BUY count | Content | "BUY" + "5" ปรากฏ |
| มี avg confidence | Content | % ปรากฏ |
| มี avg price | Content | ราคาปรากฏ |

#### `PortfolioRenderer`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Empty dict ไม่ crash | Edge Case | |
| None ไม่ crash | Edge Case | |
| มี cash balance | Content | "5,000" ปรากฏ |
| มี gold grams | Content | "1.0" ปรากฏ |
| มี P&L | Content | "300" ปรากฏ |
| Can Buy indicator | Content | "Can Buy" ปรากฏ |
| trades today | Content | "2" ปรากฏ |

---

### 3.3 `test_ui_services.py` — Services Layer

**โมดูลที่ทดสอบ:** `ui/core/services.py`

**Strategy:** Mock DB ทั้งหมดด้วย `MagicMock` — ไม่มี network call หรือ DB call จริง

#### `_normalize_provider()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| gemini_2.5_flash → gemini | Normalization | |
| gemini-2.5-flash → gemini | Normalization | hyphen variant |
| groq_llama → groq | Normalization | |
| mock-v1 → mock | Normalization | |
| openai → openai | Passthrough | ไม่มีใน alias map |
| "" → "" | Edge Case | string ว่าง |
| None → None | Edge Case | |
| unknown → unchanged | Fallback | คืนตัวเดิม |

#### `_extract_llm_log()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Return dict | Contract | |
| interval_tf set ถูกต้อง | Contract | |
| signal, confidence, provider extracted | Contract | |
| token info extracted | Contract | token_total, token_input |
| No fallback when clean | Business Logic | is_fallback = False |
| Fallback detected | Business Logic | fallback_log มีข้อมูล → is_fallback = True |
| Required keys ครบ | Contract | interval_tf, signal, confidence, provider, ... |
| Missing fields → defaults | Edge Case | dict ว่าง → HOLD, 0.0, False |

#### `PortfolioService.save_portfolio()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Save success | Happy Path | status = "success" |
| Return data | Contract | result มี "data" key |
| เรียก db.save_portfolio() | Mock Verify | ตรวจว่า DB ถูกเรียก |
| cash < 0 → error | Validation | |
| gold < 0 → error | Validation | |
| pnl < 0 → success | Business Logic | ขาดทุนได้ปกติ |
| DB error → error status | Error Handling | ไม่ crash |
| ค่า 0 ทุกตัว → success | Edge Case | |

#### `PortfolioService.load_portfolio()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Load success | Happy Path | status = "success" |
| Return data | Contract | มี "data" key |
| DB empty → DEFAULT_PORTFOLIO | Fallback | get_portfolio() = None → ใช้ default |
| DB error → error + default data | Error Handling | ไม่ crash ยังมี data |

#### `HistoryService.get_recent_runs()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Return list | Contract | |
| Count ถูกต้อง | Business Logic | mock มี 2 rows → len = 2 |
| เรียก DB ด้วย limit | Mock Verify | |
| DB error → [] | Error Handling | ไม่ crash คืน list ว่าง |

#### `HistoryService.get_statistics()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Return dict | Contract | |
| Keys ครบ | Contract | total, buy_count, sell_count |
| ค่าถูกต้อง | Business Logic | total=10, buy=5 |
| DB error → zero stats | Error Handling | ไม่ crash คืน zero |

#### `HistoryService.get_run_detail()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Found → success | Happy Path | status = "success", data.id ถูกต้อง |
| Not found → error | Negative | status = "error" |
| Fallback to get_recent_runs | Fallback | DB ไม่มี get_run_by_id → fallback |
| DB error → error | Error Handling | |

#### `HistoryService.get_llm_logs()`

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| Return list | Contract | |
| เรียก DB ด้วย run_id | Mock Verify | |
| DB error → [] | Error Handling | |
| get_recent_llm_logs returns list | Contract | |

#### `AnalysisService` — Input Validation

| Scenario | ประเภท | รายละเอียด |
|----------|--------|-----------|
| intervals ว่าง → validation error | Validation | error_type = "validation" |
| provider ไม่ถูกต้อง → validation error | Validation | |
| provider normalization ทำงาน | Business Logic | gemini_2.5_flash → gemini ก่อน validate |
| valid input → _validate_inputs = None | Happy Path | |
| bad provider → _validate_inputs error | Negative | มีคำว่า "provider" หรือ "Invalid" |
| empty intervals → _validate_inputs error | Negative | มีคำว่า "interval" |
| orchestrator exception → error dict | Error Handling | status = "error" |

---

## 4. Testing Architecture

### Mock Strategy

```
tests/test_ui/
    │
    ├── test_ui_utils.py     → ไม่มี mock (pure functions ทั้งหมด)
    │
    ├── test_ui_renderers.py → ไม่มี mock (test HTML output โดยตรง)
    │                          import ผ่านได้เพราะ renderers ไม่เรียก external service
    │
    └── test_ui_services.py  → MagicMock สำหรับ DB
                               patch("ui.core.config.validate_*") สำหรับ validation
```

### _mock_db() Helper

```python
def _mock_db():
    db = MagicMock()
    db.get_portfolio.return_value   = {...}    # fake portfolio data
    db.save_portfolio.return_value  = None
    db.get_recent_runs.return_value = [{...}]  # fake run history
    db.get_signal_stats.return_value = {...}   # fake stats
    db.get_llm_logs_for_run.return_value = []
    db.save_run.return_value = 42              # fake run_id
    return db
```

### Patch Path Rules

`validate_provider`, `validate_period`, `validate_intervals` ถูก import แบบ local ใน `_validate_inputs()` ดังนั้นต้อง patch ที่ source:

```python
# ✅ ถูกต้อง — patch ที่ source module
with patch("ui.core.config.validate_provider", return_value=True):
    ...

# ❌ ผิด — patch ที่ services ไม่ได้ผล (local import)
with patch("ui.core.services.validate_provider", return_value=True):
    ...
```

---

## 5. QA Standards & Conventions

### 5.1 Pytest Markers

```python
# ทุก test ใน test_ui/ ควรมี marker
pytestmark = pytest.mark.unit   # สำหรับ utils และ renderers
pytestmark = pytest.mark.unit   # สำหรับ services (mock DB ถือเป็น unit test)
```

### 5.2 Mock Rules

**ข้อกำหนด:** ห้าม DB call หรือ network call จริงในทุก test

```python
# ✅ ถูกต้อง — mock DB ด้วย MagicMock
svc = PortfolioService(_mock_db())

# ✅ ถูกต้อง — patch validation functions ที่ source
with patch("ui.core.config.validate_provider", return_value=True):
    ...

# ❌ ผิด — ใช้ DB จริง
svc = PortfolioService(RunDatabase())
```

### 5.3 HTML Assertion Rules

การทดสอบ HTML output ใช้ `in` operator ตรวจหา content หลัก ไม่ตรวจ HTML structure ทั้งหมด:

```python
# ✅ ถูกต้อง — ตรวจ content หลัก
assert "BUY" in result
assert "<div" in result
assert "45,000" in result or "45000" in result  # รองรับ number formatting

# ❌ ผิด — ตรวจ HTML structure ทั้งหมด (เปราะเกินไป เปลี่ยน CSS แล้วพัง)
assert result == expected_full_html
```

### 5.4 Negative Test Requirement

ทุก test class ต้องมีอย่างน้อย 1 negative test:

```python
# ✅ Negative tests ที่มีอยู่
def test_empty_trace_no_crash()           # test_ui_renderers.py
def test_none_portfolio_no_crash()        # test_ui_renderers.py
def test_negative_cash_rejected()         # test_ui_services.py
def test_db_error_returns_error_status()  # test_ui_services.py
def test_empty_input_returns_hold()       # test_ui_utils.py
```

---

## 6. How to Run

**ทุกคำสั่งรันจาก directory `Src/`**

### รัน test_ui ทั้งหมด

```bash
python -m pytest tests/test_ui/ -v
```

### รันไฟล์เดียว

```bash
python -m pytest tests/test_ui/test_ui_utils.py -v
python -m pytest tests/test_ui/test_ui_renderers.py -v
python -m pytest tests/test_ui/test_ui_services.py -v
```

### รัน test class เดียว

```bash
python -m pytest tests/test_ui/test_ui_utils.py::TestCalculateWeightedVote -v
python -m pytest tests/test_ui/test_ui_renderers.py::TestStatusRendererErrorBadge -v
python -m pytest tests/test_ui/test_ui_services.py::TestPortfolioServiceSave -v
```

### Dry Run

```bash
python -m pytest tests/test_ui/ --collect-only
```

### Filter โดย keyword

```bash
python -m pytest tests/test_ui/ -k "portfolio" -v
python -m pytest tests/test_ui/ -k "error" -v
```

---

## Appendix: Design Decisions

| รายการ | สถานะ | รายละเอียด |
|--------|-------|-----------|
| ไม่ทดสอบ Gradio UI จริง (button click, form fill) | ✅ By Design | `dashboard.py` ไม่มี business logic — ทดสอบที่ Services/Renderers แทนได้ผลดีกว่า ตาม principle "UI contains zero business logic" |
| patch ที่ `ui.core.config` ไม่ใช่ `ui.core.services` | ✅ By Design | `validate_*` functions ถูก import แบบ local ใน `_validate_inputs()` ต้อง patch ที่ source |
| ไม่มี `@pytest.mark` ใน test functions | 🔄 ควรเพิ่ม | เพิ่ม `pytestmark = pytest.mark.unit` ในอนาคตเมื่อ marker system ถูก setup ครบ |

> **กฎ QA:** ถ้า production code มี bug ที่ต้องแก้เพื่อให้ test ผ่าน — **รายงานเป็น finding** อย่าแก้ไฟล์ production เอง