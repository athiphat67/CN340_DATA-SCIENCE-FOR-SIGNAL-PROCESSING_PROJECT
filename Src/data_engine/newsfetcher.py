"""
newsfetcher.py — Gold Trading Agent · Phase 2.1 (Refactored, Batched & Optimized)

การปรับปรุง:
  [1] แหล่งข้อมูล  : yfinance (metadata) + RSS feeds → ไม่ scrape body → ไม่โดน block
  [2] Sentiment    : Batched FinBERT (ประมวลผลพร้อมกันหลังคัดกรองข่าวเสร็จ) + รองรับ MPS (Mac)
  [3] Context guard: Greedy Packing ป้องกัน context overflow ได้อย่างคุ้มค่าที่สุด
  [4] Performance  : ดึงข้อมูลแบบ Parallel (Threading) พร้อม Timeout ป้องกันค้าง
  [5] Tokenizer    : ประเมิน Token แม่นยำระดับ Production รองรับ Grok/Gemini (tiktoken)
"""

from __future__ import annotations

import logging
import concurrent.futures
from dataclasses import dataclass, asdict, field
from typing import Optional
import requests
import feedparser

logger = logging.getLogger(__name__)

# กำหนด Timezone ประเทศไทย (UTC+7)
from data_engine.thailand_timestamp import get_thai_time, to_thai_time

# ─── [A] Tokenizer Setup (tiktoken) ──────────────────────────────────────────
try:
    import tiktoken

    _tokenizer = tiktoken.get_encoding("cl100k_base")
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    _tokenizer = None
    logger.warning("tiktoken ไม่ได้ติดตั้ง — จะใช้การประมาณการ Token แบบพื้นฐาน")

# ─── [B] Sentiment: FinBERT via Hugging Face API ─────────────────────────────
import os
import time
from dotenv import load_dotenv

load_dotenv()

FINBERT_MODEL = "ProsusAI/finbert"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{FINBERT_MODEL}"
# ดึง API Token จาก Environment Variable (ต้องไปตั้งค่าใน Render)
HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    print("Warning: ไม่พบ HF_TOKEN กรุณาตรวจสอบไฟล์ .env หรือการตั้งค่า Environment Variable")


def score_sentiment_batch(texts: list[str], retries: int = 3) -> list[float]:
    """ประเมิน Sentiment ผ่าน Hugging Face Free API (วนลูปส่งทีละข้อความเพื่อแก้ปัญหา API ไม่รองรับ Batch)"""
    if not texts:
        return []

    if not HF_TOKEN:
        logger.warning("ไม่ได้ตั้งค่า HF_TOKEN จะข้ามการประเมิน Sentiment (คืนค่า 0.0)")
        return [0.0] * len(texts)

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    scores = []

    logger.info(f"กำลังประเมิน Sentiment ทีละข่าวจำนวน {len(texts)} ข่าว ผ่าน HF API...")

    # วนลูปส่งทีละข้อความ
    for i, text in enumerate(texts):
        # ส่งข้อมูลเป็น String เดี่ยวๆ (ไม่ใช่ List)
        payload = {"inputs": text[:512]}
        text_score = 0.0  # ค่าเริ่มต้นหากประเมินข่าวนี้ไม่สำเร็จ

        for attempt in range(retries):
            try:
                response = requests.post(
                    HF_API_URL, headers=headers, json=payload, timeout=15
                )

                # 1. จัดการกรณี Rate Limit (ส่งถี่เกินไป)
                if response.status_code == 429:
                    logger.warning(
                        f"  [ข่าว {i + 1}] ติด Rate Limit (429) จาก HF API รอ 10 วินาที... (ครั้งที่ {attempt + 1})"
                    )
                    time.sleep(10)
                    continue

                # 2. จัดการกรณี Model Cold Start (โมเดลเพิ่งตื่น)
                if response.status_code == 503 and "estimated_time" in response.json():
                    wait_time = response.json().get("estimated_time", 10)
                    logger.info(f"  [ข่าว {i + 1}] โมเดลกำลังโหลด รอ {wait_time} วินาที...")
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                results = response.json()

                # ... (ส่วนการแกะค่า JSON และหาคะแนน sentiment ทำเหมือนเดิม) ...
                if isinstance(results, list) and len(results) > 0:
                    res = results[0] if isinstance(results[0], list) else results
                    if isinstance(res, list) and len(res) > 0:
                        best_label = max(res, key=lambda x: x.get("score", 0))
                        label = best_label.get("label", "")
                        conf = best_label.get("score", 0.0)

                        if label == "positive":
                            text_score = round(conf, 4)
                        elif label == "negative":
                            text_score = -round(conf, 4)

                # สำเร็จแล้ว ให้ออกจากลูป retry
                break

            except Exception as e:
                logger.warning(
                    f"  [ข่าว {i + 1}] HF API Error (ครั้งที่ {attempt + 1}): {e}"
                )
                time.sleep(2)  # พัก 2 วินาทีก่อนลองใหม่ในรอบ retry

        # 3. Polite Sleep: พักหายใจ 0.5 วินาทีก่อนส่งข่าวถัดไป ป้องกันการโดนแบน
        time.sleep(0.5)

        scores.append(text_score)

        # นำคะแนนที่ได้ (หรือ 0.0 ถ้า error) เก็บเข้า list รวม
        scores.append(text_score)

    return scores


# ─── [C] Category → Sources Mapping ─────────────────────────────────────────
NEWS_CATEGORIES: dict[str, dict] = {
    "gold_price": {
        "label": "ราคาทองคำโลก",
        "impact": "direct",
        "tickers": ["GC=F", "GLD", "IAU"],
        "rss": [
            "https://www.kitco.com/rss/kitconews.xml",
            "https://www.investing.com/rss/news_301.rss",
        ],
        "keywords": ["gold", "xau", "bullion", "comex", "spot gold", "precious metal"],
    },
    "usd_thb": {
        "label": "ค่าเงิน USD/THB",
        "impact": "direct",
        "tickers": ["THB=X", "USDTHB=X"],
        "rss": [
            "https://www.fxstreet.com/rss/news",
        ],
        "keywords": [
            "thai baht",
            "thb",
            "usd/thb",
            "bank of thailand",
            "bot rate",
            "bangkok",
        ],
    },
    "fed_policy": {
        "label": "นโยบายดอกเบี้ย Fed",
        "impact": "high",
        "tickers": ["^TNX", "^IRX", "TLT"],
        "rss": [
            "https://feeds.feedburner.com/reuters/businessNews",
            "https://www.fxstreet.com/rss/news",
        ],
        "keywords": [
            "fed",
            "federal reserve",
            "fomc",
            "rate hike",
            "rate cut",
            "powell",
            "interest rate",
            "monetary policy",
        ],
    },
    "inflation": {
        "label": "เงินเฟ้อ / CPI",
        "impact": "high",
        "tickers": ["TIP", "RINF"],
        "rss": [
            "https://feeds.feedburner.com/reuters/businessNews",
        ],
        "keywords": [
            "inflation",
            "cpi",
            "pce",
            "consumer price",
            "core inflation",
            "deflation",
        ],
    },
    "geopolitics": {
        "label": "ภูมิรัฐศาสตร์ / Safe Haven",
        "impact": "high",
        "tickers": ["GC=F", "SLV", "^VIX"],
        "rss": [
            "https://www.kitco.com/rss/kitconews.xml",
            "https://feeds.feedburner.com/reuters/worldNews",
        ],
        "keywords": [
            "war",
            "conflict",
            "sanction",
            "geopolitic",
            "russia",
            "ukraine",
            "china",
            "middle east",
            "safe haven",
            "tension",
        ],
    },
    "dollar_index": {
        "label": "ดัชนีค่าเงินดอลลาร์ (DXY)",
        "impact": "medium",
        "tickers": ["DX-Y.NYB", "UUP"],
        "rss": [
            "https://www.fxstreet.com/rss/news",
        ],
        "keywords": [
            "dxy",
            "dollar index",
            "usd",
            "us dollar",
            "greenback",
            "dollar strength",
        ],
    },
    "thai_economy": {
        "label": "เศรษฐกิจไทย / ตลาดหุ้นไทย",
        "impact": "medium",
        "tickers": ["EWY", "THD", "SET.BK"],
        "rss": [
            "https://www.bangkokpost.com/rss/data/business.xml",
        ],
        "keywords": [
            "thailand",
            "thai economy",
            "set index",
            "boi",
            "gdp thai",
            "thai baht",
            "thai government",
        ],
    },
    "thai_gold_market": {
        "label": "ตลาดทองไทย",
        "impact": "direct",
        "tickers": ["GC=F", "SGOL"],
        "rss": [
            "https://www.kitco.com/rss/kitconews.xml",
            "https://www.bangkokpost.com/rss/data/business.xml",
        ],
        "keywords": [
            "gold",
            "thai gold",
            "ausiris",
            "hua seng heng",
            "gold shop",
            "ygold",
        ],
    },
}

IMPACT_PRIORITY: dict[str, int] = {"direct": 0, "high": 1, "medium": 2}

# ─── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str
    published_at: str
    ticker: str
    category: str
    impact_level: str
    sentiment_score: float = 0.0  # ปล่อยเป็น 0.0 ไว้ก่อน จะมาอัปเดตทีหลังแบบ Batch

    def estimated_tokens(self) -> int:
        text = f"{self.title} {self.source} {self.published_at} {self.url}"
        if HAS_TIKTOKEN:
            base_tokens = len(_tokenizer.encode(text, disallowed_special=()))
            return int(base_tokens * 1.10)
        else:
            return max(1, len(text) // 4)


@dataclass
class NewsFetchResult:
    fetched_at: str
    total_articles: int
    token_estimate: int
    overall_sentiment: float = 0.0
    by_category: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


# ─── GoldNewsFetcher ──────────────────────────────────────────────────────────


class GoldNewsFetcher:
    def __init__(
        self,
        max_per_category: int = 5,
        max_total_articles: int = 30,
        token_budget: int = 3_000,
        target_date: Optional[str] = None,
    ):
        self.max_per_category = max_per_category
        self.max_total_articles = max_total_articles
        self.token_budget = token_budget
        self.target_date = target_date or get_thai_time().strftime("%Y-%m-%d")

    def _fetch_yfinance_raw(self, ticker_symbol: str) -> list[dict]:
        try:
            import yfinance as yf

            ticker = yf.Ticker(ticker_symbol)
            if hasattr(ticker, "get_news"):
                try:
                    news = ticker.get_news(count=self.max_per_category * 2) or []
                    if news:
                        return news
                except Exception:
                    pass
            return ticker.news or []
        except Exception as e:
            logger.warning(f"yfinance [{ticker_symbol}]: {e}")
            return []

    def _parse_yfinance(
        self, raw: dict, ticker: str, category: str
    ) -> Optional[NewsArticle]:
        content = raw.get("content") or {}
        title = (raw.get("title") or content.get("title") or "").strip()
        if not title:
            return None

        url = (
            raw.get("link")
            or raw.get("url")
            or content.get("canonicalUrl", {}).get("url")
            or content.get("clickThroughUrl", {}).get("url")
            or ""
        )
        if not url.startswith("http"):
            return None

        source = (
            raw.get("publisher")
            or content.get("provider", {}).get("displayName")
            or "unknown"
        )
        raw_pub = (
            raw.get("providerPublishTime")
            or content.get("providerPublishTime")
            or content.get("pubDate")
            or raw.get("pubDate")
        )

        if not raw_pub:
            return None

        try:
            # โยนเข้าฟังก์ชันกลางทีเดียวจบ ไม่ต้องมี Fallback ให้ตัว Z หลุดไปได้อีก
            thai_dt = to_thai_time(raw_pub)
            if thai_dt.strftime("%Y-%m-%d") != self.target_date:
                return None
            pub_str = thai_dt.isoformat()
        except Exception:
            return None

        return NewsArticle(
            title=title,
            url=url,
            source=source,
            published_at=pub_str,
            ticker=ticker,
            category=category,
            impact_level=NEWS_CATEGORIES[category]["impact"],
            sentiment_score=0.0,  # Defer scoring
        )

    def _fetch_rss(
        self, feed_url: str, keywords: list[str], category: str
    ) -> list[NewsArticle]:
        articles: list[NewsArticle] = []
        try:
            # ใช้ requests พร้อม timeout ป้องกัน Thread ค้าง
            resp = requests.get(feed_url, timeout=10)
            feed = feedparser.parse(resp.content)

            if feed.bozo and not feed.entries:
                return []

            for entry in feed.entries:
                title = (getattr(entry, "title", "") or "").strip()
                url = getattr(entry, "link", "") or ""
                if not title or not url.startswith("http"):
                    continue

                if keywords and not any(kw in title.lower() for kw in keywords):
                    continue

                pub_str = ""
                raw_pub = getattr(entry, "published", None) or getattr(
                    entry, "updated", None
                )
                if raw_pub:
                    try:
                        thai_dt = to_thai_time(raw_pub)
                        if thai_dt.strftime("%Y-%m-%d") != self.target_date:
                            continue
                        pub_str = thai_dt.isoformat()
                    except Exception:
                        pass

                if not pub_str.startswith(self.target_date):
                    continue

                source = getattr(feed.feed, "title", None) or feed_url.split("/")[2]

                articles.append(
                    NewsArticle(
                        title=title,
                        url=url,
                        source=source,
                        published_at=pub_str,
                        ticker="rss",
                        category=category,
                        impact_level=NEWS_CATEGORIES[category]["impact"],
                        sentiment_score=0.0,  # Defer scoring
                    )
                )
        except Exception as e:
            logger.warning(f"RSS fetch error [{feed_url}]: {e}")
        return articles

    def fetch_category(self, category: str) -> list[NewsArticle]:
        cat = NEWS_CATEGORIES[category]
        seen_urls: set[str] = set()
        results: list[NewsArticle] = []

        for symbol in cat["tickers"]:
            for raw in self._fetch_yfinance_raw(symbol):
                article = self._parse_yfinance(raw, symbol, category)
                if not article or article.url in seen_urls:
                    continue
                if category == "usd_thb":
                    thai_kws = ["thai", "baht", "thb", "bangkok", "bot"]
                    if not any(k in article.title.lower() for k in thai_kws):
                        continue
                results.append(article)
                seen_urls.add(article.url)

        if len(results) < self.max_per_category:
            keywords = cat.get("keywords", [])
            for feed_url in cat.get("rss", []):
                for article in self._fetch_rss(feed_url, keywords, category):
                    if article.url not in seen_urls:
                        results.append(article)
                        seen_urls.add(article.url)

        results.sort(key=lambda a: a.published_at, reverse=True)
        return results[: self.max_per_category]

    def _apply_global_limit(
        self, by_category: dict[str, list[NewsArticle]]
    ) -> tuple[dict[str, list[NewsArticle]], int]:
        """Greedy Packing Logic"""
        flat: list[tuple[int, str, str, NewsArticle]] = []
        for cat_key, articles in by_category.items():
            priority = IMPACT_PRIORITY.get(NEWS_CATEGORIES[cat_key]["impact"], 9)
            for article in articles:
                date_key = article.published_at or ""
                flat.append((priority, date_key, cat_key, article))

        flat.sort(key=lambda x: (x[1], -x[0]), reverse=True)

        selected: list[tuple[str, NewsArticle]] = []
        total_tokens = 0

        for priority, _date_key, cat_key, article in flat:
            if len(selected) >= self.max_total_articles:
                break

            est = article.estimated_tokens()

            if total_tokens + est > self.token_budget:
                continue

            selected.append((cat_key, article))
            total_tokens += est

        trimmed: dict[str, list[NewsArticle]] = {k: [] for k in by_category}
        for cat_key, article in selected:
            trimmed[cat_key].append(article)

        return trimmed, total_tokens

    def fetch_all(self) -> NewsFetchResult:
        logger.info(
            f"GoldNewsFetcher: fetching {len(NEWS_CATEGORIES)} categories in parallel..."
        )

        # ไม่ต้องโหลด FinBERT ล่วงหน้าตรงนี้แล้ว เก็บไว้รัน Batch ตอนท้าย
        by_category_raw: dict[str, list[NewsArticle]] = {}
        errors: list[str] = []

        def _fetch_single_category(
            cat_key: str,
        ) -> tuple[str, list[NewsArticle], str | None]:
            try:
                articles = self.fetch_category(cat_key)
                return cat_key, articles, None
            except Exception as e:
                return cat_key, [], str(e)

        max_threads = min(len(NEWS_CATEGORIES), 10)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            future_to_cat = {
                executor.submit(_fetch_single_category, cat_key): cat_key
                for cat_key in NEWS_CATEGORIES.keys()
            }

            for future in concurrent.futures.as_completed(future_to_cat):
                cat_key, articles, err = future.result()
                by_category_raw[cat_key] = articles

                if err:
                    errors.append(f"{cat_key}: {err}")
                    logger.error(f"  [{cat_key}] error: {err}")
                    
        # ข้ามการอ่านข่าวซ้ำ
        global_seen_urls = set()
        for cat_key, articles in by_category_raw.items():
            unique_articles = []
            for article in articles:
                if article.url not in global_seen_urls:
                    unique_articles.append(article)
                    global_seen_urls.add(article.url)
            by_category_raw[cat_key] = unique_articles

        # 1. รัน Greedy Packing เพื่อตัดข่าวที่ไม่ใช้ออก
        by_category_trimmed, token_estimate = self._apply_global_limit(by_category_raw)

        # 2. นำข่าวที่ "รอด" จาก Token Budget มารวมกัน
        surviving_articles: list[NewsArticle] = []
        for articles in by_category_trimmed.values():
            surviving_articles.extend(articles)

        # 3. ส่ง Title ไปให้ FinBERT วิเคราะห์รวดเดียวแบบ Batch
        overall_sentiment = 0.0  # กำหนดค่าเริ่มต้น

        if surviving_articles:
            logger.info(
                f"Running batched FinBERT sentiment analysis on {len(surviving_articles)} filtered articles..."
            )
            titles = [a.title for a in surviving_articles]
            scores = score_sentiment_batch(titles)

            # Map คะแนนกลับเข้าไปใน object
            for article, score in zip(surviving_articles, scores):
                article.sentiment_score = score

            # --- คำนวณ Overall Sentiment แบบถ่วงน้ำหนักตาม Impact ---
            impact_weights = {"direct": 1.5, "high": 1.2, "medium": 1.0}
            total_weight = 0.0
            weighted_score_sum = 0.0

            for article in surviving_articles:
                weight = impact_weights.get(article.impact_level, 1.0)
                weighted_score_sum += article.sentiment_score * weight
                total_weight += weight

            if total_weight > 0:
                overall_sentiment = round(weighted_score_sum / total_weight, 4)
            # -------------------------------------------------------------------

        by_category_out: dict = {}
        total = 0
        for cat_key, articles in by_category_trimmed.items():
            cat_meta = NEWS_CATEGORIES[cat_key]
            by_category_out[cat_key] = {
                "label": cat_meta["label"],
                "impact": cat_meta["impact"],
                "tickers": cat_meta["tickers"],
                "count": len(articles),
                "articles": [asdict(a) for a in articles],
            }
            total += len(articles)

        return NewsFetchResult(
            fetched_at=get_thai_time().isoformat(),
            total_articles=total,
            token_estimate=token_estimate,
            overall_sentiment=overall_sentiment,
            by_category=by_category_out,
            errors=errors,
        )

    def to_dict(self) -> dict:
        return asdict(self.fetch_all())


# ─── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import sys

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    fetcher = GoldNewsFetcher(
        max_per_category=3,
        max_total_articles=20,
        token_budget=2_000,
    )

    data = fetcher.to_dict()

    print("\n--- START JSON OUTPUT ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print("--- END JSON OUTPUT ---")
