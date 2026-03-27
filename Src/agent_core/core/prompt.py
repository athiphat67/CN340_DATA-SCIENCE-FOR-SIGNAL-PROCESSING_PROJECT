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

    def __init__(self, role_registry, current_role):
        self.roles = role_registry
        self.role = current_role
        self._cached_system: str | None = None  # cache
        
    def _get_system(self) -> str:
        if self._cached_system is None:
            role_def = self._require_role()
            tools_list = self.roles.skills.get_tools_for_skills(role_def.available_skills)
            self._cached_system = role_def.get_system_prompt({
                "role_title": role_def.title,
                "available_tools": ", ".join(tools_list) or "none (data pre-loaded)",
            })
        return self._cached_system

    # ── public ──────────────────────────────────

    def build_thought(
        self,
        market_state: dict,
        tool_results: list,
        iteration: int,
    ) -> PromptPackage:
        # ✅ FIX BUG: ใช้ _get_system() เพื่อดึง Cache ไม่ต้องสร้าง System Prompt ใหม่ทุกรอบ
        system = self._get_system()

        user = f"""## Iteration {iteration}

        ### MARKET STATE
        {self._format_market_state(market_state)}

        ### PREVIOUS TOOL RESULTS
        {self._format_tool_results(tool_results)}

        ### INSTRUCTIONS
        Respond with a **single JSON object** (no markdown fences).

        CRITICAL SPEED RULE: If your confidence in a trading signal is already high (e.g., > 0.85) based on current data, DO NOT call more tools. Output FINAL_DECISION immediately to avoid market slippage.

        If you need more data:
        {{
        "action": "CALL_TOOL",
        "thought": "<your reasoning>",
        "tool_name": "<tool_name>",
        "tool_args": {{}}
        }}

        If you are ready to decide (or confidence is high enough):
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
        """Optimized to reduce token count by ~40% and support safe timestamp parsing"""
        md = state.get("market_data", {})
        ti = state.get("technical_indicators", {})
        news = state.get("news", {}).get("by_category", {})
        
        spot = md.get("spot_price_usd", {}).get("price_usd_per_oz", "N/A")
        rsi = ti.get("rsi", {})
        macd = ti.get("macd", {})
        trend = ti.get("trend", {})
        
        # Compact string formatting
        lines = [
            f"Gold: ${spot} | RSI({rsi.get('period', 14)}): {rsi.get('value', 'N/A')} [{rsi.get('signal', 'N/A')}]",
            f"MACD: {macd.get('macd_line', 'N/A')}/{macd.get('signal_line', 'N/A')} hist:{macd.get('histogram', 'N/A')}",
            f"Trend: EMA20={trend.get('ema_20', 'N/A')} EMA50={trend.get('ema_50', 'N/A')} [{trend.get('trend', 'N/A')}]",
            "News Highlights:"
        ]

        # ✅ FIX: News reduction 1 top sentiment article per category (Safe Timestamp Get)
        for cat, details in news.items():
            articles = details.get("articles", [])
            if articles:
                top = max(articles, key=lambda a: abs(a.get("sentiment_score", 0)))
                # Safe get for time, won't crash if missing
                time_val = top.get('timestamp', top.get('published_at', top.get('time', '')))
                time_tag = f" [{time_val}]" if time_val else ""
                
                lines.append(f"  [{cat}]{time_tag} {top.get('title', '')} (sentiment: {top.get('sentiment_score', 0):.2f})")

        return "\n".join(lines)

    def _format_tool_results(self, results: list) -> str:
        if not results:
            return "(No tool results — data pre-loaded from latest.json)"
        
        parts = []
        MAX_CHARS = 1000  # กำหนดลิมิตข้อความ ป้องกัน Prompt บวม!

        for r in results:
            if hasattr(r, "tool_name"):
                status = r.status
                # แปลงข้อมูลเป็น String ก่อน
                data_str = str(r.data or r.error)
                
                # ถ้าข้อมูลยาวเกินไป ให้ตัดทิ้งแล้วเติม ... [TRUNCATED]
                if len(data_str) > MAX_CHARS:
                    data_str = data_str[:MAX_CHARS] + f"... [TRUNCATED: Too long, showing first {MAX_CHARS} chars]"
                
                parts.append(f"[{r.tool_name}] {status}: {data_str}")
            else:
                # กรณีผลลัพธ์เป็นแค่ text ธรรมดา
                val_str = str(r)
                if len(val_str) > MAX_CHARS:
                    val_str = val_str[:MAX_CHARS] + "... [TRUNCATED]"
                parts.append(val_str)
                
        return "\n".join(parts)