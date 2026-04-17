"""
test_thailand_timestamp.py — Pytest สำหรับ thailand_timestamp module

ครอบคลุม:
  1. THAI_TZ constant — ค่า timezone string ถูกต้อง
  2. get_thai_time() — return Timestamp ที่มี tz = Asia/Bangkok
  3. convert_index_to_thai_tz() — naive index → UTC → Bangkok, aware index → Bangkok
  4. to_thai_time() — Unix timestamp, ISO string, empty value

Strategy: Pure function tests + freeze time ด้วย mock
  - Deterministic 100%
  - ไม่มี external I/O
"""

import pytest
import pandas as pd
from unittest.mock import patch

from data_engine.thailand_timestamp import (
    THAI_TZ,
    get_thai_time,
    convert_index_to_thai_tz,
    to_thai_time,
)

pytestmark = pytest.mark.data_engine


# ══════════════════════════════════════════════════════════════════
# 1. THAI_TZ constant
# ══════════════════════════════════════════════════════════════════


class TestThaiTZConstant:
    """ค่าคงที่ timezone ต้องถูกต้อง"""

    def test_value(self):
        assert THAI_TZ == "Asia/Bangkok"

    def test_is_string(self):
        assert isinstance(THAI_TZ, str)


# ══════════════════════════════════════════════════════════════════
# 2. get_thai_time
# ══════════════════════════════════════════════════════════════════


class TestGetThaiTime:
    """get_thai_time() ต้อง return Timestamp ที่มี timezone Asia/Bangkok"""

    def test_returns_timestamp(self):
        result = get_thai_time()
        assert isinstance(result, pd.Timestamp)

    def test_has_timezone(self):
        result = get_thai_time()
        assert result.tzinfo is not None

    def test_timezone_is_bangkok(self):
        result = get_thai_time()
        assert str(result.tzinfo) == THAI_TZ or "Bangkok" in str(result.tzinfo)

    def test_not_naive(self):
        """ต้องไม่เป็น naive timestamp"""
        result = get_thai_time()
        assert result.tz is not None


# ══════════════════════════════════════════════════════════════════
# 3. convert_index_to_thai_tz
# ══════════════════════════════════════════════════════════════════


class TestConvertIndexToThaiTz:
    """แปลง DatetimeIndex ให้เป็นเวลาไทย"""

    def test_naive_index_assumed_utc(self):
        """Index ไม่มี tz → สมมติว่าเป็น UTC แล้วแปลงเป็น Bangkok"""
        idx = pd.DatetimeIndex(["2026-04-01 00:00:00", "2026-04-01 06:00:00"])
        result = convert_index_to_thai_tz(idx)
        # UTC 00:00 → Bangkok 07:00
        assert result[0].hour == 7
        assert "Bangkok" in str(result.tz) or "Asia" in str(result.tz)

    def test_utc_index_converted(self):
        """Index มี tz=UTC → แปลงเป็น Bangkok"""
        idx = pd.DatetimeIndex(
            ["2026-04-01 00:00:00", "2026-04-01 12:00:00"]
        ).tz_localize("UTC")
        result = convert_index_to_thai_tz(idx)
        assert result[0].hour == 7
        assert result[1].hour == 19

    def test_other_tz_converted(self):
        """Index มี tz อื่น (US/Eastern) → แปลงเป็น Bangkok"""
        idx = pd.DatetimeIndex(["2026-04-01 12:00:00"]).tz_localize("US/Eastern")
        result = convert_index_to_thai_tz(idx)
        # US/Eastern 12:00 = UTC 16:00 = Bangkok 23:00
        assert result[0].hour == 23

    def test_preserves_length(self):
        """จำนวน elements ต้องเท่าเดิม"""
        idx = pd.DatetimeIndex(pd.date_range("2026-04-01", periods=10, freq="h"))
        result = convert_index_to_thai_tz(idx)
        assert len(result) == 10


# ══════════════════════════════════════════════════════════════════
# 4. to_thai_time
# ══════════════════════════════════════════════════════════════════


class TestToThaiTime:
    """แปลงค่าเวลาทุกรูปแบบ → pd.Timestamp ที่เป็นเวลาไทย"""

    def test_unix_timestamp(self):
        """Unix timestamp (int) → Bangkok time"""
        # 1711929600 = 2024-04-01T00:00:00 UTC
        result = to_thai_time(1711929600)
        assert isinstance(result, pd.Timestamp)
        assert "Bangkok" in str(result.tzinfo) or "Asia" in str(result.tzinfo)

    def test_unix_float(self):
        """Unix timestamp (float) → Bangkok time"""
        result = to_thai_time(1711929600.0)
        assert result.tz is not None

    def test_iso_string(self):
        """ISO 8601 string → Bangkok time"""
        result = to_thai_time("2026-04-01T00:00:00Z")
        assert result.hour == 7  # UTC 00:00 → Bangkok 07:00

    def test_datetime_string_with_tz(self):
        """String พร้อม timezone → Bangkok time"""
        result = to_thai_time("2026-04-01T12:00:00+00:00")
        assert result.hour == 19  # UTC 12:00 → Bangkok 19:00

    def test_empty_string_raises(self):
        """Empty string → ValueError"""
        with pytest.raises(ValueError, match="Empty"):
            to_thai_time("")

    def test_none_raises(self):
        """None → ValueError"""
        with pytest.raises((ValueError, TypeError)):
            to_thai_time(None)

    def test_nan_raises(self):
        """NaN → ValueError"""
        with pytest.raises(ValueError, match="Empty"):
            to_thai_time(float("nan"))
