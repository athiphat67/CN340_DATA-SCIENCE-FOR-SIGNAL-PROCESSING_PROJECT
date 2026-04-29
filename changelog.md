# สรุปโค้ดที่แก้ทั้งหมด

## 1. `engine/indicators.py`

**สิ่งที่แก้:** เพิ่ม `ML_FEATURE_COLUMNS_XAUUSD` และ `ML_FEATURE_COLUMNS_THAI` เป็น named constants แยกกัน พร้อม backward compat alias `ML_FEATURE_COLUMNS = ML_FEATURE_COLUMNS_XAUUSD`

```python
ML_FEATURE_COLUMNS_XAUUSD: list[str] = [
    "xauusd_open", "xauusd_high", "xauusd_low", "xauusd_close",
    "xauusd_ret1", "xauusd_ret3", "usdthb_ret1",
    "xau_macd_delta1", "xauusd_macd_hist",
    "xauusd_dist_ema21", "xauusd_dist_ema50", "usdthb_dist_ema21",
    "trend_regime",
    "xauusd_rsi14", "xau_rsi_delta1",
    "xauusd_atr_norm", "atr_rank50", "xauusd_bb_width",
    "wick_bias", "body_strength",
    "hour_sin", "hour_cos", "minute_sin", "minute_cos", "session_progress",
    "day_of_week",
]

ML_FEATURE_COLUMNS_THAI: list[str] = [
    "thai_open", "thai_high", "thai_low", "thai_close",
    "thai_ret1", "thai_ret3", "xauusd_ret1",
    "thai_macd_delta1", "thai_macd_hist",
    "thai_dist_ema21", "thai_dist_ema50", "xauusd_dist_ema21",
    "trend_regime",
    "thai_rsi14", "thai_rsi_delta1",
    "thai_atr_norm", "atr_rank50", "thai_bb_width",
    "wick_bias", "body_strength",
    "hour_sin", "hour_cos", "minute_sin", "minute_cos", "session_progress",
    "day_of_week",
]

ML_FEATURE_COLUMNS = ML_FEATURE_COLUMNS_XAUUSD  # backward compat
```

---

## 2. `agent_core/config/feature_columns_xauusd.json`

**สิ่งที่แก้ (Bug 1 + Bug 2):**

| จุด | เดิม | แก้เป็น |
|-----|------|---------|
| Bug 1 — column name ผิด | `"XAU_atr_rank50"` | `"atr_rank50"` |
| Bug 2 — version field หาย | ไม่มี | เพิ่ม `"version": "1.0"` |

```json
{
  "version": "1.0",
  "symbol": "XAU/USD",
  ...
  {
    "name": "atr_rank50",
    "group": "volatility",
    ...
  }
}
```

---

## 3. `agent_core/config/feature_columns_thai.json`

**สิ่งที่แก้ (Bug 1 + Bug 3):**

| จุด | เดิม | แก้เป็น |
|-----|------|---------|
| Bug 1 — column name ผิด | `"thai_atr_rank50"` | `"atr_rank50"` |
| Bug 3 — session formula ผิด | `hour - 6` | `hour - 9` |

```json
{
  "name": "atr_rank50",
  "group": "volatility",
  ...
},
{
  "name": "session_progress",
  "formula": "clamp((hour - 9) * 60 + minute) / (8*60), 0, 1)",
  "note": "session ทองไทย 09:00-17:00"
}
```

---

## 4. `tools/fetch_indicators.py`

**สิ่งที่แก้ (Bug 4 + ตัด Phase 1 ออก):**

- ลบ `fetch_indicators()` Phase 1 (ReAct Loop) ออกทั้งหมด
- ลบ `TOOL_NAME`, `TOOL_DESCRIPTION` ออก
- เพิ่ม `symbol: Literal["xauusd", "thai"]` parameter
- เปลี่ยนชื่อ `usdthb_series` → `external_series`
- เปลี่ยน `session_start_hour` / `session_end_hour` เป็น `Optional[int]` (None = ใช้ default ตาม symbol)
- เปลี่ยน core logic จาก hardcode `get_ml_features_clean()` → `calc.get_features()`

```python
from engine.indicators import (
    TechnicalIndicators,
    ML_FEATURE_COLUMNS_XAUUSD,
    ML_FEATURE_COLUMNS_THAI,
)

_FEATURE_COLS: dict[str, list[str]] = {
    "xauusd": ML_FEATURE_COLUMNS_XAUUSD,
    "thai":   ML_FEATURE_COLUMNS_THAI,
}

def fetch_ml_features(
    symbol: Literal["xauusd", "thai"] = "xauusd",  # ← เพิ่มใหม่
    ohlcv_df: pd.DataFrame = None,
    external_series: Optional[pd.Series] = None,   # ← เปลี่ยนจาก usdthb_series
    session_start_hour: Optional[int] = None,       # ← None = default ตาม symbol
    session_end_hour: Optional[int] = None,
    drop_na: bool = True,
    ...
) -> dict:
    ...
    # เปลี่ยนจาก hardcode → unified API
    features = calc.get_features(
        symbol=symbol,
        external_series=external_series,
        session_start_hour=session_start_hour,
        session_end_hour=session_end_hour,
        drop_na=drop_na,
    )
```

---

## สรุป Bug ที่แก้ทั้งหมด

| Bug | ไฟล์ | อาการ | สถานะ |
|-----|------|-------|-------|
| Bug 1 — column name ไม่ตรง | `feature_columns_xauusd.json`, `feature_columns_thai.json` | โมเดล KeyError ตอน predict | ✅ แก้แล้ว |
| Bug 2 — JSON ไม่มี version | `feature_columns_xauusd.json` | validation script error | ✅ แก้แล้ว |
| Bug 3 — session formula ผิด | `feature_columns_thai.json` | doc ไม่ตรง code | ✅ แก้แล้ว |
| Bug 4 — fetch_ml_features ไม่รองรับ thai | `fetch_indicators.py` | ทองไทยใช้ไม่ได้ | ✅ แก้แล้ว |

## Caller ที่ต้องอัปเดต

โค้ดส่วนอื่นที่เคยเรียก function เดิม ต้องแก้ตามนี้

```python
# เดิม
from tools.fetch_indicators import fetch_indicators
result = fetch_indicators(interval="5m")
fetch_ml_features(usdthb_series=my_series)

# แก้เป็น
from tools.fetch_indicators import fetch_ml_features
result = fetch_ml_features(symbol="xauusd", external_series=my_series)
result = fetch_ml_features(symbol="thai",   external_series=xauusd_series)
```
