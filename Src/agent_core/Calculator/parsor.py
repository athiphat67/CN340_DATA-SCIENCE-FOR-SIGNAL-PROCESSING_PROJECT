"""
parser.py
---------
Validates and extracts structured data from input.json.
Produces a clean ParsedInput dataclass consumed by downstream signal modules.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Data schemas
# ---------------------------------------------------------------------------

@dataclass
class NewsItem:
    id: str
    source: str
    headline: str
    body: str
    published_at: datetime
    category: str


@dataclass
class MarketState:
    dxy_index: float
    us10y_yield: float
    spx_1d_return: float
    vix: float
    oil_price_usd: float
    btc_usd: float
    gold_etf_flow_m_usd: float


@dataclass
class HistoricalPrices:
    d1: float
    d5: float
    d20: float
    d60: float
    d252: float


@dataclass
class MathOverrides:
    custom_weights: dict[str, float]
    confidence_threshold: float
    max_react_iterations: int


@dataclass
class ParsedInput:
    timestamp: datetime
    current_price_usd: float
    news: list[NewsItem]
    market_state: MarketState
    historical_prices: HistoricalPrices
    math_overrides: MathOverrides
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

REQUIRED_TOP_KEYS = {
    "timestamp", "current_price_usd", "news",
    "market_state", "historical_prices", "math_overrides"
}

REQUIRED_MARKET_KEYS = {
    "dxy_index", "us10y_yield", "spx_1d_return",
    "vix", "oil_price_usd", "btc_usd", "gold_etf_flow_m_usd"
}

VALID_CATEGORIES = {
    "monetary_policy", "geopolitical", "fx_macro",
    "supply_demand", "central_bank", "other"
}


def _validate_schema(raw: dict) -> None:
    missing = REQUIRED_TOP_KEYS - raw.keys()
    if missing:
        raise ValueError(f"input.json missing required keys: {missing}")

    missing_mkt = REQUIRED_MARKET_KEYS - raw["market_state"].keys()
    if missing_mkt:
        raise ValueError(f"market_state missing keys: {missing_mkt}")

    if not isinstance(raw["news"], list) or len(raw["news"]) == 0:
        raise ValueError("'news' must be a non-empty list")

    weights = raw["math_overrides"].get("custom_weights", {})
    weight_sum = sum(weights.values())
    if not (0.99 <= weight_sum <= 1.01):
        raise ValueError(
            f"custom_weights must sum to 1.0 (got {weight_sum:.4f})"
        )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_news(items: list[dict]) -> list[NewsItem]:
    parsed = []
    for raw_item in items:
        cat = raw_item.get("category", "other")
        if cat not in VALID_CATEGORIES:
            cat = "other"
        parsed.append(NewsItem(
            id=raw_item["id"],
            source=raw_item.get("source", "unknown"),
            headline=raw_item["headline"],
            body=raw_item.get("body", ""),
            published_at=datetime.fromisoformat(
                raw_item["published_at"].replace("Z", "+00:00")
            ),
            category=cat,
        ))
    return parsed


def _parse_market_state(raw: dict) -> MarketState:
    return MarketState(**{k: float(v) for k, v in raw.items()})


def _parse_historical(raw: dict) -> HistoricalPrices:
    return HistoricalPrices(
        d1=float(raw["1d_ago"]),
        d5=float(raw["5d_ago"]),
        d20=float(raw["20d_ago"]),
        d60=float(raw["60d_ago"]),
        d252=float(raw["252d_ago"]),
    )


def _parse_overrides(raw: dict) -> MathOverrides:
    return MathOverrides(
        custom_weights=raw["custom_weights"],
        confidence_threshold=float(raw["confidence_threshold"]),
        max_react_iterations=int(raw["max_react_iterations"]),
    )


def load_input(path: str) -> ParsedInput:
    """
    Main entry point. Reads, validates, and returns a ParsedInput.

    Args:
        path: path to input.json

    Returns:
        ParsedInput with fully typed fields

    Raises:
        ValueError: on schema or data errors
        FileNotFoundError: if path doesn't exist
    """
    with open(path, "r", encoding="utf-8") as fh:
        raw: dict[str, Any] = json.load(fh)

    _validate_schema(raw)

    return ParsedInput(
        timestamp=datetime.fromisoformat(
            raw["timestamp"].replace("Z", "+00:00")
        ),
        current_price_usd=float(raw["current_price_usd"]),
        news=_parse_news(raw["news"]),
        market_state=_parse_market_state(raw["market_state"]),
        historical_prices=_parse_historical(raw["historical_prices"]),
        math_overrides=_parse_overrides(raw["math_overrides"]),
        raw=raw,
    )


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "input.json"
    data = load_input(path)
    print(f"[parser] Loaded {len(data.news)} news items")
    print(f"[parser] Current price: ${data.current_price_usd:,.2f}")
    print(f"[parser] Confidence threshold: {data.math_overrides.confidence_threshold}")
