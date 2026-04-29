# เอกสารสถาปัตยกรรมระบบ — นักขุดทอง v2 (XGBoost-based Pipeline)

> เวอร์ชัน: 2.0 (Pure ML, ไม่พึ่งพา Generative Model)
> ภาษา: Thai
> ผู้รับผิดชอบ: ทีม CN240 — Data Science for Signal Processing
> ทุนเริ่มต้น: ฿1,500 / ขนาด Position คงที่: ฿1,400 (Aom NOW)

---

## 1. ภาพรวมระบบ (System Overview)

ระบบ "นักขุดทอง v2" เป็น **Algorithmic Trading Engine** สำหรับสร้างสัญญาณซื้อขายทองคำแท่ง (BUY / SELL / HOLD) บนแพลตฟอร์ม Aom NOW โดยปรับสถาปัตยกรรมใหม่ให้เป็น **Pure Machine Learning Pipeline** ที่ใช้ **XGBoost Classifier** เป็นหัวใจการตัดสินใจเพียงอย่างเดียว

### 1.1 จุดต่างจากเวอร์ชันก่อนหน้า

| ด้าน | v1 (เดิม) | v2 (ใหม่ — เอกสารนี้) |
|---|---|---|
| Decision Engine | Multi-step reasoning loop ผ่าน Generative Model | XGBoost Classifier ตรง ๆ |
| ค่า Latency เฉลี่ย/รอบ | 8–25 วินาที (รอเรียก Inference API) | < 200 มิลลิวินาที |
| Determinism | ผลผันแปรตาม temperature/seed | Deterministic 100% |
| ต้นทุนต่อ Inference | $0.001 – $0.01 | $0 (รันบนเครื่อง) |
| Explainability | จาก trace ข้อความ | จาก SHAP / Feature Importance |

### 1.2 Tech Stack

- **Python 3.11+**
- **XGBoost 2.x** — โมเดล Multi-class Classifier (BUY / HOLD / SELL)
- **PostgreSQL** — เก็บ run logs, portfolio snapshot, trade log
- **FastAPI + Uvicorn** — REST API layer
- **WebSocket (websockets)** — รับราคาทองสด (Intergold + HSH965)
- **TwelveData / yfinance / gold-api** — ดึงราคา Spot USD/oz (fallback chain)
- **Discord Webhook + Telegram Bot API** — ช่องทางแจ้งเตือน

### 1.3 ค่าคงที่ของระบบ

| รายการ | ค่า | แหล่งอ้างอิงในโค้ด |
|---|---|---|
| ทุนเริ่มต้น | ฿1,500 | `main.py` |
| Position Size | ฿1,400 (คงที่) | `risk.py::min_trade_thb` |
| ค่าธรรมเนียมต่อรอบ | ฿8 | (ทุนขั้นต่ำสำหรับ BUY = ฿1,408) |
| Interval ของ Loop | 900 วินาที (15 นาที) | `main.py` |
| ATR Multiplier (SL) | 2.5 | `risk.py` v5 |
| Risk : Reward | 1 : 1.5 | `risk.py::risk_reward_ratio` |
| Confidence ขั้นต่ำ (BUY/SELL) | 0.60 | `risk.py::min_confidence` |
| Daily Loss Limit | ฿500 | `risk.py::max_daily_loss_thb` |
| Max Trades / วัน | 6 | `orchestrator.py::daily_target_entries` |
| Dead Zone (ห้ามเทรด) | 02:00–06:14 (Asia/Bangkok) | `session_gate.py` |

---

## 2. แผนผัง Execution Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                        watcher.py                                │
│        (Background thread — RSI-triggered event loop)            │
└──────────────────────────────┬───────────────────────────────────┘
                               │ trigger
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                         main.py                                  │
│              (Orchestration loop — 900 วินาที / รอบ)             │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                       data_engine/                               │
│    orchestrator.py + gold_interceptor_lite.py + thailand_ts.py   │
│        → ดึงราคา / OHLCV / Indicators / News Sentiment           │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼ market_state (dict)
┌──────────────────────────────────────────────────────────────────┐
│                  extract_feature.py                              │
│             get_xgboost_feature()  →  feature_list[37]           │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼ feature_list[]
┌──────────────────────────────────────────────────────────────────┐
│                       signal.py                                  │
│   XGBoostSignal.predict()        →  "BUY" | "HOLD" | "SELL"      │
│   XGBoostSignal.predict_proba()  →  confidence ∈ [0.0, 1.0]      │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼ (signal, confidence)
┌──────────────────────────────────────────────────────────────────┐
│                        core.py                                   │
│             รับสัญญาณ + ความมั่นใจ + market_state                │
└──────────────────────────────┬───────────────────────────────────┘
                               │  fan-out (ขนาน)
                ┌──────────────┴──────────────┐
                ▼                             ▼
   ┌────────────────────────┐    ┌────────────────────────────┐
   │      risk.py           │    │     session_gate.py        │
   │  • spread / edge_score │    │  • session window check    │
   │  • daily loss check    │    │  • quota remaining         │
   │  • cash & position     │    │  • dead-zone enforcement   │
   │  • SL / TP calculation │    │  • urgent / edge / quota   │
   └───────────┬────────────┘    └─────────────┬──────────────┘
               │                               │
               └──────────────┬────────────────┘
                              ▼
                    ALL PASS ?
                ┌──────┴──────┐
                ▼ YES         ▼ NO (บังคับ HOLD)
   ┌────────────────────────────┐    │
   │     notification.py        │    │
   │  Discord + Telegram        │    │
   └─────────────┬──────────────┘    │
                 │                   │
                 └─────────┬─────────┘
                           ▼
              ┌────────────────────────┐
              │      database.py       │
              │   (บันทึกทุกกรณี)      │
              │   YES → trade + run    │
              │   HOLD → run only      │
              └────────────────────────┘
```

---

## 3. Watcher Layer (`watcher.py`)

อิงจาก `Src/engine/engine.py` (WatcherEngine) ทำหน้าที่เป็น **Event-Driven Trigger** ที่รันคู่ขนานกับ `main.py` loop เพื่อให้ระบบตอบสนองต่อสภาพตลาดแบบเรียลไทม์ ไม่ต้องรอครบรอบ 15 นาที

### 3.1 หน้าที่หลัก

1. **RSI-Triggered Wake-up** — เมื่อ RSI ของ timeframe สั้น (5m / 15m) เข้าโซน oversold (≤ 30) หรือ overbought (≥ 70) จะ trigger ให้ `main.py` รัน analysis cycle ทันที
2. **Cooldown** — เมื่อ trigger แล้วต้องรออย่างน้อย 5 นาทีก่อนยิงครั้งถัดไป เพื่อกัน flapping
3. **Trailing-Stop Manager** — ตรวจสอบ position ที่ถืออยู่ทุก 30 วินาที:
   - เมื่อกำไร ≥ ฿20/g → ล็อก SL ที่ราคาทุน + ฿5/g
   - เลื่อน trailing SL ขึ้นตามราคาเมื่อ price ≥ entry + ATR×1.0
4. **Hard Stop Loss** — ขายทันทีเมื่อขาดทุน ≥ ฿15/g (atomic emergency sell, ข้าม core.py)
5. **Heartbeat** — ส่ง log ทุก 60 วินาที เพื่อให้ system monitor ตรวจสอบความมีชีวิตของ thread

### 3.2 รูปแบบการสื่อสารกับ `main.py`

ใช้ `threading.Event()` หรือ `queue.Queue()` แบบ thread-safe เพื่อส่งสัญญาณ wake-up โดยไม่บล็อก loop หลัก

---

## 4. Main Loop (`main.py`)

จุดเริ่มต้นของระบบ — รับผิดชอบสร้าง runtime, รัน loop หลัก และจัดการสัญญาณ shutdown

### 4.1 CLI Arguments

| ตัวเลือก | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `--interval` | 900 | ระยะเวลาระหว่างแต่ละรอบ (วินาที) |
| `--skip-fetch` | false | ใช้ snapshot ล่าสุดแทนการดึงข้อมูลใหม่ |
| `--no-save` | false | ไม่บันทึกผลลง database (สำหรับ dry-run) |
| `--model` | `models/xgb_v1.json` | ที่อยู่ของไฟล์ XGBoost model |

### 4.2 Build Runtime

```python
def build_runtime() -> Runtime:
    return Runtime(
        orchestrator   = GoldTradingOrchestrator(),
        signal_engine  = XGBoostSignal(model_path="models/xgb_v1.json"),
        risk_manager   = RiskManager(),
        session_gate   = SessionGate(),
        notifier       = NotificationHub(discord=True, telegram=True),
        database       = RunDatabase(),
        watcher        = WatcherEngine(start_now=True),
    )
```

### 4.3 รอบการทำงาน (`run_analysis_once`)

1. ดึง `market_state` จาก `orchestrator.run()`
2. แปลงเป็น `feature_list[]` ผ่าน `extract_feature.get_xgboost_feature()`
3. ส่งให้ `signal_engine.predict()` + `signal_engine.predict_proba()`
4. ส่งสัญญาณ + confidence ให้ `core.evaluate()`
5. รับผลลัพธ์ → ส่งต่อให้ notification (เฉพาะ ALL PASS) และ database (ทุกกรณี)
6. รอครบ `interval` แล้ววนรอบใหม่

---

## 5. Data Engine (`data_engine/`)

### 5.1 `orchestrator.py` — `GoldTradingOrchestrator`

รับผิดชอบรวบรวมข้อมูลตลาดทุกชนิด:

| ข้อมูล | แหล่ง | Fallback Chain |
|---|---|---|
| Spot USD/oz | TwelveData | yfinance → gold-api |
| USD/THB | exchangerate-api | (cached 60s) |
| ราคาทองไทย (HSH 96.5% / Intergold) | MTS API (TradingView GLD965) | WebSocket Interceptor |
| OHLCV (8 timeframes) | TwelveData | yfinance |
| News (8 หมวด) | NewsAPI / RSS | static cache |
| Sentiment | FinBERT (local model) | — |

หลังดึงข้อมูลครบแล้ว จะประกอบเป็น `market_state: dict` ที่มีโครงสร้าง:

```python
{
    "meta": {"timestamp": "...", "tz": "Asia/Bangkok"},
    "data_quality": {...},
    "market_data": {"spot": ..., "usd_thb": ..., "thai_gold_sell": ..., ...},
    "technical_indicators": {"rsi": ..., "macd": ..., "ema_20": ..., ...},
    "news": {...},
    "portfolio": {"cash": ..., "gold_grams": ..., ...},
    "execution_quota": {"trades_today": ..., "remaining": ...}
}
```

### 5.2 `gold_interceptor_lite.py` — WebSocket Live Price

- เชื่อมต่อ `wss://ws.intergold.co.th:3000/socket.io/`
- REST fallback: Hua Seng Heng API (`apicheckpricev3.huasengheng.com`)
- เขียนไฟล์ `latest_gold_price.json` เฉพาะเมื่อราคาเปลี่ยน
- รันเป็น **background daemon thread** ที่ start ตอน orchestrator `__init__`
- มี auto-reconnect เมื่อ connection ขาด (exponential backoff)

### 5.3 `thailand_timestamp.py`

ฟังก์ชันช่วยจัดการเขตเวลา Asia/Bangkok:

| ฟังก์ชัน | คืนค่า |
|---|---|
| `get_thai_time()` | `pd.Timestamp.now(tz="Asia/Bangkok")` |
| `convert_index_to_thai_tz(df_index)` | DatetimeIndex แปลงจาก UTC → Asia/Bangkok |
| `to_thai_time(value)` | รับ str / unix / datetime → คืน Thai-tz timestamp |

---

## 6. Feature Extraction (`extract_feature.py`)

ฟังก์ชันแกน: `get_xgboost_feature(market_state, as_dataframe=False) -> list[float]`

ส่งออก **`feature_list[]` ขนาด 37 มิติ** ส่งให้ `signal.py` โดยตรง — **ไม่มี normalization, ไม่มี embedding** (XGBoost ทำงานบน feature scale ใดก็ได้)

### 6.1 ตารางสรุป Features

| กลุ่ม | จำนวน | รายละเอียด |
|---|---|---|
| **Time** | 5 | `hour`, `day_of_week`, `is_asian_session`, `is_london_session`, `is_ny_session` |
| **Price** | 6 | `spot_price`, `usd_thb`, `thai_sell`, `thai_buy`, `thai_spread`, `thai_mid` |
| **Momentum** | 3 | `price_change_pct_1c`, `price_change_pct_5c`, `price_change_pct_10c` |
| **RSI** | 2 | `rsi_value`, `rsi_signal_encoded` ∈ {-1, 0, 1} |
| **MACD** | 4 | `macd_line`, `macd_signal_line`, `macd_histogram`, `macd_crossover_encoded` ∈ {-2, -1, 0, 1, 2} |
| **Bollinger** | 5 | `bb_pct_b`, `bb_bandwidth`, `bb_signal_encoded`, `bb_dist_upper_pct`, `bb_dist_lower_pct` |
| **ATR** | 2 | `atr_value`, `atr_volatility_encoded` ∈ {0, 1, 2} |
| **Trend / EMA** | 5 | `ema_20`, `ema_50`, `ema_200`, `ema_spread_pct`, `trend_encoded` ∈ {-1, 0, 1} |
| **Sentiment** | 5 | avg sentiment ของหมวด: `thai_gold`, `gold_price`, `geopolitics`, `dollar_index`, `fed_policy` |
| **รวม** | **37** | |

### 6.2 การจัดการค่าหายไป (Missing Value Handling)

```python
# กฎประจำในไฟล์
if pd.isna(v) or np.isinf(v):
    v = 0.0
```

ทุก feature ถูกบังคับให้เป็น `float` และไม่มี `NaN` / `Inf` หลุดเข้าโมเดล

---

## 7. XGBoost Signal Engine (`signal.py`)

หัวใจการตัดสินใจของระบบ — แทนที่ Decision Loop เดิมทั้งหมดด้วย XGBoost Multi-class Classifier

### 7.1 โครงสร้างคลาส

```python
import joblib
import numpy as np
import xgboost as xgb

class XGBoostSignal:
    """
    Multi-class XGBoost classifier สำหรับสัญญาณทองคำ
    Class mapping: 0 = SELL, 1 = HOLD, 2 = BUY
    """

    LABEL_MAP = {0: "SELL", 1: "HOLD", 2: "BUY"}

    # Threshold ขั้นต่ำต่อ class (กรอง low-confidence)
    THRESHOLDS = {
        "BUY":  0.80,   # อ้างจาก xgboost_signal.py เดิม
        "SELL": 0.60,
        "HOLD": 0.00,   # default fallback
    }

    def __init__(self, model_path: str):
        try:
            self.model = joblib.load(model_path)   # หรือ xgb.Booster().load_model(...)
            self.loaded = True
        except Exception as e:
            self.model = None
            self.loaded = False
            self._error = str(e)

    def predict(self, feature_list: list[float]) -> str:
        """
        คืนค่าสัญญาณเป็น string: "BUY" | "HOLD" | "SELL"
        ถ้าโหลดโมเดลไม่ได้ → คืน "HOLD" เพื่อความปลอดภัย
        """
        if not self.loaded:
            return "HOLD"
        x = np.array(feature_list, dtype=np.float32).reshape(1, -1)
        class_idx = int(self.model.predict(x)[0])
        return self.LABEL_MAP[class_idx]

    def predict_proba(self, feature_list: list[float]) -> float:
        """
        คืน confidence score ของ class ที่ถูกเลือก (probability ∈ [0.0, 1.0])
        ถ้าโหลดโมเดลไม่ได้ → คืน 0.0
        """
        if not self.loaded:
            return 0.0
        x = np.array(feature_list, dtype=np.float32).reshape(1, -1)
        proba = self.model.predict_proba(x)[0]
        return float(np.max(proba))
```

### 7.2 อินพุต / เอาต์พุต

| ทิศทาง | รูปแบบ | คำอธิบาย |
|---|---|---|
| **อินพุต** | `feature_list: list[float]` ขนาด 37 | จาก `extract_feature.py` ตรง ๆ |
| **เอาต์พุต 1** | `predict() → str` | "BUY" / "HOLD" / "SELL" |
| **เอาต์พุต 2** | `predict_proba() → float` | confidence ของ class ที่ predict ได้ |

### 7.3 Fallback Strategy

| สถานการณ์ | พฤติกรรม |
|---|---|
| โหลดโมเดลไม่สำเร็จ | คืน `("HOLD", 0.0)` |
| feature_list มีขนาดไม่ครบ 37 | raise `ValueError` (fail-fast) |
| confidence < threshold ของ class นั้น | `core.py` จะ downgrade เป็น `HOLD` |

---

## 8. Core Decision (`core.py`)

ตัวกลางระหว่าง `signal.py` และ gates — ทำหน้าที่ **fan-out → fan-in** เพื่อรัน gates ขนานกัน

### 8.1 โครงสร้างหลัก

```python
import concurrent.futures as cf

class CoreDecision:
    def __init__(self, risk_manager: RiskManager, session_gate: SessionGate):
        self.risk = risk_manager
        self.gate = session_gate

    def evaluate(self, signal: str, confidence: float, market_state: dict) -> Decision:
        # 1) Fast-path: ถ้า signal เป็น HOLD อยู่แล้ว → ไม่ต้องเช็ค gate
        if signal == "HOLD":
            return Decision(final="HOLD", reason="model_hold", notify=False)

        # 2) เรียก gate ทั้งสองพร้อมกัน
        with cf.ThreadPoolExecutor(max_workers=2) as ex:
            f_risk    = ex.submit(self.risk.evaluate, signal, confidence, market_state)
            f_session = ex.submit(self.gate.evaluate, market_state)
            risk_res    = f_risk.result(timeout=2.0)
            session_res = f_session.result(timeout=2.0)

        # 3) รวมผล — ALL PASS = ทั้งสอง gate อนุมัติ
        all_pass = risk_res.passed and session_res.passed

        if all_pass:
            return Decision(
                final      = signal,         # คงสัญญาณเดิม
                confidence = confidence,
                entry      = risk_res.entry_price,
                sl         = risk_res.stop_loss,
                tp         = risk_res.take_profit,
                notify     = True,
            )
        else:
            return Decision(
                final      = "HOLD",
                reason     = risk_res.reason or session_res.reason,
                notify     = False,
            )
```

### 8.2 กฎการรวมผล

- **ALL PASS = YES** → คงสัญญาณเดิม (BUY / SELL), ส่ง notification, บันทึก database
- **อย่างใดอย่างหนึ่ง REJECT** → บังคับเป็น `HOLD`, **ข้าม notification**, แต่ยัง **บันทึก database** เสมอ

---

## 9. Concurrent Gates

### 9.1 `risk.py` — Risk Manager

ดัดแปลงจาก `Src/agent_core/core/risk.py` โดยตัด coupling กับ Decision Loop เดิมออก เหลือเฉพาะตรรกะการเช็คความเสี่ยง

#### 9.1.1 พารามิเตอร์

| Parameter | ค่า | หมายเหตุ |
|---|---|---|
| `min_trade_thb` | 1,400 | ขั้นต่ำขนาด position |
| `min_cash_thb` | 1,408 | 1,400 + ค่าธรรมเนียม 8 |
| `min_confidence` | 0.60 | สำหรับทั้ง BUY / SELL |
| `max_daily_loss_thb` | 500 | หยุดเทรดเมื่อขาดทุนถึง |
| `atr_multiplier` | 2.5 | สำหรับคำนวณ SL (v5) |
| `risk_reward_ratio` | 1.5 | TP = SL × 1.5 |
| `max_trade_risk_pct` | 0.20 | ความเสี่ยงสูงสุดต่อ trade |
| `max_daily_trades` | 6 | จำกัดจำนวนรอบ/วัน |

#### 9.1.2 ลำดับการเช็ค (Sequential within Gate)

| ลำดับ | การเช็ค | ผลถ้าไม่ผ่าน |
|---|---|---|
| 1 | **Spread Edge** — `edge_score ≥ 1.0` | REJECT BUY (spread กว้างเกินไป) |
| 2 | **Daily Loss** — `daily_loss < ฿500` | REJECT BUY |
| 3 | **Daily Quota** — `trades_today < 6` | REJECT BUY |
| 4 | **Confidence Tier** — critical ≥ 0.76 / defensive ≥ 0.68 / normal ≥ 0.60 | REJECT |
| 5 | **Cash Available** — `cash ≥ ฿1,408` | REJECT BUY |
| 6 | **Position Holding** — สำหรับ SELL ต้องมี `gold_grams > 0.0001` | REJECT SELL |
| 7 | **Profit Filter (SELL)** — `unrealized_pnl ≥ ฿10` | REJECT SELL (กำไรไม่คุ้ม spread) |
| 8 | **SL/TP Calculation** — `sl_dist = ATR × 2.5`, `tp_dist = sl_dist × 1.5` | (คำนวณเสริม) |

### 9.2 `session_gate.py` — Session Gate

ดัดแปลงจาก `Src/agent_core/core/session_gate.py` — เก็บเฉพาะส่วน window resolution + quota checking

#### 9.2.1 หน้าต่างการเทรด (Asia/Bangkok)

| Session | เวลา (Weekday) | กลุ่ม | โหมด |
|---|---|---|---|
| **night** | 00:00 – 01:59 | night_morning | Edge (เน้น setup ดี) |
| **dead zone** | **02:00 – 06:14** | — | **ห้ามเทรด** |
| **morning** | 06:15 – 11:59 | night_morning | Edge |
| **noon** | 12:00 – 17:59 | noon | Quota (ดัน volume กลางวัน) |
| **evening** | 18:00 – 23:59 | evening | Edge (vol สูง) |
| **weekend** | 09:30 – 17:30 | weekend | single window |

#### 9.2.2 ผลลัพธ์ของ Gate (`SessionGateResult`)

```python
@dataclass
class SessionGateResult:
    passed: bool                # อนุมัติให้เทรดได้หรือไม่
    session_id: str             # "night" | "morning" | "noon" | ...
    quota_group_id: str
    quota_urgent: bool          # True ถ้าเหลือเวลา ≤ 15 นาที
    mode: str                   # "edge" | "quota"
    suggested_min_confidence: float
    reason: str | None          # เหตุผลถ้า REJECT
```

#### 9.2.3 กฎการ REJECT

- อยู่ใน **dead zone** (02:00–06:14) → REJECT ทุก signal
- ใน window แต่ **quota ใช้หมด** (6/6) → REJECT BUY
- `mode == "edge"` แต่ confidence < 0.62 → REJECT
- `mode == "quota"` แต่ confidence < 0.58 → REJECT

---

## 10. Notification (`notification.py`)

รวม **Discord Webhook** + **Telegram Bot API** ไว้ในโมดูลเดียว

### 10.1 เงื่อนไขการส่ง

| สถานการณ์ | ส่ง? |
|---|---|
| `ALL PASS = YES` (BUY / SELL ผ่าน gate ครบ) | ✅ ส่งทุก channel |
| `HOLD` (ทั้งจากโมเดล หรือถูก gate downgrade) | ❌ ข้าม (default) |
| `DISCORD_NOTIFY_HOLD=true` | ✅ ส่งแม้เป็น HOLD |

### 10.2 รูปแบบข้อความ (Discord Embed)

```
┌─────────────────────────────────────────┐
│ 🟢 SIGNAL: BUY                          │
│ ───────────────────────────────────     │
│ Confidence: ████████░░ 0.82             │
│                                         │
│ Entry:  ฿58,420 / baht                  │
│ SL:     ฿58,180  (-฿240, ATR×2.5)       │
│ TP:     ฿58,780  (+฿360, RR 1.5)        │
│                                         │
│ Spot USD/oz:  $2,651.30                 │
│ USD/THB:      33.95                     │
│ Thai Sell:    ฿58,420                   │
│                                         │
│ Session: noon (quota mode)              │
│ Trades today: 3 / 6                     │
└─────────────────────────────────────────┘
```

### 10.3 Toggle / Configuration

| Env Var | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `DISCORD_WEBHOOK_URL` | (จำเป็น) | URL ของ Webhook |
| `DISCORD_NOTIFY_HOLD` | false | เปิดส่ง HOLD |
| `DISCORD_NOTIFY_MIN_CONF` | 0.60 | กรองข้อความตาม confidence |
| `TELEGRAM_BOT_TOKEN` | (จำเป็น) | Bot token |
| `TELEGRAM_CHAT_ID` | (จำเป็น) | Chat / Group ID ที่จะส่ง |

---

## 11. Database (`database.py`)

PostgreSQL — ใช้ `psycopg2.pool.ThreadedConnectionPool(min=1, max=5)` เหมาะกับ Render free tier

### 11.1 หลักการสำคัญ

> **บันทึกทุกครั้ง** ไม่ว่าผลลัพธ์จะเป็น YES (BUY/SELL) หรือ HOLD — เพื่อสามารถวิเคราะห์ย้อนหลังว่ารอบไหนถูก gate กรองออก เพราะอะไร

### 11.2 Schema

#### ตาราง `runs` (ทุกรอบ)

| คอลัมน์ | ชนิด | หมายเหตุ |
|---|---|---|
| `id` | SERIAL PK | |
| `run_at` | TIMESTAMPTZ | เวลาเริ่มรอบ |
| `signal` | VARCHAR(8) | "BUY" / "SELL" / "HOLD" (final หลัง gate) |
| `model_signal` | VARCHAR(8) | สัญญาณดิบจาก XGBoost ก่อน gate |
| `confidence` | NUMERIC(4,3) | 0.000 – 1.000 |
| `entry_price_thb` | NUMERIC(10,2) | NULL ถ้า HOLD |
| `stop_loss` | NUMERIC(10,2) | |
| `take_profit` | NUMERIC(10,2) | |
| `usd_thb_rate` | NUMERIC(8,4) | |
| `gold_price_thb` | NUMERIC(10,2) | |
| `rsi` | NUMERIC(6,2) | |
| `macd_line` | NUMERIC(10,4) | |
| `macd_histogram` | NUMERIC(10,4) | |
| `bb_pct_b` | NUMERIC(6,4) | |
| `atr_thb` | NUMERIC(8,4) | |
| `is_weekend` | BOOLEAN | |
| `gate_reject_reason` | TEXT | NULL ถ้าไม่ถูก reject |
| `data_quality` | JSONB | snapshot ของ data quality |
| `feature_vector` | JSONB | เก็บ feature_list[37] ทั้งชุดเพื่อ replay/debug |
| `market_snapshot` | JSONB | market_state แบบย่อ |

#### ตาราง `portfolio_snapshots`

| คอลัมน์ | ชนิด |
|---|---|
| `id` | SERIAL PK |
| `snapshot_at` | TIMESTAMPTZ |
| `cash_balance` | NUMERIC(10,2) |
| `gold_grams` | NUMERIC(10,4) |
| `cost_basis_thb` | NUMERIC(10,2) |
| `unrealized_pnl` | NUMERIC(10,2) |
| `trades_today` | SMALLINT |

#### ตาราง `trade_log` (เฉพาะ YES)

| คอลัมน์ | ชนิด |
|---|---|
| `id` | SERIAL PK |
| `run_id` | INT FK → runs.id |
| `action` | VARCHAR(4) — "BUY" / "SELL" |
| `executed_at` | TIMESTAMPTZ |
| `price_thb` | NUMERIC(10,2) |
| `gold_grams` | NUMERIC(10,4) |
| `amount_thb` | NUMERIC(10,2) |
| `pnl_thb` | NUMERIC(10,2) — NULL สำหรับ BUY |
| `pnl_pct` | NUMERIC(6,3) |

### 11.3 Pseudo-code การบันทึก

```python
def persist(decision: Decision, market_state: dict, feature_list: list[float]):
    run_id = db.insert_run(
        signal       = decision.final,         # บันทึกเสมอ
        model_signal = decision.model_signal,
        confidence   = decision.confidence,
        feature_vector = feature_list,
        gate_reject_reason = decision.reason,  # NULL ถ้า ALL PASS
        market_snapshot = compact(market_state),
    )
    if decision.notify:                        # YES path เท่านั้น
        db.insert_trade_log(run_id, decision)
    db.upsert_portfolio_snapshot()
```

---

## 12. โครงสร้างไฟล์ที่แนะนำสำหรับ `Src2/`

```
Src2/
├── about-main.md                ← เอกสารฉบับนี้
├── main.py                      ← entry point + loop หลัก
├── watcher.py                   ← background trigger
├── data_engine/
│   ├── __init__.py
│   ├── orchestrator.py          ← GoldTradingOrchestrator
│   ├── gold_interceptor_lite.py ← WebSocket
│   ├── thailand_timestamp.py    ← timezone helpers
│   └── extract_feature.py       ← get_xgboost_feature() → feature_list[37]
├── models/
│   ├── xgb_v1.json              ← XGBoost serialized model
│   └── feature_schema.json      ← schema 37 มิติ
├── signal.py                    ← XGBoostSignal class
├── core.py                      ← CoreDecision (fan-out gates)
├── risk.py                      ← RiskManager
├── session_gate.py              ← SessionGate
├── notification.py              ← Discord + Telegram
├── database.py                  ← PostgreSQL pool + insert helpers
└── tests/
    ├── test_extract_feature.py
    ├── test_signal_engine.py
    ├── test_core_concurrent.py
    ├── test_risk.py
    └── test_session_gate.py
```

---

## 13. ตัวชี้วัดความสำเร็จของระบบ

| Metric | เป้าหมาย |
|---|---|
| Latency / รอบ | < 200 ms (ไม่รวม data fetch) |
| Win Rate (BT 90 วัน) | ≥ 55% |
| Sharpe Ratio | ≥ 1.2 |
| Max Drawdown | ≤ 8% |
| Daily Loss Limit Hit | ≤ 1 ครั้ง / สัปดาห์ |
| Uptime ของ WatcherEngine | ≥ 99.5% |
| ความสมบูรณ์ของ DB log | 100% (ทุกรอบต้องมี record) |

---

## 14. สรุป

ระบบ v2 นี้ออกแบบให้ **เบากว่า, เร็วกว่า, ทำซ้ำได้แม่นยำกว่า** v1 อย่างชัดเจน โดย:

1. **ตัดโมเดลภาษาออกทั้งหมด** — ไม่มี API call ภายนอก, ไม่มี token cost, ไม่มี non-determinism
2. **ใช้ XGBoost เป็นแกนตัดสินใจเดียว** — ผ่าน `predict()` + `predict_proba()` ที่ตีความง่าย
3. **คงโครงสร้าง Risk + Session Gate เดิม** — ของพิสูจน์แล้วทั้งคู่ ใช้ต่อไม่แก้
4. **บังคับ concurrent evaluation** — ลด latency ของ gate phase ลงครึ่งหนึ่ง
5. **Database-first logging** — ทุกรอบบันทึก รวมถึง feature vector → ใช้ replay/retrain ได้
6. **Notification เลือกส่งเฉพาะ YES** — ลด noise ใน Discord/Telegram

ผลลัพธ์: ระบบ trading ที่ deterministic, auditable, และ scalable พร้อมต่อยอดเป็น production service ได้ทันที

---

*จัดทำโดย: Senior Algorithmic Trading Engineer & Data Scientist Team*
*โครงการ CN240 — Data Science for Signal Processing, Thammasat University*
