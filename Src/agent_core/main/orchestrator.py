"""
orchestrator.py
---------------
ReAct Loop หลักสำหรับระบบเทรดทองคำอัตโนมัติ

ขั้นตอน (ตรงกับ spec):
  Step 1 — Initialization       : โหลด Market State + ตั้งค่า LLM ด้วย System Prompt
  Step 2 — Thought 1 (Observe)  : ส่ง Market State ให้ LLM ประเมินรอบแรก
  Step 3 — Progressive Disclosure: ถ้า LLM ต้องการ tool ให้โหลด SKILL.md มาให้อ่าน
  Step 4 — Tool Execution       : รัน tool จริง (เช่น get_news.py) แล้วได้ Observation
  Step 5 — Thought 2 (Decide)   : ส่งข้อมูลทั้งหมดให้ LLM ตัดสินใจขั้นสุดท้าย
  Step 6 — JSON Output          : แยก JSON action แล้วเขียน output.json

การใช้งาน:
    python orchestrator.py                        # ใช้ mock LLM + mock news
    python orchestrator.py --live                 # ใช้ Gemini API จริง
    python orchestrator.py --input my_state.json  # โหลด market state จากไฟล์
    python orchestrator.py --verbose              # แสดง trace ทุก step
"""

import os
import json
import re
import time
import argparse
from datetime import datetime, timezone
from typing import Any

from agent_core.prompt.Prompt import (
    build_initial_analysis_prompt,
    build_skill_request_prompt,
    build_final_decision_prompt,
    build_conflict_resolution_prompt,
    PromptPackage,
)

from agent_core.skills.macro_news.get_news import get_news


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MAX_ITERATIONS   = 5
MAX_TOOL_CALLS   = 3
SKILL_MD_PATH    = "SKILL.md"

# แก้ตรงนี้: ชี้ไปที่โฟลเดอร์ Output/Output.json โดยอิงจากตำแหน่งไฟล์ orchestrator.py
# __file__ คือ path ของ orchestrator.py
# .. คือถอยออกไป 1 ชั้น (ไปที่ Src)
# ../.. คือถอยออกไป 2 ชั้น (ไปที่ Root)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(BASE_DIR, "..", "Output", "Output.json")

GEMINI_MODEL     = "gemini-1.5-flash"


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, callable] = {
    "get_news": get_news,
    # "get_macro_indicators": get_macro,
    # "get_gold_price":       get_price,
}


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class GeminiClient:
    """Wrapper สำหรับ Gemini API พร้อม mock mode"""

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        if not use_mock:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise EnvironmentError("GEMINI_API_KEY environment variable not set")
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(GEMINI_MODEL)

    def call(self, prompt_package: PromptPackage) -> str:
        if self.use_mock:
            return self._mock_response(prompt_package)
        full_prompt = (
            f"SYSTEM INSTRUCTIONS:\n{prompt_package.system}\n\n"
            f"USER:\n{prompt_package.user}"
        )
        response = self._model.generate_content(full_prompt)
        return response.text

    def _mock_response(self, prompt: PromptPackage) -> str:
        """Mock LLM responses — จำลองพฤติกรรม Gemini แต่ละ step"""
        step = prompt.step_label

        if step == "THOUGHT_1_INITIAL":
            return json.dumps({
                "thought": (
                    "RSI อยู่ที่ 28.5 ซึ่งต่ำมาก บ่งชี้ว่า oversold "
                    "แต่ทองคำมักขยับตามข่าว macro เช่น FED และ DXY "
                    "ข้อมูลตลาดที่มีอยู่ยังไม่พอ ต้องดูข่าวเศรษฐกิจก่อนตัดสินใจ"
                ),
                "action": "NEED_SKILL",
                "reason": "ต้องการ tool สำหรับดึงข่าว FED และ gold ล่าสุด",
            }, ensure_ascii=False, indent=2)

        elif step == "THOUGHT_1_SKILL_LOADED":
            return json.dumps({
                "thought": (
                    "อ่าน SKILL.md แล้ว มี tool ชื่อ get_news "
                    "จะใช้ keywords: FED interest rate, gold price, inflation "
                    "เพื่อประเมิน macro sentiment ก่อนตัดสินใจ"
                ),
                "action": "CALL_TOOL",
                "tool_name": "get_news",
                "tool_args": {
                    "keywords": ["FED interest rate", "gold price", "inflation"],
                    "max_results": 5,
                    "language": "en",
                },
            }, ensure_ascii=False, indent=2)

        elif step == "THOUGHT_2_FINAL":
            return json.dumps({
                "thought": (
                    "RSI = 28.5 (oversold) + ข่าว FED ส่งสัญญาณลดดอกเบี้ย = bullish. "
                    "DXY อ่อนตัว = หนุนทอง. News sentiment = +0.72 (bullish). "
                    "ทุก signal ชี้ทิศทางเดียวกัน ความเชื่อมั่นสูง → BUY"
                ),
                "action": "FINAL_DECISION",
                "signal": "BUY",
                "confidence": 0.82,
                "entry_price": 3025.40,
                "stop_loss": 2998.00,
                "take_profit": 3078.00,
                "rationale": (
                    "RSI oversold (28.5) + FED dovish signal + DXY อ่อน "
                    "= เงื่อนไขซื้อทองครบถ้วน Risk/Reward = 1:1.93"
                ),
                "key_factors": [
                    "RSI 28.5 — oversold zone",
                    "FED signals Q3 rate cut",
                    "DXY ลดลง 0.4% — หนุนทอง",
                    "News sentiment +0.72 (bullish)",
                ],
            }, ensure_ascii=False, indent=2)

        elif step == "CONFLICT_RESOLUTION":
            return json.dumps({
                "thought": "Signals ขัดแย้ง ความเชื่อมั่นต่ำ → HOLD",
                "action": "FINAL_DECISION",
                "signal": "HOLD",
                "confidence": 0.38,
                "entry_price": 0.0,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "rationale": "Signals ขัดแย้งกัน ไม่มีทิศทางชัดเจน รอข้อมูลเพิ่มเติม",
                "key_factors": ["Signal conflict detected", "Confidence below threshold"],
            }, ensure_ascii=False, indent=2)

        else:
            return json.dumps({
                "thought": "ข้อมูลไม่เพียงพอ",
                "action": "FINAL_DECISION",
                "signal": "HOLD",
                "confidence": 0.30,
                "entry_price": 0.0,
                "stop_loss": 0.0,
                "take_profit": 0.0,
                "rationale": "Fallback — ไม่สามารถประเมินได้",
                "key_factors": [],
            }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# JSON extractor
# ---------------------------------------------------------------------------

def extract_json(raw_text: str) -> dict:
    """แยก JSON จาก LLM response รองรับทั้ง raw JSON และ markdown block"""
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, raw_text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    brace_match = re.search(r"\{[\s\S]*\}", raw_text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"ไม่สามารถแยก JSON จาก LLM response:\n{raw_text[:300]}")


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

def execute_tool(tool_name: str, tool_args: dict) -> dict:
    """รัน tool จาก TOOL_REGISTRY แล้วคืน Observation"""
    if tool_name not in TOOL_REGISTRY:
        return {
            "tool":   tool_name,
            "status": "error",
            "error":  f"tool '{tool_name}' ไม่อยู่ใน registry: {list(TOOL_REGISTRY.keys())}",
        }
    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        return tool_fn(**tool_args)
    except TypeError as exc:
        return {"tool": tool_name, "status": "error", "error": f"arguments ไม่ถูกต้อง: {exc}"}
    except Exception as exc:
        return {"tool": tool_name, "status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Skill loader
# ---------------------------------------------------------------------------

def load_skill_md() -> str:
    try:
        with open(SKILL_MD_PATH, "r", encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return f"[ERROR] ไม่พบไฟล์ {SKILL_MD_PATH}"


# ---------------------------------------------------------------------------
# Conflict detector
# ---------------------------------------------------------------------------

def _detect_conflicts(market_state: dict, tool_results: list[dict]) -> tuple[bool, str]:
    conflicts = []
    rsi = market_state.get("rsi_1h") or market_state.get("rsi", 50)
    macd = market_state.get("macd_signal", "")
    news_sentiment = 0.0
    for tr in tool_results:
        if tr.get("tool") == "get_news":
            news_sentiment = tr.get("composite_sentiment", 0.0)
    if rsi < 35 and news_sentiment < -0.3:
        conflicts.append(
            f"RSI={rsi} (oversold → bullish) ขัดกับ news sentiment={news_sentiment:.2f} (bearish)"
        )
    if rsi > 65 and news_sentiment > 0.3:
        conflicts.append(
            f"RSI={rsi} (overbought → bearish) ขัดกับ news sentiment={news_sentiment:.2f} (bullish)"
        )
    if "bearish" in str(macd).lower() and news_sentiment > 0.5:
        conflicts.append(f"MACD bearish ขัดกับ news bullish sentiment={news_sentiment:.2f}")
    has_conflict = len(conflicts) > 0
    description = "\n".join(conflicts) if conflicts else "ไม่พบ conflicts"
    return has_conflict, description


# ---------------------------------------------------------------------------
# ReAct Loop
# ---------------------------------------------------------------------------

def run_react_loop(
    market_state: dict[str, Any],
    llm: GeminiClient,
    verbose: bool = False,
) -> dict:
    """รัน ReAct Loop ทั้ง 6 ขั้นตอน"""

    run_id          = f"gold-react-{int(time.time())}"
    skill_content   = load_skill_md()
    tool_results:   list[dict] = []
    react_trace:    list[dict] = []
    tool_call_count = 0
    iteration       = 0
    final_decision: dict | None = None

    def log(msg: str):
        if verbose:
            print(msg)

    log(f"\n{'='*60}")
    log(f" GoldTrader ReAct Loop  run_id={run_id}")
    log(f"{'='*60}")

    # ── STEP 1: Initialization ──────────────────────────────────────────
    log("\n[STEP 1] Initialization — โหลด Market State + SKILL.md")
    log(f"  Gold price : ${market_state.get('gold_price_usd', 'N/A')}")
    log(f"  RSI        : {market_state.get('rsi_1h', 'N/A')}")
    log(f"  MACD       : {market_state.get('macd_signal', 'N/A')}")

    while iteration < MAX_ITERATIONS:
        iteration += 1
        log(f"\n{'─'*50}")
        log(f"  Iteration {iteration}/{MAX_ITERATIONS}")

        # ── STEP 2: Thought 1 ────────────────────────────────────────────
        log(f"\n[STEP 2] Thought 1 — ส่ง Market State ให้ LLM ประเมิน")
        prompt1 = build_initial_analysis_prompt(market_state)
        raw1    = llm.call(prompt1)
        parsed1 = extract_json(raw1)

        log(f"  LLM action : {parsed1.get('action')}")
        log(f"  LLM thought: {parsed1.get('thought', '')[:120]}...")

        react_trace.append({
            "step": "THOUGHT_1", "iteration": iteration,
            "prompt": prompt1.step_label, "response": parsed1,
        })

        if parsed1.get("action") == "FINAL_DECISION":
            log("  [STEP 5→6] LLM ตัดสินใจได้เลยจาก Market State")
            final_decision = parsed1
            break

        # ── STEP 3: Progressive Disclosure ───────────────────────────────
        if parsed1.get("action") in ("NEED_SKILL", "CALL_TOOL"):
            log(f"\n[STEP 3] Progressive Disclosure — โหลด SKILL.md ให้ LLM อ่าน")
            prompt2 = build_skill_request_prompt(market_state, skill_content)
            raw2    = llm.call(prompt2)
            parsed2 = extract_json(raw2)

            log(f"  LLM action : {parsed2.get('action')}")
            log(f"  LLM thought: {parsed2.get('thought', '')[:120]}...")

            react_trace.append({
                "step": "SKILL_LOADED", "iteration": iteration,
                "prompt": prompt2.step_label, "response": parsed2,
            })

            # ── STEP 4: Tool Execution ────────────────────────────────────
            if parsed2.get("action") == "CALL_TOOL":
                tool_name = parsed2.get("tool_name", "")
                tool_args = parsed2.get("tool_args", {})

                if tool_call_count >= MAX_TOOL_CALLS:
                    log(f"  [WARN] Tool call limit ({MAX_TOOL_CALLS}) ถึงแล้ว — ข้าม")
                else:
                    log(f"\n[STEP 4] Tool Execution — รัน {tool_name}")
                    log(f"  Args: {tool_args}")

                    observation = execute_tool(tool_name, tool_args)
                    tool_results.append(observation)
                    tool_call_count += 1

                    log(f"  Status    : {observation.get('status')}")
                    if tool_name == "get_news":
                        log(f"  Sentiment : {observation.get('composite_sentiment', 'N/A')}")
                        log(f"  Theme     : {observation.get('dominant_theme', 'N/A')}")
                        for art in observation.get("results", [])[:3]:
                            icon = {"bullish": "▲", "bearish": "▼", "neutral": "—"}.get(
                                art.get("sentiment", "neutral"), "?"
                            )
                            log(f"  [{icon}] {art.get('headline', '')}")

                    react_trace.append({
                        "step": "TOOL_EXECUTION", "iteration": iteration,
                        "tool_name": tool_name, "tool_args": tool_args,
                        "observation": observation,
                    })

        # ── STEP 5: Thought 2 — Final Decision ───────────────────────────
        log(f"\n[STEP 5] Thought 2 — รวมข้อมูลทั้งหมด ตัดสินใจขั้นสุดท้าย")
        has_conflict, conflict_desc = _detect_conflicts(market_state, tool_results)

        if has_conflict:
            log(f"  [WARN] Conflict: {conflict_desc}")
            prompt3 = build_conflict_resolution_prompt(
                market_state, tool_results, conflict_desc
            )
        else:
            prompt3 = build_final_decision_prompt(
                market_state, tool_results, skill_content
            )

        raw3    = llm.call(prompt3)
        parsed3 = extract_json(raw3)

        log(f"  LLM action  : {parsed3.get('action')}")
        log(f"  Signal      : {parsed3.get('signal', 'N/A')}")
        log(f"  Confidence  : {parsed3.get('confidence', 'N/A')}")

        react_trace.append({
            "step": "THOUGHT_2_FINAL", "iteration": iteration,
            "prompt": prompt3.step_label, "response": parsed3,
        })

        if parsed3.get("action") == "FINAL_DECISION":
            final_decision = parsed3
            break

        # LLM ต้องการ tool เพิ่ม (loop ต่อ)
        if parsed3.get("action") == "CALL_TOOL" and tool_call_count < MAX_TOOL_CALLS:
            tool_name = parsed3.get("tool_name", "")
            tool_args = parsed3.get("tool_args", {})
            log(f"  [LOOP] LLM ต้องการ tool เพิ่ม: {tool_name}")
            observation = execute_tool(tool_name, tool_args)
            tool_results.append(observation)
            tool_call_count += 1
            react_trace.append({
                "step": "TOOL_EXECUTION_EXTRA", "iteration": iteration,
                "tool_name": tool_name, "tool_args": tool_args,
                "observation": observation,
            })
            continue

        # Fallback
        log(f"  [WARN] ถึง max iterations — ใช้ HOLD")
        final_decision = {
            "action": "FINAL_DECISION", "signal": "HOLD",
            "confidence": 0.30, "entry_price": 0.0,
            "stop_loss": 0.0, "take_profit": 0.0,
            "rationale": f"Max iterations ({MAX_ITERATIONS}) ถึงแล้ว",
            "key_factors": ["max_iterations_reached"],
        }
        break

    # ── STEP 6: JSON Output ───────────────────────────────────────────────
    log(f"\n[STEP 6] สร้าง {OUTPUT_PATH}")

    if not final_decision:
        final_decision = {
            "action": "FINAL_DECISION", "signal": "HOLD",
            "confidence": 0.0, "entry_price": 0.0,
            "stop_loss": 0.0, "take_profit": 0.0,
            "rationale": "ไม่ได้รับ final decision จาก LLM",
            "key_factors": [],
        }

    output = {
        "run_id":          run_id,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        "iterations_used": iteration,
        "tool_calls_used": tool_call_count,
        "market_state":    market_state,
        "final_decision": {
            "signal":      final_decision.get("signal"),
            "confidence":  final_decision.get("confidence"),
            "entry_price": final_decision.get("entry_price"),
            "stop_loss":   final_decision.get("stop_loss"),
            "take_profit": final_decision.get("take_profit"),
            "rationale":   final_decision.get("rationale"),
            "key_factors": final_decision.get("key_factors", []),
        },
        "react_trace": react_trace,
    }

    return output


# ---------------------------------------------------------------------------
# Result printer
# ---------------------------------------------------------------------------

def print_result(output: dict) -> None:
    fd = output["final_decision"]
    signal = fd.get("signal", "N/A")
    signal_icon = {"BUY": "▲ BUY ", "SELL": "▼ SELL", "HOLD": "— HOLD"}.get(signal, signal)

    print(f"\n{'='*60}")
    print(f" GOLD TRADING DECISION")
    print(f"{'='*60}")
    print(f"  Run ID       : {output['run_id']}")
    print(f"  Iterations   : {output['iterations_used']}")
    print(f"  Tool calls   : {output['tool_calls_used']}")
    print(f"  Signal       : {signal_icon}")
    print(f"  Confidence   : {fd.get('confidence', 0):.2%}")
    if signal != "HOLD":
        print(f"  Entry price  : ${fd.get('entry_price', 0):,.2f}")
        print(f"  Stop loss    : ${fd.get('stop_loss', 0):,.2f}")
        print(f"  Take profit  : ${fd.get('take_profit', 0):,.2f}")
    print(f"  Rationale    : {fd.get('rationale', '')}")
    print(f"\n  Key factors:")
    for factor in fd.get("key_factors", []):
        print(f"    • {factor}")
    print(f"\n  Output file  : {OUTPUT_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GoldTrader ReAct Orchestrator")
    parser.add_argument("--input",   default=None,        help="Path to market state JSON")
    parser.add_argument("--live",    action="store_true",  help="ใช้ Gemini API จริง")
    parser.add_argument("--verbose", action="store_true",  help="แสดง trace ทุก step")
    parser.add_argument("--output",  default=OUTPUT_PATH,  help="ชื่อไฟล์ output")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as fh:
            market_state = json.load(fh)
        print(f"[orchestrator] โหลด market state จาก {args.input}")
    else:
        market_state = {
            "timestamp":      "2025-03-25T08:00:00Z",
            "gold_price_usd": 3025.40,
            "rsi_1h":         28.5,
            "macd_signal":    "bullish_crossover",
            "dxy":            103.72,
            "vix":            18.4,
            "us10y_yield":    4.31,
            "spx_1d_return":  -0.0082,
            "gold_etf_flow":  240.5,
        }
        print("[orchestrator] ใช้ mock market state")

    use_mock = not args.live
    llm = GeminiClient(use_mock=use_mock)
    print(f"[orchestrator] LLM mode: {'mock' if use_mock else 'Gemini API'}")

    output = run_react_loop(market_state, llm, verbose=args.verbose)

    out_path = args.output
    
    # --- เพิ่ม 2 บรรทัดนี้เพื่อเช็กและสร้าง Folder ---
    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True) 
    # -------------------------------------------

    print(f"[orchestrator] กำลังเขียนไฟล์ไปที่: {out_path}") # เช็ก path อีกรอบตอนรัน
    
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, ensure_ascii=False, default=str)

    print_result(output)


if __name__ == "__main__":
    main()