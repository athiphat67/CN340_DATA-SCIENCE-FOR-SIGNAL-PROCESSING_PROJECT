"""test_backtest_pipeline.py — Integration Tests สำหรับ Backtest Pipeline

ทดสอบ components ของ backtest_main_pipeline.py:
  1. build_market_state()        — สร้าง market_state dict จาก candle row
  2. CandleCache                 — JSON cache per candle (get/set/stats)
  3. _signal_correct()           — ตรวจว่า signal ตรงกับ actual direction
  4. NullNewsProvider            — neutral news sentiment
  5. Portfolio Integration       — SimPortfolio + build_market_state
  6. Market State Completeness   — PromptBuilder compatibility
  7. _apply_to_portfolio()       — BUY/SELL/HOLD execution + session window
  8. _add_validation()           — actual_direction, net_pnl, correct flags
  9. calculate_metrics()         — accuracy, sensitivity, PnL
 10. export_csv()                — file creation + metadata
 11. Full Pipeline Flow          — MockReact + run() end-to-end

Strategy:
  - ใช้ mock data (pd.Series / DataFrame) แทน CSV จริง
  - ใช้ SimPortfolio จริง (ไม่ mock) เพราะเป็น in-memory
  - ใช้ NullNewsProvider (neutral sentiment)
  - ใช้ MagicMock แทน ReactOrchestrator (ไม่เรียก LLM จริง)
  - ใช้ tmp_path สำหรับ CandleCache + export (ไม่เขียน disk จริง)
  - ไม่ใช้ Ollama/API จริง
"""

import os
import json
import pytest
from unittest.mock import MagicMock
from pathlib import Path

import pandas as pd
import numpy as np

from backtest.backtest_main_pipeline import (
    build_market_state,
    CandleCache,
    _signal_correct,
    MainPipelineBacktest,
)
from backtest.engine.portfolio import (
    SimPortfolio,
    PortfolioBustException,
    DEFAULT_CASH,
    BUST_THRESHOLD,
    WIN_THRESHOLD,
    SPREAD_THB,
    COMMISSION_THB,
)
from backtest.engine.news_provider import NullNewsProvider


# ══════════════════════════════════════════════════════════════════
# Fixtures (Common fixtures ย้ายไป conftest.py)
# ══════════════════════════════════════════════════════════════════


# ── Shared helpers ──────────────────────────────────────────────────────────


def _make_result_row(i=0, price=45000.0, llm_signal="BUY", final_signal="BUY"):
    """สร้าง result row dict มาตรฐาน (ใช้แทน _setup_results / _prepare_bt ที่ซ้ำกัน)"""
    return {
        "timestamp": f"2026-04-01 {10 + i}:00",
        "close_thai": price,
        "llm_signal": llm_signal,
        "llm_confidence": 0.8,
        "final_signal": final_signal,
        "final_confidence": 0.8,
        "rejection_reason": None,
        "position_size_thb": 500.0,
        "stop_loss": 0.0,
        "take_profit": 0.0,
        "iterations_used": 1,
        "news_sentiment": 0.0,
        "from_cache": False,
    }


def _load_results(bt, prices, llm_signals, final_signals=None):
    """ใส่ results เข้า bt instance (ใช้แทน _setup_results / _prepare_bt ที่ซ้ำกัน)"""
    if final_signals is None:
        final_signals = llm_signals
    bt.results = [
        _make_result_row(i, p, ls, fs)
        for i, (p, ls, fs) in enumerate(zip(prices, llm_signals, final_signals))
    ]


# ══════════════════════════════════════════════════════════════════
# 1. build_market_state — สร้าง market_state dict
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestBuildMarketState:
    """ทดสอบ build_market_state() — แปลง candle row → market_state dict"""

    def test_returns_dict(self, sample_row, portfolio, neutral_news):
        """ต้องคืน dict"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        assert isinstance(ms, dict)

    def test_has_required_top_keys(self, sample_row, portfolio, neutral_news):
        """ต้องมี keys: market_data, technical_indicators, news, portfolio, interval, timestamp"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        required = {
            "market_data",
            "technical_indicators",
            "news",
            "portfolio",
            "interval",
            "timestamp",
        }
        assert required.issubset(ms.keys())

    def test_market_data_structure(self, sample_row, portfolio, neutral_news):
        """market_data ต้องมี thai_gold_thb, spot_price, forex, ohlcv"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        md = ms["market_data"]
        assert "thai_gold_thb" in md
        assert "spot_price" in md
        assert "forex" in md
        assert "ohlcv" in md

    def test_ohlcv_values(self, sample_row, portfolio, neutral_news):
        """OHLCV ต้องตรงกับ row"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        ohlcv = ms["market_data"]["ohlcv"]
        assert ohlcv["open"] == 44800.0
        assert ohlcv["high"] == 45200.0
        assert ohlcv["low"] == 44700.0
        assert ohlcv["close"] == 45000.0
        assert ohlcv["volume"] == 1000.0

    def test_price_values(self, sample_row, portfolio, neutral_news):
        """spot_price_thb ต้องตรงกับ close_thai"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        assert ms["market_data"]["thai_gold_thb"]["spot_price_thb"] == 45000.0
        assert ms["market_data"]["spot_price"]["price_usd_per_oz"] == 2350.0
        assert ms["market_data"]["forex"]["USDTHB"] == 34.5

    def test_technical_indicators_structure(self, sample_row, portfolio, neutral_news):
        """technical_indicators ต้องมี rsi, macd, trend, bollinger, atr"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        ti = ms["technical_indicators"]
        assert "rsi" in ti
        assert "macd" in ti
        assert "trend" in ti
        assert "bollinger" in ti
        assert "atr" in ti

    def test_rsi_value_and_signal(self, sample_row, portfolio, neutral_news):
        """RSI=55 → signal=neutral"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        rsi = ms["technical_indicators"]["rsi"]
        assert rsi["value"] == 55.0
        assert rsi["period"] == 14
        assert rsi["signal"] == "neutral"

    def test_rsi_overbought(self, overbought_row, portfolio, neutral_news):
        """RSI=75 → signal=overbought"""
        ms = build_market_state(overbought_row, portfolio, neutral_news, "1h")
        assert ms["technical_indicators"]["rsi"]["signal"] == "overbought"

    def test_rsi_oversold(self, oversold_row, portfolio, neutral_news):
        """RSI=25 → signal=oversold"""
        ms = build_market_state(oversold_row, portfolio, neutral_news, "1h")
        assert ms["technical_indicators"]["rsi"]["signal"] == "oversold"

    def test_macd_bullish(self, sample_row, portfolio, neutral_news):
        """macd_hist > 0 → signal=bullish"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        macd = ms["technical_indicators"]["macd"]
        assert macd["histogram"] == 2.3
        assert macd["signal"] == "bullish"

    def test_macd_bearish(self, overbought_row, portfolio, neutral_news):
        """macd_hist < 0 → signal=bearish"""
        ms = build_market_state(overbought_row, portfolio, neutral_news, "1h")
        assert ms["technical_indicators"]["macd"]["signal"] == "bearish"

    def test_trend_uptrend(self, sample_row, portfolio, neutral_news):
        """ema_20 > ema_50 → trend=uptrend"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        assert ms["technical_indicators"]["trend"]["trend"] == "uptrend"

    def test_trend_downtrend(self, overbought_row, portfolio, neutral_news):
        """ema_20 < ema_50 → trend=downtrend"""
        ms = build_market_state(overbought_row, portfolio, neutral_news, "1h")
        assert ms["technical_indicators"]["trend"]["trend"] == "downtrend"

    def test_bollinger_values(self, sample_row, portfolio, neutral_news):
        """Bollinger bands ต้องตรงกับ row"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        bb = ms["technical_indicators"]["bollinger"]
        assert bb["upper"] == 45500.0
        assert bb["lower"] == 44300.0
        assert bb["mid"] == 44900.0

    def test_atr_value(self, sample_row, portfolio, neutral_news):
        """ATR ต้องตรงกับ row"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        assert ms["technical_indicators"]["atr"]["value"] == 150.0

    def test_news_passthrough(self, sample_row, portfolio, neutral_news):
        """news dict ต้อง pass through ตรงๆ"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        assert ms["news"]["overall_sentiment"] == 0.0
        assert ms["news"]["news_count"] == 0

    def test_portfolio_state(self, sample_row, portfolio, neutral_news):
        """portfolio ต้องมี cash_balance, gold_grams, can_buy, can_sell"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        port = ms["portfolio"]
        assert port["cash_balance"] == DEFAULT_CASH
        assert port["gold_grams"] == 0.0
        assert "YES" in port["can_buy"]
        assert "NO" in port["can_sell"]

    def test_interval_passthrough(self, sample_row, portfolio, neutral_news):
        """interval ต้อง pass through"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "4h")
        assert ms["interval"] == "4h"

    def test_timestamp_string(self, sample_row, portfolio, neutral_news):
        """timestamp ต้องเป็น string"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        assert isinstance(ms["timestamp"], str)
        assert "2026-04-01" in ms["timestamp"]

    def test_missing_columns_use_defaults(self, portfolio, neutral_news):
        """column ที่ไม่มี → ใช้ default values"""
        minimal_row = pd.Series(
            {
                "timestamp": pd.Timestamp("2026-04-01"),
                "close_thai": 44000.0,
            }
        )
        ms = build_market_state(minimal_row, portfolio, neutral_news, "1h")
        assert ms["market_data"]["ohlcv"]["close"] == 44000.0
        assert ms["technical_indicators"]["rsi"]["value"] == 50.0  # default
        assert ms["technical_indicators"]["atr"]["value"] == 0.0  # default


# ══════════════════════════════════════════════════════════════════
# 2. CandleCache — JSON cache per candle
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestCandleCache:
    """ทดสอบ CandleCache — file-based cache สำหรับ backtest"""

    def test_miss_on_empty_cache(self, tmp_path):
        """cache ว่าง → get returns None"""
        cache = CandleCache(str(tmp_path), model="test_model")
        ts = pd.Timestamp("2026-04-01 10:00")
        assert cache.get(ts) is None

    def test_set_and_get(self, tmp_path):
        """set แล้ว get → ได้ค่าเดิม"""
        cache = CandleCache(str(tmp_path), model="test_model")
        ts = pd.Timestamp("2026-04-01 10:00")
        data = {"signal": "BUY", "confidence": 0.8}

        cache.set(ts, data)
        result = cache.get(ts)
        assert result is not None
        assert result["signal"] == "BUY"
        assert result["confidence"] == 0.8

    def test_miss_different_timestamp(self, tmp_path):
        """set timestamp A → get timestamp B → None"""
        cache = CandleCache(str(tmp_path), model="test_model")
        ts_a = pd.Timestamp("2026-04-01 10:00")
        ts_b = pd.Timestamp("2026-04-01 11:00")

        cache.set(ts_a, {"signal": "BUY"})
        assert cache.get(ts_b) is None

    def test_stats_initial(self, tmp_path):
        """stats เริ่มต้น = 0 hits, 0 misses"""
        cache = CandleCache(str(tmp_path), model="test_model")
        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    def test_stats_after_hit(self, tmp_path):
        """hit 1 ครั้ง → stats ถูกต้อง"""
        cache = CandleCache(str(tmp_path), model="test_model")
        ts = pd.Timestamp("2026-04-01 10:00")
        cache.set(ts, {"signal": "HOLD"})
        cache.get(ts)  # hit

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 1.0

    def test_stats_after_miss(self, tmp_path):
        """miss 1 ครั้ง → stats ถูกต้อง"""
        cache = CandleCache(str(tmp_path), model="test_model")
        ts = pd.Timestamp("2026-04-01 10:00")
        cache.get(ts)  # miss

        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.0

    def test_stats_mixed(self, tmp_path):
        """1 hit + 1 miss → hit_rate = 0.5"""
        cache = CandleCache(str(tmp_path), model="test_model")
        ts = pd.Timestamp("2026-04-01 10:00")
        cache.set(ts, {"signal": "HOLD"})
        cache.get(ts)  # hit
        cache.get(pd.Timestamp("2026-04-01 11:00"))  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_overwrite_existing(self, tmp_path):
        """set ซ้ำ → overwrite ค่าเก่า"""
        cache = CandleCache(str(tmp_path), model="test_model")
        ts = pd.Timestamp("2026-04-01 10:00")

        cache.set(ts, {"signal": "BUY"})
        cache.set(ts, {"signal": "SELL"})

        result = cache.get(ts)
        assert result["signal"] == "SELL"

    def test_creates_directory(self, tmp_path):
        """cache directory ถูกสร้างอัตโนมัติ"""
        cache_dir = str(tmp_path / "deep" / "nested" / "cache")
        cache = CandleCache(cache_dir, model="test")
        assert os.path.isdir(cache_dir)

    def test_special_chars_in_model(self, tmp_path):
        """model name มีอักขระพิเศษ → sanitize ได้"""
        cache = CandleCache(str(tmp_path), model="qwen3.5:9b")
        ts = pd.Timestamp("2026-04-01 10:00")
        cache.set(ts, {"ok": True})
        assert cache.get(ts)["ok"] is True

    def test_unicode_data(self, tmp_path):
        """data มี unicode → save/load ได้"""
        cache = CandleCache(str(tmp_path), model="test")
        ts = pd.Timestamp("2026-04-01 10:00")
        cache.set(ts, {"rationale": "ราคาทองสูงเกินไป"})
        result = cache.get(ts)
        assert "ราคาทอง" in result["rationale"]


# ══════════════════════════════════════════════════════════════════
# 3. _signal_correct — ตรวจว่า signal ตรง actual direction
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestSignalCorrect:
    """ทดสอบ _signal_correct() — signal vs actual direction"""

    def test_buy_up_correct(self):
        """BUY + UP → True"""
        assert _signal_correct("BUY", "UP") is True

    def test_buy_down_incorrect(self):
        """BUY + DOWN → False"""
        assert _signal_correct("BUY", "DOWN") is False

    def test_buy_flat_incorrect(self):
        """BUY + FLAT → False"""
        assert _signal_correct("BUY", "FLAT") is False

    def test_sell_down_correct(self):
        """SELL + DOWN → True"""
        assert _signal_correct("SELL", "DOWN") is True

    def test_sell_up_incorrect(self):
        """SELL + UP → False"""
        assert _signal_correct("SELL", "UP") is False

    def test_sell_flat_incorrect(self):
        """SELL + FLAT → False"""
        assert _signal_correct("SELL", "FLAT") is False

    def test_hold_flat_correct(self):
        """HOLD + FLAT → True"""
        assert _signal_correct("HOLD", "FLAT") is True

    def test_hold_up_incorrect(self):
        """HOLD + UP → False"""
        assert _signal_correct("HOLD", "UP") is False

    def test_hold_down_incorrect(self):
        """HOLD + DOWN → False"""
        assert _signal_correct("HOLD", "DOWN") is False

    def test_unknown_signal(self):
        """signal ไม่รู้จัก → False"""
        assert _signal_correct("UNKNOWN", "UP") is False

    def test_empty_signal(self):
        """signal ว่าง → False"""
        assert _signal_correct("", "UP") is False


# ══════════════════════════════════════════════════════════════════
# 4. NullNewsProvider — neutral news
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestNullNewsProvider:
    """ทดสอบ NullNewsProvider — คืน neutral sentiment เสมอ"""

    def test_returns_dict(self):
        """get() ต้องคืน dict"""
        provider = NullNewsProvider(log=False)
        result = provider.get(pd.Timestamp("2026-04-01 10:00"))
        assert isinstance(result, dict)

    def test_neutral_sentiment(self):
        """sentiment ต้องเป็น 0.0"""
        provider = NullNewsProvider(log=False)
        result = provider.get(pd.Timestamp("2026-04-01 10:00"))
        assert result["overall_sentiment"] == 0.0

    def test_zero_news_count(self):
        """news_count ต้องเป็น 0"""
        provider = NullNewsProvider(log=False)
        result = provider.get(pd.Timestamp("2026-04-01 10:00"))
        assert result["news_count"] == 0

    def test_has_summary(self):
        """ต้องมี top_headlines_summary"""
        provider = NullNewsProvider(log=False)
        result = provider.get(pd.Timestamp("2026-04-01 10:00"))
        assert "top_headlines_summary" in result

    def test_different_timestamps_same_result(self):
        """ทุก timestamp → ผลลัพธ์เหมือนกัน"""
        provider = NullNewsProvider(log=False)
        r1 = provider.get(pd.Timestamp("2026-01-01"))
        r2 = provider.get(pd.Timestamp("2026-12-31"))
        assert r1 == r2

    def test_source_name(self):
        """source_name ต้องเป็นชื่อ class"""
        provider = NullNewsProvider(log=False)
        assert provider.source_name == "NullNewsProvider"

    def test_returns_copy(self):
        """get() ต้องคืน copy (ไม่ share reference)"""
        provider = NullNewsProvider(log=False)
        r1 = provider.get(pd.Timestamp("2026-04-01"))
        r1["overall_sentiment"] = 999.0
        r2 = provider.get(pd.Timestamp("2026-04-01"))
        assert r2["overall_sentiment"] == 0.0


# ══════════════════════════════════════════════════════════════════
# 5. Portfolio Integration — ใช้ SimPortfolio จริง
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestPortfolioIntegration:
    """ทดสอบ SimPortfolio ร่วมกับ build_market_state"""

    def test_initial_portfolio_in_market_state(self, sample_row, neutral_news):
        """portfolio ใหม่ → cash = DEFAULT_CASH, gold = 0"""
        port = SimPortfolio()
        ms = build_market_state(sample_row, port, neutral_news, "1h")
        assert ms["portfolio"]["cash_balance"] == DEFAULT_CASH
        assert ms["portfolio"]["gold_grams"] == 0.0

    def test_after_buy_portfolio_in_market_state(self, sample_row, neutral_news):
        """หลัง buy → gold_grams > 0, cash ลดลง"""
        port = SimPortfolio()
        port.execute_buy(45000.0, 500.0, timestamp="2026-04-01 10:00")

        ms = build_market_state(sample_row, port, neutral_news, "1h")
        assert ms["portfolio"]["gold_grams"] > 0
        assert ms["portfolio"]["cash_balance"] < DEFAULT_CASH
        assert "YES" in ms["portfolio"]["can_sell"]

    def test_portfolio_updates_reflect_in_market_state(self, sample_row, neutral_news):
        """buy + sell → กลับไป gold = 0"""
        port = SimPortfolio()
        port.execute_buy(45000.0, 500.0, timestamp="2026-04-01 10:00")
        port.execute_sell(45100.0, timestamp="2026-04-01 11:00")

        ms = build_market_state(sample_row, port, neutral_news, "1h")
        assert ms["portfolio"]["gold_grams"] == 0.0
        assert "NO" in ms["portfolio"]["can_sell"]


# ══════════════════════════════════════════════════════════════════
# 6. Market State Completeness — PromptBuilder compatibility
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestMarketStateCompleteness:
    """ตรวจว่า market_state มีโครงสร้างครบตาม PromptBuilder spec"""

    def test_all_indicator_keys(self, sample_row, portfolio, neutral_news):
        """technical_indicators ต้องมี 5 keys"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        ti = ms["technical_indicators"]
        expected = {"rsi", "macd", "trend", "bollinger", "atr"}
        assert expected == set(ti.keys())

    def test_rsi_has_required_fields(self, sample_row, portfolio, neutral_news):
        """rsi ต้องมี value, period, signal"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        rsi = ms["technical_indicators"]["rsi"]
        assert "value" in rsi
        assert "period" in rsi
        assert "signal" in rsi

    def test_macd_has_required_fields(self, sample_row, portfolio, neutral_news):
        """macd ต้องมี macd_line, signal_line, histogram, signal"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        macd = ms["technical_indicators"]["macd"]
        assert "macd_line" in macd
        assert "signal_line" in macd
        assert "histogram" in macd
        assert "signal" in macd

    def test_trend_has_required_fields(self, sample_row, portfolio, neutral_news):
        """trend ต้องมี ema_20, ema_50, trend"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        trend = ms["technical_indicators"]["trend"]
        assert "ema_20" in trend
        assert "ema_50" in trend
        assert "trend" in trend

    def test_bollinger_has_required_fields(self, sample_row, portfolio, neutral_news):
        """bollinger ต้องมี upper, lower, mid"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        bb = ms["technical_indicators"]["bollinger"]
        assert "upper" in bb
        assert "lower" in bb
        assert "mid" in bb

    def test_all_values_are_numbers(self, sample_row, portfolio, neutral_news):
        """ค่า technical indicator ต้องเป็นตัวเลข"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        ti = ms["technical_indicators"]

        assert isinstance(ti["rsi"]["value"], (int, float))
        assert isinstance(ti["macd"]["macd_line"], (int, float))
        assert isinstance(ti["trend"]["ema_20"], (int, float))
        assert isinstance(ti["bollinger"]["upper"], (int, float))
        assert isinstance(ti["atr"]["value"], (int, float))

    def test_market_state_json_serializable(self, sample_row, portfolio, neutral_news):
        """market_state ต้อง serialize เป็น JSON ได้"""
        ms = build_market_state(sample_row, portfolio, neutral_news, "1h")
        json_str = json.dumps(ms, default=str)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["interval"] == "1h"


# ══════════════════════════════════════════════════════════════════
# Helpers สำหรับ integration tests
# ══════════════════════════════════════════════════════════════════


def _make_candle_result(
    signal="HOLD",
    price=45000.0,
    pos_size=500.0,
    can_execute=True,
    confidence=0.8,
    rejection=None,
):
    """สร้าง candle_result dict สำหรับ _apply_to_portfolio"""
    return {
        "timestamp": "2026-04-01 10:00",
        "close_thai": price,
        "llm_signal": signal,
        "llm_confidence": confidence,
        "llm_rationale": "test",
        "final_signal": signal,
        "final_confidence": confidence,
        "rejection_reason": rejection,
        "position_size_thb": pos_size,
        "stop_loss": price - 500,
        "take_profit": price + 1000,
        "iterations_used": 1,
        "news_sentiment": 0.0,
        "from_cache": False,
        "session_id": "MORN",
        "can_execute": can_execute,
        "hsh_buy": 0.0,
        "hsh_sell": 0.0,
        "has_real_hsh": False,
    }


@pytest.fixture
def bt_instance(tmp_path):
    """MainPipelineBacktest พร้อม temp directories (ไม่ต้อง CSV จริง)"""
    # สร้างไฟล์ dummy CSV เพื่อป้องกัน path-validation error ในอนาคต
    dummy_csv = tmp_path / "dummy.csv"
    dummy_csv.touch()
    bt = MainPipelineBacktest(
        gold_csv=str(dummy_csv),
        news_provider=NullNewsProvider(log=False),
        cache_dir=str(tmp_path / "cache"),
        output_dir=str(tmp_path / "output"),
        request_delay=0,
    )
    return bt


# ══════════════════════════════════════════════════════════════════
# 7. _apply_to_portfolio — BUY/SELL/HOLD execution
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestApplyToPortfolio:
    """ทดสอบ _apply_to_portfolio() — อัปเดต portfolio ตาม signal"""

    def test_buy_signal_increases_gold(self, bt_instance):
        """BUY → gold_grams > 0"""
        cr = _make_candle_result(signal="BUY", price=45000.0, pos_size=500.0)
        bt_instance._apply_to_portfolio(cr, timestamp="2026-04-01 10:00")
        assert bt_instance.portfolio.gold_grams > 0

    def test_buy_signal_decreases_cash(self, bt_instance):
        """BUY → cash ลดลง"""
        initial_cash = bt_instance.portfolio.cash_balance
        cr = _make_candle_result(signal="BUY", price=45000.0, pos_size=500.0)
        bt_instance._apply_to_portfolio(cr, timestamp="2026-04-01 10:00")
        assert bt_instance.portfolio.cash_balance < initial_cash

    def test_sell_after_buy_clears_gold(self, bt_instance):
        """BUY → SELL → gold = 0"""
        cr_buy = _make_candle_result(signal="BUY", price=45000.0, pos_size=500.0)
        bt_instance._apply_to_portfolio(cr_buy, timestamp="2026-04-01 10:00")
        assert bt_instance.portfolio.gold_grams > 0

        cr_sell = _make_candle_result(signal="SELL", price=45500.0)
        bt_instance._apply_to_portfolio(cr_sell, timestamp="2026-04-01 11:00")
        assert bt_instance.portfolio.gold_grams == 0.0

    def test_hold_signal_no_change(self, bt_instance):
        """HOLD → portfolio ไม่เปลี่ยน"""
        cash_before = bt_instance.portfolio.cash_balance
        gold_before = bt_instance.portfolio.gold_grams
        cr = _make_candle_result(signal="HOLD")
        bt_instance._apply_to_portfolio(cr, timestamp="2026-04-01 10:00")
        assert bt_instance.portfolio.cash_balance == cash_before
        assert bt_instance.portfolio.gold_grams == gold_before

    def test_outside_session_skips_execution(self, bt_instance):
        """can_execute=False → ไม่ execute แม้ signal=BUY"""
        cash_before = bt_instance.portfolio.cash_balance
        cr = _make_candle_result(signal="BUY", can_execute=False)
        bt_instance._apply_to_portfolio(cr, timestamp="2026-04-01 03:00")
        assert bt_instance.portfolio.cash_balance == cash_before
        assert bt_instance.portfolio.gold_grams == 0.0

    def test_sell_without_gold_no_error(self, bt_instance):
        """SELL ตอนไม่มีทอง → ไม่ error, cash ไม่เปลี่ยน"""
        cash_before = bt_instance.portfolio.cash_balance
        cr = _make_candle_result(signal="SELL", price=45000.0)
        bt_instance._apply_to_portfolio(cr, timestamp="2026-04-01 10:00")
        assert bt_instance.portfolio.cash_balance == cash_before

    def test_buy_records_trade(self, bt_instance):
        """BUY → trades_today เพิ่ม"""
        bt_instance.portfolio.reset_daily("2026-04-01")
        cr = _make_candle_result(signal="BUY", price=45000.0, pos_size=500.0)
        bt_instance._apply_to_portfolio(cr, timestamp="2026-04-01 10:00")
        assert bt_instance.portfolio.trades_today >= 1


# ══════════════════════════════════════════════════════════════════
# 8. _add_validation — actual_direction, net_pnl, correct flags
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestAddValidation:
    """ทดสอบ _add_validation() — เพิ่ม validation columns"""

    def test_adds_actual_direction_up(self, bt_instance):
        """ราคาขึ้น → actual_direction = UP"""
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "BUY", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert df.iloc[0]["actual_direction"] == "UP"

    def test_adds_actual_direction_down(self, bt_instance):
        """ราคาลง → actual_direction = DOWN"""
        _load_results(
            bt_instance,
            prices=[46000, 45000, 44000],
            llm_signals=["SELL", "SELL", "HOLD"],
            final_signals=["SELL", "SELL", "HOLD"],
        )
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert df.iloc[0]["actual_direction"] == "DOWN"

    def test_last_row_is_nan(self, bt_instance):
        """แถวสุดท้ายไม่มี next_close → NaN"""
        _load_results(bt_instance, [45000, 45500], ["BUY", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert pd.isna(df.iloc[-1]["next_close"])

    def test_adds_actual_direction_flat(self, bt_instance):
        """ราคาเท่ากัน → actual_direction = FLAT"""
        _load_results(bt_instance, [45000, 45000, 45000], ["HOLD", "HOLD", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert df.iloc[0]["actual_direction"] == "FLAT"

    def test_net_pnl_calculation(self, bt_instance):
        """net_pnl = price_change - SPREAD_THB - COMMISSION_THB"""
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "HOLD", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        expected_pnl = 500.0 - SPREAD_THB - COMMISSION_THB
        assert abs(df.iloc[0]["net_pnl_thb"] - expected_pnl) < 0.01

    def test_llm_correct_flag(self, bt_instance):
        """BUY + UP → llm_correct = True"""
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "BUY", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert df.iloc[0]["llm_correct"]

    def test_llm_incorrect_flag(self, bt_instance):
        """BUY + DOWN → llm_correct = False"""
        _load_results(bt_instance, [46000, 45000, 44000], ["BUY", "BUY", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert not df.iloc[0]["llm_correct"]

    def test_final_correct_flag(self, bt_instance):
        """SELL + DOWN → final_correct = True"""
        _load_results(bt_instance, [46000, 45000, 44000], ["SELL", "SELL", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert df.iloc[0]["final_correct"]

    def test_profitable_flag(self, bt_instance):
        """BUY + UP + net_pnl > 0 → llm_profitable = True"""
        # BUY ราคาขึ้น 500 บาท ต้อง profitable แน่นอนหากค่า spread+commission < 500
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "BUY", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        assert df.iloc[0]["net_pnl_thb"] > 0, "ข้อมูลทดสอบควรให้ net_pnl > 0"
        assert df.iloc[0]["llm_profitable"]

    def test_result_df_has_all_columns(self, bt_instance):
        """result_df ต้องมี validation columns ครบ"""
        _load_results(bt_instance, [45000, 45500], ["BUY", "HOLD"])
        bt_instance._add_validation()
        df = bt_instance.result_df
        required = [
            "actual_direction",
            "next_close",
            "price_change",
            "net_pnl_thb",
            "llm_correct",
            "final_correct",
            "llm_profitable",
            "final_profitable",
        ]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"


# ══════════════════════════════════════════════════════════════════
# 9. calculate_metrics — accuracy, sensitivity, PnL
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestCalculateMetrics:
    """ทดสอบ calculate_metrics() — สรุปผล backtest"""

    def test_returns_dict(self, bt_instance):
        """calculate_metrics() ต้องคืน dict"""
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "BUY", "HOLD"])
        bt_instance._add_validation()
        metrics = bt_instance.calculate_metrics()
        assert isinstance(metrics, dict)

    def test_has_llm_and_final_keys(self, bt_instance):
        """ต้องมี llm และ final keys"""
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "BUY", "HOLD"])
        bt_instance._add_validation()
        metrics = bt_instance.calculate_metrics()
        assert "llm" in metrics
        assert "final" in metrics

    def test_metrics_structure(self, bt_instance):
        """metric ต้องมี keys ครบ"""
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "SELL", "HOLD"])
        bt_instance._add_validation()
        metrics = bt_instance.calculate_metrics()
        required_keys = {
            "directional_accuracy_pct",
            "signal_sensitivity_pct",
            "total_signals",
            "buy_signals",
            "sell_signals",
            "correct_signals",
            "correct_profitable",
            "avg_net_pnl_thb",
            "rejected_by_risk",
            "avg_confidence",
        }
        assert required_keys.issubset(metrics["llm"].keys())

    def test_all_hold_returns_note(self, bt_instance):
        """ทุก signal เป็น HOLD → note: all HOLD"""
        _load_results(bt_instance, [45000, 45500, 46000], ["HOLD", "HOLD", "HOLD"])
        bt_instance._add_validation()
        metrics = bt_instance.calculate_metrics()
        assert metrics["llm"]["note"] == "all HOLD"
        assert metrics["final"]["note"] == "all HOLD"

    def test_accuracy_100_pct(self, bt_instance):
        """BUY ทั้งหมด + ราคาขึ้นทั้งหมด → accuracy 100%"""
        _load_results(
            bt_instance, [45000, 45500, 46000, 46500], ["BUY", "BUY", "BUY", "HOLD"]
        )
        bt_instance._add_validation()
        metrics = bt_instance.calculate_metrics()
        assert metrics["llm"]["directional_accuracy_pct"] == 100.0

    def test_buy_sell_counts(self, bt_instance):
        """นับ BUY/SELL ถูกต้อง"""
        _load_results(
            bt_instance, [45000, 45500, 45300, 45800], ["BUY", "SELL", "BUY", "HOLD"]
        )
        bt_instance._add_validation()
        metrics = bt_instance.calculate_metrics()
        assert metrics["llm"]["buy_signals"] == 2
        assert metrics["llm"]["sell_signals"] == 1
        assert metrics["llm"]["total_signals"] == 3

    def test_sensitivity_calculation(self, bt_instance):
        """sensitivity = active_signals / total_candles * 100"""
        _load_results(
            bt_instance, [45000, 45500, 46000, 46500], ["BUY", "HOLD", "HOLD", "HOLD"]
        )
        bt_instance._add_validation()
        metrics = bt_instance.calculate_metrics()
        assert metrics["llm"]["signal_sensitivity_pct"] == 25.0

    def test_stores_metrics_on_instance(self, bt_instance):
        """calculate_metrics() ต้องเก็บผลใน bt.metrics"""
        _load_results(bt_instance, [45000, 45500, 46000], ["BUY", "HOLD", "HOLD"])
        bt_instance._add_validation()
        bt_instance.calculate_metrics()
        assert bt_instance.metrics is not None
        assert "llm" in bt_instance.metrics


# ══════════════════════════════════════════════════════════════════
# 10. export_csv — file creation + metadata
# ══════════════════════════════════════════════════════════════════


@pytest.mark.integration
class TestExportCsv:
    """ทดสอบ export_csv() — สร้างไฟล์ CSV"""

    def _ready(self, bt):
        """เตรียม bt ให้มี result_df + metrics พร้อม export"""
        _load_results(bt, [45000, 45500, 46000], ["BUY", "BUY", "HOLD"])
        bt._add_validation()
        bt.calculate_metrics()

    def test_creates_file(self, bt_instance):
        """export_csv() ต้องสร้างไฟล์"""
        self._ready(bt_instance)
        path = bt_instance.export_csv(filename="test_export.csv")
        assert os.path.exists(path)

    def test_returns_path_string(self, bt_instance):
        """ต้องคืน path string"""
        self._ready(bt_instance)
        path = bt_instance.export_csv(filename="test_export.csv")
        assert isinstance(path, str)
        assert "test_export.csv" in path

    def test_file_has_summary_header(self, bt_instance):
        """ไฟล์ต้องมี summary header"""
        self._ready(bt_instance)
        path = bt_instance.export_csv(filename="test_export.csv")
        with open(path, encoding="utf-8-sig") as f:
            content = f.read()
        assert "MAIN PIPELINE BACKTEST" in content

    def test_file_has_signal_log(self, bt_instance):
        """ไฟล์ต้องมี signal log data"""
        self._ready(bt_instance)
        path = bt_instance.export_csv(filename="test_export.csv")
        with open(path, encoding="utf-8-sig") as f:
            content = f.read()
        assert "DETAILED SIGNAL LOG" in content
        assert "close_thai" in content

    def test_auto_filename(self, bt_instance):
        """ไม่ระบุ filename → สร้างอัตโนมัติ"""
        self._ready(bt_instance)
        path = bt_instance.export_csv()
        assert os.path.exists(path)
        assert "main_backtest_" in os.path.basename(path)

    def test_output_dir_created(self, bt_instance):
        """output directory ถูกสร้างอัตโนมัติ"""
        self._ready(bt_instance)
        bt_instance.export_csv(filename="test_export.csv")
        assert os.path.isdir(bt_instance.output_dir)


# ══════════════════════════════════════════════════════════════════
# 11. Full Pipeline Flow — MockReact + run() end-to-end
# ══════════════════════════════════════════════════════════════════


def _make_mock_react(signal="BUY", confidence=0.85):
    """สร้าง mock ReactOrchestrator ที่คืน deterministic result"""
    mock = MagicMock()
    mock.run.return_value = {
        "final_decision": {
            "signal": signal,
            "confidence": confidence,
            "rationale": "mock test rationale",
            "rejection_reason": None,
            "position_size_thb": 500.0,
            "stop_loss": 44500.0,
            "take_profit": 46000.0,
        },
        "react_trace": [
            {
                "response": {
                    "signal": signal,
                    "confidence": confidence,
                    "rationale": "trace",
                }
            }
        ],
        "iterations_used": 2,
    }
    return mock


def _make_agg_df(n=5, base_price=45000.0, step=100.0):
    """สร้าง DataFrame จำลอง n candles (ราคาขึ้นทีละ step)"""
    rows = []
    for i in range(n):
        p = base_price + i * step
        rows.append(
            {
                "timestamp": pd.Timestamp(f"2026-04-01 {10 + i}:00"),
                "close_thai": p,
                "open_thai": p - 50,
                "high_thai": p + 100,
                "low_thai": p - 100,
                "volume": 1000.0,
                "gold_spot_usd": 2350.0,
                "usd_thb_rate": 34.5,
                "rsi": 55.0,
                "macd_line": 10.0,
                "signal_line": 8.0,
                "macd_hist": 2.0,
                "ema_20": p - 100,
                "ema_50": p - 300,
                "bb_upper": p + 500,
                "bb_lower": p - 500,
                "bb_mid": p,
                "atr": 150.0,
            }
        )
    return pd.DataFrame(rows)


@pytest.mark.integration
class TestFullPipelineFlow:
    """ทดสอบ MainPipelineBacktest.run() end-to-end ด้วย MockReact"""

    def _run_pipeline(self, bt, mock_react, agg_df):
        """inject mock + agg_df แล้วรัน pipeline

        หมายเหตุ: ใช้การ inject private attributes โดยตรงเพื่อ bypass LLM จริง
        หาก MainPipelineBacktest เพิ่ม constructor parameters สำหรับ dependency
        injection ในอนาคต ให้เปลี่ยนมาใช้วิธีนั้นแทน
        """
        bt.agg_df = agg_df
        bt._react = mock_react
        bt._prompt_builder = MagicMock()
        bt._risk_manager = MagicMock()
        bt.run()

    def test_run_produces_results(self, bt_instance):
        """run() ต้องสร้าง results"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(3))
        assert len(bt_instance.results) == 3

    def test_run_sets_result_df(self, bt_instance):
        """run() ต้อง set result_df (DataFrame)"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(3))
        assert bt_instance.result_df is not None
        assert isinstance(bt_instance.result_df, pd.DataFrame)

    def test_result_has_required_keys(self, bt_instance):
        """แต่ละ result ต้องมี keys ครบ"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(3))
        required = {
            "timestamp",
            "close_thai",
            "llm_signal",
            "final_signal",
            "from_cache",
            "iterations_used",
        }
        for r in bt_instance.results:
            assert required.issubset(r.keys())

    def test_portfolio_total_value_tracked(self, bt_instance):
        """ทุก candle ต้องมี portfolio_total_value"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(3))
        for r in bt_instance.results:
            assert "portfolio_total_value" in r
            assert r["portfolio_total_value"] > 0

    def test_mock_react_called(self, bt_instance):
        """ReactOrchestrator.run() ต้องถูกเรียกทุก candle"""
        mock = _make_mock_react()
        self._run_pipeline(bt_instance, mock, _make_agg_df(5))
        assert mock.run.call_count == 5

    def test_cache_populated_after_run(self, bt_instance):
        """หลัง run ครั้งแรก → miss ทุก candle (ยังไม่มี cache)"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(3))
        stats = bt_instance.cache.stats
        assert stats["misses"] == 3

    def test_cache_hit_on_second_run(self, bt_instance):
        """run ครั้งที่สอง (ข้อมูลเดิม) → cache hits ทุก candle, LLM ไม่ถูกเรียกซ้ำ"""
        agg_df = _make_agg_df(3)
        mock = _make_mock_react()
        self._run_pipeline(bt_instance, mock, agg_df)
        first_call_count = mock.run.call_count  # 3

        # reset stats แต่ cache file ยังอยู่
        bt_instance.cache._hits = 0
        bt_instance.cache._misses = 0
        mock2 = _make_mock_react()
        self._run_pipeline(bt_instance, mock2, agg_df)

        assert bt_instance.cache.stats["hits"] == 3
        assert mock2.run.call_count == 0  # ไม่เรียก LLM เพราะ cache hit ทุกตัว

    def test_all_hold_flow(self, bt_instance):
        """ทุก signal HOLD → portfolio ไม่เปลี่ยน"""
        mock = _make_mock_react(signal="HOLD", confidence=0.5)
        self._run_pipeline(bt_instance, mock, _make_agg_df(3))
        assert bt_instance.portfolio.gold_grams == 0.0
        assert bt_instance.portfolio.cash_balance == DEFAULT_CASH

    def test_buy_signal_changes_portfolio(self, bt_instance):
        """BUY signals → portfolio มี gold"""
        mock = _make_mock_react(signal="BUY", confidence=0.9)
        self._run_pipeline(bt_instance, mock, _make_agg_df(3))
        assert bt_instance.portfolio.gold_grams > 0

    def test_validation_columns_after_run(self, bt_instance):
        """run() → result_df มี validation columns"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(3))
        df = bt_instance.result_df
        assert "actual_direction" in df.columns
        assert "llm_correct" in df.columns
        assert "final_correct" in df.columns

    def test_full_flow_metrics(self, bt_instance):
        """run() → calculate_metrics() ทำงาน"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(5))
        metrics = bt_instance.calculate_metrics()
        assert "llm" in metrics
        assert "final" in metrics

    def test_full_flow_export(self, bt_instance):
        """run() → export_csv() สร้างไฟล์"""
        self._run_pipeline(bt_instance, _make_mock_react(), _make_agg_df(3))
        bt_instance.calculate_metrics()
        path = bt_instance.export_csv(filename="full_test.csv")
        assert os.path.exists(path)

    def test_react_error_handled(self, bt_instance):
        """ReactOrchestrator error → HOLD fallback ไม่ crash"""
        mock = MagicMock()
        mock.run.side_effect = RuntimeError("LLM timeout")
        self._run_pipeline(bt_instance, mock, _make_agg_df(3))
        assert len(bt_instance.results) == 3
        for r in bt_instance.results:
            assert r["final_signal"] == "HOLD"
