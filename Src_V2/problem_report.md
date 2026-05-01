# Gold Trading Agent — Input/Output Audit Report
> ตรวจสอบ input/output ของทุกโมดูลในระบบ  
> วันที่ตรวจ: 2026-05-01 | อ้างอิง payload: `latest.json` (2026-04-11T22:56)

---
*******************
บรรทัด 181
บรรทัด 277
บรรทัด 432
บรรทัด 537 มีแนะนำการแก้ไข 620

*******************


## สารบัญ
1. [ภาพรวม Pipeline](#1-ภาพรวม-pipeline)
2. [GoldDataFetcher.fetch_all()](#2-golddatafetcherfetch_all)
3. [fetch_price tool](#3-fetch_price-tool)
4. [fetch_indicators tool](#4-fetch_indicators-tool)
5. [fetch_news tool](#5-fetch_news-tool)
6. [GoldTradingOrchestrator._assemble_payload()](#6-goldtradingorchestratorassemble_payload)
7. [resolve_session_gate()](#7-resolve_session_gate)
8. [_attach_portfolio_state()](#8-_attach_portfolio_state)
9. [get_xgboost_feature_v2()](#9-get_xgboost_feature_v2)
10. [XGBoostPredictor.predict()](#10-xgboostpredictorpredict)
11. [CoreDecision.evaluate()](#11-coredecisionevaluate)
12. [RiskManager.evaluate()](#12-riskmanagerevaluate)
13. [Decision.to_persist_dict()](#13-decisionto_persist_dict)
14. [RunDatabase.save_run()](#14-rundatabasesave_run)
15. [TelegramNotifier.notify()](#15-telegramnotifiernotify)
16. [สรุปปัญหา Input/Output ทั้งหมด](#16-สรุปปัญหา-inputoutput-ทั้งหมด)

---

## 1. ภาพรวม Pipeline

```
main.py
  └─ GoldTradingOrchestrator.run()
       ├─ fetch_price()         → spot_price_usd, thai_gold_thb, ohlcv_df
       ├─ fetch_indicators()    → indicators dict
       ├─ fetch_news()          → news dict
       ├─ _fetch_mts_latest_price()  → override sell_price_thb
       └─ _assemble_payload()   → market_state dict
  └─ resolve_session_gate()    → session_gate dict → attach to market_state
  └─ _attach_portfolio_state() → portfolio, execution_quota, portfolio_summary
  └─ get_xgboost_feature_v2()  → 26-dim feature dict
  └─ XGBoostPredictor.predict() → XGBOutput (direction, confidence, proba)
  └─ CoreDecision.evaluate()
       ├─ RiskManager.evaluate()    → risk gate result
       └─ resolve_session_gate()    → session gate result (2nd call)
  └─ _persist_run()            → RunDatabase.save_run() → run_id
  └─ _notify_if_pass()         → TelegramNotifier.notify()
```

---

## 2. GoldDataFetcher.fetch_all()

**Input:** `history_days: int`, `interval: str`

**Output:** `dict`

| Key | Type | ค่าตัวอย่าง | สถานะ |
|-----|------|-------------|-------|
| `spot_price` | dict | `{source, price_usd_per_oz, timestamp, confidence}` | ✅ |
| `thai_gold` | dict | `{sell_price_thb, buy_price_thb, ...}` | ✅ |
| `forex` | dict | `{usd_thb, source}` | ✅ |
| `ohlcv_df` | DataFrame | OHLCV index=UTC | ✅ |

**หมายเหตุ:** Waterfall source: TwelveData → YFinance → Gold-API  
Confidence ลดลงตาม source: 0.9 → 0.7 → 0.5

---

## 3. fetch_price tool

**Input:** `history_days: int`, `interval: str`

**Output:** `dict`

| Key | Type | ผู้ใช้ | สถานะ |
|-----|------|--------|-------|
| `spot_price_usd` | dict | orchestrator | ✅ |
| `thai_gold_thb` | dict | orchestrator | ✅ |
| `forex` | dict | orchestrator | ✅ |
| `recent_price_action` | list[dict] | orchestrator → payload | ✅ |
| `ohlcv_df` | DataFrame | fetch_indicators, extract_features_v2 | ✅ |
| `data_sources` | dict | orchestrator → payload.data_sources | ✅ |
| `error` | str\|None | orchestrator (logged) | ✅ |

---

## 4. fetch_indicators tool

**Input:** `ohlcv_df: DataFrame` (ส่งมาจาก orchestrator โดยตรง), `interval: str`

**Output:** `dict`

```python
{
  "indicators": {
    "rsi":        {"value": float, "signal": str, "period": int},
    "macd":       {"macd_line": float, "signal_line": float, "histogram": float, "crossover": str},
    "bollinger":  {"upper": float, "middle": float, "lower": float, "bandwidth": float, "pct_b": float, "signal": str},
    "atr":        {"value": float, "period": int, "volatility_level": str, "unit": str},
    "trend":      {"ema_20": float, "ema_50": float, "trend": str, "golden_cross": bool, "death_cross": bool},
    "latest_close": float,
    "calculated_at": str,
    "data_quality": {"warnings": [], "is_weekend": False, "quality_score": "good"}
  },
  "data_quality": {"quality_score": str, "is_weekend": bool, "warnings": list},
  "error": None
}
```

### ⚠️ ปัญหาที่พบ:  `sma_200` mismatch

| จุด | Key ที่ใช้ | ค่าที่ได้ | ผลกระทบ |
|-----|----------|----------|---------|
| `TrendResult` dataclass | ไม่มี `ema_200` field | — | — |
| `indicators.py` คำนวณ | `self.df["ema_200"]` | ✅ คำนวณได้ | แต่ไม่ถูก include ใน dataclass |
| `asdict(TrendResult)` output | `ema_20`, `ema_50` | -  | — |
| `latest.json` ที่บันทึกออกมา | มี key `sma_200` | 4785.01 | มาจากไหน? (เก่ากว่า?) |


---

## 5. fetch_news tool

**Input:** `max_per_category: int = 5`

**Output:** `dict` (async wrapped เป็น sync ใน tool_registry)

| Key | Type | สถานะ |
|-----|------|-------|
| `summary.total_articles` | int | ✅ |
| `summary.overall_sentiment` | float | ✅ |
| `by_category` | dict | ✅ |
| `by_category.top_5_key_headlines` | list[str] | ✅ orchestrator อ่านได้ |

**หมายเหตุ:** orchestrator ตรวจก่อนว่า `news_s` เป็น `None` หรือไม่ แล้ว fallback ได้ถูกต้อง

---

## 6. GoldTradingOrchestrator._assemble_payload()

**Input:** ผลจาก fetch_price, fetch_indicators, fetch_news

**Output:** `market_state dict` — โครงสร้างหลักที่ไหลต่อไปทั้ง pipeline

### โครงสร้าง output ที่ตรวจแล้ว

| Path | Type | Source | สถานะ |
|------|------|--------|-------|
| `meta.version` | str | hardcode "1.3.0" | ✅ |
| `market_data.spot_price_usd` | dict | fetch_price | ✅ |
| `market_data.forex.usd_thb` | float | fetch_price | ✅ |
| `market_data.forex.source` | str | ดึงจาก 4 key fallback | ✅ |
| `market_data.thai_gold_thb.sell_price_thb` | float | **MTS API override** | ✅ |
| `market_data.thai_gold_thb.buy_price_thb` | float | huasengheng_api | ✅ |
| `market_data.thai_gold_thb.mid_price_thb` | float | คำนวณจาก (sell+buy)/2 | ✅ |
| `market_data.spread_coverage.spread_thb` | float | sell - buy | ✅ |
| `market_data.spread_coverage.edge_score` | float | expected_move / spread | ✅ |
| `market_data.price_trend` | dict | คำนวณจาก OHLCV | ✅ |
| `market_data.recent_price_action` | list[dict] | 5 แท่งล่าสุด | ✅ |
| `technical_indicators` | dict | fetch_indicators | ✅ |
| `news.summary` | dict | fetch_news | ✅ |
| `news.latest_news` | list[str] | top_5_key_headlines | ✅ |
| `portfolio` | dict | empty (DB attach ทีหลัง) | ✅ |
| `execution_quota` | dict | คำนวณจาก trades_today | ✅ |
| `interval` | str | propagate ถูกต้อง (FIX B2) | ✅ |
| `_raw_ohlcv` | DataFrame | attach หลัง save (ไม่ถูก serialize) | ✅ |

### ⚠️ ปัญหาที่พบ: `logger` ถูก define ซ้ำ 2 ครั้ง





*******************************
```python
# orchestrator.py บรรทัด 12
logger = logging.getLogger(__name__)
# บรรทัด 16 — ซ้ำ ไม่มีผลต่อระบบแต่ code ไม่สะอาด
logger = logging.getLogger(__name__)
```
********************************





## 7. resolve_session_gate()

**Input:** `now: datetime (Asia/Bangkok tz-aware)`

**Output:** `SessionGateResult`

| Field | Type | ค่าที่เป็นไปได้ | สถานะ |
|-------|------|----------------|-------|
| `apply_gate` | bool | True / False | ✅ |
| `session_id` | str\|None | morning/noon/evening/weekend/None | ✅ |
| `minutes_to_session_end` | int\|None | 0-719 | ✅ |
| `quota_urgent` | bool | True ถ้า ≤15 นาที | ✅ |
| `suggested_min_confidence` | float | 0.1 (urgent) / 0.2 (edge) | ✅ |
| `llm_mode` | str | "quota" / "edge" | ✅ |

### ⚠️ ปัญหาที่พบ: Weekend หลัง 17:30 → apply_gate=False → session="Unknown"

```python
_WEEKEND_WINDOWS = (
    SessionWindow(_t(9, 30), _t(17, 30), "weekend", "weekend", 0),
)
# latest.json generated_at = 22:56 (weekend) → นอก window → apply_gate=False
# → attach_session_gate_to_market_state() จะ pop "session_gate" ออก
# → _resolve_session_label() จะคืน "Unknown"
# → XGBoost log: session=Unknown
```

> **ผลกระทบ:** ไม่กระทบ inference (session เป็นแค่ trace) แต่ log ไม่ถูกต้อง  
> และ CoreDecision._eval_session_gate() จะ reject ทุก BUY/SELL นอก window weekend

### ✅ ถูกต้อง: เรียก 2 ครั้งโดยตั้งใจ

- **ครั้งที่ 1:** `main.py run_analysis_once()` — attach session_gate ก่อน XGBoost (FIX-1 v2.2)
- **ครั้งที่ 2:** `core.py _eval_session_gate()` — ป้องกัน clock drift ระหว่าง 2 ขั้นตอน

---

## 8. _attach_portfolio_state()

**Input:** `rt: Runtime`, `market_state: dict`

**Side effect:** เติม 3 key ลง market_state

| Key เพิ่ม | Source | สถานะ |
|----------|--------|-------|
| `market_state["portfolio"]` | RunDatabase.get_portfolio() หรือ {} | ✅ |
| `market_state["execution_quota"]` | คำนวณจาก trades_today + BASE_CONFIDENCE + CONFIDENCE_STEP | ✅ |
| `market_state["portfolio_summary"]` | mode: normal/defensive/critical + can_trade | ✅ |

**หมายเหตุ:** ถ้า DB ไม่พร้อม → ใช้ portfolio จาก orchestrator (อาจเป็น `{}`) → cash_balance = 0.0 → `can_trade=False` → RiskManager reject ทุก BUY

---

## 9. get_xgboost_feature_v2()

**Input:** `market_state: dict` (ต้องมี `_raw_ohlcv`)

**Output:** `dict` — 26 features

| กลุ่ม | Features | Input Source | สถานะ |
|-------|----------|-------------|-------|
| Candle OHLC | xauusd_open/high/low/close | `_raw_ohlcv.iloc[-1]` | ✅ |
| Returns | xauusd_ret1, xauusd_ret3 | `_raw_ohlcv["close"]` | ✅ |
| USDTHB | usdthb_ret1, usdthb_dist_ema21 | **hardcode 0.0** | ⚠️ |
| MACD | xau_macd_delta1 | อ่าน `prev_histogram` จาก indicators | ⚠️ |
| RSI | xauusd_rsi14, xau_rsi_delta1 | อ่าน `prev_value` จาก indicators | ⚠️ |
| Bollinger | xauusd_bb_width | `bandwidth` | ✅ |
| ATR | xauusd_atr_norm, atr_rank50 | value / close, percentile rank | ✅ |
| EMA dist | xauusd_dist_ema21, xauusd_dist_ema50 | (close - ema) / ema | ✅ |
| Trend | trend_regime | uptrend=1/sideways=0/downtrend=-1 | ✅ |
| Candle shape | wick_bias, body_strength | (h-l) geometry | ✅ |
| Time | hour_sin/cos, minute_sin/cos, session_progress, day_of_week | timestamp | ✅ |

### ⚠️ Features ที่ hardcode 0.0 (ไม่มีข้อมูลจริง) ปกติของ version 2 
# ไม่มี USDTHB time series → return 0 เป็น default (ปลอดภัย, เปลี่ยนใน v2.2)
```python
usdthb_ret1      = 0.0   # ไม่มี USDTHB time series → comment ว่า "ปลอดภัย, เปลี่ยนใน v2.2"
usdthb_dist_ema21 = 0.0  # เช่นกัน
```




**************************************************
### ⚠️ `xau_rsi_delta1` และ `xau_macd_delta1` มักได้ 0.0

```python
rsi_prev = rsi_data.get("prev_value")        # fetch_indicators ไม่ส่ง prev_value
macd_hist_prev = macd_data.get("prev_histogram")  # fetch_indicators ไม่ส่ง prev_histogram
# → ถ้า prev เป็น None → delta = 0.0 เสมอ
```

> indicators.py ไม่ expose `prev_value` หรือ `prev_histogram` ใน output dict  
> ทำให้ 4 features (usdthb_ret1, usdthb_dist_ema21, xau_rsi_delta1, xau_macd_delta1) **มักได้ค่า 0.0 ทุกรอบ**  
> โมเดลที่ train มาอาจ learn บน 0.0 เหล่านี้แล้วก็ได้ แต่ถ้าไม่ใช่จะทำให้ prediction bias

### ⚠️ `session_progress()` — ค่าไม่ต่อเนื่องที่เที่ยงคืน

```python
# ช่วง NY 00:00-04:00
return (minutes_of_day + 4 * 60) / (8 * 60)
# 00:00 → 0.5 (ไม่ใช่ 0)
# 04:00 → 1.0
# แต่ 20:00 → 0.0  ← ไม่ต่อเนื่อง
```
****************************************************




---

## 10. XGBoostPredictor.predict()

**Input:** `features: dict` (26 keys), `session: str`

**Output:** `XGBOutput`

```python
@dataclass
class XGBOutput:
    prob_buy:   float   # 0.0–1.0
    prob_sell:  float   # 0.0–1.0
    direction:  str     # "BUY" | "SELL" | "HOLD"
    confidence: float   # = winning proba
    session:    str
    is_high_accuracy_session: bool
    top_features: str   # SHAP summary (ว่างถ้าไม่มี shap)
```

**Decision rule:**
```
buy_proba > 0.60 AND buy_proba >= sell_proba  → BUY
sell_proba > 0.60 AND sell_proba > buy_proba  → SELL
else                                           → HOLD
```

### ✅ ถูกต้อง: `_build_row()` บังคับ column order ตาม schema

```python
return pd.DataFrame([ordered], columns=self.feature_columns)
# columns= บังคับลำดับ — XGBoost ต้องการลำดับตรงกับตอน train
```

### ✅ ถูกต้อง: `_proba()` handle หลาย output shape

```python
if arr.ndim == 2 and arr.shape[1] >= 2: return float(arr[0][1])  # standard
if arr.ndim == 2 and arr.shape[1] == 1: return float(arr[0][0])  # edge case
return float(arr.flat[-1])  # booster fallback
```

---

## 11. CoreDecision.evaluate()

**Input:** `signal: str`, `confidence: float`, `market_state: dict`, `rationale: str`, `xgb_output: XGBOutput (optional)`

**Output:** `Decision`

### ✅ Path ที่ทำงานถูกต้อง

| Case | Path | Output |
|------|------|--------|
| `signal == "HOLD"` | bypass gate | `Decision(final="HOLD", notify=False)` |
| BUY/SELL, gate PASS | RiskManager ✅ + SessionGate ✅ | `Decision(final=signal, notify=True)` |
| BUY/SELL, gate FAIL | either rejects | `Decision(final="HOLD", notify=False, reject_reason=...)` |
| `xgb_output.is_forced=True` | bypass gate | `Decision(final=signal, notify=True, is_forced=True)` |

### ⚠️ Forced path เป็น Dead Code ณ ปัจจุบัน

```python
# core.py รองรับ is_forced=True แต่...
# signal.py ไม่มี EndOfSessionForcer class ใน codebase ที่ให้มา
# XGBoostPredictor.predict() ไม่ set is_forced เลย
# → forced bypass path ไม่ถูกเรียกใช้งานจริง
```

### ✅ ถูกต้อง: `_eval_session_gate()` ส่ง tz-aware datetime (FIX v1.1)

```python
if _BKK_TZ is not None:
    now_bkk = datetime.now(_BKK_TZ)   # ✅ tz-aware Asia/Bangkok
```

---

## 12. RiskManager.evaluate()

**Input:** `llm_decision: dict`, `market_state: dict`

llm_decision keys ที่อ่าน:
```
signal, confidence, market_context, position_size_thb, execution_check
```

market_state keys ที่อ่าน:
```
portfolio.cash_balance, portfolio.gold_grams, portfolio.unrealized_pnl
portfolio.trades_today, portfolio.take_profit_price, portfolio.stop_loss_price
market_data.thai_gold_thb.sell_price_thb (→ buy_price_thb สำหรับ BUY)
market_data.thai_gold_thb.buy_price_thb  (→ sell_price_thb สำหรับ SELL)
technical_indicators.atr.value
session_gate.is_dead_zone, session_gate.quota_urgent
session_gate.minutes_to_session_end, session_gate.session_quota
execution_quota.min_entries_by_now, execution_quota.required_confidence_for_next_buy
portfolio_summary.mode, portfolio_summary.can_trade
market_data.spread_coverage.edge_score
pre_fetched_tools.get_htf_trend.trend
```

**Output:** `dict`

```python
{
  "signal":            str,   # BUY/SELL/HOLD
  "confidence":        float,
  "entry_price":       float | None,   # THB/baht-weight
  "stop_loss":         float | None,
  "take_profit":       float | None,
  "position_size_thb": float,
  "rationale":         str,
  "rejection_reason":  str | None,
}
```

### ⚠️ ปัญหา: ชื่อ key BUY/SELL price กลับกัน (naming convention)

```python
# risk.py บรรทัด 94-95:
buy_price_thb  = float(thai_gold["sell_price_thb"])  # ← ใช้ sell price เป็น BUY entry
sell_price_thb = float(thai_gold["buy_price_thb"])   # ← ใช้ buy price เป็น SELL entry
```





*******************************************************************
> ชื่อตัวแปรสับสน แต่ **logic ถูกต้อง** เพราะ:
> - ผู้ซื้อทอง (BUY) ต้องจ่ายในราคา `sell_price_thb` (ราคาขายของร้าน)
> - ผู้ขายทอง (SELL) ได้รับ `buy_price_thb` (ราคารับซื้อของร้าน)

### ⚠️ ปัญหา: `edge_score` fallback อาจให้ค่าผิด


```python
if effective_spread > 0 and expected_move_thb <= 0:
    if atr_value > 0:
        expected_move_thb = atr_value  # ← ATR หน่วย USD/oz ≈ 4.2 แต่ spread หน่วย THB ≈ 200
        # edge_score = 4.2 / 200 = 0.021 → reject เสมอ
        # edge_score ≈ 0 ตลอด
        # → BUY โดน reject แทบทุกครั้ง
```

> ATR มาจาก `technical_indicators.atr.value` หน่วย **USD/oz** ≈ 4.2  
> แต่ spread หน่วย **THB/baht-weight** ≈ 200  
> → `edge_score < 1.0` ทุกครั้ง → BUY ถูก reject ด้วยเหตุ "Edge ไม่พอชนะ spread"  

---

**************************************************
### ⚠️ Column `atr_thb` บันทึกค่า USD

```python
atr_thb = ti.get("atr", {}).get("value")  # ค่า ~4.2 USD/oz
# DB column ชื่อ atr_thb แต่ค่าจริงเป็น USD/oz — ไม่มีการ convert
```

**Output:** `run_id: int` (RETURNING id)
**************************************************


****************************************************************************






## 13. Decision.to_persist_dict()

**Output ที่ส่งไป save_run():**

```python
{
  "signal":            str,
  "confidence":        float,
  "entry_price":       float | None,
  "stop_loss":         float | None,
  "take_profit":       float | None,
  "position_size_thb": float,
  "rationale":         str,
  "rejection_reason":  str | None,
  "model_signal":      str,
  "is_forced":         bool,
  "forced_reason":     str,
  "iterations_used":   0,   # hardcode — ไม่ได้ track จริง
  "tool_calls_used":   0,   # hardcode — ไม่ได้ track จริง
}
```

### ✅ ทุก key ถูก consume โดย save_run() ถูกต้อง

---

## 14. RunDatabase.save_run()

**Input:** `provider: str`, `result: dict`, `market_state: dict`, `interval_tf: str`, `period: str`

**อ่านจาก result:**

| result key | DB column | สถานะ |
|-----------|-----------|-------|
| `signal` | `signal` | ✅ |
| `confidence` | `confidence` | ✅ |
| `entry_price` | `entry_price`, `entry_price_thb` | ✅ (save 2 คอลัมน์) |
| `stop_loss` | `stop_loss`, `stop_loss_thb` | ✅ |
| `take_profit` | `take_profit`, `take_profit_thb` | ✅ |
| `rationale` | `rationale` | ✅ |
| `iterations_used` | `iterations_used` | ✅ (ได้ 0 เสมอ) |
| `tool_calls_used` | `tool_calls_used` | ✅ (ได้ 0 เสมอ) |
| `react_trace` | `react_trace` | ✅ (ได้ `[]` เสมอ) |

**อ่านจาก market_state:**

| market_state path | DB column | สถานะ |
|------------------|-----------|-------|
| `market_data.spot_price_usd.price_usd_per_oz` | `gold_price` | ✅ |
| `market_data.forex.usd_thb` | `usd_thb_rate` | ✅ |
| `market_data.thai_gold_thb.sell_price_thb` | `gold_price_thb` | ✅ |
| `technical_indicators.rsi.value` | `rsi` | ✅ |
| `technical_indicators.macd.macd_line` | `macd_line` | ✅ |
| `technical_indicators.macd.signal_line` | `signal_line` | ✅ |
| `technical_indicators.trend.trend` | `trend` | ✅ |
| `technical_indicators.macd.histogram` | `macd_histogram` | ✅ |
| `technical_indicators.bollinger.pct_b` | `bb_pct_b` | ✅ |
| `technical_indicators.atr.value` | `atr_thb` | ⚠️ หน่วย USD ไม่ใช่ THB |
| `data_quality.is_weekend` | `is_weekend` | ✅ |
| `data_quality.quality_score` | `data_quality` | ✅ |



**************************************************
### ⚠️ Column `atr_thb` บันทึกค่า USD

```python
atr_thb = ti.get("atr", {}).get("value")  # ค่า ~4.2 USD/oz
# DB column ชื่อ atr_thb แต่ค่าจริงเป็น USD/oz — ไม่มีการ convert
```

**Output:** `run_id: int` (RETURNING id)
**************************************************
---

## 15. TelegramNotifier.notify()

**Input:** `voting_result: dict`, `provider: str`, `period: str`, `interval_results: dict`, `market_state: dict`, `run_id: int`

**อ่านจาก voting_result:**

| Key | สถานะ |
|-----|-------|
| `final_signal` | ✅ |
| `weighted_confidence` | ✅ |
| `rationale` | ✅ (ไม่มีใน voting_breakdown ก็ได้) |

**อ่านจาก interval_results (ผ่าน best_iv):**

| Key | อ่านโดย | สถานะ |
|-----|--------|-------|
| `entry_price` | แสดงใน message | ✅ |
| `stop_loss` | แสดงใน message | ✅ |
| `take_profit` | แสดงใน message | ✅ |
| `rationale` | แสดงใน message | ✅ |

**ที่ main.py ส่งมา:**
```python
interval_results = {
  "xgb": {
    "signal":       decision.final,
    "confidence":   float(decision.confidence),
    "entry_price":  decision.entry_price,    # ✅ มี
    "stop_loss":    decision.stop_loss,      # ✅ มี
    "take_profit":  decision.take_profit,    # ✅ มี
    "provider":     PROVIDER_TAG,
  }
}
```

> ✅ ทุก key ที่ notifier ต้องการมีครบ

**Output:** `bool` (True = ส่งสำเร็จ)

---

## 16. สรุปปัญหา Input/Output ทั้งหมด

### 🔴 Critical — กระทบผล production

| # | จุด | ปัญหา | ผลกระทบ |
|---|-----|-------|---------|
| C1 | `RiskManager.evaluate()` | ATR (USD/oz ≈ 4.2) หารด้วย spread (THB ≈ 200) ใน edge_score fallback | `edge_score < 1.0` ทุกครั้ง → BUY ถูก reject เสมอถ้า expected_move = 0 |
| C2 | `get_xgboost_feature_v2()` | `usdthb_ret1`, `usdthb_dist_ema21`, `xau_rsi_delta1`, `xau_macd_delta1` ได้ 0.0 ทุกรอบ | 4/26 features เป็น 0 เสมอ — โมเดลอาจ bias |

### 🟡 Warning — ผลกระทบบางส่วน

| # | จุด | ปัญหา | ผลกระทบ |
|---|-----|-------|---------|
| W1 | `indicators.py` | `TrendResult` ไม่มี `ema_200` field แต่ `to_dict()` มี `sma_200` ใน latest.json | `get_xgboost_feature()` (37-feat) ได้ `ema_200=0` — ไม่กระทบ v2 |
| W2 | `session_gate.py` | Weekend window 09:30–17:30 เท่านั้น | หลัง 17:30 weekend → apply_gate=False → session="Unknown" → gate reject ทุก signal |
| W3 | `database.py` | `atr_thb` column บันทึก USD/oz แทน THB | ค่าใน DB ไม่ตรงกับ column name |
| W4 | `extract_features.py` | `session_progress()` ไม่ต่อเนื่องที่เที่ยงคืน | feature กระโดดจาก 0.0 เป็น 0.5 |

### 🔵 Info — ไม่กระทบ production

| # | จุด | ปัญหา |
|---|-----|-------|
| I1 | `orchestrator.py` | `logger` define ซ้ำ 2 ครั้ง |
| I2 | `core.py` | `EndOfSessionForcer` forced path เป็น dead code |
| I3 | `main.py` | `iterations_used` และ `tool_calls_used` hardcode 0 เสมอ |
| I4 | `main.py` | Discord notifier ถูก comment out ตั้งใจ |
| I5 | `risk.py` | ชื่อตัวแปร `buy_price_thb`/`sell_price_thb` กลับกัน แต่ logic ถูกต้อง |

---

## แนะนำการแก้ไข

### แก้ด่วน (Critical)

**C1 — edge_score fallback หน่วยผิด:**
```python
# risk.py — เปลี่ยนจาก:
expected_move_thb = atr_value  # USD/oz
# เป็น:
usd_thb = market_state.get("market_data", {}).get("forex", {}).get("usd_thb", 33.0)
atr_thb_per_baht = atr_value * usd_thb / 32.15  # แปลง USD/oz → THB/baht-weight
expected_move_thb = atr_thb_per_baht
```

**C2 — เพิ่ม prev_value ใน indicators output:**
```python
# indicators.py — เพิ่มใน to_dict():
result_dict["rsi"]["prev_value"] = float(self.df["rsi"].iloc[-2])    if len(self.df) > 1 else None
result_dict["macd"]["prev_histogram"] = float(self.df["macd_hist"].iloc[-2]) if len(self.df) > 1 else None
```

### แก้รอง (Warning)

**W2 — ขยาย weekend session:**
```python
# session_gate.py
_WEEKEND_WINDOWS = (
    SessionWindow(_t(0, 0),  _t(2, 0),   "weekend", "weekend", 0),
    SessionWindow(_t(9, 30), _t(23, 59), "weekend", "weekend", 0),
)
```

**W3 — แก้ชื่อ column หรือ convert ก่อน insert:**
```python
# database.py
atr_thb = ti.get("atr", {}).get("value", 0) * usd_thb / 32.15  # convert USD→THB
```

---

*Report สร้างโดยการตรวจสอบ source code ทุกไฟล์ใน project.zip และเปรียบเทียบกับ payload จริงใน latest.json*
