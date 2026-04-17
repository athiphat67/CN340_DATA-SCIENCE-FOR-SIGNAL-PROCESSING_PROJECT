"""
test_react.py — Pytest สำหรับทดสอบ ReactOrchestrator + helpers

Strategy: Real logic + MockClient (ไม่เรียก API จริง)
- ReactOrchestrator เป็น dependency-injected → ใส่ MockClient/StubClient เข้าไป
- RiskManager ข้างใน → รัน Real (เป็น pure logic)
- PromptBuilder → ใช้ Stub ที่คืน PromptPackage ง่ายๆ
- ไม่ mock อะไรด้วย unittest.mock เลย — ใช้ stub classes แทน

ครอบคลุม:
  1. extract_json() — parse JSON จาก LLM response (pure function)
  2. _build_decision() / _fallback_decision() — normalize dict (static methods)
  3. _aggregate_trace() — รวม token counts จาก trace
  4. Fast path (max_tool_calls=0) — single LLM call → FINAL_DECISION
  5. Full ReAct loop — THOUGHT → CALL_TOOL → THOUGHT → FINAL_DECISION
  6. Max iterations reached → forced final decision
  7. Unknown action → fallback HOLD
  8. Tool execution — success / error / unknown tool
  9. RiskManager integration — low confidence → rejected
  10. _make_llm_log() — trace entry structure
"""

import json
import pytest
from dataclasses import dataclass
from typing import Optional

from agent_core.core.react import (
    ReactOrchestrator,
    ReactConfig,
    ToolResult,
    extract_json,
    _make_llm_log,
)


# ══════════════════════════════════════════════════════════════════
# Stubs — ไม่เรียก API จริง, ไม่ใช้ unittest.mock
# ══════════════════════════════════════════════════════════════════


@dataclass
class FakeLLMResponse:
    """จำลอง LLMResponse จาก client.py"""

    text: str
    prompt_text: str = "fake prompt"
    token_input: int = 10
    token_output: int = 20
    token_total: int = 30
    model: str = "fake-model"
    provider: str = "fake"


@dataclass
class FakePromptPackage:
    system: str = "You are a trader"
    user: str = "Analyze gold"
    step_label: str = "THOUGHT_1"


class StubLLMClient:
    """
    LLM Client ที่คืน response ตามลำดับที่กำหนดไว้
    แต่ละครั้งที่เรียก .call() จะคืนค่าถัดไปจาก responses list
    """

    def __init__(self, responses: list[str]):
        self._responses = responses
        self._idx = 0

    def call(self, prompt_package) -> FakeLLMResponse:
        text = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return FakeLLMResponse(text=text)

    def is_available(self) -> bool:
        return True


class StubPromptBuilder:
    """PromptBuilder ที่คืน FakePromptPackage ง่ายๆ"""

    def build_thought(self, market_state, tool_results, iteration):
        return FakePromptPackage(step_label=f"THOUGHT_{iteration}")

    def build_final_decision(self, market_state, tool_results):
        return FakePromptPackage(step_label="THOUGHT_FINAL")


def _market_state():
    """market_state ขั้นต่ำที่ RiskManager ต้องการ"""
    return {
        "date": "2026-04-06",
        "portfolio": {"cash_balance": 5000.0, "gold_grams": 0.0},
        "market_data": {
            "thai_gold_thb": {
                "sell_price_thb": 45000.0,
                "buy_price_thb": 44900.0,
                "spot_price_thb": 45000.0,
            },
        },
        "technical_indicators": {
            "atr": {"value": 150.0, "unit": "THB"},
        },
    }


def _final_decision_json(signal="BUY", confidence=0.8):
    """สร้าง JSON string ที่ LLM จะตอบกลับ"""
    return json.dumps(
        {
            "action": "FINAL_DECISION",
            "signal": signal,
            "confidence": confidence,
            "rationale": "Test decision",
            "entry_price": 45000,
            "stop_loss": 44700,
            "take_profit": 45450,
        }
    )


def _call_tool_json(tool_name="get_news"):
    return json.dumps(
        {
            "action": "CALL_TOOL",
            "thought": "Need more data",
            "tool_name": tool_name,
            "tool_args": {},
        }
    )


# ══════════════════════════════════════════════════════════════════
# 1. extract_json() — Pure function
# ══════════════════════════════════════════════════════════════════


class TestExtractJson:
    """parse JSON จาก LLM response หลายรูปแบบ"""

    def test_plain_json(self):
        result = extract_json('{"signal": "BUY", "confidence": 0.8}')
        assert result["signal"] == "BUY"

    def test_fenced_json(self):
        result = extract_json('```json\n{"signal": "SELL"}\n```')
        assert result["signal"] == "SELL"

    def test_fenced_no_lang(self):
        result = extract_json('```\n{"signal": "HOLD"}\n```')
        assert result["signal"] == "HOLD"

    def test_json_with_preamble(self):
        """LLM อาจมีข้อความก่อน JSON"""
        result = extract_json('Here is my analysis:\n{"signal": "BUY"}')
        assert result["signal"] == "BUY"

    def test_empty_string(self):
        result = extract_json("")
        assert result.get("_parse_error") is True

    def test_none_like(self):
        result = extract_json("   ")
        assert result.get("_parse_error") is True

    def test_invalid_json(self):
        result = extract_json("not json at all")
        assert result.get("_parse_error") is True

    def test_nested_json(self):
        raw = '{"action": "FINAL_DECISION", "data": {"nested": true}}'
        result = extract_json(raw)
        assert result["action"] == "FINAL_DECISION"
        assert result["data"]["nested"] is True


# ══════════════════════════════════════════════════════════════════
# 2. _build_decision / _fallback_decision — Static methods
# ══════════════════════════════════════════════════════════════════


class TestBuildDecision:
    def test_normal_build(self):
        parsed = {"signal": "BUY", "confidence": 0.85, "rationale": "Strong trend"}
        d = ReactOrchestrator._build_decision(parsed)
        assert d["signal"] == "BUY"
        assert d["confidence"] == 0.85
        assert d["rationale"] == "Strong trend"

    def test_missing_fields_defaults(self):
        """ไม่มี field → ใช้ default"""
        d = ReactOrchestrator._build_decision({})
        assert d["signal"] == "HOLD"
        assert d["confidence"] == 0.0
        assert d["entry_price"] is None

    def test_thought_as_rationale_fallback(self):
        """ถ้าไม่มี rationale ใช้ thought แทน"""
        d = ReactOrchestrator._build_decision({"thought": "My reasoning"})
        assert d["rationale"] == "My reasoning"

    def test_fallback_decision(self):
        d = ReactOrchestrator._fallback_decision("timeout")
        assert d["signal"] == "HOLD"
        assert d["confidence"] == 0.0
        assert "timeout" in d["rationale"]


# ══════════════════════════════════════════════════════════════════
# 3. _aggregate_trace — Token aggregation
# ══════════════════════════════════════════════════════════════════


class TestAggregateTrace:
    def test_sums_tokens(self):
        trace = [
            {
                "step": "THOUGHT_1",
                "token_input": 100,
                "token_output": 50,
                "token_total": 150,
                "prompt_text": "p1",
                "response_raw": "r1",
            },
            {
                "step": "THOUGHT_FINAL",
                "token_input": 200,
                "token_output": 80,
                "token_total": 280,
                "prompt_text": "p_final",
                "response_raw": "r_final",
            },
        ]
        agg = ReactOrchestrator._aggregate_trace(trace)
        assert agg["token_input"] == 300
        assert agg["token_output"] == 130
        assert agg["token_total"] == 430

    def test_uses_final_prompt(self):
        trace = [
            {
                "step": "THOUGHT_1",
                "token_input": 10,
                "token_output": 5,
                "token_total": 15,
                "prompt_text": "first",
                "response_raw": "first_resp",
            },
            {
                "step": "THOUGHT_FINAL",
                "token_input": 20,
                "token_output": 10,
                "token_total": 30,
                "prompt_text": "final_prompt",
                "response_raw": "final_resp",
            },
        ]
        agg = ReactOrchestrator._aggregate_trace(trace)
        assert agg["prompt_text"] == "final_prompt"
        assert agg["response_raw"] == "final_resp"

    def test_skips_tool_execution(self):
        trace = [
            {
                "step": "THOUGHT_1",
                "token_input": 50,
                "token_output": 25,
                "token_total": 75,
            },
            {
                "step": "TOOL_EXECUTION",
                "token_input": 0,
                "token_output": 0,
                "token_total": 0,
            },
            {
                "step": "THOUGHT_FINAL",
                "token_input": 60,
                "token_output": 30,
                "token_total": 90,
                "prompt_text": "p",
                "response_raw": "r",
            },
        ]
        agg = ReactOrchestrator._aggregate_trace(trace)
        assert agg["token_input"] == 110  # 50+60, skip tool

    def test_empty_trace(self):
        agg = ReactOrchestrator._aggregate_trace([])
        assert agg["token_input"] is None  # 0 → None


# ══════════════════════════════════════════════════════════════════
# 4. Fast Path (max_tool_calls=0)
# ══════════════════════════════════════════════════════════════════


class TestFastPath:
    """max_tool_calls=0 → single LLM call → FINAL_DECISION"""

    def test_returns_final_decision(self):
        llm = StubLLMClient([_final_decision_json("BUY", 0.8)])
        react = ReactOrchestrator(
            llm_client=llm,
            prompt_builder=StubPromptBuilder(),
            tool_registry={},
            config=ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())

        assert "final_decision" in result
        # RiskManager อาจ adjust signal
        assert result["final_decision"]["signal"] in ("BUY", "HOLD")

    def test_iterations_used_is_1(self):
        llm = StubLLMClient([_final_decision_json()])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())
        assert result["iterations_used"] == 1
        assert result["tool_calls_used"] == 0

    def test_trace_has_one_entry(self):
        llm = StubLLMClient([_final_decision_json()])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())
        assert len(result["react_trace"]) == 1
        assert result["react_trace"][0]["step"] == "THOUGHT_FINAL"

    def test_hold_signal_passes_through(self):
        llm = StubLLMClient([_final_decision_json("HOLD", 0.5)])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())
        assert result["final_decision"]["signal"] == "HOLD"

    def test_token_metadata_in_result(self):
        llm = StubLLMClient([_final_decision_json()])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())
        assert "token_input" in result
        assert "token_output" in result


# ══════════════════════════════════════════════════════════════════
# 5. Full ReAct Loop
# ══════════════════════════════════════════════════════════════════


class TestFullReactLoop:
    """ReAct loop: THOUGHT → CALL_TOOL → THOUGHT → FINAL_DECISION"""

    def _make_react(self, responses, tools=None, max_iter=5, max_tools=3):
        return ReactOrchestrator(
            llm_client=StubLLMClient(responses),
            prompt_builder=StubPromptBuilder(),
            tool_registry=tools or {},
            config=ReactConfig(max_iterations=max_iter, max_tool_calls=max_tools),
        )

    def test_tool_call_then_decision(self):
        """CALL_TOOL → FINAL_DECISION (2 iterations)"""
        responses = [
            _call_tool_json("get_news"),
            _final_decision_json("SELL", 0.75),
        ]
        tools = {"get_news": lambda: {"headline": "Gold rises"}}

        react = self._make_react(responses, tools)
        # ต้องใช้ market_state ที่มี gold_grams > 0 เพื่อให้ SELL ผ่าน RiskManager
        ms = _market_state()
        ms["portfolio"]["gold_grams"] = 1.0

        result = react.run(ms)
        assert result["iterations_used"] == 2
        assert result["tool_calls_used"] == 1

    def test_trace_includes_tool_execution(self):
        """trace ต้องมี TOOL_EXECUTION entry"""
        responses = [
            _call_tool_json("calculator"),
            _final_decision_json(),
        ]
        tools = {"calculator": lambda: {"result": 42}}

        react = self._make_react(responses, tools)
        result = react.run(_market_state())

        steps = [t["step"] for t in result["react_trace"]]
        assert "TOOL_EXECUTION" in steps
        assert any("THOUGHT" in s for s in steps)

    def test_unknown_tool_returns_error(self):
        """เรียก tool ที่ไม่มีใน registry → ToolResult error"""
        responses = [
            _call_tool_json("nonexistent_tool"),
            _final_decision_json(),
        ]
        react = self._make_react(responses, tools={})
        result = react.run(_market_state())

        # ตรวจ trace ว่ามี error observation
        tool_steps = [
            t for t in result["react_trace"] if t.get("step") == "TOOL_EXECUTION"
        ]
        assert len(tool_steps) == 1
        assert tool_steps[0]["observation"]["status"] == "error"

    def test_tool_exception_caught(self):
        """tool raise Exception → ToolResult error, ไม่ crash"""
        responses = [
            _call_tool_json("bad_tool"),
            _final_decision_json(),
        ]
        tools = {"bad_tool": lambda: (_ for _ in ()).throw(ValueError("boom"))}

        react = self._make_react(responses, tools)
        result = react.run(_market_state())

        tool_steps = [
            t for t in result["react_trace"] if t.get("step") == "TOOL_EXECUTION"
        ]
        assert tool_steps[0]["observation"]["status"] == "error"
        assert "boom" in tool_steps[0]["observation"]["error"]


# ══════════════════════════════════════════════════════════════════
# 6. Max Iterations Reached
# ══════════════════════════════════════════════════════════════════


class TestMaxIterations:
    def test_forced_final_at_max(self):
        """LLM ไม่ยอม FINAL_DECISION → ถึง max_iterations → forced"""
        # LLM ตอบ CALL_TOOL ทุกรอบ + forced final ท้ายสุด
        responses = [
            _call_tool_json("t1"),
            _call_tool_json("t2"),
            _call_tool_json("t3"),  # max_iterations=3 → forced
            _final_decision_json(),  # ถูกเรียกตอน forced final
        ]
        tools = {
            "t1": lambda: {"ok": True},
            "t2": lambda: {"ok": True},
            "t3": lambda: {"ok": True},
        }
        react = ReactOrchestrator(
            StubLLMClient(responses),
            StubPromptBuilder(),
            tools,
            ReactConfig(max_iterations=3, max_tool_calls=5),
        )
        result = react.run(_market_state())

        # ต้องมี forced final ใน trace
        final_steps = [t for t in result["react_trace"] if "FINAL" in t.get("step", "")]
        assert len(final_steps) >= 1


# ══════════════════════════════════════════════════════════════════
# 7. Unknown Action → Fallback HOLD
# ══════════════════════════════════════════════════════════════════


class TestUnknownAction:
    def test_unknown_action_returns_hold(self):
        """LLM ตอบ action ที่ไม่รู้จัก → fallback HOLD"""
        bad_response = json.dumps(
            {
                "action": "DANCE",
                "thought": "Let me dance",
            }
        )
        react = ReactOrchestrator(
            StubLLMClient([bad_response]),
            StubPromptBuilder(),
            {},
            ReactConfig(max_iterations=5, max_tool_calls=3),
        )
        result = react.run(_market_state())

        assert result["final_decision"]["signal"] == "HOLD"

    def test_unknown_action_triggers_fallback_decision(self):
        """Unknown action (เช่น action: YOLO) ต้องถูก Pydantic ดักจับและ force เป็น HOLD"""
        bad_response = json.dumps({"action": "YOLO"})
        react = ReactOrchestrator(
            StubLLMClient([bad_response]),
            StubPromptBuilder(),
            {},
            ReactConfig(max_iterations=5, max_tool_calls=3),
        )
        result = react.run(_market_state())

        # ระบบบังคับสับสวิตช์ความปลอดภัยเป็น HOLD ทันทีที่ parse failed
        assert result["final_decision"]["signal"] == "HOLD"
        assert "parse failed" in result["final_decision"]["rationale"]

        # log จะออกมาเป็น THOUGHT_1 (หรือ THOUGHT_FINAL) แทน UNKNOWN_ACTION
        steps = [t["step"] for t in result["react_trace"]]
        assert "UNKNOWN_ACTION" not in steps


# ══════════════════════════════════════════════════════════════════
# 8. RiskManager Integration
# ══════════════════════════════════════════════════════════════════


class TestRiskManagerInReact:
    """ReactOrchestrator มี RiskManager ข้างใน → ตรวจ confidence/position"""

    def test_low_confidence_rejected(self):
        """confidence 0.3 < min 0.6 → RiskManager reject → HOLD"""
        llm = StubLLMClient([_final_decision_json("BUY", 0.3)])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())
        assert result["final_decision"]["signal"] == "HOLD"
        assert result["final_decision"]["rejection_reason"] is not None

    def test_high_confidence_passes(self):
        """confidence 0.9 → RiskManager approve → BUY"""
        llm = StubLLMClient([_final_decision_json("BUY", 0.9)])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())
        assert result["final_decision"]["signal"] == "BUY"

    def test_sell_without_gold_rejected(self):
        """SELL แต่ไม่มี gold_grams → rejected"""
        llm = StubLLMClient([_final_decision_json("SELL", 0.9)])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        ms = _market_state()
        ms["portfolio"]["gold_grams"] = 0.0
        result = react.run(ms)
        assert result["final_decision"]["signal"] == "HOLD"


# ══════════════════════════════════════════════════════════════════
# 9. _make_llm_log — Trace entry builder
# ══════════════════════════════════════════════════════════════════


class TestMakeLLMLog:
    def test_basic_log(self):
        resp = FakeLLMResponse(text='{"signal":"BUY"}')
        log = _make_llm_log("THOUGHT_1", 1, resp, {"signal": "BUY"})
        assert log["step"] == "THOUGHT_1"
        assert log["iteration"] == 1
        assert log["response"]["signal"] == "BUY"
        assert log["token_input"] == 10
        assert log["model"] == "fake-model"

    def test_none_response(self):
        """llm_resp=None → defaults ทั้งหมด"""
        log = _make_llm_log("FALLBACK", 0, None, {})
        assert log["prompt_text"] == ""
        assert log["token_total"] == 0
        assert log["model"] == ""

    def test_note_field(self):
        resp = FakeLLMResponse(text="")
        log = _make_llm_log("THOUGHT_FINAL", 3, resp, {}, note="forced")
        assert log["note"] == "forced"

    def test_no_note_field_when_empty(self):
        resp = FakeLLMResponse(text="")
        log = _make_llm_log("THOUGHT_1", 1, resp, {})
        assert "note" not in log


# ══════════════════════════════════════════════════════════════════
# 10. Return Structure
# ══════════════════════════════════════════════════════════════════


class TestReturnStructure:
    """ทดสอบว่า result dict มี keys ครบ"""

    def test_required_keys(self):
        llm = StubLLMClient([_final_decision_json()])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())

        required = {
            "final_decision",
            "react_trace",
            "iterations_used",
            "tool_calls_used",
            "prompt_text",
            "response_raw",
            "token_input",
            "token_output",
            "token_total",
        }
        assert required.issubset(result.keys())

    def test_final_decision_keys(self):
        llm = StubLLMClient([_final_decision_json()])
        react = ReactOrchestrator(
            llm,
            StubPromptBuilder(),
            {},
            ReactConfig(max_tool_calls=0),
        )
        result = react.run(_market_state())
        fd = result["final_decision"]

        assert "signal" in fd
        assert "confidence" in fd
        assert "rationale" in fd
