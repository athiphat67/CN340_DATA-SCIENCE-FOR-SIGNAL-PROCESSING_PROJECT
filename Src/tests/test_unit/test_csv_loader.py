"""
test_csv_loader.py — Pytest สำหรับ backtest.data.csv_loader

Strategy: Real logic + Fixture (tmp_path)
- load_gold_csv() อ่าน CSV จาก disk → resample → คำนวณ indicators + shift(1) → drop warmup
- ไม่ mock — ใช้ tmp_path สร้าง CSV ชั่วคราว

ครอบคลุม production API จริง:
  1. Happy path — load_gold_csv() คืน DataFrame ที่มี timestamp tz = Asia/Bangkok
  2. Output columns — OHLCV + indicators (ไม่มี open_thai/close_thai, ไม่มี macd_signal label)
  3. Indicator values — RSI ∈ [0,100], BB upper ≥ mid ≥ lower, ATR > 0, macd_hist = macd_line - macd_signal
  4. Look-ahead bias — _calculate_indicators() ใช้ shift(1)
  5. Warmup drop — row ที่ indicator NaN ถูก drop (ไม่มี flag drop_warmup)
  6. Signal labels — rsi_signal / trend_signal (trend ใช้ "sideways" ไม่ใช่ "neutral")
  7. Error handling — FileNotFoundError, ValueError(Missing datetime)
  8. Resample — timeframe parameter รวม candle ถูกต้อง
  9. _find_column — signature (df, expected_name, candidates), case-insensitive
 10. _calc_* helpers — unit test บน DataFrame
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from backtest.data.csv_loader import (
    load_gold_csv,
    _find_column,
    _calculate_indicators,
    _calc_rsi,
    _calc_ema_and_trend,
    _calc_macd,
    _calc_bollinger_bands,
    _calc_atr,
    RSI_PERIOD,
    MACD_FAST,
    MACD_SLOW,
    MACD_SIGNAL,
    BB_PERIOD,
    ATR_PERIOD,
)


# ══════════════════════════════════════════════════════════════════
# Fixtures — สร้าง CSV ชั่วคราวด้วย tmp_path
# ══════════════════════════════════════════════════════════════════


def _make_csv(
    tmp_path: Path,
    n: int = 300,
    seed: int = 42,
    filename: str = "test_gold.csv",
    freq: str = "1min",
    start: str = "2026-01-01 09:00",
) -> Path:
    """สร้าง CSV ราคาทองจำลองใน tmp_path (tz-naive datetime — production localize เอง)"""
    rng = np.random.RandomState(seed)
    base = 45000.0
    price = base + np.cumsum(rng.randn(n) * 50)
    dates = pd.date_range(start, periods=n, freq=freq)

    df = pd.DataFrame(
        {
            "Datetime": dates.strftime("%Y-%m-%d %H:%M:%S"),
            "Open": (price - rng.rand(n) * 30).round(2),
            "High": (price + rng.rand(n) * 60).round(2),
            "Low": (price - rng.rand(n) * 60).round(2),
            "Close": price.round(2),
            "Volume": rng.randint(100, 5000, n),
        }
    )
    path = tmp_path / filename
    df.to_csv(path, index=False)
    return path


def _make_ohlc_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """สร้าง DataFrame OHLC (timestamp + open/high/low/close) สำหรับ unit test _calc_*"""
    rng = np.random.RandomState(seed)
    close = 45000 + np.cumsum(rng.randn(n) * 30)
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=n, freq="1min"),
            "open": close - rng.rand(n) * 20,
            "high": close + rng.rand(n) * 40,
            "low": close - rng.rand(n) * 40,
            "close": close,
            "volume": rng.randint(100, 5000, n),
        }
    )


@pytest.fixture
def csv_path(tmp_path):
    """CSV มาตรฐาน 300 rows @ 1min — พอสำหรับ warmup ทุก indicator"""
    return _make_csv(tmp_path, n=300, seed=42)


@pytest.fixture
def csv_short(tmp_path):
    """CSV สั้น 20 rows — ไม่พอ warmup"""
    return _make_csv(tmp_path, n=20, seed=99, filename="short.csv")


# ══════════════════════════════════════════════════════════════════
# 1. Happy Path
# ══════════════════════════════════════════════════════════════════


class TestLoadGoldCsv:
    """load_gold_csv() — พฤติกรรมพื้นฐาน"""

    def test_returns_dataframe(self, csv_path):
        """คืน DataFrame ไม่ว่างเปล่า"""
        df = load_gold_csv(str(csv_path))
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_rows_less_than_input_due_to_warmup(self, csv_path):
        """Output rows < input เพราะ warmup drop"""
        df = load_gold_csv(str(csv_path))
        assert len(df) < 300

    def test_timestamp_sorted_ascending(self, csv_path):
        """timestamp เรียงจากเก่าไปใหม่"""
        df = load_gold_csv(str(csv_path))
        assert df["timestamp"].is_monotonic_increasing

    def test_timestamp_is_datetime(self, csv_path):
        """timestamp dtype เป็น datetime"""
        df = load_gold_csv(str(csv_path))
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

    def test_timestamp_tz_bangkok(self, csv_path):
        """timestamp ต้อง localize เป็น Asia/Bangkok"""
        df = load_gold_csv(str(csv_path))
        tz = df["timestamp"].dt.tz
        assert tz is not None
        assert "Bangkok" in str(tz)


# ══════════════════════════════════════════════════════════════════
# 2. Output Columns
# ══════════════════════════════════════════════════════════════════


class TestOutputColumns:
    """Output columns ต้องครบตาม production spec"""

    def test_ohlcv_columns(self, csv_path):
        df = load_gold_csv(str(csv_path))
        for col in ["open", "high", "low", "close", "volume", "timestamp"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_indicator_columns(self, csv_path):
        """indicators ที่ production สร้างจริง"""
        df = load_gold_csv(str(csv_path))
        expected = [
            "rsi",
            "rsi_signal",
            "ema_20",
            "ema_50",
            "trend_signal",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "bb_mid",
            "bb_upper",
            "bb_lower",
            "atr",
        ]
        for col in expected:
            assert col in df.columns, f"Missing indicator: {col}"


# ══════════════════════════════════════════════════════════════════
# 3. Indicator Values
# ══════════════════════════════════════════════════════════════════


class TestIndicatorValues:
    def test_rsi_range(self, csv_path):
        """RSI ทุกแถว ∈ [0, 100]"""
        df = load_gold_csv(str(csv_path))
        assert (df["rsi"] >= 0).all()
        assert (df["rsi"] <= 100).all()

    def test_bb_ordering(self, csv_path):
        """BB upper ≥ mid ≥ lower"""
        df = load_gold_csv(str(csv_path))
        assert (df["bb_upper"] >= df["bb_mid"]).all()
        assert (df["bb_mid"] >= df["bb_lower"]).all()

    def test_atr_positive(self, csv_path):
        """ATR > 0 ทุกแถว (หลัง warmup)"""
        df = load_gold_csv(str(csv_path))
        assert (df["atr"] > 0).all()

    def test_macd_hist_equals_line_minus_signal(self, csv_path):
        """macd_hist = macd_line - macd_signal (ทั้งคู่ถูก shift แล้ว)"""
        df = load_gold_csv(str(csv_path))
        diff = df["macd_line"] - df["macd_signal"]
        pd.testing.assert_series_equal(
            diff.round(4),
            df["macd_hist"].round(4),
            check_names=False,
            atol=1e-3,
        )

    def test_no_nan_in_indicators_after_load(self, csv_path):
        """หลัง warmup drop — indicator หลักต้องไม่มี NaN"""
        df = load_gold_csv(str(csv_path))
        for col in ["rsi", "macd_line", "ema_50", "bb_upper", "atr"]:
            assert df[col].isna().sum() == 0, f"NaN found in {col}"


# ══════════════════════════════════════════════════════════════════
# 4. Look-Ahead Bias Prevention
# ══════════════════════════════════════════════════════════════════


class TestLookAheadBias:
    """_calculate_indicators() shift(1) เพื่อป้องกัน look-ahead"""

    def test_first_row_indicators_are_nan(self):
        """row 0 ของ indicator ต้อง NaN เพราะ shift(1)"""
        df = _make_ohlc_df(n=100)
        result = _calculate_indicators(df)
        for col in ["rsi", "macd_line", "ema_20", "ema_50", "bb_mid", "atr"]:
            assert pd.isna(result.loc[0, col]), f"Row 0 of {col} should be NaN"

    def test_indicator_row_t_equals_raw_row_t_minus_1(self):
        """indicator[T] (after shift) = raw_indicator[T-1] (before shift)"""
        df = _make_ohlc_df(n=100)
        # raw: compute without shift
        raw = _calc_rsi(df.copy())
        # shifted: full pipeline
        shifted = _calculate_indicators(df)

        # เช็ค row 50 — ต้องไม่ NaN ทั้งคู่
        assert not pd.isna(raw.loc[49, "rsi"])
        assert not pd.isna(shifted.loc[50, "rsi"])
        assert abs(shifted.loc[50, "rsi"] - raw.loc[49, "rsi"]) < 1e-6


# ══════════════════════════════════════════════════════════════════
# 5. Warmup Drop
# ══════════════════════════════════════════════════════════════════


class TestWarmupDrop:
    """load_gold_csv drop row ที่ indicator หลักยัง NaN อัตโนมัติ"""

    def test_warmup_drops_rows(self, csv_path):
        """จำนวน row ที่ถูก drop ≥ 10 (จาก BB period=20 + shift + ema_50 warmup)"""
        # อ่าน raw ก่อน resample เพื่อนับ input
        raw_df = pd.read_csv(csv_path)
        n_input = len(raw_df)
        result = load_gold_csv(str(csv_path))
        dropped = n_input - len(result)
        assert dropped >= 10, f"Expected ≥10 warmup rows dropped, got {dropped}"

    def test_short_csv_does_not_crash(self, csv_short):
        """CSV 20 rows → อาจเหลือ 0 rows แต่ไม่ crash"""
        df = load_gold_csv(str(csv_short))
        assert isinstance(df, pd.DataFrame)


# ══════════════════════════════════════════════════════════════════
# 6. Signal Labels
# ══════════════════════════════════════════════════════════════════


class TestSignalLabels:
    """rsi_signal / trend_signal — labels ที่ production generate จริง"""

    def test_rsi_signal_values(self, csv_path):
        """rsi_signal ∈ {overbought, oversold, neutral}"""
        df = load_gold_csv(str(csv_path))
        valid = {"overbought", "oversold", "neutral"}
        assert set(df["rsi_signal"].unique()).issubset(valid)

    def test_trend_signal_values(self, csv_path):
        """trend_signal ∈ {uptrend, downtrend, sideways} — production ใช้ sideways"""
        df = load_gold_csv(str(csv_path))
        valid = {"uptrend", "downtrend", "sideways"}
        assert set(df["trend_signal"].unique()).issubset(valid)

    def test_rsi_signal_logic(self):
        """_calc_rsi: RSI>70→overbought, <30→oversold, else→neutral"""
        # สร้าง df ที่มี close ขึ้นแรงๆ → RSI สูง
        n = 50
        rising = pd.DataFrame({"close": np.linspace(100, 200, n)})
        result = _calc_rsi(rising)
        # RSI ของขาขึ้นล้วนๆ ต้อง > 70 (overbought)
        last_rsi = result["rsi"].iloc[-1]
        assert last_rsi > 70
        assert result["rsi_signal"].iloc[-1] == "overbought"


# ══════════════════════════════════════════════════════════════════
# 7. Error Handling
# ══════════════════════════════════════════════════════════════════


class TestErrorHandling:
    def test_file_not_found_raises(self, tmp_path):
        """ไฟล์ไม่มี → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_gold_csv(str(tmp_path / "nonexistent.csv"))

    def test_missing_datetime_column_raises(self, tmp_path):
        """ไม่มี column ที่เป็น datetime → ValueError"""
        df = pd.DataFrame(
            {
                "Price": [100, 101, 102],
                "Open": [100, 101, 102],
                "High": [110, 111, 112],
                "Low": [90, 91, 92],
                "Close": [105, 106, 107],
            }
        )
        path = tmp_path / "no_datetime.csv"
        df.to_csv(path, index=False)
        with pytest.raises(ValueError, match="datetime"):
            load_gold_csv(str(path))


# ══════════════════════════════════════════════════════════════════
# 8. Resample (timeframe parameter)
# ══════════════════════════════════════════════════════════════════


class TestResample:
    """timeframe param ต้อง resample ถูก"""

    def test_resample_5m_reduces_rows(self, tmp_path):
        """timeframe='5m' บน data 1-min → rows น้อยกว่า input (รวมทุก 5 นาที)"""
        path = _make_csv(tmp_path, n=300, seed=42, freq="1min")
        df_1m = load_gold_csv(str(path), timeframe="1m")
        df_5m = load_gold_csv(str(path), timeframe="5m")
        # 5-min resample ต้องมี rows น้อยกว่า 1-min (ประมาณ 1/5)
        assert len(df_5m) < len(df_1m)
        assert len(df_5m) > 0

    def test_resample_timestamps_aligned(self, tmp_path):
        """timeframe='5m' → timestamps ต้อง align กับ 5-min grid"""
        path = _make_csv(tmp_path, n=300, seed=42, freq="1min")
        df = load_gold_csv(str(path), timeframe="5m")
        # minute ของทุก timestamp ต้องหาร 5 ลงตัว
        minutes = df["timestamp"].dt.minute
        assert (minutes % 5 == 0).all()


# ══════════════════════════════════════════════════════════════════
# 9. _find_column helper
# ══════════════════════════════════════════════════════════════════


class TestFindColumn:
    """_find_column(df, expected_name, candidates) — case-insensitive"""

    def test_exact_match(self):
        df = pd.DataFrame(columns=["Datetime", "Open"])
        assert _find_column(df, "timestamp", ["datetime"]) == "Datetime"

    def test_case_insensitive(self):
        df = pd.DataFrame(columns=["CLOSE", "OPEN"])
        assert _find_column(df, "close", ["close"]) == "CLOSE"

    def test_first_candidate_wins(self):
        """ลำดับใน candidates → ตัวแรกที่เจอใน df.columns ชนะ"""
        df = pd.DataFrame(columns=["time", "date"])
        assert _find_column(df, "ts", ["datetime", "time", "date"]) == "time"

    def test_not_found_returns_none(self):
        df = pd.DataFrame(columns=["A", "B"])
        assert _find_column(df, "missing", ["x", "y"]) is None


# ══════════════════════════════════════════════════════════════════
# 10. _calc_* Indicator Helpers (DataFrame-based)
# ══════════════════════════════════════════════════════════════════


class TestCalcHelpers:
    """ทดสอบ _calc_rsi / _calc_ema_and_trend / _calc_macd / _calc_bollinger_bands / _calc_atr"""

    @pytest.fixture
    def df(self):
        return _make_ohlc_df(n=200, seed=42)

    def test_calc_rsi_adds_columns(self, df):
        """_calc_rsi เพิ่ม rsi + rsi_signal columns"""
        result = _calc_rsi(df.copy())
        assert "rsi" in result.columns
        assert "rsi_signal" in result.columns

    def test_calc_rsi_range(self, df):
        """RSI ที่คำนวณได้ ∈ [0, 100]"""
        result = _calc_rsi(df.copy())
        rsi = result["rsi"].dropna()
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_calc_ema_and_trend_adds_columns(self, df):
        """_calc_ema_and_trend เพิ่ม ema_20, ema_50, trend_signal"""
        result = _calc_ema_and_trend(df.copy())
        for col in ["ema_20", "ema_50", "trend_signal"]:
            assert col in result.columns

    def test_calc_ema_trend_labels(self, df):
        """trend_signal ∈ {uptrend, downtrend, sideways}"""
        result = _calc_ema_and_trend(df.copy())
        valid = {"uptrend", "downtrend", "sideways"}
        assert set(result["trend_signal"].unique()).issubset(valid)

    def test_calc_macd_histogram_identity(self, df):
        """macd_hist = macd_line - macd_signal"""
        result = _calc_macd(df.copy())
        diff = result["macd_line"] - result["macd_signal"]
        pd.testing.assert_series_equal(
            diff.round(4),
            result["macd_hist"].round(4),
            check_names=False,
            atol=1e-3,
        )

    def test_calc_bollinger_ordering(self, df):
        """BB upper ≥ mid ≥ lower (ที่ไม่ NaN)"""
        result = _calc_bollinger_bands(df.copy())
        valid = result["bb_upper"].dropna().index
        assert (result.loc[valid, "bb_upper"] >= result.loc[valid, "bb_mid"]).all()
        assert (result.loc[valid, "bb_mid"] >= result.loc[valid, "bb_lower"]).all()

    def test_calc_atr_positive(self, df):
        """ATR > 0 (ที่ไม่ NaN)"""
        result = _calc_atr(df.copy())
        atr = result["atr"].dropna()
        assert (atr > 0).all()


# ══════════════════════════════════════════════════════════════════
# 11. Indicator Constants
# ══════════════════════════════════════════════════════════════════


class TestConstants:
    """ตรวจว่า constants ที่ production export มีค่าตามที่เอกสารอ้างอิงระบุ"""

    def test_rsi_period(self):
        assert RSI_PERIOD == 14

    def test_macd_periods(self):
        assert MACD_FAST == 12
        assert MACD_SLOW == 26
        assert MACD_SIGNAL == 9

    def test_bb_period(self):
        assert BB_PERIOD == 20

    def test_atr_period(self):
        assert ATR_PERIOD == 14
