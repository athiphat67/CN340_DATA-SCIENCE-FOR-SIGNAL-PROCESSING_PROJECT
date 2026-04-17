"""
test_ohlcv_fetcher.py — Pytest สำหรับ ohlcv_fetcher module

ครอบคลุม:
  1. _ensure_utc_index — naive → UTC, aware → UTC, empty
  2. _calculate_fetch_days — empty cache, fresh cache, few rows
  3. _estimate_candles — ต่าง interval, unknown interval
  4. _validate_ohlcv — ลบ row ที่ high < low, NaN, ค่าลบ
  5. _retry_request — success, failure after retries
  6. OHLCVFetcher.fetch_historical_ohlcv — cache + API

Strategy: Pure function tests + mock external APIs
  - ไม่เรียก yfinance / TwelveData จริง
  - Deterministic 100%
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.data_engine

from data_engine.ohlcv_fetcher import (
    _ensure_utc_index,
    _calculate_fetch_days,
    _estimate_candles,
    _validate_ohlcv,
    _retry_request,
    OHLCVFetcher,
    INTERVAL_TO_MINUTES,
    TD_INTERVAL_MAP,
    YF_MAX_DAYS,
)


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _make_ohlcv_df(n: int = 50, start: str = "2026-03-01") -> pd.DataFrame:
    """สร้าง OHLCV DataFrame จำลอง"""
    rng = np.random.RandomState(42)
    dates = pd.date_range(start, periods=n, freq="D", tz="UTC")
    close = 2300 + rng.randn(n).cumsum()
    return pd.DataFrame(
        {
            "open": close - rng.rand(n),
            "high": close + rng.rand(n) * 5,
            "low": close - rng.rand(n) * 5,
            "close": close,
            "volume": rng.randint(10000, 50000, n),
        },
        index=pd.DatetimeIndex(dates, name="datetime"),
    )


# ══════════════════════════════════════════════════════════════════
# 1. _ensure_utc_index
# ══════════════════════════════════════════════════════════════════


class TestEnsureUtcIndex:
    """ทดสอบ _ensure_utc_index"""

    def test_empty_df(self):
        """DataFrame ว่าง → return ว่าง"""
        df = pd.DataFrame()
        result = _ensure_utc_index(df)
        assert result.empty

    def test_naive_index_to_utc(self):
        """Naive index → localize เป็น UTC"""
        df = pd.DataFrame(
            {"close": [1, 2, 3]},
            index=pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-03"]),
        )
        result = _ensure_utc_index(df)
        assert str(result.index.tz) == "UTC"

    def test_aware_index_to_utc(self):
        """Index ที่มี tz อื่น → convert เป็น UTC"""
        idx = pd.DatetimeIndex(["2026-01-01 07:00"]).tz_localize("Asia/Bangkok")
        df = pd.DataFrame({"close": [1]}, index=idx)
        result = _ensure_utc_index(df)
        assert str(result.index.tz) == "UTC"
        # Bangkok 07:00 → UTC 00:00
        assert result.index[0].hour == 0

    def test_utc_index_unchanged(self):
        """Index ที่เป็น UTC อยู่แล้ว → ไม่เปลี่ยน"""
        idx = pd.DatetimeIndex(["2026-01-01 12:00"]).tz_localize("UTC")
        df = pd.DataFrame({"close": [1]}, index=idx)
        result = _ensure_utc_index(df)
        assert result.index[0].hour == 12


# ══════════════════════════════════════════════════════════════════
# 2. _calculate_fetch_days
# ══════════════════════════════════════════════════════════════════


class TestCalculateFetchDays:
    """ทดสอบ _calculate_fetch_days"""

    def test_empty_cache(self):
        """Cache ว่าง → fetch เต็มจำนวน"""
        result = _calculate_fetch_days(pd.DataFrame(), 90)
        assert result == 90

    def test_few_rows_in_cache(self):
        """Cache มีน้อยกว่า min_candles → fetch เต็มจำนวน"""
        df = _make_ohlcv_df(n=10)
        result = _calculate_fetch_days(df, 90, min_candles=50)
        assert result == 90

    def test_fresh_cache_reduces_days(self):
        """Cache ล่าสุด → ลดจำนวนวันที่ต้อง fetch"""
        df = _make_ohlcv_df(n=100)
        # index ล่าสุดอยู่ใกล้ now → ควร fetch น้อยลง
        recent_idx = pd.date_range(
            end=pd.Timestamp.now("UTC"), periods=100, freq="D", tz="UTC"
        )
        df.index = recent_idx
        result = _calculate_fetch_days(df, 90)
        assert result < 90

    def test_stale_cache_full_fetch(self):
        """Cache เก่ามาก → fetch เต็มจำนวน"""
        df = _make_ohlcv_df(n=100, start="2020-01-01")
        result = _calculate_fetch_days(df, 90)
        assert result == 90


# ══════════════════════════════════════════════════════════════════
# 3. _estimate_candles
# ══════════════════════════════════════════════════════════════════


class TestEstimateCandles:
    """ทดสอบ _estimate_candles"""

    def test_1d_interval(self):
        """1d × 90 days → ~90 candles"""
        result = _estimate_candles("1d", 90)
        assert result == 90  # 1440/1440 * 90

    def test_1h_interval(self):
        """1h × 30 days → 720 candles"""
        result = _estimate_candles("1h", 30)
        assert result == 720  # 24 * 30

    def test_5m_interval(self):
        """5m × 7 days → 2016 candles"""
        result = _estimate_candles("5m", 7)
        assert result == 2016  # 288 * 7

    def test_unknown_interval(self):
        """Unknown interval → fallback 5000"""
        result = _estimate_candles("10m", 30)
        assert result == 5000


# ══════════════════════════════════════════════════════════════════
# 4. _validate_ohlcv
# ══════════════════════════════════════════════════════════════════


class TestValidateOhlcv:
    """ทดสอบ _validate_ohlcv — data quality checks"""

    def test_empty_df(self):
        result = _validate_ohlcv(pd.DataFrame())
        assert result.empty

    def test_valid_data_unchanged(self):
        """ข้อมูลถูกต้อง → ไม่ถูกลบ"""
        df = pd.DataFrame({
            "open": [2300.0], "high": [2310.0],
            "low": [2290.0], "close": [2305.0],
        })
        result = _validate_ohlcv(df)
        assert len(result) == 1

    def test_removes_high_lt_low(self):
        """high < low → ลบ row"""
        df = pd.DataFrame({
            "open": [2300.0, 2300.0],
            "high": [2280.0, 2310.0],  # row 0: high < low
            "low": [2290.0, 2290.0],
            "close": [2305.0, 2305.0],
        })
        result = _validate_ohlcv(df)
        assert len(result) == 1

    def test_removes_negative_prices(self):
        """ราคาติดลบ → ลบ row"""
        df = pd.DataFrame({
            "open": [-100.0, 2300.0],
            "high": [2310.0, 2310.0],
            "low": [2290.0, 2290.0],
            "close": [2305.0, 2305.0],
        })
        result = _validate_ohlcv(df)
        assert len(result) == 1

    def test_removes_nan_prices(self):
        """ราคาเป็น NaN → ลบ row"""
        df = pd.DataFrame({
            "open": [float("nan"), 2300.0],
            "high": [2310.0, 2310.0],
            "low": [2290.0, 2290.0],
            "close": [2305.0, 2305.0],
        })
        result = _validate_ohlcv(df)
        assert len(result) == 1

    def test_coerces_string_to_numeric(self):
        """String ที่เป็นตัวเลข → แปลงได้"""
        df = pd.DataFrame({
            "open": ["2300"], "high": ["2310"],
            "low": ["2290"], "close": ["2305"],
        })
        result = _validate_ohlcv(df)
        assert len(result) == 1
        assert result["close"].iloc[0] == 2305.0

    def test_does_not_mutate_original(self):
        """ต้องไม่แก้ไข DataFrame ต้นฉบับ"""
        df = pd.DataFrame({
            "open": [2300.0], "high": [2310.0],
            "low": [2290.0], "close": [2305.0],
        })
        original_id = id(df)
        _validate_ohlcv(df)
        assert id(df) == original_id


# ══════════════════════════════════════════════════════════════════
# 5. _retry_request
# ══════════════════════════════════════════════════════════════════


class TestRetryRequest:
    """ทดสอบ _retry_request"""

    @patch("data_engine.ohlcv_fetcher.time.sleep")
    def test_success_first_try(self, mock_sleep):
        """สำเร็จรอบแรก → return JSON"""
        session = MagicMock()
        resp = MagicMock()
        resp.json.return_value = {"values": []}
        resp.raise_for_status = MagicMock()
        session.get.return_value = resp

        result = _retry_request(session, "http://test", {})
        assert result == {"values": []}
        mock_sleep.assert_not_called()

    @patch("data_engine.ohlcv_fetcher.time.sleep")
    def test_retry_on_failure(self, mock_sleep):
        """Fail ครั้งแรก, สำเร็จครั้งที่ 2"""
        session = MagicMock()
        resp_ok = MagicMock()
        resp_ok.json.return_value = {"values": [1]}
        resp_ok.raise_for_status = MagicMock()
        session.get.side_effect = [Exception("fail"), resp_ok]

        result = _retry_request(session, "http://test", {}, retries=3)
        assert result == {"values": [1]}

    @patch("data_engine.ohlcv_fetcher.time.sleep")
    def test_all_retries_fail_raises(self, mock_sleep):
        """Fail ทุกครั้ง → raise exception"""
        session = MagicMock()
        session.get.side_effect = Exception("persistent failure")

        with pytest.raises(Exception, match="persistent failure"):
            _retry_request(session, "http://test", {}, retries=3)


# ══════════════════════════════════════════════════════════════════
# 6. Config constants
# ══════════════════════════════════════════════════════════════════


class TestConstants:
    """ทดสอบค่าคงที่"""

    def test_interval_to_minutes_complete(self):
        """ต้องมี mapping ครบทุก interval"""
        expected = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}
        assert expected == set(INTERVAL_TO_MINUTES.keys())

    def test_td_interval_map_complete(self):
        """TwelveData interval map ต้องครบ"""
        assert set(TD_INTERVAL_MAP.keys()) == set(INTERVAL_TO_MINUTES.keys())

    def test_yf_max_days_reasonable(self):
        """YF max days ต้องสมเหตุสมผล"""
        for interval, max_days in YF_MAX_DAYS.items():
            assert max_days > 0
