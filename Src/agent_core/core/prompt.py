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

from data_engine.tools.tool_registry import list_tools

@dataclass
class PromptPackage:
    system: str
    user: str
    step_label: str = "THOUGHT"
    thinking_mode: Optional[str] = None

class AIRole(Enum):
    ANALYST = "analyst"

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
            if skill: tools.update(skill.tools)
        return sorted(tools)

    def load_from_json(self, filepath: str) -> None:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for sd in data.get("skills", []):
            self.register(Skill(name=sd["name"], description=sd["description"], tools=sd.get("tools", []), constraints=sd.get("constraints")))

@dataclass
class RoleDefinition:
    name: AIRole
    title: str
    system_prompt_template: str
    available_skills: list
    confidence_threshold: float = 0.58
    max_position_thb: int = 1000
    system_prompt_static: str = ""
    system_prompt_dynamic_template: str = ""

    def get_system_prompt(self, context: dict) -> str:
        base_prompt = self.system_prompt_static or self.system_prompt_template
        for key, value in context.items():
            base_prompt = base_prompt.replace(f"{{{key}}}", str(value))
        return base_prompt

    def render_dynamic(self, directive: str, session_gate: dict, market_state: dict) -> str:
        tpl = self.system_prompt_dynamic_template
        if not tpl: return ""
        return tpl.format(directive=directive or "NONE", session_gate=session_gate or {}, market_state=market_state)

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
            self.register(RoleDefinition(
                name=role_enum, title=rd["title"], system_prompt_template=legacy_prompt,
                available_skills=rd["available_skills"], confidence_threshold=rd.get("confidence_threshold", 0.58),
                max_position_thb=rd.get("max_position_thb", 1000),
                system_prompt_static=rd.get("system_prompt_static", legacy_prompt),
                system_prompt_dynamic_template=rd.get("system_prompt_dynamic_template", ""),
            ))

class PromptBuilder:
    def __init__(self, role_registry, current_role):
        self.roles = role_registry
        self.role = current_role
        self._cached_system: str | None = None
        self._cached_tools: list | None = None
        role_def = role_registry.get(current_role)
        self.confidence_threshold = role_def.confidence_threshold if role_def else 0.58
        
    def _get_system(self) -> str:
        if self._cached_system is None:
            role_def = self._require_role()
            self._cached_system = role_def.system_prompt_static or role_def.system_prompt_template
        return self._cached_system
    
    def _get_tools(self) -> list:
        if self._cached_tools is None:
            role_def = self._require_role()
            self._cached_tools = self.roles.skills.get_tools_for_skills(role_def.available_skills)
        return self._cached_tools or []

    def build_messages(self, market_state: dict, history: list) -> list:
        role_def = self._require_role()
        static_text = role_def.system_prompt_static or role_def.system_prompt_template
        dynamic_text = role_def.render_dynamic(
            directive=market_state.get("backtest_directive", ""),
            session_gate=market_state.get("session_gate"),
            market_state={k: v for k, v in market_state.items() if k not in ("backtest_directive", "session_gate")},
        )
        system_content = static_text + ("\n\n" + dynamic_text if dynamic_text else "")
        return [{"role": "system", "content": system_content}] + history

    def build_thought(self, market_state: dict, tool_results: list, iteration: int) -> PromptPackage:
        role_def = self._require_role()
        max_pos = int(role_def.max_position_thb or 1000)
        
        system = self._get_system()
        
        # 🟢 [SNIPER BYPASS] ยก Sniper Mode ขึ้น System Prompt (จะมีผลแค่ตอนเป็น Golden Setup)
        directive = market_state.get("backtest_directive", "")
        if "SNIPER MODE" in directive:
            system += "\n\n## [OVERRIDE SYSTEM DIRECTIVE - HIGHEST PRIORITY] " + directive

        has_pre_fetched = bool(market_state.get("pre_fetched_tools"))

        if iteration == 1 and has_pre_fetched:
            action_guidance = textwrap.dedent(f"""
                ## YOUR TASK: FAST-TRACK FINAL_DECISION
                Review 'PRE-FETCHED TOOL RESULTS'. If data is sufficient, output FINAL_DECISION now.
                ── Option A (FAST TRACK): Final Decision ──
                {{{{
                  "action": "FINAL_DECISION",
                  "agent_reasoning": {{{{ "1_data_grounding": "...", "2_market_hypothesis": "...", "3_logical_constraints": "...", "4_risk_assessment": "..." }}}},
                  "analysis": {{{{ "bull_case": "...", "bear_case": "...", "neutral_case": "..." }}}},
                  "execution_check": {{{{ "is_spread_covered": true|false, "is_profitable_to_sell": true|false|null }}}},
                  "signal": "BUY" | "SELL" | "HOLD",
                  "confidence": 0.0-1.0,
                  "position_size_thb": {max_pos} or null,
                  "rationale": "<Synthesis of Bull vs Bear. Max 40 words>"
                }}}}
                ── Option B (Fallback): Call Additional Tools ──
                {{{{
                  "action": "CALL_TOOLS",
                  "thought": "<why you need MORE tools>",
                  "tools": [{{"tool_name": "...", "tool_args": {{{{}}}}}}]
                }}}}
                CRITICAL: If signal is BUY, position_size_thb MUST be {max_pos}. If confidence < {self.confidence_threshold}, MUST be HOLD.
            """).strip()
        elif iteration == 1:
            action_guidance = "## ITERATION 1 — Preferred: CALL_TOOLS (max 2 core tools, only if critical missing data).\nIf market_state + prefetch are sufficient, you may output FINAL_DECISION."
        elif iteration == 2:
            action_guidance = "## ITERATION 2 — Choose: FINAL_DECISION (if enough data) or CALL_TOOLS (max 2, if critical gap)."
        else:
            action_guidance = "## FINAL_DECISION: Provide your verdict. Act ONLY on high-probability technical setups. If already holding, output HOLD to let profits run unless the exit signal is clear."
        
        if iteration == 1 and not has_pre_fetched:
            tools_section = self._format_available_tools(verbose=True)
        else:
            _TOOL_NAMES = ", ".join(self._get_tools()) if self._get_tools() else "none"
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
        role_def = self._require_role()
        max_pos = int(role_def.max_position_thb or 1000)
        system = self._get_system()

        # 🟢 [SNIPER BYPASS] ยก Sniper Mode ขึ้น System Prompt
        directive = market_state.get("backtest_directive", "")
        if "SNIPER MODE" in directive:
            system += "\n\n## [OVERRIDE SYSTEM DIRECTIVE - HIGHEST PRIORITY] " + directive

        user = textwrap.dedent(f"""
            ### MARKET DATA
            {self._format_market_state(market_state)}
            ### ANALYSIS SO FAR
            {self._format_tool_results(tool_results)}
            ## FINAL VERDICT REQUIRED
            You must follow the strict reasoning framework before deciding. Inhibit your final signal until reasoning is fully written.
            {{
              "action": "FINAL_DECISION",
              "agent_reasoning": {{ "1_data_grounding": "...", "2_market_hypothesis": "...", "3_logical_constraints": "...", "4_risk_assessment": "..." }},
              "analysis": {{ "bull_case": "...", "bear_case": "...", "neutral_case": "..." }},
              "execution_check": {{ "is_spread_covered": bool, "is_profitable_to_sell": bool }},
              "signal": "BUY" | "SELL" | "HOLD",
              "confidence": 0.0-1.0,
              "position_size_thb": {max_pos},
              "rationale": "..."
            }}
            CRITICAL RULES:
            1. If signal is BUY, position_size_thb MUST be {max_pos}.
            2."CRITICAL: Default to HOLD ONLY if: (a) confidence < {self.confidence_threshold} , OR "
            2.1"(b) fewer than 2 BUY/SELL conditions are met. "
            2.2"A bearish intermarket signal alone is NOT sufficient to override "
            2.3"a bullish technical setup with ≥3 conditions met."
            3. Output ONLY valid JSON.
        """).strip()
        return PromptPackage(system=system, user=user, step_label="THOUGHT_FINAL")

    def _require_role(self) -> RoleDefinition:
        role_def = self.roles.get(self.role)
        if not role_def: raise ValueError(f"Role '{self.role}' not registered")
        return role_def

    def _format_available_tools(self, verbose: bool = False) -> str:
        allowed = set(self._get_tools())
        if not allowed: return "### AVAILABLE TOOLS\n(none)"
        if not verbose: return f"### AVAILABLE TOOLS (names only)\n{', '.join(sorted(allowed))}"
        meta = {t.get("name"): t for t in list_tools()}
        lines = ["### AVAILABLE TOOLS"]
        for i, name in enumerate(sorted(allowed), start=1):
            desc = (meta.get(name, {}).get("description") or "").strip()
            lines.append(f"{i}. {name}: {desc}" if desc else f"{i}. {name}")
        return "\n".join(lines)

    def _format_market_state(self, state: dict, iteration: int = 1) -> str:
        md, ti, news_data = state.get("market_data", {}), state.get("technical_indicators", {}), state.get("news", {})
        spot, usd_thb = md.get("spot_price_usd", {}).get("price_usd_per_oz", "N/A"), md.get("forex", {}).get("usd_thb", "N/A")
        thai, spread_cov = md.get("thai_gold_thb", {}), md.get("spread_coverage", {})
        sell_thb, buy_thb = thai.get("sell_price_thb", "N/A"), thai.get("buy_price_thb", "N/A")
        
        try: gold_thb_per_gram_str = f"{float(sell_thb) / 15.244:,.2f}"
        except (ValueError, TypeError): gold_thb_per_gram_str = "N/A"

        rsi, macd, trend, bb, atr = ti.get("rsi", {}), ti.get("macd", {}), ti.get("trend", {}), ti.get("bollinger", {}), ti.get("atr", {})
        timestamp_str = state.get("timestamp") or md.get("spot_price_usd", {}).get("timestamp", "")
        interval = state.get("interval", "15m")

        gold_g, tp_price, sl_price, cash, cost, cur_val, pnl, trades_td, directive = 0.0, None, None, 0.0, 0.0, 0.0, 0.0, 0, ""
        time_part = ""
        if timestamp_str and timestamp_str != "N/A":
            try: time_part = timestamp_str.split("T")[1][:5] if "T" in timestamp_str else timestamp_str.split(" ")[1][:5]
            except Exception: time_part = str(timestamp_str)

        external_sg = state.get("session_gate") or {}
        trades_this_session = external_sg.get("trades_this_session") or external_sg.get("session_trades") or 0
        sg = self._compute_session_gate(timestamp_str, trades_this_session=trades_this_session)
        for k, v in external_sg.items():
            if v is not None and k in sg: sg[k] = v

        dead_zone_warning = ""
        if time_part:
            try:
                if sg.get("is_dead_zone"): dead_zone_warning = f"\n*** DEAD ZONE (Session '{sg['session_name']}') — NO new BUY entries allowed. HOLD only. ***"
            except Exception: pass

        lines = [
            f"Timestamp: {timestamp_str} (time: {time_part}) | Interval: {interval}{dead_zone_warning}",
            f"Gold (USD): ${spot}/oz | USD/THB: {usd_thb}",
            f"Gold (THB/baht_weight): ฿{sell_thb} sell / ฿{buy_thb} buy  [ออม NOW]",
            f"Gold (THB/gram actual): ≈{gold_thb_per_gram_str}/gram  ← use this for position sizing, NOT baht_weight",
            f"Spread coverage: spread={spread_cov.get('spread_thb', 'N/A')} THB | expected_move={spread_cov.get('expected_move_thb', 'N/A')} THB | edge_score={spread_cov.get('edge_score', 'N/A')}",
            f"RSI({rsi.get('period', 14)}): {rsi.get('value', 'N/A')} [{rsi.get('signal', 'N/A')}]",
            f"MACD: {macd.get('macd_line', 'N/A')}/{macd.get('signal_line', 'N/A')} hist:{macd.get('histogram', 'N/A')} [{macd.get('signal', 'N/A')}]",
            f"Trend: EMA20={trend.get('ema_20', 'N/A')} EMA50={trend.get('ema_50', 'N/A')} [{trend.get('trend', 'N/A')}]",
            f"BB: upper={bb.get('upper', 'N/A')} lower={bb.get('lower', 'N/A')}",
            f"Latest Close ({interval}): ${ti.get('latest_close', 'N/A')}/oz",
            f"ATR: {atr.get('value', 'N/A')} {atr.get('unit', '')}",
        ]

        portfolio = state.get("portfolio", {})
        quota = state.get("execution_quota", {})
        if quota:
            lines += ["", "── Daily Entry Quota ──", f"  Target entries/day: {quota.get('daily_target_entries', 6)}", f"  Entries done:       {quota.get('entries_done', 0)}", f"  Entries remaining:  {quota.get('entries_remaining', 0)}", f"  Quota met:          {quota.get('quota_met', False)}", f"  Current slot:       {quota.get('current_slot', 'N/A')} / 6", f"  Min entries by now: {quota.get('min_entries_by_now', 'N/A')}", f"  Next BUY min conf:  {quota.get('required_confidence_for_next_buy', 'N/A')}", f"  Next BUY size:      {quota.get('recommended_next_position_thb', 'N/A')} THB", "  Rule: prioritize capital safety first; if no valid edge, HOLD is allowed.", "── End Daily Entry Quota ──"]

        if portfolio:
            cash, gold_g, pnl, trades_td = float(portfolio.get("cash_balance", 0.0)), float(portfolio.get("gold_grams", 0.0)), float(portfolio.get("unrealized_pnl", 0.0)), portfolio.get("trades_today", 0)
            cost, cur_val, tp_price, sl_price = float(portfolio.get("cost_basis_thb", 0.0)), float(portfolio.get("current_value_thb", 0.0)), portfolio.get("take_profit_price"), portfolio.get("stop_loss_price")

            MIN_BUY_CASH = 1000
            if cash >= MIN_BUY_CASH and gold_g == 0: can_buy = "YES"
            elif cash < MIN_BUY_CASH: can_buy = f"NO — insufficient cash (฿{cash:.0f} < ฿{MIN_BUY_CASH})"
            else: can_buy = "NO — already holding gold"
            can_sell = f"YES ({gold_g:.4f}g held)" if gold_g > 0 else "NO — no gold held"

            pnl_status = portfolio.get("risk_status", "")
            pnl_tag = f"  ← {pnl_status} (You MUST NOT SELL if this is negative, unless SL is hit)" if pnl < 0 else "  ← PROFITABLE (Ready to SELL if momentum drops)"

            lines += ["", "── Portfolio ──", f"  Cash:           ฿{cash:,.2f}", f"  Gold:           {gold_g:.4f} g", f"  Cost basis:     ฿{cost:,.2f}", f"  Current value:  ฿{cur_val:,.2f}", f"  Unrealized PnL: ฿{pnl:,.2f}{pnl_tag}", f"  Trades today:   {trades_td}", f"  can_buy:  {can_buy}", f"  can_sell: {can_sell}", "── End Portfolio ──"]

        if sg:
            session_name, is_dead, remaining, trades_sess, min_req, day_type = sg.get("session_name", "UNKNOWN"), sg.get("is_dead_zone", False), sg.get("minutes_remaining", "?"), sg.get("trades_this_session", 0), sg.get("min_required_trades", 2), sg.get("day_type", "")
            session_status = "⛔ DEAD ZONE (HOLD only)" if is_dead else "✅ ACTIVE"
            lines += ["", "── Session & Quota ──", f"  Session: {session_name}{' (' + day_type + ')' if day_type else ''} | {session_status}", f"  Trades this session: {trades_sess} / min required: {min_req}", f"  Time remaining: {remaining} min", "── End Session ──"]

        directive = state.get("backtest_directive", "")
        if directive: lines += ["", "── DIRECTIVE ──", directive, "── End DIRECTIVE ──"]

        tp_price, sl_price, gold_g = portfolio.get("take_profit_price"), portfolio.get("stop_loss_price"), float(portfolio.get("gold_grams", 0.0))
        if gold_g > 0 and (tp_price or sl_price):
            lines += ["", f"── Active Position: {gold_g:.4f}g held ──", f"  TP={tp_price} / SL={sl_price} (System auto-sells at these levels. You may SELL early if momentum reverses strongly.)", "──────────────────────────────────────"]

        if iteration == 1:
            lines.append(""); lines.append("News Highlights:")
            latest_news = news_data.get("latest_news", [])
            if latest_info := latest_news:
                for item in latest_news: lines.append(f"  {item}")
            else: lines.append("  [INFO] No significant macro news available. Focus entirely on technical setups.")
            sg = state.get("session_gate")
            if sg and sg.get("apply_gate"):
                notes = [f"  • {n}" for n in (sg.get("notes") or [])]
                lines += ["", "── Session Context ──", f"session: {sg.get('session_id')}", f"mins_left: {sg.get('minutes_to_session_end')}", f"mode: {sg.get('llm_mode')}", "Use as context only; do not override market evidence.", *notes, "── End Session Context ──"]
            price_trend = md.get("price_trend", {})
            if price_trend: lines += ["", "── Price Trend ──", f"  Current: ${price_trend.get('current_close_usd', 'N/A')} | Prev: ${price_trend.get('prev_close_usd', 'N/A')}", f"  Daily chg: {price_trend.get('daily_change_pct', 'N/A')}%", "── End Price Trend ──"]
            pre_fetched = state.get("pre_fetched_tools", {})
            if pre_fetched:
                lines += ["", "── PRE-FETCHED TOOL RESULTS ──"]
                for tool_name, result in pre_fetched.items():
                    if isinstance(result, dict) and result.get("status") == "success":
                        data_str = str(result.get("data", result))
                        if len(data_str) > 1000: data_str = data_str[:1000] + "... [truncated]"
                        lines.append(f"  [{tool_name}] {data_str}")
                    else: lines.append(f"  [{tool_name}] {result}")
        else:
            lines += ["", f"── Iteration 2+ Summary ──", f"  Price: ฿{sell_thb} sell / ฿{buy_thb} buy | Close: ${ti.get('latest_close','N/A')}/oz"]
            if directive: lines += ["── DIRECTIVE ──", directive, "────────────────"]
            if gold_g > 0 and (tp_price or sl_price): lines.append(f"  Active position: {gold_g:.4f}g | TP={tp_price} SL={sl_price}")
            if gold_g > 0: lines.append("\n[CRITICAL] You are holding gold. DO NOT rush to SELL just to clear the quota. If the trend is still alive, output HOLD to let profits run.")
            lines.append("  [Prices refreshed. Use tool results below.]")

        return "\n".join(lines)

    def _format_tool_results(self, results: list) -> str:
        if not results: return "(No tool results yet)"
        parts = []
        for r in results:
            if hasattr(r, "tool_name"): parts.append(f"[{r.tool_name}] {r.status}: {r.data if r.data is not None else r.error}")
            else: parts.append(str(r))
        return "\n".join(parts)
    
    TZ_BKK = timezone(timedelta(hours=7))

    def _compute_session_gate(self, timestamp_str: str, trades_this_session: int = 0) -> dict:
        _default = {"session_name": "UNKNOWN", "is_dead_zone": False, "minutes_remaining": 0, "trades_this_session": trades_this_session, "min_required_trades": 2, "day_type": ""}
        bkk_min = self._parse_to_bkk_minutes(timestamp_str)
        if bkk_min is None: return _default
        try:
            ts_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=self.TZ_BKK)
            else: dt = dt.astimezone(self.TZ_BKK)
            weekday = dt.weekday()
        except Exception: return _default

        def _gate(name: str, end_min: int, dead: bool = False, day_type: str = "weekday") -> dict:
            return {"session_name": name, "is_dead_zone": dead, "minutes_remaining": max(0, end_min - bkk_min), "trades_this_session": trades_this_session, "min_required_trades": 2, "day_type": day_type}

        if weekday >= 5:
            WKND_START, WKND_END = 9 * 60 + 30, 17 * 60 + 30
            if WKND_START <= bkk_min <= WKND_END: return _gate("WEEKEND", WKND_END, dead=False, day_type="weekend")
            return _gate("DEAD_ZONE", 0, dead=True, day_type="weekend")

        if bkk_min <= 119: return _gate("AB", 119)
        if bkk_min <= 374: return _gate("DEAD_ZONE", 374, dead=True)
        if bkk_min <= 719: return _gate("AB", 719)
        if bkk_min <= 1079: return _gate("AFTN", 1079)
        return _gate("EVEN", 1439)

    def _parse_to_bkk_minutes(self, timestamp_str: str) -> int | None:
        try:
            ts_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=self.TZ_BKK)
            else: dt = dt.astimezone(self.TZ_BKK)
            return dt.hour * 60 + dt.minute
        except Exception: return None