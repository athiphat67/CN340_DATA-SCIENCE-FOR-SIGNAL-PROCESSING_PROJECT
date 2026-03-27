"""
react.py — Part B: ReAct Orchestration Loop
Thought → Action → Observation → ... → FINAL_DECISION
"""

import json
import re
from typing import Callable, Any, Optional
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
# Config (ต้องอยู่ก่อน ReactState)
# ─────────────────────────────────────────────

@dataclass
class ReactConfig:
    """Config สำหรับ ReAct loop"""
    max_iterations: int   = 5
    max_tool_calls: int   = 0      # 0 = ไม่ใช้ tool (data pre-loaded)
    timeout_seconds: Optional[int] = None


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class ToolResult:
    """Result จากการ execute tool"""
    tool_name: str
    status:    str              # "success" | "error"
    data:      dict
    error:     Optional[str] = None


@dataclass
class ReactState:
    """Mutable state ตลอด loop"""
    market_state:    dict
    tool_results:    list        # list[ToolResult]
    iteration:       int = 0
    tool_call_count: int = 0
    react_trace:     list = field(default_factory=list)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def extract_json(raw: str) -> dict:
    """
    Parse JSON จาก LLM response อย่างปลอดภัย
    รองรับ: plain JSON, ```json ... ```, ``` ... ```
    """
    if not raw or not raw.strip():
        return {}

    # Strip markdown fences (Gemini / Claude อาจส่งมา)
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    # หา JSON object แรก
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # fallback
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw": raw[:500]}


# ─────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────

class ReactOrchestrator:
    """
    ReAct loop: Thought → Action → Observation → repeat → FINAL_DECISION

    Fully dependency-injected:
      llm_client     — Part A (LLMClient)
      prompt_builder — Part C (PromptBuilder)
      tool_registry  — dict[str, Callable]
      config         — ReactConfig
    """

    def __init__(
        self,
        llm_client,                        # LLMClient (Part A)
        prompt_builder,                    # PromptBuilder (Part C)
        tool_registry: dict,
        config: ReactConfig,
    ):
        self.llm            = llm_client
        self.prompt_builder = prompt_builder
        self.tools          = tool_registry
        self.config         = config

    # ── Entry point ─────────────────────────────

    def run(
        self,
        market_state: dict,
        initial_observation: Optional[ToolResult] = None,
    ) -> dict:
        """
        Run ReAct loop.

        Returns:
            {
                "final_decision": { signal, confidence, entry_price,
                                    stop_loss, take_profit, rationale },
                "react_trace": [ {step, iteration, ...}, ... ],
                "iterations_used": int,
                "tool_calls_used": int,
            }
        """
        
        if self.config.max_tool_calls == 0:
        # ไม่มี tools → ตัดสินใจรอบเดียว ไม่ต้องวน loop
            prompt = self.prompt_builder.build_final_decision(market_state, [])
            raw = self.llm.call(prompt)
            parsed = extract_json(raw)
            return {
                "final_decision": self._build_decision(parsed),
                "react_trace": [{"step": "THOUGHT_FINAL", "iteration": 1, "response": parsed}],
                "iterations_used": 1,
                "tool_calls_used": 0,
        }
        
        state = ReactState(
            market_state=market_state,
            tool_results=[initial_observation] if initial_observation else [],
        )

        final_decision = None

        while state.iteration < self.config.max_iterations:
            state.iteration += 1

            # ── THOUGHT ────────────────────────────
            prompt   = self.prompt_builder.build_thought(
                state.market_state,
                state.tool_results,
                state.iteration,
            )
            raw_resp = self.llm.call(prompt)
            thought  = extract_json(raw_resp)

            state.react_trace.append({
                "step":      f"THOUGHT_{state.iteration}",
                "iteration": state.iteration,
                "response":  thought,
            })

            action = thought.get("action", "")

            # ── ACTION: FINAL_DECISION ──────────────
            if action == "FINAL_DECISION":
                final_decision = self._build_decision(thought)
                break

            # ── ACTION: CALL_TOOL ───────────────────
            elif action == "CALL_TOOL":
                if state.tool_call_count >= self.config.max_tool_calls:
                    # Max tool calls ถึงแล้ว → force final decision
                    final_prompt = self.prompt_builder.build_final_decision(
                        state.market_state,
                        state.tool_results,
                    )
                    raw_final    = self.llm.call(final_prompt)
                    final_parsed = extract_json(raw_final)
                    final_decision = self._build_decision(final_parsed)

                    state.react_trace.append({
                        "step":      "THOUGHT_FINAL",
                        "iteration": state.iteration,
                        "response":  final_parsed,
                        "note":      "forced — max_tool_calls reached",
                    })
                    break

                tool_name = thought.get("tool_name", "")
                tool_args = thought.get("tool_args", {})

                observation = self._execute_tool(tool_name, tool_args)
                state.tool_results = state.tool_results + [observation]   # no mutation
                state.tool_call_count += 1

                state.react_trace.append({
                    "step":        "TOOL_EXECUTION",
                    "iteration":   state.iteration,
                    "tool_name":   tool_name,
                    "observation": {
                        "status": observation.status,
                        "data":   observation.data,
                        "error":  observation.error,
                    },
                })
                continue

            # ── UNKNOWN ACTION ──────────────────────
            else:
                state.react_trace.append({
                    "step":      "UNKNOWN_ACTION",
                    "iteration": state.iteration,
                    "raw":       thought,
                })
                final_decision = self._fallback_decision("unknown action")
                break

        # ── Max iterations reached ──────────────────
        if final_decision is None:
            final_prompt = self.prompt_builder.build_final_decision(
                state.market_state,
                state.tool_results,
            )
            raw_final    = self.llm.call(final_prompt)
            final_parsed = extract_json(raw_final)
            final_decision = self._build_decision(final_parsed)

            state.react_trace.append({
                "step":      "THOUGHT_FINAL",
                "iteration": state.iteration,
                "response":  final_parsed,
                "note":      "forced — max_iterations reached",
            })

        return {
            "final_decision":  final_decision,
            "react_trace":     state.react_trace,
            "iterations_used": state.iteration,
            "tool_calls_used": state.tool_call_count,
        }

    # ── Private helpers ─────────────────────────

    def _execute_tool(self, tool_name: str, tool_args: dict) -> ToolResult:
        if tool_name not in self.tools:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                data={},
                error=f"Tool '{tool_name}' not found in registry",
            )
        try:
            result = self.tools[tool_name](**tool_args)
            return ToolResult(tool_name=tool_name, status="success", data=result)
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                data={},
                error=str(exc),
            )

    @staticmethod
    def _build_decision(parsed: dict) -> dict:
        """Normalise LLM output → final_decision dict"""
        return {
            "signal":      parsed.get("signal", "HOLD"),
            "confidence":  float(parsed.get("confidence", 0.0)),
            "entry_price": parsed.get("entry_price"),
            "stop_loss":   parsed.get("stop_loss"),
            "take_profit": parsed.get("take_profit"),
            "rationale":   parsed.get("rationale", parsed.get("thought", "")),
        }

    @staticmethod
    def _fallback_decision(reason: str = "") -> dict:
        return {
            "signal":      "HOLD",
            "confidence":  0.0,
            "entry_price": None,
            "stop_loss":   None,
            "take_profit": None,
            "rationale":   f"Fallback HOLD — {reason}",
        }