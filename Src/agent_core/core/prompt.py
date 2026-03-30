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
    ANALYST = "analyst"
    RISK_MANAGER = "risk_manager"
    TRADER = "trader"


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
            self.register(
                Skill(
                    name=sd["name"],
                    description=sd["description"],
                    tools=sd.get("tools", []),
                    constraints=sd.get("constraints"),
                )
            )


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
            self.register(
                RoleDefinition(
                    name=role_enum,
                    title=rd["title"],
                    system_prompt_template=rd["system_prompt_template"],
                    available_skills=rd["available_skills"],
                )
            )


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
        self._cached_system: str | None = None

    def _get_system(self) -> str:
        if self._cached_system is None:
            role_def = self._require_role()
            tools_list = self.roles.skills.get_tools_for_skills(
                role_def.available_skills
            )
            self._cached_system = role_def.get_system_prompt(
                {
                    "role_title": role_def.title,
                    "available_tools": ", ".join(tools_list)
                    or "none (data pre-loaded)",
                }
            )
        return self._cached_system

    # ── public ──────────────────────────────────

    def build_thought(
        self,
        market_state: dict,
        tool_results: list,
        iteration: int,
    ) -> PromptPackage:
        role_def = self._require_role()
        tools_list = self.roles.skills.get_tools_for_skills(role_def.available_skills)

        system = self._get_system()

        user = f"""## Iteration {iteration}
        
        ### INSTRUCTIONS
        - Respond ONLY with a single JSON object.
        - DO NOT include markdown code blocks like ```json.
        - DO NOT include any 'Thinking' process in the text, go straight to JSON.

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
        return PromptPackage(
            system=system, user=user, step_label=f"THOUGHT_{iteration}"
        )

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
        """Optimized to reduce token count by ~40%"""
        md = state.get("market_data", {})
        ti = state.get("technical_indicators", {})
        news = state.get("news", {}).get("by_category", {})

        spot     = md.get("spot_price_usd", {}).get("price_usd_per_oz", "N/A")
        usd_thb  = md.get("forex", {}).get("usd_thb", "N/A")
        thai     = md.get("thai_gold_thb", {})
        sell_thb = thai.get("sell_price_thb", "N/A")
        buy_thb  = thai.get("buy_price_thb", "N/A")
        rsi   = ti.get("rsi", {})
        macd  = ti.get("macd", {})
        trend = ti.get("trend", {})

        lines = [
            f"Gold (USD): ${spot}/oz | USD/THB: {usd_thb}",
            f"Gold (THB/gram): ฿{sell_thb} sell / ฿{buy_thb} buy  [ออม NOW]",
            f"RSI({rsi.get('period', 14)}): {rsi.get('value', 'N/A')} [{rsi.get('signal', 'N/A')}]",
            f"MACD: {macd.get('macd_line', 'N/A')}/{macd.get('signal_line', 'N/A')} hist:{macd.get('histogram', 'N/A')}",
            f"Trend: EMA20={trend.get('ema_20', 'N/A')} EMA50={trend.get('ema_50', 'N/A')} [{trend.get('trend', 'N/A')}]",
            "News Highlights:",
        ]

        # News reduction: 1 top sentiment article per category
        for cat, details in news.items():
            articles = details.get("articles", [])
            if articles:
                top = max(articles, key=lambda a: abs(a.get("sentiment_score", 0)))
                lines.append(
                    f"  [{cat}] {top.get('title', '')} (sentiment: {top.get('sentiment_score', 0):.2f})"
                )

        # ── Price Trend Section (backtest) ────────────────────────────
        price_trend = md.get("price_trend", {})
        if price_trend:
            lines += [
                "",
                "── Price Trend ──",
                f"  Current: ${price_trend.get('current_close_usd', 'N/A')} | Prev: ${price_trend.get('prev_close_usd', 'N/A')}",
                f"  Daily chg: {price_trend.get('daily_change_pct', 'N/A')}%",
            ]
            if "5d_change_pct" in price_trend:
                lines.append(f"  5d chg: {price_trend['5d_change_pct']}%")
            if "10d_change_pct" in price_trend:
                lines.append(f"  10d chg: {price_trend['10d_change_pct']}%")
            if "10d_high" in price_trend:
                lines.append(
                    f"  10d range: ${price_trend['10d_low']} — ${price_trend['10d_high']}"
                )
            lines.append("── End Price Trend ──")

        # ── Portfolio Section ──────────────────────────────────────
        # ดึง portfolio จาก market_state (ถูกใส่เข้ามาจาก dashboard.py)
        portfolio = state.get("portfolio", {})
        if portfolio:
            cash = portfolio.get("cash_balance", 0.0)
            gold_g = portfolio.get("gold_grams", 0.0)
            pnl = portfolio.get("unrealized_pnl", 0.0)
            trades_td = portfolio.get("trades_today", 0)
            cost = portfolio.get("cost_basis_thb", 0.0)
            cur_val = portfolio.get("current_value_thb", 0.0)

            # คำนวณ flag ที่ LLM จะใช้ตัดสินใจ
            can_buy = (
                "YES" if cash >= 1000 else f"NO (cash ฿{cash:.0f} < ฿1000 minimum)"
            )
            can_sell = "YES" if gold_g > 0 else "NO (gold_grams = 0)"

            lines += [
                "",
                "── Portfolio ──",
                f"  Cash:       ฿{cash:,.2f}",
                f"  Gold:       {gold_g:.4f} g",
                f"  Cost basis: ฿{cost:,.2f}",
                f"  Cur. value: ฿{cur_val:,.2f}",
                f"  Unreal PnL: ฿{pnl:,.2f}",
                f"  Trades today: {trades_td}",
                f"  can_buy:  {can_buy}",
                f"  can_sell: {can_sell}",
                "── End Portfolio ──",
            ]

        # ── Backtest Directive (if present) ────────────────────────
        directive = state.get("backtest_directive", "")
        if directive:
            lines += ["", "── DIRECTIVE ──", directive, "── End DIRECTIVE ──"]

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