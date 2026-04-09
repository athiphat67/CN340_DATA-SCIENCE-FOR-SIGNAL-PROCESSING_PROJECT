"""
prompt.py — Part C: Prompt System
Builds PromptPackage objects for the ReAct loop.

[FIX v2.1]
  - build_final_decision() ใช้ system prompt เต็มจาก roles.json (ไม่ใช่ stripped version)
  - _format_market_state() เพิ่ม timestamp ให้ LLM ใช้ตรวจ time-based exit rule
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
        prompt = self.system_prompt_template
        for key, value in context.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt


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
                    system_prompt_template=rd.get(
                        "system_prompt_template", rd.get("system_prompt", "")
                    ),
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
        Respond with a **single JSON object** (no markdown fences).

        ### MARKET STATE
        {self._format_market_state(market_state)}

        ### PREVIOUS TOOL RESULTS
        {self._format_tool_results(tool_results)}

        If you are ready to decide:
        {{
        "action": "FINAL_DECISION",
        "thought": "<your reasoning>",
        "signal": "BUY" | "SELL" | "HOLD",
        "confidence": 0.0-1.0,
        "entry_price": <number or null>,
        "stop_loss": <number or null>,
        "take_profit": <number or null>,
        "position_size_thb": 1000 or null,
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
        # [FIX v2.1] ใช้ system prompt เต็มจาก roles.json
        # เดิม: สร้าง system prompt สั้นๆ ใหม่เอง → LLM ไม่เห็น TP/SL rules เลย
        # ใหม่: ใช้ _get_system() เหมือน build_thought() → LLM เห็น rules ครบ
        system = self._get_system()

        user = f"""### MARKET STATE
        {self._format_market_state(market_state)}

        ### ANALYSIS SO FAR
        {self._format_tool_results(tool_results)}

        You have reached the maximum number of iterations.
        Work through the DECISION CHECKLIST in your system prompt, then output your FINAL_DECISION as a single JSON object.
        Remember: position_size_thb must be exactly 1000 if signal is BUY.
        """
        return PromptPackage(system=system, user=user, step_label="THOUGHT_FINAL")

    # ── private ─────────────────────────────────

    def _require_role(self) -> RoleDefinition:
        role_def = self.roles.get(self.role)
        if not role_def:
            raise ValueError(f"Role '{self.role}' not registered")
        return role_def

    def _format_market_state(self, state: dict) -> str:
        """Format market state for LLM — includes timestamp for time-based rules"""
        md   = state.get("market_data", {})
        ti   = state.get("technical_indicators", {})
        news = state.get("news", {}).get("by_category", {})
    
        # --- แทรกบรรทัดนี้เพื่อกางข้อมูลออกมาดู ---
        # print("\n=== FULL md ===")
        # print(json.dumps(md, indent=4, ensure_ascii=False))
        # print("========================\n")
         
        # print("\n=== FULL ti ===")
        # print(json.dumps(ti, indent=4, ensure_ascii=False))
        # print("========================\n")
        
        # print("\n=== FULL news ===")
        # print(json.dumps(news, indent=4, ensure_ascii=False))
        # print("========================\n")

        # --- แก้ไขการดึงข้อมูลให้ตรงกับโครงสร้าง JSON (md) ---
        # 1. spot_price เปลี่ยนคีย์เป็น spot_price_usd
        spot = md.get("spot_price_usd", {}).get("price_usd_per_oz", "N/A")
        
        # 2. usd_thb ย้ายไปอยู่ใน object 'forex'
        usd_thb = md.get("forex", {}).get("usd_thb", "N/A")
        
        # thai_gold_thb ยังดึงได้ปกติ
        thai = md.get("thai_gold_thb", {})
        sell_thb = thai.get("sell_price_thb", "N/A")
        buy_thb  = thai.get("buy_price_thb", "N/A")

        rsi   = ti.get("rsi", {})
        macd  = ti.get("macd", {})
        trend = ti.get("trend", {})
        bb    = ti.get("bollinger", {})
        atr   = ti.get("atr", {})

        # --- แก้ไขการดึง Timestamp ---
        # ถ้า state หลักไม่มี timestamp ให้ไปดึงจาก spot_price_usd หรือ forex แทน
        timestamp_str = state.get("timestamp") or md.get("spot_price_usd", {}).get("timestamp", "")
        interval      = state.get("interval", "15m")

        # --- แก้ไขการตัดคำ Time part (รองรับฟอร์แมตที่มีตัว 'T' คั่น) ---
        time_part = ""
        if timestamp_str and timestamp_str != "N/A":
            try:
                # รองรับเวลาแบบ 2026-04-07T11:15:34.985273+07:00
                if "T" in timestamp_str:
                    time_part = timestamp_str.split("T")[1][:5]  # จะได้ "11:15"
                else:
                    time_part = timestamp_str.split(" ")[1][:5]
            except Exception:
                time_part = str(timestamp_str)

        # ตรวจ dead zone warning ให้ LLM รู้ล่วงหน้า
        dead_zone_warning = ""
        if time_part:
            try:
                h, m = int(time_part[:2]), int(time_part[3:5])
                minutes = h * 60 + m
                # 01:30–01:59 = ช่วงอันตราย ควร SELL ถ้าถือทองอยู่
                if 90 <= minutes <= 119:
                    dead_zone_warning = "\n*** WARNING: Time 01:30–01:59 — Market closes at 02:00. SL3: SELL if holding gold! ***"
                # 02:00–06:14 = dead zone
                elif 120 <= minutes <= 374:
                    dead_zone_warning = "\n*** INFO: Dead zone 02:00–06:14 — Cannot execute trades. ***"
            except Exception:
                pass

        lines = [
            f"Timestamp: {timestamp_str} (time: {time_part}) | Interval: {interval}{dead_zone_warning}",
            f"Gold (USD): ${spot}/oz | USD/THB: {usd_thb}",
            f"Gold (THB/gram): ฿{sell_thb} sell / ฿{buy_thb} buy  [ออม NOW]",
            f"RSI({rsi.get('period', 14)}): {rsi.get('value', 'N/A')} [{rsi.get('signal', 'N/A')}]",
            f"MACD: {macd.get('macd_line', 'N/A')}/{macd.get('signal_line', 'N/A')} hist:{macd.get('histogram', 'N/A')} [{macd.get('signal', 'N/A')}]",
            f"Trend: EMA20={trend.get('ema_20', 'N/A')} EMA50={trend.get('ema_50', 'N/A')} [{trend.get('trend', 'N/A')}]",
            f"BB: upper={bb.get('upper', 'N/A')} lower={bb.get('lower', 'N/A')}",
            f"ATR: {atr.get('value', 'N/A')}",
            "News Highlights:",
        ]

        # News: 1 top article per category
        for cat, details in news.items():
            # [FIX] เช็คให้ชัวร์ว่า details เป็น Dictionary 
            if isinstance(details, dict):
                articles = details.get("articles", [])
            # กรณี details เป็น List ของบทความไปเลย (เผื่อโครงสร้างข่าวเปลี่ยน)
            elif isinstance(details, list):
                articles = details
            else:
                articles = []

            if articles and isinstance(articles, list):
                # ป้องกันกรณีของข้างใน articles ไม่ใช่ dict ด้วย
                valid_articles = [a for a in articles if isinstance(a, dict)]
                if valid_articles:
                    top = max(valid_articles, key=lambda a: abs(float(a.get("sentiment_score", 0))))
                    lines.append(
                        f"  [{cat}] {top.get('title', '')} (sentiment: {top.get('sentiment_score', 0):.2f})"
                    )

        # Price Trend (backtest)
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

        # Portfolio — แสดงชัดเพื่อให้ LLM ตรวจ TP/SL ได้ถูกต้อง
        portfolio = state.get("portfolio", {})
        if portfolio:
            cash      = portfolio.get("cash_balance", 0.0)
            gold_g    = portfolio.get("gold_grams", 0.0)
            pnl       = portfolio.get("unrealized_pnl", 0.0)
            trades_td = portfolio.get("trades_today", 0)
            cost      = portfolio.get("cost_basis_thb", 0.0)
            cur_val   = portfolio.get("current_value_thb", 0.0)

            can_buy  = "YES" if cash >= 1010 else f"NO (cash ฿{cash:.0f} < ฿1,010 minimum)"
            can_sell = f"YES ({gold_g:.4f}g held)" if gold_g > 0 else "NO (no gold held)"

            # [FIX v2.1] แสดง PnL status เพื่อให้ LLM ตรวจ TP/SL rule ได้ทันที
            pnl_status = ""
            if gold_g > 0:
                if pnl >= 300:
                    pnl_status = " ← TP1 TRIGGERED (≥+300)"
                elif pnl >= 150:
                    pnl_status = " ← CHECK TP2 (≥+150, check RSI)"
                elif pnl >= 100:
                    pnl_status = " ← CHECK TP3 (≥+100, check MACD)"
                elif pnl <= -150:
                    pnl_status = " ← SL1 TRIGGERED (≤-150)"
                elif pnl <= -80:
                    pnl_status = " ← CHECK SL2 (≤-80, check RSI)"

            lines += [
                "",
                "── Portfolio ──",
                f"  Cash:          ฿{cash:,.2f}",
                f"  Gold:          {gold_g:.4f} g",
                f"  Cost basis:    ฿{cost:,.2f}",
                f"  Current value: ฿{cur_val:,.2f}",
                f"  Unrealized PnL: ฿{pnl:,.2f}{pnl_status}",
                f"  Trades today:  {trades_td}",
                f"  can_buy:  {can_buy}",
                f"  can_sell: {can_sell}",
                "── End Portfolio ──",
            ]

        # Backtest directive
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
                parts.append(f"[{r.tool_name}] {r.status}: {r.data or r.error}")
            else:
                parts.append(str(r))
        return "\n".join(parts)