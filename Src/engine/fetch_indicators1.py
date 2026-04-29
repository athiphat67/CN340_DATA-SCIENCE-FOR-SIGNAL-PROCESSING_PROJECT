"""
tools/fetch_indicators.py — Tool: คำนวณ Technical Indicators
ดึงข้อมูล OHLCV ผ่าน OHLCVFetcher แล้วคำนวณ indicators พร้อม data_quality

Phase 1 (Bot):  คืน dict indicators สำหรับ ReAct Loop / LLM
Phase 2 (ML):   คืน pd.DataFrame 26 features พร้อมเข้าโมเดล
"""

import logging
import pandas as pd
from typing import Optional

from engine.indicator_new import TechnicalIndicators, ML_FEATURE_COLUMNS
from data_engine.thailand_timestamp import get_thai_time
from data_engine.ohlcv_fetcher import OHLCVFetcher

logger = logging.getLogger(__name__)

TOOL_NAME        = "fetch_indicators"
TOOL_DESCRIPTION = (
    "ดึงข้อมูล OHLCV แล้วคำนวณ Technical Indicators: RSI, MACD, Bollinger Bands, EMA, ATR "
    "พร้อม data_quality report และคำแนะนำสำหรับ LLM  "
    "รองรับโหมด ML (26 features) ผ่าน fetch_ml_features()"
)


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — Bot / LLM indicator dict (เหมือนเดิม 100%)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_indicators(
    interval: str = "5m",
    days: int = 90,
    twelvedata_symbol: str = "XAU/USD",
    yf_symbol: str = "GC=F",
    use_cache: bool = True,
    ohlcv_df: pd.DataFrame = None,
) -> dict:
    """
    [Phase 1] ดึง OHLCV แล้วคำนวณ Technical Indicators สำหรับ Bot / LLM

    Returns:
        {
            "indicators"  : dict  — ผลลัพธ์ indicators ทั้งหมด,
            "data_quality": dict  — quality_score / warnings / llm_instruction,
            "ohlcv_df"    : pd.DataFrame | None  — raw OHLCV (ส่งต่อไป Phase 2 ได้),
            "error"       : str | None
        }
    """
    data_quality = {
        "quality_score":   "good",
        "is_weekend":      get_thai_time().weekday() >= 5,
        "llm_instruction": "Use standard technical analysis.",
        "warnings":        [],
    }

    # 1. ดึง OHLCV (ถ้ายังไม่มี DataFrame)
    if ohlcv_df is None or ohlcv_df.empty:
        logger.info(
            f"[fetch_indicators] Fetching OHLCV "
            f"(symbol={twelvedata_symbol}, interval={interval}, days={days})..."
        )
        try:
            fetcher  = OHLCVFetcher()
            ohlcv_df = fetcher.fetch_historical_ohlcv(
                days=days,
                interval=interval,
                twelvedata_symbol=twelvedata_symbol,
                yf_symbol=yf_symbol,
                use_cache=use_cache,
            )
        except Exception as e:
            logger.error(f"[fetch_indicators] OHLCV fetch failed: {e}")
            data_quality["quality_score"] = "degraded"
            data_quality["warnings"].append(f"OHLCV fetch error: {e}")
            return {"indicators": {}, "data_quality": data_quality,
                    "ohlcv_df": None, "error": str(e)}

    if ohlcv_df is None or ohlcv_df.empty:
        logger.warning("[fetch_indicators] No OHLCV data — skipping indicators")
        data_quality["quality_score"] = "degraded"
        data_quality["warnings"].append("No OHLCV data available.")
        return {"indicators": {}, "data_quality": data_quality,
                "ohlcv_df": None, "error": "No OHLCV data"}

    logger.info(
        f"[fetch_indicators] Computing indicators on {len(ohlcv_df)} candles "
        f"(interval={interval})..."
    )

    # 2. คำนวณ Indicators
    try:
        calc             = TechnicalIndicators(ohlcv_df)
        indicators_dict  = calc.to_dict(interval=interval)

        if "data_quality" in indicators_dict:
            dq = indicators_dict.pop("data_quality")
            data_quality["warnings"].extend(dq.get("warnings", []))
            data_quality["quality_score"] = dq.get("quality_score", "good")

        if data_quality["is_weekend"]:
            data_quality["warnings"].append(
                "Market is closed (Weekend) — Price data might be stale."
            )
            data_quality["llm_instruction"] = (
                "Market is closed. Weigh news sentiment higher than short-term indicators."
            )

        logger.info(f"[fetch_indicators] ✅ Done — quality={data_quality['quality_score']}")
        return {
            "indicators":  indicators_dict,
            "data_quality": data_quality,
            "ohlcv_df":    ohlcv_df,      # ← ส่งต่อให้ Phase 2 ใช้ต่อได้เลย
            "error":       None,
        }

    except Exception as e:
        logger.error(f"[fetch_indicators] Calculation failed: {e}")
        data_quality["quality_score"] = "degraded"
        data_quality["warnings"].append(f"Indicator calc error: {e}")
        return {"indicators": {}, "data_quality": data_quality,
                "ohlcv_df": ohlcv_df, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — ML 26-feature DataFrame
# ──────────────────────────────────────────────────────────────────────────────

def fetch_ml_features(
    interval: str = "5m",
    days: int = 90,
    twelvedata_symbol: str = "XAU/USD",
    yf_symbol: str = "GC=F",
    use_cache: bool = True,
    ohlcv_df: pd.DataFrame = None,
    usdthb_series: Optional[pd.Series] = None,
    session_start_hour: int = 6,
    session_end_hour: int = 23,
    drop_na: bool = True,
) -> dict:
    """
    [Phase 2] คืน DataFrame ที่มี 26 ML features พร้อมเข้าโมเดล

    Args:
        interval            : Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
        days                : จำนวนวันย้อนหลัง
        twelvedata_symbol   : Symbol TwelveData (fallback)
        yf_symbol           : Symbol Yahoo Finance (primary)
        use_cache           : เปิด/ปิด cache
        ohlcv_df            : ส่ง DataFrame ตรงๆ ข้ามการ fetch
        usdthb_series       : pd.Series ราคา USD/THB (index ตรงกับ ohlcv_df)
                              ถ้า None → features ที่ใช้ usdthb จะเป็น 0.0
        session_start_hour  : ชั่วโมงเริ่ม session (default 6)
        session_end_hour    : ชั่วโมงสิ้นสุด session (default 23)
        drop_na             : dropna แถวที่มี NaN (default True)

    Returns:
        {
            "features"    : pd.DataFrame  — 26 columns (ML_FEATURE_COLUMNS),
            "feature_cols": list[str]     — ชื่อ columns ลำดับคงที่,
            "n_rows"      : int,
            "data_quality": dict,
            "error"       : str | None
        }
    """
    data_quality = {
        "quality_score":   "good",
        "is_weekend":      get_thai_time().weekday() >= 5,
        "warnings":        [],
    }

    # 1. ดึง OHLCV
    if ohlcv_df is None or ohlcv_df.empty:
        logger.info(
            f"[fetch_ml_features] Fetching OHLCV "
            f"(symbol={twelvedata_symbol}, interval={interval}, days={days})..."
        )
        try:
            fetcher  = OHLCVFetcher()
            ohlcv_df = fetcher.fetch_historical_ohlcv(
                days=days,
                interval=interval,
                twelvedata_symbol=twelvedata_symbol,
                yf_symbol=yf_symbol,
                use_cache=use_cache,
            )
        except Exception as e:
            logger.error(f"[fetch_ml_features] OHLCV fetch failed: {e}")
            data_quality["quality_score"] = "degraded"
            data_quality["warnings"].append(f"OHLCV fetch error: {e}")
            return {
                "features": pd.DataFrame(columns=ML_FEATURE_COLUMNS),
                "feature_cols": ML_FEATURE_COLUMNS,
                "n_rows": 0,
                "data_quality": data_quality,
                "error": str(e),
            }

    if ohlcv_df is None or ohlcv_df.empty:
        msg = "No OHLCV data available"
        logger.warning(f"[fetch_ml_features] {msg}")
        data_quality["quality_score"] = "degraded"
        data_quality["warnings"].append(msg)
        return {
            "features": pd.DataFrame(columns=ML_FEATURE_COLUMNS),
            "feature_cols": ML_FEATURE_COLUMNS,
            "n_rows": 0,
            "data_quality": data_quality,
            "error": msg,
        }

    logger.info(
        f"[fetch_ml_features] Building 26 ML features from {len(ohlcv_df)} candles "
        f"(interval={interval})..."
    )

    # 2. คำนวณ 26 features
    try:
        calc     = TechnicalIndicators(ohlcv_df)
        features = (
            calc.get_ml_features_clean(
                usdthb_series=usdthb_series,
                session_start_hour=session_start_hour,
                session_end_hour=session_end_hour,
            )
            if drop_na
            else calc.get_ml_features(
                usdthb_series=usdthb_series,
                session_start_hour=session_start_hour,
                session_end_hour=session_end_hour,
            )
        )

        if data_quality["is_weekend"]:
            data_quality["warnings"].append(
                "Market is closed (Weekend) — time features may reflect non-trading hours."
            )

        logger.info(
            f"[fetch_ml_features] ✅ Done — shape={features.shape}, "
            f"quality={data_quality['quality_score']}"
        )
        return {
            "features":     features,
            "feature_cols": ML_FEATURE_COLUMNS,
            "n_rows":       len(features),
            "data_quality": data_quality,
            "error":        None,
        }

    except Exception as e:
        logger.error(f"[fetch_ml_features] Feature build failed: {e}")
        data_quality["quality_score"] = "degraded"
        data_quality["warnings"].append(f"Feature build error: {e}")
        return {
            "features": pd.DataFrame(columns=ML_FEATURE_COLUMNS),
            "feature_cols": ML_FEATURE_COLUMNS,
            "n_rows": 0,
            "data_quality": data_quality,
            "error": str(e),
        }