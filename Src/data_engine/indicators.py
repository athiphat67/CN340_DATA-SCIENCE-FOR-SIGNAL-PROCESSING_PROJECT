"""
data_engine/indicators.py
Pure-Python math engine — LLM must NEVER calculate these numbers itself.
All calculations use Pandas / pandas_ta for deterministic, reproducible results.
"""

import logging
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


class MathEngine:
    """
    Computes technical indicators and returns a clean state dict
    that is safe to pass directly to the LLM agent as its market snapshot.
    """

    def calculate_metrics(self, df: pd.DataFrame) -> dict:
        """
        Accepts a raw OHLCV DataFrame (from DataFetcher) and returns a
        flat dict of indicators rounded to 2 decimal places.

        Raises ValueError if df is empty or missing the 'Close' column.
        """
        if df is None or df.empty:
            raise ValueError("DataFrame is empty — cannot calculate indicators")
        if "Close" not in df.columns:
            raise ValueError("DataFrame must contain a 'Close' column")

        df = df.copy()

        # --- RSI (14) ---
        df["RSI"] = ta.rsi(df["Close"], length=14)

        # --- MACD (12, 26, 9) ---
        macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd is not None:
            df = pd.concat([df, macd], axis=1)

        # --- Bollinger Bands (20, 2σ) ---
        bbands = ta.bbands(df["Close"], length=20, std=2)
        if bbands is not None:
            df = pd.concat([df, bbands], axis=1)

        # --- EMA 50 & 200 ---
        df["EMA_50"]  = ta.ema(df["Close"], length=50)
        df["EMA_200"] = ta.ema(df["Close"], length=200)

        # --- ATR (14) — volatility proxy ---
        if all(c in df.columns for c in ("High", "Low", "Close")):
            df["ATR"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)

        latest = df.iloc[-1]

        def _round(col: str, decimals: int = 2):
            val = latest.get(col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return None
            return round(float(val), decimals)

        metrics = {
            # Price
            "price":      _round("Close"),
            # Momentum
            "rsi":        _round("RSI"),
            # MACD
            "macd":       _round("MACD_12_26_9"),
            "macd_signal":_round("MACDs_12_26_9"),
            "macd_hist":  _round("MACDh_12_26_9"),
            # Bollinger Bands
            "bb_upper":   _round("BBU_20_2.0"),
            "bb_mid":     _round("BBM_20_2.0"),
            "bb_lower":   _round("BBL_20_2.0"),
            # Trend
            "ema_50":     _round("EMA_50"),
            "ema_200":    _round("EMA_200"),
            # Volatility
            "atr":        _round("ATR"),
        }

        # Derived signals (deterministic rules — not for LLM to guess)
        metrics["signal_rsi_oversold"]    = (metrics["rsi"] or 50) < 30
        metrics["signal_rsi_overbought"]  = (metrics["rsi"] or 50) > 70
        metrics["signal_macd_bullish"]    = (
            metrics["macd"] is not None
            and metrics["macd_signal"] is not None
            and metrics["macd"] > metrics["macd_signal"]
        )
        metrics["signal_above_ema50"]     = (
            metrics["price"] is not None
            and metrics["ema_50"] is not None
            and metrics["price"] > metrics["ema_50"]
        )

        logger.info(
            f"[MathEngine] price={metrics['price']} "
            f"RSI={metrics['rsi']} MACD={metrics['macd']}"
        )
        return metrics
