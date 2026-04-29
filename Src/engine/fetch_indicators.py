"""
tools/fetch_indicators.py — ML Feature Builder
ดึงข้อมูล OHLCV แล้วคำนวณ 26 ML features พร้อมเข้าโมเดล XGBoost

รองรับ 2 ชุด:
    symbol="xauusd" → ทองโลก  XAU/USD  (USD/oz)
    symbol="thai"   → ทองไทย  HSH/THB  (THB/บาท)
"""

import logging
import pandas as pd
from typing import Literal, Optional

from engine.indicators import (
    TechnicalIndicators,
    ML_FEATURE_COLUMNS_XAUUSD,
    ML_FEATURE_COLUMNS_THAI,
)
from data_engine.thailand_timestamp import get_thai_time
from data_engine.ohlcv_fetcher import OHLCVFetcher

logger = logging.getLogger(__name__)

# feature column list ที่ถูกต้องตาม symbol
_FEATURE_COLS: dict[str, list[str]] = {
    "xauusd": ML_FEATURE_COLUMNS_XAUUSD,
    "thai":   ML_FEATURE_COLUMNS_THAI,
}


def fetch_ml_features(
    symbol: Literal["xauusd", "thai"] = "xauusd",
    interval: str = "5m",
    days: int = 90,
    twelvedata_symbol: str = "XAU/USD",
    yf_symbol: str = "GC=F",
    use_cache: bool = True,
    ohlcv_df: pd.DataFrame = None,
    external_series: Optional[pd.Series] = None,  # xauusd → usdthb_series
                                                   # thai   → xauusd_series
    session_start_hour: Optional[int] = None,      # None = ใช้ default ตาม symbol
    session_end_hour: Optional[int] = None,        # None = ใช้ default ตาม symbol
    drop_na: bool = True,
) -> dict:
    """
    คืน DataFrame ที่มี 26 ML features พร้อมเข้าโมเดล

    Args:
        symbol              : "xauusd" (ทองโลก USD/oz) | "thai" (ทองไทย THB/บาท)
        interval            : Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
        days                : จำนวนวันย้อนหลัง
        twelvedata_symbol   : Symbol TwelveData (fallback)
        yf_symbol           : Symbol Yahoo Finance (primary)
        use_cache           : เปิด/ปิด cache
        ohlcv_df            : ส่ง DataFrame ตรงๆ ข้ามการ fetch
        external_series     : pd.Series cross-market signal
                                - symbol="xauusd" → ส่ง usdthb_series
                                - symbol="thai"   → ส่ง xauusd_series
                              None → external features จะเป็น 0.0
        session_start_hour  : override ชั่วโมงเริ่ม session
                              None → default (xauusd=6, thai=9)
        session_end_hour    : override ชั่วโมงสิ้นสุด session
                              None → default (xauusd=23, thai=17)
        drop_na             : dropna แถวที่มี NaN (default True)

    Returns:
        {
            "features"    : pd.DataFrame  — 26 columns ตาม symbol,
            "feature_cols": list[str]     — ชื่อ columns ลำดับคงที่,
            "symbol"      : str,
            "n_rows"      : int,
            "data_quality": dict,
            "error"       : str | None
        }

    ตัวอย่าง:
        # ทองโลก
        result = fetch_ml_features(
            symbol="xauusd",
            external_series=usdthb_series,
        )

        # ทองไทย
        result = fetch_ml_features(
            symbol="thai",
            ohlcv_df=thai_ohlcv_df,
            external_series=xauusd_series,
        )

        X = result["features"]
        prob_buy = buy_model.predict_proba(X)[:, 1]
    """
    if symbol not in _FEATURE_COLS:
        raise ValueError(f"symbol ต้องเป็น 'xauusd' หรือ 'thai'  ได้รับ: '{symbol}'")

    feature_cols = _FEATURE_COLS[symbol]

    data_quality = {
        "quality_score": "good",
        "is_weekend":    get_thai_time().weekday() >= 5,
        "symbol":        symbol,
        "warnings":      [],
    }

    def _empty_result(error_msg: str) -> dict:
        data_quality["quality_score"] = "degraded"
        data_quality["warnings"].append(error_msg)
        return {
            "features":     pd.DataFrame(columns=feature_cols),
            "feature_cols": feature_cols,
            "symbol":       symbol,
            "n_rows":       0,
            "data_quality": data_quality,
            "error":        error_msg,
        }

    # 1. ดึง OHLCV
    if ohlcv_df is None or ohlcv_df.empty:
        logger.info(
            f"[fetch_ml_features] Fetching OHLCV "
            f"(symbol={symbol}, source={twelvedata_symbol}, interval={interval}, days={days})..."
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
            return _empty_result(f"OHLCV fetch error: {e}")

    if ohlcv_df is None or ohlcv_df.empty:
        logger.warning("[fetch_ml_features] No OHLCV data")
        return _empty_result("No OHLCV data available")

    logger.info(
        f"[fetch_ml_features] Building 26 ML features "
        f"(symbol={symbol}, candles={len(ohlcv_df)}, interval={interval})..."
    )

    # 2. คำนวณ 26 features
    try:
        calc     = TechnicalIndicators(ohlcv_df)
        features = calc.get_features(
            symbol=symbol,
            external_series=external_series,
            session_start_hour=session_start_hour,
            session_end_hour=session_end_hour,
            drop_na=drop_na,
        )

        if data_quality["is_weekend"]:
            data_quality["warnings"].append(
                "Market is closed (Weekend) — time features may reflect non-trading hours."
            )

        logger.info(
            f"[fetch_ml_features] ✅ Done — symbol={symbol}, shape={features.shape}"
        )
        return {
            "features":     features,
            "feature_cols": feature_cols,
            "symbol":       symbol,
            "n_rows":       len(features),
            "data_quality": data_quality,
            "error":        None,
        }

    except Exception as e:
        logger.error(f"[fetch_ml_features] Feature build failed (symbol={symbol}): {e}")
        return _empty_result(f"Feature build error: {e}")
