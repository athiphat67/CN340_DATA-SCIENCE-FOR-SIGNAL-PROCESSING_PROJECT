import json
import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Union


def build_feature_dataset(json_file_path, csv_file_path):
    """
    อ่านไฟล์ JSON ล่าสุด สกัดเฉพาะ Feature ที่จำเป็นสำหรับ ML
    พร้อมเพิ่ม Time Features และ Trading Sessions
    แล้วนำไปต่อท้าย (Append) ในตาราง CSV
    """
    if not os.path.exists(json_file_path):
        print(f"❌ ไม่พบไฟล์ {json_file_path}")
        print(
            "💡 คำแนะนำ: รัน python orchestrator.py หรือ conJSON.py เพื่อสร้าง latest.json ก่อน"
        )
        return

    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # ==========================================
    # 1. TIME FEATURES & TRADING SESSIONS
    # ==========================================
    timestamp_str = data["meta"]["generated_at"]
    dt = pd.to_datetime(timestamp_str)

    hour = dt.hour
    day_of_week = dt.dayofweek  # 0=วันจันทร์, 6=วันอาทิตย์

    # รอบเวลาตลาดทองคำ (เวลาไทย UTC+7)
    # Asian Session (โตเกียว): 07:00 - 15:00
    # London Session (ยุโรป): 15:00 - 23:00
    # New York Session (อเมริกา): 20:00 - 04:00 (ทับซ้อนกับลอนดอนช่วง 20:00-23:00 ซึ่งราคามักจะสวิงแรงสุด)
    is_asian = 1 if 7 <= hour < 15 else 0
    is_london = 1 if 15 <= hour < 23 else 0
    is_ny = 1 if (20 <= hour <= 23) or (0 <= hour < 4) else 0

    # ==========================================
    # 2. MARKET & TECHNICAL FEATURES
    # ==========================================
    market = data["market_data"]
    tech = data["technical_indicators"]

    # Categorical Encoding (แปลงข้อความเป็นตัวเลขให้ ML)
    trend_map = {"uptrend": 1, "downtrend": -1, "sideways": 0}

    features = {
        # --- Time ---
        "datetime": timestamp_str,
        "hour": hour,
        "day_of_week": day_of_week,
        "is_asian_session": is_asian,
        "is_london_session": is_london,
        "is_ny_session": is_ny,
        # --- Price Data ---
        "spot_price": market["spot_price_usd"]["price_usd_per_oz"],
        "usd_thb": market["forex"]["usd_thb"],
        "thai_gold_sell": market["thai_gold_thb"]["sell_price_thb"],
        # --- Indicators ---
        "rsi": tech["rsi"]["value"],
        "macd_hist": tech["macd"]["histogram"],
        "bollinger_pct_b": tech["bollinger"]["pct_b"],
        "bollinger_bw": tech["bollinger"]["bandwidth"],
        "atr": tech["atr"]["value"],
        "trend_encoded": trend_map.get(tech["trend"]["trend"], 0),
        "ema_20": tech["trend"]["ema_20"],
        "sma_200": tech["trend"]["sma_200"],
    }

    # ==========================================
    # 3. SENTIMENT FEATURES (NLP)
    # ==========================================
    news_cats = data["news"]["by_category"]
    target_categories = [
        "thai_gold_market",
        "gold_price",
        "geopolitics",
        "dollar_index",
        "fed_policy",
    ]

    for cat in target_categories:
        cat_data = news_cats.get(cat, {})
        articles = cat_data.get("articles", [])

        if articles:
            # หาค่าเฉลี่ย Sentiment ของแต่ละหมวด (-1.0 ถึง 1.0)
            avg_sent = sum(a.get("sentiment_score", 0.0) for a in articles) / len(
                articles
            )
        else:
            avg_sent = 0.0

        features[f"sentiment_{cat}"] = round(avg_sent, 4)

    # ==========================================
    # 4. EXPORT TO CSV
    # ==========================================
    df_new = pd.DataFrame([features])

    os.makedirs(os.path.dirname(csv_file_path), exist_ok=True)
    file_exists = os.path.isfile(csv_file_path)

    # บันทึกแบบ Append (ต่อท้ายเรื่อยๆ)
    df_new.to_csv(
        csv_file_path, mode="a", header=not file_exists, index=False, encoding="utf-8"
    )

    print(f"✅ สกัด Features ลง {os.path.basename(csv_file_path)} สำเร็จ!")
    print(
        f"   📊 Spot: {features['spot_price']} | RSI: {features['rsi']} | NY Session: {bool(features['is_ny_session'])}"
    )



# ==========================================
# SHARED HELPERS (ใช้ร่วมกันทั้ง 2 functions)
# ==========================================

def _extract_time_features(timestamp_str: str) -> dict:
    """สกัด Time & Session Features จาก timestamp string"""
    dt = pd.to_datetime(timestamp_str)
    hour = dt.hour
    return {
        "hour":              hour,
        "day_of_week":       dt.dayofweek,  # 0=จันทร์, 6=อาทิตย์
        "is_asian_session":  int(7  <= hour < 15),
        "is_london_session": int(15 <= hour < 23),
        "is_ny_session":     int((20 <= hour <= 23) or (0 <= hour < 4)),
    }


def _extract_sentiment_features(news_by_category: dict) -> dict:
    """สกัด Sentiment เฉลี่ยแยกตาม Category ที่มีผลต่อทองคำโดยตรง"""
    target_categories = [
        "thai_gold_market",
        "gold_price",
        "geopolitics",
        "dollar_index",
        "fed_policy",
    ]
    feats = {}
    for cat in target_categories:
        cat_data = news_by_category.get(cat, {})
        # รองรับทั้ง format เก่า (list) และ format ใหม่ (dict with 'articles' key)
        articles = cat_data if isinstance(cat_data, list) else cat_data.get("articles", [])
        if articles:
            avg = sum(a.get("sentiment_score", 0.0) for a in articles) / len(articles)
        else:
            avg = 0.0
        feats[f"sentiment_{cat}"] = round(avg, 4)
    return feats


def get_xgboost_feature(
    data: Union[dict, str],
    as_dataframe: bool = False,
) -> Union[dict, pd.DataFrame]:
    """
    สกัด Feature Set ที่ครบสมบูรณ์สำหรับ XGBoost Buy/Sell Models
    (ออกแบบให้ตรงกับ hyperparams ใน finetune_dual_results.json)

    Parameters
    ----------
    data : dict | str
        - dict  → payload จาก orchestrator.run() โดยตรง (เร็วกว่า ไม่ต้อง I/O)
        - str   → path ของ latest.json (อ่านไฟล์ให้อัตโนมัติ)
    as_dataframe : bool
        - False → คืน dict  (ใช้กับ model.predict(pd.DataFrame([feat])))
        - True  → คืน pd.DataFrame 1 แถว (ใช้กับ pipeline ที่ต้องการ DataFrame)

    Returns
    -------
    dict หรือ pd.DataFrame ที่มี features เฉพาะตัวเลข พร้อม predict ได้ทันที

    Feature Groups
    --------------
    [1] Time (5)         : hour, day_of_week, session flags x3
    [2] Price (6)        : spot, usd_thb, thai sell/buy/spread/mid
    [3] Momentum (3)     : 1-candle, 5-candle %chg, 10-candle range %
    [4] RSI (2)          : value + signal encoded
    [5] MACD (4)         : line, signal_line, histogram, crossover encoded
    [6] Bollinger (5)    : pct_b, bandwidth, signal encoded, upper/lower distance %
    [7] ATR (2)          : value, volatility_level encoded
    [8] Trend/EMA (5)    : ema_20, ema_50, ema_200, ema_spread %, trend encoded
    [9] Sentiment (5)    : avg score per news category
    ─────────────────────────────────────────────────────────
    Total: 37 features (ทั้งหมดเป็นตัวเลข ไม่มี string / NaN)

    Notes
    -----
    - `sma_200` ใน build_feature_dataset เดิมนั้น key ผิด → indicators.py ใช้ `ema_200`
      ฟังก์ชันนี้แก้ไขเป็น ema_200 ที่ถูกต้องแล้ว
    - sell_model มี scale_pos_weight=2.67 (imbalanced มากกว่า buy_model=1.43)
      ดังนั้น threshold ที่เหมาะสมของ sell อาจต้องปรับสูงกว่า 0.5
    """
    # ── โหลดข้อมูล ─────────────────────────────────────────────────────────────
    if isinstance(data, str):
        if not os.path.exists(data):
            raise FileNotFoundError(f"❌ ไม่พบไฟล์ {data}")
        with open(data, "r", encoding="utf-8") as f:
            data = json.load(f)

    market = data["market_data"]
    tech   = data["technical_indicators"]

    # ─── Encoding Maps ──────────────────────────────────────────────────────────
    _trend_map = {"uptrend": 1, "sideways": 0, "downtrend": -1}

    # bullish_cross=2 (Action) > bullish_zone=1 (State) เพื่อให้ XGBoost แยกน้ำหนักได้
    _macd_cross_map = {
        "bullish_cross": 2,
        "bullish_zone":  1,
        "neutral":       0,
        "bearish_zone": -1,
        "bearish_cross": -2,
    }
    _rsi_signal_map   = {"overbought": 1,  "neutral": 0, "oversold": -1}
    _bb_signal_map    = {"above_upper": 1, "inside": 0,  "below_lower": -1}
    _atr_vol_map      = {"high": 2, "normal": 1, "low": 0}

    # ── [1] TIME FEATURES ───────────────────────────────────────────────────────
    feats = _extract_time_features(data["meta"]["generated_at"])

    # ── [2] PRICE FEATURES ──────────────────────────────────────────────────────
    spot_data  = market.get("spot_price_usd", {})
    forex_data = market.get("forex", {})
    thai_data  = market.get("thai_gold_thb", {})

    sell_thb = float(thai_data.get("sell_price_thb", 0) or 0)
    buy_thb  = float(thai_data.get("buy_price_thb",  0) or 0)
    mid_thb  = float(thai_data.get("mid_price_thb",  0) or (sell_thb + buy_thb) / 2 if sell_thb + buy_thb > 0 else 0)

    feats.update({
        "spot_price":       float(spot_data.get("price_usd_per_oz", 0) or 0),
        "usd_thb":          float(forex_data.get("usd_thb", 0) or 0),
        "thai_gold_sell":   sell_thb,
        "thai_gold_buy":    buy_thb,
        "thai_gold_spread": round(sell_thb - buy_thb, 2),
        "thai_gold_mid":    round(mid_thb, 2),
    })

    # ── [3] PRICE MOMENTUM (จาก price_trend ของ Orchestrator) ──────────────────
    price_trend = market.get("price_trend", {})
    r_high = float(price_trend.get("10p_range_high", 0) or 0)
    r_low  = float(price_trend.get("10p_range_low",  0) or 0)
    range_pct = round((r_high - r_low) / r_low * 100, 4) if r_low > 0 else 0.0

    feats.update({
        "price_change_pct":    float(price_trend.get("change_pct",    0) or 0),
        "price_5p_change_pct": float(price_trend.get("5p_change_pct", 0) or 0),
        "price_10p_range_pct": range_pct,
    })

    # ── [4] RSI ─────────────────────────────────────────────────────────────────
    rsi_data = tech.get("rsi", {})
    feats.update({
        "rsi":               float(rsi_data.get("value",  50) or 50),
        "rsi_signal_encoded": _rsi_signal_map.get(rsi_data.get("signal", "neutral"), 0),
    })

    # ── [5] MACD ────────────────────────────────────────────────────────────────
    macd_data = tech.get("macd", {})
    feats.update({
        "macd_line":              float(macd_data.get("macd_line",   0) or 0),
        "macd_signal_line":       float(macd_data.get("signal_line", 0) or 0),
        "macd_hist":              float(macd_data.get("histogram",   0) or 0),
        "macd_crossover_encoded": _macd_cross_map.get(
            macd_data.get("crossover", macd_data.get("signal", "neutral")), 0
        ),
    })

    # ── [6] BOLLINGER BANDS ─────────────────────────────────────────────────────
    bb_data   = tech.get("bollinger", {})
    spot_px   = feats["spot_price"]
    bb_upper  = float(bb_data.get("upper",  0) or 0)
    bb_lower  = float(bb_data.get("lower",  0) or 0)

    # ระยะห่างจาก Band บน/ล่าง (% ของราคา) → บอกว่าราคาใกล้ขอบแค่ไหน
    dist_upper = round((bb_upper - spot_px) / spot_px * 100, 4) if spot_px > 0 and bb_upper > 0 else 0.0
    dist_lower = round((spot_px - bb_lower) / spot_px * 100, 4) if spot_px > 0 and bb_lower > 0 else 0.0

    feats.update({
        "bb_pct_b":            float(bb_data.get("pct_b",     0.5) or 0.5),
        "bb_bandwidth":        float(bb_data.get("bandwidth", 0)   or 0),
        "bb_signal_encoded":   _bb_signal_map.get(bb_data.get("signal", "inside"), 0),
        "bb_dist_upper_pct":   dist_upper,
        "bb_dist_lower_pct":   dist_lower,
    })

    # ── [7] ATR ─────────────────────────────────────────────────────────────────
    atr_data = tech.get("atr", {})
    feats.update({
        "atr":                    float(atr_data.get("value", 0) or 0),
        "atr_volatility_encoded": _atr_vol_map.get(atr_data.get("volatility_level", "normal"), 1),
    })

    # ── [8] TREND / EMA ─────────────────────────────────────────────────────────
    trend_data = tech.get("trend", {})
    ema_20  = float(trend_data.get("ema_20",  0) or 0)
    ema_50  = float(trend_data.get("ema_50",  0) or 0)
    # หมายเหตุ: key ที่ถูกต้องคือ ema_200 (ไม่ใช่ sma_200 ที่ build_feature_dataset ใช้ผิด)
    ema_200 = float(trend_data.get("ema_200", 0) or 0)

    # % spread ระหว่าง EMA20 กับ EMA50 → วัดความแรงของ Trend
    ema_spread_pct = round((ema_20 - ema_50) / ema_50 * 100, 4) if ema_50 > 0 else 0.0

    feats.update({
        "ema_20":           ema_20,
        "ema_50":           ema_50,
        "ema_200":          ema_200,
        "ema_20_50_spread_pct": ema_spread_pct,
        "trend_encoded":    _trend_map.get(trend_data.get("trend", "sideways"), 0),
    })

    # ── [9] SENTIMENT ───────────────────────────────────────────────────────────
    news_by_cat = data.get("news", {}).get("by_category", {})
    feats.update(_extract_sentiment_features(news_by_cat))

    # ── Sanity check: แทน NaN/Inf ด้วย 0 ────────────────────────────────────────
    feats = {
        k: (0.0 if (v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v)))) else v)
        for k, v in feats.items()
    }

    if as_dataframe:
        return pd.DataFrame([feats])
    return feats


# ============================================================
# v2.1 — 26-feature extractor for Dual-Model XGBoost
# ============================================================
#
# คืน dict ที่มี keys ตรงกับไฟล์ models/feature_columns.json (length=26)
# ใช้ในระบบ inference หลักของ Src_V2 main.py (XGBoostPredictor dual model)
#
# IMPORTANT: ห้ามแก้ get_xgboost_feature() เดิม (37 features) เพราะมีโค้ดอื่นใช้

# Schema canonical สำหรับ 26 features (ใช้ตรวจซ้ำว่า keys ครบ)
_V2_FEATURE_COLUMNS = [
    "xauusd_open", "xauusd_high", "xauusd_low", "xauusd_close",
    "xauusd_ret1", "xauusd_ret3", "usdthb_ret1",
    "xau_macd_delta1", "xauusd_dist_ema21", "xauusd_dist_ema50",
    "usdthb_dist_ema21", "trend_regime",
    "xauusd_rsi14", "xau_rsi_delta1", "xauusd_macd_hist",
    "xauusd_atr_norm", "xauusd_bb_width", "atr_rank50",
    "wick_bias", "body_strength",
    "hour_sin", "hour_cos", "minute_sin", "minute_cos",
    "session_progress", "day_of_week",
]

_V2_TREND_MAP = {"uptrend": 1.0, "sideways": 0.0, "downtrend": -1.0}
_EPS = 1e-9


def _safe_float(v, default: float = 0.0) -> float:
    """แปลงเป็น float พร้อม guard NaN/Inf/None → default"""
    if v is None:
        return float(default)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float(default)
    if np.isnan(f) or np.isinf(f):
        return float(default)
    return f


def _session_progress(hour: int, minute: int, dow: int) -> float:
    """0..1 ตามตำแหน่งภายใน Asian/London/NY session (เวลาไทย UTC+7)"""
    # minutes_of_day = hour * 60 + minute
    # # Asian 07:00-15:00
    # if 7 * 60 <= minutes_of_day < 15 * 60:
    #     return (minutes_of_day - 7 * 60) / (8 * 60)
    # # London 15:00-23:00
    # if 15 * 60 <= minutes_of_day < 23 * 60:
    #     return (minutes_of_day - 15 * 60) / (8 * 60)
    # # NY (overlap) 20:00-04:00 — handle wrap
    # if 20 * 60 <= minutes_of_day < 24 * 60:
    #     return (minutes_of_day - 20 * 60) / (8 * 60)
    # if 0 <= minutes_of_day < 4 * 60:
    #     return (minutes_of_day + 4 * 60) / (8 * 60)
    # return 0.0

    """0..1 ตามตำแหน่งภายใน Session ของทองไทย (อิงตาม gold_data_label_v4)"""
    minutes_of_day = hour * 60 + minute

    # วันหยุดเสาร์-อาทิตย์ (Weekend: 9:30 - 17:30)
    if dow >= 5:
        if 570 <= minutes_of_day <= 1050:
            return (minutes_of_day - 570) / (1050 - 570)
        return 0.0

    # วันธรรมดา (Weekday)
    # Morning (6:15 - 12:00) -> 375 - 720 นาที
    if 375 <= minutes_of_day < 720:
        return (minutes_of_day - 375) / (720 - 375)
    # Afternoon (12:00 - 18:00) -> 720 - 1080 นาที
    if 720 <= minutes_of_day < 1080:
        return (minutes_of_day - 720) / (1080 - 720)
    # Night (18:00 - 02:00 วันถัดไป)
    if minutes_of_day >= 1080:  # ช่วงก่อนเที่ยงคืน
        return (minutes_of_day - 1080) / (480) # รวมเวลาทั้งหมดคือ 8 ชม. (480 นาที)
    if minutes_of_day < 120:    # ช่วงหลังเที่ยงคืนถึงตี 2
        return (minutes_of_day + 360) / (480) 

    return 0.0


def get_xgboost_feature_v2(market_state: dict) -> dict:
    """
    สกัด **26 features** ตาม schema models/feature_columns.json
    สำหรับใช้กับ Dual-Model XGBoost (model_buy.pkl + model_sell.pkl)

    Parameters
    ----------
    market_state : dict
        payload จาก GoldTradingOrchestrator.run() — ต้องมี:
        - "_raw_ohlcv" : pandas.DataFrame index Asia/Bangkok (open/high/low/close)
        - "market_data" : forex / thai_gold_thb / spot_price_usd
        - "technical_indicators" : rsi / macd / bollinger / atr / trend
        - "meta.generated_at" : ISO timestamp

    Returns
    -------
    dict[str, float] : ขนาด 26, key ตรงกับ _V2_FEATURE_COLUMNS เป๊ะ
    """
    md = market_state.get("market_data", {}) or {}
    ti = market_state.get("technical_indicators", {}) or {}
    ohlcv = market_state.get("_raw_ohlcv")

    # ── 1. Candle OHLC (xauusd_*) + returns ─────────────────────
    o = h = l = c = 0.0
    ret1 = ret3 = 0.0
    atr_rank50 = 0.5  # default neutral rank
    if isinstance(ohlcv, pd.DataFrame) and not ohlcv.empty:
        last = ohlcv.iloc[-1]
        o = _safe_float(last.get("open"))
        h = _safe_float(last.get("high"))
        l = _safe_float(last.get("low"))
        c = _safe_float(last.get("close"))

        closes = ohlcv["close"].astype(float).dropna() if "close" in ohlcv.columns else pd.Series(dtype=float)
        if len(closes) >= 2 and closes.iloc[-2] != 0:
            ret1 = float(closes.iloc[-1] / closes.iloc[-2] - 1.0)
        if len(closes) >= 4 and closes.iloc[-4] != 0:
            ret3 = float(closes.iloc[-1] / closes.iloc[-4] - 1.0)

        # ATR proxy ranking (ใช้ True Range จาก high-low เป็น approximation)
        if len(ohlcv) >= 2 and {"high", "low", "close"}.issubset(ohlcv.columns):
            try:
                tr = (ohlcv["high"] - ohlcv["low"]).abs()
                window = tr.tail(50)
                if len(window) >= 5:
                    rank = (window.rank(pct=True).iloc[-1])
                    atr_rank50 = _safe_float(rank, 0.5)
            except Exception:
                atr_rank50 = 0.5

    # ── 2. Forex / USDTHB ───────────────────────────────────────
    usd_thb_now = _safe_float((md.get("forex") or {}).get("usd_thb"))
    # ไม่มี USDTHB time series → return 0 เป็น default (ปลอดภัย, เปลี่ยนใน v2.2)
    usdthb_ret1 = _safe_float((md.get("forex") or {}).get("usdthb_ret1", 0.0))
    usdthb_dist_ema21 = _safe_float((md.get("forex") or {}).get("usdthb_dist_ema21", 0.0))

    # ── 3. RSI ──────────────────────────────────────────────────
    rsi_data = ti.get("rsi") or {}
    rsi = _safe_float(rsi_data.get("value"), 50.0)
    rsi_prev = rsi_data.get("prev_value")
    rsi_delta1 = _safe_float(rsi - _safe_float(rsi_prev, rsi)) if rsi_prev is not None else 0.0

    # ── 4. MACD ─────────────────────────────────────────────────
    macd_data = ti.get("macd") or {}
    macd_hist = _safe_float(macd_data.get("histogram"))
    macd_hist_prev = macd_data.get("prev_histogram")
    macd_delta1 = (
        _safe_float(macd_hist - _safe_float(macd_hist_prev, macd_hist))
        if macd_hist_prev is not None else 0.0
    )

    # ── 5. Bollinger ────────────────────────────────────────────
    bb_data = ti.get("bollinger") or {}
    bb_width = _safe_float(bb_data.get("bandwidth"))

    # ── 6. ATR (normalized vs price) ───────────────────────────
    # คำนวณ ATR USD จาก ohlcv โดยตรงเพื่อป้องกันค่าที่แปลงเป็น THB แล้ว
    if isinstance(ohlcv, pd.DataFrame) and len(ohlcv) >= 15:
        prev_close = ohlcv["close"].shift(1)
        tr = pd.concat([
            ohlcv["high"] - ohlcv["low"],
            (ohlcv["high"] - prev_close).abs(),
            (ohlcv["low"] - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr_usd = float(tr.ewm(alpha=1/14, adjust=False).mean().iloc[-1])
        atr_norm = atr_usd / c if c > 0 else 0.0
    else:
        atr_norm = 0.0

    # ── 7. Trend / EMA ──────────────────────────────────────────
    trend_data = ti.get("trend") or {}
    ema_21 = _safe_float(trend_data.get("ema_21", trend_data.get("ema_20"))) # พยายามใช้ 21 ถ้ามี
    ema_50 = _safe_float(trend_data.get("ema_50"))
    
    dist_ema21 = (c - ema_21) / ema_21 if ema_21 > 0 else 0.0
    dist_ema50 = (c - ema_50) / ema_50 if ema_50 > 0 else 0.0
    
    # แก้ trend_regime ให้ตรงกับตอนเทรน (dist_ema21 > 0)
    trend_regime = 1.0 if dist_ema21 > 0 else 0.0

    # ── 8. Candle metrics: wick_bias + body_strength ──
    rng = h - l
    if rng > _EPS:
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        
        # แก้ wick_bias ให้เป็น (Lower - Upper) เหมือนตอนเทรน
        # *หมายเหตุ: ถ้าตอนเทรนไม่ได้หาร rng ก็ไม่ต้องหาร แต่ถ้าอยากให้ Normalized แนะนำให้กลับไปแก้โค้ดฝั่งเทรนให้หาร rng ด้วยจะดีกว่าครับ
        wick_bias = lower_wick - upper_wick 
        body_strength = abs(c - o) / rng
    else:
        wick_bias = 0.0
        body_strength = 0.0

    # ── 9. Time encodings ───────────────────────────────────────
    ts_str = (market_state.get("meta") or {}).get("generated_at") \
        or market_state.get("timestamp")
    try:
        dt = pd.to_datetime(ts_str)
    except Exception:
        dt = pd.Timestamp.now(tz="Asia/Bangkok")
    hour = int(dt.hour)
    minute = int(dt.minute)
    dow = int(dt.dayofweek)

    hour_rad = 2.0 * np.pi * (hour / 24.0)
    minute_rad = 2.0 * np.pi * (minute / 60.0)

    feats = {
        # Candle
        "xauusd_open":        _safe_float(o),
        "xauusd_high":        _safe_float(h),
        "xauusd_low":         _safe_float(l),
        "xauusd_close":       _safe_float(c),
        "xauusd_ret1":        _safe_float(ret1),
        "xauusd_ret3":        _safe_float(ret3),
        "usdthb_ret1":        _safe_float(usdthb_ret1),
        # MACD / EMA distances / trend
        "xau_macd_delta1":    _safe_float(macd_delta1),
        "xauusd_dist_ema21":  _safe_float(dist_ema21),
        "xauusd_dist_ema50":  _safe_float(dist_ema50),
        "usdthb_dist_ema21":  _safe_float(usdthb_dist_ema21),
        "trend_regime":       _safe_float(trend_regime),
        # Oscillators
        "xauusd_rsi14":       _safe_float(rsi),
        "xau_rsi_delta1":     _safe_float(rsi_delta1),
        "xauusd_macd_hist":   _safe_float(macd_hist),
        # Volatility
        "xauusd_atr_norm":    _safe_float(atr_norm),
        "xauusd_bb_width":    _safe_float(bb_width),
        "atr_rank50":         _safe_float(atr_rank50, 0.5),
        # Candle shape
        "wick_bias":          _safe_float(wick_bias),
        "body_strength":      _safe_float(body_strength),
        # Cyclic time
        "hour_sin":           float(np.sin(hour_rad)),
        "hour_cos":           float(np.cos(hour_rad)),
        "minute_sin":         float(np.sin(minute_rad)),
        "minute_cos":         float(np.cos(minute_rad)),
        "session_progress": _safe_float(_session_progress(hour, minute, dow)),
        "day_of_week":        float(dow),
    }

    # Sanity: ต้องครบ 26 keys ตรงตาม schema
    missing = [k for k in _V2_FEATURE_COLUMNS if k not in feats]
    if missing:
        raise RuntimeError(f"get_xgboost_feature_v2: missing keys {missing}")

    # คืนเฉพาะ 26 keys ตามลำดับ schema
    return {k: feats[k] for k in _V2_FEATURE_COLUMNS}


if __name__ == "__main__":
    # หาตำแหน่งไฟล์ extract_features.py (ใน Src/data_engine)
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # ชี้เป้าไปที่ output/latest.json และ Data/features_master.csv นอกสุด
    json_path = os.path.join(current_dir, "..", "agent_core", "data", "latest.json")
    csv_path = os.path.join(current_dir, "..", "..", "Data", "features_master.csv")

    build_feature_dataset(json_file_path=json_path, csv_file_path=csv_path)