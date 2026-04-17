"""
test_react_orchestrator.py — Pytest for agent_core/core/react.py

Covers:
  1. AgentDecision — Pydantic model: confidence clamp, signal uppercase,
     action inference/degradation, parse_failed flag
  2. parse_agent_response — JSON extraction, markdown fence stripping,
     balanced-brace scanner, fallback to SAFE_HOLD
  3. StateReadinessChecker — is_ready() with technical_indicators + HTF coverage
  4. ReactOrchestrator.run() — fast path, readiness skip, CALL_TOOL loop,
     CALL_TOOLS parallel, max_iterations guard
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call
from dataclasses import dataclass
from typing import Optional

from agent_core.core.react import (
    AgentDecision,
    parse_agent_response,
    StateReadinessChecker,
    ReadinessConfig,
    ReactOrchestrator,
    ReactConfig,
    ToolResult,
)

pytestmark = [pytest.mark.unit]


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _llm_response(text: str) -> MagicMock:
    """Create a minimal mock LLMResponse with required attributes."""
    resp = MagicMock()
    resp.text = text
    resp.prompt_text = ""
    resp.token_input = 0
    resp.token_output = 0
    resp.token_total = 0
    resp.model = "test_model"
    resp.provider = "test"
    return resp


def _hold_json(**kwargs) -> str:
    """Return a valid HOLD FINAL_DECISION JSON string."""
    payload = {
        "action": "FINAL_DECISION",
        "signal": "HOLD",
        "confidence": 0.0,
        "rationale": "test hold",
    }
    payload.update(kwargs)
    return json.dumps(payload)


def _buy_json(**kwargs) -> str:
    """Return a valid BUY FINAL_DECISION JSON string."""
    payload = {
        "action": "FINAL_DECISION",
        "signal": "BUY",
        "confidence": 0.8,
        "rationale": "test buy",
    }
    payload.update(kwargs)
    return json.dumps(payload)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def minimal_market_state():
    """Bare market_state that passes RiskManager without triggering guards."""
    return {
        "time": "10:00",
        "date": "2026-04-13",
        "interval": "5m",
        "portfolio": {
            "cash_balance": 5000.0,
            "gold_grams": 0.0,
            "unrealized_pnl": 0.0,
        },
        "market_data": {
            "thai_gold_thb": {
                "sell_price_thb": 72000.0,
                "buy_price_thb": 71800.0,
            },
            "forex": {"usd_thb": 34.0},
        },
        "technical_indicators": {},
    }


@pytest.fixture
def mock_prompt_builder():
    """Prompt builder mock with build_thought and build_final_decision."""
    pb = MagicMock()
    pb.build_thought.return_value = MagicMock(system="sys", user="user")
    pb.build_final_decision.return_value = MagicMock(system="sys", user="user")
    return pb


@pytest.fixture
def mock_llm_client():
    """LLM client mock whose .call() returns a mock LLMResponse."""
    client = MagicMock()
    return client


@pytest.fixture
def fast_path_orchestrator(mock_llm_client, mock_prompt_builder):
    """ReactOrchestrator configured for fast path (max_tool_calls=0)."""
    cfg = ReactConfig(max_tool_calls=0)
    return ReactOrchestrator(
        llm_client=mock_llm_client,
        prompt_builder=mock_prompt_builder,
        tool_registry={},
        config=cfg,
    )


# ─────────────────────────────────────────────────────────────────────
# TestAgentDecision — Pydantic validators
# ─────────────────────────────────────────────────────────────────────


class TestAgentDecision:
    """Unit tests for AgentDecision field_validators and model_validators."""

    def test_confidence_clamped_above_1(self):
        """Confidence > 1.0 must be clamped to 1.0."""
        d = AgentDecision(action="FINAL_DECISION", signal="HOLD", confidence=1.5)
        assert d.confidence == 1.0

    def test_confidence_clamped_below_0(self):
        """Confidence < 0.0 must be clamped to 0.0."""
        d = AgentDecision(action="FINAL_DECISION", signal="HOLD", confidence=-0.2)
        assert d.confidence == 0.0

    def test_confidence_valid_midrange(self):
        """Confidence in [0, 1] must pass through unchanged."""
        d = AgentDecision(action="FINAL_DECISION", signal="HOLD", confidence=0.75)
        assert d.confidence == 0.75

    def test_confidence_none_becomes_zero(self):
        """confidence=None must coerce to 0.0."""
        d = AgentDecision(action="FINAL_DECISION", signal="HOLD", confidence=None)
        assert d.confidence == 0.0

    def test_signal_lowercase_uppercased(self):
        """Signal 'buy' must be normalised to 'BUY'."""
        d = AgentDecision(action="FINAL_DECISION", signal="buy", confidence=0.8)
        assert d.signal == "BUY"

    def test_signal_mixed_case_uppercased(self):
        """Signal 'Sell' must be normalised to 'SELL'."""
        d = AgentDecision(action="FINAL_DECISION", signal="Sell", confidence=0.8)
        assert d.signal == "SELL"

    def test_action_inferred_from_signal_only(self):
        """Dict with 'signal' but no 'action' → action inferred as FINAL_DECISION."""
        d = AgentDecision(**{"signal": "BUY", "confidence": 0.8})
        assert d.action == "FINAL_DECISION"

    def test_call_tool_without_tool_name_degraded_to_hold(self):
        """CALL_TOOL with no tool_name → degrade to FINAL_DECISION/HOLD."""
        d = AgentDecision(action="CALL_TOOL", tool_name=None, confidence=0.5)
        assert d.action == "FINAL_DECISION"
        assert d.signal == "HOLD"

    def test_call_tools_without_tools_list_degraded_to_hold(self):
        """CALL_TOOLS with tools=None and no tool_name → degrade to FINAL_DECISION/HOLD."""
        d = AgentDecision(action="CALL_TOOLS", tools=None, tool_name=None, confidence=0.5)
        assert d.action == "FINAL_DECISION"
        assert d.signal == "HOLD"

    def test_call_tools_without_list_but_with_tool_name_degraded_to_call_tool(self):
        """CALL_TOOLS with tools=None but tool_name present → degrade to CALL_TOOL."""
        d = AgentDecision(action="CALL_TOOLS", tools=None, tool_name="get_price", confidence=0.5)
        assert d.action == "CALL_TOOL"

    def test_final_decision_signal_none_becomes_hold(self):
        """FINAL_DECISION with signal=None → signal defaults to 'HOLD'."""
        d = AgentDecision(action="FINAL_DECISION", signal=None, confidence=0.0)
        assert d.signal == "HOLD"

    def test_parse_failed_default_is_false(self):
        """parse_failed must default to False for normal construction."""
        d = AgentDecision(action="FINAL_DECISION", signal="HOLD", confidence=0.0)
        assert d.parse_failed is False

    def test_to_decision_dict_keys(self):
        """to_decision_dict() must contain the keys RiskManager.evaluate() expects."""
        d = AgentDecision(action="FINAL_DECISION", signal="BUY", confidence=0.8, rationale="ok")
        result = d.to_decision_dict()
        expected_keys = {"signal", "confidence", "entry_price", "stop_loss", "take_profit", "rationale"}
        assert expected_keys.issubset(result.keys())

    def test_to_decision_dict_signal_holds_value(self):
        """to_decision_dict()['signal'] must reflect the validated signal."""
        d = AgentDecision(action="FINAL_DECISION", signal="sell", confidence=0.9)
        assert d.to_decision_dict()["signal"] == "SELL"


# ─────────────────────────────────────────────────────────────────────
# TestParseAgentResponse — JSON extraction & fallback chain
# ─────────────────────────────────────────────────────────────────────


class TestParseAgentResponse:
    """Unit tests for parse_agent_response() fallback chain."""

    def test_valid_hold_json_parsed(self):
        """Plain valid HOLD JSON string → AgentDecision with HOLD."""
        raw = _hold_json()
        result = parse_agent_response(raw)
        assert result.signal == "HOLD"
        assert result.parse_failed is False

    def test_valid_buy_json_parsed(self):
        """Valid BUY JSON → AgentDecision with BUY signal."""
        raw = _buy_json()
        result = parse_agent_response(raw)
        assert result.signal == "BUY"
        assert result.confidence == 0.8

    def test_markdown_code_fence_stripped(self):
        """JSON wrapped in ```json ... ``` must be parsed correctly."""
        raw = "```json\n" + _hold_json() + "\n```"
        result = parse_agent_response(raw)
        assert result.signal == "HOLD"
        assert result.parse_failed is False

    def test_markdown_plain_fence_stripped(self):
        """JSON wrapped in ``` ... ``` (no language tag) must be parsed correctly."""
        raw = "```\n" + _hold_json() + "\n```"
        result = parse_agent_response(raw)
        assert result.parse_failed is False

    def test_empty_string_falls_back_to_safe_hold(self):
        """Empty raw string → SAFE_HOLD with parse_failed=True."""
        result = parse_agent_response("")
        assert result.signal == "HOLD"
        assert result.parse_failed is True

    def test_no_json_in_response_falls_back_to_safe_hold(self):
        """Plain text with no JSON → SAFE_HOLD with parse_failed=True."""
        result = parse_agent_response("I think I should wait and observe the market.")
        assert result.signal == "HOLD"
        assert result.parse_failed is True

    def test_multiple_json_objects_prefers_one_with_signal_key(self):
        """Two JSON objects in response — the one with 'signal' key is preferred."""
        irrelevant = json.dumps({"tool": "fetch_price", "status": "ok"})
        relevant = _buy_json()
        raw = irrelevant + " some text " + relevant
        result = parse_agent_response(raw)
        assert result.signal == "BUY"

    def test_nested_json_balanced_brace_scanner(self):
        """JSON with nested objects in string values must be parsed correctly."""
        raw = json.dumps({
            "action": "FINAL_DECISION",
            "signal": "HOLD",
            "confidence": 0.0,
            "rationale": "complex {nested: {value}} string",
        })
        result = parse_agent_response(raw)
        assert result.signal == "HOLD"
        assert result.parse_failed is False

    def test_trailing_comma_in_json_tolerated(self):
        """JSON with trailing comma (common LLM output) must be parsed without error."""
        raw = '{"action": "FINAL_DECISION", "signal": "HOLD", "confidence": 0.0,}'
        result = parse_agent_response(raw)
        # lenient_loads strips trailing comma
        assert result.parse_failed is False

    def test_parse_failed_sets_rationale(self):
        """When parse_failed=True, rationale must explain the failure."""
        result = parse_agent_response("no json here", context="test_ctx")
        assert result.parse_failed is True
        assert result.rationale is not None
        assert len(result.rationale) > 0


# ─────────────────────────────────────────────────────────────────────
# TestStateReadinessChecker — is_ready()
# ─────────────────────────────────────────────────────────────────────


class TestStateReadinessChecker:
    """Tests for StateReadinessChecker.is_ready()."""

    def _make_state_with_ti(self, indicators: dict) -> dict:
        """Helper: build minimal market_state with given technical_indicators."""
        return {"technical_indicators": indicators}

    def test_ready_when_all_required_indicators_present(self):
        """rsi + macd + trend all populated → is_ready=True."""
        cfg = ReadinessConfig(required_indicators=["rsi", "macd", "trend"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({
            "rsi":   {"value": 55.0},
            "macd":  {"macd_line": 5.0, "histogram": 1.2},
            "trend": {"trend": "Bullish", "ema_20": 3200.0, "ema_50": 3150.0},
        })
        assert checker.is_ready(state, []) is True

    def test_not_ready_when_rsi_section_missing(self):
        """technical_indicators missing 'rsi' section → is_ready=False."""
        cfg = ReadinessConfig(required_indicators=["rsi", "macd"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({"macd": {"macd_line": 5.0}})
        assert checker.is_ready(state, []) is False

    def test_not_ready_when_rsi_value_is_none(self):
        """rsi section present but rsi.value=None → is_ready=False."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({"rsi": {"value": None}})
        assert checker.is_ready(state, []) is False

    def test_not_ready_when_rsi_value_is_na_string(self):
        """rsi.value='N/A' (fetcher placeholder) → is_ready=False."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({"rsi": {"value": "N/A"}})
        assert checker.is_ready(state, []) is False

    def test_ready_with_extra_unknown_indicators(self):
        """Extra keys beyond required_indicators must not affect readiness."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({
            "rsi":          {"value": 55.0},
            "custom_extra": {"foo": "bar"},
        })
        assert checker.is_ready(state, []) is True

    def test_htf_covered_via_tool_result(self):
        """When require_htf=True, a successful 'htf' tool result satisfies coverage."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=True)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({"rsi": {"value": 55.0}})
        htf_result = ToolResult(tool_name="get_htf_trend", status="success", data={})
        assert checker.is_ready(state, [htf_result]) is True

    def test_htf_covered_via_trend_in_market_state(self):
        """When require_htf=True and trend section has ema_20/ema_50/trend, HTF is satisfied."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=True)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({
            "rsi":   {"value": 55.0},
            "trend": {"trend": "Bullish", "ema_20": 3200.0, "ema_50": 3150.0},
        })
        assert checker.is_ready(state, []) is True

    def test_not_ready_when_htf_required_but_not_present(self):
        """require_htf=True, no htf tool result, no trend data → is_ready=False."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=True)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({"rsi": {"value": 55.0}})
        assert checker.is_ready(state, []) is False

    def test_require_htf_false_skips_htf_check(self):
        """require_htf=False → HTF check always passes."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = self._make_state_with_ti({"rsi": {"value": 55.0}})
        # No htf result and no trend data — still ready because require_htf=False
        assert checker.is_ready(state, []) is True

    def test_empty_technical_indicators_not_ready(self):
        """Empty technical_indicators dict → is_ready=False."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = {"technical_indicators": {}}
        assert checker.is_ready(state, []) is False

    def test_missing_technical_indicators_key_not_ready(self):
        """market_state without 'technical_indicators' key → is_ready=False."""
        cfg = ReadinessConfig(required_indicators=["rsi"], require_htf=False)
        checker = StateReadinessChecker(cfg)
        state = {}
        assert checker.is_ready(state, []) is False


# ─────────────────────────────────────────────────────────────────────
# TestReactOrchestratorFastPath
# ─────────────────────────────────────────────────────────────────────


class TestReactOrchestratorFastPath:
    """ReactOrchestrator.run() with max_tool_calls=0 (fast path — single LLM call)."""

    def test_fast_path_returns_dict_with_required_keys(
        self, fast_path_orchestrator, mock_llm_client, minimal_market_state
    ):
        """Fast path result must contain final_decision, react_trace, iterations_used, tool_calls_used."""
        mock_llm_client.call.return_value = _llm_response(_hold_json())
        result = fast_path_orchestrator.run(minimal_market_state)
        assert "final_decision" in result
        assert "react_trace" in result
        assert "iterations_used" in result
        assert "tool_calls_used" in result

    def test_fast_path_uses_single_llm_call(
        self, fast_path_orchestrator, mock_llm_client, minimal_market_state
    ):
        """Fast path must invoke llm.call() exactly once."""
        mock_llm_client.call.return_value = _llm_response(_hold_json())
        fast_path_orchestrator.run(minimal_market_state)
        assert mock_llm_client.call.call_count == 1

    def test_fast_path_tool_calls_used_is_zero(
        self, fast_path_orchestrator, mock_llm_client, minimal_market_state
    ):
        """Fast path never calls tools — tool_calls_used must be 0."""
        mock_llm_client.call.return_value = _llm_response(_hold_json())
        result = fast_path_orchestrator.run(minimal_market_state)
        assert result["tool_calls_used"] == 0

    def test_fast_path_final_decision_signal_present(
        self, fast_path_orchestrator, mock_llm_client, minimal_market_state
    ):
        """final_decision must include a 'signal' key."""
        mock_llm_client.call.return_value = _llm_response(_hold_json())
        result = fast_path_orchestrator.run(minimal_market_state)
        assert "signal" in result["final_decision"]

    def test_fast_path_parse_failure_returns_safe_hold(
        self, fast_path_orchestrator, mock_llm_client, minimal_market_state
    ):
        """If LLM returns garbage, fast path falls back to HOLD without raising."""
        mock_llm_client.call.return_value = _llm_response("not valid json at all")
        result = fast_path_orchestrator.run(minimal_market_state)
        assert result["final_decision"]["signal"] == "HOLD"


# ─────────────────────────────────────────────────────────────────────
# TestReactOrchestratorReadinessSkip
# ─────────────────────────────────────────────────────────────────────


class TestReactOrchestratorReadinessSkip:
    """ReactOrchestrator.run() skips the full loop when StateReadinessChecker returns True."""

    def _make_ready_state(self) -> dict:
        """Market state that satisfies readiness check with default required_indicators."""
        return {
            "time": "10:00",
            "date": "2026-04-13",
            "interval": "5m",
            "portfolio": {
                "cash_balance": 5000.0,
                "gold_grams": 0.0,
                "unrealized_pnl": 0.0,
            },
            "market_data": {
                "thai_gold_thb": {
                    "sell_price_thb": 72000.0,
                    "buy_price_thb": 71800.0,
                },
                "forex": {"usd_thb": 34.0},
            },
            "technical_indicators": {
                "rsi":   {"value": 55.0},
                "macd":  {"macd_line": 5.0, "histogram": 1.0},
                "trend": {"trend": "Bullish", "ema_20": 3200.0, "ema_50": 3150.0},
            },
        }

    def test_readiness_skip_invokes_single_llm_call(self, mock_llm_client, mock_prompt_builder):
        """When data is ready, the tool loop is skipped — only 1 LLM call made."""
        cfg = ReactConfig(max_tool_calls=3)  # tools enabled but should be skipped
        # ReadinessConfig with require_htf=False so trend section covers HTF
        cfg.readiness = ReadinessConfig(
            required_indicators=["rsi", "macd", "trend"],
            require_htf=False,
        )
        orchestrator = ReactOrchestrator(
            llm_client=mock_llm_client,
            prompt_builder=mock_prompt_builder,
            tool_registry={},
            config=cfg,
        )
        mock_llm_client.call.return_value = _llm_response(_hold_json())
        orchestrator.run(self._make_ready_state())
        assert mock_llm_client.call.call_count == 1

    def test_readiness_skip_returns_valid_final_decision(self, mock_llm_client, mock_prompt_builder):
        """Readiness skip path returns a final_decision with 'signal' key."""
        cfg = ReactConfig(max_tool_calls=3)
        cfg.readiness = ReadinessConfig(
            required_indicators=["rsi", "macd", "trend"],
            require_htf=False,
        )
        orchestrator = ReactOrchestrator(
            llm_client=mock_llm_client,
            prompt_builder=mock_prompt_builder,
            tool_registry={},
            config=cfg,
        )
        mock_llm_client.call.return_value = _llm_response(_hold_json())
        result = orchestrator.run(self._make_ready_state())
        assert "signal" in result["final_decision"]


# ─────────────────────────────────────────────────────────────────────
# TestReactOrchestratorToolExecution
# ─────────────────────────────────────────────────────────────────────


class TestReactOrchestratorToolExecution:
    """ReactOrchestrator.run() with tool calls — CALL_TOOL and CALL_TOOLS branches."""

    def _make_tool_orchestrator(self, mock_llm_client, mock_prompt_builder, max_tool_calls: int = 2):
        """Helper: build ReactOrchestrator with tools enabled and readiness always False."""
        cfg = ReactConfig(max_tool_calls=max_tool_calls, max_iterations=5)
        # ReadinessConfig that will never be satisfied (empty required_indicators would pass, so set one)
        cfg.readiness = ReadinessConfig(
            required_indicators=["rsi"],  # market state has no technical_indicators → not ready
            require_htf=False,
        )
        tool_fn = MagicMock(return_value={"status": "success", "data": {}})
        tool_registry = {"mock_tool": tool_fn}
        orch = ReactOrchestrator(
            llm_client=mock_llm_client,
            prompt_builder=mock_prompt_builder,
            tool_registry=tool_registry,
            config=cfg,
        )
        return orch

    def _market_state_no_ti(self) -> dict:
        """Market state without technical_indicators so readiness check fails."""
        return {
            "time": "10:00",
            "date": "2026-04-13",
            "interval": "5m",
            "portfolio": {
                "cash_balance": 5000.0,
                "gold_grams": 0.0,
                "unrealized_pnl": 0.0,
            },
            "market_data": {
                "thai_gold_thb": {
                    "sell_price_thb": 72000.0,
                    "buy_price_thb": 71800.0,
                },
                "forex": {"usd_thb": 34.0},
            },
        }

    def test_call_tool_action_executes_tool(self, mock_llm_client, mock_prompt_builder):
        """LLM returning CALL_TOOL → _execute_tool is invoked for that tool."""
        call_tool_resp = json.dumps({
            "action": "CALL_TOOL",
            "tool_name": "mock_tool",
            "tool_args": {},
            "thought": "need data",
        })
        final_resp = _hold_json()

        orch = self._make_tool_orchestrator(mock_llm_client, mock_prompt_builder)
        mock_llm_client.call.side_effect = [
            _llm_response(call_tool_resp),
            _llm_response(final_resp),
        ]

        with patch.object(orch, "_execute_tool", wraps=orch._execute_tool) as spy:
            orch.run(self._market_state_no_ti())
            assert spy.call_count >= 1

    def test_call_tools_parallel_executes_all_tools(self, mock_llm_client, mock_prompt_builder):
        """LLM returning CALL_TOOLS with 2 tools → both tools executed."""
        call_tools_resp = json.dumps({
            "action": "CALL_TOOLS",
            "tools": [
                {"tool_name": "mock_tool", "tool_args": {}},
                {"tool_name": "mock_tool", "tool_args": {}},
            ],
            "thought": "need two tools",
        })
        final_resp = _hold_json()

        orch = self._make_tool_orchestrator(mock_llm_client, mock_prompt_builder, max_tool_calls=3)
        mock_llm_client.call.side_effect = [
            _llm_response(call_tools_resp),
            _llm_response(final_resp),
        ]

        with patch.object(orch, "_execute_tool", wraps=orch._execute_tool) as spy:
            orch.run(self._market_state_no_ti())
            assert spy.call_count >= 2

    def test_max_iterations_forces_final_decision(self, mock_llm_client, mock_prompt_builder):
        """Loop exceeding max_iterations must request a forced FINAL_DECISION and not raise."""
        # Each LLM call returns CALL_TOOL so the loop never breaks naturally
        call_tool_resp = json.dumps({
            "action": "CALL_TOOL",
            "tool_name": "mock_tool",
            "tool_args": {},
        })
        forced_final = _hold_json()

        orch = self._make_tool_orchestrator(mock_llm_client, mock_prompt_builder, max_tool_calls=10)
        # 5 CALL_TOOL iterations → exceeds max_iterations=5, then forced final
        mock_llm_client.call.side_effect = [_llm_response(call_tool_resp)] * 5 + [_llm_response(forced_final)]

        result = orch.run(self._market_state_no_ti())
        # Must complete without raising and contain signal
        assert "signal" in result["final_decision"]

    def test_unknown_tool_produces_error_result(self, mock_llm_client, mock_prompt_builder):
        """Calling a tool not in registry → ToolResult with status='error', loop continues."""
        call_tool_resp = json.dumps({
            "action": "CALL_TOOL",
            "tool_name": "nonexistent_tool",
            "tool_args": {},
        })
        final_resp = _hold_json()

        orch = self._make_tool_orchestrator(mock_llm_client, mock_prompt_builder)
        mock_llm_client.call.side_effect = [
            _llm_response(call_tool_resp),
            _llm_response(final_resp),
        ]
        # Should not raise even though tool is not in registry
        result = orch.run(self._market_state_no_ti())
        assert "signal" in result["final_decision"]

    def test_result_contains_iterations_and_tool_counts(self, mock_llm_client, mock_prompt_builder):
        """Final result must expose iterations_used and tool_calls_used integers."""
        call_tool_resp = json.dumps({
            "action": "CALL_TOOL",
            "tool_name": "mock_tool",
            "tool_args": {},
        })
        final_resp = _hold_json()

        orch = self._make_tool_orchestrator(mock_llm_client, mock_prompt_builder)
        mock_llm_client.call.side_effect = [
            _llm_response(call_tool_resp),
            _llm_response(final_resp),
        ]
        result = orch.run(self._market_state_no_ti())
        assert isinstance(result["iterations_used"], int)
        assert isinstance(result["tool_calls_used"], int)
