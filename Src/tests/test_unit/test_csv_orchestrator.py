"""
test_csv_orchestrator.py — Tests สำหรับ CSVOrchestrator

ครอบคลุม:
  1. __init__ gold_csv ไม่พบ         — raise RuntimeError
  2. __init__ gold_csv โหลดสำเร็จ   — _gold_df ไม่เป็น None
  3. external_csv optional           — ไม่มีไฟล์ → ไม่ crash
  4. news_csv optional               — ไม่มีไฟล์ → ไม่ crash
  5. run() payload structure         — มี keys มาตรฐาน
  6. run() thai_gold_thb              — sell < buy (bid/ask structure)
  7. run() recent_price_action        — มี 5 candles หรือน้อยกว่า
  8. run() no data in history_days    — raise ValueError
  9. run() save_to_file=True          — เขียนไฟล์
  10. external_csv alias columns      — usd_thb_rate, gold_spot_usd normalize

Strategy: สร้าง CSV จริงใน tmp directory — ไม่ใช้ mock file
"""

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest.engine.csv_orchestrator import CSVOrchestrator


# ══════════════════════════════════════════════════════════════════
# Helpers — สร้าง CSV จริงใน temp directory
# ══════════════════════════════════════════════════════════════════


def _make_gold_csv(path: str, rows: int = 500) -> None:
    """สร้าง Gold OHLCV CSV ตาม format ที่ load_gold_csv ต้องการ
    ใช้ 500 rows และ varying prices เพราะ:
    - drop_warmup=True ตัดแถวแรก ~40 rows (MACD slow + signal warmup)
    - Constant prices ทำให้ indicators เป็น NaN → rows ถูกตัดหมด
    """
    np.random.seed(42)
    dates = pd.date_range("2026-01-01 06:15", periods=rows, freq="1h")
    close = 45000 + np.cumsum(np.random.randn(rows) * 100)
    df = pd.DataFrame({
        "Datetime": dates.strftime("%Y-%m-%d %H:%M:%S"),
        "Open":   close - 50,
        "High":   close + 100,
        "Low":    close - 100,
        "Close":  close,
        "Volume": [1000] * rows,
    })
    df.to_csv(path, index=False)


def _make_external_csv(path: str, rows: int = 50) -> None:
    """สร้าง external CSV สำหรับ spot USD + forex"""
    dates = pd.date_range("2026-01-01 06:00", periods=rows, freq="8h")
    df = pd.DataFrame({
        "timestamp":       dates.strftime("%Y-%m-%d %H:%M:%S"),
        "gold_spot_usd":   [2350.0 + i for i in range(rows)],
        "usd_thb_rate":    [34.5] * rows,
    })
    df.to_csv(path, index=False)


def _make_news_csv(path: str, rows: int = 5) -> None:
    """สร้าง news CSV"""
    dates = pd.date_range("2026-01-01 06:00", periods=rows, freq="6h")
    df = pd.DataFrame({
        "timestamp":              dates.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_sentiment":      [0.3, -0.1, 0.5, 0.2, -0.2],
        "news_count":             [5, 3, 7, 4, 2],
        "top_headlines_summary":  ["Gold rises", "Market dips", "Rally", "Steady", "Fall"],
    })
    df.to_csv(path, index=False)


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def gold_csv(tmp_dir):
    path = os.path.join(tmp_dir, "gold.csv")
    _make_gold_csv(path, rows=50)
    return path


@pytest.fixture
def ext_csv(tmp_dir):
    path = os.path.join(tmp_dir, "external.csv")
    _make_external_csv(path)
    return path


@pytest.fixture
def news_csv(tmp_dir):
    path = os.path.join(tmp_dir, "news.csv")
    _make_news_csv(path)
    return path


@pytest.fixture
def orchestrator(gold_csv, tmp_dir):
    return CSVOrchestrator(
        gold_csv=gold_csv,
        interval="1h",
        output_dir=os.path.join(tmp_dir, "output"),
    )


# ══════════════════════════════════════════════════════════════════
# 1. __init__ — gold_csv ไม่พบ
# ══════════════════════════════════════════════════════════════════


class TestCSVOrchestratorInit:
    def test_missing_gold_csv_raises_runtime_error(self, tmp_dir):
        """gold_csv ไม่มีไฟล์ → RuntimeError"""
        with pytest.raises(RuntimeError, match="gold_csv"):
            CSVOrchestrator(
                gold_csv="/nonexistent/path/file.csv",
                output_dir=os.path.join(tmp_dir, "out"),
            )

    def test_gold_csv_loaded_on_init(self, orchestrator):
        """gold_csv โหลดสำเร็จ → _gold_df ไม่เป็น None"""
        assert orchestrator._gold_df is not None
        assert len(orchestrator._gold_df) > 0

    def test_external_csv_not_required(self, gold_csv, tmp_dir):
        """ไม่ส่ง external_csv → ไม่ crash"""
        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            output_dir=os.path.join(tmp_dir, "out"),
        )
        assert orch._ext_df is None

    def test_news_csv_not_required(self, gold_csv, tmp_dir):
        """ไม่ส่ง news_csv → ไม่ crash"""
        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            output_dir=os.path.join(tmp_dir, "out"),
        )
        assert orch._news_df is None

    def test_external_csv_loaded_when_exists(self, gold_csv, ext_csv, tmp_dir):
        """external_csv มีไฟล์ → _ext_df ไม่เป็น None"""
        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            external_csv=ext_csv,
            output_dir=os.path.join(tmp_dir, "out"),
        )
        assert orch._ext_df is not None

    def test_news_csv_loaded_when_exists(self, gold_csv, news_csv, tmp_dir):
        """news_csv มีไฟล์ → _news_df ไม่เป็น None"""
        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            news_csv=news_csv,
            output_dir=os.path.join(tmp_dir, "out"),
        )
        assert orch._news_df is not None

    def test_nonexistent_external_csv_no_crash(self, gold_csv, tmp_dir):
        """external_csv ชี้ไปที่ไฟล์ที่ไม่มี → ไม่ crash (optional)"""
        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            external_csv="/nonexistent/ext.csv",
            output_dir=os.path.join(tmp_dir, "out"),
        )
        assert orch._ext_df is None

    def test_output_dir_created(self, gold_csv, tmp_dir):
        """output_dir ที่ยังไม่มี → สร้างให้อัตโนมัติ"""
        out_dir = os.path.join(tmp_dir, "new_output_dir")
        assert not os.path.exists(out_dir)
        CSVOrchestrator(gold_csv=gold_csv, output_dir=out_dir)
        assert os.path.exists(out_dir)


# ══════════════════════════════════════════════════════════════════
# 2. run() payload structure
# ══════════════════════════════════════════════════════════════════


class TestRunPayloadStructure:
    def test_run_returns_dict(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert isinstance(payload, dict)

    def test_run_has_meta_key(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert "meta" in payload

    def test_run_has_market_data_key(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert "market_data" in payload

    def test_run_has_technical_indicators_key(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert "technical_indicators" in payload

    def test_run_has_data_quality_key(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert "data_quality" in payload

    def test_run_has_news_key(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert "news" in payload

    def test_meta_data_mode_is_csv(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert payload["meta"]["data_mode"] == "csv"

    def test_meta_interval_matches_init(self, gold_csv, tmp_dir):
        orch = CSVOrchestrator(gold_csv=gold_csv, interval="5m", output_dir=os.path.join(tmp_dir, "out"))
        payload = orch.run(history_days=30)
        assert payload["meta"]["interval"] == "5m"


# ══════════════════════════════════════════════════════════════════
# 3. thai_gold_thb bid/ask structure
# ══════════════════════════════════════════════════════════════════


class TestThaiGoldThb:
    def test_sell_price_less_than_buy_price(self, orchestrator):
        """sell_price_thb < buy_price_thb (bid < ask)"""
        payload = orchestrator.run(history_days=30)
        thai = payload["market_data"]["thai_gold_thb"]
        assert thai["sell_price_thb"] < thai["buy_price_thb"]

    def test_spread_is_200_thb(self, orchestrator):
        """spread = ask - bid = 200 THB"""
        payload = orchestrator.run(history_days=30)
        thai = payload["market_data"]["thai_gold_thb"]
        spread = thai["buy_price_thb"] - thai["sell_price_thb"]
        assert spread == pytest.approx(200.0)

    def test_source_is_csv_hsh(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert payload["market_data"]["thai_gold_thb"]["source"] == "csv_hsh"

    def test_timestamp_present(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        assert payload["market_data"]["thai_gold_thb"]["timestamp"] != ""


# ══════════════════════════════════════════════════════════════════
# 4. recent_price_action
# ══════════════════════════════════════════════════════════════════


class TestRecentPriceAction:
    def test_recent_price_action_has_candles(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        rpa = payload["market_data"]["recent_price_action"]
        assert len(rpa) > 0

    def test_recent_price_action_max_5_candles(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        rpa = payload["market_data"]["recent_price_action"]
        assert len(rpa) <= 5

    def test_each_candle_has_ohlcv(self, orchestrator):
        payload = orchestrator.run(history_days=30)
        for candle in payload["market_data"]["recent_price_action"]:
            for key in ["datetime", "open", "high", "low", "close", "volume"]:
                assert key in candle


# ══════════════════════════════════════════════════════════════════
# 5. run() with no data in history_days
# ══════════════════════════════════════════════════════════════════


class TestRunNoData:
    def test_too_small_history_days_raises_value_error(self, gold_csv, tmp_dir):
        """history_days ติดลบ → cutoff > max_ts → ไม่มีข้อมูล → ValueError"""
        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            output_dir=os.path.join(tmp_dir, "out"),
        )
        # history_days=-1 ทำให้ cutoff = max_ts + 1 day → ไม่มีแถวผ่าน filter
        with pytest.raises(ValueError):
            orch.run(history_days=-1)


# ══════════════════════════════════════════════════════════════════
# 6. run() save_to_file=True
# ══════════════════════════════════════════════════════════════════


class TestSaveToFile:
    def test_save_creates_latest_json(self, orchestrator, tmp_dir):
        """save_to_file=True → สร้าง latest.json"""
        out_dir = Path(tmp_dir) / "output"
        orch = CSVOrchestrator(
            gold_csv=orchestrator.gold_csv,
            output_dir=str(out_dir),
        )
        orch.run(history_days=30, save_to_file=True)
        assert (out_dir / "latest.json").exists()

    def test_saved_file_is_valid_json(self, orchestrator, tmp_dir):
        """latest.json ต้องเป็น JSON ที่ parse ได้"""
        out_dir = Path(tmp_dir) / "output"
        orch = CSVOrchestrator(
            gold_csv=orchestrator.gold_csv,
            output_dir=str(out_dir),
        )
        orch.run(history_days=30, save_to_file=True)
        with open(out_dir / "latest.json", encoding="utf-8") as f:
            data = json.load(f)
        assert "market_data" in data

    def test_no_file_when_save_false(self, orchestrator, tmp_dir):
        """save_to_file=False → ไม่สร้างไฟล์"""
        out_dir = Path(tmp_dir) / "no_save_output"
        orch = CSVOrchestrator(
            gold_csv=orchestrator.gold_csv,
            output_dir=str(out_dir),
        )
        orch.run(history_days=30, save_to_file=False)
        assert not (out_dir / "latest.json").exists()


# ══════════════════════════════════════════════════════════════════
# 7. external CSV alias columns
# ══════════════════════════════════════════════════════════════════


class TestExternalCSVAliases:
    def test_alias_xau_usd_normalized_to_gold_spot_usd(self, gold_csv, tmp_dir):
        """column 'xau_usd' ใน external CSV → normalize เป็น 'gold_spot_usd'"""
        ext_path = os.path.join(tmp_dir, "ext_alias.csv")
        dates = pd.date_range("2026-04-01", periods=5, freq="1h")
        pd.DataFrame({
            "timestamp": dates.strftime("%Y-%m-%d %H:%M:%S"),
            "xau_usd":   [2350.0] * 5,
            "usd_thb":   [34.5] * 5,
        }).to_csv(ext_path, index=False)

        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            external_csv=ext_path,
            output_dir=os.path.join(tmp_dir, "out"),
        )
        # column ต้องถูก normalize
        assert "gold_spot_usd" in orch._ext_df.columns

    def test_usdthb_alias_normalized(self, gold_csv, tmp_dir):
        """column 'usdthb' → normalize เป็น 'usd_thb_rate'"""
        ext_path = os.path.join(tmp_dir, "ext_alias2.csv")
        dates = pd.date_range("2026-04-01", periods=5, freq="1h")
        pd.DataFrame({
            "timestamp": dates.strftime("%Y-%m-%d %H:%M:%S"),
            "gold_spot_usd": [2350.0] * 5,
            "usdthb": [34.5] * 5,
        }).to_csv(ext_path, index=False)

        orch = CSVOrchestrator(
            gold_csv=gold_csv,
            external_csv=ext_path,
            output_dir=os.path.join(tmp_dir, "out"),
        )
        assert "usd_thb_rate" in orch._ext_df.columns
