"""
conftest.py — Shared pytest fixtures for Gold Trading Agent tests.
Provides: sample DataFrames, mock LLM clients, sample market states, portfolios.
"""

import os
import sys
import json
import pytest
import numpy as np
import pandas as pd

# Ensure Src/ and Src/data_engine/ are on sys.path
_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
_DATA_ENGINE_DIR = os.path.join(_SRC_DIR, "data_engine")
if _DATA_ENGINE_DIR not in sys.path:
    sys.path.insert(0, _DATA_ENGINE_DIR)


# ─── Sample OHLCV DataFrame ─────────────────────────────────────────────────

@pytest.fixture
def sample_ohlcv_df():
    """Realistic gold OHLCV DataFrame with 100 rows."""
    np.random.seed(42)
    n = 100
    base_price = 2300.0
    prices = base_price + np.cumsum(np.random.randn(n) * 5)
    dates = pd.date_range("2025-07-01", periods=n, freq="B")

    df = pd.DataFrame({
        "open":   prices - np.random.rand(n) * 3,
        "high":   prices + np.random.rand(n) * 8,
        "low":    prices - np.random.rand(n) * 8,
        "close":  prices,
        "volume": np.random.randint(10000, 50000, n),
    }, index=dates)
    return df


@pytest.fixture
def small_ohlcv_df():
    """Small OHLCV DataFrame (10 rows) for quick tests."""
    np.random.seed(123)
    n = 10
    prices = np.array([2300, 2310, 2305, 2320, 2315, 2330, 2325, 2340, 2335, 2350], dtype=float)
    dates = pd.date_range("2025-10-01", periods=n, freq="B")

    df = pd.DataFrame({
        "open":   prices - 2,
        "high":   prices + 5,
        "low":    prices - 5,
        "close":  prices,
        "volume": [20000] * n,
    }, index=dates)
    return df


# ─── Mock LLM Client ────────────────────────────────────────────────────────

@pytest.fixture
def mock_llm_client():
    """MockClient from agent_core with default responses."""
    from agent_core.llm.client import MockClient
    return MockClient()


@pytest.fixture
def mock_llm_buy():
    """MockClient that always returns BUY signal."""
    from agent_core.llm.client import MockClient
    buy_response = json.dumps({
        "action": "FINAL_DECISION",
        "signal": "BUY",
        "confidence": 0.8,
        "entry_price": 2300,
        "stop_loss": 2250,
        "take_profit": 2400,
        "rationale": "Mock BUY signal for testing",
    })
    return MockClient(response_map={
        "THOUGHT_1": buy_response,
        "THOUGHT_FINAL": buy_response,
    })


@pytest.fixture
def mock_llm_sell():
    """MockClient that always returns SELL signal."""
    from agent_core.llm.client import MockClient
    sell_response = json.dumps({
        "action": "FINAL_DECISION",
        "signal": "SELL",
        "confidence": 0.7,
        "entry_price": 2300,
        "stop_loss": 2350,
        "take_profit": 2200,
        "rationale": "Mock SELL signal for testing",
    })
    return MockClient(response_map={
        "THOUGHT_1": sell_response,
        "THOUGHT_FINAL": sell_response,
    })


# ─── Sample Market State ────────────────────────────────────────────────────

@pytest.fixture
def sample_market_state():
    """Market state dict matching the format used by the agent."""
    return {
        "market_data": {
            "spot_price_usd": {
                "source": "test",
                "price_usd_per_oz": 2300.0,
                "timestamp": "2025-10-01T00:00:00",
                "confidence": 0.95,
            },
            "forex": {
                "source": "test",
                "usd_thb": 34.5,
                "timestamp": "2025-10-01T00:00:00",
            },
            "thai_gold_thb": {
                "source": "test",
                "price_thb_per_baht_weight": 42000.0,
                "sell_price_thb": 42050.0,
                "buy_price_thb": 41950.0,
                "spread_thb": 100.0,
            },
        },
        "technical_indicators": {
            "rsi": {"value": 55.0, "signal": "neutral", "period": 14},
            "macd": {
                "macd_line": 1.5,
                "signal_line": 1.2,
                "histogram": 0.3,
                "crossover": "none",
            },
            "bollinger": {
                "upper": 2350.0, "middle": 2300.0, "lower": 2250.0,
                "bandwidth": 0.04, "pct_b": 0.5, "signal": "inside",
            },
            "atr": {"value": 15.0, "period": 14, "volatility_level": "normal"},
            "trend": {
                "ema_20": 2310.0, "ema_50": 2290.0, "sma_200": 2250.0,
                "trend": "uptrend", "golden_cross": True, "death_cross": False,
            },
            "latest_close": 2300.0,
            "calculated_at": "2025-10-01T00:00:00",
        },
        "news": {"summary": {}, "by_category": {}},
    }


@pytest.fixture
def sample_market_state_with_portfolio(sample_market_state):
    """Market state with portfolio data included."""
    state = sample_market_state.copy()
    state["portfolio"] = {
        "cash_balance": 1500.0,
        "gold_grams": 0.0,
        "cost_basis_thb": 0.0,
        "current_value_thb": 0.0,
        "unrealized_pnl": 0.0,
        "trades_today": 0,
    }
    return state


# ─── Sample Portfolio ────────────────────────────────────────────────────────

@pytest.fixture
def sample_portfolio():
    """Default portfolio dict (VC starting capital)."""
    return {
        "cash_balance": 1500.0,
        "gold_grams": 0.0,
        "cost_basis_thb": 0.0,
        "current_value_thb": 0.0,
        "unrealized_pnl": 0.0,
        "trades_today": 0,
    }


# ─── Config paths ───────────────────────────────────────────────────────────

@pytest.fixture
def skills_json_path():
    """Path to skills.json config."""
    return os.path.join(_SRC_DIR, "agent_core", "config", "skills.json")


@pytest.fixture
def roles_json_path():
    """Path to roles.json config."""
    return os.path.join(_SRC_DIR, "agent_core", "config", "roles.json")
