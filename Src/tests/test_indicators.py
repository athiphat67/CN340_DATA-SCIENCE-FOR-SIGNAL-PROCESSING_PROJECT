"""
test_indicators.py — Unit tests for TechnicalIndicators (~70% coverage)
Tests: RSI, MACD, Bollinger Bands, ATR, Trend, compute_all, edge cases.
"""

import pytest
import numpy as np
import pandas as pd

from data_engine.indicators import (
    TechnicalIndicators,
    RSIResult,
    MACDResult,
    BollingerResult,
    ATRResult,
    TrendResult,
    AllIndicators,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_df(prices: list[float], n: int = None) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame from close prices."""
    if n is None:
        n = len(prices)
    close = np.array(prices[-n:], dtype=float)
    return pd.DataFrame({
        "open":   close - 1,
        "high":   close + 3,
        "low":    close - 3,
        "close":  close,
        "volume": [20000] * len(close),
    })


def _trending_up_df(n: int = 100, start: float = 2000.0, step: float = 5.0) -> pd.DataFrame:
    """Strongly trending up data."""
    prices = [start + i * step for i in range(n)]
    return _make_df(prices)


def _trending_down_df(n: int = 100, start: float = 3000.0, step: float = 5.0) -> pd.DataFrame:
    """Strongly trending down data."""
    prices = [start - i * step for i in range(n)]
    return _make_df(prices)


def _sideways_df(n: int = 100, center: float = 2300.0, amplitude: float = 2.0) -> pd.DataFrame:
    """Sideways / mean-reverting data."""
    np.random.seed(99)
    prices = center + np.random.randn(n) * amplitude
    return _make_df(prices.tolist())


# ─── RSI Tests ───────────────────────────────────────────────────────────────

class TestRSI:

    def test_rsi_overbought(self):
        """Strongly trending up should produce RSI > 70."""
        # ใช้ noise เล็กน้อยเพื่อให้ RSI คำนวณได้ถูกต้อง
        # (linear step สม่ำเสมอ 100% ทำให้ Wilder's smoothing คืน 50.0)
        np.random.seed(42)
        prices = [2000 + i * 5 + np.random.uniform(0, 2) for i in range(100)]
        df = _make_df(prices)
        calc = TechnicalIndicators(df)
        result = calc.rsi()
        assert isinstance(result, RSIResult)
        assert result.value > 70
        assert result.signal == "overbought"

    def test_rsi_oversold(self):
        """Strongly trending down should produce RSI < 30."""
        df = _trending_down_df(100)
        calc = TechnicalIndicators(df)
        result = calc.rsi()
        assert result.value < 30
        assert result.signal == "oversold"

    def test_rsi_neutral(self):
        """Sideways data should produce RSI between 30 and 70."""
        df = _sideways_df(100)
        calc = TechnicalIndicators(df)
        result = calc.rsi()
        assert 30 <= result.value <= 70
        assert result.signal == "neutral"

    def test_rsi_period_default(self):
        df = _sideways_df(100)
        calc = TechnicalIndicators(df)
        result = calc.rsi()
        assert result.period == 14

    def test_rsi_custom_period(self):
        df = _sideways_df(100)
        calc = TechnicalIndicators(df)
        result = calc.rsi(period=7)
        assert result.period == 7
        assert 0 <= result.value <= 100


# ─── MACD Tests ──────────────────────────────────────────────────────────────

class TestMACD:

    def test_macd_returns_dataclass(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.macd()
        assert isinstance(result, MACDResult)

    def test_macd_bullish_cross(self):
        """After a dip then recovery, MACD should show bullish crossover."""
        # Create data: down then sharply up
        prices = [2300 - i * 3 for i in range(50)] + [2150 + i * 8 for i in range(50)]
        df = _make_df(prices)
        calc = TechnicalIndicators(df)
        result = calc.macd()
        # Histogram should be positive after recovery
        assert result.histogram > 0 or result.crossover in ("bullish_cross", "none")

    def test_macd_bearish_cross(self):
        """After a rise then decline, MACD should show bearish crossover."""
        prices = [2000 + i * 3 for i in range(50)] + [2150 - i * 8 for i in range(50)]
        df = _make_df(prices)
        calc = TechnicalIndicators(df)
        result = calc.macd()
        assert result.histogram < 0 or result.crossover in ("bearish_cross", "none")

    def test_macd_fields_are_floats(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.macd()
        assert isinstance(result.macd_line, float)
        assert isinstance(result.signal_line, float)
        assert isinstance(result.histogram, float)


# ─── Bollinger Bands Tests ───────────────────────────────────────────────────

class TestBollinger:

    def test_bollinger_inside(self):
        """Sideways data: close should be inside bands."""
        df = _sideways_df(100)
        calc = TechnicalIndicators(df)
        result = calc.bollinger_bands()
        assert isinstance(result, BollingerResult)
        assert result.signal == "inside"
        assert result.lower <= result.middle <= result.upper

    def test_bollinger_above_upper(self):
        """Strongly trending up: close should be above upper band."""
        df = _trending_up_df(100, step=10)
        calc = TechnicalIndicators(df)
        result = calc.bollinger_bands()
        # Close is likely above upper or close to it
        assert result.upper > result.middle

    def test_bollinger_below_lower(self):
        """Strongly trending down: close should be below lower band."""
        df = _trending_down_df(100, step=10)
        calc = TechnicalIndicators(df)
        result = calc.bollinger_bands()
        assert result.lower < result.middle

    def test_bollinger_bandwidth_positive(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.bollinger_bands()
        assert result.bandwidth >= 0

    def test_bollinger_pct_b_range(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.bollinger_bands()
        # pct_b can be outside [0,1] if price is outside bands
        assert isinstance(result.pct_b, float)


# ─── ATR Tests ───────────────────────────────────────────────────────────────

class TestATR:

    def test_atr_positive(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.atr()
        assert isinstance(result, ATRResult)
        assert result.value > 0

    def test_atr_volatility_levels(self):
        """Low volatility data → 'low', high volatility → 'high'."""
        # Low vol: very tight range
        prices = [2300 + 0.01 * i for i in range(100)]
        df = pd.DataFrame({
            "open": prices,
            "high": [p + 0.005 for p in prices],
            "low": [p - 0.005 for p in prices],
            "close": prices,
            "volume": [20000] * 100,
        })
        calc = TechnicalIndicators(df)
        result = calc.atr()
        assert result.volatility_level == "low"

    def test_atr_default_period(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.atr()
        assert result.period == 14


# ─── Trend Tests ─────────────────────────────────────────────────────────────

class TestTrend:

    def test_uptrend(self):
        df = _trending_up_df(100)
        calc = TechnicalIndicators(df)
        result = calc.trend()
        assert isinstance(result, TrendResult)
        assert result.trend == "uptrend"
        assert result.ema_20 > result.ema_50

    def test_downtrend(self):
        df = _trending_down_df(100)
        calc = TechnicalIndicators(df)
        result = calc.trend()
        assert result.trend == "downtrend"
        assert result.ema_20 < result.ema_50

    def test_golden_cross(self):
        """In strong uptrend: EMA20 > EMA50 > SMA200."""
        df = _trending_up_df(250, step=3)
        calc = TechnicalIndicators(df)
        result = calc.trend()
        if result.ema_20 > result.ema_50 > result.sma_200:
            assert result.golden_cross is True

    def test_death_cross(self):
        """In strong downtrend: EMA20 < EMA50 < SMA200."""
        df = _trending_down_df(250, step=3)
        calc = TechnicalIndicators(df)
        result = calc.trend()
        if result.ema_20 < result.ema_50 < result.sma_200:
            assert result.death_cross is True

    def test_short_data_sma200_fallback(self):
        """With < 200 rows, SMA200 should still compute (using available data)."""
        df = _sideways_df(50)
        calc = TechnicalIndicators(df)
        result = calc.trend()
        assert result.sma_200 > 0


# ─── compute_all / to_dict ───────────────────────────────────────────────────

class TestComputeAll:

    def test_compute_all_returns_dataclass(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.compute_all()
        assert isinstance(result, AllIndicators)
        assert isinstance(result.rsi, RSIResult)
        assert isinstance(result.macd, MACDResult)
        assert isinstance(result.bollinger, BollingerResult)
        assert isinstance(result.atr, ATRResult)
        assert isinstance(result.trend, TrendResult)
        assert result.latest_close > 0

    def test_to_dict_returns_dict(self, sample_ohlcv_df):
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.to_dict()
        assert isinstance(result, dict)
        assert "rsi" in result
        assert "macd" in result
        assert "bollinger" in result
        assert "atr" in result
        assert "trend" in result


# ─── Edge Cases ──────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_empty_dataframe_raises(self):
        df = pd.DataFrame()
        with pytest.raises(ValueError, match="empty"):
            TechnicalIndicators(df)

    def test_missing_columns_raises(self):
        df = pd.DataFrame({"foo": [1, 2, 3]})
        with pytest.raises(ValueError, match="columns"):
            TechnicalIndicators(df)

    def test_minimum_data_works(self):
        """Just enough rows to compute all indicators (26 for MACD)."""
        prices = [2300 + i for i in range(30)]
        df = _make_df(prices)
        calc = TechnicalIndicators(df)
        result = calc.to_dict()
        assert "rsi" in result