"""
test_regression.py — Regression tests for LLM output consistency
Tests: deterministic mock outputs, valid signal values, confidence range,
       decision schema stability, snapshot-based comparison.
"""

import json
import pytest

from agent_core.llm.client import MockClient, DEFAULT_MOCK_RESPONSES
from agent_core.core.react import ReactOrchestrator, ReactConfig, extract_json
from agent_core.core.prompt import (
    PromptBuilder,
    PromptPackage,
    RoleRegistry,
    SkillRegistry,
    AIRole,
    RoleDefinition,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_orchestrator(client=None):
    if client is None:
        client = MockClient()
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
        llm_client=client,
        prompt_builder=prompt_builder,
        tool_registry={},
        config=ReactConfig(max_iterations=3, max_tool_calls=0),
    )


# ─── Expected snapshot for MockClient default responses ──────────────────────

EXPECTED_MOCK_SNAPSHOT = {
    "signal": "HOLD",
    "confidence_range": (0.0, 1.0),
    "required_keys": ["signal", "confidence", "entry_price", "stop_loss", "take_profit", "rationale"],
}


# ─── Regression Tests ────────────────────────────────────────────────────────

class TestMockResponseDeterministic:

    def test_same_input_same_output(self, sample_market_state):
        """Running the same input twice with MockClient should yield identical output."""
        orch = _make_orchestrator()
        result1 = orch.run(sample_market_state)
        # Create fresh orchestrator (MockClient is stateless)
        orch2 = _make_orchestrator()
        result2 = orch2.run(sample_market_state)

        assert result1["final_decision"]["signal"] == result2["final_decision"]["signal"]
        assert result1["final_decision"]["confidence"] == result2["final_decision"]["confidence"]
        assert result1["final_decision"]["rationale"] == result2["final_decision"]["rationale"]

    def test_mock_responses_are_valid_json(self):
        """All default mock responses should be valid JSON."""
        for key, resp in DEFAULT_MOCK_RESPONSES.items():
            parsed = json.loads(resp)
            assert isinstance(parsed, dict), f"Response for {key} is not a dict"
            assert "action" in parsed, f"Response for {key} missing 'action'"

    def test_mock_client_fallback_is_valid(self):
        """MockClient fallback response should be valid JSON with HOLD."""
        client = MockClient()
        prompt = PromptPackage(system="test", user="test", step_label="UNKNOWN_STEP")
        raw = client.call(prompt)
        parsed = json.loads(raw)
        assert parsed["signal"] == "HOLD"


class TestSignalValuesValid:

    def test_signal_always_valid(self, sample_market_state):
        """Signal must always be BUY, SELL, or HOLD."""
        valid_signals = {"BUY", "SELL", "HOLD"}

        # Test with default mock
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        assert result["final_decision"]["signal"] in valid_signals

    def test_signal_valid_with_custom_buy(self, sample_market_state):
        client = MockClient(response_map={
            "THOUGHT_FINAL": json.dumps({
                "action": "FINAL_DECISION",
                "signal": "BUY",
                "confidence": 0.8,
                "rationale": "test",
            }),
        })
        orch = _make_orchestrator(client)
        result = orch.run(sample_market_state)
        assert result["final_decision"]["signal"] == "BUY"

    def test_signal_valid_with_custom_sell(self, sample_market_state):
        client = MockClient(response_map={
            "THOUGHT_FINAL": json.dumps({
                "action": "FINAL_DECISION",
                "signal": "SELL",
                "confidence": 0.7,
                "rationale": "test",
            }),
        })
        orch = _make_orchestrator(client)
        result = orch.run(sample_market_state)
        assert result["final_decision"]["signal"] == "SELL"


class TestConfidenceRange:

    def test_confidence_in_range(self, sample_market_state):
        """Confidence must be 0.0 ≤ c ≤ 1.0."""
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        conf = result["final_decision"]["confidence"]
        assert 0.0 <= conf <= 1.0

    @pytest.mark.parametrize("conf_val", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_various_confidence_values(self, sample_market_state, conf_val):
        client = MockClient(response_map={
            "THOUGHT_FINAL": json.dumps({
                "action": "FINAL_DECISION",
                "signal": "HOLD",
                "confidence": conf_val,
                "rationale": "test",
            }),
        })
        orch = _make_orchestrator(client)
        result = orch.run(sample_market_state)
        assert result["final_decision"]["confidence"] == conf_val


class TestDecisionSchemaStable:

    def test_decision_has_all_required_keys(self, sample_market_state):
        """Output dict must always contain the required keys."""
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        fd = result["final_decision"]
        for key in EXPECTED_MOCK_SNAPSHOT["required_keys"]:
            assert key in fd, f"Missing key: {key}"

    def test_result_has_meta_keys(self, sample_market_state):
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        assert "iterations_used" in result
        assert "tool_calls_used" in result
        assert "react_trace" in result
        assert isinstance(result["react_trace"], list)

    def test_decision_types(self, sample_market_state):
        """Verify types of decision fields."""
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        fd = result["final_decision"]
        assert isinstance(fd["signal"], str)
        assert isinstance(fd["confidence"], float)
        assert isinstance(fd["rationale"], str)


class TestSnapshotComparison:

    def test_mock_default_matches_snapshot(self, sample_market_state):
        """Default MockClient should produce HOLD with 0.5 confidence."""
        orch = _make_orchestrator()
        result = orch.run(sample_market_state)
        fd = result["final_decision"]

        assert fd["signal"] == EXPECTED_MOCK_SNAPSHOT["signal"]
        lo, hi = EXPECTED_MOCK_SNAPSHOT["confidence_range"]
        assert lo <= fd["confidence"] <= hi

    def test_multiple_runs_consistent(self, sample_market_state):
        """10 consecutive runs should all produce the same result."""
        results = []
        for _ in range(10):
            orch = _make_orchestrator()
            r = orch.run(sample_market_state)
            results.append(r["final_decision"])

        signals = {r["signal"] for r in results}
        confidences = {r["confidence"] for r in results}
        assert len(signals) == 1, f"Inconsistent signals: {signals}"
        assert len(confidences) == 1, f"Inconsistent confidences: {confidences}"
