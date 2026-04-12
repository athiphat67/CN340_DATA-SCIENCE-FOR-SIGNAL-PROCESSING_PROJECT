"""
react.py — Part B: ReAct Orchestration Loop
Thought → Action → Observation → ... → FINAL_DECISION

v2: แก้ไขให้รองรับ LLMResponse จาก client.py
    - บันทึก prompt_text, response_raw, token_input/output/total, model
      ลงใน react_trace ทุก step เพื่อ LLM Log UI

v2.1 (fixes):
    - [FIX #1] extract_json: ตรวจ _parse_error ก่อนส่งเข้า _build_decision — log warning ทุกครั้ง
    - [FIX #2] RiskManager รับผ่าน __init__ (dependency injection) แทน hardcode
    - [FIX #3] _aggregate_trace: แยก token count กับ prompt/response ให้ถูกต้อง
                ใช้ elif "FINAL" เพื่อกัน overwrite ซ้ำ และไม่นับ token จาก FINAL ซ้ำ
    - [FIX #4] extract_json: หา JSON ที่มี key "action" หรือ "signal" ก่อน แทน match แรกที่เจอ
"""

import json
import logging
import re
import inspect 
from typing import Optional
from dataclasses import dataclass, field
from .risk import RiskManager

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Config (ต้องอยู่ก่อน ReactState)
# ─────────────────────────────────────────────


@dataclass
class ReactConfig:
    """Config สำหรับ ReAct loop"""

    max_iterations: int = 5
    max_tool_calls: int = 0  # 0 = ไม่ใช้ tool (data pre-loaded)
    timeout_seconds: Optional[int] = None  # TODO: enforce at orchestration level


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────


@dataclass
class ToolResult:
    """Result จากการ execute tool"""

    tool_name: str
    status: str  # "success" | "error"
    data: dict
    error: Optional[str] = None


@dataclass
class ReactState:
    """Mutable state ตลอด loop"""

    market_state: dict
    tool_results: list  # list[ToolResult]
    iteration: int = 0
    tool_call_count: int = 0
    react_trace: list = field(default_factory=list)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────


def extract_json(raw: str) -> dict:
    """
    Parse JSON จาก LLM response อย่างปลอดภัย
    รองรับ: plain JSON, ```json ... ```, ``` ... ```

    [FIX #4] ลำดับการหา JSON:
      1. หา JSON object ที่มี key "action" หรือ "signal" — decision object จริงๆ
      2. fallback: JSON object แรกที่เจอ
      3. fallback: parse ทั้ง string
      4. คืน _parse_error dict พร้อม raw สำหรับ debug
    """
    if not raw or not raw.strip():
        return {"_parse_error": True, "_raw": ""}

    # Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    # หา JSON objects ทั้งหมดใน response
    candidates = []
    for m in re.finditer(r"\{.*?\}", cleaned, re.DOTALL):
        try:
            obj = json.loads(m.group())
            candidates.append(obj)
        except json.JSONDecodeError:
            pass

    # [FIX #4] เลือก decision object ก่อน — ต้องมี key "action" หรือ "signal"
    for obj in candidates:
        if "action" in obj or "signal" in obj:
            return obj

    # fallback: JSON object แรกที่ parse ได้
    if candidates:
        return candidates[0]

    # fallback: parse ทั้ง string
    try:
        result = json.loads(cleaned)
        # [FIX #5] json.loads สำเร็จแต่ได้ str/int/bool ออกมา (เช่น LLM ตอบแค่ "HOLD")
        # → caller ทุกตัวคาดหวัง dict เสมอ ถือเป็น parse error
        if not isinstance(result, dict):
            logger.warning(
                f"extract_json: json.loads returned {type(result).__name__} "
                f"(value={repr(result)[:100]}) — treating as parse error"
            )
            return {"_parse_error": True, "_raw": raw[:500], "_parsed_value": result}
        return result
    except json.JSONDecodeError:
        return {"_parse_error": True, "_raw": raw[:500]}


def _check_parse_error(parsed: dict, context: str = "") -> bool:
    """
    [FIX #1] ตรวจ parse error และ log warning
    Return True ถ้ามี error (caller ควร fallback)
    """
    if parsed.get("_parse_error"):
        raw_preview = parsed.get("_raw", "")[:200]
        logger.warning(
            f"LLM response parse failed{' at ' + context if context else ''} — "
            f"falling back to HOLD. Raw preview: {repr(raw_preview)}"
        )
        return True
    return False


def _make_llm_log(
    step: str,
    iteration: int,
    llm_resp,  # LLMResponse object จาก client.py
    parsed: dict,
    note: str = "",
) -> dict:
    """
    Helper: สร้าง trace entry พร้อม LLM metadata ครบถ้วน

    Args:
        llm_resp: LLMResponse instance (หรือ None ถ้า fallback)
    """
    entry = {
        "step": step,
        "iteration": iteration,
        "response": parsed,
        # ── LLM metadata ──────────────────────────────────────────
        "prompt_text": getattr(llm_resp, "prompt_text", "") if llm_resp else "",
        "response_raw": getattr(llm_resp, "text", "") if llm_resp else "",
        "token_input": getattr(llm_resp, "token_input", 0) if llm_resp else 0,
        "token_output": getattr(llm_resp, "token_output", 0) if llm_resp else 0,
        "token_total": getattr(llm_resp, "token_total", 0) if llm_resp else 0,
        "model": getattr(llm_resp, "model", "") if llm_resp else "",
        "provider": getattr(llm_resp, "provider", "") if llm_resp else "",
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
      risk_manager   — RiskManager (optional, สร้าง default ถ้าไม่ส่งมา)
    """

    def __init__(
        self,
        llm_client,
        prompt_builder,
        tool_registry: dict,
        config: ReactConfig,
        # [FIX #2] รับ RiskManager จากภายนอกแทน hardcode
        risk_manager: Optional[RiskManager] = None,
    ):
        self.llm = llm_client
        self.prompt_builder = prompt_builder
        self.tools = tool_registry
        self.config = config
        # [FIX #2] ถ้าไม่ส่งมาค่อย fallback เป็น default — แต่ log warning ให้รู้
        if risk_manager is None:
            logger.warning(
                "RiskManager not injected — using default params "
                "(atr_multiplier=2.0, risk_reward_ratio=1.5). "
                "Consider passing risk_manager explicitly."
            )
            self.risk_manager = RiskManager(atr_multiplier=2.0, risk_reward_ratio=1.5)
        else:
            self.risk_manager = risk_manager

    # ── Entry point ─────────────────────────────

    def run(
        self,
        market_state: dict,
        initial_observation: Optional[ToolResult] = None,
        ohlcv_df=None, # 🎯 เพิ่มตรงนี้
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
            prompt = self.prompt_builder.build_final_decision(market_state, [])

            # ── Check prompt before input LLM ───────────────
            # print(f"\n{'=' * 20} [DEBUG: PROMPT BEFORE AI] {'=' * 20}")
            # print(f"SYSTEM: {prompt.system[:200]}...")  # ปริ้นพอสังเขป
            # print(f"USER:\n{prompt.user}")
            # print(f"{'=' * 60}\n")

            # llm_resp = self.llm.call(prompt)
            # raw = llm_resp.text

            # # --- เพิ่มการปริ้น AI Response (ความคิด AI) ---
            # print(f"\n{'=' * 20} [DEBUG: PROMPT AFTER AI] {'=' * 20}")
            # print(f"{raw}")
            # print(f"{'=' * 60}\n")
            logger.debug("[ReAct] fast_path prompt_len=%d", len(prompt.user))
            llm_resp = self.llm.call(prompt)
            raw = llm_resp.text
            logger.debug("[ReAct] fast_path response=%s", raw[:200])

            parsed = extract_json(raw)

            # [FIX #1] ตรวจ parse error ก่อน build decision
            if _check_parse_error(parsed, context="fast_path"):
                parsed = {}

            llm_decision = self._build_decision(parsed)
            adjusted_decision = self.risk_manager.evaluate(
                llm_decision=llm_decision,
                market_state=market_state,
            )

            trace = [_make_llm_log("THOUGHT_FINAL", 1, llm_resp, parsed)]
            return {
                "final_decision": adjusted_decision,
                "react_trace": trace,
                "iterations_used": 1,
                "tool_calls_used": 0,
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
            prompt = self.prompt_builder.build_thought(
                state.market_state,
                state.tool_results,
                state.iteration,
            )

            # ──(IN While loop) Check prompt before input LLM ───────────────
            print(f"\n{'=' * 20} [DEBUG: (IN While loop) PROMPT BEFORE AI] {'=' * 20}")
            print(f"SYSTEM: {prompt.system[:200]}...")  # ปริ้นพอสังเขป
            print(f"USER:\n{prompt.user}")
            print(f"{'=' * 60}\n")

            # llm_resp = self.llm.call(prompt)
            # raw_resp = llm_resp.text

            # # --- เพิ่มการปริ้น AI Response (ความคิด AI) ---
            # print(f"\n{'=' * 20} [DEBUG: (IN While loop) PROMPT AFTER AI] {'=' * 20}")
            # print(f"{raw_resp}")
            # print(f"{'=' * 60}\n")
            logger.debug("[ReAct] iter=%d prompt_len=%d", state.iteration, len(prompt.user))
            llm_resp = self.llm.call(prompt)
            raw_resp = llm_resp.text
            logger.debug("[ReAct] iter=%d response=%s", state.iteration, raw_resp[:200])

            thought = extract_json(raw_resp)

            # [FIX #1] ตรวจ parse error — ถ้าพัง fallback เป็น HOLD ทันที
            if _check_parse_error(thought, context=f"iteration_{state.iteration}"):
                state.react_trace.append(
                    _make_llm_log(
                        f"THOUGHT_{state.iteration}",
                        state.iteration,
                        llm_resp,
                        thought,
                        note="parse_error — fallback to HOLD",
                    )
                )
                final_decision = self._fallback_decision("LLM response parse failed")
                break

            state.react_trace.append(
                _make_llm_log(
                    f"THOUGHT_{state.iteration}", state.iteration, llm_resp, thought
                )
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
                    final_prompt = self.prompt_builder.build_final_decision(
                        state.market_state,
                        state.tool_results,
                    )

                    # ──(IN Elif action == 'CALL_TOOL') Check prompt before input LLM ───────────────
                    # print(
                    #     f"\n{'=' * 20} [DEBUG: (IN Elif action == 'CALL_TOOL') PROMPT BEFORE AI] {'=' * 20}"
                    # )
                    # print(f"SYSTEM: {final_prompt.system[:200]}...")  # ปริ้นพอสังเขป
                    # print(f"USER:\n{final_prompt.user}")
                    # print(f"{'=' * 60}\n")

                    # llm_resp_fin = self.llm.call(final_prompt)
                    # raw_final = llm_resp_fin.text

                    # # --- เพิ่มการปริ้น AI Response (ความคิด AI) ---
                    # print(
                    #     f"\n{'=' * 20} (IN Elif action == 'CALL_TOOL') [DEBUG: PROMPT AFTER AI] {'=' * 20}"
                    # )
                    # print(f"{raw_final}")
                    # print(f"{'=' * 60}\n")
                    logger.debug("[ReAct] forced_final (max_tool_calls) prompt_len=%d", len(final_prompt.user))
                    llm_resp_fin = self.llm.call(final_prompt)
                    raw_final = llm_resp_fin.text
                    logger.debug("[ReAct] forced_final response=%s", raw_final[:200])

                    final_parsed = extract_json(raw_final)

                    # [FIX #1] ตรวจ parse error ของ forced final
                    if _check_parse_error(
                        final_parsed, context="forced_final_max_tool_calls"
                    ):
                        final_parsed = {}

                    final_decision = self._build_decision(final_parsed)

                    state.react_trace.append(
                        _make_llm_log(
                            "THOUGHT_FINAL",
                            state.iteration,
                            llm_resp_fin,
                            final_parsed,
                            note="forced — max_tool_calls reached",
                        )
                    )
                    break

                tool_name = thought.get("tool_name", "")
                tool_args = thought.get("tool_args", {})
                
                base_interval = market_state.get("interval", "5m")
                observation = self._execute_tool(
                    tool_name, 
                    tool_args,
                    ohlcv_df=ohlcv_df,
                    base_interval=base_interval
                )

                # observation = self._execute_tool(tool_name, tool_args)
                state.tool_results = state.tool_results + [observation]  # no mutation
                state.tool_call_count += 1

                state.react_trace.append(
                    {
                        "step": "TOOL_EXECUTION",
                        "iteration": state.iteration,
                        "tool_name": tool_name,
                        "observation": {
                            "status": observation.status,
                            "data": observation.data,
                            "error": observation.error,
                        },
                        # TOOL_EXECUTION ไม่มี LLM metadata
                        "prompt_text": "",
                        "response_raw": "",
                        "token_input": 0,
                        "token_output": 0,
                        "token_total": 0,
                        "model": "",
                        "provider": "",
                    }
                )
                continue

            # ── UNKNOWN ACTION ──────────────────────────────────
            else:
                logger.warning(
                    f"Unknown action '{action}' at iteration {state.iteration} — "
                    "falling back to HOLD"
                )
                state.react_trace.append(
                    {
                        "step": "UNKNOWN_ACTION",
                        "iteration": state.iteration,
                        "raw": thought,
                        "prompt_text": getattr(llm_resp, "prompt_text", ""),
                        "response_raw": getattr(llm_resp, "text", ""),
                        "token_input": getattr(llm_resp, "token_input", 0),
                        "token_output": getattr(llm_resp, "token_output", 0),
                        "token_total": getattr(llm_resp, "token_total", 0),
                        "model": getattr(llm_resp, "model", ""),
                        "provider": getattr(llm_resp, "provider", ""),
                        "note": f"unknown action: '{action}'",
                    }
                )
                final_decision = self._fallback_decision(f"unknown action: '{action}'")
                break

        # ── Max iterations reached ──────────────────────────────
        if final_decision is None:
            final_prompt = self.prompt_builder.build_final_decision(
                state.market_state,
                state.tool_results,
            )
            llm_resp_fin = self.llm.call(final_prompt)
            raw_final = llm_resp_fin.text
            final_parsed = extract_json(raw_final)

            # [FIX #1] ตรวจ parse error ของ max_iterations final
            if _check_parse_error(final_parsed, context="forced_final_max_iterations"):
                final_parsed = {}

            final_decision = self._build_decision(final_parsed)

            state.react_trace.append(
                _make_llm_log(
                    "THOUGHT_FINAL",
                    state.iteration,
                    llm_resp_fin,
                    final_parsed,
                    note="forced — max_iterations reached",
                )
            )

        adjusted_decision = self.risk_manager.evaluate(
            llm_decision=final_decision,
            market_state=market_state,
        )

        return {
            "final_decision": adjusted_decision,
            "react_trace": state.react_trace,
            "iterations_used": state.iteration,
            "tool_calls_used": state.tool_call_count,
            **self._aggregate_trace(state.react_trace),
        }

    @staticmethod
    def _aggregate_trace(trace: list) -> dict:
        """
        สกัด top-level LLM metadata จาก trace entries
        เพื่อให้ services.py → _run_single_interval ดึงได้โดยตรง

        - prompt_text / response_raw : มาจาก THOUGHT_FINAL step ล่าสุด
        - token_input/output/total   : รวมทุก LLM step (ไม่รวม TOOL_EXECUTION)

        [FIX #3] ใช้ elif "FINAL" เพื่อกัน overwrite ซ้ำกรณี edge case
                 และ skip token นับซ้ำสำหรับ FINAL step ที่ถูกนับแยกอยู่แล้ว
        """
        token_input = 0
        token_output = 0
        token_total = 0
        prompt_text = ""
        response_raw = ""

        for entry in trace:
            step = entry.get("step", "")

            if step == "TOOL_EXECUTION":
                continue

            # [FIX #3] แยก: FINAL step → เก็บ prompt/response และนับ token
            #               non-FINAL step → นับ token เท่านั้น
            token_input += entry.get("token_input", 0) or 0
            token_output += entry.get("token_output", 0) or 0
            token_total += entry.get("token_total", 0) or 0

            if "FINAL" in step:
                # overwrite ด้วย FINAL ล่าสุดเสมอ (ถ้ามีหลายตัว)
                prompt_text = entry.get("prompt_text", "") or ""
                response_raw = entry.get("response_raw", "") or ""

        return {
            "prompt_text": prompt_text,
            "response_raw": response_raw,
            "token_input": token_input or None,
            "token_output": token_output or None,
            "token_total": token_total or None,
        }

    # ── Private helpers ─────────────────────────


    def _execute_tool(self, tool_name: str, tool_args: dict, ohlcv_df=None, base_interval=None) -> ToolResult:
        if tool_name not in self.tools:
            logger.warning(f"Tool '{tool_name}' not found in registry")
            return ToolResult(tool_name=tool_name, status="error", data={}, error=f"Tool '{tool_name}' not found")
        
        target = self.tools[tool_name]
        fn = target["fn"] if isinstance(target, dict) and "fn" in target else target

        # 🔥 [FIX] สร้าง Copy ของ arguments ป้องกันการยัด DataFrame กลับไปใน Trace ของ AI
        exec_args = tool_args.copy()

        try:
            sig = inspect.signature(fn)
            if ohlcv_df is not None and "ohlcv_df" in sig.parameters:
                requested_interval = exec_args.get("interval", base_interval)
                if requested_interval == base_interval:
                    exec_args["ohlcv_df"] = ohlcv_df
                    logger.info(f"💉 [Smart Injection] ส่ง DataFrame ที่มีอยู่เข้า '{tool_name}' สำเร็จ (ข้ามการดึง API ซ้ำ)")
        except Exception as e:
            logger.warning(f"Signature check failed for {tool_name}: {e}")

        try:
            # 🔥 [FIX] ใช้ exec_args ที่เป็น Copy แทน
            result = fn(**exec_args)
            return ToolResult(tool_name=tool_name, status="success", data=result)
        except Exception as exc:
            logger.error(f"Tool '{tool_name}' execution failed: {exc}")
            return ToolResult(tool_name=tool_name, status="error", data={}, error=str(exc))

    @staticmethod
    def _build_decision(parsed: dict) -> dict:
        """Normalise LLM output → final_decision dict"""
        return {
            "signal": parsed.get("signal", "HOLD"),
            "confidence": float(parsed.get("confidence", 0.0)),
            "entry_price": parsed.get("entry_price"),
            "stop_loss": parsed.get("stop_loss"),
            "take_profit": parsed.get("take_profit"),
            "rationale": parsed.get("rationale", parsed.get("thought", "")),
        }

    @staticmethod
    def _fallback_decision(reason: str = "") -> dict:
        return {
            "signal": "HOLD",
            "confidence": 0.0,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "rationale": f"Fallback HOLD — {reason}",
        }
