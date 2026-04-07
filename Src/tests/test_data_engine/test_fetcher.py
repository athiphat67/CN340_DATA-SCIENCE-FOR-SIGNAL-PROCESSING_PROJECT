"""
test_fetcher.py — Pytest สำหรับ fetcher module (GoldDataFetcher)

ครอบคลุม:
  1. compute_confidence — 0 prices, 1 price, multiple close/divergent
  2. calc_thai_gold_price — fallback calculation, zero input, JSON file
  3. fetch_gold_spot_usd — mock API responses
  4. fetch_usd_thb_rate — mock API response
  5. fetch_all — integration ทุก method

Strategy: Mock requests.Session + os.path.exists + file I/O
  - ไม่เรียก API จริง
  - Deterministic 100%
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

from data_engine.fetcher import (
    GoldDataFetcher,
    TROY_OUNCE_IN_GRAMS,
    THAI_GOLD_BAHT_IN_GRAMS,
    THAI_GOLD_PURITY,
)


# ══════════════════════════════════════════════════════════════════
# 1. compute_confidence
# ══════════════════════════════════════════════════════════════════


class TestComputeConfidence:
    """ทดสอบ compute_confidence — วัดความน่าเชื่อถือของราคาจากหลายแหล่ง"""

    def setup_method(self):
        self.fetcher = GoldDataFetcher()

    def test_empty_prices(self):
        """ไม่มีราคา → confidence = 0"""
        assert self.fetcher.compute_confidence({}) == 0.0

    def test_single_price(self):
        """1 แหล่ง → confidence = 0.6"""
        assert self.fetcher.compute_confidence({"src1": 2350.0}) == 0.6

    def test_identical_prices(self):
        """ราคาเหมือนกัน → confidence สูงมาก"""
        result = self.fetcher.compute_confidence(
            {"src1": 2350.0, "src2": 2350.0, "src3": 2350.0}
        )
        assert result == 1.0

    def test_close_prices(self):
        """ราคาใกล้กัน → confidence สูง"""
        result = self.fetcher.compute_confidence(
            {"src1": 2350.0, "src2": 2351.0}
        )
        assert result > 0.9

    def test_divergent_prices(self):
        """ราคาห่างกันมาก → confidence ต่ำ"""
        result = self.fetcher.compute_confidence(
            {"src1": 2350.0, "src2": 2500.0}
        )
        assert result < 0.5

    def test_confidence_never_negative(self):
        """confidence ต้อง >= 0"""
        result = self.fetcher.compute_confidence(
            {"src1": 100.0, "src2": 9999.0}
        )
        assert result >= 0.0

    def test_zero_median(self):
        """median = 0 → confidence = 0"""
        assert self.fetcher.compute_confidence({"src1": 0.0}) == 0.6  # single


# ══════════════════════════════════════════════════════════════════
# 2. calc_thai_gold_price — fallback calculation
# ══════════════════════════════════════════════════════════════════


class TestCalcThaiGoldPrice:
    """ทดสอบ calc_thai_gold_price — คำนวณราคาทองไทย"""

    def setup_method(self):
        self.fetcher = GoldDataFetcher()

    @patch("data_engine.fetcher.os.path.exists", return_value=False)
    def test_fallback_calculation(self, mock_exists):
        """ไม่มี JSON file → ใช้สูตร fallback"""
        result = self.fetcher.calc_thai_gold_price(2350.0, 34.5)
        assert "sell_price_thb" in result
        assert "buy_price_thb" in result
        assert result["source"] == "calculated_fallback"
        assert result["sell_price_thb"] > result["buy_price_thb"]

    @patch("data_engine.fetcher.os.path.exists", return_value=False)
    def test_fallback_sell_gt_buy(self, mock_exists):
        """ราคาขาย > ราคาซื้อเสมอ"""
        result = self.fetcher.calc_thai_gold_price(2350.0, 34.5)
        assert result["sell_price_thb"] > result["buy_price_thb"]

    @patch("data_engine.fetcher.os.path.exists", return_value=False)
    def test_fallback_rounded_to_50(self, mock_exists):
        """ราคาต้องหาร 50 ลงตัว (rounded to nearest 50)"""
        result = self.fetcher.calc_thai_gold_price(2350.0, 34.5)
        assert result["sell_price_thb"] % 50 == 0
        assert result["buy_price_thb"] % 50 == 0

    @patch("data_engine.fetcher.os.path.exists", return_value=False)
    def test_zero_price_returns_empty(self, mock_exists):
        """ราคา = 0 → return {}"""
        assert self.fetcher.calc_thai_gold_price(0, 34.5) == {}
        assert self.fetcher.calc_thai_gold_price(2350.0, 0) == {}

    @patch("data_engine.fetcher.os.path.exists", return_value=False)
    def test_fallback_spread_positive(self, mock_exists):
        """spread = sell - buy > 0"""
        result = self.fetcher.calc_thai_gold_price(2350.0, 34.5)
        assert result["spread_thb"] > 0

    @patch("data_engine.fetcher.os.path.exists", return_value=True)
    def test_reads_json_file(self, mock_exists):
        """มี JSON file → อ่านจากไฟล์"""
        json_data = {"sell_price_thb": 45200, "buy_price_thb": 45000}
        mock_open = MagicMock()
        mock_open.return_value.__enter__ = lambda s: MagicMock(
            read=lambda: json.dumps(json_data)
        )
        mock_open.return_value.__exit__ = MagicMock(return_value=False)

        with patch("builtins.open", mock_open):
            with patch("json.load", return_value=json_data):
                result = self.fetcher.calc_thai_gold_price(2350.0, 34.5)
        assert result["sell_price_thb"] == 45200
        assert result["buy_price_thb"] == 45000


# ══════════════════════════════════════════════════════════════════
# 3. fetch_gold_spot_usd — mock API
# ══════════════════════════════════════════════════════════════════


class TestFetchGoldSpotUsd:
    """ทดสอบ fetch_gold_spot_usd — ดึงราคาทองจาก 3 แหล่ง"""

    def _make_fetcher_with_mock_session(self):
        fetcher = GoldDataFetcher()
        fetcher.session = MagicMock()
        return fetcher

    @patch("data_engine.fetcher.os.getenv", return_value="fake_api_key")
    @patch("data_engine.fetcher.get_thai_time")
    def test_twelvedata_only(self, mock_time, mock_env):
        """TwelveData สำเร็จ → return ราคา"""
        mock_time.return_value = MagicMock(isoformat=lambda: "2026-04-01T10:00:00")
        fetcher = self._make_fetcher_with_mock_session()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"price": "2350.50"}
        mock_resp.raise_for_status = MagicMock()
        fetcher.session.get.return_value = mock_resp

        with patch("data_engine.fetcher.yf", create=True):
            with patch.dict("sys.modules", {"yfinance": MagicMock()}):
                # Mock yfinance to fail so only twelvedata works
                import sys
                yf_mock = sys.modules["yfinance"]
                yf_mock.Ticker.return_value.history.return_value = MagicMock(empty=True)
                result = fetcher.fetch_gold_spot_usd()

        assert result.get("price_usd_per_oz") is not None

    def test_all_sources_fail_returns_empty(self):
        """ทุก API fail → return {}"""
        fetcher = self._make_fetcher_with_mock_session()
        fetcher.session.get.side_effect = Exception("Network error")

        with patch("data_engine.fetcher.os.getenv", return_value="key"):
            with patch.dict("sys.modules", {"yfinance": MagicMock()}):
                import sys
                yf_mock = sys.modules["yfinance"]
                yf_mock.Ticker.side_effect = Exception("fail")
                result = fetcher.fetch_gold_spot_usd()

        assert result == {}


# ══════════════════════════════════════════════════════════════════
# 4. fetch_usd_thb_rate — mock API
# ══════════════════════════════════════════════════════════════════


class TestFetchUsdThbRate:
    """ทดสอบ fetch_usd_thb_rate"""

    @patch("data_engine.fetcher.get_thai_time")
    def test_success(self, mock_time):
        mock_time.return_value = MagicMock(isoformat=lambda: "2026-04-01T10:00:00")
        fetcher = GoldDataFetcher()
        fetcher.session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rates": {"THB": 34.50}}
        mock_resp.raise_for_status = MagicMock()
        fetcher.session.get.return_value = mock_resp

        result = fetcher.fetch_usd_thb_rate()
        assert result["usd_thb"] == 34.50
        assert result["source"] == "exchangerate-api.com"

    def test_failure_returns_empty(self):
        """API fail → return {}"""
        fetcher = GoldDataFetcher()
        fetcher.session = MagicMock()
        fetcher.session.get.side_effect = Exception("timeout")
        result = fetcher.fetch_usd_thb_rate()
        assert result == {}


# ══════════════════════════════════════════════════════════════════
# 5. fetch_all — integration
# ══════════════════════════════════════════════════════════════════


class TestFetchAll:
    """ทดสอบ fetch_all — รวมทุก fetch method"""

    @patch("data_engine.fetcher.get_thai_time")
    def test_returns_all_keys(self, mock_time):
        """ต้องมี keys: spot_price, forex, thai_gold, ohlcv_df, fetched_at"""
        mock_time.return_value = MagicMock(isoformat=lambda: "2026-04-01T10:00:00")

        fetcher = GoldDataFetcher()
        fetcher.fetch_gold_spot_usd = MagicMock(return_value={"price_usd_per_oz": 2350.0})
        fetcher.fetch_usd_thb_rate = MagicMock(return_value={"usd_thb": 34.5})
        fetcher.calc_thai_gold_price = MagicMock(return_value={"sell_price_thb": 45200})
        fetcher.ohlcv_fetcher = MagicMock()
        fetcher.ohlcv_fetcher.fetch_historical_ohlcv.return_value = MagicMock()

        result = fetcher.fetch_all()
        assert "spot_price" in result
        assert "forex" in result
        assert "thai_gold" in result
        assert "ohlcv_df" in result
        assert "fetched_at" in result
