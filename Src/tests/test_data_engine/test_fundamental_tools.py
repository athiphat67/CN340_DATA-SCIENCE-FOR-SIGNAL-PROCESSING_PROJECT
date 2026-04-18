"""
Tests for data_engine/analysis_tools/fundamental_tools.py

Covers:
- _compute_news_relevance: keyword matching, case-insensitivity, empty input,
  unknown category, all 8 known categories
- get_deep_news_by_category: success/error paths, fallback branch, import error,
  relevance_score range
- check_upcoming_economic_calendar: all risk levels (critical/high/medium/low),
  currency filtering, tentative events, hours_ahead parameter, capped events,
  network errors
"""

import sys
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from data_engine.analysis_tools.fundamental_tools import (
    _compute_news_relevance,
    check_upcoming_economic_calendar,
    get_deep_news_by_category,
)

pytestmark = pytest.mark.data_engine

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_gold_articles():
    """5 articles: 3 match gold_price keywords, 2 do not."""
    return [
        {"title": "Gold hits new high as dollar weakens", "summary": "spot gold rose", "description": ""},
        {"title": "XAU/USD consolidating near resistance", "summary": "precious metal demand", "description": ""},
        {"title": "Bullion traders cautious ahead of CPI", "summary": "gold futures flat", "description": ""},
        {"title": "US stocks rally on tech earnings", "summary": "S&P 500 gains", "description": ""},
        {"title": "Oil prices slide on supply data", "summary": "crude oil fell", "description": ""},
    ]


def _make_ff_event(title, country, impact, hours_from_now, time_str="08:30"):
    """Build a ForexFactory-style event dict with a proper ISO-8601 date."""
    dt = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    return {
        "title": title,
        "country": country,
        "impact": impact,
        "date": dt.isoformat(),
        "time": time_str,
        "forecast": "",
        "previous": "",
    }


def _make_mock_response(json_data, raise_for_status=False):
    """Build a mock requests.Response object."""
    mock_resp = MagicMock()
    if raise_for_status:
        import requests
        mock_resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
    else:
        mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = json_data
    return mock_resp


# ─────────────────────────────────────────────────────────────────────────────
# TestComputeNewsRelevance
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeNewsRelevance:
    def test_all_articles_match_returns_1_0(self):
        articles = [
            {"title": "Gold prices surge", "summary": "spot gold climbed", "description": ""},
            {"title": "XAU demand rising", "summary": "bullion buying", "description": ""},
            {"title": "precious metal record", "summary": "gold high", "description": ""},
        ]
        assert _compute_news_relevance(articles, "gold_price") == 1.0

    def test_partial_match_correct_ratio(self, sample_gold_articles):
        # 3 of 5 articles match gold_price keywords
        result = _compute_news_relevance(sample_gold_articles, "gold_price")
        assert result == pytest.approx(0.6, abs=0.001)

    def test_no_match_returns_0_0(self):
        articles = [
            {"title": "US stocks rally strongly", "summary": "S&P gains", "description": ""},
            {"title": "Oil supply data released", "summary": "crude fell", "description": ""},
        ]
        assert _compute_news_relevance(articles, "gold_price") == 0.0

    def test_empty_articles_returns_0_0(self):
        assert _compute_news_relevance([], "gold_price") == 0.0

    def test_unknown_category_returns_0_5(self):
        articles = [{"title": "Anything", "summary": "anything", "description": ""}]
        assert _compute_news_relevance(articles, "totally_new_unknown_category") == 0.5

    def test_case_insensitive_keyword_matching(self):
        articles = [{"title": "GOLD PRICES SURGE GLOBALLY", "summary": "", "description": ""}]
        assert _compute_news_relevance(articles, "gold_price") == 1.0

    @pytest.mark.parametrize("category,keyword_in_title", [
        ("fed_policy", "Federal Reserve raises rates"),
        ("inflation", "CPI data exceeds forecast"),
        ("geopolitics", "Ukraine war escalates tension"),
        ("dollar_index", "DXY dollar index falls sharply"),
        ("thai_economy", "Bank of Thailand holds policy rate"),
        ("thai_gold_market", "ราคาทองคำ Thai gold association"),
        ("usd_thb", "USD/THB baht weakens against dollar"),
        ("usd_thb", "Thai baht depreciation accelerates"),
    ])
    def test_known_category_matches_keyword(self, category, keyword_in_title):
        articles = [{"title": keyword_in_title, "summary": "", "description": ""}]
        result = _compute_news_relevance(articles, category)
        assert result == 1.0, f"Expected 1.0 for category='{category}', got {result}"

    def test_match_via_summary_field(self):
        """A keyword in 'summary' (not title) should still count as a match."""
        articles = [{"title": "Market recap", "summary": "spot gold prices rose sharply", "description": ""}]
        assert _compute_news_relevance(articles, "gold_price") == 1.0

    def test_match_via_description_field(self):
        """A keyword in 'description' should count as a match."""
        articles = [{"title": "Commodities", "summary": "", "description": "XAU futures gained 0.5%"}]
        assert _compute_news_relevance(articles, "gold_price") == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# TestGetDeepNewsByCategory
# ─────────────────────────────────────────────────────────────────────────────

_FETCH_NEWS_PATH = "data_engine.tools.fetch_news.fetch_news"


class TestGetDeepNewsByCategory:
    def test_success_returns_expected_structure(self):
        """Happy path: fetch_news returns deep_news with articles."""
        mock_articles = [
            {"title": "Gold surges on Fed news", "summary": "spot gold rose", "description": ""},
        ]
        mock_result = {
            "deep_news": {"articles": mock_articles, "count": 1},
            "error": None,
        }
        with patch(_FETCH_NEWS_PATH, return_value=mock_result):
            result = get_deep_news_by_category("gold_price")

        assert result["status"] == "success"
        assert result["category"] == "gold_price"
        assert "articles" in result
        assert "count" in result
        assert "relevance_score" in result

    def test_relevance_score_between_0_and_1(self):
        mock_articles = [
            {"title": "Gold prices rise on safe haven demand", "summary": "bullion", "description": ""},
        ]
        mock_result = {
            "deep_news": {"articles": mock_articles, "count": 1},
            "error": None,
        }
        with patch(_FETCH_NEWS_PATH, return_value=mock_result):
            result = get_deep_news_by_category("gold_price")

        assert 0.0 <= result["relevance_score"] <= 1.0

    def test_empty_articles_returns_zero_count(self):
        mock_result = {
            "deep_news": {"articles": [], "count": 0},
            "error": None,
        }
        with patch(_FETCH_NEWS_PATH, return_value=mock_result):
            result = get_deep_news_by_category("gold_price")

        assert result["count"] == 0
        assert result["articles"] == []

    def test_deep_news_error_key_returns_error(self):
        """When fetch_news returns deep_news_error, wrap it into status=error."""
        mock_result = {
            "deep_news_error": "RSS feed connection timeout",
        }
        with patch(_FETCH_NEWS_PATH, return_value=mock_result):
            result = get_deep_news_by_category("fed_policy")

        assert result["status"] == "error"
        assert "RSS feed connection timeout" in result.get("message", "")

    def test_generic_exception_returns_error(self):
        """Network error raised inside fetch_news → status=error with message."""
        with patch(_FETCH_NEWS_PATH, side_effect=ConnectionError("network down")):
            result = get_deep_news_by_category("gold_price")

        assert result["status"] == "error"
        assert "network down" in result["message"]

    def test_fallback_branch_no_known_keys(self):
        """When response has neither deep_news nor deep_news_error → fallback success."""
        mock_result = {"totally_unexpected_key": "something"}
        with patch(_FETCH_NEWS_PATH, return_value=mock_result):
            result = get_deep_news_by_category("inflation")

        assert result["status"] == "success"
        assert result["count"] == 0
        assert "note" in result

    def test_import_error_returns_error(self):
        """Simulate module import failure for fetch_news."""
        saved = sys.modules.get("data_engine.tools.fetch_news")
        try:
            sys.modules["data_engine.tools.fetch_news"] = None  # type: ignore[assignment]
            result = get_deep_news_by_category("gold_price")
        finally:
            if saved is None:
                sys.modules.pop("data_engine.tools.fetch_news", None)
            else:
                sys.modules["data_engine.tools.fetch_news"] = saved

        assert result["status"] == "error"
        assert "import" in result["message"].lower() or "load" in result["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# TestCheckUpcomingEconomicCalendar
# ─────────────────────────────────────────────────────────────────────────────

_REQUESTS_PATH = "data_engine.analysis_tools.fundamental_tools.requests.get"


class TestCheckUpcomingEconomicCalendar:
    def test_network_error_returns_error_dict(self):
        import requests as req
        with patch(_REQUESTS_PATH, side_effect=req.ConnectionError("timeout")):
            result = check_upcoming_economic_calendar()

        assert result["status"] == "error"
        assert "ForexFactory" in result["message"]

    def test_http_error_returns_error_dict(self):
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("403")
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar()

        assert result["status"] == "error"

    def test_empty_json_returns_low_risk(self):
        mock_resp = _make_mock_response([])
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar()

        assert result["status"] == "success"
        assert result["risk_level"] == "low"
        assert result["events"] == []

    def test_critical_when_high_usd_within_2h(self):
        events = [_make_ff_event("Non-Farm Payrolls", "USD", "High", hours_from_now=1.0)]
        mock_resp = _make_mock_response(events)
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar(hours_ahead=24)

        assert result["risk_level"] == "critical"
        assert result["is_safe_to_trade"] is False
        assert result["trade_action"] == "avoid"
        assert result["high_impact_usd_count"] == 1

    def test_high_when_high_usd_beyond_2h(self):
        events = [_make_ff_event("FOMC Minutes", "USD", "High", hours_from_now=10.0)]
        mock_resp = _make_mock_response(events)
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar(hours_ahead=24)

        assert result["risk_level"] == "high"
        assert result["is_safe_to_trade"] is False
        assert result["trade_action"] == "reduce"

    def test_medium_from_non_usd_high_impact(self):
        events = [_make_ff_event("ECB Rate Decision", "EUR", "High", hours_from_now=3.0)]
        mock_resp = _make_mock_response(events)
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar(hours_ahead=24)

        assert result["risk_level"] == "medium"
        assert result["is_safe_to_trade"] is True
        assert result["trade_action"] == "caution"

    def test_low_when_only_irrelevant_currencies(self):
        """Events from currencies not in GOLD_RELEVANT_CURRENCIES → low risk."""
        events = [
            _make_ff_event("NZ GDP", "NZD", "High", hours_from_now=2.0),
            _make_ff_event("AU CPI", "AUD", "High", hours_from_now=5.0),
        ]
        mock_resp = _make_mock_response(events)
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar(hours_ahead=24)

        assert result["risk_level"] == "low"
        assert result["trade_action"] == "proceed"
        assert result["events"] == []

    def test_events_capped_at_15(self):
        """Output events list should never exceed 15 items."""
        events = [
            _make_ff_event(f"USD Event {i}", "USD", "Medium", hours_from_now=float(i))
            for i in range(1, 21)  # 20 events
        ]
        mock_resp = _make_mock_response(events)
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar(hours_ahead=24)

        assert len(result["events"]) <= 15

    def test_tentative_high_usd_included(self):
        """Tentative High USD events should appear in the result."""
        tentative_event = {
            "title": "Fed Speech",
            "country": "USD",
            "impact": "High",
            "date": datetime.now(timezone.utc).isoformat(),
            "time": "Tentative",
            "forecast": "",
            "previous": "",
        }
        mock_resp = _make_mock_response([tentative_event])
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar(hours_ahead=24)

        tentative_results = [e for e in result["events"] if e.get("is_tentative")]
        assert len(tentative_results) >= 1

    def test_hours_ahead_parameter_is_respected(self):
        """An event 36h away should be excluded with hours_ahead=24 but included with hours_ahead=48."""
        events = [_make_ff_event("US CPI", "USD", "High", hours_from_now=36.0)]
        mock_resp = _make_mock_response(events)

        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result_24 = check_upcoming_economic_calendar(hours_ahead=24)

        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result_48 = check_upcoming_economic_calendar(hours_ahead=48)

        high_usd_24 = [e for e in result_24["events"] if not e.get("is_tentative") and e["country"] == "USD"]
        high_usd_48 = [e for e in result_48["events"] if not e.get("is_tentative") and e["country"] == "USD"]
        assert len(high_usd_24) == 0
        assert len(high_usd_48) == 1

    def test_invalid_date_silently_skipped(self):
        """An event with an unparseable date is silently skipped; valid events still appear."""
        bad_event = {
            "title": "Broken Event",
            "country": "USD",
            "impact": "High",
            "date": "not-a-date",
            "time": "08:30",
            "forecast": "",
            "previous": "",
        }
        good_event = _make_ff_event("NFP", "USD", "High", hours_from_now=5.0)
        mock_resp = _make_mock_response([bad_event, good_event])

        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar(hours_ahead=24)

        # Only the valid event should appear (bad_event skipped)
        titles = [e["title"] for e in result["events"] if not e.get("is_tentative")]
        assert "NFP" in titles
        assert "Broken Event" not in titles

    def test_result_contains_interpretation_string(self):
        mock_resp = _make_mock_response([])
        with patch(_REQUESTS_PATH, return_value=mock_resp):
            result = check_upcoming_economic_calendar()

        assert isinstance(result.get("interpretation"), str)
        assert len(result["interpretation"]) > 0
