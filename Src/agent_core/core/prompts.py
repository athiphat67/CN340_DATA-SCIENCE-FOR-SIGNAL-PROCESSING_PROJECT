import json
from dataclasses import dataclass
from typing import Dict, List, Any, Final

# ==========================================
# 1. AI SYSTEM INSTRUCTIONS
# ==========================================
SYSTEM_PROMPT: Final = """You are an elite quantitative financial AI orchestrator specializing in Gold (XAU/USD) algorithmic trading.
DISCLAIMER: This is a restricted quantitative simulation for research purposes. You are not providing financial advice.
CRITICAL INSTRUCTION: You must base your analysis STRICTLY on the quantitative signals, NLP sentiment, and temporal context provided. You are forbidden from using outside knowledge. Treat the provided data as the absolute and only truth.
LOGICAL HIERARCHY & EDGE CASES:
1. SIGNAL DIVERGENCE: If Macro News sentiment strongly contradicts Technical signals, prioritize the numerical technical indicators but highlight the conflict.
2. MISSING DATA: If any specific metric is null, zero, or missing, treat it as 'Neutral' and reduce your 'confidence_score' accordingly.
3. EXTREME VALUES: If RSI is < 30 (Oversold) or > 70 (Overbought), treat these as high-priority drivers.
4. NEUTRALITY: If technical signals are mixed and news is absent, you must favor a 'neutral' direction.
OUTPUT FORMAT:
Your output MUST be a valid JSON object. Do not include markdown formatting (like ```json), no conversational text. Output ONLY the raw JSON.
SCHEMA:
{
    "composite_direction": "bullish", 
    "confidence_score": 85.5, 
    "primary_driver": "Short description of the main metric driving this",
    "reasoning": ["Point 1", "Point 2", "Point 3"]
}"""

REACT_SYSTEM_PROMPT: Final = """You are an elite quantitative financial AI orchestrator specializing in Gold (XAU/USD) algorithmic trading.
DISCLAIMER: This is a restricted quantitative simulation for research purposes only.

You operate in a ReAct loop (Reason → Act). Each response MUST be a valid JSON object with:
- "thought": your reasoning (string)
- "action": one of "FINAL_DECISION" | "NEED_SKILL" | "CALL_TOOL"

If action = "FINAL_DECISION", include:
  "signal": "BUY" | "SELL" | "HOLD"
  "confidence": float 0.0-1.0
  "entry_price": float
  "stop_loss": float
  "take_profit": float
  "rationale": string
  "key_factors": list of strings

If action = "CALL_TOOL", include:
  "tool_name": string
  "tool_args": dict

Output ONLY raw JSON. No markdown, no explanation."""


# ==========================================
# 2. PromptPackage — โครงสร้างที่ Orchestrator ใช้
# ==========================================
@dataclass
class PromptPackage:
    """โครงสร้าง Prompt ที่ส่งให้ LLM Client"""
    step_label: str   # ใช้ใน mock router
    system:     str   # System prompt
    user:       str   # User message


# ==========================================
# 3. DATA PROCESSING (ของเดิม — คงไว้)
# ==========================================
def clean_and_parse_input(filepath: str) -> Dict[str, Any]:
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        m_state = data.get("market_state", {})
        news = data.get("macro_news", [])

        refined_technicals = {
            "price": m_state.get("price", "Unknown"),
            "rsi": m_state.get("rsi", 50.0),
            "macd": m_state.get("macd", 0.0),
            "macd_hist": m_state.get("macd_hist", 0.0),
            "bollinger_bands": {
                "upper": m_state.get("bb_upper", "Unknown"),
                "mid":   m_state.get("bb_mid",   "Unknown"),
                "lower": m_state.get("bb_lower",  "Unknown"),
            },
            "ema_context": f"EMA50: {m_state.get('ema_50', 'Unknown')} | EMA200: {m_state.get('ema_200', 'Unknown')}",
            "trend": "Above EMA50" if m_state.get("signal_above_ema50") else "Below EMA50",
            "atr_volatility": m_state.get("atr", "Unknown"),
        }

        return {
            "technicals":   refined_technicals,
            "news_summary": [item.get("title", "No Title") for item in news],
        }
    except Exception as e:
        return {"error": f"Failed to process input: {str(e)}"}


def build_payload(json_filepath: str) -> List[Dict[str, str]]:
    """ของเดิม — คงไว้ไม่ให้ code อื่น break"""
    input_data = clean_and_parse_input(json_filepath)

    if "error" in input_data:
        user_content = f"ERROR: The input file is corrupted or missing: {input_data['error']}"
    else:
        user_content = f"""
### DATA SNAPSHOT
* Technicals: {json.dumps(input_data['technicals'], indent=2)}
* Recent News: {json.dumps(input_data['news_summary'], indent=2)}
Analyze the convergence of these signals and provide the prediction dictionary."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]


# ==========================================
# 4. REACT PROMPT BUILDERS — ใหม่ทั้งหมด
# ==========================================

def build_initial_analysis_prompt(market_state: Dict[str, Any]) -> PromptPackage:
    """
    STEP 2 — Thought 1 (Initial)
    ส่ง Market State ให้ LLM ประเมินรอบแรก
    LLM ควรตอบว่า NEED_SKILL, CALL_TOOL หรือ FINAL_DECISION
    """
    user = f"""## Market State — Initial Analysis

```json
{json.dumps(market_state, indent=2, ensure_ascii=False)}
```

Analyze the market state above. 
- If you need more information (news, macro data), respond with action = "NEED_SKILL".
- If you have enough data to decide, respond with action = "FINAL_DECISION".

Respond ONLY with a valid JSON object."""

    return PromptPackage(
        step_label="THOUGHT_1_INITIAL",
        system=REACT_SYSTEM_PROMPT,
        user=user,
    )


def build_skill_request_prompt(
    market_state: Dict[str, Any],
    skill_content: str,
) -> PromptPackage:
    """
    STEP 3 — Progressive Disclosure
    ส่ง SKILL.md ให้ LLM เลือก tool ที่จะใช้
    """
    user = f"""## Market State

```json
{json.dumps(market_state, indent=2, ensure_ascii=False)}
```

## Available Skills / Tools

{skill_content}

Choose the most appropriate tool from the skills above and call it.
Respond with action = "CALL_TOOL" and specify tool_name + tool_args.
Respond ONLY with a valid JSON object."""

    return PromptPackage(
        step_label="THOUGHT_1_SKILL_LOADED",
        system=REACT_SYSTEM_PROMPT,
        user=user,
    )


def build_final_decision_prompt(
    market_state:  Dict[str, Any],
    tool_results:  List[Dict[str, Any]],
    skill_content: str,
) -> PromptPackage:
    """
    STEP 5 — Thought 2 (Final Decision)
    รวมข้อมูลทั้งหมด ให้ LLM ตัดสินใจขั้นสุดท้าย
    """
    # สรุป tool results ให้กระชับ
    observations_text = ""
    for i, obs in enumerate(tool_results, 1):
        tool = obs.get("tool", "unknown")
        status = obs.get("status", "unknown")

        if tool == "get_news" and status == "success":
            observations_text += f"""
### Observation {i}: get_news
- Composite Sentiment : {obs.get('composite_sentiment', 'N/A')}
- Dominant Theme      : {obs.get('dominant_theme', 'N/A')}
- Headlines           : {json.dumps([r.get('headline','') for r in obs.get('results', [])[:5]], ensure_ascii=False)}
"""
        elif tool == "run_calculator" and status == "success":
            observations_text += f"""
### Observation {i}: Calculator
- Direction       : {obs.get('direction', 'N/A')}
- Composite Score : {obs.get('composite_score', 'N/A')}
- Math Score      : {obs.get('math_score', 'N/A')}
- News Score      : {obs.get('news_score', 'N/A')}
"""
        else:
            observations_text += f"""
### Observation {i}: {tool} (status={status})
{json.dumps(obs, indent=2, ensure_ascii=False)}
"""

    user = f"""## Market State

```json
{json.dumps(market_state, indent=2, ensure_ascii=False)}
```

## Tool Observations
{observations_text if observations_text else "No tool observations available."}

## Skills Reference
{skill_content}

Based on ALL information above, make your FINAL trading decision.
Respond with action = "FINAL_DECISION" including signal, confidence, entry_price, stop_loss, take_profit, rationale, and key_factors.
Respond ONLY with a valid JSON object."""

    return PromptPackage(
        step_label="THOUGHT_2_FINAL",
        system=REACT_SYSTEM_PROMPT,
        user=user,
    )


def build_conflict_resolution_prompt(
    market_state:  Dict[str, Any],
    tool_results:  List[Dict[str, Any]],
    conflict_desc: str,
) -> PromptPackage:
    """
    STEP 5 (Conflict) — ส่งข้อมูล conflict ให้ LLM แก้ไขและตัดสินใจ
    """
    user = f"""## Market State

```json
{json.dumps(market_state, indent=2, ensure_ascii=False)}
```

## Tool Results Summary

```json
{json.dumps(tool_results, indent=2, ensure_ascii=False, default=str)}
```

## ⚠️ Signal Conflicts Detected

{conflict_desc}

The signals above are contradicting each other. Carefully weigh each signal.
- Prioritize quantitative technical indicators over news sentiment.
- If uncertainty is too high, prefer HOLD with low confidence.

Make your FINAL decision. Respond with action = "FINAL_DECISION".
Respond ONLY with a valid JSON object."""

    return PromptPackage(
        step_label="CONFLICT_RESOLUTION",
        system=REACT_SYSTEM_PROMPT,
        user=user,
    )