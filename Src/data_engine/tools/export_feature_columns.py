"""
export_feature_columns.py — สร้าง feature_columns JSON 2 ชุด
สำหรับ BUY/SELL XGBoost Models

Output:
    agent_core/config/feature_columns_xauusd.json  — ทองโลก (XAU/USD)
    agent_core/config/feature_columns_thai.json    — ทองไทย (HSH/THB)

วิธีรัน:
    cd Src
    python -m data_engine.tools.export_feature_columns
"""

import json
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# ชุดที่ 1 — ทองโลก XAU/USD
# prefix: xauusd_ / xau_ / usdthb_
# ──────────────────────────────────────────────────────────────────────────────
FEATURE_COLUMNS_XAUUSD = {
    "symbol":      "XAU/USD",
    "source":      "yfinance / TwelveData",
    "unit":        "USD per troy oz",
    "n_features":  26,
    "description": "26 ML features สำหรับทองโลก ใช้กับ BUY/SELL XGBoost model",
    "features": [
        # ── OHLC raw (4) ──────────────────────────────────────────────────────
        {
            "name":    "xauusd_open",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "open price (USD/oz)",
            "note":    "ราคาเปิด XAU/USD ต่อแท่ง — baseline ราคา"
        },
        {
            "name":    "xauusd_high",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "high price (USD/oz)",
            "note":    "ราคาสูงสุด"
        },
        {
            "name":    "xauusd_low",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "low price (USD/oz)",
            "note":    "ราคาต่ำสุด"
        },
        {
            "name":    "xauusd_close",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "close price (USD/oz)",
            "note":    "ราคาปิด — ใช้คำนวณ feature อื่นๆ"
        },
        # ── Returns (3) ───────────────────────────────────────────────────────
        {
            "name":    "xauusd_ret1",
            "group":   "returns",
            "dtype":   "float",
            "formula": "(close[t] - close[t-1]) / close[t-1]",
            "note":    "momentum 1 bar — บอกทิศทางราคาระยะสั้น"
        },
        {
            "name":    "xauusd_ret3",
            "group":   "returns",
            "dtype":   "float",
            "formula": "(close[t] - close[t-3]) / close[t-3]",
            "note":    "momentum 3 bars — บอก momentum ระยะสั้นกว่า"
        },
        {
            "name":    "usdthb_ret1",
            "group":   "returns",
            "dtype":   "float",
            "formula": "(usdthb[t] - usdthb[t-1]) / usdthb[t-1]",
            "note":    "return USD/THB 1 bar — ทิศทางค่าเงินผลกับต้นทุนจริง"
        },
        # ── MACD (2) ──────────────────────────────────────────────────────────
        {
            "name":    "xau_macd_delta1",
            "group":   "macd",
            "dtype":   "float",
            "formula": "macd_hist[t] - macd_hist[t-1]",
            "note":    "histogram velocity — momentum กำลังเร่งหรือชะลอ"
        },
        {
            "name":    "xauusd_macd_hist",
            "group":   "macd",
            "dtype":   "float",
            "formula": "EMA(12) - EMA(26) - signal(9)",
            "note":    "histogram absolute — ระดับ momentum ปัจจุบัน"
        },
        # ── EMA Distance (3) ──────────────────────────────────────────────────
        {
            "name":    "xauusd_dist_ema21",
            "group":   "ema_distance",
            "dtype":   "float",
            "formula": "(close - ema21) / ema21",
            "note":    "ระยะห่างจาก EMA21 เป็น % — mean-reversion signal"
        },
        {
            "name":    "xauusd_dist_ema50",
            "group":   "ema_distance",
            "dtype":   "float",
            "formula": "(close - ema50) / ema50",
            "note":    "ระยะห่างจาก EMA50 เป็น % — trend distance"
        },
        {
            "name":    "usdthb_dist_ema21",
            "group":   "ema_distance",
            "dtype":   "float",
            "formula": "(usdthb - usdthb_ema21) / usdthb_ema21",
            "note":    "ระยะห่าง USD/THB จาก EMA21 — forex trend context"
        },
        # ── Trend (1) ─────────────────────────────────────────────────────────
        {
            "name":    "trend_regime",
            "group":   "trend",
            "dtype":   "int",
            "formula": "1 if ema21 > ema50*(1+0.001) else -1 if ema21 < ema50*(1-0.001) else 0",
            "note":    "1=uptrend, 0=sideways, -1=downtrend (±0.1% band)"
        },
        # ── RSI (2) ───────────────────────────────────────────────────────────
        {
            "name":    "xauusd_rsi14",
            "group":   "rsi",
            "dtype":   "float",
            "range":   "0-100",
            "formula": "RSI(14) Wilder smoothing",
            "note":    "overbought >70, oversold <30"
        },
        {
            "name":    "xau_rsi_delta1",
            "group":   "rsi",
            "dtype":   "float",
            "formula": "rsi[t] - rsi[t-1]",
            "note":    "RSI velocity — กำลังเพิ่มหรือลด"
        },
        # ── Volatility (3) ────────────────────────────────────────────────────
        {
            "name":    "xauusd_atr_norm",
            "group":   "volatility",
            "dtype":   "float",
            "formula": "ATR(14) / close",
            "note":    "normalized volatility — scale-free เทียบข้ามช่วงราคาได้"
        },
        {
            "name":    "XAU_atr_rank50",
            "group":   "volatility",
            "dtype":   "float",
            "range":   "0-1",
            "formula": "percentile_rank(ATR(14), window=50)",
            "note":    "ATR relative rank 50 bars — ตลาดผันผวนมากกว่าปกติไหม"
        },
        {
            "name":    "xauusd_bb_width",
            "group":   "volatility",
            "dtype":   "float",
            "formula": "(bb_upper - bb_lower) / bb_middle",
            "note":    "Bollinger Band width — squeeze=ต่ำ, expansion=สูง"
        },
        # ── Candle Shape (2) ──────────────────────────────────────────────────
        {
            "name":    "wick_bias",
            "group":   "candle_shape",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "(upper_wick - lower_wick) / denom = (high - low).replace(0, 1e-6)",
            "note":    ">0=selling pressure, <0=buying pressure"
        },
        {
            "name":    "body_strength",
            "group":   "candle_shape",
            "dtype":   "float",
            "range":   "0-1",
            "formula": "|close - open| / (high - low)",
            "note":    "0=doji, 1=full body candle — conviction of move"
        },
        # ── Time Cyclical (5) ─────────────────────────────────────────────────
        {
            "name":    "hour_sin",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "sin(2π × hour / 24)",
            "note":    "เวลาของวัน (cyclical) — ไม่มี discontinuity ที่ midnight"
        },
        {
            "name":    "hour_cos",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "cos(2π × hour / 24)",
            "note":    "คู่กับ hour_sin ทำให้โมเดลรู้ตำแหน่งเวลาในวงกลม"
        },
        {
            "name":    "minute_sin",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "sin(2π × minute / 60)",
            "note":    "ตำแหน่งภายในชั่วโมง"
        },
        {
            "name":    "minute_cos",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "cos(2π × minute / 60)",
            "note":    "คู่กับ minute_sin"
        },
        {
            "name":    "session_progress",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "0-1",
            "formula": "clamp((hour - session_start) * 60 + minute) / session_length_min, 0, 1)",
            "note":    "0=เปิด session, 1=ปิด session — บอก LLM ว่าเหลือเวลาเท่าไหร่"
        },
        # ── Calendar (1) ──────────────────────────────────────────────────────
        {
            "name":    "day_of_week",
            "group":   "calendar",
            "dtype":   "int",
            "range":   "0-4",
            "formula": "index.dayofweek",
            "note":    "0=Monday … 4=Friday — pattern รายวันในสัปดาห์"
        },
    ]
}

# ──────────────────────────────────────────────────────────────────────────────
# ชุดที่ 2 — ทองไทย HSH/THB
# prefix เปลี่ยนจาก xauusd_ → thai_  และ usdthb_ features ถูกแทนที่
# ──────────────────────────────────────────────────────────────────────────────
FEATURE_COLUMNS_THAI = {
    "symbol":      "HSH/THB",
    "source":      "Hua Seng Heng WebSocket / Mock_HSH_OHLC.csv",
    "unit":        "THB per baht weight (บาททอง)",
    "n_features":  26,
    "description": "26 ML features สำหรับทองไทย (ออม NOW) ใช้กับ BUY/SELL XGBoost model",
    "features": [
        # ── OHLC raw (4) ──────────────────────────────────────────────────────
        {
            "name":    "thai_open",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "open price (THB/baht_weight)",
            "note":    "ราคาเปิดทองไทย — หน่วย THB ต่อ 1 บาททอง"
        },
        {
            "name":    "thai_high",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "high price (THB/baht_weight)",
            "note":    "ราคาสูงสุด"
        },
        {
            "name":    "thai_low",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "low price (THB/baht_weight)",
            "note":    "ราคาต่ำสุด"
        },
        {
            "name":    "thai_close",
            "group":   "ohlc",
            "dtype":   "float",
            "formula": "close price (THB/baht_weight)",
            "note":    "ราคาปิด — ใช้คำนวณ feature อื่นๆ"
        },
        # ── Returns (3) ───────────────────────────────────────────────────────
        {
            "name":    "thai_ret1",
            "group":   "returns",
            "dtype":   "float",
            "formula": "(close[t] - close[t-1]) / close[t-1]",
            "note":    "momentum 1 bar ในหน่วย THB"
        },
        {
            "name":    "thai_ret3",
            "group":   "returns",
            "dtype":   "float",
            "formula": "(close[t] - close[t-3]) / close[t-3]",
            "note":    "momentum 3 bars ในหน่วย THB"
        },
        {
            "name":    "xauusd_ret1",
            "group":   "returns",
            "dtype":   "float",
            "formula": "(xauusd_close[t] - xauusd_close[t-1]) / xauusd_close[t-1]",
            "note":    "return ทองโลก 1 bar — ใช้เป็น external signal ให้โมเดลรู้ทิศทางตลาดโลก"
        },
        # ── MACD (2) ──────────────────────────────────────────────────────────
        {
            "name":    "thai_macd_delta1",
            "group":   "macd",
            "dtype":   "float",
            "formula": "thai_macd_hist[t] - thai_macd_hist[t-1]",
            "note":    "histogram velocity ของทองไทย"
        },
        {
            "name":    "thai_macd_hist",
            "group":   "macd",
            "dtype":   "float",
            "formula": "EMA(12) - EMA(26) - signal(9)  คำนวณบนราคา THB",
            "note":    "histogram absolute ของทองไทย"
        },
        # ── EMA Distance (3) ──────────────────────────────────────────────────
        {
            "name":    "thai_dist_ema21",
            "group":   "ema_distance",
            "dtype":   "float",
            "formula": "(thai_close - thai_ema21) / thai_ema21",
            "note":    "ระยะห่างจาก EMA21 ของทองไทย"
        },
        {
            "name":    "thai_dist_ema50",
            "group":   "ema_distance",
            "dtype":   "float",
            "formula": "(thai_close - thai_ema50) / thai_ema50",
            "note":    "ระยะห่างจาก EMA50 ของทองไทย"
        },
        {
            "name":    "xauusd_dist_ema21",
            "group":   "ema_distance",
            "dtype":   "float",
            "formula": "(xauusd_close - xauusd_ema21) / xauusd_ema21",
            "note":    "ระยะห่าง EMA21 ของทองโลก — cross-market signal"
        },
        # ── Trend (1) ─────────────────────────────────────────────────────────
        {
            "name":    "trend_regime",
            "group":   "trend",
            "dtype":   "int",
            "formula": "1 if thai_ema21 > thai_ema50*(1+0.001) else -1 if thai_ema21 < thai_ema50*(1-0.001) else 0",
            "note":    "1=uptrend, 0=sideways, -1=downtrend คำนวณบนราคา THB"
        },
        # ── RSI (2) ───────────────────────────────────────────────────────────
        {
            "name":    "thai_rsi14",
            "group":   "rsi",
            "dtype":   "float",
            "range":   "0-100",
            "formula": "RSI(14) คำนวณบนราคา THB",
            "note":    "overbought >70, oversold <30"
        },
        {
            "name":    "thai_rsi_delta1",
            "group":   "rsi",
            "dtype":   "float",
            "formula": "thai_rsi14[t] - thai_rsi14[t-1]",
            "note":    "RSI velocity ทองไทย"
        },
        # ── Volatility (3) ────────────────────────────────────────────────────
        {
            "name":    "thai_atr_norm",
            "group":   "volatility",
            "dtype":   "float",
            "formula": "ATR(14) / thai_close  (THB)",
            "note":    "normalized volatility ทองไทย"
        },
        {
            "name":    "thai_atr_rank50",
            "group":   "volatility",
            "dtype":   "float",
            "range":   "0-1",
            "formula": "percentile_rank(thai_ATR(14), window=50)",
            "note":    "ATR relative rank 50 bars ทองไทย"
        },
        {
            "name":    "thai_bb_width",
            "group":   "volatility",
            "dtype":   "float",
            "formula": "(bb_upper - bb_lower) / bb_middle  คำนวณบน THB",
            "note":    "Bollinger Band width ทองไทย"
        },
        # ── Candle Shape (2) ──────────────────────────────────────────────────
        {
            "name":    "wick_bias",
            "group":   "candle_shape",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "(upper_wick - lower_wick) / denom = (high - low).replace(0, 1e-6)",
            "note":    "เหมือนกันทั้งสองชุด — shape ไม่ขึ้นกับ unit"
        },
        {
            "name":    "body_strength",
            "group":   "candle_shape",
            "dtype":   "float",
            "range":   "0-1",
            "formula": "|close - open| / (high - low)",
            "note":    "เหมือนกันทั้งสองชุด"
        },
        # ── Time Cyclical (5) ─────────────────────────────────────────────────
        {
            "name":    "hour_sin",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "sin(2π × hour / 24)",
            "note":    "เหมือนกันทั้งสองชุด"
        },
        {
            "name":    "hour_cos",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "cos(2π × hour / 24)",
            "note":    "เหมือนกันทั้งสองชุด"
        },
        {
            "name":    "minute_sin",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "sin(2π × minute / 60)",
            "note":    "เหมือนกันทั้งสองชุด"
        },
        {
            "name":    "minute_cos",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "-1 to 1",
            "formula": "cos(2π × minute / 60)",
            "note":    "เหมือนกันทั้งสองชุด"
        },
        {
            "name":    "session_progress",
            "group":   "time_cyclic",
            "dtype":   "float",
            "range":   "0-1",
            "formula": "clamp((hour - 9) * 60 + minute) / (17*60), 0, 1)",
            "note":    "session ทองไทย 09:00-17:00 (ออม NOW)"
        },
        # ── Calendar (1) ──────────────────────────────────────────────────────
        {
            "name":    "day_of_week",
            "group":   "calendar",
            "dtype":   "int",
            "range":   "0-4",
            "formula": "index.dayofweek",
            "note":    "0=Monday … 4=Friday"
        },
    ]
}


# ──────────────────────────────────────────────────────────────────────────────
# Export JSON
# ──────────────────────────────────────────────────────────────────────────────

def export_feature_columns(output_dir: str = "agent_core/config") -> None:
    """
    สร้างไฟล์ JSON 2 ชุดไปยัง output_dir

    Args:
        output_dir: path ที่จะบันทึก JSON (relative จาก Src/)
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # ทองโลก
    xauusd_file = out_path / "feature_columns_xauusd.json"
    with open(xauusd_file, "w", encoding="utf-8") as f:
        json.dump(FEATURE_COLUMNS_XAUUSD, f, ensure_ascii=False, indent=2)
    print(f"✅ สร้างแล้ว: {xauusd_file}  ({len(FEATURE_COLUMNS_XAUUSD['features'])} features)")

    # ทองไทย
    thai_file = out_path / "feature_columns_thai.json"
    with open(thai_file, "w", encoding="utf-8") as f:
        json.dump(FEATURE_COLUMNS_THAI, f, ensure_ascii=False, indent=2)
    print(f"✅ สร้างแล้ว: {thai_file}  ({len(FEATURE_COLUMNS_THAI['features'])} features)")

    # ตรวจสอบ
    assert len(FEATURE_COLUMNS_XAUUSD["features"]) == 26, "xauusd ต้องมี 26 features"
    assert len(FEATURE_COLUMNS_THAI["features"])   == 26, "thai ต้องมี 26 features"

    xauusd_names = [f["name"] for f in FEATURE_COLUMNS_XAUUSD["features"]]
    thai_names   = [f["name"] for f in FEATURE_COLUMNS_THAI["features"]]

    # features ที่เหมือนกันทั้งสองชุด (time + shape)
    shared = set(xauusd_names) & set(thai_names)
    print(f"\n📋 Shared features ({len(shared)}): {sorted(shared)}")
    print(f"📋 XAUUSD-only ({len(set(xauusd_names)-shared)}): {sorted(set(xauusd_names)-shared)}")
    print(f"📋 Thai-only   ({len(set(thai_names)-shared)}): {sorted(set(thai_names)-shared)}")


# ──────────────────────────────────────────────────────────────────────────────
# Helper — โหลด feature names กลับมาใช้ใน pipeline
# ──────────────────────────────────────────────────────────────────────────────

def load_feature_columns(symbol: str = "xauusd",
                         config_dir: str = "agent_core/config") -> list[str]:
    """
    โหลด feature column names จาก JSON กลับมาเป็น list

    Args:
        symbol: "xauusd" หรือ "thai"

    Returns:
        list[str] — ชื่อ features ตามลำดับ พร้อมส่งเข้า X = df[feature_cols]

    ตัวอย่าง:
        cols = load_feature_columns("xauusd")
        X = features_df[cols]
        prob_buy = buy_model.predict_proba(X)[:, 1]
    """
    fname = f"feature_columns_{symbol}.json"
    fpath = Path(config_dir) / fname

    if not fpath.exists():
        raise FileNotFoundError(
            f"ไม่พบ {fpath} — รัน export_feature_columns() ก่อน"
        )

    with open(fpath, encoding="utf-8") as f:
        data = json.load(f)

    return [feat["name"] for feat in data["features"]]


# ──────────────────────────────────────────────────────────────────────────────
# ML Feature Column names สำหรับ Thai (ใช้ใน indicators.py เพิ่มเติม)
# ──────────────────────────────────────────────────────────────────────────────
ML_FEATURE_COLUMNS_THAI = [f["name"] for f in FEATURE_COLUMNS_THAI["features"]]


if __name__ == "__main__":
    export_feature_columns()