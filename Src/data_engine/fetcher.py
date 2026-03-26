"""
fetcher.py — Gold Trading Agent · Phase 1 (Deterministic)
ดึงข้อมูลราคาทองคำไทย + ข่าวสาร ผ่าน Data APIs พร้อมรองรับ Timeframe ย่อย
"""

import requests
import pandas as pd
from datetime import datetime
from typing import Optional
import logging
import random
import re
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─── Constants ──────────────────────────────────────────────────────────────────
GOLD_API_URL   = "https://api.gold-api.com/price/XAU"        # ราคาทอง spot (USD)
FOREX_API_URL  = "https://api.exchangerate-api.com/v4/latest/USD"  # อัตราแลกเปลี่ยน
NEWS_API_URL   = "https://newsapi.org/v2/everything"

THAI_GOLD_PRICE_PER_BAHT_WEIGHT = 15.244   # 1 troy oz ≈ 15.244 บาทน้ำหนัก
THAI_GOLD_PURITY = 0.965                    # ทองคำ 96.5% (ทองสมาคม)

# รายชื่อ User-Agent สำหรับสุ่มเพื่อลดโอกาสถูกบล็อกเวลาดึงข้อมูลเว็บ
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

class GoldDataFetcher:
    """ดึงข้อมูลราคาทองและข่าวสำหรับตลาดทองคำไทย"""

    def __init__(self, news_api_key: Optional[str] = None):
        self.news_api_key = news_api_key
        self.session = requests.Session()

    # def get_market_status(self) -> dict:
    #     """เช็คว่าตอนนี้ตลาดทองคำโลก (CME) เปิดหรือปิด"""
    #     now = datetime.utcnow()
    #     weekday = now.weekday()  # 0=Mon, 5=Sat, 6=Sun
    #     hour = now.hour
        
    #     is_open = True
    #     reason = "Market is Open"

    #     # ตลาดทองคำปิดวันเสาร์ (5) และวันอาทิตย์ (6) 
    #     # ปกติเปิดเช้าวันจันทร์ ~05:00-06:00 น. เวลาไทย (22:00-23:00 UTC)
    #     if weekday == 5:
    #         is_open = False
    #         reason = "Market Closed (Weekend - Saturday)"
    #     elif weekday == 6:
    #         is_open = False
    #         reason = "Market Closed (Weekend - Sunday)"
    #     elif hour == 21: # ช่วงพักระบบรายวันสั้นๆ
    #         reason = "Market Daily Break"

    #     return {"is_open": is_open, "reason": reason, "utc_time": now.strftime("%H:%M")}
    
    # ─── Gold Spot Price (USD) ─────────────────────────────────────────────────
    def fetch_gold_spot_usd(self) -> dict:
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})
        try:
            resp = self.session.get(GOLD_API_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            price_usd = float(data.get("price", 0))
            logger.info(f"Gold Spot (USD): ${price_usd:.2f}/oz")
            return {
                "source": "gold-api.com",
                "price_usd_per_oz": price_usd,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"fetch_gold_spot_usd failed: {e}")
            return {}

    # ─── USD/THB Exchange Rate ─────────────────────────────────────────────────
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
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"fetch_usd_thb_rate failed: {e}")
            return {}

    # ─── Thai Gold Price (ดึงจากเว็บ Intergold + Fallback) ────────────────────
    def calc_thai_gold_price(
        self,
        price_usd_per_oz: float,
        usd_thb: float,
    ) -> dict:
        """ดึงราคาทองไทยจาก Intergold หากไม่สำเร็จจะสลับไปคำนวณด้วยสูตร"""
        try:
            url = "https://www.intergold.co.th/"
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = self.session.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            buy_node = soup.select_one('tr#trend-1 td.buy span.price')
            sell_node = soup.select_one('tr#trend-1 td.sell span.price')
            
            if buy_node and sell_node:
                buy_price = float(re.sub(r'[^\d.]', '', buy_node.text))
                sell_price = float(re.sub(r'[^\d.]', '', sell_node.text))
                price_thb_per_baht = (buy_price + sell_price) / 2
                
                logger.info(f"Thai Gold (Intergold) — Sell: ฿{sell_price:,.0f} | Buy: ฿{buy_price:,.0f}")
                return {
                    "source": "intergold.co.th",
                    "price_thb_per_baht_weight": round(price_thb_per_baht, 2),
                    "sell_price_thb": sell_price,
                    "buy_price_thb": buy_price,
                    "spread_thb": sell_price - buy_price,
                }
            else:
                logger.warning("ไม่พบ HTML Element ของราคาทองบน Intergold — สลับไปใช้โหมดคำนวณ")
                
        except Exception as e:
            logger.error(f"การดึงข้อมูลจาก Intergold ล้มเหลว ({e}) — สลับไปใช้โหมดคำนวณ")

        # ─── Fallback: คำนวณแบบเดิม ───
        if price_usd_per_oz == 0 or usd_thb == 0:
            return {}

        price_thb_per_oz   = price_usd_per_oz * THAI_GOLD_PURITY * usd_thb
        price_thb_per_baht = price_thb_per_oz / THAI_GOLD_PRICE_PER_BAHT_WEIGHT

        sell_price = round(price_thb_per_baht + 150, -2)
        buy_price  = round(price_thb_per_baht - 150, -2)

        logger.info(f"Thai Gold (Fallback) — Sell: ฿{sell_price:,.0f} | Buy: ฿{buy_price:,.0f}")
        return {
            "source": "calculated",
            "price_thb_per_baht_weight": round(price_thb_per_baht, 2),
            "sell_price_thb": sell_price,
            "buy_price_thb": buy_price,
            "spread_thb": sell_price - buy_price,
        }

    # ─── Historical OHLCV (รองรับ Timeframe: 1m, 5m, 15m, 1h, 1d) ───────────
    def fetch_historical_ohlcv(
        self,
        days: int = 90,
        interval: str = "1d",
        symbol: str = "GC=F",
    ) -> pd.DataFrame:
        """
        ดึงข้อมูล OHLCV ย้อนหลัง พร้อมกำหนด Timeframe (`interval`)
        """
        try:
            import yfinance as yf

            # ป้องกัน Error จากข้อจำกัดของ yfinance API
            if interval == "1m" and days > 7:
                logger.warning(f"yfinance รองรับ {interval} สูงสุด 7 วัน -> ปรับลด days = 7")
                days = 7
            elif interval in ["2m", "5m", "15m", "30m", "90m"] and days > 60:
                logger.warning(f"yfinance รองรับ {interval} สูงสุด 60 วัน -> ปรับลด days = 60")
                days = 60
            elif interval == "1h" and days > 730:
                logger.warning(f"yfinance รองรับ {interval} สูงสุด 730 วัน -> ปรับลด days = 730")
                days = 730
                
            # 2. แปลงจำนวนวัน (days) ให้เป็นรูปแบบ period ที่ yfinance เข้าใจ (เช่น '3650d')
            # วิธีนี้จะทำให้คุณใส่ days = 3650 เพื่อเอาข้อมูล 10 ปีได้เลย
            period_str = f"{days}d"
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period_str, interval=interval)
            
            if df.empty:
                logger.warning(f"ไม่พบข้อมูล OHLCV สำหรับ {symbol} (interval={interval}, period={period_str})")
                return pd.DataFrame()

            df.columns = [c.lower() for c in df.columns]
            df = df[["open", "high", "low", "close", "volume"]].dropna()
            logger.info(f"OHLCV fetched: {len(df)} rows ({symbol} | Timeframe: {interval}) | Period: {period_str}")
            return df
        except ImportError:
            logger.warning("yfinance not installed. Run: pip install yfinance")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"fetch_historical_ohlcv failed: {e}")
            return pd.DataFrame()

    # ─── Gold News Headlines ───────────────────────────────────────────────────
    def fetch_gold_news(self, max_articles: int = 10) -> list[dict]:
        if not self.news_api_key:
            return []
        try:
            params = {
                "q": "gold price OR ราคาทอง OR XAU",
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_articles,
                "apiKey": self.news_api_key,
            }
            resp = self.session.get(NEWS_API_URL, params=params, timeout=10)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
            news = [
                {
                    "title": a.get("title", ""),
                    "source": a.get("source", {}).get("name", ""),
                    "published_at": a.get("publishedAt", ""),
                    "url": a.get("url", ""),
                }
                for a in articles
            ]
            return news
        except Exception as e:
            logger.error(f"fetch_gold_news failed: {e}")
            return []

    # ─── Main Fetch All ────────────────────────────────────────────────────────
    def fetch_all(self, include_news: bool = True, history_days: int = 90, interval: str = "1d") -> dict:
        spot   = self.fetch_gold_spot_usd()
        forex  = self.fetch_usd_thb_rate()
        thai   = self.calc_thai_gold_price(
            price_usd_per_oz=spot.get("price_usd_per_oz", 0),
            usd_thb=forex.get("usd_thb", 0),
        )
        ohlcv  = self.fetch_historical_ohlcv(days=history_days, interval=interval)
        news   = self.fetch_gold_news() if include_news else []

        return {
            "spot_price":     spot,
            "forex":          forex,
            "thai_gold":      thai,
            "ohlcv_df":       ohlcv,
            "news":           news,
            "fetched_at":     datetime.utcnow().isoformat(),
        }
        
    if __name__ == "__main__":
        fetcher = GoldDataFetcher()

        # --- วิธีแก้เพื่อดึง Real-time 1 วัน รายนาที ---
        # ให้เปลี่ยนตัวเลขในวงเล็บตามนี้ครับ:
        df = fetcher.fetch_historical_ohlcv(days=90, interval="1d") 
    