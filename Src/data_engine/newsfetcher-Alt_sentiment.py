import logging
import requests
import json
import sys
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Initialize analyzer
analyzer = SentimentIntensityAnalyzer()
logger = logging.getLogger(__name__)

# ─── Category → Ticker Mapping ──────────────────────────────────────────────────
NEWS_CATEGORIES = {
    "gold_price": {"label": "ราคาทองคำโลก", "impact": "direct", "weight": 1.0, "tickers": ["GC=F", "GLD", "IAU"]},
    "usd_thb": {"label": "ค่าเงิน USD/THB", "impact": "direct", "weight": 1.0, "tickers": ["THB=X", "USDTHB=X"]},
    "fed_policy": {"label": "นโยบายดอกเบี้ย Fed", "impact": "high", "weight": -1.0, "tickers": ["^TNX", "^IRX", "TLT"]},
    "inflation": {"label": "เงินเฟ้อ / CPI", "impact": "high", "weight": 1.0, "tickers": ["TIP", "RINF"]},
    "geopolitics": {"label": "ภูมิรัฐศาสตร์ / Safe Haven", "impact": "high", "weight": 1.0, "tickers": ["GC=F", "SLV", "^VIX"]},
    "dollar_index": {"label": "ดัชนีค่าเงินดอลลาร์ (DXY)", "impact": "medium", "weight": -1.0, "tickers": ["DX-Y.NYB", "UUP"]},
    "thai_economy": {"label": "เศรษฐกิจไทย / ตลาดหุ้นไทย", "impact": "medium", "weight": 0.5, "tickers": ["EWY", "THD", "SET.BK"]},
    "thai_gold_market": {"label": "ตลาดทองไทย", "impact": "direct", "weight": 0.5, "tickers": ["GC=F", "SGOL"]},
}

# ─── Dataclasses ────────────────────────────────────────────────────────────────
@dataclass
class NewsArticle:
    title: str
    url: str
    source: str
    published_at: str
    ticker: str
    category: str
    impact_level: str
    raw_sentiment: float = 0.0      # Vader's original score
    adjusted_sentiment: float = 0.0 # Score flipped based on Gold correlation

@dataclass
class NewsFetchResult:
    fetched_at: str
    total_articles: int
    by_category: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

# ─── Unified GoldNewsFetcher ────────────────────────────────────────────────────
class GoldNewsFetcher:
    def __init__(self, max_per_category: int = 5):
        self.max_per_category = max_per_category
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _fetch_full_content(self, url: str) -> str:
        try:
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                paragraphs = soup.find_all('p')
                full_text = " ".join([p.get_text().strip() for p in paragraphs])
                return full_text[:3000]
        except Exception as e:
            logger.debug(f"Scrape failed: {e}")
        return ""

    def _fetch_ticker_news(self, ticker_symbol: str) -> list[dict]:
        try:
            import yfinance as yf
            ticker = yf.Ticker(ticker_symbol)
            if hasattr(ticker, "get_news"):
                return ticker.get_news() or []
            return ticker.news or []
        except Exception as e:
            logger.warning(f"yfinance error [{ticker_symbol}]: {e}")
            return []

    def _parse(self, raw: dict, ticker: str, category: str) -> Optional[NewsArticle]:
        content = raw.get("content") or {}
        title = (raw.get("title") or content.get("title") or "").strip()
        url = (raw.get("link") or raw.get("url") or 
               content.get("canonicalUrl", {}).get("url") or "")
        
        if not title or not url.startswith("http"):
            return None

        # 1. Scraping and Sentiment Calculation
        full_article_text = self._fetch_full_content(url)
        text_for_analysis = full_article_text if len(full_article_text) > 150 else title
        
        vs = analyzer.polarity_scores(text_for_analysis)
        raw_score = vs['compound']
        
        # 2. SEPARATE SENTIMENT LOGIC: Apply weights
        weight = NEWS_CATEGORIES[category].get("weight", 1.0)
        adjusted_score = raw_score * weight

        # 3. Date Handling
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
            raw_sentiment=raw_score,
            adjusted_sentiment=round(adjusted_score, 4)
        )

    def fetch_category(self, category: str) -> list[NewsArticle]:
        tickers = NEWS_CATEGORIES[category]["tickers"]
        results = []
        seen_urls = set()

        for symbol in tickers:
            raw_list = self._fetch_ticker_news(symbol)
            for raw in raw_list:
                article = self._parse(raw, symbol, category)
                if article and article.url not in seen_urls:
                    if category == "usd_thb":
                        thai_keywords = ['thai', 'baht', 'thb', 'bangkok', 'bot']
                        if not any(word in article.title.lower() for word in thai_keywords):
                            continue
                    results.append(article)
                    seen_urls.add(article.url)

        results.sort(key=lambda a: a.published_at, reverse=True)
        return results[:self.max_per_category]

    def fetch_all(self) -> NewsFetchResult:
        logger.info(f"NewsFetcher: ดึงข่าว {len(NEWS_CATEGORIES)} categories")
        by_category = {}
        errors = []
        total = 0

        for cat_key, cat_meta in NEWS_CATEGORIES.items():
            try:
                articles = self.fetch_category(cat_key)
                by_category[cat_key] = {
                    "label": cat_meta["label"],
                    "impact": cat_meta["impact"],
                    "articles": [asdict(a) for a in articles],
                }
                total += len(articles)
            except Exception as e:
                errors.append(f"{cat_key}: {e}")
                logger.error(f"Error in {cat_key}: {e}")

        return NewsFetchResult(
            fetched_at=datetime.now(timezone.utc).isoformat(),
            total_articles=total,
            by_category=by_category,
            errors=errors
        )

    def to_dict(self) -> dict:
        return asdict(self.fetch_all())

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    fetcher = GoldNewsFetcher(max_per_category=2)
    data = fetcher.to_dict()
    print("\n--- START JSON OUTPUT ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("--- END JSON OUTPUT ---")