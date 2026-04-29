"""
test_pipeline.py — ทดสอบ Feature Pipeline ก่อนเชื่อมโมเดลจริง

รันด้วย:
    cd Src
    python -m tests.test_pipeline

ผ่านทั้งหมด → พร้อมเชื่อมโมเดลจริง
"""

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier

from .fetch_indicators import (
    TechnicalIndicators,
    ML_FEATURE_COLUMNS_XAUUSD,
    ML_FEATURE_COLUMNS_THAI,
)
from .fetch_indicators import fetch_ml_features

# ──────────────────────────────────────────────────────────────────────────────
# Mock Data
# ──────────────────────────────────────────────────────────────────────────────

def _make_mock_ohlcv(price: np.ndarray, index: pd.DatetimeIndex) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n   = len(price)
    return pd.DataFrame({
        "open":  price - rng.random(n) * 3,
        "high":  price + rng.random(n) * 8,
        "low":   price - rng.random(n) * 8,
        "close": price,
    }, index=index)


np.random.seed(42)
N         = 300
TS_XAUUSD = pd.date_range("2024-01-01 06:00", periods=N, freq="5min", tz="UTC")
TS_THAI   = pd.date_range("2024-01-01 09:00", periods=N, freq="5min", tz="UTC")

PRICE_XAUUSD = 2300 + np.cumsum(np.random.randn(N) * 5)
PRICE_THAI   = PRICE_XAUUSD * 35 / 31.1035 * 15.244

OHLCV_XAUUSD = _make_mock_ohlcv(PRICE_XAUUSD, TS_XAUUSD)
OHLCV_THAI   = _make_mock_ohlcv(PRICE_THAI,   TS_THAI)

USDTHB_SERIES  = pd.Series(35.0 + np.cumsum(np.random.randn(N) * 0.05), index=TS_XAUUSD)
XAUUSD_SERIES  = pd.Series(PRICE_XAUUSD, index=TS_THAI)


# ──────────────────────────────────────────────────────────────────────────────
# Level 1 — Features ออกมาถูกรูปไหม
# ──────────────────────────────────────────────────────────────────────────────

def test_level1_xauusd_features():
    print("\n[Level 1] XAU/USD features shape & columns")

    calc = TechnicalIndicators(OHLCV_XAUUSD)
    feat = calc.get_features("xauusd", external_series=USDTHB_SERIES)

    assert feat.shape[1] == 26,                          f"ต้องมี 26 columns ได้ {feat.shape[1]}"
    assert list(feat.columns) == ML_FEATURE_COLUMNS_XAUUSD, "column order ไม่ตรง"
    assert feat.isnull().sum().sum() == 0,               "มี NaN หลุดออกมา"
    assert len(feat) > 0,                                "ไม่มีแถวเลย"

    print(f"  ✅ shape={feat.shape}")
    print(f"  ✅ columns ตรงทั้ง 26")
    print(f"  ✅ ไม่มี NaN")
    print(feat.tail(2).to_string())


def test_level1_thai_features():
    print("\n[Level 1] Thai HSH features shape & columns")

    calc = TechnicalIndicators(OHLCV_THAI)
    feat = calc.get_features("thai", external_series=XAUUSD_SERIES)

    assert feat.shape[1] == 26,                        f"ต้องมี 26 columns ได้ {feat.shape[1]}"
    assert list(feat.columns) == ML_FEATURE_COLUMNS_THAI, "column order ไม่ตรง"
    assert feat.isnull().sum().sum() == 0,             "มี NaN หลุดออกมา"
    assert len(feat) > 0,                              "ไม่มีแถวเลย"

    print(f"  ✅ shape={feat.shape}")
    print(f"  ✅ columns ตรงทั้ง 26")
    print(f"  ✅ ไม่มี NaN")
    print(feat.tail(2).to_string())


def test_level1_feature_ranges():
    print("\n[Level 1] Feature value ranges")

    calc = TechnicalIndicators(OHLCV_XAUUSD)
    feat = calc.get_features("xauusd", external_series=USDTHB_SERIES)

    # RSI ต้องอยู่ใน 0–100
    rsi = feat["xauusd_rsi14"]
    assert rsi.between(0, 100).all(), f"RSI ออกนอก 0–100: min={rsi.min():.2f} max={rsi.max():.2f}"

    # atr_rank50 ต้องอยู่ใน 0–1
    rank = feat["atr_rank50"]
    assert rank.between(0, 1).all(), f"atr_rank50 ออกนอก 0–1: min={rank.min():.4f} max={rank.max():.4f}"

    # session_progress ต้องอยู่ใน 0–1
    sp = feat["session_progress"]
    assert sp.between(0, 1).all(), f"session_progress ออกนอก 0–1"

    # body_strength ต้องอยู่ใน 0–1
    bs = feat["body_strength"]
    assert bs.between(0, 1).all(), f"body_strength ออกนอก 0–1"

    print(f"  ✅ RSI         : {rsi.min():.1f} – {rsi.max():.1f}")
    print(f"  ✅ atr_rank50  : {rank.min():.3f} – {rank.max():.3f}")
    print(f"  ✅ session_prog: {sp.min():.3f} – {sp.max():.3f}")
    print(f"  ✅ body_strength: {bs.min():.3f} – {bs.max():.3f}")


# ──────────────────────────────────────────────────────────────────────────────
# Level 2 — ส่งเข้า Mock Model
# ──────────────────────────────────────────────────────────────────────────────

def _make_mock_model(feat: pd.DataFrame) -> DummyClassifier:
    """สร้าง mock BUY/SELL model จาก DummyClassifier"""
    X = feat.values
    y = np.random.randint(0, 2, len(X))
    model = DummyClassifier(strategy="uniform", random_state=42)
    model.fit(X, y)
    return model


def test_level2_mock_model_xauusd():
    print("\n[Level 2] Mock model inference — XAU/USD")

    calc = TechnicalIndicators(OHLCV_XAUUSD)
    feat = calc.get_features("xauusd", external_series=USDTHB_SERIES)

    buy_model  = _make_mock_model(feat)
    sell_model = _make_mock_model(feat)

    # inference บน 1 แถวล่าสุด (เหมือน live trading)
    X_latest  = feat.iloc[[-1]]
    prob_buy  = buy_model.predict_proba(X_latest)[:, 1][0]
    prob_sell = sell_model.predict_proba(X_latest)[:, 1][0]

    assert 0.0 <= prob_buy  <= 1.0, f"prob_buy ออกนอก 0–1: {prob_buy}"
    assert 0.0 <= prob_sell <= 1.0, f"prob_sell ออกนอก 0–1: {prob_sell}"

    print(f"  ✅ X_latest shape : {X_latest.shape}")
    print(f"  ✅ prob_buy       : {prob_buy:.4f}")
    print(f"  ✅ prob_sell      : {prob_sell:.4f}")


def test_level2_mock_model_thai():
    print("\n[Level 2] Mock model inference — Thai HSH")

    calc = TechnicalIndicators(OHLCV_THAI)
    feat = calc.get_features("thai", external_series=XAUUSD_SERIES)

    buy_model  = _make_mock_model(feat)
    sell_model = _make_mock_model(feat)

    X_latest  = feat.iloc[[-1]]
    prob_buy  = buy_model.predict_proba(X_latest)[:, 1][0]
    prob_sell = sell_model.predict_proba(X_latest)[:, 1][0]

    assert 0.0 <= prob_buy  <= 1.0
    assert 0.0 <= prob_sell <= 1.0

    print(f"  ✅ X_latest shape : {X_latest.shape}")
    print(f"  ✅ prob_buy       : {prob_buy:.4f}")
    print(f"  ✅ prob_sell      : {prob_sell:.4f}")


def test_level2_column_order_matches_model():
    """
    เช็คว่า column ที่ส่งเข้าโมเดลตรงกับ feature_columns.json
    (จำลองว่าโมเดลถูก train ด้วย ML_FEATURE_COLUMNS_XAUUSD)
    """
    print("\n[Level 2] Column order matches training order")

    calc = TechnicalIndicators(OHLCV_XAUUSD)
    feat = calc.get_features("xauusd", external_series=USDTHB_SERIES)

    # สมมติโมเดลถูก train ด้วย columns นี้ (ลำดับต้องตรง 100%)
    expected_cols = ML_FEATURE_COLUMNS_XAUUSD
    actual_cols   = list(feat.columns)

    assert actual_cols == expected_cols, (
        f"Column order ไม่ตรง!\n"
        f"Expected: {expected_cols}\n"
        f"Actual  : {actual_cols}"
    )
    print(f"  ✅ Column order ตรง 100% ({len(actual_cols)} columns)")


# ──────────────────────────────────────────────────────────────────────────────
# Level 3 — ทดสอบ fetch_ml_features() ทั้ง pipeline (bypass API)
# ──────────────────────────────────────────────────────────────────────────────

def test_level3_pipeline_xauusd():
    print("\n[Level 3] fetch_ml_features() pipeline — XAU/USD (bypass API)")

    result = fetch_ml_features(
        symbol="xauusd",
        ohlcv_df=OHLCV_XAUUSD,          # bypass fetch จริง
        external_series=USDTHB_SERIES,
    )

    assert result["error"] is None,          f"error: {result['error']}"
    assert result["symbol"] == "xauusd"
    assert result["n_rows"] > 0
    assert result["features"].shape[1] == 26
    assert result["data_quality"]["quality_score"] == "good"

    print(f"  ✅ error         : None")
    print(f"  ✅ symbol        : {result['symbol']}")
    print(f"  ✅ n_rows        : {result['n_rows']}")
    print(f"  ✅ features shape: {result['features'].shape}")
    print(f"  ✅ quality       : {result['data_quality']['quality_score']}")


def test_level3_pipeline_thai():
    print("\n[Level 3] fetch_ml_features() pipeline — Thai HSH (bypass API)")

    result = fetch_ml_features(
        symbol="thai",
        ohlcv_df=OHLCV_THAI,             # bypass fetch จริง
        external_series=XAUUSD_SERIES,
    )

    assert result["error"] is None,        f"error: {result['error']}"
    assert result["symbol"] == "thai"
    assert result["n_rows"] > 0
    assert result["features"].shape[1] == 26
    assert result["data_quality"]["quality_score"] == "good"

    print(f"  ✅ error         : None")
    print(f"  ✅ symbol        : {result['symbol']}")
    print(f"  ✅ n_rows        : {result['n_rows']}")
    print(f"  ✅ features shape: {result['features'].shape}")
    print(f"  ✅ quality       : {result['data_quality']['quality_score']}")


def test_level3_invalid_symbol():
    print("\n[Level 3] fetch_ml_features() invalid symbol → ValueError")

    try:
        fetch_ml_features(symbol="bitcoin")  # type: ignore
        assert False, "ต้อง raise ValueError"
    except ValueError as e:
        print(f"  ✅ ValueError: {e}")


def test_level3_empty_ohlcv():
    print("\n[Level 3] fetch_ml_features() empty ohlcv_df → error graceful")

    result = fetch_ml_features(
        symbol="xauusd",
        ohlcv_df=pd.DataFrame(),
    )

    assert result["error"] is not None
    assert result["n_rows"] == 0
    assert result["features"].empty
    print(f"  ✅ error   : {result['error']}")
    print(f"  ✅ n_rows  : {result['n_rows']}")
    print(f"  ✅ quality : {result['data_quality']['quality_score']}")


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        # Level 1
        test_level1_xauusd_features,
        test_level1_thai_features,
        test_level1_feature_ranges,
        # Level 2
        test_level2_mock_model_xauusd,
        test_level2_mock_model_thai,
        test_level2_column_order_matches_model,
        # Level 3
        test_level3_pipeline_xauusd,
        test_level3_pipeline_thai,
        test_level3_invalid_symbol,
        test_level3_empty_ohlcv,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"\n  ❌ FAILED: {test_fn.__name__}")
            print(f"     {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed / {len(tests)} total")
    if failed == 0:
        print("✅ พร้อมเชื่อมโมเดลจริง")
    else:
        print("❌ แก้ bug ก่อน deploy")
    print('='*50)


if __name__ == "__main__":
    run_all()
