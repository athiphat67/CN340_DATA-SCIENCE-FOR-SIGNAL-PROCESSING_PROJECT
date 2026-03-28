"""
test_integration.py — Integration tests for the full pipeline
Tests: data → indicators → prompt → MockLLM → decision (end-to-end with mocks).
"""

import json
import os
import pytest
import pandas as pd
import numpy as np

from agent_core.llm.client import MockClient, LLMClientFactory
from agent_core.core.react import ReactOrchestrator, ReactConfig
from agent_core.core.prompt import (
    PromptBuilder,
    RoleRegistry,
    SkillRegistry,
    AIRole,
    RoleDefinition,
)
from data_engine.indicators import TechnicalIndicators


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _create_pipeline(mock_client=None):
    """Create a full pipeline with mock LLM."""
    if mock_client is None:
        mock_client = MockClient()

    _src = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    skill_reg = SkillRegistry()
    skill_path = os.path.join(_src, "agent_core", "config", "skills.json")
    if os.path.exists(skill_path):
        skill_reg.load_from_json(skill_path)

    role_reg = RoleRegistry(skill_reg)
    role_path = os.path.join(_src, "agent_core", "config", "roles.json")
    if os.path.exists(role_path):
        role_reg.load_from_json(role_path)
    else:
        role_reg.register(RoleDefinition(
            name=AIRole.ANALYST,
            title="Test Analyst",
            system_prompt_template="You are a {role_title}. Tools: {available_tools}",
            available_skills=[],
        ))

    prompt_builder = PromptBuilder(role_reg, AIRole.ANALYST)
    orchestrator = ReactOrchestrator(
        llm_client=mock_client,
        prompt_builder=prompt_builder,
        tool_registry={},
        config=ReactConfig(max_iterations=3, max_tool_calls=0),
    )
    return orchestrator


def _make_market_state_from_df(df: pd.DataFrame, portfolio: dict = None) -> dict:
    """Build a market_state dict from OHLCV DataFrame + indicators."""
    calc = TechnicalIndicators(df)
    indicators = calc.to_dict()
    close = float(df["close"].iloc[-1])

    state = {
        "market_data": {
            "spot_price_usd": {
                "source": "test",
                "price_usd_per_oz": close,
                "timestamp": "2025-10-01T00:00:00",
                "confidence": 0.9,
            },
            "forex": {"source": "test", "usd_thb": 34.5},
            "thai_gold_thb": {
                "source": "test",
                "price_thb_per_baht_weight": close * 34.5 / 31.1035 * 15.244 * 0.965,
                "sell_price_thb": 42050.0,
                "buy_price_thb": 41950.0,
            },
        },
        "technical_indicators": indicators,
        "news": {"summary": {}, "by_category": {}},
    }
    if portfolio:
        state["portfolio"] = portfolio
    return state


# ─── Integration Tests ───────────────────────────────────────────────────────

class TestFullPipelineMock:

    def test_data_to_indicators_to_decision(self, sample_ohlcv_df):
        """Full flow: DataFrame → Indicators → Prompt → MockLLM → Decision."""
        market_state = _make_market_state_from_df(sample_ohlcv_df)
        orch = _create_pipeline()
        result = orch.run(market_state)

        assert "final_decision" in result
        fd = result["final_decision"]
        assert fd["signal"] in ("BUY", "SELL", "HOLD")
        assert 0.0 <= fd["confidence"] <= 1.0
        assert "rationale" in fd

    def test_pipeline_with_portfolio(self, sample_ohlcv_df):
        """Pipeline with portfolio data → portfolio should appear in prompt."""
        portfolio = {
            "cash_balance": 1500.0,
            "gold_grams": 0.0,
            "cost_basis_thb": 0.0,
            "unrealized_pnl": 0.0,
            "trades_today": 0,
        }
        market_state = _make_market_state_from_df(sample_ohlcv_df, portfolio)

        # Verify portfolio is in market_state
        assert "portfolio" in market_state
        assert market_state["portfolio"]["cash_balance"] == 1500.0

        orch = _create_pipeline()
        result = orch.run(market_state)
        assert result["final_decision"]["signal"] in ("BUY", "SELL", "HOLD")

    def test_pipeline_with_held_gold(self, sample_ohlcv_df):
        """Pipeline with gold already in portfolio."""
        portfolio = {
            "cash_balance": 500.0,
            "gold_grams": 0.0305,
            "cost_basis_thb": 1000.0,
            "unrealized_pnl": 50.0,
            "trades_today": 1,
        }
        market_state = _make_market_state_from_df(sample_ohlcv_df, portfolio)
        orch = _create_pipeline()
        result = orch.run(market_state)
        assert "final_decision" in result

    def test_pipeline_empty_ohlcv_graceful(self):
        """Empty OHLCV should raise during indicator computation."""
        with pytest.raises(ValueError):
            TechnicalIndicators(pd.DataFrame())

    def test_pipeline_buy_signal_mock(self, sample_ohlcv_df):
        """Mock LLM that returns BUY → verify BUY in output."""
        buy_resp = json.dumps({
            "action": "FINAL_DECISION",
            "signal": "BUY",
            "confidence": 0.85,
            "entry_price": 2300,
            "stop_loss": 2250,
            "take_profit": 2400,
            "rationale": "Strong bullish setup",
        })
        client = MockClient(response_map={
            "THOUGHT_1": buy_resp,
            "THOUGHT_FINAL": buy_resp,
        })
        market_state = _make_market_state_from_df(sample_ohlcv_df)
        orch = _create_pipeline(client)
        result = orch.run(market_state)
        assert result["final_decision"]["signal"] == "BUY"
        assert result["final_decision"]["confidence"] == 0.85


class TestFactoryIntegration:

    def test_mock_provider_via_factory(self):
        """LLMClientFactory.create('mock') should work."""
        client = LLMClientFactory.create("mock")
        assert client.is_available()

    def test_available_providers_includes_mock(self):
        providers = LLMClientFactory.available_providers()
        assert "mock" in providers
        assert "gemini" in providers

    def test_factory_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMClientFactory.create("nonexistent_provider")
