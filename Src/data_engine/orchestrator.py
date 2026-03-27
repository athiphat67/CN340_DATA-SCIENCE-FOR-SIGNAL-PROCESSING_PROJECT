"""
orchestrator.py — Gold Trading Agent · Phase 1 (Deterministic)
รวมข้อมูลจาก fetcher.py + indicators.py + newsfetcher.py
แล้ว output เป็น JSON สำหรับส่งให้ LLM Agent
"""

import json
import os 
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fetcher     import GoldDataFetcher
from indicators  import TechnicalIndicators
from newsfetcher import GoldNewsFetcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class GoldTradingOrchestrator:
    """รวม Fetcher + Indicators + NewsFetcher แล้วสร้าง JSON Payload สำหรับ LLM Agent"""

    def __init__(
        self,
        history_days:     int = 90,
        interval:         str = "1d",  # <--- เพิ่มพารามิเตอร์ Timeframe ตรงนี้
        max_news_per_cat: int = 5,
        output_dir:       Optional[str] = None,
    ):
        self.price_fetcher = GoldDataFetcher()
        self.news_fetcher  = GoldNewsFetcher(max_per_category=max_news_per_cat)
        self.history_days  = history_days
        self.interval      = interval  # <--- เก็บค่าไว้ใช้
        self.output_dir    = Path(output_dir) if output_dir else Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # 🆕 NEW: Calculate Sampling Parameters
    # --------------------------------------------------------
    def _calculate_sampling_params(self, indicators_dict: dict) -> dict:
        """
        คำนวณ Temperature (τ) และ Top-p สำหรับ Nucleus Sampling
        
        ตามหลักการ:
        - ความผันผวนสูง → τ สูง (sampling โปรแกรมกว่า)
        - ความผันผวนต่ำ → τ ต่ำ (greedy, deterministic)
        """
        volatility = indicators_dict.get("volatility", 0.15)
        
        # Temperature scaling: ยิ่ง volatile มากยิ่ง τ สูง
        # τ = 0.5 (ต่ำ) → 2.0 (สูง)
        temperature = min(2.0, 0.5 + volatility * 5)
        
        # Top-p nucleus sampling: ยิ่ง confident มากยิ่ง p ต่ำ
        if volatility < 0.10:
            top_p = 0.1  # Very confident, very greedy
        elif volatility < 0.20:
            top_p = 0.3  # Normal volatility
        else:
            top_p = 0.5  # High volatility, more exploratory

    def run(self, save_to_file: bool = True) -> dict:
        logger.info(f"═══ Orchestrator — Building LLM Payload ({self.interval} Timeframe) ═══")

        # ── Step 1: ราคาทองและ OHLCV ──────────────────────────────────────────
        logger.info(f"Step 1: Fetching price data (Interval: {self.interval})...")
        raw = self.price_fetcher.fetch_all(
            include_news = False,
            history_days = self.history_days,
            interval     = self.interval,  # <--- ส่งค่าต่อไปให้ fetcher
        )
        spot_data  = raw.get("spot_price", {})
        forex_data = raw.get("forex", {})
        thai_gold  = raw.get("thai_gold", {})
        ohlcv_df   = raw.get("ohlcv_df")

        # ── Step 2: Technical Indicators ──────────────────────────────────────
        indicators_dict = {}
        if ohlcv_df is not None and not ohlcv_df.empty:
            logger.info(f"Step 2: Computing indicators on {len(ohlcv_df)} candles...")
            try:
                calc = TechnicalIndicators(ohlcv_df)
                indicators_dict = calc.to_dict()
            except Exception as e:
                logger.error(f"Indicator calculation failed: {e}")
        else:
            logger.warning("Step 2: No OHLCV data — skipping indicators")

        # ── Step 3: ข่าวสาร (yfinance) ────────────────────────────────────────
        logger.info("Step 3: Fetching news via yfinance...")
        news_data = self.news_fetcher.to_dict()

        # ── Step 4: Assemble JSON Payload ──────────────────────────────────────
        payload = {
            "meta": {
                "agent":          "gold-trading-agent",
                "version":        "1.1.0",
                "generated_at":   datetime.utcnow().isoformat() + "Z",
                "history_days":   self.history_days,
                "interval":       self.interval,  # <--- บันทึก Timeframe ลงใน JSON
            },
            "market_data": {
                "spot_price_usd": spot_data,
                "forex":          forex_data,
                "thai_gold_thb":  thai_gold,
            },
            "technical_indicators": indicators_dict,
            "news": {
                "summary": {
                    "total_articles": news_data.get("total_articles", 0),
                    "fetched_at":     news_data.get("fetched_at", ""),
                    "errors":         news_data.get("errors", []),
                },
                "by_category": news_data.get("by_category", {}),
            },
        }

        # ──── New Step: Calculate Sampling Parameters ─────────────────────────
        logger.info("Step 3.5: Computing sampling parameters...")
        sampling_params = self._calculate_sampling_params(indicators_dict)

        # ── Step 5: Save JSON ─────────────────────────────────────────────────
        if save_to_file:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            for fp in [
                self.output_dir / f"payload_{timestamp}.json",
                self.output_dir / "latest.json",
            ]:
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
                logger.info(f"Saved: {fp}")

        logger.info(f"═══ Payload ready — {news_data.get('total_articles', 0)} news articles ═══")
        return payload

# ─── CLI ─────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Gold Orchestrator — JSON payload for LLM")
    parser.add_argument("--history",    type=int, default=90, help="ย้อนหลังกี่วัน")
    parser.add_argument("--interval",   type=str, default="1d", help="Timeframe (1m, 5m, 15m, 1h, 1d)")
    parser.add_argument("--max-news",   type=int, default=5,  help="ข่าวสูงสุดต่อ category")
    parser.add_argument("--no-save",    action="store_true")
    args = parser.parse_args()

    # ระบุ Path เป้าหมายไปที่ Src/agent_core/data แบบ Absolute Path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_output_dir = os.path.join(current_dir, "..", "agent_core", "data")

    orchestrator = GoldTradingOrchestrator(
        history_days     = args.history,
        interval         = args.interval,
        max_news_per_cat = args.max_news,
        output_dir       = target_output_dir, # ใช้ Path ที่คำนวณไว้
    )

    payload = orchestrator.run(save_to_file=not args.no_save)
    # print(json.dumps(payload, indent=2, ensure_ascii=False, default=str)) # ปิด print ไว้จะได้ไม่รก Terminal

if __name__ == "__main__":
    main()