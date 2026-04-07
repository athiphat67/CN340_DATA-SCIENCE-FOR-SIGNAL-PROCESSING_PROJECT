"""
test_csv_loader.py — Pytest สำหรับทดสอบ load_gold_csv

Strategy: Real logic + Fixture (tmp_path)
- load_gold_csv() อ่าน CSV จาก disk → คำนวณ indicators → คืน DataFrame
- Logic (RSI, MACD, BB, ATR, shift, signal labels) = Real ทั้งหมด
- File I/O = ใช้ pytest tmp_path สร้าง CSV ชั่วคราว (controlled, reproducible)
- ไม่ mock อะไรเลย — แค่ควบคุม input file

ครอบคลุม:
  1. Happy path — โหลด CSV ปกติ ได้ DataFrame ครบ
  2. Output columns — มี indicators + thai aliases + signal labels
  3. Indicator values — RSI ∈ [0,100], BB upper > lower, ATR > 0
  4. Look-ahead bias — indicators shift(1) จริง
  5. Warmup drop — candles แรกๆ ถูกตัดออก
  6. Error handling — file not found, missing columns, bad datetime
  7. _find_col — case-insensitive column matching
  8. _rsi_signal — label mapping
  9. HSH columns — pass-through ไม่ถูก shift
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from backtest.data.csv_loader import (
    load_gold_csv,
    _rsi,
    _macd,
    _bollinger,
    _atr,
    _rsi_signal,
    _find_col,
    WARMUP_BARS,
)


# ══════════════════════════════════════════════════════════════════
# Fixtures — สร้าง CSV ชั่วคราวด้วย tmp_path
# ══════════════════════════════════════════════════════════════════


def _make_csv(
    tmp_path: Path,
    n: int = 300,
    seed: int = 42,
    filename: str = "test_gold.csv",
    include_hsh: bool = False,
) -> Path:
    """
    สร้าง CSV ราคาทองจำลองใน tmp_path

    Parameters
    ----------
    tmp_path     : pytest tmp_path fixture
    n            : จำนวน rows
    seed         : random seed
    filename     : ชื่อไฟล์
    include_hsh  : เพิ่ม hsh_buy, hsh_sell columns
    """
    rng = np.random.RandomState(seed)
    base = 45000.0  # ราคาทองไทย ~45,000 THB/บาท
    price = base + np.cumsum(rng.randn(n) * 50)

    dates = pd.date_range("2026-01-01 06:15", periods=n, freq="5min")

    data = {
        "Datetime": dates.strftime("%Y-%m-%d %H:%M:%S"),
        "Open": (price - rng.rand(n) * 30).round(2),
        "High": (price + rng.rand(n) * 60).round(2),
        "Low": (price - rng.rand(n) * 60).round(2),
        "Close": price.round(2),
        "Volume": rng.randint(100, 5000, n),
    }

    if include_hsh:
        data["hsh_buy"] = (price - 50).round(2)
        data["hsh_sell"] = (price + 50).round(2)
        data["has_real_hsh"] = 1

    df = pd.DataFrame(data)
    path = tmp_path / filename
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def csv_path(tmp_path):
    """CSV มาตรฐาน 300 rows"""
    return _make_csv(tmp_path, n=300, seed=42)


@pytest.fixture
def csv_short(tmp_path):
    """CSV สั้น 20 rows — ไม่พอ warmup"""
    return _make_csv(tmp_path, n=20, seed=99, filename="short.csv")


@pytest.fixture
def csv_with_hsh(tmp_path):
    """CSV พร้อม hsh_buy, hsh_sell columns"""
    return _make_csv(tmp_path, n=300, seed=42, filename="hsh.csv", include_hsh=True)


# ══════════════════════════════════════════════════════════════════
# 1. Happy Path — โหลดปกติ
# ══════════════════════════════════════════════════════════════════


class TestHappyPath:
    def test_returns_dataframe(self, csv_path):
        df = load_gold_csv(csv_path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_rows_less_than_original(self, csv_path):
        """drop_warmup=True → rows < 300 (ตัด warmup ออก)"""
        df = load_gold_csv(csv_path, drop_warmup=True)
        assert len(df) < 300

    def test_no_warmup_drop(self, csv_path):
        """drop_warmup=False → rows = 300 (แต่มี NaN)"""
        df = load_gold_csv(csv_path, drop_warmup=False)
        assert len(df) == 300

    def test_sorted_ascending(self, csv_path):
        """timestamp ต้องเรียงจากเก่าไปใหม่"""
        df = load_gold_csv(csv_path)
        assert df["timestamp"].is_monotonic_increasing

    def test_timestamp_is_datetime(self, csv_path):
        df = load_gold_csv(csv_path)
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])


# ══════════════════════════════════════════════════════════════════
# 2. Output Columns — ครบตาม spec
# ══════════════════════════════════════════════════════════════════


class TestOutputColumns:
    def test_ohlcv_columns(self, csv_path):
        df = load_gold_csv(csv_path)
        for col in ["open", "high", "low", "close", "volume", "timestamp"]:
            assert col in df.columns, f"Missing column: {col}"

    def test_indicator_columns(self, csv_path):
        df = load_gold_csv(csv_path)
        expected = [
            "rsi",
            "macd_line",
            "signal_line",
            "macd_hist",
            "ema_20",
            "ema_50",
            "bb_upper",
            "bb_mid",
            "bb_lower",
            "atr",
        ]
        for col in expected:
            assert col in df.columns, f"Missing indicator: {col}"

    def test_signal_label_columns(self, csv_path):
        df = load_gold_csv(csv_path)
        for col in ["rsi_signal", "macd_signal", "trend_signal", "bb_signal"]:
            assert col in df.columns, f"Missing signal label: {col}"

    def test_thai_alias_columns(self, csv_path):
        """open_thai, high_thai, low_thai, close_thai"""
        df = load_gold_csv(csv_path)
        for col in ["open_thai", "high_thai", "low_thai", "close_thai"]:
            assert col in df.columns, f"Missing alias: {col}"

    def test_thai_alias_equals_original(self, csv_path):
        """close_thai == close"""
        df = load_gold_csv(csv_path)
        pd.testing.assert_series_equal(
            df["close_thai"],
            df["close"].astype(float),
            check_names=False,
        )


# ══════════════════════════════════════════════════════════════════
# 3. Indicator Values — ค่าถูกต้อง
# ══════════════════════════════════════════════════════════════════


class TestIndicatorValues:
    def test_rsi_range(self, csv_path):
        """RSI ทุกแถวต้องอยู่ [0, 100]"""
        df = load_gold_csv(csv_path)
        assert (df["rsi"] >= 0).all()
        assert (df["rsi"] <= 100).all()

    def test_bb_ordering(self, csv_path):
        """BB upper > mid > lower ทุกแถว"""
        df = load_gold_csv(csv_path)
        assert (df["bb_upper"] >= df["bb_mid"]).all()
        assert (df["bb_mid"] >= df["bb_lower"]).all()

    def test_atr_positive(self, csv_path):
        """ATR > 0 ทุกแถว"""
        df = load_gold_csv(csv_path)
        assert (df["atr"] > 0).all()

    def test_macd_hist_equals_diff(self, csv_path):
        """macd_hist = macd_line - signal_line"""
        df = load_gold_csv(csv_path)
        diff = (df["macd_line"] - df["signal_line"]).round(4)
        pd.testing.assert_series_equal(
            diff,
            df["macd_hist"],
            check_names=False,
            atol=0.001,
        )

    def test_no_nan_after_warmup(self, csv_path):
        """drop_warmup=True → indicator columns ไม่มี NaN"""
        df = load_gold_csv(csv_path, drop_warmup=True)
        ind_cols = ["rsi", "macd_line", "ema_20", "ema_50", "bb_upper", "atr"]
        for col in ind_cols:
            assert df[col].isna().sum() == 0, f"NaN found in {col}"


# ══════════════════════════════════════════════════════════════════
# 4. Look-Ahead Bias Prevention — shift(1)
# ══════════════════════════════════════════════════════════════════


class TestLookAheadBias:
    """indicators ต้อง shift(1) เพื่อป้องกัน look-ahead bias"""

    def test_first_row_indicators_are_nan_before_drop(self, csv_path):
        """row แรกของ indicators ต้องเป็น NaN (เพราะ shift)"""
        df = load_gold_csv(csv_path, drop_warmup=False)
        # row 0 ต้อง NaN เพราะ shift(1) ทำให้ row แรกไม่มีค่า
        assert pd.isna(df.loc[0, "rsi"])
        assert pd.isna(df.loc[0, "macd_line"])
        assert pd.isna(df.loc[0, "atr"])

    def test_indicator_uses_previous_candle(self, csv_path):
        """indicator ณ row T ต้องมาจาก candle T-1 (ไม่ใช่ T)"""
        df_no_drop = load_gold_csv(csv_path, drop_warmup=False)

        # คำนวณ RSI แบบไม่ shift
        close = df_no_drop["close"].astype(float)
        rsi_raw = _rsi(close)

        # df["rsi"] ณ row 50 ต้อง = rsi_raw ณ row 49 (shift 1)
        row = 50
        if not pd.isna(df_no_drop.loc[row, "rsi"]):
            assert abs(df_no_drop.loc[row, "rsi"] - rsi_raw.iloc[row - 1]) < 0.01


# ══════════════════════════════════════════════════════════════════
# 5. Warmup Drop
# ══════════════════════════════════════════════════════════════════


class TestWarmupDrop:
    def test_warmup_bars_constant(self):
        """WARMUP_BARS ≈ 40 (MACD_SLOW + MACD_SIGNAL + 5)"""
        assert WARMUP_BARS == 26 + 9 + 5  # = 40

    def test_dropped_rows_count(self, csv_path):
        """drop_warmup ต้องตัด rows ที่ indicator ยังเป็น NaN ออก

        จำนวนที่ตัดขึ้นกับ indicator ที่ warmup ช้าที่สุด + shift(1)
        เช่น BB(20) + shift(1) ≈ 21 rows, RSI(14) + shift(1) ≈ 16 rows
        ต้องตัดอย่างน้อย 10 rows (มากกว่า 0 แน่นอน)
        """
        df_full = load_gold_csv(csv_path, drop_warmup=False)
        df_drop = load_gold_csv(csv_path, drop_warmup=True)
        dropped = len(df_full) - len(df_drop)
        assert dropped >= 10, f"Expected ≥10 warmup rows dropped, got {dropped}"
        assert dropped < 100, f"Dropped too many rows: {dropped}"

    def test_short_csv_still_works(self, csv_short):
        """CSV 20 rows → drop_warmup อาจตัดจนเหลือน้อยหรือ 0"""
        df = load_gold_csv(csv_short, drop_warmup=True)
        # ไม่ crash — อาจได้ 0 rows
        assert isinstance(df, pd.DataFrame)


# ══════════════════════════════════════════════════════════════════
# 6. Signal Labels
# ══════════════════════════════════════════════════════════════════


class TestSignalLabels:
    def test_rsi_signal_values(self, csv_path):
        """rsi_signal ∈ {overbought, oversold, neutral}"""
        df = load_gold_csv(csv_path)
        valid = {"overbought", "oversold", "neutral"}
        assert set(df["rsi_signal"].unique()).issubset(valid)

    def test_macd_signal_values(self, csv_path):
        """macd_signal ∈ {bullish, bearish, neutral}"""
        df = load_gold_csv(csv_path)
        valid = {"bullish", "bearish", "neutral"}
        assert set(df["macd_signal"].unique()).issubset(valid)

    def test_trend_signal_values(self, csv_path):
        """trend_signal ∈ {uptrend, downtrend, neutral}"""
        df = load_gold_csv(csv_path)
        valid = {"uptrend", "downtrend", "neutral"}
        assert set(df["trend_signal"].unique()).issubset(valid)

    def test_bb_signal_values(self, csv_path):
        """bb_signal ∈ {overbought, oversold, neutral}"""
        df = load_gold_csv(csv_path)
        valid = {"overbought", "oversold", "neutral"}
        assert set(df["bb_signal"].unique()).issubset(valid)


# ══════════════════════════════════════════════════════════════════
# 7. Error Handling
# ══════════════════════════════════════════════════════════════════


class TestErrorHandling:
    def test_file_not_found(self, tmp_path):
        """ไฟล์ไม่มี → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_gold_csv(tmp_path / "nonexistent.csv")

    def test_missing_close_column(self, tmp_path):
        """ไม่มี column Close → ValueError"""
        df = pd.DataFrame(
            {
                "Datetime": ["2026-01-01 10:00"],
                "Open": [100],
                "High": [110],
                "Low": [90],
                # ไม่มี Close
                "Volume": [1000],
            }
        )
        path = tmp_path / "no_close.csv"
        df.to_csv(path, index=False)
        with pytest.raises(ValueError, match="close"):
            load_gold_csv(path)

    def test_missing_datetime_column(self, tmp_path):
        """ไม่มี datetime column → ValueError"""
        df = pd.DataFrame(
            {
                "Price": [100],
                "Open": [100],
                "High": [110],
                "Low": [90],
                "Close": [105],
            }
        )
        path = tmp_path / "no_datetime.csv"
        df.to_csv(path, index=False)
        with pytest.raises(ValueError, match="datetime"):
            load_gold_csv(path)

    def test_bad_datetime_rows_dropped(self, tmp_path):
        """datetime parse ไม่ได้ → drop แถวนั้น ไม่ crash"""
        dates = pd.date_range("2026-01-01", periods=100, freq="5min")
        rng = np.random.RandomState(1)
        price = 45000 + np.cumsum(rng.randn(100) * 10)

        df = pd.DataFrame(
            {
                "Datetime": dates.strftime("%Y-%m-%d %H:%M:%S"),
                "Open": price,
                "High": price + 5,
                "Low": price - 5,
                "Close": price,
                "Volume": 1000,
            }
        )
        # ใส่ bad datetime
        df.loc[5, "Datetime"] = "NOT_A_DATE"
        df.loc[10, "Datetime"] = "INVALID"

        path = tmp_path / "bad_dates.csv"
        df.to_csv(path, index=False)

        result = load_gold_csv(path, drop_warmup=False)
        assert len(result) == 98  # 100 - 2 bad rows


# ══════════════════════════════════════════════════════════════════
# 8. HSH Columns — Pass-through
# ══════════════════════════════════════════════════════════════════


class TestHSHColumns:
    """hsh_buy, hsh_sell ต้องไม่ถูก shift (เป็นราคา execution)"""

    def test_hsh_columns_present(self, csv_with_hsh):
        df = load_gold_csv(csv_with_hsh, drop_warmup=False)
        assert "hsh_buy" in df.columns
        assert "hsh_sell" in df.columns

    def test_hsh_not_shifted(self, csv_with_hsh):
        """hsh_buy row 0 ต้องไม่เป็น NaN (ไม่ shift)"""
        df = load_gold_csv(csv_with_hsh, drop_warmup=False)
        assert not pd.isna(df.loc[0, "hsh_buy"])
        assert not pd.isna(df.loc[0, "hsh_sell"])


# ══════════════════════════════════════════════════════════════════
# 9. Helper Functions (Real)
# ══════════════════════════════════════════════════════════════════


class TestFindCol:
    """_find_col — case-insensitive column matching"""

    def test_exact_match(self):
        assert _find_col(["Datetime", "Open"], ["datetime"]) == "Datetime"

    def test_case_insensitive(self):
        assert _find_col(["CLOSE", "OPEN"], ["close"]) == "CLOSE"

    def test_first_candidate_wins(self):
        """ลอง candidates ตามลำดับ — ตัวแรกที่เจอชนะ"""
        assert _find_col(["time", "date"], ["datetime", "time", "date"]) == "time"

    def test_not_found(self):
        assert _find_col(["A", "B"], ["x", "y"]) is None


class TestRSISignal:
    """_rsi_signal — RSI → label"""

    def test_overbought(self):
        assert _rsi_signal(75) == "overbought"

    def test_oversold(self):
        assert _rsi_signal(25) == "oversold"

    def test_neutral(self):
        assert _rsi_signal(50) == "neutral"

    def test_boundary_70(self):
        """RSI = 70 → neutral (ต้อง > 70 ถึง overbought)"""
        assert _rsi_signal(70) == "neutral"

    def test_boundary_30(self):
        """RSI = 30 → neutral (ต้อง < 30 ถึง oversold)"""
        assert _rsi_signal(30) == "neutral"

    def test_nan(self):
        assert _rsi_signal(float("nan")) == "neutral"


# ══════════════════════════════════════════════════════════════════
# 10. Internal Indicator Functions (Real)
# ══════════════════════════════════════════════════════════════════


class TestIndicatorFunctions:
    """ทดสอบ _rsi, _macd, _bollinger, _atr แยกจาก load_gold_csv"""

    @pytest.fixture
    def close_series(self):
        rng = np.random.RandomState(42)
        return pd.Series(45000 + np.cumsum(rng.randn(200) * 30))

    @pytest.fixture
    def ohlc(self, close_series):
        rng = np.random.RandomState(42)
        n = len(close_series)
        return {
            "high": close_series + rng.rand(n) * 50,
            "low": close_series - rng.rand(n) * 50,
            "close": close_series,
        }

    def test_rsi_output_range(self, close_series):
        rsi = _rsi(close_series).dropna()
        assert (rsi >= 0).all()
        assert (rsi <= 100).all()

    def test_macd_histogram(self, close_series):
        line, sig, hist = _macd(close_series)
        diff = (line - sig).round(4)
        pd.testing.assert_series_equal(
            diff, hist, check_names=False, atol=1e-3, rtol=1e-3
        )

    def test_bollinger_ordering(self, close_series):
        upper, mid, lower = _bollinger(close_series)
        valid = upper.dropna().index
        assert (upper[valid] >= mid[valid]).all()
        assert (mid[valid] >= lower[valid]).all()

    def test_atr_positive(self, ohlc):
        atr = _atr(ohlc["high"], ohlc["low"], ohlc["close"]).dropna()
        assert (atr > 0).all()


# ══════════════════════════════════════════════════════════════════
# 11. Column Name Variations
# ══════════════════════════════════════════════════════════════════


class TestColumnVariations:
    """CSV อาจมี header ต่างกัน เช่น Datetime vs Time vs Timestamp"""

    def test_timestamp_header(self, tmp_path):
        """header 'Timestamp' แทน 'Datetime'"""
        rng = np.random.RandomState(42)
        n = 100
        price = 45000 + np.cumsum(rng.randn(n) * 10)
        df = pd.DataFrame(
            {
                "Timestamp": pd.date_range("2026-01-01", periods=n, freq="5min"),
                "Open": price,
                "High": price + 5,
                "Low": price - 5,
                "Close": price,
                "Volume": 1000,
            }
        )
        path = tmp_path / "alt_header.csv"
        df.to_csv(path, index=False)
        result = load_gold_csv(path, drop_warmup=False)
        assert len(result) == n

    def test_uppercase_ohlc(self, tmp_path):
        """header 'OPEN', 'HIGH', 'LOW', 'CLOSE' (uppercase)"""
        rng = np.random.RandomState(42)
        n = 100
        price = 45000 + np.cumsum(rng.randn(n) * 10)
        df = pd.DataFrame(
            {
                "Datetime": pd.date_range("2026-01-01", periods=n, freq="5min"),
                "OPEN": price,
                "HIGH": price + 5,
                "LOW": price - 5,
                "CLOSE": price,
                "VOLUME": 1000,
            }
        )
        path = tmp_path / "upper.csv"
        df.to_csv(path, index=False)
        result = load_gold_csv(path, drop_warmup=False)
        assert "close" in result.columns
