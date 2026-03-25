import google.generativeai as genai
import json
import re
import logging
from agent_core.prompts import SYSTEM_PROMPT
from agent_core.skills.macro_news import get_macro_news

logger = logging.getLogger(__name__)

AVAILABLE_TOOLS = {
    "get_macro_news": get_macro_news,
}

MAX_REACT_STEPS = 5


class AgentOrchestrator:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-pro")
        self.trace: list[dict] = []

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run_cycle(self, market_state: dict) -> dict:
        """
        Execute one full ReAct cycle given the current market state.
        Returns a dict with keys: action, quantity, reasoning, trace.
        """
        self.trace = []
        conversation = self._build_initial_prompt(market_state)

        for step in range(1, MAX_REACT_STEPS + 1):
            logger.info(f"[ReAct] Step {step}")
            raw = self._call_llm(conversation)
            self.trace.append({"step": step, "llm_output": raw})

            # Check if the model wants to call a tool
            tool_call = self._parse_tool_call(raw)
            if tool_call:
                tool_name, tool_args = tool_call
                observation = self._execute_tool(tool_name, tool_args)
                self.trace[-1]["tool"] = tool_name
                self.trace[-1]["observation"] = observation

                # Append tool result back into the conversation
                conversation += f"\nObservation: {observation}\n"
            else:
                # No tool call → try to extract final JSON decision
                decision = self._parse_final_decision(raw)
                if decision:
                    decision["trace"] = self.trace
                    return decision

                # Model produced text but no valid JSON yet; let it continue
                conversation += f"\nThought (continued): {raw}\n"

        # Fallback if max steps reached without a decision
        logger.warning("[ReAct] Max steps reached — defaulting to HOLD")
        return {
            "action": "HOLD",
            "quantity": 0.0,
            "reasoning": "Agent could not reach a decision within the step limit.",
            "trace": self.trace,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_initial_prompt(self, market_state: dict) -> str:
        state_str = json.dumps(market_state, indent=2)
        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"=== Current Market State ===\n{state_str}\n\n"
            "Begin your ReAct reasoning now.\n"
            "Thought:"
        )

    def _call_llm(self, prompt: str) -> str:
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def _parse_tool_call(self, text: str) -> tuple[str, str] | None:
        """
        Detect lines like:
            Action: get_macro_news("gold Fed rate 2025")
        Returns (tool_name, args_string) or None.
        """
        match = re.search(
            r"Action:\s*([\w_]+)\s*\(([^)]*)\)", text, re.IGNORECASE
        )
        if match:
            name = match.group(1).strip()
            args = match.group(2).strip().strip('"').strip("'")
            if name in AVAILABLE_TOOLS:
                return name, args
        return None

    def _execute_tool(self, tool_name: str, args: str) -> str:
        logger.info(f"[Tool] Calling {tool_name}({args!r})")
        try:
            result = AVAILABLE_TOOLS[tool_name](args)
            return str(result)
        except Exception as e:
            return f"Tool error: {e}"

    def _parse_final_decision(self, text: str) -> dict | None:
        """
        Extract a JSON object from the model output.
        Accepts both fenced (```json ... ```) and bare JSON.
        """
        # Try fenced code block first
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        candidate = fenced.group(1) if fenced else None

        # Fall back to first bare { ... } block
        if not candidate:
            bare = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            candidate = bare.group(0) if bare else None

        if not candidate:
            return None

        try:
            decision = json.loads(candidate)
            # Validate required fields
            if decision.get("action") in ("BUY", "SELL", "HOLD") and "quantity" in decision:
                decision.setdefault("reasoning", "No reasoning provided.")
                return decision
        except json.JSONDecodeError:
            pass

        return None

    def get_trace(self) -> list[dict]:
        return self.trace
