"""
test_orchestrator.py — Pytest สำหรับ orchestrator module (GoldTradingOrchestrator)

ครอบคลุม:
  1. __init__ — สร้าง output_dir, เก็บ config
  2. run() — payload structure ครบถ้วน
  3. run() — save_to_file สร้างไฟล์ JSON
  4. run() — history_days override
  5. run() — no OHLCV data → degraded quality
  6. run() — indicator error → degraded quality
  7. Payload structure — meta, market_data, technical_indicators, news, data_quality

Strategy: Mock ทุก dependency (GoldDataFetcher, TechnicalIndicators, GoldNewsFetcher)
  - ไม่เรียก API จริง
  - ไม่คำนวณ indicator จริง
  - Deterministic 100%
"""

import json
import os
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from data_engine.orchestrator import GoldTradingOrchestrator

pytestmark = pytest.mark.data_engine


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════


def _mock_ohlcv_df() -> pd.DataFrame:
    """Mock OHLCV DataFrame"""
    rng = np.random.RandomState(42)
    n = 100
    dates = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    close = 2300 + rng.randn(n).cumsum()
    return pd.DataFrame(
        {
            "open": close - 1,
            "high": close + 5,
            "low": close - 5,
            "close": close,
            "volume": rng.randint(10000, 50000, n),
        },
        index=pd.DatetimeIndex(dates, name="datetime"),
    )


def _mock_call_tool(tool_name, **kwargs):
    """Mock call_tool — route แต่ละ tool ไปยัง mock data ที่ถูกต้อง"""
    if tool_name == "fetch_price":
        return {
            "spot_price_usd": {
                "source": "twelvedata",
                "price_usd_per_oz": 2350.50,
                "timestamp": "2026-04-01T10:00:00",
                "confidence": 0.98,
            },
            "forex": {"usd_thb": 34.50, "source": "exchangerate-api.com"},
            "thai_gold_thb": {"sell_price_thb": 45200, "buy_price_thb": 45000},
            "data_sources": {"spot": "twelvedata", "forex": "exchangerate-api"},
            "ohlcv_df": _mock_ohlcv_df(),
            "recent_price_action": [],
        }
    elif tool_name == "fetch_indicators":
        return {
            "indicators": {
                "rsi": {"value": 55.0, "signal": "neutral"},
                "macd": {"macd_line": 1.0, "signal_line": 0.5, "histogram": 0.5},
            },
            "data_quality": {"quality_score": "good", "warnings": []},
        }
    elif tool_name == "fetch_news":
        return {
            "summary": {
                "total_articles": 5,
                "overall_sentiment": 0.2,
                "fetched_at": "2026-04-01T10:00:00",
                "errors": [],
            },
            "by_category": {},
        }
    return {}


def _mock_call_tool_no_ohlcv(tool_name, **kwargs):
    """Mock call_tool — fetch_price คืน ohlcv_df=None (ไม่มีข้อมูล OHLCV)"""
    if tool_name == "fetch_price":
        return {
            "spot_price_usd": {
                "source": "twelvedata",
                "price_usd_per_oz": 2350.50,
                "timestamp": "2026-04-01T10:00:00",
                "confidence": 0.98,
            },
            "forex": {"usd_thb": 34.50, "source": "exchangerate-api.com"},
            "thai_gold_thb": {"sell_price_thb": 45200, "buy_price_thb": 45000},
            "data_sources": {},
            "ohlcv_df": None,
            "recent_price_action": [],
        }
    elif tool_name == "fetch_indicators":
        return {
            "indicators": {},
            "data_quality": {
                "quality_score": "degraded",
                "warnings": ["No OHLCV data available — technical indicators skipped"],
            },
        }
    elif tool_name == "fetch_news":
        return {
            "summary": {
                "total_articles": 5,
                "overall_sentiment": 0.2,
                "fetched_at": "2026-04-01T10:00:00",
                "errors": [],
            },
            "by_category": {},
        }
    return {}


def _mock_thai_time():
    """สร้าง mock object สำหรับ get_thai_time() return value"""
    return MagicMock(
        isoformat=lambda: "2026-04-01T10:00:00",
        strftime=lambda fmt: "20260401_100000",
    )


# ══════════════════════════════════════════════════════════════════
# 1. __init__
# ══════════════════════════════════════════════════════════════════


class TestInit:
    """ทดสอบ GoldTradingOrchestrator.__init__"""

    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_creates_output_dir(self, mock_interceptor, tmp_path):
        """สร้าง output_dir อัตโนมัติ"""
        out_dir = str(tmp_path / "my_output")
        orch = GoldTradingOrchestrator(output_dir=out_dir)
        assert os.path.isdir(out_dir)

    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_stores_config(self, mock_interceptor, tmp_path):
        """เก็บ config ไว้"""
        orch = GoldTradingOrchestrator(
            history_days=30,
            interval="1h",
            max_news_per_cat=3,
            output_dir=str(tmp_path),
        )
        assert orch.history_days == 30
        assert orch.interval == "1h"

    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_default_output_dir(self, mock_interceptor):
        """ไม่ส่ง output_dir → ใช้ ./output"""
        orch = GoldTradingOrchestrator()
        assert "output" in str(orch.output_dir)


# ══════════════════════════════════════════════════════════════════
# 2. run() — payload structure
# ══════════════════════════════════════════════════════════════════


class TestRunPayload:
    """ทดสอบ run() -> payload มี keys ครบ"""

    @patch("data_engine.orchestrator.validate_market_state", return_value=[])
    @patch("data_engine.orchestrator.call_tool", side_effect=_mock_call_tool)
    @patch("data_engine.orchestrator.get_thai_time")
    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_payload_has_all_top_keys(
        self, mock_interceptor, mock_time, mock_call, mock_validate, tmp_path
    ):
        """Payload ต้องมี meta, data_quality, data_sources, market_data, technical_indicators, news"""
        mock_time.return_value = _mock_thai_time()

        orch = GoldTradingOrchestrator(output_dir=str(tmp_path))
        payload = orch.run(save_to_file=False)

        assert "meta" in payload
        assert "data_quality" in payload
        assert "data_sources" in payload
        assert "market_data" in payload
        assert "technical_indicators" in payload
        assert "news" in payload

    @patch("data_engine.orchestrator.validate_market_state", return_value=[])
    @patch("data_engine.orchestrator.call_tool", side_effect=_mock_call_tool)
    @patch("data_engine.orchestrator.get_thai_time")
    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_meta_fields(
        self, mock_interceptor, mock_time, mock_call, mock_validate, tmp_path
    ):
        """meta ต้องมี agent, version, generated_at, history_days, interval"""
        mock_time.return_value = _mock_thai_time()

        orch = GoldTradingOrchestrator(output_dir=str(tmp_path), interval="15m")
        payload = orch.run(save_to_file=False)

        meta = payload["meta"]
        assert meta["agent"] == "gold-trading-agent"
        assert meta["interval"] == "15m"
        assert "version" in meta


# ══════════════════════════════════════════════════════════════════
# 3. run() — save_to_file
# ══════════════════════════════════════════════════════════════════


class TestRunSaveFile:
    """ทดสอบ run() -> save_to_file=True สร้างไฟล์ JSON"""

    @patch("data_engine.orchestrator.validate_market_state", return_value=[])
    @patch("data_engine.orchestrator.call_tool", side_effect=_mock_call_tool)
    @patch("data_engine.orchestrator.get_thai_time")
    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_saves_latest_json(
        self, mock_interceptor, mock_time, mock_call, mock_validate, tmp_path
    ):
        mock_time.return_value = _mock_thai_time()

        orch = GoldTradingOrchestrator(output_dir=str(tmp_path))
        orch.run(save_to_file=True)

        assert (tmp_path / "latest.json").exists()
        with open(tmp_path / "latest.json", "r") as f:
            data = json.load(f)
        assert "meta" in data


# ══════════════════════════════════════════════════════════════════
# 4. run() — history_days override
# ══════════════════════════════════════════════════════════════════


class TestHistoryDaysOverride:
    """ทดสอบ run(history_days=X) override"""

    @patch("data_engine.orchestrator.validate_market_state", return_value=[])
    @patch("data_engine.orchestrator.call_tool", side_effect=_mock_call_tool)
    @patch("data_engine.orchestrator.get_thai_time")
    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_override_history_days(
        self, mock_interceptor, mock_time, mock_call, mock_validate, tmp_path
    ):
        mock_time.return_value = _mock_thai_time()

        orch = GoldTradingOrchestrator(history_days=90, output_dir=str(tmp_path))
        orch.run(save_to_file=False, history_days=7)

        # ต้องเรียก call_tool("fetch_price") ด้วย history_days=7
        mock_call.assert_any_call("fetch_price", history_days=7, interval="5m")


# ══════════════════════════════════════════════════════════════════
# 5. run() — no OHLCV data → degraded quality
# ══════════════════════════════════════════════════════════════════


class TestNoOhlcvData:
    """ทดสอบ run() เมื่อไม่มี OHLCV data"""

    @patch("data_engine.orchestrator.validate_market_state", return_value=[])
    @patch("data_engine.orchestrator.call_tool", side_effect=_mock_call_tool_no_ohlcv)
    @patch("data_engine.orchestrator.get_thai_time")
    @patch("data_engine.orchestrator.start_interceptor_background")
    def test_degraded_quality(
        self, mock_interceptor, mock_time, mock_call, mock_validate, tmp_path
    ):
        mock_time.return_value = _mock_thai_time()

        orch = GoldTradingOrchestrator(output_dir=str(tmp_path))
        payload = orch.run(save_to_file=False)

        assert payload["data_quality"]["quality_score"] == "degraded"
        assert any("No OHLCV" in w for w in payload["data_quality"]["warnings"])
