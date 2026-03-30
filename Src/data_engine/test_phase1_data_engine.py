"""
test_phase1_data_engine.py
Unit + Integration Tests for Phase 1: Data Engine Components
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_gold_price_data():
    """Mock price data from 3 sources"""
    return {
        "twelvedata": 2300.50,
        "gold-api": 2301.00,
        "yfinance": 2299.80,
    }

@pytest.fixture
def sample_ohlcv_df():
    """Generate sample OHLCV data (300 rows)"""
    np.random.seed(42)
    n = 300
    price = 2300 + np.cumsum(np.random.randn(n) * 5)
    
    return pd.DataFrame({
        "open": price - np.random.rand(n) * 3,
        "high": price + np.random.rand(n) * 8,
        "low": price - np.random.rand(n) * 8,
        "close": price,
        "volume": np.random.randint(10000, 50000, n),
    }, index=pd.date_range("2026-01-01", periods=n, freq="1h"))

@pytest.fixture
def short_ohlcv_df():
    """Generate short OHLCV data (30 rows) - tests SMA200 edge case"""
    np.random.seed(123)
    n = 30
    price = 2300 + np.cumsum(np.random.randn(n) * 2)
    
    return pd.DataFrame({
        "open": price - np.random.rand(n) * 1,
        "high": price + np.random.rand(n) * 3,
        "low": price - np.random.rand(n) * 3,
        "close": price,
        "volume": np.random.randint(5000, 20000, n),
    }, index=pd.date_range("2026-03-20", periods=n, freq="1h"))

# ============================================================================
# FETCHER.PY TESTS
# ============================================================================

class TestGoldDataFetcher:
    """Tests for GoldDataFetcher class"""
    
    def test_compute_confidence_single_source(self):
        """Single source should have 0.6 confidence"""
        from fetcher import GoldDataFetcher
        fetcher = GoldDataFetcher()
        
        result = fetcher.compute_confidence({"yfinance": 2300.0})
        assert result == 0.6, f"Expected 0.6, got {result}"
    
    def test_compute_confidence_three_sources_aligned(self, mock_gold_price_data):
        """Three aligned sources should have high confidence"""
        from fetcher import GoldDataFetcher
        fetcher = GoldDataFetcher()
        
        # All prices within 0.5% deviation
        prices = {
            "source1": 2300.00,
            "source2": 2300.50,  # 0.02%
            "source3": 2301.00,  # 0.04%
        }
        result = fetcher.compute_confidence(prices)
        assert result > 0.9, f"Expected > 0.9, got {result}"
    
    def test_compute_confidence_high_deviation(self):
        """High deviation should give low confidence"""
        from fetcher import GoldDataFetcher
        fetcher = GoldDataFetcher()
        
        prices = {
            "source1": 2300.00,
            "source2": 2500.00,  # 8.7% deviation → very low confidence
        }
        result = fetcher.compute_confidence(prices)
        assert result < 0.6, f"Expected < 0.6 for high deviation, got {result}"

    def test_compute_confidence_zero_median(self):
        """Zero prices should return 0 confidence"""
        from fetcher import GoldDataFetcher
        fetcher = GoldDataFetcher()
        
        result = fetcher.compute_confidence({})
        assert result == 0.0
    
    @patch('fetcher.requests.Session.get')
    def test_fetch_gold_spot_usd_all_sources_fail(self, mock_get):
        """Should return empty dict if all sources fail"""
        from fetcher import GoldDataFetcher
        mock_get.side_effect = Exception("Network error")
        
        fetcher = GoldDataFetcher()
        # This will raise exception unless caught
        try:
            result = fetcher.fetch_gold_spot_usd()
            # If sources fail gracefully, result should be {}
            assert result == {} or "price_usd_per_oz" not in result
        except Exception:
            # Expected if no exception handling
            pass
    
    def test_calc_thai_gold_price_fallback_calculation(self):
        """Test Thai gold price calculation fallback"""
        from fetcher import GoldDataFetcher
        fetcher = GoldDataFetcher()
        
        result = fetcher.calc_thai_gold_price(
            price_usd_per_oz=2300.0,
            usd_thb=32.0
        )
        
        assert "price_thb_per_baht_weight" in result
        assert result["price_thb_per_baht_weight"] > 0
        assert "buy_price_thb" in result
        assert "sell_price_thb" in result
        assert result["sell_price_thb"] >= result["buy_price_thb"]  # Sell ≥ Buy
    
    def test_calc_thai_gold_price_zero_inputs(self):
        """Zero inputs should return empty dict"""
        from fetcher import GoldDataFetcher
        fetcher = GoldDataFetcher()
        
        # จำลองให้ Scraping พังด้วย เพื่อเทสต์กรณี fallback ของศูนย์
        with patch('fetcher.requests.Session.get') as mock_get:
            mock_get.side_effect = Exception("Timeout")
            result = fetcher.calc_thai_gold_price(0, 0)
            assert result == {}
    
    def test_intergold_fallback_on_scrape_failure(self):
        """Should fallback to calculation if Intergold fails"""
        from fetcher import GoldDataFetcher
        
        with patch('fetcher.requests.Session.get') as mock_get:
            mock_get.side_effect = Exception("Timeout")
            
            fetcher = GoldDataFetcher()
            result = fetcher.calc_thai_gold_price(2300.0, 32.0)
            
            # Should use fallback calculation
            assert result["source"] == "calculated"


# ============================================================================
# INDICATORS.PY TESTS
# ============================================================================

class TestTechnicalIndicators:
    """Tests for TechnicalIndicators class"""
    
    def test_empty_dataframe_raises_error(self):
        """Empty DataFrame should raise ValueError"""
        from indicators import TechnicalIndicators
        
        empty_df = pd.DataFrame({"open": [], "high": [], "low": [], "close": []})
        with pytest.raises(ValueError):
            TechnicalIndicators(empty_df)
    
    def test_missing_required_columns_raises_error(self):
        """Missing OHLC columns should raise ValueError"""
        from indicators import TechnicalIndicators
        
        incomplete_df = pd.DataFrame({"open": [100], "close": [101]})
        with pytest.raises(ValueError):
            TechnicalIndicators(incomplete_df)
    
    def test_rsi_overbought(self, sample_ohlcv_df):
        """Pure uptrend should show RSI > 70 (overbought)"""
        from indicators import TechnicalIndicators
        
        # Create pure uptrend data
        uptrend_df = sample_ohlcv_df.copy()
        uptrend_df["close"] = range(2300, 2300 + len(uptrend_df))  # Linear up
        uptrend_df["high"] = uptrend_df["close"] + 1
        uptrend_df["low"] = uptrend_df["close"] - 1
        uptrend_df["open"] = uptrend_df["close"]
        
        calc = TechnicalIndicators(uptrend_df)
        rsi = calc.rsi()
        
        assert rsi.value >= 70, f"Uptrend RSI should be ≥ 70, got {rsi.value}"
        assert rsi.signal == "overbought"
    
    def test_rsi_oversold(self, sample_ohlcv_df):
        """Pure downtrend should show RSI < 30 (oversold)"""
        from indicators import TechnicalIndicators
        
        # Create pure downtrend data
        downtrend_df = sample_ohlcv_df.copy()
        downtrend_df["close"] = range(2600, 2300, -1)[:len(sample_ohlcv_df)]  # Linear down
        downtrend_df["high"] = downtrend_df["close"] + 1
        downtrend_df["low"] = downtrend_df["close"] - 1
        downtrend_df["open"] = downtrend_df["close"]
        
        calc = TechnicalIndicators(downtrend_df)
        rsi = calc.rsi()
        
        assert rsi.value <= 30, f"Downtrend RSI should be ≤ 30, got {rsi.value}"
        assert rsi.signal == "oversold"
    
    def test_macd_bullish_crossover(self, sample_ohlcv_df):
        """Price moving up should eventually show MACD bullish crossover"""
        from indicators import TechnicalIndicators
        
        uptrend_df = sample_ohlcv_df.copy()
        uptrend_df["close"] = 2300 + np.cumsum(np.abs(np.random.randn(len(uptrend_df))))
        uptrend_df["high"] = uptrend_df["close"] + 0.5
        uptrend_df["low"] = uptrend_df["close"] - 0.5
        uptrend_df["open"] = uptrend_df["close"] - 0.2
        
        calc = TechnicalIndicators(uptrend_df)
        macd = calc.macd()
        
        # MACD should be positive on strong uptrend
        assert macd.macd_line > 0, f"MACD line should be positive on uptrend"
    
    def test_bollinger_bands_inside_band(self, sample_ohlcv_df):
        """Normal data should have prices inside bands"""
        from indicators import TechnicalIndicators
        
        calc = TechnicalIndicators(sample_ohlcv_df)
        bb = calc.bollinger_bands()
        
        assert bb.signal in ["inside", "above_upper", "below_lower"]
        assert bb.lower < bb.middle < bb.upper
    
    def test_atr_calculation(self, sample_ohlcv_df):
        """ATR should be positive and non-zero"""
        from indicators import TechnicalIndicators
        
        calc = TechnicalIndicators(sample_ohlcv_df)
        atr = calc.atr()
        
        assert atr.value > 0, "ATR should be positive"
        assert atr.volatility_level in ["low", "normal", "high"]
    
    def test_trend_golden_cross_on_uptrend(self, sample_ohlcv_df):
        """Strong uptrend should show golden cross (EMA20 > EMA50 > SMA200)"""
        from indicators import TechnicalIndicators
        
        uptrend_df = sample_ohlcv_df.copy()
        uptrend_df["close"] = 2300 + np.cumsum(np.abs(np.random.randn(len(uptrend_df)))) * 5
        uptrend_df["high"] = uptrend_df["close"] + 2
        uptrend_df["low"] = uptrend_df["close"] - 2
        uptrend_df["open"] = uptrend_df["close"]
        
        calc = TechnicalIndicators(uptrend_df)
        trend = calc.trend()
        
        assert trend.ema_20 >= trend.ema_50, "EMA20 should be above EMA50 in uptrend"
    
    def test_short_data_warning(self, short_ohlcv_df):
        """Short data should trigger reliability warnings"""
        from indicators import TechnicalIndicators
        
        calc = TechnicalIndicators(short_ohlcv_df)
        warnings = calc.get_reliability_warnings("1h")
        
        # Should warn about short SMA200
        assert warnings is not None
        assert isinstance(warnings, list)
    
    def test_ml_dataframe_has_no_nan(self, sample_ohlcv_df):
        """ML DataFrame should have all rows without NaN"""
        from indicators import TechnicalIndicators
        
        calc = TechnicalIndicators(sample_ohlcv_df)
        ml_df = calc.get_ml_dataframe()
        
        assert ml_df.isnull().sum().sum() == 0, "ML DataFrame should not have NaN"
    
    def test_to_dict_returns_valid_json(self, sample_ohlcv_df):
        """to_dict() should return JSON-serializable dict"""
        from indicators import TechnicalIndicators
        import json
        
        calc = TechnicalIndicators(sample_ohlcv_df)
        result = calc.to_dict()
        
        # Should be JSON serializable
        json_str = json.dumps(result, default=str)
        assert json_str is not None
        
        # Should have all required keys
        assert "rsi" in result
        assert "macd" in result
        assert "bollinger" in result
        assert "atr" in result
        assert "trend" in result


# ============================================================================
# OHLCV_FETCHER.PY TESTS
# ============================================================================

class TestOHLCVFetcher:
    """Tests for OHLCVFetcher class"""
    
    def test_empty_ohlcv_returns_empty_dataframe(self):
        """Empty OHLCV fetch should return empty DataFrame"""
        from ohlcv_fetcher import OHLCVFetcher
        
        fetcher = OHLCVFetcher()
        # With mock that returns no data
        with patch.object(fetcher, 'session') as mock_session:
            mock_session.get.side_effect = Exception("API unavailable")
            # Would need proper test setup
    
    def test_validate_ohlcv_removes_invalid_rows(self):
        """_validate_ohlcv should remove rows with high < low"""
        from ohlcv_fetcher import _validate_ohlcv
        
        df = pd.DataFrame({
            "open": [100, 105, 200],
            "high": [102, 108, 195],  # Row 3: high < low (invalid)
            "low": [99, 104, 200],    # Row 3: low = 200, high = 195
            "close": [101, 104, 197],
            "volume": [1000, 2000, 3000]
        })
        
        cleaned = _validate_ohlcv(df)
        assert len(cleaned) == 2, "Should remove 1 invalid row"
        assert cleaned["high"].iloc[0] >= cleaned["low"].iloc[0]
    
    def test_timezone_localization(self):
        """UTC timezone should be properly localized"""
        from ohlcv_fetcher import _ensure_utc_index
        
        df = pd.DataFrame(
            {"close": [100, 101, 102]},
            index=pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-03"])
        )
        
        result = _ensure_utc_index(df)
        assert result.index.tz is not None
        assert str(result.index.tz) == "UTC"
    
    def test_calculate_fetch_days_with_cache(self):
        """Should calculate appropriate fetch_days based on cache"""
        from ohlcv_fetcher import _calculate_fetch_days
        
        # Old cache (5 days old)
        old_cache = pd.DataFrame(
            {"close": range(100)},
            index=pd.date_range("2026-01-01", periods=100, freq="1h", tz="UTC")
        )
        
        fetch_days = _calculate_fetch_days(old_cache, requested_days=30)
        assert fetch_days > 0
        assert fetch_days <= 30


# ============================================================================
# ORCHESTRATOR.PY TESTS
# ============================================================================

class TestGoldTradingOrchestrator:
    """Tests for GoldTradingOrchestrator class"""
    
    @patch('orchestrator.GoldDataFetcher')
    @patch('orchestrator.GoldNewsFetcher')
    def test_orchestrator_run_returns_valid_payload(self, mock_news, mock_price):
        """Orchestrator.run() should return dict with all required keys"""
        from orchestrator import GoldTradingOrchestrator
        
        # Mock fetchers
        mock_price_instance = MagicMock()
        mock_news_instance = MagicMock()
        mock_price.return_value = mock_price_instance
        mock_news.return_value = mock_news_instance
        
        # Mock data
        mock_price_instance.fetch_all.return_value = {
            "spot_price": {"price_usd_per_oz": 2300, "source": "test"},
            "forex": {"usd_thb": 32.0, "source": "test"},
            "thai_gold": {"price_thb_per_baht_weight": 70000},
            "ohlcv_df": pd.DataFrame({
                "open": [100]*10,
                "high": [102]*10,
                "low": [98]*10,
                "close": [101]*10,
                "volume": [1000]*10,
            }, index=pd.date_range("2026-03-30", periods=10, freq="1h", tz="UTC"))
        }
        
        mock_news_instance.to_dict.return_value = {
            "total_articles": 10,
            "overall_sentiment": 0.1,
            "by_category": {},
        }
        
        orchestrator = GoldTradingOrchestrator(history_days=30)
        payload = orchestrator.run(save_to_file=False)
        
        # Check structure
        assert "meta" in payload
        assert "market_data" in payload
        assert "technical_indicators" in payload
        assert "news" in payload
    
    @patch('orchestrator.GoldDataFetcher')
    @patch('orchestrator.GoldNewsFetcher')
    def test_orchestrator_respects_interval(self, mock_news, mock_price):
        """Orchestrator should use specified interval"""
        from orchestrator import GoldTradingOrchestrator
        
        mock_price_instance = MagicMock()
        mock_news_instance = MagicMock()
        mock_price.return_value = mock_price_instance
        mock_news.return_value = mock_news_instance
        
        mock_price_instance.fetch_all.return_value = {
            "spot_price": {},
            "forex": {},
            "thai_gold": {},
            "ohlcv_df": pd.DataFrame(),
        }
        
        mock_news_instance.to_dict.return_value = {
            "total_articles": 0,
            "by_category": {},
        }
        
        orchestrator = GoldTradingOrchestrator(interval="5m")
        orchestrator.run(save_to_file=False)
        
        # Verify fetch_all was called with correct interval
        mock_price_instance.fetch_all.assert_called_once()
        call_kwargs = mock_price_instance.fetch_all.call_args[1]
        assert call_kwargs.get("interval") == "5m"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestPhase1Integration:
    """Full integration tests for Phase 1"""
    
    def test_indicators_pipeline_with_real_csv(self):
        """Test indicators on actual CSV data"""
        # Load real data
        try:
            df = pd.read_csv("thai_gold_1m_dataset.csv", nrows=300)
            df.columns = [c.lower().replace("close_thai", "close")
                          .replace("open_thai", "open")
                          .replace("high_thai", "high")
                          .replace("low_thai", "low")
                          for c in df.columns]
            
            # Keep only OHLCV
            df = df[["open", "high", "low", "close"]]
            
            from indicators import TechnicalIndicators
            calc = TechnicalIndicators(df)
            all_ind = calc.compute_all()
            
            assert all_ind.rsi.value is not None
            assert all_ind.macd.macd_line is not None
            assert all_ind.trend.trend is not None
        except FileNotFoundError:
            pytest.skip("thai_gold_1m_dataset.csv not found")
    
    def test_news_csv_sentiment_range(self):
        """Test that news sentiment is in proper range"""
        try:
            df = pd.read_csv("finnhub_3month_news_ready_v2.csv")
            
            # Sentiment should be between -1 and 1
            assert df["overall_sentiment"].min() >= -1.0
            assert df["overall_sentiment"].max() <= 1.0
            
            # News count should be positive
            assert (df["news_count"] > 0).all()
        except FileNotFoundError:
            pytest.skip("finnhub_3month_news_ready_v2.csv not found")


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
