"""
backtest/logger.py
บันทึกผล backtest ลง JSON log file เพื่อเปรียบเทียบแต่ละโมเดล
"""

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")


class BacktestLogger:
    """
    เก็บ log ผล backtest แต่ละครั้งลง JSON
    โครงสร้าง:
        backtest/logs/
        ├── backtest_log.json          ← master log (สรุปทุกรอบ)
        └── detail/
            └── {model}_{timestamp}.json  ← รายละเอียดแต่ละรอบ
    """

    def __init__(self, log_dir: str = DEFAULT_LOG_DIR):
        self.log_dir = log_dir
        self.detail_dir = os.path.join(log_dir, "detail")
        os.makedirs(self.detail_dir, exist_ok=True)
        self.master_log_path = os.path.join(log_dir, "backtest_log.json")

    def save(self, summary: dict) -> str:
        """
        บันทึกผล backtest 1 รอบ

        Parameters
        ----------
        summary : dict
            ผลจาก BacktestSummary (as dict)

        Returns
        -------
        str : path ของ detail file ที่บันทึก
        """
        model_name = summary.get("model_name", "unknown")
        timestamp = summary.get("run_timestamp", datetime.now().isoformat())
        safe_ts = timestamp.replace(":", "-").replace(".", "-")

        # ─── 1. Save detail file (full trades) ─────────────────────────
        detail_filename = f"{model_name}_{safe_ts}.json"
        detail_path = os.path.join(self.detail_dir, detail_filename)
        with open(detail_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        logger.info(f"Detail log saved: {detail_path}")

        # ─── 2. Append to master log (summary only, no trades) ─────────
        master_entry = {k: v for k, v in summary.items() if k != "trades"}
        master_entry["detail_file"] = detail_filename

        master_data = self._load_master_log()
        master_data.append(master_entry)

        with open(self.master_log_path, "w", encoding="utf-8") as f:
            json.dump(master_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Master log updated: {self.master_log_path}")

        return detail_path

    def _load_master_log(self) -> list:
        """โหลด master log ที่มีอยู่ หรือสร้างใหม่"""
        if os.path.exists(self.master_log_path):
            try:
                with open(self.master_log_path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Master log corrupted, creating new one")
                return []
        return []

    def get_comparison_table(self) -> list[dict]:
        """
        ดึงข้อมูลสรุปทุกรอบเพื่อเปรียบเทียบ

        Returns
        -------
        list[dict] : แต่ละ entry = 1 backtest run
        """
        return self._load_master_log()

    def print_comparison(self) -> None:
        """พิมพ์ตารางเปรียบเทียบผล backtest ทุกรอบ"""
        data = self.get_comparison_table()
        if not data:
            print("No backtest logs found.")
            return

        header = (
            f"{'Model':<20} {'Signals':>8} {'Trades':>7} {'WinRate':>8} "
            f"{'AvgRR':>6} {'PnL(pts)':>10} {'MaxDD':>8} "
            f"{'Sharpe':>8} {'Sortino':>8} {'Timestamp':<22}"
        )
        print("\n" + "=" * len(header))
        print("  BACKTEST COMPARISON LOG")
        print("=" * len(header))
        print(header)
        print("-" * len(header))

        for entry in data:
            print(
                f"{entry.get('model_name', '?'):<20} "
                f"{entry.get('total_signals', 0):>8} "
                f"{entry.get('total_trades', 0):>7} "
                f"{entry.get('win_rate', 0):>7.1f}% "
                f"{entry.get('avg_rr', 0):>6.2f} "
                f"{entry.get('total_pnl_pts', 0):>10.2f} "
                f"{entry.get('max_drawdown', 0):>8.2f} "
                f"{entry.get('sharpe_ratio', 0):>8.4f} "
                f"{entry.get('sortino_ratio', 0):>8.4f} "
                f"{entry.get('run_timestamp', ''):<22}"
            )
        print("=" * len(header) + "\n")
