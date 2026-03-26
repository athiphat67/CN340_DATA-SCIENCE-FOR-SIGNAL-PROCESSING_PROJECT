"""
newsfetcher.py — Gold Trading Agent · Phase 1 (Deterministic)
ดึงข่าวสารที่มีผลกระทบต่อราคาทองไทยผ่าน yfinance (.news)
ครอบคลุม: ราคาทองโลก, ค่าเงิน USD/THB, Fed, ภูมิรัฐศาสตร์, เศรษฐกิจไทย
ไม่ต้องใช้ API Key — ใช้ yfinance ได้เลย
"""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

analyzer = SentimentIntensityAnalyzer()

logger = logging.getLogger(__name__)


# ─── Category → Ticker Mapping ──────────────────────────────────────────────────
#
# แต่ละ category ผูกกับ yfinance tickers ที่เกี่ยวข้อง
# yfinance จะดึงข่าวล่าสุดของ ticker นั้นโดยอัตโนมัติ


#GC=F: Gold Comex Futures (The global benchmark price for gold).
#GLD / IAU / SGOL: Gold Exchanged-Traded Funds (ETFs). These are stocks that represent physical gold.
#THB=X: Thai Baht Exchange Rate (specifically USD to THB).
#^TNX: CBOE 10-Year Treasury Note Yield (US interest rates).
#^IRX: 13-Week Treasury Bill (Short-term interest rates).
#TLT: iShares 20+ Year Treasury Loan Bond ETF.
#TIP: Treasury Inflation-Protected Securities (Bonds that go up when inflation rises).
#RINF: ProShares Inflation Expectations ETF.
#^VIX: Volatility Index (The "Fear Index").
#DX-Y.NYB: Dollar Index (DXY). Measures the US Dollar against other major currencies.
#UUP: Invesco DB US Dollar Index Bullish Fund.
#EWY / THD: iShares MSCI (Morgan Stanley Capital International) South Korea and Thailand ETFs.
#SET.BK: Stock Exchange of Thailand (Bangkok).
#

NEWS_CATEGORIES = {
    "gold_price": {
        "label":   "ราคาทองคำโลก",
        "impact":  "direct",
        "tickers": ["GC=F", "GLD", "IAU"],        # Gold Futures, Gold ETFs
    },
    "usd_thb": {
        "label":   "ค่าเงิน USD/THB",
        "impact":  "direct",
        "tickers": ["THB=X", "USDTHB=X"],          # USD/THB pair
    },
    "fed_policy": {
        "label":   "นโยบายดอกเบี้ย Fed",
        "impact":  "high",
        "tickers": ["^TNX", "^IRX", "TLT"],        # US Treasury Yields, Bond ETF
    },
    "inflation": {
        "label":   "เงินเฟ้อ / CPI",
        "impact":  "high",
        "tickers": ["TIP", "RINF"],                # TIPS ETF (inflation-linked)
    },
    "geopolitics": {
        "label":   "ภูมิรัฐศาสตร์ / Safe Haven",
        "impact":  "high",
        "tickers": ["GC=F", "SLV", "^VIX"],        # Gold, Silver, VIX (fear index)
    },
    "dollar_index": {
        "label":   "ดัชนีค่าเงินดอลลาร์ (DXY)",
        "impact":  "medium",
        "tickers": ["DX-Y.NYB", "UUP"],            # DXY, Dollar Bull ETF
    },
    "thai_economy": {
        "label":   "เศรษฐกิจไทย / ตลาดหุ้นไทย",
        "impact":  "medium",
        "tickers": ["EWY", "THD", "SET.BK"],       # Thai/EM ETFs, SET Index
    },
    "thai_gold_market": {
        "label":   "ตลาดทองไทย",
        "impact":  "direct",
        "tickers": ["GC=F", "SGOL"],               # Spot Gold, Physical Gold ETF
    },
}


# ─── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class NewsArticle:
    title:        str
    url:          str
    source:       str
    published_at: str           # ISO 8601
    ticker:       str           # yfinance ticker ที่ดึงมา
    category:     str           # key จาก NEWS_CATEGORIES
    impact_level: str           # "direct" | "high" | "medium"
    sentiment_score: float = 0.0


@dataclass
class NewsFetchResult:
    fetched_at:     str
    total_articles: int
    by_category:    dict = field(default_factory=dict)
    errors:         list = field(default_factory=list)

class GoldNewsFetcher:
    def __init__(self, max_per_category: int = 5):
        self.max_per_category = max_per_category
        # Use a session for better performance during multiple requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def _fetch_full_content(self, url: str) -> str:
        """Visits the URL and extracts all paragraph text."""
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Find all paragraph tags
                paragraphs = soup.find_all('p')
                # Join them into one large string
                full_text = " ".join([p.get_text().strip() for p in paragraphs])
                # Return only the first 3000 chars to avoid overwhelming the sentiment analyzer
                return full_text[:3000]
        except Exception as e:
            logger.debug(f"Failed to scrape {url}: {e}")
        return ""

    def _fetch_ticker_news(self, ticker_symbol: str) -> list[dict]:
        try:
            import yfinance as yf
            ticker = yf.Ticker(ticker_symbol)
            if hasattr(ticker, "get_news"):
                return ticker.get_news() or []
            return ticker.news or []
        except Exception as e:
            logger.warning(f"yfinance news error [{ticker_symbol}]: {e}")
            return []

    def _parse(self, raw: dict, ticker: str, category: str) -> Optional[NewsArticle]:
        content = raw.get("content") or {}
        
        # ── 1. Basic Metadata ──
        title = (raw.get("title") or content.get("title") or "").strip()
        url = (raw.get("link") or raw.get("url") or 
               content.get("canonicalUrl", {}).get("url") or "")
        
        if not title or not url.startswith("http"):
            return None

        # ── 2. NEW: Fetch Full Content from URL ──
        logger.info(f"Scraping content for: {title[:50]}...")
        full_article_text = self._fetch_full_content(url)

        # ── 3. Sentiment Analysis ──
        # If scraping found text, use it. Otherwise, fall back to the title.
        text_for_analysis = full_article_text if len(full_article_text) > 150 else title
        vs = analyzer.polarity_scores(text_for_analysis)
        score = vs['compound']

        # ── 4. Published Date ──
        pub_str = content.get("pubDate") or raw.get("pubDate") or ""
        if not pub_str:
            ts = raw.get("providerPublishTime", 0)
            pub_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else ""

        return NewsArticle(
            title=title,
            url=url,
            source=raw.get("publisher") or content.get("provider", {}).get("displayName") or "unknown",
            published_at=pub_str,
            ticker=ticker,
            category=category,
            impact_level=NEWS_CATEGORIES[category]["impact"],
            sentiment_score=score,

        )

# ─── NewsFetcher ────────────────────────────────────────────────────────────────

class GoldNewsFetcher:
    """
    ดึงข่าวผ่าน yfinance .news — ไม่ต้องใช้ API Key
    pip install yfinance
    """

    def __init__(self, max_per_category: int = 5):
        self.max_per_category = max_per_category

    # ─── Internal: ดึงข่าวจาก 1 ticker ─────────────────────────────────────────
    def _fetch_ticker_news(self, ticker_symbol: str) -> list[dict]:
        """
        ดึง raw news list จาก yfinance Ticker
        รองรับทั้ง yfinance เวอร์ชันเก่า (<0.2.37) และใหม่ (>=0.2.37 / 2.x)
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(ticker_symbol)

            # ── วิธี 1: .get_news() — yfinance >= 0.2.37 ─────────────────────
            if hasattr(ticker, "get_news"):
                try:
                    news = ticker.get_news(count=self.max_per_category * 2) or []
                    if news:
                        logger.debug(f"[{ticker_symbol}] get_news() → {len(news)} items")
                        return news
                except Exception as e:
                    logger.debug(f"[{ticker_symbol}] get_news() failed: {e}")

            # ── วิธี 2: .news attribute — yfinance เวอร์ชันเก่า ──────────────
            news = ticker.news or []
            logger.debug(f"[{ticker_symbol}] .news → {len(news)} items")
            return news

        except ImportError:
            raise RuntimeError("yfinance ไม่ได้ติดตั้ง — รัน: pip install yfinance")
        except Exception as e:
            logger.warning(f"yfinance news error [{ticker_symbol}]: {e}")
            return []

    # ─── Internal: แปลง raw → NewsArticle ───────────────────────────────────────
    @staticmethod
    def _parse(raw: dict, ticker: str, category: str) -> Optional[NewsArticle]:
        """
        รองรับ 2 โครงสร้างที่ yfinance ใช้:

        โครงสร้างเก่า (< 0.2.37):
        {
          "title": str,
          "link": str,
          "publisher": str,
          "providerPublishTime": int,
          "thumbnail": {"resolutions": [{"url": str}]}
        }

        โครงสร้างใหม่ (>= 0.2.37 / 2.x):
        {
          "title": str,
          "content": {
            "title": str,
            "canonicalUrl": {"url": str},
            "provider": {"displayName": str},
            "pubDate": str (ISO),
            "thumbnail": {"resolutions": [{"url": str}]}
          }
        }
        """
        # ── ดึง content block (ถ้ามี) ─────────────────────────────────────────
        content = raw.get("content") or {}

        # ── title ─────────────────────────────────────────────────────────────
        title = (
            raw.get("title")
            or content.get("title")
            or ""
        ).strip()
        if not title:
            return None

        # ── url ───────────────────────────────────────────────────────────────
        # Inside _parse method, near the URL logic:
        url = (
            raw.get("link")
            or raw.get("url")
            or content.get("canonicalUrl", {}).get("url")
            or content.get("clickThroughUrl", {}).get("url")
            or ""
        )
        if not url.startswith("http"):
            return None # Ignore invalid or empty links

        # ── source / publisher ────────────────────────────────────────────────
        source = (
            raw.get("publisher")
            or content.get("provider", {}).get("displayName")
            or "unknown"
        )

        # ── published_at ──────────────────────────────────────────────────────
        published_at = ""
        # เวอร์ชันใหม่ → ISO string
        pub_str = content.get("pubDate") or raw.get("pubDate") or ""
        if pub_str:
            published_at = pub_str
        else:
            # เวอร์ชันเก่า → unix timestamp
            ts = raw.get("providerPublishTime", 0)
            if ts:
                try:
                    published_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
                except Exception:
                    pass
                
        # ─── คำนวณ Sentiment Score จาก Title ──────────────────────────
        # title คือส่วนที่สรุปเนื้อหาได้ดีที่สุดสำหรับข่าวการเงิน
        vs = analyzer.polarity_scores(title)
        score = vs['compound']  # compound คือคะแนนรวม (-1 = ร้ายแรง, 1 = ดีมาก)




        return NewsArticle(
            title        = title,
            url          = url,
            source       = source,
            published_at = published_at,
            ticker       = ticker,
            category     = category,
            impact_level = NEWS_CATEGORIES[category]["impact"],
            sentiment_score = score,

        )

    # ─── Fetch one category ──────────────────────────────────────────────────────
    def fetch_category(self, category: str) -> list[NewsArticle]:
        """
        ดึงข่าวของทุก ticker ใน category
        deduplicate ด้วย URL แล้ว sort ตาม published_at desc
        """
        tickers    = NEWS_CATEGORIES[category]["tickers"]
        results:   list[NewsArticle] = []
        seen_urls: set[str] = set()

        for symbol in tickers:
            raw_list = self._fetch_ticker_news(symbol)
            for raw in raw_list:
                article = self._parse(raw, symbol, category)
                if article and article.url not in seen_urls:
                    if category == "usd_thb":
                        thai_keywords = ['thai', 'baht', 'thb', 'bangkok', 'bot'] #bot is not stand for Robot, It's stand for Back of Thailand.
                        title_lower = article.title.lower()
                        
                        if not any(word in title_lower for word in thai_keywords):
                            continue
                    results.append(article)
                    seen_urls.add(article.url)

        results.sort(key=lambda a: a.published_at, reverse=True)
        return results[: self.max_per_category]

    # ─── Fetch All Categories ────────────────────────────────────────────────────
    def fetch_all(self) -> NewsFetchResult:
        """ดึงข่าวทุก category แล้วรวมเป็น NewsFetchResult"""
        logger.info(f"NewsFetcher (yfinance): ดึงข่าว {len(NEWS_CATEGORIES)} categories")
        by_category: dict = {}
        errors:      list = []
        total = 0

        for cat_key, cat_meta in NEWS_CATEGORIES.items():
            try:
                articles = self.fetch_category(cat_key)
                by_category[cat_key] = {
                    "label":    cat_meta["label"],
                    "impact":   cat_meta["impact"],
                    "tickers":  cat_meta["tickers"],
                    "count":    len(articles),
                    "articles": [asdict(a) for a in articles],
                }
                total += len(articles)
                logger.info(f"  [{cat_key}] {len(articles)} articles "
                            f"(tickers: {cat_meta['tickers']})")
            except Exception as e:
                errors.append(f"{cat_key}: {e}")
                logger.error(f"  [{cat_key}] error: {e}")

        return NewsFetchResult(
            fetched_at     = datetime.utcnow().isoformat() + "Z",
            total_articles = total,
            by_category    = by_category,
            errors         = errors,
        )

    def to_dict(self) -> dict:
        """fetch_all() แล้วแปลงเป็น dict พร้อม serialize ส่งให้ Orchestrator"""
        return asdict(self.fetch_all())


# ─── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    fetcher = GoldNewsFetcher(max_per_category=2) # Small count because scraping takes time
    data = fetcher.to_dict()
    
    print("\n--- START JSON OUTPUT ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("--- END JSON OUTPUT ---")