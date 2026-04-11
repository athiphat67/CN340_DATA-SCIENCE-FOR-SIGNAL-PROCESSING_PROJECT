"""
fetcher.py — Gold Trading Agent · Phase 1 (Deterministic)
ดึงข้อมูลราคาทองคำไทย + ข่าวสาร ผ่าน Data APIs พร้อมรองรับ Timeframe ย่อย
"""

# Standard library
import logging
import os
import random
import statistics
from typing import Optional
from data_engine.ohlcv_fetcher import OHLCVFetcher
from data_engine.thailand_timestamp import get_thai_time

# Third-party libraries
import pandas as pd
import requests
import json
from dotenv import load_dotenv

# โหลดตัวแปรจากไฟล์ .env เข้าสู่ระบบ Environment ของ Python
load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
GOLD_API_URL = "https://api.gold-api.com/price/XAU"
FOREX_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"

TROY_OUNCE_IN_GRAMS = 31.1034768
THAI_GOLD_BAHT_IN_GRAMS = 15.244
THAI_GOLD_PURITY = 0.965

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

class GoldDataFetcher:
    def __init__(self, news_api_key: Optional[str] = None):
        self.news_api_key = news_api_key
        self.session = requests.Session()
        self.ohlcv_fetcher = OHLCVFetcher(session=self.session)

    # fetch gold price XAUUSD
    def fetch_gold_spot_usd(self) -> dict:
        prices = {}

        # twelvedata fetch
        try:
            api_key = os.getenv("TWELVEDATA_API_KEY")
            url = f"https://api.twelvedata.com/price?symbol=XAU/USD&apikey={api_key}"

            resp = self.session.get(url, timeout=5)
            resp.raise_for_status()
            price = float(resp.json().get("price", 0))

            if price > 0:
                prices["twelvedata"] = price

        except Exception as e:
            logger.warning(f"twelvedata failed: {e}")

        # yfinance - validator
        try:
            import yfinance as yf
            df = yf.Ticker("GC=F").history(period="1d")

            if not df.empty:
                price = float(df["Close"].iloc[-1])
                prices["yfinance"] = price

        except Exception as e:
            logger.warning(f"yfinance failed: {e}")

        # gold-api
        try:
            self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
            resp = self.session.get(GOLD_API_URL, timeout=5)
            resp.raise_for_status()
            price = float(resp.json().get("price", 0))

            if price > 0:
                prices["gold-api"] = price

        except Exception as e:
            logger.warning(f"gold-api failed: {e}")

        if not prices:
            return {}

        confidence = self.compute_confidence(prices)

        if len(prices) == 1:
            source, price = next(iter(prices.items()))
            return {
                "source": source,
                "price_usd_per_oz": price,
                "timestamp": get_thai_time().isoformat(),
                "confidence": confidence,
            }
            
        median_price = statistics.median(prices.values())
        MAX_DEVIATION = 0.005
        valid_prices = {}

        for source, price in prices.items():
            if median_price > 0:
                diff = abs(price - median_price) / median_price
                if diff <= MAX_DEVIATION:
                    valid_prices[source] = price

        if not valid_prices:
            logger.error("🚨 ข้อมูลราคาทองขัดแย้งกันอย่างรุนแรง (Deviation เกินลิมิต)")
            best_source = "yfinance" if "yfinance" in prices else next(iter(prices.keys()))
            final_price = prices[best_source]
            confidence = 0.0 
        else:
            if "twelvedata" in valid_prices:
                best_source, final_price = "twelvedata", valid_prices["twelvedata"]
            elif "gold-api" in valid_prices:
                best_source, final_price = "gold-api", valid_prices["gold-api"]
            else:
                best_source, final_price = "yfinance", valid_prices["yfinance"]

        return {
            "source": best_source,
            "price_usd_per_oz": final_price,
            "timestamp": get_thai_time().isoformat(),
            "confidence": confidence,
        }

    def compute_confidence(self, prices: dict) -> float:
        if len(prices) == 0: return 0.0
        if len(prices) == 1: return 0.6
        values = list(prices.values())
        median_val = statistics.median(values)
        if median_val == 0: return 0.0
        max_diff = max(abs(p - median_val) / median_val for p in values)
        penalty = max_diff * 10
        confidence = max(0.0, 1.0 - penalty)
        return round(confidence, 3)

    def fetch_usd_thb_rate(self) -> dict:
        # 1. พยายามดึงเรทจาก Intergold (Live Stream) ก่อน
        logger.info("กำลังดึงเรท USD/THB จาก Intergold Live Stream...")
        live_data = self.fetch_latest_from_interceptor()
        
        if live_data and "usd_thb_live" in live_data:
            logger.info(f"✅ ใช้เรท USD/THB จาก Intergold: {live_data['usd_thb_live']:.4f}")
            return {
                "source": "intergold_live_stream",
                "usd_thb": live_data["usd_thb_live"],
                "timestamp": live_data["timestamp"],
            }

        # 2. Fallback ให้กลับมาใช้ API เดิม
        logger.warning("⚠️ ไม่พบข้อมูลเรทเงินจาก Intergold — กำลังใช้ Fallback API (exchangerate-api)")
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
        try:
            resp = self.session.get(FOREX_API_URL, timeout=10)
            resp.raise_for_status()
            rates = resp.json().get("rates", {})
            thb = float(rates.get("THB", 0))
            # ปิดการแสดง log เพื่อลดความซ้ำซ้อน เนื่องจากไม่ได้เป็นข้อมูลหลักอีกต่อไป
            # logger.info(f"USD/THB: {thb:.4f}") 
            return {
                "source": "exchangerate-api.com",
                "usd_thb": thb,
                "timestamp": get_thai_time().isoformat(),
            }
        except Exception as e:
            logger.error(f"fetch_usd_thb_rate failed: {e}")
            return {}
        
    def fetch_latest_from_interceptor(self) -> dict:
        # 1. จัดการเรื่อง Path ให้ไปที่ Folder 'interceptor_xauthb_fetch'
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, "interceptor_xauthb_fetch", "gold_prices_dataset.csv")
        
        if not os.path.exists(csv_path):
            # ลองหาแบบ Relative Path เผื่อไว้กรณีรันจากตำแหน่งที่ต่างกัน
            csv_path = os.path.join("interceptor_xauthb_fetch", "gold_prices_dataset.csv")
            if not os.path.exists(csv_path):
                logger.warning(f"File {csv_path} not found.")
                return {}

        try:
            # 2. อ่านไฟล์โดยระบุ Path ที่เราคำนวณไว้ด้านบน (เดิมคุณเขียน "gold_prices_dataset.csv" เฉยๆ)
            df = pd.read_csv(csv_path)
            
            # 3. ✅ สำคัญมาก: เช็คว่าไฟล์ว่างหรือไม่ เพื่อป้องกัน Error 'out-of-bounds'
            if df.empty or len(df) < 1:
                logger.warning("CSV file exists but is still empty (Waiting for first data tick...)")
                return {}
            
            latest = df.iloc[-1]
            
            return {
                "source": "intergold_live_stream",
                "sell_price_thb": float(latest['ask_96']), 
                "buy_price_thb": float(latest['bid_96']),
                "gold_spot_usd": float(latest['gold_spot']),
                "usd_thb_live": float(latest['fx_usd_thb']),
                "timestamp": str(latest['timestamp'])
            }
        except Exception as e:
            logger.error(f"Error reading live gold data: {e}") 
            return {}

    def calc_thai_gold_price(
        self,
        price_usd_per_oz: float,
        usd_thb: float,
    ) -> dict:
        """
        อ่านข้อมูลราคาทองไทยจากไฟล์ JSON ที่สร้างโดย gold_interceptor_lite.py
        หากไม่มีข้อมูล จะทำการสลับไปใช้สมการคำนวณ (Fallback) อัตโนมัติ โดยใช้ usd_thb เป็นตัวแปรภายใน
        """
        json_path = "latest_gold_price.json"
        
        try:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    result_data = json.load(f)
                
                if "sell_price_thb" in result_data and "buy_price_thb" in result_data:
                    logger.info(f"Thai Gold (from JSON) — Sell: ฿{result_data['sell_price_thb']:,.0f} | Buy: ฿{result_data['buy_price_thb']:,.0f}")
                    return result_data
        except Exception as e:
            logger.error(f"❌ ระบบอ่านไฟล์ JSON ขัดข้อง: {e}")

        logger.warning("ไม่สามารถดึงข้อมูลจากไฟล์ได้ — สลับไปใช้โหมดคำนวณ (Fallback)")

        # ─── Fallback: คำนวณแบบเดิม (หากไฟล์พังหรือไม่อัปเดต) ───

        if price_usd_per_oz == 0 or usd_thb == 0:
            return {}

        price_thb_per_oz = price_usd_per_oz * usd_thb
        price_thb_per_gram = price_thb_per_oz / TROY_OUNCE_IN_GRAMS
        price_thb_per_baht = (
            price_thb_per_gram * THAI_GOLD_BAHT_IN_GRAMS * THAI_GOLD_PURITY
        )
        
        sell_price = round((price_thb_per_baht + 50) / 50) * 50
        buy_price = round((price_thb_per_baht - 50) / 50) * 50

        logger.info(
            f"Thai Gold (Fallback-Dataset Logic) — Sell: ฿{sell_price:,.0f} | Buy: ฿{buy_price:,.0f} (Spread=฿{sell_price - buy_price:,.0f})"
        )
        return {
            "source": "calculated_fallback",
            "price_thb_per_baht_weight": round(price_thb_per_baht, 2),
            "sell_price_thb": sell_price,
            "buy_price_thb": buy_price,
            "spread_thb": sell_price - buy_price,
        }

    # ─── Main Fetch All ────────────────────────────────────────────────────────
    def fetch_all(
        self, include_news: bool = True, history_days: int = 90, interval: str = "1d"
    ) -> dict:
        spot = self.fetch_gold_spot_usd()
        
        # ดึง Forex มาเป็นแค่ Internal Variable สำหรับ Fallback
        internal_usd = self.fetch_usd_thb_rate()
        
        thai = self.calc_thai_gold_price(
            price_usd_per_oz=spot.get("price_usd_per_oz", 0),
            usd_thb=internal_usd.get("usd_thb", 0),
        )
        
        ohlcv = self.ohlcv_fetcher.fetch_historical_ohlcv(
            days=history_days, interval=interval
        )
        
        # ส่งคืนเฉพาะข้อมูลที่จำเป็น โดยตัด key 'forex' ออกไป
        return {
            "spot_price": spot,
            "thai_gold": thai,
            "ohlcv_df": ohlcv,
            "fetched_at": get_thai_time().isoformat(),
        }