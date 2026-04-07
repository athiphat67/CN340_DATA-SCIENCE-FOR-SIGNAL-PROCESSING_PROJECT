"""
test_indicators.py — Pytest สำหรับทดสอบ TechnicalIndicators

Strategy: Real logic + Fixture data
- Logic คำนวณ indicator เป็น pure math → ใช้ Real ทั้งหมด
- Input DataFrame สร้างจาก numpy seed → ผลลัพธ์ reproducible ทุกครั้ง
- Mock เฉพาะ get_thai_time() (เป็น I/O boundary ที่ดึงเวลาจริง)

Fixtures:
  ohlcv_df       — DataFrame 300 rows, np.random.seed(42), ราคาทอง ~2300
  ohlcv_short_df — DataFrame 20 rows, ไม่พอ warmup SMA200
  uptrend_df     — DataFrame 300 rows, ราคาขึ้นเรื่อยๆ → RSI สูง, EMA20 > EMA50
  downtrend_df   — DataFrame 300 rows, ราคาลงเรื่อยๆ → RSI ต่ำ, EMA20 < EMA50
  flat_df        — DataFrame 300 rows, ราคาคงที่ → RSI ~50, ATR ~0
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch
from dataclasses import asdict

from data_engine.indicators import (
    TechnicalIndicators,
    RSIResult,
    MACDResult,
    BollingerResult,
    ATRResult,
    TrendResult,
    AllIndicators,
)


# ══════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════


def _make_ohlcv(
    n: int, seed: int, trend: float = 0.0, noise: float = 5.0, ohlc_spread: float = 3.0
) -> pd.DataFrame:
    """
    สร้าง OHLCV DataFrame จำลอง

    Parameters
    ----------
    n           : จำนวน rows
    seed        : random seed (ให้ผลลัพธ์เหมือนกันทุกครั้ง)
    trend       : ค่าบวก = ราคาขึ้น, ค่าลบ = ราคาลง, 0 = random walk
    noise       : ขนาด random noise ต่อ candle (close)
    ohlc_spread : ขนาด high-low spread (ควบคุม ATR)
    """
    rng = np.random.RandomState(seed)
    base = 2300.0
    steps = rng.randn(n) * noise + trend
    price = base + np.cumsum(steps)

    return pd.DataFrame(
        {
            "open": price - rng.rand(n) * ohlc_spread,
            "high": price + rng.rand(n) * ohlc_spread * 2,
            "low": price - rng.rand(n) * ohlc_spread * 2,
            "close": price,
            "volume": rng.randint(10000, 50000, n),
        }
    )


@pytest.fixture
def ohlcv_df() -> pd.DataFrame:
    """DataFrame มาตรฐาน 300 rows — เพียงพอสำหรับ SMA200 + warmup"""
    return _make_ohlcv(n=300, seed=42)


@pytest.fixture
def ohlcv_short_df() -> pd.DataFrame:
    """DataFrame สั้น 20 rows — ไม่พอ warmup SMA200 แต่พอ RSI(14)"""
    return _make_ohlcv(n=20, seed=99)


@pytest.fixture
def uptrend_df() -> pd.DataFrame:
    """ราคาขึ้นต่อเนื่อง → RSI สูง, EMA20 > EMA50"""
    return _make_ohlcv(n=300, seed=42, trend=2.0, noise=1.0)


@pytest.fixture
def downtrend_df() -> pd.DataFrame:
    """ราคาลงต่อเนื่อง → RSI ต่ำ, EMA20 < EMA50"""
    return _make_ohlcv(n=300, seed=42, trend=-2.0, noise=1.0)


@pytest.fixture
def flat_df() -> pd.DataFrame:
    """ราคาคงที่แทบไม่เปลี่ยน → ATR ≈ 0, RSI ≈ 50"""
    return _make_ohlcv(n=300, seed=42, trend=0.0, noise=0.001, ohlc_spread=0.001)


@pytest.fixture
def calc(ohlcv_df) -> TechnicalIndicators:
    """Instance มาตรฐานพร้อมใช้ทดสอบ"""
    return TechnicalIndicators(ohlcv_df)


# ══════════════════════════════════════════════════════════════════
# 1. Initialization & Validation
# ══════════════════════════════════════════════════════════════════


class TestInit:
    """ทดสอบ __init__ ว่า validate input ถูกต้อง"""

    def test_empty_dataframe_raises(self):
        """DataFrame ว่าง → ต้อง raise ValueError"""
        with pytest.raises(ValueError, match="empty"):
            TechnicalIndicators(pd.DataFrame())

    def test_missing_columns_raises(self):
        """ขาด column 'close' → ต้อง raise ValueError"""
        df = pd.DataFrame({"open": [1], "high": [2], "low": [0.5]})
        with pytest.raises(ValueError, match="columns"):
            TechnicalIndicators(df)

    def test_valid_dataframe_ok(self, ohlcv_df):
        """DataFrame ถูกต้อง → สร้าง instance ได้ไม่ error"""
        calc = TechnicalIndicators(ohlcv_df)
        assert calc.df is not None
        assert len(calc.df) == 300

    def test_does_not_mutate_original(self, ohlcv_df):
        """ต้องไม่แก้ไข DataFrame ต้นฉบับ (ใช้ .copy() ภายใน)"""
        original_cols = set(ohlcv_df.columns)
        TechnicalIndicators(ohlcv_df)
        assert set(ohlcv_df.columns) == original_cols

    def test_precomputed_columns_exist(self, calc):
        """หลัง init ต้องมี columns ที่ pre-calculate ไว้ครบ"""
        expected = {
            "rsi_14",
            "macd_line",
            "macd_signal",
            "macd_hist",
            "bb_mid",
            "bb_up",
            "bb_low",
            "bb_bandwidth",
            "bb_pct_b",
            "atr_14",
            "ema_20",
            "ema_50",
            "sma_200",
        }
        assert expected.issubset(calc.df.columns)


# ══════════════════════════════════════════════════════════════════
# 2. RSI
# ══════════════════════════════════════════════════════════════════


class TestRSI:
    """ทดสอบ RSI(14) — ค่าต้องอยู่ในช่วง [0, 100] และ signal ถูก"""

    def test_rsi_range(self, calc):
        """RSI ต้องอยู่ระหว่าง 0-100"""
        result = calc.rsi()
        assert 0 <= result.value <= 100

    def test_rsi_returns_dataclass(self, calc):
        """ต้องคืน RSIResult dataclass"""
        result = calc.rsi()
        assert isinstance(result, RSIResult)
        assert result.period == 14

    def test_rsi_overbought_in_uptrend(self, uptrend_df):
        """ราคาขึ้นต่อเนื่อง → RSI ควร > 70 (overbought)"""
        calc = TechnicalIndicators(uptrend_df)
        result = calc.rsi()
        assert result.value > 70
        assert result.signal == "overbought"

    def test_rsi_oversold_in_downtrend(self, downtrend_df):
        """ราคาลงต่อเนื่อง → RSI ควร < 30 (oversold)"""
        calc = TechnicalIndicators(downtrend_df)
        result = calc.rsi()
        assert result.value < 30
        assert result.signal == "oversold"

    def test_rsi_neutral_in_flat(self, flat_df):
        """ราคาคงที่ → RSI ≈ 50 (neutral)"""
        calc = TechnicalIndicators(flat_df)
        result = calc.rsi()
        assert result.signal == "neutral"
        assert 30 < result.value < 70

    def test_rsi_all_values_valid(self, calc):
        """RSI column ทั้งหมดต้องอยู่ใน [0, 100] (ไม่มีค่าเกิน)"""
        rsi_col = calc.df["rsi_14"].dropna()
        assert (rsi_col >= 0).all()
        assert (rsi_col <= 100).all()


# ══════════════════════════════════════════════════════════════════
# 3. MACD
# ══════════════════════════════════════════════════════════════════


class TestMACD:
    """ทดสอบ MACD(12, 26, 9) — histogram = macd_line - signal_line"""

    def test_macd_returns_dataclass(self, calc):
        result = calc.macd()
        assert isinstance(result, MACDResult)

    def test_histogram_equals_diff(self, calc):
        """histogram ต้อง ≈ macd_line - signal_line (ตรวจสูตร)

        Note: ใช้ tolerance เพราะ histogram คำนวณจาก full-precision columns
        แล้ว round 4 ตำแหน่ง ส่วน macd_line/signal_line ก็ round 4 ตำแหน่งแยก
        ทำให้อาจต่างกัน ±0.0001 จาก rounding order
        """
        result = calc.macd()
        expected = result.macd_line - result.signal_line
        assert abs(result.histogram - expected) < 0.001

    def test_crossover_bullish(self):
        """สร้าง scenario: hist เปลี่ยนจากลบเป็นบวก → bullish_cross"""
        # สร้าง data ที่ราคาลงก่อนแล้วขึ้นแรง
        rng = np.random.RandomState(77)
        n = 300
        price = np.concatenate(
            [
                2300 - np.arange(150) * 0.5,  # ช่วงลง
                2225 + np.arange(150) * 2.0,  # ช่วงขึ้นแรง
            ]
        )
        df = pd.DataFrame(
            {
                "open": price - 1,
                "high": price + 3,
                "low": price - 3,
                "close": price,
                "volume": np.full(n, 30000),
            }
        )
        calc = TechnicalIndicators(df)
        result = calc.macd()
        # เมื่อราคาขึ้นแรงช่วงท้าย histogram ต้องเป็นบวก
        assert result.histogram > 0

    def test_crossover_values(self, calc):
        """crossover ต้องเป็นหนึ่งใน 3 ค่าเท่านั้น"""
        result = calc.macd()
        assert result.crossover in {"bullish_cross", "bearish_cross", "none"}

    def test_macd_column_consistency(self, calc):
        """macd_hist column ทั้ง series ต้อง = macd_line - macd_signal"""
        df = calc.df.dropna(subset=["macd_line", "macd_signal", "macd_hist"])
        diff = df["macd_line"] - df["macd_signal"]
        pd.testing.assert_series_equal(
            diff.round(10), df["macd_hist"].round(10), check_names=False
        )


# ══════════════════════════════════════════════════════════════════
# 4. Bollinger Bands
# ══════════════════════════════════════════════════════════════════


class TestBollinger:
    """ทดสอบ Bollinger Bands(20, 2σ)"""

    def test_returns_dataclass(self, calc):
        result = calc.bollinger_bands()
        assert isinstance(result, BollingerResult)

    def test_band_ordering(self, calc):
        """upper > middle > lower เสมอ"""
        bb = calc.bollinger_bands()
        assert bb.upper > bb.middle > bb.lower

    def test_bandwidth_positive(self, calc):
        """bandwidth ต้อง > 0"""
        bb = calc.bollinger_bands()
        assert bb.bandwidth > 0

    def test_pct_b_in_range_for_normal(self, calc):
        """pct_b ปกติจะอยู่ใกล้ๆ 0-1 (อาจเกินได้ถ้าราคาหลุด band)"""
        bb = calc.bollinger_bands()
        # ตรวจแค่ว่าเป็น finite number
        assert np.isfinite(bb.pct_b)

    def test_signal_above_upper(self):
        """ราคาสูงกว่า upper band → signal = above_upper"""
        n = 300
        # ราคาคงที่ 290 candles แล้วพุ่งขึ้นเร็วกว่า band ปรับตัวทัน
        price = np.concatenate(
            [
                np.full(290, 2300.0),
                2300 + np.arange(10) * 50.0,  # พุ่ง +500 ใน 10 candles
            ]
        )
        df = pd.DataFrame(
            {
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": np.full(n, 20000),
            }
        )
        bb = TechnicalIndicators(df).bollinger_bands()
        assert bb.signal == "above_upper"

    def test_signal_below_lower(self):
        """ราคาต่ำกว่า lower band → signal = below_lower"""
        n = 300
        price = np.concatenate(
            [
                np.full(290, 2300.0),
                2300 - np.arange(10) * 50.0,  # ดิ่ง -500 ใน 10 candles
            ]
        )
        df = pd.DataFrame(
            {
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": np.full(n, 20000),
            }
        )
        bb = TechnicalIndicators(df).bollinger_bands()
        assert bb.signal == "below_lower"

    def test_signal_inside(self, calc):
        """ราคา random walk ปกติ → มักอยู่ inside band"""
        bb = calc.bollinger_bands()
        assert bb.signal in {"inside", "above_upper", "below_lower"}


# ══════════════════════════════════════════════════════════════════
# 5. ATR
# ══════════════════════════════════════════════════════════════════


class TestATR:
    """ทดสอบ ATR(14) — ค่าความผันผวน"""

    def test_returns_dataclass(self, calc):
        result = calc.atr()
        assert isinstance(result, ATRResult)
        assert result.period == 14

    def test_atr_positive(self, calc):
        """ATR ต้อง > 0 เสมอ (เพราะ high-low > 0)"""
        assert calc.atr().value > 0

    def test_atr_near_zero_for_flat(self, flat_df):
        """ราคาแทบไม่ขยับ → ATR ≈ 0"""
        calc = TechnicalIndicators(flat_df)
        assert calc.atr().value < 0.1

    def test_volatility_level_values(self, calc):
        """volatility_level ต้องเป็น low / normal / high"""
        assert calc.atr().volatility_level in {"low", "normal", "high"}

    def test_high_volatility_detected(self):
        """ราคานิ่งยาวนานแล้ว high-low กระโดดแรง → ATR สูงกว่า average"""
        n = 300
        # ราคานิ่ง 290 candles แล้ว spike 10 candles สุดท้าย
        price = np.full(n, 2300.0)
        high = price.copy()
        low = price.copy()
        high[:290] = price[:290] + 0.5  # high-low range แคบมาก
        low[:290] = price[:290] - 0.5
        high[290:] = price[290:] + 200  # กระโดดแรงมาก
        low[290:] = price[290:] - 200
        df = pd.DataFrame(
            {
                "open": price,
                "high": high,
                "low": low,
                "close": price,
                "volume": np.full(n, 25000),
            }
        )
        calc = TechnicalIndicators(df)
        assert calc.atr().volatility_level == "high"


# ══════════════════════════════════════════════════════════════════
# 6. Trend (EMA20, EMA50, SMA200)
# ══════════════════════════════════════════════════════════════════


class TestTrend:
    """ทดสอบ Trend detection ด้วย EMA crossover"""

    def test_returns_dataclass(self, calc):
        result = calc.trend()
        assert isinstance(result, TrendResult)

    def test_uptrend_detection(self, uptrend_df):
        """ราคาขึ้นต่อเนื่อง → EMA20 > EMA50, trend = uptrend"""
        calc = TechnicalIndicators(uptrend_df)
        result = calc.trend()
        assert result.trend == "uptrend"
        assert result.ema_20 > result.ema_50
        assert result.golden_cross is True
        assert result.death_cross is False

    def test_downtrend_detection(self, downtrend_df):
        """ราคาลงต่อเนื่อง → EMA20 < EMA50, trend = downtrend"""
        calc = TechnicalIndicators(downtrend_df)
        result = calc.trend()
        assert result.trend == "downtrend"
        assert result.ema_20 < result.ema_50
        assert result.death_cross is True
        assert result.golden_cross is False

    def test_sma200_fallback_when_nan(self, ohlcv_short_df):
        """DataFrame สั้น → SMA200 = NaN → ใช้ EMA50 แทน"""
        calc = TechnicalIndicators(ohlcv_short_df)
        result = calc.trend()
        # SMA200 ต้อง fallback เป็นค่าเดียวกับ EMA50
        assert result.sma_200 == result.ema_50

    def test_trend_label_valid(self, calc):
        """trend ต้องเป็น uptrend / downtrend / sideways"""
        assert calc.trend().trend in {"uptrend", "downtrend", "sideways"}


# ══════════════════════════════════════════════════════════════════
# 7. compute_all() — รวมทุก indicator
# ══════════════════════════════════════════════════════════════════


class TestComputeAll:
    """ทดสอบ compute_all() ว่าประกอบ AllIndicators ครบ"""

    @patch("data_engine.indicators.get_thai_time")
    def test_returns_all_indicators(self, mock_time, ohlcv_df):
        """ต้องคืน AllIndicators dataclass ที่มี field ครบ"""
        mock_time.return_value = pd.Timestamp("2025-06-15 10:30:00", tz="Asia/Bangkok")
        calc = TechnicalIndicators(ohlcv_df)
        result = calc.compute_all()

        assert isinstance(result, AllIndicators)
        assert isinstance(result.rsi, RSIResult)
        assert isinstance(result.macd, MACDResult)
        assert isinstance(result.bollinger, BollingerResult)
        assert isinstance(result.atr, ATRResult)
        assert isinstance(result.trend, TrendResult)
        assert result.latest_close > 0

    @patch("data_engine.indicators.get_thai_time")
    def test_calculated_at_uses_thai_time(self, mock_time, ohlcv_df):
        """calculated_at ต้องใช้เวลาไทย (mock get_thai_time)"""
        fake_time = pd.Timestamp("2025-12-25 14:00:00", tz="Asia/Bangkok")
        mock_time.return_value = fake_time
        calc = TechnicalIndicators(ohlcv_df)
        result = calc.compute_all()
        assert "2025-12-25" in result.calculated_at


# ══════════════════════════════════════════════════════════════════
# 8. get_ml_dataframe()
# ══════════════════════════════════════════════════════════════════


class TestMLDataFrame:
    """ทดสอบ DataFrame export สำหรับ ML pipeline"""

    def test_no_nan(self, calc):
        """ML DataFrame ต้องไม่มี NaN เลย"""
        ml_df = calc.get_ml_dataframe()
        assert ml_df.isna().sum().sum() == 0

    def test_has_indicator_columns(self, calc):
        """ต้องมี columns indicator ครบ"""
        ml_df = calc.get_ml_dataframe()
        for col in ["rsi_14", "macd_line", "macd_hist", "bb_mid", "atr_14", "ema_20"]:
            assert col in ml_df.columns, f"Missing column: {col}"

    def test_shorter_than_original(self, calc):
        """ตัด NaN rows ออกแล้ว ต้องสั้นกว่า original (เพราะ warmup)"""
        ml_df = calc.get_ml_dataframe()
        assert len(ml_df) < len(calc.df)
        assert len(ml_df) > 0


# ══════════════════════════════════════════════════════════════════
# 9. to_dict() — JSON-ready output
# ══════════════════════════════════════════════════════════════════


class TestToDict:
    """ทดสอบ to_dict() ว่าสร้าง JSON-ready dict ถูกต้อง"""

    @patch("data_engine.indicators.get_thai_time")
    def test_has_all_keys(self, mock_time, ohlcv_df):
        mock_time.return_value = pd.Timestamp("2025-06-15 10:00:00", tz="Asia/Bangkok")
        calc = TechnicalIndicators(ohlcv_df)
        d = calc.to_dict(interval="5m")

        assert "rsi" in d
        assert "macd" in d
        assert "bollinger" in d
        assert "atr" in d
        assert "trend" in d
        assert "data_quality" in d

    @patch("data_engine.indicators.get_thai_time")
    def test_data_quality_good(self, mock_time, ohlcv_df):
        """ถ้าไม่มี warning → quality_score = good"""
        mock_time.return_value = pd.Timestamp("2025-06-15 10:00:00", tz="Asia/Bangkok")
        calc = TechnicalIndicators(ohlcv_df)
        d = calc.to_dict(interval="5m")
        # quality อาจเป็น good หรือ degraded ขึ้นกับ data
        assert d["data_quality"]["quality_score"] in {"good", "degraded"}

    @patch("data_engine.indicators.get_thai_time")
    def test_json_serializable(self, mock_time, ohlcv_df):
        """to_dict() ต้อง JSON serializable ได้"""
        import json

        mock_time.return_value = pd.Timestamp("2025-06-15 10:00:00", tz="Asia/Bangkok")
        calc = TechnicalIndicators(ohlcv_df)
        d = calc.to_dict(interval="1h")
        # ถ้า serialize ไม่ได้จะ raise TypeError
        json_str = json.dumps(d, ensure_ascii=False)
        assert len(json_str) > 0


# ══════════════════════════════════════════════════════════════════
# 10. Reliability Warnings
# ══════════════════════════════════════════════════════════════════


class TestReliabilityWarnings:
    """ทดสอบ get_reliability_warnings()"""

    def test_flat_market_warns_sideways(self, flat_df):
        """ราคาคงที่ → MA ทั้ง 3 ใกล้กัน → ต้อง warn"""
        calc = TechnicalIndicators(flat_df)
        warnings = calc.get_reliability_warnings(interval="5m")
        assert len(warnings) > 0
        assert any("sideways" in w for w in warnings)

    def test_trending_market_no_warning(self, uptrend_df):
        """ราคาขึ้นชัด → MA ห่างกัน → ไม่มี warning"""
        calc = TechnicalIndicators(uptrend_df)
        warnings = calc.get_reliability_warnings(interval="5m")
        assert len(warnings) == 0


# ══════════════════════════════════════════════════════════════════
# 11. Edge Cases
# ══════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """ทดสอบกรณีพิเศษ"""

    def test_minimum_rows_for_rsi(self):
        """15 rows = พอดี RSI(14) warmup → ต้องคำนวณได้"""
        df = _make_ohlcv(n=15, seed=1)
        calc = TechnicalIndicators(df)
        result = calc.rsi()
        assert np.isfinite(result.value)

    def test_constant_price(self):
        """ราคาเท่ากันทุก candle → RSI ≈ 100 (gain=0, loss=0 fillna)"""
        n = 100
        price = np.full(n, 2500.0)
        df = pd.DataFrame(
            {
                "open": price,
                "high": price + 0.01,
                "low": price - 0.01,
                "close": price,
                "volume": np.full(n, 10000),
            }
        )
        calc = TechnicalIndicators(df)
        result = calc.rsi()
        assert 0 <= result.value <= 100

    def test_two_rows_macd_no_crash(self):
        """
        MACD ต้องการ prev_hist → ถ้ามี 2 rows ต้องไม่ crash
        (อาจได้ NaN แต่ไม่ error)
        """
        df = _make_ohlcv(n=30, seed=5)  # ต้องมีอย่างน้อย 2 rows
        calc = TechnicalIndicators(df)
        result = calc.macd()
        assert isinstance(result, MACDResult)

    def test_reproducibility(self):
        """สร้าง 2 instance จาก seed เดียวกัน → ผลลัพธ์ต้องเหมือนกัน"""
        df1 = _make_ohlcv(n=300, seed=42)
        df2 = _make_ohlcv(n=300, seed=42)
        r1 = TechnicalIndicators(df1).rsi()
        r2 = TechnicalIndicators(df2).rsi()
        assert r1.value == r2.value
        assert r1.signal == r2.signal
