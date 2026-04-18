"""
prompt.py — Part C: Prompt System
Builds PromptPackage objects for the ReAct loop.
"""

import json
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import textwrap
from datetime import datetime, timezone, timedelta

from data_engine.tools.tool_registry import AVAILABLE_TOOLS_INFO

# ─────────────────────────────────────────────────────────────────────────────
# Trading Session Windows  (Bangkok time = UTC+7, minutes from midnight)
# Format: (internal_id, start_min_inclusive, end_min_exclusive, display_name, is_dead_zone)
# ─────────────────────────────────────────────────────────────────────────────
_WEEKDAY_SESSIONS = [
    # Mon–Fri
    ("A1",      0,    120, "A",    False),  # 00:00–01:59  ┐ Session A
    ("DEAD_WD", 120,  360, "DEAD", True),   # 02:00–05:59  Dead Zone
    ("A2",      360,  720, "A",    False),  # 06:00–11:59  ┘ Session A
    ("B",       720,  1080,"B",    False),  # 12:00–17:59  Session B
    ("C",       1080, 1440,"C",    False),  # 18:00–23:59  Session C
]
_WEEKEND_SESSIONS = [
    # Sat–Sun
    ("DEAD_WE_AM", 0,    570,  "DEAD", True),  # 00:00–09:29  Dead Zone
    ("W",          570,  1050, "W",    False),  # 09:30–17:29  Session W
    ("DEAD_WE_PM", 1050, 1440, "DEAD", True),  # 17:30–23:59  Dead Zone
]

# ─────────────────────────────────────────────────────────────────────────────
# Core data transfer object
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PromptPackage:
    system: str
    user: str
    step_label: str = "THOUGHT"
    thinking_mode: Optional[str] = None

# ─────────────────────────────────────────────────────────────────────────────
# Role enum
# ─────────────────────────────────────────────────────────────────────────────

class AIRole(Enum):
    ANALYST = "analyst"

# ─────────────────────────────────────────────────────────────────────────────
# Skill
# ─────────────────────────────────────────────────────────────────────────────

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
        with open(filepath, 'r', encoding='utf-8') as f:
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

# ─────────────────────────────────────────────────────────────────────────────
# Role
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RoleDefinition:
    name: AIRole
    title: str
    system_prompt_template: str
    available_skills: list
    confidence_threshold: float = 0.55
    max_position_thb: int = 1250
    system_prompt_static: str = ""
    system_prompt_dynamic_template: str = ""

    def get_system_prompt(self, context: dict) -> str:
        base_prompt = self.system_prompt_static or self.system_prompt_template
        for key, value in context.items():
            base_prompt = base_prompt.replace(f"{{{key}}}", str(value))
        return base_prompt

    def render_dynamic(self, directive: str, session_gate: dict, market_state: dict) -> str:
        tpl = self.system_prompt_dynamic_template
        if not tpl:
            return ""
        return tpl.format(
            directive=directive or "NONE",
            session_gate=session_gate or {},
            market_state=market_state,
        )

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
            legacy_prompt = rd.get("system_prompt_template", rd.get("system_prompt", ""))
            self.register(
                RoleDefinition(
                    name=role_enum,
                    title=rd["title"],
                    system_prompt_template=legacy_prompt,
                    available_skills=rd["available_skills"],
                    confidence_threshold=rd.get("confidence_threshold", 0.55),
                    max_position_thb=rd.get("max_position_thb", 1250),
                    system_prompt_static=rd.get("system_prompt_static", legacy_prompt),
                    system_prompt_dynamic_template=rd.get("system_prompt_dynamic_template", ""),
                )
            )

# ─────────────────────────────────────────────────────────────────────────────
# PromptBuilder
# ─────────────────────────────────────────────────────────────────────────────

class PromptBuilder:
    def __init__(self, role_registry, current_role):
        self.roles = role_registry
        self.role = current_role
        self._cached_system: str | None = None
        self._cached_tools: list | None = None
        self.confidence_threshold = role_registry.get(current_role).confidence_threshold
        
    def _get_system(self) -> str:
        if self._cached_system is None:
            role_def = self._require_role()
            self._cached_system = (
                role_def.system_prompt_static
                or role_def.system_prompt_template
            )
        return self._cached_system
    
    def _get_tools(self) -> list:
        if self._cached_tools is None:
            role_def = self._require_role()
            self._cached_tools = self.roles.skills.get_tools_for_skills(
                role_def.available_skills
            )
        return self._cached_tools or []

    def build_messages(self, market_state: dict, history: list) -> list:
        role_def = self._require_role()
        static_text = role_def.system_prompt_static or role_def.system_prompt_template
        dynamic_text = role_def.render_dynamic(
            directive=market_state.get("backtest_directive", ""),
            session_gate=market_state.get("session_gate"),
            market_state={k: v for k, v in market_state.items()
                          if k not in ("backtest_directive", "session_gate")},
        )
        system_content = static_text + ("\n\n" + dynamic_text if dynamic_text else "")
        return [{"role": "system", "content": system_content}] + history

    # ── public ──────────────────────────────────

    def build_thought(self, market_state: dict, tool_results: list, iteration: int) -> PromptPackage:
        system = self._get_system()
        has_pre_fetched = bool(market_state.get("pre_fetched_tools"))

        if iteration == 1 and has_pre_fetched:
            action_guidance = textwrap.dedent("""
                ## YOUR TASK: FAST-TRACK FINAL_DECISION
                Review 'PRE-FETCHED TOOL RESULTS'. If data is sufficient, output FINAL_DECISION now.
                
                Option A:
                {"action": "FINAL_DECISION", "signal": "BUY|SELL|HOLD", "confidence": 0.0-1.0, "market_context": "Brief synthesis"}

                Option B:
                {"action": "CALL_TOOLS", "thought": "Need more data", "tools": [{"tool_name": "...", "tool_args": {}}]}
            """).strip()
        elif iteration == 1:
            action_guidance = "## ITERATION 1: Call necessary tools to gather data. A trade decision requires tool results first — do not skip this step."
        elif iteration == 2:
            action_guidance = "## ITERATION 2: Choose FINAL_DECISION if evidence is sufficient, or call 1-2 more critical tools."
        else:
            # [V3] Changed Guidance to focus on Technicals and Holding Profit
            action_guidance = "## FINAL_DECISION: Provide your verdict. Act ONLY on high-probability technical setups. If already holding, output HOLD to let profits run unless the exit signal is clear."
        
        if iteration == 1 and not has_pre_fetched:
            tools_section = f"### AVAILABLE TOOLS\n{AVAILABLE_TOOLS_INFO}"
        else:
            tool_names_list = self._get_tools()
            _TOOL_NAMES = ", ".join(tool_names_list) if tool_names_list else "none"
            tools_section = f"### AVAILABLE TOOLS (names only)\n{_TOOL_NAMES}"

        user = textwrap.dedent(f"""
            ## Iteration {iteration}

            {tools_section}

            ### MARKET DATA
            {self._format_market_state(market_state, iteration=iteration)}

            ### PREVIOUS TOOL RESULTS
            {self._format_tool_results(tool_results)}

            {action_guidance}
        """).strip()
        
        return PromptPackage(system=system, user=user, step_label=f"THOUGHT_{iteration}", thinking_mode=None)
    
    def build_final_decision(self, market_state: dict, tool_results: list) -> PromptPackage:
        system = self._get_system()

        user = textwrap.dedent(f"""
            ### MARKET DATA
            {self._format_market_state(market_state)}

            ### ANALYSIS SO FAR
            {self._format_tool_results(tool_results)}

            ## FINAL VERDICT REQUIRED
            Maximum iterations reached. Output your FINAL_DECISION in JSON:
            {{
              "action": "FINAL_DECISION",
              "signal": "BUY|SELL|HOLD",
              "confidence": 0.00-1.00,
              "market_context": "Short 1-sentence synthesis"
            }}
        """).strip()

        return PromptPackage(system=system, user=user, step_label="THOUGHT_FINAL")

    # ── private ─────────────────────────────────

    def _require_role(self) -> RoleDefinition:
        role_def = self.roles.get(self.role)
        if not role_def:
            raise ValueError(f"Role '{self.role}' not registered")
        return role_def

    def _format_market_state(self, state: dict, iteration: int = 1) -> str:
        md   = state.get("market_data", {})
        ti   = state.get("technical_indicators", {})
        news_data = state.get("news", {})

        spot    = md.get("spot_price_usd", {}).get("price_usd_per_oz", "N/A")
        usd_thb = md.get("forex", {}).get("usd_thb", "N/A")
        thai    = md.get("thai_gold_thb", {})
        sell_thb = thai.get("sell_price_thb", "N/A")
        buy_thb  = thai.get("buy_price_thb", "N/A")

        rsi   = ti.get("rsi", {})
        macd  = ti.get("macd", {})
        trend = ti.get("trend", {})
        bb    = ti.get("bollinger", {})
        atr   = ti.get("atr", {})

        timestamp_str = state.get("timestamp") or md.get("spot_price_usd", {}).get("timestamp", "")
        interval      = state.get("interval", "15m")

        time_part = ""
        if timestamp_str and timestamp_str != "N/A":
            try:
                if "T" in timestamp_str:
                    time_part = timestamp_str.split("T")[1][:5]
                else:
                    time_part = timestamp_str.split(" ")[1][:5]
            except Exception:
                time_part = str(timestamp_str)

        external_sg = state.get("session_gate") or {}
        trades_this_session = (
            external_sg.get("trades_this_session")
            or external_sg.get("session_trades")
            or 0
        )
        sg = self._compute_session_gate(
            timestamp_str,
            trades_this_session=trades_this_session,
        )
        for k, v in external_sg.items():
            if v is not None and k in sg:
                sg[k] = v

        dead_zone_warning = ""
        if time_part:
            try:
                if sg.get("is_dead_zone"):
                    dead_zone_warning = (
                        f"\n*** DEAD ZONE (Session '{sg['session_name']}') — "
                        f"NO new BUY entries allowed. HOLD only. "
                        f"If holding gold, SELL to close position. ***"
                    )
            except Exception:
                pass

        lines = [
            f"Timestamp: {timestamp_str} (time: {time_part}) | Interval: {interval}{dead_zone_warning}",
            f"Gold (USD): ${spot}/oz | USD/THB: {usd_thb}",
            f"Gold (THB/gram): ฿{sell_thb} sell / ฿{buy_thb} buy  [Aom NOW]",
            f"RSI({rsi.get('period', 14)}): {rsi.get('value', 'N/A')} [{rsi.get('signal', 'N/A')}]",
            f"MACD: {macd.get('macd_line', 'N/A')}/{macd.get('signal_line', 'N/A')} hist:{macd.get('histogram', 'N/A')} [{macd.get('signal', 'N/A')}]",
            f"Trend: EMA20={trend.get('ema_20', 'N/A')} EMA50={trend.get('ema_50', 'N/A')} [{trend.get('trend', 'N/A')}]",
            f"BB: upper={bb.get('upper', 'N/A')} lower={bb.get('lower', 'N/A')}",
            f"Latest Close ({interval}): ${ti.get('latest_close', 'N/A')}/oz",
            f"ATR: {atr.get('value', 'N/A')} {atr.get('unit', '')}",
        ]

        portfolio = state.get("portfolio", {})
        if portfolio:
            cash      = portfolio.get("cash_balance", 0.0)
            gold_g    = portfolio.get("gold_grams", 0.0)
            pnl       = portfolio.get("unrealized_pnl", 0.0)
            trades_td = portfolio.get("trades_today", 0)
            cost      = portfolio.get("cost_basis_thb", 0.0)
            cur_val   = portfolio.get("current_value_thb", 0.0)

            MIN_BUY_CASH = 1000

            if gold_g > 0:
                can_buy = "NO — already holding gold"
            elif cash < MIN_BUY_CASH:
                can_buy = f"NO — insufficient cash (฿{cash:.0f} < ฿{MIN_BUY_CASH})"
            else:
                can_buy = "YES"

            can_sell = f"YES ({gold_g:.4f}g held)" if gold_g > 0 else "NO — no gold held"

            pnl_status = portfolio.get("risk_status", "")
            pnl_tag = f"  ← {pnl_status}" if pnl_status else ""

            lines += [
                "",
                "── Portfolio ──",
                f"  Cash:           ฿{cash:,.2f}",
                f"  Gold:           {gold_g:.4f} g",
                f"  Cost basis:     ฿{cost:,.2f}",
                f"  Current value:  ฿{cur_val:,.2f}",
                f"  Unrealized PnL: ฿{pnl:,.2f}{pnl_tag}",
                f"  Trades today:   {trades_td}",
                f"  can_buy:  {can_buy}",
                f"  can_sell: {can_sell}",
                "── End Portfolio ──",
            ]

        # ── [SESSION V3] Cleaned up Session Block ──
        if sg:
            session_name  = sg.get("session_name", "UNKNOWN")
            is_dead       = sg.get("is_dead_zone", False)
            remaining     = sg.get("minutes_remaining", "?")
            trades_sess   = sg.get("trades_this_session", 0)
            min_req       = sg.get("min_required_trades", 2)
            day_type      = sg.get("day_type", "")

            if is_dead:
                session_status = "⛔ DEAD ZONE (HOLD only)"
            else:
                session_status = "✅ ACTIVE"

            lines += [
                "",
                "── Session & Quota ──",
                f"  Session: {session_name}{' (' + day_type + ')' if day_type else ''} | {session_status}",
                f"  Trades this session: {trades_sess} / min required: {min_req}",
                f"  Time remaining: {remaining} min",
                "── End Session ──",
            ]

        directive = state.get("backtest_directive", "")
        if directive:
            lines += ["", "── DIRECTIVE ──", directive, "── End DIRECTIVE ──"]

        tp_price = portfolio.get("take_profit_price")
        sl_price = portfolio.get("stop_loss_price")
        gold_g   = float(portfolio.get("gold_grams", 0.0))
        if gold_g > 0 and (tp_price or sl_price):
            lines += [
                "",
                f"── Active Position: {gold_g:.4f}g held ──",
                f"  TP={tp_price} / SL={sl_price} (System auto-sells at these levels. You may SELL early if momentum reverses strongly.)",
                "──────────────────────────────────────",
            ]

        if iteration == 1:
            lines.append("News Highlights:")
            latest_news = news_data.get("latest_news", [])
            news_count  = news_data.get("news_count", 0)
            if latest_news:
                for item in latest_news:
                    lines.append(f"  {item}")
            elif news_count == 0:
                lines.append("  [INFO] No significant macro news available. Focus on technicals.")

            price_trend = md.get("price_trend", {})
            if price_trend:
                lines += [
                    "",
                    "── Price Trend ──",
                    f"  Current: ${price_trend.get('current_close_usd', 'N/A')} | Prev: ${price_trend.get('prev_close_usd', 'N/A')}",
                    f"  Daily chg: {price_trend.get('daily_change_pct', 'N/A')}%",
                ]
                lines.append("── End Price Trend ──")
                
            pre_fetched = state.get("pre_fetched_tools", {})
            if pre_fetched:
                lines += ["", "── PRE-FETCHED TOOL RESULTS ──"]
                for tool_name, result in pre_fetched.items():
                    if isinstance(result, dict) and result.get("status") == "success":
                        data_str = str(result.get("data", result))
                        if len(data_str) > 1000: data_str = data_str[:1000] + "... [truncated]"
                        lines.append(f"  [{tool_name}] {data_str}")
                    else:
                        lines.append(f"  [{tool_name}] {result}")

        else:
            lines += [
                "",
                f"── Iteration 2+ Summary ──",
                f"  Price: ฿{sell_thb} sell / ฿{buy_thb} buy | Close: ${ti.get('latest_close','N/A')}/oz",
            ]
            if directive:
                lines += ["── DIRECTIVE ──", directive, "────────────────"]
            if gold_g > 0 and (tp_price or sl_price):
                lines.append(f"  Active position: {gold_g:.4f}g | TP={tp_price} SL={sl_price}")
            
            # [V3] เพิ่มคำเตือนใน Iteration ท้ายๆ ให้ Let Profit Run
            if gold_g > 0:
                lines.append("\n[CRITICAL] You are holding gold. DO NOT rush to SELL just to clear the quota. If the trend is still alive, output HOLD to let profits run.")
                
            lines.append("  [Prices refreshed. Use tool results below.]")

        return "\n".join(lines)

    def _format_tool_results(self, results: list) -> str:
        if not results:
            return "(No tool results yet)"
        parts = []
        for r in results:
            if hasattr(r, "tool_name"):
                display = r.data if r.data is not None else r.error
                parts.append(f"[{r.tool_name}] {r.status}: {display}")
            else:
                parts.append(str(r))
        return "\n".join(parts)
    
    TZ_BKK = timezone(timedelta(hours=7))

    def _parse_to_bkk_minutes(self, timestamp_str: str) -> int | None:
        try:
            ts_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.TZ_BKK)
            else:
                dt = dt.astimezone(self.TZ_BKK)
            return dt.hour * 60 + dt.minute
        except Exception:
            return None

    def _compute_session_gate(
        self,
        timestamp_str: str,
        trades_this_session: int = 0,
        force_sell_minutes: int = 30,
    ) -> dict:
        minutes = self._parse_to_bkk_minutes(timestamp_str)
        default = {
            "session_name": "UNKNOWN",
            "is_dead_zone": False,
            "is_active": True,
            "trades_this_session": trades_this_session,
            "min_required_trades": 2,
            "minutes_remaining": 999,
            "near_session_end": False,
            "day_type": "Weekday",
        }
        if minutes is None:
            return default

        try:
            ts_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)
            dt = dt.astimezone(self.TZ_BKK) if dt.tzinfo else dt.replace(tzinfo=self.TZ_BKK)
            weekday = dt.weekday()
        except Exception:
            weekday = 0

        is_weekend = weekday >= 5
        sessions   = _WEEKEND_SESSIONS if is_weekend else _WEEKDAY_SESSIONS
        day_type   = "Weekend" if is_weekend else "Weekday"

        for _, start, end, display, is_dead in sessions:
            if start <= minutes < end:
                remaining = end - minutes
                return {
                    "session_name":        display,
                    "is_dead_zone":        is_dead,
                    "is_active":           not is_dead,
                    "trades_this_session": trades_this_session,
                    "min_required_trades": 2,
                    "minutes_remaining":   remaining,
                    "near_session_end":    (not is_dead) and (remaining <= force_sell_minutes),
                    "day_type":            day_type,
                }

        return {**default, "day_type": day_type}