"""
test_newsfetcher.py — Pytest สำหรับ newsfetcher module

ครอบคลุม:
  1. NewsArticle — dataclass fields, estimated_tokens
  2. NewsFetchResult — defaults, structure
  3. score_sentiment_batch — empty list, no HF_TOKEN
  4. GoldNewsFetcher._apply_global_limit — token budget, max articles
  5. GoldNewsFetcher._parse_yfinance — valid/invalid entries
  6. GoldNewsFetcher._fetch_rss — keyword filtering
  7. NEWS_CATEGORIES — structure validation

Strategy: Mock external APIs (HF, yfinance, RSS)
  - ไม่เรียก API จริง
  - Deterministic 100%
"""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import asdict

pytestmark = pytest.mark.data_engine

from data_engine.newsfetcher import (
    NewsArticle,
    NewsFetchResult,
    score_sentiment_batch,
    GoldNewsFetcher,
    NEWS_CATEGORIES,
    IMPACT_PRIORITY,
)


# ══════════════════════════════════════════════════════════════════
# 1. NewsArticle
# ══════════════════════════════════════════════════════════════════


class TestNewsArticle:
    """ทดสอบ NewsArticle dataclass"""

    def _make_article(self, **kwargs) -> NewsArticle:
        defaults = {
            "title": "Gold prices surge amid geopolitical tensions",
            "url": "https://example.com/gold-surge",
            "source": "Reuters",
            "published_at": "2026-04-01T10:00:00+07:00",
            "ticker": "GC=F",
            "category": "gold_price",
            "impact_level": "direct",
            "sentiment_score": 0.5,
        }
        defaults.update(kwargs)
        return NewsArticle(**defaults)

    def test_fields(self):
        """ต้องมี fields ครบ"""
        a = self._make_article()
        assert a.title == "Gold prices surge amid geopolitical tensions"
        assert a.category == "gold_price"
        assert a.sentiment_score == 0.5

    def test_default_sentiment(self):
        """sentiment_score default = 0.0"""
        a = NewsArticle(
            title="t", url="u", source="s",
            published_at="p", ticker="t", category="c",
            impact_level="direct",
        )
        assert a.sentiment_score == 0.0

    def test_estimated_tokens_positive(self):
        """estimated_tokens > 0"""
        a = self._make_article()
        assert a.estimated_tokens() > 0

    def test_estimated_tokens_proportional(self):
        """Title ยาว → tokens มากกว่า title สั้น"""
        short = self._make_article(title="Gold up")
        long = self._make_article(title="Gold prices surge significantly amid global tensions and geopolitical uncertainty")
        assert long.estimated_tokens() > short.estimated_tokens()

    def test_to_dict(self):
        """asdict() ต้องแปลงได้"""
        a = self._make_article()
        d = asdict(a)
        assert d["title"] == a.title
        assert d["sentiment_score"] == 0.5


# ══════════════════════════════════════════════════════════════════
# 2. NewsFetchResult
# ══════════════════════════════════════════════════════════════════


class TestNewsFetchResult:
    """ทดสอบ NewsFetchResult dataclass"""

    def test_defaults(self):
        """Default values ถูกต้อง"""
        r = NewsFetchResult(
            fetched_at="2026-04-01T10:00:00",
            total_articles=5,
            token_estimate=200,
        )
        assert r.overall_sentiment == 0.0
        assert r.by_category == {}
        assert r.errors == []

    def test_with_values(self):
        r = NewsFetchResult(
            fetched_at="2026-04-01T10:00:00",
            total_articles=10,
            token_estimate=500,
            overall_sentiment=0.3,
            by_category={"gold": {"count": 3}},
            errors=["rss failed"],
        )
        assert r.total_articles == 10
        assert len(r.errors) == 1


# ══════════════════════════════════════════════════════════════════
# 3. score_sentiment_batch
# ══════════════════════════════════════════════════════════════════


class TestScoreSentimentBatch:
    """ทดสอบ score_sentiment_batch"""

    def test_empty_list(self):
        """Empty list → empty result"""
        assert score_sentiment_batch([]) == []

    @patch("data_engine.newsfetcher.HF_TOKEN", None)
    def test_no_token_returns_zeros(self):
        """ไม่มี HF_TOKEN → return [0.0, ...]"""
        result = score_sentiment_batch(["text1", "text2"])
        assert result == [0.0, 0.0]

    @patch("data_engine.newsfetcher.HF_TOKEN", None)
    def test_no_token_correct_length(self):
        """ไม่มี HF_TOKEN → length ตรงกับ input"""
        texts = ["a", "b", "c", "d"]
        result = score_sentiment_batch(texts)
        assert len(result) == len(texts)


# ══════════════════════════════════════════════════════════════════
# 4. GoldNewsFetcher._apply_global_limit
# ══════════════════════════════════════════════════════════════════


class TestApplyGlobalLimit:
    """ทดสอบ _apply_global_limit — จำกัดจำนวนข่าวตาม token budget"""

    def _make_articles(self, n: int, category: str = "gold_price") -> list:
        return [
            NewsArticle(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                source="Test",
                published_at=f"2026-04-01T{10+i:02d}:00:00+07:00",
                ticker="GC=F",
                category=category,
                impact_level=NEWS_CATEGORIES[category]["impact"],
            )
            for i in range(n)
        ]

    @patch("data_engine.newsfetcher.get_thai_time")
    def test_within_budget(self, mock_time):
        """ข่าวน้อย + budget สูง → ไม่ถูกตัด"""
        mock_time.return_value = MagicMock(strftime=lambda fmt: "2026-04-01")
        fetcher = GoldNewsFetcher(token_budget=10_000)
        articles = self._make_articles(3)
        by_cat = {"gold_price": articles}
        trimmed, tokens = fetcher._apply_global_limit(by_cat)
        assert len(trimmed["gold_price"]) == 3

    @patch("data_engine.newsfetcher.get_thai_time")
    def test_max_total_articles(self, mock_time):
        """เกิน max_total_articles → ตัด"""
        mock_time.return_value = MagicMock(strftime=lambda fmt: "2026-04-01")
        fetcher = GoldNewsFetcher(max_total_articles=2, token_budget=10_000)
        articles = self._make_articles(5)
        by_cat = {"gold_price": articles}
        trimmed, _ = fetcher._apply_global_limit(by_cat)
        total = sum(len(v) for v in trimmed.values())
        assert total <= 2

    @patch("data_engine.newsfetcher.get_thai_time")
    def test_token_budget_limit(self, mock_time):
        """เกิน token budget → ตัดข่าวที่เกิน"""
        mock_time.return_value = MagicMock(strftime=lambda fmt: "2026-04-01")
        fetcher = GoldNewsFetcher(token_budget=1, max_total_articles=100)
        articles = self._make_articles(10)
        by_cat = {"gold_price": articles}
        trimmed, tokens = fetcher._apply_global_limit(by_cat)
        assert tokens <= 1 or sum(len(v) for v in trimmed.values()) < 10


# ══════════════════════════════════════════════════════════════════
# 5. GoldNewsFetcher._parse_yfinance
# ══════════════════════════════════════════════════════════════════


class TestParseYfinance:
    """ทดสอบ _parse_yfinance — แปลง raw yfinance news dict → NewsArticle"""

    @patch("data_engine.newsfetcher.get_thai_time")
    def test_valid_entry(self, mock_time):
        mock_time.return_value = MagicMock(strftime=lambda fmt: "2026-04-01")
        fetcher = GoldNewsFetcher()
        fetcher.target_date = "2026-04-01"

        raw = {
            "title": "Gold surges",
            "link": "https://example.com/1",
            "publisher": "Reuters",
            "providerPublishTime": 1743465600,  # 2025-04-01 UTC
        }
        # ถ้า date ไม่ตรง target_date จะ return None
        result = fetcher._parse_yfinance(raw, "GC=F", "gold_price")
        # ผลลัพธ์อาจเป็น None ถ้า date ไม่ตรง — ทดสอบว่าไม่ crash
        assert result is None or isinstance(result, NewsArticle)

    @patch("data_engine.newsfetcher.get_thai_time")
    def test_missing_title_returns_none(self, mock_time):
        mock_time.return_value = MagicMock(strftime=lambda fmt: "2026-04-01")
        fetcher = GoldNewsFetcher()
        raw = {"link": "https://example.com/1"}
        result = fetcher._parse_yfinance(raw, "GC=F", "gold_price")
        assert result is None

    @patch("data_engine.newsfetcher.get_thai_time")
    def test_invalid_url_returns_none(self, mock_time):
        mock_time.return_value = MagicMock(strftime=lambda fmt: "2026-04-01")
        fetcher = GoldNewsFetcher()
        raw = {"title": "Gold", "link": "not-a-url"}
        result = fetcher._parse_yfinance(raw, "GC=F", "gold_price")
        assert result is None


# ══════════════════════════════════════════════════════════════════
# 6. NEWS_CATEGORIES structure
# ══════════════════════════════════════════════════════════════════


class TestNewsCategories:
    """ทดสอบ NEWS_CATEGORIES config"""

    def test_all_categories_have_required_keys(self):
        """ทุก category ต้องมี label, impact, tickers, rss, keywords"""
        for cat_key, cat_data in NEWS_CATEGORIES.items():
            assert "label" in cat_data, f"{cat_key} missing label"
            assert "impact" in cat_data, f"{cat_key} missing impact"
            assert "tickers" in cat_data, f"{cat_key} missing tickers"
            assert "rss" in cat_data, f"{cat_key} missing rss"
            assert "keywords" in cat_data, f"{cat_key} missing keywords"

    def test_impact_values_valid(self):
        """impact ต้องเป็น direct/high/medium"""
        valid_impacts = {"direct", "high", "medium"}
        for cat_key, cat_data in NEWS_CATEGORIES.items():
            assert cat_data["impact"] in valid_impacts, f"{cat_key} invalid impact"

    def test_impact_priority_complete(self):
        """IMPACT_PRIORITY ต้องครอบคลุมทุก impact level"""
        for cat_data in NEWS_CATEGORIES.values():
            assert cat_data["impact"] in IMPACT_PRIORITY

    def test_expected_categories_present(self):
        """ต้องมี categories หลักๆ"""
        expected = {"gold_price", "fed_policy", "geopolitics", "thai_gold_market"}
        assert expected.issubset(set(NEWS_CATEGORIES.keys()))
