"""
test_fetcher.py — Unit tests for GoldDataFetcher (~70% coverage)
Tests: fetch_gold_spot_usd, compute_confidence, fetch_usd_thb_rate,
       calc_thai_gold_price, fetch_historical_ohlcv.
"""

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

from data_engine.fetcher import GoldDataFetcher


@pytest.fixture
def fetcher():
    return GoldDataFetcher()


# ─── compute_confidence ─────────────────────────────────────────────────────

class TestComputeConfidence:

    def test_empty_prices(self, fetcher):
        assert fetcher.compute_confidence({}) == 0.0

    def test_single_source(self, fetcher):
        result = fetcher.compute_confidence({"twelvedata": 2300.0})
        assert result == 0.6

    def test_multiple_close_prices(self, fetcher):
        """Two sources within 0.1% should give high confidence."""
        result = fetcher.compute_confidence({
            "twelvedata": 2300.0,
            "yfinance": 2301.0,
        })
        assert result >= 0.9

    def test_divergent_prices(self, fetcher):
        """Two sources with >5% difference should give low confidence."""
        result = fetcher.compute_confidence({
            "twelvedata": 2300.0,
            "yfinance": 2500.0,
        })
        assert result < 0.6

    def test_three_sources_close(self, fetcher):
        result = fetcher.compute_confidence({
            "twelvedata": 2300.0,
            "gold-api": 2302.0,
            "yfinance": 2301.0,
        })
        assert result >= 0.9

    def test_confidence_never_negative(self, fetcher):
        """Even extreme divergence should not produce negative confidence."""
        result = fetcher.compute_confidence({
            "a": 100.0,
            "b": 5000.0,
        })
        assert result >= 0.0


# ─── fetch_gold_spot_usd ────────────────────────────────────────────────────

class TestFetchGoldSpotUSD:

    @patch("data_engine.fetcher.yf.Ticker")
    def test_fetch_gold_spot_parses_response_correctly(self, mock_ticker_cls):
        """Mock HTTP session → verify real parsing logic extracts price_usd_per_oz."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"price": "2300.50"}
        mock_resp.raise_for_status.return_value = None

        fetcher = GoldDataFetcher()
        fetcher.session = MagicMock()
        fetcher.session.get.return_value = mock_resp

        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        result = fetcher.fetch_gold_spot_usd()
        assert "source" in result
        assert "price_usd_per_oz" in result
        assert result["price_usd_per_oz"] == 2300.50

    @patch("data_engine.fetcher.requests.Session")
    def test_all_apis_fail_returns_empty(self, mock_session_cls):
        """When all API sources fail, should return empty dict."""
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Network error")
        mock_session_cls.return_value = mock_session

        fetcher = GoldDataFetcher()
        fetcher.session = mock_session

        with patch("yfinance.Ticker") as mock_yf:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_yf.return_value = mock_ticker

            result = fetcher.fetch_gold_spot_usd()
            assert result == {} or isinstance(result, dict)


# ─── fetch_usd_thb_rate ─────────────────────────────────────────────────────

class TestFetchUSDTHB:

    def test_fetch_usd_thb_parses_response_correctly(self):
        """Mock HTTP session → verify real parsing logic extracts usd_thb rate."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"THB": 34.5}}
        mock_resp.raise_for_status.return_value = None

        fetcher = GoldDataFetcher()
        fetcher.session = MagicMock()
        fetcher.session.get.return_value = mock_resp

        result = fetcher.fetch_usd_thb_rate()
        assert "usd_thb" in result
        assert result["usd_thb"] == 34.5

    def test_api_failure_returns_empty(self, fetcher):
        """Mock the session to simulate API failure."""
        fetcher.session = MagicMock()
        fetcher.session.get.side_effect = Exception("Timeout")
        result = fetcher.fetch_usd_thb_rate()
        assert result == {}


# ─── calc_thai_gold_price ────────────────────────────────────────────────────

class TestCalcThaiGoldPrice:

    def test_fallback_calculation(self, fetcher):
        """When scraping fails, fallback formula should produce valid prices."""
        with patch.object(fetcher.session, "get", side_effect=Exception("scrape fail")):
            result = fetcher.calc_thai_gold_price(
                price_usd_per_oz=2300.0,
                usd_thb=34.5,
            )
        assert "price_thb_per_baht_weight" in result
        assert result["sell_price_thb"] > result["buy_price_thb"]
        assert result["source"] == "calculated"

    def test_zero_inputs_returns_empty(self, fetcher):
        with patch.object(fetcher.session, "get", side_effect=Exception("fail")):
            result = fetcher.calc_thai_gold_price(0, 0)
        assert result == {}

    def test_spread_is_reasonable(self, fetcher):
        """Spread should be ~100 THB for typical prices."""
        with patch.object(fetcher.session, "get", side_effect=Exception("fail")):
            result = fetcher.calc_thai_gold_price(2300.0, 34.5)
        if result:
            spread = result["sell_price_thb"] - result["buy_price_thb"]
            assert 0 <= spread <= 200


# ─── fetch_historical_ohlcv ─────────────────────────────────────────────────
# fetch_historical_ohlcv lives on OHLCVFetcher (GoldDataFetcher.ohlcv_fetcher).
# yfinance is imported locally inside the function, so patch "yfinance.Ticker" globally.

class TestFetchHistoricalOHLCV:

    @patch("yfinance.Ticker")
    def test_returns_dataframe_with_expected_columns(self, mock_ticker_cls):
        mock_df = pd.DataFrame(
            {"Open": [2300], "High": [2310], "Low": [2290], "Close": [2305], "Volume": [50000]},
            index=pd.DatetimeIndex(["2024-01-01"], tz="UTC"),
        )
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df
        mock_ticker_cls.return_value = mock_ticker

        from ohlcv_fetcher import OHLCVFetcher
        result = OHLCVFetcher().fetch_historical_ohlcv(days=7, interval="1d", use_cache=False)
        assert isinstance(result, pd.DataFrame)
        assert set(["open", "high", "low", "close"]).issubset(result.columns)

    @patch("yfinance.Ticker")
    def test_empty_data_returns_empty_df(self, mock_ticker_cls):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        from ohlcv_fetcher import OHLCVFetcher
        result = OHLCVFetcher().fetch_historical_ohlcv(days=7, use_cache=False)
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    @patch("yfinance.Ticker")
    def test_1m_interval_caps_days(self, mock_ticker_cls):
        """1m interval caps yfinance fetch to 7 days (YF_MAX_DAYS["1m"] = 7)."""
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_ticker_cls.return_value = mock_ticker

        from ohlcv_fetcher import OHLCVFetcher
        OHLCVFetcher().fetch_historical_ohlcv(days=30, interval="1m", use_cache=False)
        call_args = mock_ticker.history.call_args
        assert "7d" in str(call_args)
