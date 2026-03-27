"""
test_react.py — Unit tests for ReactOrchestrator and extract_json
Tests: JSON parsing, zero-tool run, final decision, max iterations, fallback.
"""

import json
import pytest

from agent_core.core.react import (
    ReactOrchestrator,
    ReactConfig,
    extract_json,
    ToolResult,
)
from agent_core.core.prompt import (
    PromptBuilder,
    PromptPackage,
    RoleRegistry,
    SkillRegistry,
    AIRole,
    RoleDefinition,
)
from agent_core.llm.client import MockClient


# ─── extract_json ────────────────────────────────────────────────────────────

class TestExtractJSON:

    def test_plain_json(self):
        raw = '{"signal": "BUY", "confidence": 0.8}'
        result = extract_json(raw)
        assert result["signal"] == "BUY"
        assert result["confidence"] == 0.8

    def test_markdown_fenced_json(self):
        raw = '```json\n{"signal": "SELL", "confidence": 0.7}\n```'
        result = extract_json(raw)
        assert result["signal"] == "SELL"

    def test_markdown_fenced_no_lang(self):
        raw = '```\n{"signal": "HOLD", "confidence": 0.5}\n```'
        result = extract_json(raw)
        assert result["signal"] == "HOLD"

    def test_json_with_surrounding_text(self):
        raw = 'Here is my analysis:\n{"signal": "BUY", "confidence": 0.9}\nEnd.'
        result = extract_json(raw)
        assert result["signal"] == "BUY"

    def test_invalid_json_returns_parse_error(self):
        raw = "This is not JSON at all"
        result = extract_json(raw)
        assert result.get("_parse_error") is True

    def test_empty_string(self):
        result = extract_json("")
        assert result == {}

    def test_none_input(self):
        result = extract_json(None)
        assert result == {}

    def test_nested_json(self):
        raw = '{"action": "FINAL_DECISION", "data": {"key": "value"}}'
        result = extract_json(raw)
        assert result["action"] == "FINAL_DECISION"
        assert result["data"]["key"] == "value"


# ─── Helper: create a minimal ReactOrchestrator ─────────────────────────────

def _make_orchestrator(mock_client=None, max_iterations=5, max_tool_calls=0):
    """Create a ReactOrchestrator with mock components."""
    if mock_client is None:
        mock_client = MockClient()

    skill_reg = SkillRegistry()
    role_reg = RoleRegistry(skill_reg)
    role_reg.register(RoleDefinition(
        name=AIRole.ANALYST,
        title="Test Analyst",
        system_prompt_template="You are a {role_title}. Tools: {available_tools}",
        available_skills=[],
    ))
    prompt_builder = PromptBuilder(role_reg, AIRole.ANALYST)

    return ReactOrchestrator(
        llm_client=mock_client,
        prompt_builder=prompt_builder,
        tool_registry={},
        config=ReactConfig(
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
        ),
    )


# ─── ReactOrchestrator.run ───────────────────────────────────────────────────

class TestReactOrchestratorRun:

    def test_zero_tools_single_decision(self, sample_market_state):
        """With max_tool_calls=0, should return a decision in 1 iteration."""
        orch = _make_orchestrator(max_tool_calls=0)
        result = orch.run(sample_market_state)

        assert "final_decision" in result
        assert "react_trace" in result
        assert result["iterations_used"] == 1
        assert result["tool_calls_used"] == 0

        fd = result["final_decision"]
        assert fd["signal"] in ("BUY", "SELL", "HOLD")
        assert 0.0 <= fd["confidence"] <= 1.0

    def test_run_with_buy_signal(self, sample_market_state):
        """Mock client returns BUY → final decision should be BUY."""
        buy_resp = json.dumps({
            "action": "FINAL_DECISION",
            "signal": "BUY",
            "confidence": 0.85,
            "rationale": "Strong signal",
        })
        client = MockClient(response_map={
            "THOUGHT_1": buy_resp,
            "THOUGHT_FINAL": buy_resp,
        })
        orch = _make_orchestrator(client, max_tool_calls=0)
        result = orch.run(sample_market_state)
        assert result["final_decision"]["signal"] == "BUY"

    def test_run_with_sell_signal(self, sample_market_state):
        client = MockClient(response_map={
            "THOUGHT_FINAL": json.dumps({
                "action": "FINAL_DECISION",
                "signal": "SELL",
                "confidence": 0.7,
                "rationale": "Overbought",
            }),
        })
        orch = _make_orchestrator(client, max_tool_calls=0)
        result = orch.run(sample_market_state)
        assert result["final_decision"]["signal"] == "SELL"

    def test_run_max_iterations_forced(self, sample_market_state):
        """When LLM never says FINAL_DECISION, should force after max iterations."""
        # Mock returns CALL_TOOL every time → hits max iterations
        tool_resp = json.dumps({
            "action": "CALL_TOOL",
            "thought": "Need more data",
            "tool_name": "fake_tool",
            "tool_args": {},
        })
        final_resp = json.dumps({
            "action": "FINAL_DECISION",
            "signal": "HOLD",
            "confidence": 0.3,
            "rationale": "Forced",
        })
        client = MockClient(response_map={
            "THOUGHT_1": tool_resp,
            "THOUGHT_2": tool_resp,
            "THOUGHT_3": tool_resp,
            "THOUGHT_FINAL": final_resp,
        })
        orch = _make_orchestrator(client, max_iterations=3, max_tool_calls=2)
        result = orch.run(sample_market_state)

        assert "final_decision" in result
        assert result["final_decision"]["signal"] in ("BUY", "SELL", "HOLD")

    def test_result_has_required_keys(self, sample_market_state):
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        assert "final_decision" in result
        assert "react_trace" in result
        assert "iterations_used" in result
        assert "tool_calls_used" in result

    def test_react_trace_is_list(self, sample_market_state):
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        assert isinstance(result["react_trace"], list)
        assert len(result["react_trace"]) > 0


# ─── _build_decision / _fallback_decision ────────────────────────────────────

class TestBuildDecision:

    def test_build_decision_with_all_fields(self):
        parsed = {
            "signal": "BUY",
            "confidence": 0.9,
            "entry_price": 2300,
            "stop_loss": 2250,
            "take_profit": 2400,
            "rationale": "Strong bullish signal",
        }
        result = ReactOrchestrator._build_decision(parsed)
        assert result["signal"] == "BUY"
        assert result["confidence"] == 0.9
        assert result["entry_price"] == 2300
        assert result["rationale"] == "Strong bullish signal"

    def test_build_decision_defaults(self):
        result = ReactOrchestrator._build_decision({})
        assert result["signal"] == "HOLD"
        assert result["confidence"] == 0.0
        assert result["entry_price"] is None

    def test_fallback_decision(self):
        result = ReactOrchestrator._fallback_decision("test reason")
        assert result["signal"] == "HOLD"
        assert result["confidence"] == 0.0
        assert "test reason" in result["rationale"]
