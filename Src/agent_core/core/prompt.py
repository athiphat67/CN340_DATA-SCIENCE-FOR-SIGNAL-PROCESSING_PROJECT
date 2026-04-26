"""
prompt.py — Part C: Prompt System
Builds PromptPackage objects for the ReAct loop.

[FIX v2.1]
  - build_final_decision() ใช้ system prompt เต็มจาก roles.json
  - _format_market_state() เพิ่ม timestamp ให้ LLM ใช้ตรวจ time-based exit rule

[FIX v2.2]
  - build_thought() เพิ่ม iteration-aware guidance:
      Iteration 1 → บังคับ CALL_TOOL ห้าม FINAL_DECISION
      Iteration 2 → แนะนำ tool เพิ่มหรือตัดสินใจได้
      Iteration 3+ → บังคับ FINAL_DECISION ทันที
  - ลบ OUTPUT FORMAT ซ้ำออกจาก user prompt (ให้ system prompt จัดการ)

[FIX v2.5]
  - แก้ NameError: TZ_BKK → self.TZ_BKK ใน _parse_to_bkk_minutes()
  - ลบ PnL hardcode thresholds ออกจาก _format_market_state()
      → pnl_status อ่านจาก portfolio["risk_status"] ที่ risk.py inject มา
      → PromptBuilder ไม่มี TP/SL constants ใดๆ อีกต่อไป
  - sync MIN_BUY_CASH = 1000 (no fee)
  - can_buy logic แยก case: insufficient cash vs already holding
  - build_final_decision: position_size_thb 1000 

[P10 — Async Tool Execution / Parallel Tool Calls]
  - build_thought() เพิ่ม action "CALL_TOOLS" (plural) ใน action_guidance ทุก iteration
      iteration 1 → แนะนำ CALL_TOOLS เป็น preferred path (เรียก 2 tool พร้อมกันได้)
                    ยังคง CALL_TOOL (single) ไว้เป็น fallback format
      iteration 2 → เพิ่ม option C: CALL_TOOLS ถ้ายังต้องการ tool เพิ่มหลายตัว
      iteration 3+ → บังคับ FINAL_DECISION เหมือนเดิม (ไม่เพิ่ม CALL_TOOLS)
  - format CALL_TOOLS: {"action": "CALL_TOOLS", "thought": "...", "tools": [...]}
"""

import json
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import textwrap
from datetime import datetime, timezone, timedelta

from data_engine.tools.tool_registry import AVAILABLE_TOOLS_INFO
# ─────────────────────────────────────────────
# Core data transfer object
# ─────────────────────────────────────────────


@dataclass
class PromptPackage:
    """Container ที่ส่งระหว่าง PromptBuilder → LLMClient"""

    system: str
    user: str
    step_label: str = "THOUGHT"
    thinking_mode: Optional[str] = None


# ─────────────────────────────────────────────
# Role enum
# ─────────────────────────────────────────────


class AIRole(Enum):
    ANALYST = "analyst"
    # RISK_MANAGER = "risk_manager"  # TODO: implement later
    # TRADER = "trader"              # TODO: implement later


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
    system_prompt_template: str          # legacy / fallback (single string)
    available_skills: list
    confidence_threshold: float = 0.58
    max_position_thb: int = 1000
    system_prompt_static: str = ""       # cacheable — rules, conditions, format
    system_prompt_dynamic_template: str = ""  # injected per-call — market context

    def get_system_prompt(self, context: dict) -> str:
        """Fix v2.6: ดึงจาก system_prompt_static ก่อน ถ้าไม่มีค่อย fallback"""
        base_prompt = self.system_prompt_static or self.system_prompt_template
        for key, value in context.items():
            base_prompt = base_prompt.replace(f"{{{key}}}", str(value))
        return base_prompt

    def render_dynamic(self, directive: str, session_gate: dict, market_state: dict) -> str:
        """Render dynamic context block สำหรับ build_messages()"""
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
            # รองรับทั้ง format เก่า (system_prompt) และใหม่ (system_prompt_static)
            legacy_prompt = rd.get("system_prompt_template", rd.get("system_prompt", ""))
            self.register(
                RoleDefinition(
                    name=role_enum,
                    title=rd["title"],
                    system_prompt_template=legacy_prompt,
                    available_skills=rd["available_skills"],
                    confidence_threshold=rd.get("confidence_threshold", 0.58),
                    max_position_thb=rd.get("max_position_thb", 1000),
                    system_prompt_static=rd.get("system_prompt_static", legacy_prompt),
                    system_prompt_dynamic_template=rd.get("system_prompt_dynamic_template", ""),
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

    def build_messages(
        self,
        market_state: dict,
        history: list,
    ) -> list:
        """
        Fix v2.6: สร้าง payload แบบ List of Dicts เพื่อให้เข้ากับ OpenRouter / OpenAI Format 100%
        """
        role_def = self._require_role()
        max_pos = int(role_def.max_position_thb or 1000)

        static_text = role_def.system_prompt_static or role_def.system_prompt_template
        dynamic_text = role_def.render_dynamic(
            directive=market_state.get("backtest_directive", ""),
            session_gate=market_state.get("session_gate"),
            market_state={k: v for k, v in market_state.items()
                          if k not in ("backtest_directive", "session_gate")},
        )

        system_content = static_text + ("\n\n" + dynamic_text if dynamic_text else "")
        
        # คืนค่าเป็น List ที่มี role: system อยู่ด้านบนสุด
        return [{"role": "system", "content": system_content}] + history

    # ── public ──────────────────────────────────

    def build_thought(
        self,
        market_state: dict,
        tool_results: list,
        iteration: int,
    ) -> PromptPackage:
        role_def = self._require_role()
        tools_list = self._get_tools()
        system = self._get_system()
        
        has_pre_fetched = bool(market_state.get("pre_fetched_tools"))

        if iteration == 1 and has_pre_fetched:
            # 🚀 [FAST TRACK MODE] ถ้ามีข้อมูล Pre-fetch สั่งให้ออกออเดอร์ทันที (Single-Shot)
            action_guidance = textwrap.dedent(f"""
                ## YOUR TASK: FAST-TRACK FINAL_DECISION
                The backend has pre-fetched core tools. Review them in 'PRE-FETCHED TOOL RESULTS'.
                If data is sufficient, output FINAL_DECISION now using the TRIPLE-SCENARIO format.
                
                ── Option A (FAST TRACK): Final Decision ──
                {{
                  "action": "FINAL_DECISION",
                  "agent_reasoning": {{
                    "1_data_grounding": "...",
                    "2_market_hypothesis": "...",
                    "3_logical_constraints": "...",
                    "4_risk_assessment": "..."
                  }},
                  "analysis": {{ "bull_case": "...", "bear_case": "...", "neutral_case": "..." }},
                  "execution_check": {{ "is_spread_covered": true|false, "is_profitable_to_sell": true|false|null }},
                  "signal": "BUY" | "SELL" | "HOLD",
                  "confidence": 0.0-1.0,
                  "position_size_thb": {max_pos} or null,
                  "rationale": "<Synthesis of Bull vs Bear. Max 40 words>"
                }}

                ── Option B (Fallback): Call Additional Tools ──
                {{
                  "action": "CALL_TOOLS",
                  "thought": "<why you need MORE tools>",
                  "tools": [{{"tool_name": "...", "tool_args": {{}}}}]
                }}
                
                CRITICAL: If signal is BUY, position_size_thb MUST be {max_pos}. If confidence < {self.confidence_threshold}, MUST be HOLD.
            """).strip()
        elif iteration == 1:
            action_guidance = (
                "## ITERATION 1 — Preferred: CALL_TOOLS (max 2 core tools, only if critical missing data).\n"
                "If market_state + prefetch are sufficient, you may output FINAL_DECISION."
            )
        elif iteration == 2:
            action_guidance = (
                "## ITERATION 2 — Choose: FINAL_DECISION (if enough data) or CALL_TOOLS (max 2, if critical gap)."
            )
        # else:
        #     action_guidance = textwrap.dedent("""
        #         ## YOUR TASK THIS ITERATION: FINAL_DECISION (mandatory)
        #         You have reached the final stage. You MUST perform a Triple-Scenario Analysis (Bull/Bear/Neutral) 
        #         before reaching your verdict to ensure zero confirmation bias.

        #         ```json
        #         {
        #           "action": "FINAL_DECISION",
        #           "analysis": {
        #             "bull_case": "<why price might go UP + supporting evidence>",
        #             "bear_case": "<why price might go DOWN + potential risks>",
        #             "neutral_case": "<reasons for staying flat/sideways/uncertainty>"
        #           },
        #           "signal": "BUY" | "SELL" | "HOLD",
        #           "confidence": 0.0-1.0,
        #           "position_size_thb": 1000 or null,
        #           "rationale": "<Synthesis: Why your chosen signal outweighs the opposing cases. Max 40 words>"
        #         }
        #         ```
                
        #         "CRITICAL: Default to HOLD ONLY if: (a) confidence < {self.confidence_threshold} , OR (b) fewer than 2 BUY/SELL conditions are met. A bearish intermarket signal alone is NOT sufficient to override a bullish technical setup with ≥3 conditions met."
        #     """).strip()
        else:
            # แก้ไขจากเดิมที่เป็นข้อความยาวๆ ให้เหลือแบบสั้น (Slim Version)
            action_guidance = (
                f"## FINAL_DECISION mandatory – Triple scenario (bull/bear/neutral) then decision.\n"
                f"HOLD only if confidence<{self.confidence_threshold} or <2 conditions met."
            )
        
        if iteration == 1 and not has_pre_fetched:
            tools_section = f"### AVAILABLE TOOLS\n{AVAILABLE_TOOLS_INFO}"
        else:
            tool_names_list = self._get_tools()
            _TOOL_NAMES = ", ".join(tool_names_list) if tool_names_list else "none"
            tools_section = f"### AVAILABLE TOOLS (names only)\n{_TOOL_NAMES}"

        # 🎯 [ปรับแก้] ส่ง iteration เข้าไปใน _format_market_state
        user = textwrap.dedent(f"""
            ## Iteration {iteration}

            {tools_section}

            ### MARKET STATE
            {self._format_market_state(market_state, iteration=iteration)}

            ### PREVIOUS TOOL RESULTS
            {self._format_tool_results(tool_results)}

            {action_guidance}
        """).strip()
        
        return PromptPackage(
            system=system, user=user, step_label=f"THOUGHT_{iteration}", thinking_mode=None
        )

    def build_final_decision(
        self,
        market_state: dict,
        tool_results: list,
    ) -> PromptPackage:
        role_def = self._require_role()
        max_pos = int(role_def.max_position_thb or 1000)
        system = self._get_system()

        user = textwrap.dedent(f"""
            ### MARKET STATE
            {self._format_market_state(market_state)}

            ### ANALYSIS SO FAR
            {self._format_tool_results(tool_results)}

            ## FINAL VERDICT REQUIRED
            You must follow the strict reasoning framework before deciding. Inhibit your final signal until reasoning is fully written.

            {{
              "action": "FINAL_DECISION",
              "agent_reasoning": {{
                "1_data_grounding": "...",
                "2_market_hypothesis": "...",
                "3_logical_constraints": "...",
                "4_risk_assessment": "..."
              }},
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

    # ── private ─────────────────────────────────

    def _require_role(self) -> RoleDefinition:
        role_def = self.roles.get(self.role)
        if not role_def:
            raise ValueError(f"Role '{self.role}' not registered")
        return role_def

    def _format_market_state(self, state: dict, iteration: int = 1) -> str:
        """Format market state for LLM — dynamically slims down in later iterations"""
        md   = state.get("market_data", {})
        ti   = state.get("technical_indicators", {})
        news_data = state.get("news", {})

        spot    = md.get("spot_price_usd", {}).get("price_usd_per_oz", "N/A")
        usd_thb = md.get("forex", {}).get("usd_thb", "N/A")
        thai    = md.get("thai_gold_thb", {})
        spread_cov = md.get("spread_coverage", {})
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

        dead_zone_warning = ""
        if time_part:
            try:
                minutes = self._parse_to_bkk_minutes(timestamp_str)
                if minutes is not None:
                    if 90 <= minutes <= 119:
                        dead_zone_warning = "\n*** WARNING: Time 01:30–01:59 — Market closes at 02:00. SL3: SELL if holding gold! ***"
            except Exception:
                pass

        # ── 1. แกนหลัก (ส่งทุกรอบเพราะต้องใช้อ้างอิงราคา Real-time) ──
        lines = [
            f"Timestamp: {timestamp_str} (time: {time_part}) | Interval: {interval}{dead_zone_warning}",
            f"Gold (USD): ${spot}/oz | USD/THB: {usd_thb}",
            f"Gold (THB/gram): ฿{sell_thb} sell / ฿{buy_thb} buy  [ออม NOW]",
            f"Spread coverage: spread={spread_cov.get('spread_thb', 'N/A')} THB | expected_move={spread_cov.get('expected_move_thb', 'N/A')} THB | edge_score={spread_cov.get('edge_score', 'N/A')}",
            f"RSI({rsi.get('period', 14)}): {rsi.get('value', 'N/A')} [{rsi.get('signal', 'N/A')}]",
            f"MACD: {macd.get('macd_line', 'N/A')}/{macd.get('signal_line', 'N/A')} hist:{macd.get('histogram', 'N/A')} [{macd.get('signal', 'N/A')}]",
            f"Trend: EMA20={trend.get('ema_20', 'N/A')} EMA50={trend.get('ema_50', 'N/A')} [{trend.get('trend', 'N/A')}]",
            f"BB: upper={bb.get('upper', 'N/A')} lower={bb.get('lower', 'N/A')}",
            f"Latest Close ({interval}): ${ti.get('latest_close', 'N/A')}/oz  ← use this vs EMA/BB",
            f"ATR: {atr.get('value', 'N/A')} {atr.get('unit', '')} (≈{atr.get('value_usd', '?')} USD/oz)",
        ]

        # latest_news = news_data.get("latest_news", [])
        # news_count  = news_data.get("news_count", 0)
        # if latest_news:
        #     for item in latest_news:
        #         lines.append(f"  {item}")
        #     lines.append("  [INFO] News data is slimmed. Call 'get_deep_news_by_category' for deep-dive sentiment and details.")
        # elif news_count == 0:
        #     lines.append("  [INFO] No significant macro news available. Focus entirely on technical setups.")

        # sg = state.get("session_gate")
        # if sg and sg.get("apply_gate"):
        #     lines += [
        #         "",
        #         "── Session Gate (in-session trading context) ──",
        #         f"  session_id: {sg.get('session_id')}",
        #         f"  quota_group_id: {sg.get('quota_group_id')}",
        #         f"  minutes_to_session_end: {sg.get('minutes_to_session_end')}",
        #         f"  quota_urgent: {sg.get('quota_urgent')}",
        #         f"  llm_mode: {sg.get('llm_mode')} "
        #         f"(suggested min confidence: {sg.get('suggested_min_confidence')})",
        #     ]
        #     for note in sg.get("notes") or []:
        #         lines.append(f"  • {note}")
        #     lines.append("── End Session Gate ──")

        # price_trend = md.get("price_trend", {})
        # if price_trend:
        #     # ดึง interval มาแสดงใน Label เพื่อความเท่และแม่นยำ
        #     lines += [
        #         "",
        #         f"── Price Trend (Interval {interval}) ──",
        #         f"  Current: ${price_trend.get('current_close_usd', 'N/A')} | Prev: ${price_trend.get('prev_close_usd', 'N/A')}",
        #     ]
            
        #     # [FIX] เปลี่ยนการเรียก Key ให้ตรงกับที่คำนวณใน Orchestrator
        #     # ใช้ get('change_pct') หรือ '1_period_change_pct' ตามที่คุณตั้งชื่อไว้
        #     change = price_trend.get('change_pct') or price_trend.get('1_period_change_pct', 'N/A')
        #     lines.append(f"  1-bar chg: {change}%")

        #     if "5p_change_pct" in price_trend:
        #         lines.append(f"  5-bar chg: {price_trend['5p_change_pct']}%")
                
        #     if "10p_range_high" in price_trend:
        #         lines.append(
        #             f"  10-bar range: ${price_trend.get('10p_range_low', 'N/A')} — ${price_trend.get('10p_range_high', 'N/A')}"
        #         )
        #     lines.append("── End Price Trend ──")

        portfolio = state.get("portfolio", {})
        if portfolio:
            cash      = portfolio.get("cash_balance", 0.0)
            gold_g    = portfolio.get("gold_grams", 0.0)
            pnl       = portfolio.get("unrealized_pnl", 0.0)
            trades_td = portfolio.get("trades_today", 0)
            cost      = portfolio.get("cost_basis_thb", 0.0)
            cur_val   = portfolio.get("current_value_thb", 0.0)

            MIN_BUY_CASH = 1000
            can_buy = (
                "YES" if (cash >= MIN_BUY_CASH and gold_g == 0)
                else f"NO — insufficient cash (฿{cash:.0f} < ฿{MIN_BUY_CASH})" if cash < MIN_BUY_CASH
                else "NO — already holding gold"
            )
            can_sell = f"YES ({gold_g:.4f}g held)" if gold_g > 0 else "NO — no gold held (short selling not supported)"

            pnl_status = portfolio.get("risk_status", "")
            pnl_tag = f"  ← {pnl_status} (You MUST NOT SELL if this is negative, unless SL is hit)" if pnl < 0 else "  ← PROFITABLE (Ready to SELL if momentum drops)"

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
            
            
        recent_trades = state.get("recent_trades", [])
        
        print(f"DEBUG: Processing {len(recent_trades)} recent trades in PromptBuilder")
        
        
        if recent_trades:
            lines += ["", "── RECENT TRADE MEMORY (LEARN FROM MISTAKES) ──"]
            for t in recent_trades[-3:]:
                # รูปแบบ: 14:15 | SELL | Result: ❌ LOSS (-150.00 THB) | Reason: RSI ตัดลง...
                lines.append(f"  • {t.get('time')} | {t.get('action')} | Result: {t.get('status')} ({t.get('pnl_thb')} THB) | Reason: {t.get('reason')}")
            
            lines.append("  [CRITICAL RULE]: Review the memory. If the last trade was a LOSS, DO NOT use the exact same logic/setup again unless the market regime has clearly reversed.")
            lines.append("── End Trade Memory ──")

        # ── คำสั่งบังคับต้องให้เห็นทุกรอบ ──
        directive = state.get("backtest_directive", "")
        if directive:
            lines += ["", "── DIRECTIVE ──", directive, "── End DIRECTIVE ──"]

        # ── Portfolio TP/SL — LLM ต้องรู้ว่า RiskManager ตั้งค่าไว้เท่าไหร่ ──
        portfolio = state.get("portfolio", {})
        tp_price = portfolio.get("take_profit_price")
        sl_price = portfolio.get("stop_loss_price")
        gold_g   = float(portfolio.get("gold_grams", 0.0))
        if gold_g > 0 and (tp_price or sl_price):
            lines += [
                "",
                f"── Active Position: {gold_g:.4f}g held ──",
                f"  TP={tp_price} / SL={sl_price} (system will auto-SELL when hit — do NOT pre-empt unless technical signal warrants early exit)",
                "──────────────────────────────────────",
            ]

        # ── 2. ส่วนเสริม (ส่งเฉพาะ Iteration 1 เพื่อประหยัด Token) ──
        if iteration == 1:
            lines.append("News Highlights:")
            latest_news = news_data.get("latest_news", [])
            news_count  = news_data.get("news_count", 0)
            if latest_news:
                for item in latest_news:
                    lines.append(f"  {item}")
                lines.append("  [INFO] News data is slimmed. Call 'get_deep_news_by_category' for deep-dive sentiment and details.")
            elif news_count == 0:
                lines.append("  [INFO] No significant macro news available. Focus entirely on technical setups.")

            sg = state.get("session_gate")
            if sg and sg.get("apply_gate"):
                notes = [f"  • {n}" for n in (sg.get("notes") or [])]
                lines += [
                    "",
                    "── Session Context ──",
                    f"session: {sg.get('session_id')}",
                    f"mins_left: {sg.get('minutes_to_session_end')}",
                    f"mode: {sg.get('llm_mode')}",
                    "Use as context only; do not override market evidence.",
                    *notes,
                    "── End Session Context ──",
                ]

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
                    lines.append(f"  10d range: ${price_trend['10d_low']} — ${price_trend['10d_high']}")
                lines.append("── End Price Trend ──")
                
            pre_fetched = state.get("pre_fetched_tools", {})
            if pre_fetched:
                lines += ["", "── PRE-FETCHED TOOL RESULTS ──"]
                lines.append("The backend has already executed these tools for you. DO NOT call them again unless necessary:")
                for tool_name, result in pre_fetched.items():
                    if isinstance(result, dict) and result.get("status") == "success":
                        data_str = str(result.get("data", result))
                        if len(data_str) > 1000: data_str = data_str[:1000] + "... [truncated]"
                        lines.append(f"  [{tool_name}] {data_str}")
                    else:
                        lines.append(f"  [{tool_name}] {result}")
                lines.append("── End Pre-fetched Tools ──")
        
        # ── 3. ซ่อนข้อมูลยืดเยื้อใน Iteration ถัดไป ──
        else:
            # ส่งเฉพาะราคา latest ที่อาจเปลี่ยน ไม่ซ้ำ RSI/MACD/BB ที่ LLM เห็นแล้วใน iter 1
            lines = [
                f"Timestamp: {timestamp_str} | Price: ฿{sell_thb} sell / ฿{buy_thb} buy | Close: ${ti.get('latest_close','N/A')}/oz",
            ]
            if directive:
                lines += ["── DIRECTIVE ──", directive, "────────────────"]
            if gold_g > 0 and (tp_price or sl_price):
                lines.append(f"Active position: {gold_g:.4f}g | TP={tp_price} SL={sl_price}")
            lines.append("[Prices refreshed. All other market data unchanged from iteration 1 — use tool results below.]")

        return "\n".join(lines)

    def _format_tool_results(self, results: list) -> str:
        if not results:
            return "(No tool results yet)"
        parts = []
        for r in results:
            if hasattr(r, "tool_name"):
                parts.append(f"[{r.tool_name}] {r.status}: {r.data or r.error}")
            else:
                parts.append(str(r))
        return "\n".join(parts)
    
    TZ_BKK = timezone(timedelta(hours=7))

    def _parse_to_bkk_minutes(self, timestamp_str: str) -> int | None:
        """แปลง timestamp (UTC หรือ UTC+7) → นาทีนับจากเที่ยงคืน Bangkok time"""
        try:
            # รองรับ 2 format: "2024-03-01T10:00:00Z" และ "2024-03-01 10:00:00"
            ts_str = timestamp_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_str)

            # ถ้าไม่มี tzinfo สมมติว่าเป็น UTC+7 แล้ว (จาก HSH data)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.TZ_BKK)
            else:
                dt = dt.astimezone(self.TZ_BKK)

            return dt.hour * 60 + dt.minute
        except Exception:
            return None
