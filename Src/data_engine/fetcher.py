"""
fetcher.py — Gold Trading Agent · Phase 1 (Deterministic)
ดึงข้อมูลราคาทองคำไทย + ข่าวสาร ผ่าน Data APIs พร้อมรองรับ Timeframe ย่อย
"""

# Standard library
import logging
import os
import random
import re
import statistics
from typing import Optional
from data_engine.ohlcv_fetcher import OHLCVFetcher
from data_engine.thailand_timestamp import get_thai_time

# Third-party libraries
import pandas as pd
import requests
import yfinance as yf
from bs4 import BeautifulSoup
from dotenv import load_dotenv

import websocket
import json

# โหลดตัวแปรจากไฟล์ .env เข้าสู่ระบบ Environment ของ Python
load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
GOLD_API_URL = "https://api.gold-api.com/price/XAU"
FOREX_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"

# --- แก้ไขค่าคงที่ตรงนี้ใหม่ทั้งหมด ---
TROY_OUNCE_IN_GRAMS = 31.1034768
THAI_GOLD_BAHT_IN_GRAMS = 15.244
THAI_GOLD_PURITY = 0.965
# ----------------------------------
# รายชื่อ User-Agent สำหรับสุ่มเพื่อลดโอกาสถูกบล็อกเวลาดึงข้อมูลเว็บ
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

            yf_session = requests.Session()
            yf_session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

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

        """
        ระบบคำนวณค่านี้ขึ้นมาเพื่อรู้ว่าราคาทองที่ดึงมาในวินาทีนั้นเชื่อถือได้แค่ไหน
        หาก API ทั้ง 3 ตัวให้ราคาออกมาใกล้เคียงกัน ความน่าเชื่อถือก็จะสูง
        แต่ถ้ามีตัวใดตัวหนึ่งให้ราคาฉีกแปลกประหลาดออกไป ความน่าเชื่อถือจะลดลง
        """
        confidence = self.compute_confidence(prices)

        # กรณีมีข้อมูลแหล่งเดียว ไม่ต้องเทียบ คืนค่าเลย
        if len(prices) == 1:
            source, price = next(iter(prices.items()))
            return {
                "source": source,
                "price_usd_per_oz": price,
                "timestamp": get_thai_time().isoformat(),
                "confidence": confidence,
            }
        # หาราคากลาง (Median) เพื่อใช้เป็นตัวแทนของราคาที่ถูกต้อง
        median_price = statistics.median(prices.values())

        # กรองเอาเฉพาะแหล่งที่ราคาไม่ห่างจาก Median เกิน 0.5%
        # (ราคาทอง Spot ปกติจะห่างกันระหว่าง Broker ไม่กี่เหรียญ 0.5% ถือว่าปลอดภัยมาก)
        MAX_DEVIATION = 0.005
        valid_prices = {}

        for source, price in prices.items():
            if median_price > 0:
                diff = abs(price - median_price) / median_price
                if diff <= MAX_DEVIATION:
                    valid_prices[source] = price

        # ── 4. เลือก Source ที่ดีที่สุดตามลำดับความสำคัญ ──
        if not valid_prices:
            # Extreme Case: ข้อมูลมี 2 แหล่งแต่ตีกันยับเยินจนเกิน Deviation
            # เช่น twelvedata = 100, yfinance = 2300
            # บังคับเลือก yfinance (ถ้ามี) เพราะเป็นข้อมูลตลาดโลกย้อนหลัง น่าเชื่อถือสุดในจังหวะฉุกเฉิน
            logger.error("🚨 ข้อมูลราคาทองขัดแย้งกันอย่างรุนแรง (Deviation เกินลิมิต)")
            best_source = (
                "yfinance" if "yfinance" in prices else next(iter(prices.keys()))
            )
            final_price = prices[best_source]
            confidence = 0.0  # บังคับให้ความน่าเชื่อถือเป็น 0 ทันที เพื่อเตือนบอทไม่ให้ใช้ราคานี้เทรดหนัก
        else:
            # เลือกลำดับ Priority ตามความเสถียรและ Real-time
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
        if len(prices) == 0:
            return 0.0
        if len(prices) == 1:
            return 0.6
        values = list(prices.values())
        median_val = statistics.median(values)
        if median_val == 0:
            return 0.0
        max_diff = max(abs(p - median_val) / median_val for p in values)
        penalty = max_diff * 10
        confidence = max(0.0, 1.0 - penalty)

        return round(confidence, 3)

    def fetch_usd_thb_rate(self) -> dict:
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
        try:
            resp = self.session.get(FOREX_API_URL, timeout=10)
            resp.raise_for_status()
            rates = resp.json().get("rates", {})
            thb = float(rates.get("THB", 0))
            logger.info(f"USD/THB: {thb:.4f}")
            return {
                "source": "exchangerate-api.com",
                "usd_thb": thb,
                "timestamp": get_thai_time().isoformat(),
            }
        except Exception as e:
            logger.error(f"fetch_usd_thb_rate failed: {e}")
            return {}
        
    def fetch_latest_from_interceptor(self) -> dict:
        csv_path = "gold_prices_dataset.csv"
        
        if not os.path.exists(csv_path):
            logger.warning(f"File {csv_path} not found.")
            return {}

        try:
            df = pd.read_csv("gold_prices_dataset.csv")
            latest = df.iloc[-1]
            
            # --- แก้ไขตรงนี้: ใช้ชื่อให้ตรงกับ Headers ใน interceptor ล่าสุด ---
            return {
                "source": "intergold_live_stream",
                # เช็คชื่อใน [ ] ให้ตรงกับ headers ในไฟล์ interceptor
                "sell_price_thb": float(latest['ask_96']), 
                "buy_price_thb": float(latest['bid_96']),
                "gold_spot_usd": float(latest['gold_spot']),
                "usd_thb_live": float(latest['fx_usd_thb']),
                "timestamp": str(latest['timestamp'])
            }
        except Exception as e:
            # ถ้ายัง Error อีก บรรทัดนี้จะพ่นชื่อ Column ที่พังออกมาครับ
            logger.error(f"Error reading live gold data: {e}") 
            return {}

    def calc_thai_gold_price(
        self,
        price_usd_per_oz: float,
        usd_thb: float,
    ) -> dict:
        """
        ดึงราคาทองไทย 96.5% จาก Intergold (ผ่าน Playwright WebSocket)
        หากระบบขัดข้อง จะทำการสลับไปใช้สมการคำนวณ (Fallback) อัตโนมัติ
        """
        logger.info("กำลังดึงราคาทองไทยจาก Intergold ผ่าน Playwright WebSocket...")
        
        try:
            from playwright.sync_api import sync_playwright
            from playwright_stealth import stealth_sync
            import json
            import time
            import random

            result_data = {}  # ใช้ Dictionary ว่าง เพื่อให้ตัวแปรคงที่และแก้ปัญหา Scope

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--window-size=1920,1080",
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="th-TH",
                    timezone_id="Asia/Bangkok"
                )
                page = context.new_page()
                stealth_sync(page)

                # --- ฟังก์ชันจัดการข้อมูล ---
                def process_message(payload):
                    # ตรวจสอบว่า payload เป็น String และขึ้นต้นด้วย 42
                    if isinstance(payload, str) and payload.startswith('42'):
                        try:
                            data_list = json.loads(payload[2:])
                            if data_list[0] == "updateGoldRateData":
                                gold = data_list[1]
                                bid_96 = float(gold.get("bidPrice96", 0))
                                ask_96 = float(gold.get("offerPrice96", 0))

                                if bid_96 > 0 and ask_96 > 0:
                                    # ✅ ใช้ .update() แทนการกำหนดค่า (=) เพื่อบังคับให้แก้ค่าใน Scope หลัก
                                    result_data.update({
                                        "source": "intergold.co.th",
                                        "price_thb_per_baht_weight": round((bid_96 + ask_96) / 2, 2),
                                        "sell_price_thb": ask_96,
                                        "buy_price_thb": bid_96,
                                        "spread_thb": ask_96 - bid_96,
                                    })
                                    logger.info("✅ ได้รับข้อมูลอัปเดตราคาทองจาก WebSocket แล้ว!")
                        except Exception as e:
                            logger.error(f"Error parsing payload: {e}")

                def on_websocket(ws):
                    if "socket.io" in ws.url:
                        logger.info(f"🔗 ตรวจพบเส้นทาง WebSocket: {ws.url}")
                        # โยนฟังก์ชันเข้าไปตรงๆ โดยไม่ต้องใช้ lambda เพื่อป้องกันปัญหา Argument
                        ws.on("framereceived", process_message)

                page.on("websocket", on_websocket)

                try:
                    # ✅ เพิ่ม Timeout เป็น 60 วินาที 
                    page.goto("https://www.intergold.co.th/curr-price/", wait_until="domcontentloaded", timeout=60000)
                    
                    page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    page.evaluate(f"window.scrollBy(0, {random.randint(100, 300)})")

                    logger.info("⏳ หน้าเว็บโหลดสำเร็จ กำลังรอข้อมูลราคาวิ่งเข้ามา... (สูงสุด 20 วินาที)")
                    
                    # รอข้อมูล 20 รอบ (รอบละ 1 วินาที)
                    for _ in range(20):
                        if result_data:
                            break  # ถ้า Dictionary มีข้อมูลแล้ว ให้พังลูปออกไปปิดเบราว์เซอร์ทันที
                        page.wait_for_timeout(1000)

                except Exception as e:
                    logger.warning(f"⚠️ Playwright โหลดหน้าเว็บขัดข้อง: {e}")
                finally:
                    context.close()
                    browser.close()

            # --- ถ้าได้ข้อมูล ให้ Return ค่าออกไปเลย ---
            if result_data:
                logger.info(f"Thai Gold (Intergold) — Sell: ฿{result_data['sell_price_thb']:,.0f} | Buy: ฿{result_data['buy_price_thb']:,.0f}")
                return result_data

        except Exception as e:
            logger.error(f"❌ ระบบ Playwright ภายในขัดข้อง: {e}")

        logger.warning("ไม่สามารถดึงข้อมูลจาก Intergold ได้ — สลับไปใช้โหมดคำนวณ (Fallback)")

        # ─── Fallback: คำนวณแบบเดิม (หากวิธีแรกพัง) ───
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
            f"Thai Gold (Fallback-Dataset Logic) — Sell: ฿{sell_price:,.0f} | Buy: ฿{buy_price:,.0f} (Spread={sell_price - buy_price})"
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
        forex = self.fetch_usd_thb_rate()
        thai = self.calc_thai_gold_price(
            price_usd_per_oz=spot.get("price_usd_per_oz", 0),
            usd_thb=forex.get("usd_thb", 0),
        )
        ohlcv = self.ohlcv_fetcher.fetch_historical_ohlcv(
            days=history_days, interval=interval
        )
        return {
            "spot_price": spot,
            "forex": forex,
            "thai_gold": thai,
            "ohlcv_df": ohlcv,
            "fetched_at": get_thai_time().isoformat(),
        }
