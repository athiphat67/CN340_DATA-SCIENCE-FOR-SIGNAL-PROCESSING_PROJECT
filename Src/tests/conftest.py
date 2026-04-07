import os
import sys
import pytest
import pandas as pd

# เพิ่ม Src_DIR เข้า sys.path เพื่อให้ import module ของโปรเจคได้สะดวก
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backtest.engine.portfolio import SimPortfolio, DEFAULT_CASH, BUST_THRESHOLD, WIN_THRESHOLD
from backtest.engine.news_provider import NullNewsProvider

# ══════════════════════════════════════════════════════════════════
# Common Fixtures สำหรับ Backtest / Pipeline / Portfolio
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def portfolio():
    """SimPortfolio ใหม่พร้อมค่า default (ใช้ทดสอบ integration ทั่วไป)"""
    return SimPortfolio(
        initial_cash=DEFAULT_CASH,
        bust_threshold=BUST_THRESHOLD,
        win_threshold=WIN_THRESHOLD,
    )

@pytest.fixture
def neutral_news():
    """Neutral news dict (NullNewsProvider) สำหรับทดสอบโดยไม่มีผลกระทบจากข่าว"""
    return NullNewsProvider(log=False).get(pd.Timestamp("2026-04-01 10:00"))

@pytest.fixture
def sample_row():
    """1 candle row ปกติที่มี columns ครบ"""
    return pd.Series(
        {
            "timestamp": pd.Timestamp("2026-04-01 10:00"),
            "close_thai": 45000.0,
            "open_thai": 44800.0,
            "high_thai": 45200.0,
            "low_thai": 44700.0,
            "volume": 1000.0,
            "gold_spot_usd": 2350.0,
            "usd_thb_rate": 34.5,
            "rsi": 55.0,
            "macd_line": 10.5,
            "signal_line": 8.2,
            "macd_hist": 2.3,
            "ema_20": 44900.0,
            "ema_50": 44600.0,
            "bb_upper": 45500.0,
            "bb_lower": 44300.0,
            "bb_mid": 44900.0,
            "atr": 150.0,
        }
    )

@pytest.fixture
def overbought_row():
    """Candle ที่ RSI overbought + downtrend"""
    return pd.Series(
        {
            "timestamp": pd.Timestamp("2026-04-01 14:00"),
            "close_thai": 46000.0,
            "open_thai": 46200.0,
            "high_thai": 46300.0,
            "low_thai": 45900.0,
            "volume": 800.0,
            "gold_spot_usd": 2380.0,
            "usd_thb_rate": 34.5,
            "rsi": 75.0,
            "macd_line": -5.0,
            "signal_line": 2.0,
            "macd_hist": -7.0,
            "ema_20": 45800.0,
            "ema_50": 46100.0,
            "bb_upper": 46500.0,
            "bb_lower": 45500.0,
            "bb_mid": 46000.0,
            "atr": 200.0,
        }
    )

# ══════════════════════════════════════════════════════════════════
# Common Fixtures สำหรับ Notification / Market State
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def market_state():
    """Market state dict มาตรฐานที่ใช้ทดสอบร่วมกัน"""
    return {
        "market_data": {
            "thai_gold_thb": {
                "sell_price_thb": 45200,
                "buy_price_thb": 45000,
            },
            "spot_price_usd": {
                "price_usd_per_oz": 2350.50,
                "confidence": 0.98,
            },
            "forex": {"usd_thb": 34.50},
        },
        "data_quality": {"quality_score": "good"},
    }

@pytest.fixture
def market_state_minimal():
    """Market state ที่ไม่มี optional fields สำหรับทดสอบ edge cases"""
    return {"market_data": {}}
