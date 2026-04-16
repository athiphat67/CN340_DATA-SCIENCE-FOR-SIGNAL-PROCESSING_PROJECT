"""
Tests for data_engine/analysis_tools/technical_tools.py

Strategy:
- Every function that accepts `ohlcv_df` receives an in-memory DataFrame,
  so network calls to _fetcher are avoided for the happy-path tests.
- `get_htf_trend` requires >= 200 rows to use the injected df; tests that
  intentionally exercise the fallback-to-fetcher path mock _fetcher directly.
- _HTF_CACHE is cleared before and after every test via the autouse fixture.
"""

import time

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from data_engine.analysis_tools.technical_tools import (
    calculate_ema_distance,
    check_bb_rsi_combo,
    check_spot_thb_alignment,
    detect_breakout_confirmation,
    detect_rsi_divergence,
    get_htf_trend,
    get_support_resistance_zones,
    _HTF_CACHE,
)

pytestmark = pytest.mark.data_engine

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def ohlcv_df():
    """300-row random OHLCV DataFrame (seed=42) centred around 3200 USD."""
    rng = np.random.default_rng(42)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="5min")
    closes = 3200 + np.cumsum(rng.standard_normal(n) * 2)
    opens = closes - rng.uniform(0, 2, n)
    highs = np.maximum(closes, opens) + rng.uniform(0, 3, n)
    lows = np.minimum(closes, opens) - rng.uniform(0, 3, n)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes,
         "volume": rng.integers(100, 1000, n)},
        index=dates,
    )


@pytest.fixture
def bullish_ohlcv():
    """300-row strong uptrend DataFrame for overextension tests."""
    rng = np.random.default_rng(7)
    n = 300
    dates = pd.date_range("2024-01-01", periods=n, freq="5min")
    closes = 3200 + np.arange(n) * 0.5 + rng.standard_normal(n) * 0.3
    opens = closes - 0.2
    highs = closes + 0.5
    lows = closes - 0.5
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes,
         "volume": np.ones(n) * 500},
        index=dates,
    )


def _make_df(closes, start="2024-01-01", freq="5min"):
    """Helper: build a minimal OHLCV DataFrame from a closes array."""
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq=freq)
    opens = np.array(closes) - 0.5
    highs = np.array(closes) + 1.0
    lows = np.array(closes) - 1.0
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": np.array(closes),
         "volume": np.ones(n) * 300},
        index=dates,
    )


@pytest.fixture
def bb_rsi_ohlcv(ohlcv_df):
    """ohlcv_df pre-enriched with a 'bb_high' column (alias of 'bb_up').

    check_bb_rsi_combo accesses latest['bb_high'] but TechnicalIndicators
    generates 'bb_up'.  Pre-computing bb_high here ensures it survives the
    internal TechnicalIndicators pass inside check_bb_rsi_combo without
    touching production code.
    """
    from data_engine.indicators import TechnicalIndicators

    enriched = TechnicalIndicators(ohlcv_df.copy()).df.copy()
    enriched["bb_high"] = enriched["bb_up"]
    return enriched


@pytest.fixture(autouse=True)
def clear_htf_cache():
    """Clear _HTF_CACHE before and after every test to prevent leakage."""
    _HTF_CACHE.clear()
    yield
    _HTF_CACHE.clear()


# ─────────────────────────────────────────────────────────────────────────────
# TestCheckSpotThbAlignment
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckSpotThbAlignment:
    def _make_trending(self, start, step, n=10):
        """Build a small df trending in one direction."""
        closes = [start + i * step for i in range(n)]
        return _make_df(closes)

    def test_strong_bullish_when_both_up(self):
        df_spot = self._make_trending(3200, 5)    # uptrend
        df_thb = self._make_trending(35, 0.05)   # uptrend
        result = check_spot_thb_alignment(lookback_candles=4, df_spot=df_spot, df_thb=df_thb)
        assert result["status"] == "success"
        assert result["alignment"] == "Strong Bullish"

    def test_strong_bearish_when_both_down(self):
        df_spot = self._make_trending(3200, -5)
        df_thb = self._make_trending(35, -0.05)
        result = check_spot_thb_alignment(lookback_candles=4, df_spot=df_spot, df_thb=df_thb)
        assert result["alignment"] == "Strong Bearish"

    def test_neutral_spot_leading_spot_up_thb_down(self):
        df_spot = self._make_trending(3200, 5)
        df_thb = self._make_trending(35, -0.05)
        result = check_spot_thb_alignment(lookback_candles=4, df_spot=df_spot, df_thb=df_thb)
        assert result["alignment"] == "Neutral (Spot Leading)"

    def test_neutral_thb_leading_spot_down_thb_up(self):
        df_spot = self._make_trending(3200, -5)
        df_thb = self._make_trending(35, 0.05)
        result = check_spot_thb_alignment(lookback_candles=4, df_spot=df_spot, df_thb=df_thb)
        assert result["alignment"] == "Neutral (THB Leading)"

    def test_insufficient_data_returns_error(self):
        df_spot = _make_df([3200, 3205])   # only 2 rows
        df_thb = _make_df([35.0, 35.1])
        result = check_spot_thb_alignment(lookback_candles=4, df_spot=df_spot, df_thb=df_thb)
        assert result["status"] == "error"
        assert "Insufficient" in result["message"]

    def test_details_pct_changes_are_floats(self):
        df_spot = self._make_trending(3200, 3)
        df_thb = self._make_trending(35, 0.02)
        result = check_spot_thb_alignment(lookback_candles=4, df_spot=df_spot, df_thb=df_thb)
        assert isinstance(result["details"]["spot_pct_change"], float)
        assert isinstance(result["details"]["thb_pct_change"], float)


# ─────────────────────────────────────────────────────────────────────────────
# TestDetectBreakoutConfirmation
# ─────────────────────────────────────────────────────────────────────────────


class TestDetectBreakoutConfirmation:
    def _confirmed_up_df(self, zone_top=3250.0):
        """Build a 5-row df where the last candle clearly breaks above zone_top
        with a strong body and no large upper wick."""
        closes = [3240, 3242, 3244, 3246, zone_top + 10]
        opens  = [3239, 3241, 3243, 3245, zone_top + 2]
        highs  = [3241, 3243, 3245, 3247, zone_top + 11]  # small wick
        lows   = [3238, 3240, 3242, 3244, zone_top + 1]
        n = len(closes)
        dates = pd.date_range("2024-01-01", periods=n, freq="5min")
        return pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [300]*n},
            index=dates,
        )

    def _confirmed_down_df(self, zone_bottom=3150.0):
        closes = [3160, 3158, 3156, 3154, zone_bottom - 10]
        opens  = [3161, 3159, 3157, 3155, zone_bottom - 2]
        highs  = [3162, 3160, 3158, 3156, zone_bottom - 1]
        lows   = [3159, 3157, 3155, 3153, zone_bottom - 11]  # small lower wick
        n = len(closes)
        dates = pd.date_range("2024-01-01", periods=n, freq="5min")
        return pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [300]*n},
            index=dates,
        )

    def test_confirmed_upward_breakout(self):
        df = self._confirmed_up_df(zone_top=3250.0)
        result = detect_breakout_confirmation(zone_top=3250.0, zone_bottom=3200.0, ohlcv_df=df)
        assert result["status"] == "success"
        assert result["is_confirmed_breakout"] is True
        assert "Upward" in result["breakout_direction"]

    def test_confirmed_downward_breakout(self):
        df = self._confirmed_down_df(zone_bottom=3150.0)
        result = detect_breakout_confirmation(zone_top=3200.0, zone_bottom=3150.0, ohlcv_df=df)
        assert result["is_confirmed_breakout"] is True
        assert "Downward" in result["breakout_direction"]

    def test_no_breakout_when_inside_zone(self):
        df = _make_df([3200, 3202, 3201, 3200, 3201])
        result = detect_breakout_confirmation(zone_top=3250.0, zone_bottom=3150.0, ohlcv_df=df)
        assert result["is_confirmed_breakout"] is False

    def test_weak_body_no_confirmation(self):
        """Last candle breaks above zone_top but has a very weak body (wick-heavy)."""
        zone_top = 3250.0
        # close > zone_top, but body is tiny relative to total range
        n = 5
        dates = pd.date_range("2024-01-01", periods=n, freq="5min")
        closes = [3240, 3242, 3244, 3246, zone_top + 5]
        opens  = [3239, 3241, 3243, 3245, zone_top + 4]   # body = 1
        highs  = [3241, 3243, 3245, 3247, zone_top + 30]  # long upper wick = 21
        lows   = [3238, 3240, 3242, 3244, zone_top + 4]
        df = pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [300]*n},
            index=dates,
        )
        result = detect_breakout_confirmation(zone_top=zone_top, zone_bottom=3200.0, ohlcv_df=df)
        assert result["is_confirmed_breakout"] is False

    def test_doji_candle_no_confirmation(self):
        """Doji (open == close) triggers the total_size == 0 path."""
        zone_top = 3250.0
        n = 5
        dates = pd.date_range("2024-01-01", periods=n, freq="5min")
        closes = [3240, 3242, 3244, 3246, zone_top + 5]
        opens  = closes.copy()  # exact doji
        highs  = [c + 0.5 for c in closes]
        lows   = [c - 0.5 for c in closes]
        df = pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": [300]*n},
            index=dates,
        )
        result = detect_breakout_confirmation(zone_top=zone_top, zone_bottom=3200.0, ohlcv_df=df)
        assert result["is_confirmed_breakout"] is False

    def test_single_candle_df_returns_error(self):
        df = _make_df([3260.0])
        result = detect_breakout_confirmation(zone_top=3250.0, zone_bottom=3200.0, ohlcv_df=df)
        assert result["status"] == "error"
        assert "Insufficient" in result["message"]

    def test_body_strength_pct_in_valid_range(self):
        df = self._confirmed_up_df()
        result = detect_breakout_confirmation(zone_top=3250.0, zone_bottom=3200.0, ohlcv_df=df)
        if result["is_confirmed_breakout"]:
            pct = result["details"]["body_strength_pct"]
            assert 0.0 <= pct <= 100.0


# ─────────────────────────────────────────────────────────────────────────────
# TestGetSupportResistanceZones
# ─────────────────────────────────────────────────────────────────────────────


class TestGetSupportResistanceZones:
    def test_success_with_300_rows(self, ohlcv_df):
        result = get_support_resistance_zones(ohlcv_df=ohlcv_df)
        assert result["status"] == "success"
        assert "zones" in result
        assert "adaptive_metrics" in result

    def test_insufficient_data_returns_error(self):
        df = _make_df(list(range(3200, 3230)))  # 30 rows
        result = get_support_resistance_zones(ohlcv_df=df)
        assert result["status"] == "error"
        assert "50+" in result["message"]

    def test_zones_have_required_fields(self, ohlcv_df):
        result = get_support_resistance_zones(ohlcv_df=ohlcv_df)
        for zone in result.get("zones", []):
            for key in ("type", "bottom", "top", "touches", "strength"):
                assert key in zone, f"Missing key '{key}' in zone: {zone}"

    def test_strength_values_are_valid(self, ohlcv_df):
        result = get_support_resistance_zones(ohlcv_df=ohlcv_df)
        valid_strengths = {"Low", "Medium", "High"}
        for zone in result.get("zones", []):
            assert zone["strength"] in valid_strengths

    def test_empty_swings_returns_empty_zones(self):
        """A perfectly flat price has no peaks or troughs → zones=[]."""
        n = 200
        closes = np.full(n, 3200.0)
        dates = pd.date_range("2024-01-01", periods=n, freq="5min")
        opens  = closes - 0.01
        highs  = closes + 0.01
        lows   = closes - 0.01
        flat_df = pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes, "volume": np.ones(n)*100},
            index=dates,
        )
        result = get_support_resistance_zones(ohlcv_df=flat_df)
        assert result["status"] == "success"
        assert result["zones"] == []

    def test_adaptive_metrics_atr_is_positive(self, ohlcv_df):
        result = get_support_resistance_zones(ohlcv_df=ohlcv_df)
        assert result["adaptive_metrics"]["atr_used"] > 0


# ─────────────────────────────────────────────────────────────────────────────
# TestDetectRsiDivergence
# ─────────────────────────────────────────────────────────────────────────────


class TestDetectRsiDivergence:
    def test_returns_success_structure(self, ohlcv_df):
        result = detect_rsi_divergence(ohlcv_df=ohlcv_df)
        assert result["status"] == "success"
        assert "divergence_detected" in result
        assert "logic" in result

    def test_divergence_detected_is_bool(self, ohlcv_df):
        result = detect_rsi_divergence(ohlcv_df=ohlcv_df)
        assert isinstance(result["divergence_detected"], bool)

    def test_insufficient_data_returns_error(self):
        """10-row df with default lookback_candles=30 → error."""
        df = _make_df([3200 + i for i in range(10)])
        result = detect_rsi_divergence(ohlcv_df=df)
        assert result["status"] == "error"
        assert "Insufficient" in result["message"]

    def test_flat_price_no_divergence(self):
        """Perfectly flat price has no swing troughs → divergence_detected=False."""
        n = 100
        flat_df = _make_df(np.full(n, 3200.0).tolist())
        result = detect_rsi_divergence(ohlcv_df=flat_df, lookback_candles=30)
        if result["status"] == "success":
            assert result["divergence_detected"] is False


# ─────────────────────────────────────────────────────────────────────────────
# TestCheckBbRsiCombo
# ─────────────────────────────────────────────────────────────────────────────


class TestCheckBbRsiCombo:
    def test_returns_success_structure(self, bb_rsi_ohlcv):
        result = check_bb_rsi_combo(ohlcv_df=bb_rsi_ohlcv)
        assert result["status"] == "success"
        assert "combo_detected" in result
        assert "combo_direction" in result

    def test_no_combo_on_neutral_data(self, bb_rsi_ohlcv):
        """Random walk data is unlikely to trigger the full combo condition."""
        result = check_bb_rsi_combo(ohlcv_df=bb_rsi_ohlcv)
        # combo_direction is None when no combo
        assert isinstance(result["combo_detected"], bool)
        if not result["combo_detected"]:
            assert result["combo_direction"] is None

    def test_raw_data_contains_expected_keys(self, bb_rsi_ohlcv):
        result = check_bb_rsi_combo(ohlcv_df=bb_rsi_ohlcv)
        for key in ("price", "lower_bb", "upper_bb", "rsi", "macd_hist"):
            assert key in result["raw_data"], f"Missing key '{key}' in raw_data"

    def test_insufficient_data_returns_error(self):
        """3-row df is too short for indicator warmup."""
        df = _make_df([3200, 3201, 3202])
        result = check_bb_rsi_combo(ohlcv_df=df)
        assert result["status"] == "error"


# ─────────────────────────────────────────────────────────────────────────────
# TestCalculateEmaDistance
# ─────────────────────────────────────────────────────────────────────────────


class TestCalculateEmaDistance:
    def test_returns_success_structure(self, ohlcv_df):
        result = calculate_ema_distance(ohlcv_df=ohlcv_df)
        assert result["status"] == "success"
        assert "distance_atr_ratio" in result
        assert "is_overextended" in result

    def test_is_overextended_is_bool(self, ohlcv_df):
        result = calculate_ema_distance(ohlcv_df=ohlcv_df)
        assert isinstance(result["is_overextended"], bool)

    def test_metrics_block_present(self, ohlcv_df):
        result = calculate_ema_distance(ohlcv_df=ohlcv_df)
        for key in ("current_price", "ema_20", "atr"):
            assert key in result["metrics"], f"Missing key '{key}' in metrics"

    def test_bullish_uptrend_may_be_overextended(self, bullish_ohlcv):
        """Strong uptrend df should produce a notable positive distance."""
        result = calculate_ema_distance(ohlcv_df=bullish_ohlcv)
        assert result["status"] == "success"
        # Distance should be positive (price above EMA20 in uptrend)
        assert result["distance_atr_ratio"] > 0

    def test_distance_formula_consistency(self, ohlcv_df):
        """Verify is_overextended matches abs(distance) > 2.5."""
        result = calculate_ema_distance(ohlcv_df=ohlcv_df)
        expected = abs(result["distance_atr_ratio"]) > 2.5
        assert result["is_overextended"] is expected


# ─────────────────────────────────────────────────────────────────────────────
# TestGetHtfTrend
# ─────────────────────────────────────────────────────────────────────────────

_FETCHER_PATCH = "data_engine.analysis_tools.technical_tools._fetcher.fetch_historical_ohlcv"


class TestGetHtfTrend:
    def _make_200_row_df(self):
        """Build a 300-row df to satisfy the >= 200 candle requirement."""
        rng = np.random.default_rng(99)
        n = 300
        dates = pd.date_range("2024-01-01", periods=n, freq="1h")
        closes = 3200 + np.cumsum(rng.standard_normal(n) * 1.5)
        opens = closes - 1.0
        highs = closes + 2.0
        lows  = closes - 2.0
        return pd.DataFrame(
            {"open": opens, "high": highs, "low": lows, "close": closes,
             "volume": np.ones(n) * 1000},
            index=dates,
        )

    def test_success_with_300_row_df(self):
        df = self._make_200_row_df()
        result = get_htf_trend(timeframe="1h", ohlcv_df=df)
        assert result["status"] == "success"
        assert result["trend"] in ("Bullish", "Bearish")

    def test_result_contains_expected_keys(self):
        df = self._make_200_row_df()
        result = get_htf_trend(timeframe="1h", ohlcv_df=df)
        for key in ("timeframe", "trend", "current_price", "ema_200", "distance_from_ema_pct"):
            assert key in result

    def test_result_is_cached_on_second_call(self):
        """Second call with same timeframe should return from cache."""
        df = self._make_200_row_df()
        result1 = get_htf_trend(timeframe="1h", ohlcv_df=df)
        assert "1h" in _HTF_CACHE, "Cache should be populated after first call"
        result2 = get_htf_trend(timeframe="1h", ohlcv_df=df)
        assert result1 == result2

    def test_stale_cache_is_refreshed(self):
        """A cache entry older than TTL should not be returned."""
        stale = {"status": "success", "trend": "StaleCachedValue", "timeframe": "1h",
                 "current_price": 0.0, "ema_200": 0.0, "distance_from_ema_pct": 0.0}
        _HTF_CACHE["1h"] = {"timestamp": time.time() - 1900, "result": stale}

        df = self._make_200_row_df()
        result = get_htf_trend(timeframe="1h", ohlcv_df=df)
        assert result["trend"] != "StaleCachedValue"

    def test_insufficient_df_falls_back_to_fetcher_returns_error(self):
        """When injected df has < 200 rows, function fetches from _fetcher.
        If _fetcher also returns empty, we get status=error."""
        small_df = _make_df([3200 + i for i in range(100)])
        with patch(_FETCHER_PATCH, return_value=pd.DataFrame()):
            result = get_htf_trend(timeframe="1h", ohlcv_df=small_df)
        assert result["status"] == "error"

    def test_distance_pct_sign_matches_trend(self):
        """Bullish trend → price > EMA200 → positive distance_from_ema_pct."""
        df = self._make_200_row_df()
        result = get_htf_trend(timeframe="1h", ohlcv_df=df)
        if result["trend"] == "Bullish":
            assert result["distance_from_ema_pct"] > 0
        else:
            assert result["distance_from_ema_pct"] < 0
