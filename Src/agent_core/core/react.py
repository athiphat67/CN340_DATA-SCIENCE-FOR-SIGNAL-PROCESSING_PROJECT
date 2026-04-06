"""
react.py — Part B: ReAct Orchestration Loop
Thought → Action → Observation → ... → FINAL_DECISION

v2: แก้ไขให้รองรับ LLMResponse จาก client.py
    - บันทึก prompt_text, response_raw, token_input/output/total, model
      ลงใน react_trace ทุก step เพื่อ LLM Log UI
"""

import json
import re
from typing import Callable, Any, Optional
from dataclasses import dataclass, field
from .risk import RiskManager


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

    # Strip markdown fences
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


def _make_llm_log(
    step: str,
    iteration: int,
    llm_resp,           # LLMResponse object จาก client.py
    parsed: dict,
    note: str = "",
) -> dict:
    """
    Helper: สร้าง trace entry พร้อม LLM metadata ครบถ้วน
    
    Args:
        llm_resp: LLMResponse instance (หรือ None ถ้า fallback)
    """
    entry = {
        "step":         step,
        "iteration":    iteration,
        "response":     parsed,
        # ── LLM metadata (ใหม่) ──────────────────────────────────
        "prompt_text":  getattr(llm_resp, "prompt_text",  "") if llm_resp else "",
        "response_raw": getattr(llm_resp, "text",         "") if llm_resp else "",
        "token_input":  getattr(llm_resp, "token_input",  0)  if llm_resp else 0,
        "token_output": getattr(llm_resp, "token_output", 0)  if llm_resp else 0,
        "token_total":  getattr(llm_resp, "token_total",  0)  if llm_resp else 0,
        "model":        getattr(llm_resp, "model",        "")  if llm_resp else "",
        "provider":     getattr(llm_resp, "provider",     "")  if llm_resp else "",
    }
    if note:
        entry["note"] = note
    return entry


# ─────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────

class ReactOrchestrator:
    """
    ReAct loop: Thought → Action → Observation → repeat → FINAL_DECISION

    Fully dependency-injected:
      llm_client     — Part A (LLMClient) — ต้องรองรับ LLMResponse return
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
        self.risk_manager   = RiskManager(atr_multiplier=2.0, risk_reward_ratio=1.5)

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
                "react_trace": [ {step, iteration, response,
                                   prompt_text, response_raw,
                                   token_input, token_output, token_total,
                                   model, provider, ...}, ... ],
                "iterations_used": int,
                "tool_calls_used": int,
            }
        """

        # ── Fast path: no tools → single LLM call ───────────────
        if self.config.max_tool_calls == 0:
            prompt   = self.prompt_builder.build_final_decision(market_state, [])
            llm_resp = self.llm.call(prompt)
            raw      = llm_resp.text
            parsed   = extract_json(raw)

            llm_decision     = self._build_decision(parsed)
            adjusted_decision = self.risk_manager.evaluate(
                llm_decision=llm_decision,
                market_state=market_state,
            )

            trace = [_make_llm_log("THOUGHT_FINAL", 1, llm_resp, parsed)]
            return {
                "final_decision":  adjusted_decision,
                "react_trace":     trace,
                "iterations_used": 1,
                "tool_calls_used": 0,
                # ── top-level LLM metadata (consumed by services.py → llm_logs) ──
                **self._aggregate_trace(trace),
            }

        # ── Full ReAct loop ──────────────────────────────────────
        state = ReactState(
            market_state=market_state,
            tool_results=[initial_observation] if initial_observation else [],
        )

        final_decision = None

        while state.iteration < self.config.max_iterations:
            state.iteration += 1

            # ── THOUGHT ────────────────────────────────────────
            prompt   = self.prompt_builder.build_thought(
                state.market_state,
                state.tool_results,
                state.iteration,
            )
            llm_resp = self.llm.call(prompt)
            raw_resp = llm_resp.text
            thought  = extract_json(raw_resp)

            state.react_trace.append(
                _make_llm_log(f"THOUGHT_{state.iteration}", state.iteration, llm_resp, thought)
            )

            action = thought.get("action", "")

            # ── ACTION: FINAL_DECISION ──────────────────────────
            if action == "FINAL_DECISION":
                final_decision = self._build_decision(thought)
                break

            # ── ACTION: CALL_TOOL ───────────────────────────────
            elif action == "CALL_TOOL":
                if state.tool_call_count >= self.config.max_tool_calls:
                    # Max tool calls ถึงแล้ว → force final decision
                    final_prompt  = self.prompt_builder.build_final_decision(
                        state.market_state,
                        state.tool_results,
                    )
                    llm_resp_fin  = self.llm.call(final_prompt)
                    raw_final     = llm_resp_fin.text
                    final_parsed  = extract_json(raw_final)
                    final_decision = self._build_decision(final_parsed)

                    state.react_trace.append(
                        _make_llm_log(
                            "THOUGHT_FINAL", state.iteration,
                            llm_resp_fin, final_parsed,
                            note="forced — max_tool_calls reached",
                        )
                    )
                    break

                tool_name = thought.get("tool_name", "")
                tool_args = thought.get("tool_args", {})

                observation = self._execute_tool(tool_name, tool_args)
                state.tool_results    = state.tool_results + [observation]  # no mutation
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
                    # TOOL_EXECUTION ไม่มี LLM metadata
                    "prompt_text":  "",
                    "response_raw": "",
                    "token_input":  0,
                    "token_output": 0,
                    "token_total":  0,
                    "model":        "",
                    "provider":     "",
                })
                continue

            # ── UNKNOWN ACTION ──────────────────────────────────
            else:
                state.react_trace.append({
                    "step":         "UNKNOWN_ACTION",
                    "iteration":    state.iteration,
                    "raw":          thought,
                    "prompt_text":  getattr(llm_resp, "prompt_text",  ""),
                    "response_raw": getattr(llm_resp, "text",         ""),
                    "token_input":  getattr(llm_resp, "token_input",  0),
                    "token_output": getattr(llm_resp, "token_output", 0),
                    "token_total":  getattr(llm_resp, "token_total",  0),
                    "model":        getattr(llm_resp, "model",        ""),
                    "provider":     getattr(llm_resp, "provider",     ""),
                })
                final_decision = self._fallback_decision("unknown action")
                break

        # ── Max iterations reached ──────────────────────────────
        if final_decision is None:
            final_prompt  = self.prompt_builder.build_final_decision(
                state.market_state,
                state.tool_results,
            )
            llm_resp_fin  = self.llm.call(final_prompt)
            raw_final     = llm_resp_fin.text
            final_parsed  = extract_json(raw_final)
            final_decision = self._build_decision(final_parsed)

            state.react_trace.append(
                _make_llm_log(
                    "THOUGHT_FINAL", state.iteration,
                    llm_resp_fin, final_parsed,
                    note="forced — max_iterations reached",
                )
            )

        adjusted_decision = self.risk_manager.evaluate(
            llm_decision=final_decision,
            market_state=market_state,
        )

        return {
            "final_decision":  adjusted_decision,
            "react_trace":     state.react_trace,
            "iterations_used": state.iteration,
            "tool_calls_used": state.tool_call_count,
            # ── top-level LLM metadata (consumed by services.py → llm_logs) ──
            **self._aggregate_trace(state.react_trace),
        }

    @staticmethod
    def _aggregate_trace(trace: list) -> dict:
        """
        สกัด top-level LLM metadata จาก trace entries
        เพื่อให้ services.py → _run_single_interval ดึงได้โดยตรง
        
        - prompt_text / response_raw  : มาจาก THOUGHT_FINAL step (step สุดท้ายที่เป็น LLM)
        - token_input/output/total    : รวมทุก LLM step (ไม่รวม TOOL_EXECUTION)
        """
        token_input  = 0
        token_output = 0
        token_total  = 0
        prompt_text  = ""
        response_raw = ""

        # รวม token ทุก LLM step และเก็บ prompt/response จาก THOUGHT_FINAL ล่าสุด
        for entry in trace:
            step = entry.get("step", "")
            if step == "TOOL_EXECUTION":
                continue  # ไม่มี token สำหรับ tool calls
            token_input  += entry.get("token_input",  0) or 0
            token_output += entry.get("token_output", 0) or 0
            token_total  += entry.get("token_total",  0) or 0
            # THOUGHT_FINAL คือ final decision step — เก็บ prompt/response จากตัวนี้
            if "FINAL" in step:
                prompt_text  = entry.get("prompt_text",  "") or ""
                response_raw = entry.get("response_raw", "") or ""

        return {
            "prompt_text":  prompt_text,
            "response_raw": response_raw,
            "token_input":  token_input  or None,
            "token_output": token_output or None,
            "token_total":  token_total  or None,
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