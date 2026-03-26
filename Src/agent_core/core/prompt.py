"""
prompt.py — Part C: Prompt System
Builds PromptPackage objects for the ReAct loop.
"""

import json
from enum import Enum
from typing import Optional
from dataclasses import dataclass


# ─────────────────────────────────────────────
# Core data transfer object
# ─────────────────────────────────────────────

@dataclass
class PromptPackage:
    """Container ที่ส่งระหว่าง PromptBuilder → LLMClient"""
    system: str
    user: str
    step_label: str = "THOUGHT"


# ─────────────────────────────────────────────
# Role enum
# ─────────────────────────────────────────────

class AIRole(Enum):
    ANALYST      = "analyst"
    RISK_MANAGER = "risk_manager"
    TRADER       = "trader"


# ─────────────────────────────────────────────
# Skill
# ─────────────────────────────────────────────

@dataclass
class Skill:
    name: str
    description: str
    tools: list
    constraints: Optional[dict] = None

    def to_prompt_text(self) -> str:
        tools_str = ", ".join(self.tools) if self.tools else "none"
        return f"- {self.name}: {self.description}\n  Tools: {tools_str}"


class SkillRegistry:
    def __init__(self):
        self.skills: dict = {}

    def register(self, skill: Skill) -> None:
        self.skills[skill.name] = skill

    def get(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def get_tools_for_skills(self, skill_names: list) -> list:
        tools = set()
        for name in skill_names:
            skill = self.get(name)
            if skill:
                tools.update(skill.tools)
        return sorted(tools)

    def load_from_json(self, filepath: str) -> None:
        with open(filepath) as f:
            data = json.load(f)
        for sd in data.get("skills", []):
            self.register(Skill(
                name=sd["name"],
                description=sd["description"],
                tools=sd.get("tools", []),
                constraints=sd.get("constraints"),
            ))


# ─────────────────────────────────────────────
# Role
# ─────────────────────────────────────────────

@dataclass
class RoleDefinition:
    name: AIRole
    title: str
    system_prompt_template: str
    available_skills: list

    def get_system_prompt(self, context: dict) -> str:
        return self.system_prompt_template.format(**context)


class RoleRegistry:
    def __init__(self, skill_registry: SkillRegistry):
        self.roles: dict = {}
        self.skills = skill_registry

    def register(self, role_def: RoleDefinition) -> None:
        self.roles[role_def.name] = role_def

    def get(self, role: AIRole) -> Optional[RoleDefinition]:
        return self.roles.get(role)

    def load_from_json(self, filepath: str) -> None:
        with open(filepath) as f:
            data = json.load(f)
        for rd in data.get("roles", []):
            role_enum = AIRole(rd["name"])
            self.register(RoleDefinition(
                name=role_enum,
                title=rd["title"],
                system_prompt_template=rd["system_prompt_template"],
                available_skills=rd["available_skills"],
            ))


# ─────────────────────────────────────────────
# PromptBuilder
# ─────────────────────────────────────────────

class PromptBuilder:
    """
    สร้าง PromptPackage สำหรับแต่ละ step ของ ReAct loop
    """

    def __init__(self, role_registry: RoleRegistry, current_role: AIRole):
        self.roles = role_registry
        self.role = current_role

    # ── public ──────────────────────────────────

    def build_thought(
        self,
        market_state: dict,
        tool_results: list,
        iteration: int,
    ) -> PromptPackage:
        role_def = self._require_role()
        tools_list = self.roles.skills.get_tools_for_skills(role_def.available_skills)

        system = role_def.get_system_prompt({
            "role_title":      role_def.title,
            "available_tools": ", ".join(tools_list) if tools_list else "none (data pre-loaded)",
        })

        user = f"""## Iteration {iteration}

### MARKET STATE
{self._format_market_state(market_state)}

### PREVIOUS TOOL RESULTS
{self._format_tool_results(tool_results)}

### INSTRUCTIONS
Respond with a **single JSON object** (no markdown fences).

If you need more data:
{{
  "action": "CALL_TOOL",
  "thought": "<your reasoning>",
  "tool_name": "<tool_name>",
  "tool_args": {{}}
}}

If you are ready to decide:
{{
  "action": "FINAL_DECISION",
  "thought": "<your reasoning>",
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "entry_price": <number or null>,
  "stop_loss": <number or null>,
  "take_profit": <number or null>,
  "rationale": "<concise rationale>"
}}
"""
        return PromptPackage(system=system, user=user, step_label=f"THOUGHT_{iteration}")

    def build_final_decision(
        self,
        market_state: dict,
        tool_results: list,
    ) -> PromptPackage:
        role_def = self._require_role()
        system = (
            f"You are a {role_def.title}. "
            "You MUST output a final trading decision as a single JSON object (no markdown fences). "
            "Fields: action (FINAL_DECISION), signal (BUY/SELL/HOLD), confidence (0-1), "
            "entry_price, stop_loss, take_profit, rationale."
        )
        user = f"""### MARKET STATE
{self._format_market_state(market_state)}

### ANALYSIS SO FAR
{self._format_tool_results(tool_results)}

You have reached the maximum number of iterations.
Output your FINAL_DECISION now as a single JSON object.
"""
        return PromptPackage(system=system, user=user, step_label="THOUGHT_FINAL")

    # ── private ─────────────────────────────────

    def _require_role(self) -> RoleDefinition:
        role_def = self.roles.get(self.role)
        if not role_def:
            raise ValueError(f"Role '{self.role}' not registered")
        return role_def

    def _format_market_state(self, state: dict) -> str:
        md = state.get("market_data", {})
        ti = state.get("technical_indicators", {})
        news = state.get("news", {})

        lines = []
        # Market data
        lines.append(f"Gold Spot  : ${md.get('spot_price_usd', 'N/A')}/oz")
        forex = md.get("forex", {})
        lines.append(f"USD/THB    : {forex.get('usd_thb', 'N/A')}")
        tg = md.get("thai_gold_thb", {})
        lines.append(f"Thai Gold  : Buy {tg.get('buy', 'N/A')} ฿ / Sell {tg.get('sell', 'N/A')} ฿")

        # Technical indicators
        lines.append("")
        lines.append("Technical Indicators:")
        lines.append(f"  RSI(14)   : {ti.get('rsi_14', 'N/A')}")
        macd = ti.get("macd", {})
        lines.append(
            f"  MACD      : {macd.get('value', 'N/A')} / "
            f"signal {macd.get('signal', 'N/A')} / "
            f"hist {macd.get('histogram', 'N/A')}"
        )
        bb = ti.get("bollinger_bands", {})
        lines.append(f"  Bollinger : %B = {bb.get('percent_b', 'N/A')}")
        lines.append(f"  ATR(14)   : {ti.get('atr_14', 'N/A')}")
        trend = ti.get("trend", {})
        lines.append(
            f"  Trend     : EMA20={trend.get('ema20', 'N/A')} "
            f"EMA50={trend.get('ema50', 'N/A')} "
            f"SMA200={trend.get('sma200', 'N/A')}"
        )

        # News summary
        by_cat = news.get("by_category", {})
        if by_cat:
            lines.append("")
            lines.append(f"News ({news.get('total_articles', 0)} articles):")
            for cat, articles in by_cat.items():
                lines.append(f"  {cat}: {len(articles)} articles")

        return "\n".join(lines)

    def _format_tool_results(self, results: list) -> str:
        if not results:
            return "(No tool results — data pre-loaded from latest.json)"
        parts = []
        for r in results:
            if hasattr(r, "tool_name"):
                status = r.status
                parts.append(f"[{r.tool_name}] {status}: {r.data or r.error}")
            else:
                parts.append(str(r))
        return "\n".join(parts)