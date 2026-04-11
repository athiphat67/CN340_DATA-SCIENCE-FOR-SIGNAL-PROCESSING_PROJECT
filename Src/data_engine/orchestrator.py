"""
orchestrator.py — Gold Trading Agent · Phase 1 (Deterministic)
รวมข้อมูลจาก fetcher.py + indicators.py + newsfetcher.py
แล้ว output เป็น JSON สำหรับส่งให้ LLM Agent
"""

import json
import os
import argparse
import logging
import threading # <--- เพิ่มสำหรับจัดการ Background Thread
import time      # <--- เพิ่มสำหรับการหน่วงเวลาใน Thread
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional
import subprocess
import time
import signal

from data_engine.fetcher import GoldDataFetcher
from data_engine.indicators import TechnicalIndicators
from data_engine.newsfetcher import GoldNewsFetcher
from data_engine.thailand_timestamp import get_thai_time, convert_index_to_thai_tz

# ─── นำเข้าไฟล์ Interceptor ของเรา ───────────────────────────────────────────
from data_engine.gold_interceptor_lite import start_interceptor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)
        # ฟังก์ชันสำหรับเริ่มรันบอท Interceptor เบื้องหลัง
def start_data_engine():
    bot_script = os.path.join("interceptor_xauthb_fetch", "gold_interceptor.py")
    process = subprocess.Popen(
        ["python", bot_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    print(f"🚀 Data Engine started (PID: {process.pid})")
    
    # รอ 10 วินาทีเพื่อให้บอทต่อ WebSocket และเริ่มจดราคาลง CSV บรรทัดแรก
    print("⏳ Waiting 10s for initial data stream...")
    time.sleep(10)
    return process

<<<<<<< HEAD
# ฟังก์ชันสำหรับปิดบอทเมื่อจบงาน
def stop_data_engine(process):
    if process:
        print("🛑 Shutting down Data Engine...")
        process.terminate() # ส่งสัญญาณปิดโปรแกรม
        process.wait()      # รอจนกว่าจะคืน Memory ครบ
        print("✅ Data Engine stopped.")
=======
# ─── ส่วนจัดการ Background Thread (ป้องกันการรันซ้ำ) ───────────────────────
_interceptor_thread_started = False
_interceptor_lock = threading.Lock()

def _run_interceptor_forever():
    """ฟังก์ชันทำงานเบื้องหลัง: ดึงราคาทองค้างไว้ตลอดเวลา"""
    logger.info("🚀 [Background Thread] เริ่มรันท่อ WebSocket (gold_interceptor_lite)...")
    while True:
        try:
            start_interceptor()
        except Exception as e:
            logger.error(f"❌ [Background Thread] WebSocket หลุดหรือมีปัญหา: {e}")
        
        logger.info("🔄 [Background Thread] จะพยายามเชื่อมต่อใหม่ใน 5 วินาที...")
        time.sleep(5)

def _start_interceptor_background():
    """ฟังก์ชันเช็คและเปิด Thread แค่ครั้งเดียวต่อการรัน 1 โปรเซส"""
    global _interceptor_thread_started
    with _interceptor_lock:
        if not _interceptor_thread_started:
            # daemon=True เพื่อให้ Thread นี้ปิดตัวเองอัตโนมัติถ้าโปรแกรมหลักทำงานเสร็จ/ถูกปิด
            t = threading.Thread(target=_run_interceptor_forever, daemon=True)
            t.start()
            _interceptor_thread_started = True
# ────────────────────────────────────────────────────────────────────────
# athiphat-edit

def validate_market_state(state: dict) -> list[str]:
    """คืน list ของ missing fields เพื่อตรวจสอบ Schema ให้ตรงกันทั้งโปรเจกต์"""
    required = [
        "market_data.thai_gold_thb.sell_price_thb",
        "market_data.thai_gold_thb.buy_price_thb",
        "technical_indicators.rsi.value",
    ]
    errors = []
    for path in required:
        parts = path.split(".")
        obj = state
        for p in parts:
            if not isinstance(obj, dict) or p not in obj:
                errors.append(f"Missing: {path}")
                break
            obj = obj[p]
    return errors

# ────────────────────────────────────────────────────────────────────────

>>>>>>> c0fe0af2395c9b7211f71e58f1c7238a3f7e8bad

class GoldTradingOrchestrator:
    """รวม Fetcher + Indicators + NewsFetcher แล้วสร้าง JSON Payload สำหรับ LLM Agent"""

    def __init__(
        self,
        history_days: int = 90,
        interval: str = "5m",  # <--- เพิ่มพารามิเตอร์ Timeframe ตรงนี้
        max_news_per_cat: int = 5,
        output_dir: Optional[str] = None,
    ):
        # 🟢 ทริกเกอร์ WebSocket ให้รันทันทีที่มีการเรียกใช้คลาสนี้ (และจะรันแค่ครั้งเดียว)
        _start_interceptor_background()

        self.price_fetcher = GoldDataFetcher()
        self.news_fetcher = GoldNewsFetcher(max_per_category=max_news_per_cat)
        self.history_days = history_days
        self.interval = interval  # <--- เก็บค่าไว้ใช้
        self.output_dir = Path(output_dir) if output_dir else Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self, save_to_file: bool = True, history_days: int = None) -> dict:
        bot_process = None
        try:
            # 1. เปิดบอทก่อนเริ่มดึงข้อมูล
            bot_process = start_data_engine()

            # 2. ทำงาน Fetch ข้อมูลตามปกติ (ตอนนี้จะอ่านจาก CSV ได้ทันที)
            # logger.info("═══ Orchestrator — Building LLM Payload ═══")
            # raw = self.price_fetcher.fetch_all(
            #     history_days=history_days or self.history_days,
            #     interval=self.interval,
            # )
            # ถ้าส่ง history_days มาตอนเรียก run() ให้ใช้ค่านั้น มิฉะนั้นใช้ค่าจาก __init__
            effective_history_days = (
                history_days if history_days is not None else self.history_days
            )

            logger.info(
                f"═══ Orchestrator — Building LLM Payload ({self.interval} Timeframe) ═══"
            )

            # ── Step 1: ราคาทองและ OHLCV ──────────────────────────────────────────
            logger.info(
                f"Step 1: Fetching price data (Interval: {self.interval}, History: {effective_history_days}d)..."
            )
            raw = self.price_fetcher.fetch_all(
                history_days=effective_history_days,
                interval=self.interval,
            )
            spot_data = raw.get("spot_price", {})
            forex_data = raw.get("forex", {})
            thai_gold = raw.get("thai_gold", {})
            ohlcv_df = raw.get("ohlcv_df")

            # ── Step 2: Technical Indicators ──────────────────────────────────────
            indicators_dict = {}
            # ตั้งค่า Default กันเหนียวไว้ก่อน
            data_quality_dict = {
                "quality_score": "good",
                "is_weekend": get_thai_time().weekday() >= 5, # 5=Sat, 6=Sun
                "llm_instruction": "Use standard technical analysis.",
                "warnings": []
            }

            if ohlcv_df is not None and not ohlcv_df.empty:
                logger.info(f"Step 2: Computing indicators on {len(ohlcv_df)} candles...")
                try:
                    calc = TechnicalIndicators(ohlcv_df)
                    # ส่ง interval เข้าไปตามที่เราแก้ไว้ใน indicators.py
                    indicators_dict = calc.to_dict(interval=self.interval)
                    
                    # ดึง data_quality ออกมาจาก indicators_dict (ถ้ามี)
                    if "data_quality" in indicators_dict:
                        dq = indicators_dict.pop("data_quality")
                        data_quality_dict["warnings"].extend(dq.get("warnings", []))
                        data_quality_dict["quality_score"] = dq.get("quality_score", "good")
                        
                    # เพิ่ม Warning ถ้าเป็นวันหยุด
                    if data_quality_dict["is_weekend"]:
                        data_quality_dict["warnings"].append("Market is closed (Weekend) - Price data might be stale.")
                        data_quality_dict["llm_instruction"] = "Market is closed. Weigh news sentiment higher than short-term indicators."

                except Exception as e:
                    logger.error(f"Indicator calculation failed: {e}")
                    data_quality_dict["quality_score"] = "degraded"
                    data_quality_dict["warnings"].append(f"Indicator calc error: {e}")
            else:
                logger.warning("Step 2: No OHLCV data — skipping indicators")
                data_quality_dict["quality_score"] = "degraded"
                data_quality_dict["warnings"].append("No OHLCV data available.")

            # STEP 2.5 ดึงข้อมูล 5 แท่งล่าสุด
            recent_price_action = []
            if ohlcv_df is not None and not ohlcv_df.empty:
                recent_candles = ohlcv_df.tail(5).copy()
                if len(recent_candles) < 5:
                    logger.warning(f"⚠️ Only {len(recent_candles)} recent candles available (expected 5)")
                
                # เรียกใช้ฟังก์ชันแปลงเวลาจากไฟล์ของเรา
                recent_candles.index = convert_index_to_thai_tz(recent_candles.index)
                # ดึง 5 แถวสุดท้ายจาก DataFrame
                for idx, row in recent_candles.iterrows():
                    recent_price_action.append({
                        "datetime": idx.isoformat(), # ตัด Timezone รกๆ ออก
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0
                    })
            # -----------------------------------------------------------------------------

            # ── Step 3: ข่าวสาร (yfinance) ────────────────────────────────────────
            logger.info("Step 3: Fetching news via NewsFetcher (FinBERT + RSS)...")
            news_data = self.news_fetcher.to_dict()

            # ── Step 4: Assemble JSON Payload ──────────────────────────────────────
            payload = {
                "meta": {
                    "agent": "gold-trading-agent",
                    "version": "1.1.0",
                    "generated_at": get_thai_time().isoformat(),
                    "history_days": self.history_days,
                    "interval": self.interval,
                },
<<<<<<< HEAD
                "data_quality": data_quality_dict,  # <--- โผล่มาตรงนี้แล้วครับ
                "data_sources": {
                    "price": spot_data.get("source"),
                    "forex": forex_data.get("source"),
                    "thai_gold": thai_gold.get("source"),
                    "news": "newsfetcher",
                },
                "market_data": {
                    "spot_price_usd": spot_data,
                    "forex": forex_data,
                    "thai_gold_thb": thai_gold,
                    # นำ data 5 แท่งล่าสุดมาใส่
                    "recent_price_action": recent_price_action,
                },
                "technical_indicators": indicators_dict,
                "news": {
                    "summary": {
                        "total_articles": news_data.get("total_articles", 0),
                        "token_estimate": news_data.get("token_estimate", 0),
                        "overall_sentiment": news_data.get("overall_sentiment", 0.0),
                        "fetched_at": news_data.get("fetched_at", ""),
                        "errors": news_data.get("errors", []),
                    },
                    "by_category": news_data.get("by_category", {}),
                },
            }
=======
                "by_category": news_data.get("by_category", {}),
            },
        }
        
        # ── Step 4.5: Validate Payload Schema ( athiphat dev) ─────────────────────────────────
        schema_errors = validate_market_state(payload)
        if schema_errors:
            logger.error(f"🚨 Payload Schema Validation Failed: {schema_errors}")
>>>>>>> c0fe0af2395c9b7211f71e58f1c7238a3f7e8bad

            # ── Step 5: Save JSON ─────────────────────────────────────────────────
            if save_to_file:
                timestamp = get_thai_time().strftime("%Y%m%d_%H%M%S")
                for fp in [
                    self.output_dir / f"payload_{timestamp}.json",
                    self.output_dir / "latest.json",
                ]:
                    with open(fp, "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
                    logger.info(f"Saved: {fp}")

            logger.info(
                f"═══ Payload ready — {news_data.get('total_articles', 0)} news articles ═══"
            )
            return payload
    
        finally:
            # 3. ไม่ว่างานจะสำเร็จหรือ Error ต้องสั่งปิดบอทเสมอเพื่อไม่ให้ค้างใน RAM
            if bot_process:
                stop_data_engine(bot_process)


# ─── CLI ─────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Gold Orchestrator — JSON payload for LLM"
    )
    parser.add_argument("--history", type=int, default=30, help="ย้อนหลังกี่วัน")
    parser.add_argument(
        "--interval", type=str, default="5m", help="Timeframe (1m, 5m, 15m, 1h, 1d)"
    )
    parser.add_argument("--max-news", type=int, default=5, help="ข่าวสูงสุดต่อ category")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    # ระบุ Path เป้าหมายไปที่ Src/agent_core/data แบบ Absolute Path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_output_dir = os.path.join(current_dir, "..", "agent_core", "data")

    orchestrator = GoldTradingOrchestrator(
        history_days=args.history,
        interval=args.interval,
        max_news_per_cat=args.max_news,
        output_dir=target_output_dir,  # ใช้ Path ที่คำนวณไว้
    )

    payload = orchestrator.run(save_to_file=not args.no_save)
    # print(json.dumps(payload, indent=2, ensure_ascii=False, default=str)) # ปิด print ไว้จะได้ไม่รก Terminal

    # --- ส่วนป้องกันการจบการทำงานของโปรแกรมหลัก (เฉพาะตอนเรียกแบบ CLI) ---
    # เนื่องจาก Thread เป็นแบบ daemon ถ้า function main() จบ โปรแกรมจะปิดทันที
    # เราจึงพักลูปไว้เพื่อให้ท่อ WebSocket ทำงานต่อไปได้
    logger.info("🟢 [CLI Mode] รันคำสั่งเสร็จแล้ว กำลังเปิดท่อข้อมูลทิ้งไว้ กด Ctrl+C เพื่อออก...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🔴 ปิดการทำงาน")

if __name__ == "__main__":
    main()