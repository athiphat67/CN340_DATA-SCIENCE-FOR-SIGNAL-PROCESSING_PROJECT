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
  - sync MIN_BUY_CASH = 1008 (position 1000 + fee 8)
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
    max_position_thb: int = 1250
    system_prompt_static: str = ""       # cacheable — rules, conditions, format
    system_prompt_dynamic_template: str = ""  # injected per-call — market context

    def get_system_prompt(self, context: dict) -> str:
        """Legacy: ใช้ใน build_thought / build_final_decision เดิม"""
        prompt = self.system_prompt_template
        for key, value in context.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt

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
                    max_position_thb=rd.get("max_position_thb", 1250),
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
                    or "none (data pre-loaded)"
                    or role_def.system_prompt_template
                    or ""
                }
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
    ) -> dict:
        """
        สร้าง payload สำหรับ LLM API (ใช้ได้ทุก provider — OpenAI, Anthropic, Gemini ฯลฯ)
        Token savings มาจาก roles.json ที่กระชับขึ้น + แยก dynamic context ออกจาก static

        Returns
        -------
        {
            "system": "<static rules>\\n\\n<dynamic market context>",
            "messages": <history>
        }

        การใช้งาน (Anthropic)
        ----------------------
        payload = builder.build_messages(market_state, history)
        client.messages.create(model=..., max_tokens=1000, **payload)

        การใช้งาน (OpenAI-compatible)
        ------------------------------
        payload = builder.build_messages(market_state, history)
        messages = [{"role": "system", "content": payload["system"]}] + payload["messages"]
        client.chat.completions.create(model=..., messages=messages)
        """
        role_def = self._require_role()

        # ── Static block (cache ได้ — rules/conditions ไม่เปลี่ยนตลอด session) ──
        static_text = role_def.system_prompt_static or role_def.system_prompt_template

        # ── Dynamic block (inject ทุก call — เปลี่ยนตาม market/session) ──
        dynamic_text = role_def.render_dynamic(
            directive=market_state.get("backtest_directive", ""),
            session_gate=market_state.get("session_gate"),
            market_state={k: v for k, v in market_state.items()
                          if k not in ("backtest_directive", "session_gate")},
        )

        system = static_text + ("\n\n" + dynamic_text if dynamic_text else "")
        return {"system": system, "messages": history}

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

        # [FIX v2.2 & v2.3] อัปเดตชื่อ Tool ให้ตรงกับ registry จริง และสอนวิธีส่ง Args
        # [P10] เพิ่ม CALL_TOOLS (plural) format เพื่อ run หลาย tool พร้อมกัน
        if iteration == 1 and has_pre_fetched:
            # 🚀 [FAST TRACK MODE] ถ้ามีข้อมูล Pre-fetch สั่งให้ออกออเดอร์ทันที (Single-Shot)
            action_guidance = textwrap.dedent("""
                ## YOUR TASK: FAST-TRACK FINAL_DECISION
                The backend has pre-fetched core tools. Review them in 'PRE-FETCHED TOOL RESULTS'.
                If data is sufficient, output FINAL_DECISION now using the TRIPLE-SCENARIO format.
                
                ── Option A (FAST TRACK): Final Decision ──
                {
                  "action": "FINAL_DECISION",
                  "analysis": {
                    "bull_case": "<evidence for UP>",
                    "bear_case": "<risks for DOWN>",
                    "neutral_case": "<reasons to stay flat>"
                  },
                  "signal": "BUY" | "SELL" | "HOLD",
                  "confidence": 0.0-1.0,
                  "position_size_thb": 1250 or null,
                  "rationale": "<Synthesis of Bull vs Bear. Max 40 words>"
                }

                ── Option B (Fallback): Call Additional Tools ──
                {
                  "action": "CALL_TOOLS",
                  "thought": "<why you need MORE tools>",
                  "tools": [{"tool_name": "...", "tool_args": {}}]
                }
                
                CRITICAL: If signal is BUY, position_size_thb MUST be 1250. If confidence < 0.58, MUST be HOLD.
            """).strip()
        elif iteration == 1:
            action_guidance = (
                "## YOUR TASK THIS ITERATION: CALL_TOOL or CALL_TOOLS (mandatory)\n"
                "You MUST call at least one tool before deciding. "
                "If you need multiple tools, use CALL_TOOLS to run them in parallel — "
                "this saves iterations and is preferred over sequential single calls.\n\n"

                "── Option A (PREFERRED): Call multiple tools at once ──\n"
                "{\n"
                "  \"action\": \"CALL_TOOLS\",\n"
                "  \"thought\": \"<why you need these tools>\",\n"
                "  \"tools\": [\n"
                "    {\"tool_name\": \"get_htf_trend\", \"tool_args\": {}},\n"
                "    {\"tool_name\": \"get_deep_news_by_category\", \"tool_args\": {\"category\": \"fed_policy\"}}\n"
                "  ]\n"
                "}\n\n"

                "── Option B (fallback): Call a single tool ──\n"
                "{\n"
                "  \"action\": \"CALL_TOOL\",\n"
                "  \"thought\": \"<why you need this tool>\",\n"
                "  \"tool_name\": \"get_htf_trend\",\n"
                "  \"tool_args\": {}\n"
                "}\n\n"

                "DO NOT output FINAL_DECISION this iteration."
            )
        elif iteration == 2:
            action_guidance = (
                "## YOUR TASK THIS ITERATION: CALL_TOOL, CALL_TOOLS, or FINAL_DECISION\n"
                "You have tool results so far. Choose ONE option:\n"
                "  A) FINAL_DECISION — if you already have enough data to decide.\n"
                "  B) CALL_TOOL — if you need exactly one more tool.\n"
                "  C) CALL_TOOLS — if you need multiple additional tools at once (parallel).\n\n"

                "FINAL_DECISION format:\n"
                "{\n"
                "  \"action\": \"FINAL_DECISION\",\n"
                "  \"signal\": \"BUY\" | \"SELL\" | \"HOLD\",\n"
                "  \"confidence\": 0.0-1.0,\n"
                "  \"position_size_thb\": 1250 or null,\n"
                "  \"rationale\": \"[Met Buy: 1,3,6 | Met Sell: None] <อธิบายเหตุผลสั้นๆ>\"\n"
                "}\n\n"

                "CALL_TOOL format (single tool):\n"
                "{\n"
                "  \"action\": \"CALL_TOOL\",\n"
                "  \"thought\": \"<why you need this tool>\",\n"
                "  \"tool_name\": \"get_deep_news_by_category\",\n"
                "  \"tool_args\": {\"category\": \"fed_policy\"}\n"
                "}\n\n"

                "CALL_TOOLS format (multiple tools in parallel):\n"
                "{\n"
                "  \"action\": \"CALL_TOOLS\",\n"
                "  \"thought\": \"<why you need these tools>\",\n"
                "  \"tools\": [\n"
                "    {\"tool_name\": \"detect_swing_low\", \"tool_args\": {}},\n"
                "    {\"tool_name\": \"get_deep_news_by_category\", \"tool_args\": {\"category\": \"geopolitics\"}}\n"
                "  ]\n"
                "}"
            )
        else:
            action_guidance = textwrap.dedent("""
                ## YOUR TASK THIS ITERATION: FINAL_DECISION (mandatory)
                You have reached the final stage. You MUST perform a Triple-Scenario Analysis (Bull/Bear/Neutral) 
                before reaching your verdict to ensure zero confirmation bias.

                ```json
                {
                  "action": "FINAL_DECISION",
                  "analysis": {
                    "bull_case": "<why price might go UP + supporting evidence>",
                    "bear_case": "<why price might go DOWN + potential risks>",
                    "neutral_case": "<reasons for staying flat/sideways/uncertainty>"
                  },
                  "signal": "BUY" | "SELL" | "HOLD",
                  "confidence": 0.0-1.0,
                  "position_size_thb": 1250 or null,
                  "rationale": "<Synthesis: Why your chosen signal outweighs the opposing cases. Max 40 words>"
                }
                ```
                "CRITICAL: Default to HOLD ONLY if: (a) confidence < 0.50, OR "
                "(b) fewer than 2 BUY/SELL conditions are met. "
                "A bearish intermarket signal alone is NOT sufficient to override "
                "a bullish technical setup with ≥3 conditions met."
            """).strip()
        
        if iteration == 1 and not has_pre_fetched:
            tools_section = f"### AVAILABLE TOOLS\n{AVAILABLE_TOOLS_INFO}"
        else:
            # ดึงชื่อ tool จาก AVAILABLE_TOOLS_INFO แบบ static หรือ hardcode ก็ได้
            tool_names_list = self._get_tools()
            _TOOL_NAMES = ", ".join(tool_names_list) if tool_names_list else "none"
            tools_section = f"### AVAILABLE TOOLS (names only)\n{_TOOL_NAMES}"

        user = textwrap.dedent(f"""
            ## Iteration {iteration}

            {tools_section}

            ### MARKET STATE
            {self._format_market_state(market_state)}

            ### PREVIOUS TOOL RESULTS
            {self._format_tool_results(tool_results)}

            {action_guidance}
        """).strip()
        
        return PromptPackage(
            system=system, user=user, step_label=f"THOUGHT_{iteration}", thinking_mode="high"
        )

    def build_final_decision(
        self,
        market_state: dict,
        tool_results: list,
    ) -> PromptPackage:
        system = self._get_system()

        user = textwrap.dedent(f"""
            ### MARKET STATE
            {self._format_market_state(market_state)}

            ### ANALYSIS SO FAR
            {self._format_tool_results(tool_results)}

            ## FINAL VERDICT REQUIRED
            You have reached the maximum number of iterations. You MUST output a FINAL_DECISION now.
            Perform a Triple-Scenario Analysis (ToT) to weigh all evidence before signaling.

            {{
              "action": "FINAL_DECISION",
              "analysis": {{
                "bull_case": "...",
                "bear_case": "...",
                "neutral_case": "..."
              }},
              "signal": "BUY" | "SELL" | "HOLD",
              "confidence": 0.0-1.0,
              "position_size_thb": 1250,
              "rationale": "<Synthesis: Why your chosen signal wins. Max 40 words>"
            }}

            CRITICAL RULES:
            1. If signal is BUY, position_size_thb MUST be 1250.
            2."CRITICAL: Default to HOLD ONLY if: (a) confidence < 0.58, OR "
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

    def _format_market_state(self, state: dict) -> str:
        """Format market state for LLM — includes timestamp for time-based rules"""
        # print(state)  # Debug: ดูโครงสร้าง market state เต็มๆ ก่อนจัดรูปแบบ
        md   = state.get("market_data", {})
        ti   = state.get("technical_indicators", {})
        news_data = state.get("news", {})

        # print("\n=== FULL md ===")
        # print(json.dumps(md, indent=4, ensure_ascii=False))
        # print("========================\n")

        # print("\n=== FULL ti ===")
        # print(json.dumps(ti, indent=4, ensure_ascii=False))
        # print("========================\n")

        # print("\n=== FULL news ===")
        # print(json.dumps(news_data, indent=4, ensure_ascii=False))
        # print("========================\n")

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

        dead_zone_warning = ""
        if time_part:
            try:
                minutes = self._parse_to_bkk_minutes(timestamp_str)
                if minutes is None:
                    pass
                else:
                    if 90 <= minutes <= 119:
                        dead_zone_warning = "\n*** WARNING: Time 01:30–01:59 — Market closes at 02:00. SL3: SELL if holding gold! ***"
                    # elif 120 <= minutes <= 374:
                    #     dead_zone_warning = "\n*** INFO: Dead zone 02:00–06:14 — Cannot execute trades. ***"
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
            f"Latest Close ({interval}): ${ti.get('latest_close', 'N/A')}/oz  ← use this vs EMA/BB",
            f"ATR: {atr.get('value', 'N/A')} {atr.get('unit', '')} (≈{atr.get('value_usd', '?')} USD/oz)",
            "News Highlights:",
        ]

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
            lines += [
                "",
                "── Session Gate (in-session trading context) ──",
                f"  session_id: {sg.get('session_id')}",
                f"  quota_group_id: {sg.get('quota_group_id')}",
                f"  minutes_to_session_end: {sg.get('minutes_to_session_end')}",
                f"  quota_urgent: {sg.get('quota_urgent')}",
                f"  llm_mode: {sg.get('llm_mode')} "
                f"(suggested min confidence: {sg.get('suggested_min_confidence')})",
            ]
            for note in sg.get("notes") or []:
                lines.append(f"  • {note}")
            lines.append("── End Session Gate ──")

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

        portfolio = state.get("portfolio", {})
        if portfolio:
            cash      = portfolio.get("cash_balance", 0.0)
            gold_g    = portfolio.get("gold_grams", 0.0)
            pnl       = portfolio.get("unrealized_pnl", 0.0)
            trades_td = portfolio.get("trades_today", 0)
            cost      = portfolio.get("cost_basis_thb", 0.0)
            cur_val   = portfolio.get("current_value_thb", 0.0)

            MIN_BUY_CASH = 1008
            can_buy = (
                "YES" if (cash >= MIN_BUY_CASH and gold_g == 0)
                else f"NO — insufficient cash (฿{cash:.0f} < ฿{MIN_BUY_CASH})" if cash < MIN_BUY_CASH
                else "NO — already holding gold"
            )
            can_sell = f"YES ({gold_g:.4f}g held)" if gold_g > 0 else "NO — no gold held (short selling not supported)"

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

        directive = state.get("backtest_directive", "")
        if directive:
            lines += ["", "── DIRECTIVE ──", directive, "── End DIRECTIVE ──"]
            
        # --- [เพิ่มใหม่] นำ Pre-fetched Tools มาแสดงผล ---
        pre_fetched = state.get("pre_fetched_tools", {})
        if pre_fetched:
            lines += ["", "── PRE-FETCHED TOOL RESULTS ──"]
            lines.append("The backend has already executed these tools for you. DO NOT call them again unless necessary:")
            for tool_name, result in pre_fetched.items():
                # จัด Format ให้อ่านง่าย
                if isinstance(result, dict) and result.get("status") == "success":
                    # ซ่อน status เพื่อประหยัด Token โชว์แค่ data
                    data_str = str(result.get("data", result))
                    # ตัดให้สั้นลงถ้าข่าวฟังก์ชันส่งมายาวเกินไป
                    if len(data_str) > 1000: data_str = data_str[:1000] + "... [truncated]"
                    lines.append(f"  [{tool_name}] {data_str}")
                else:
                    lines.append(f"  [{tool_name}] {result}")
            lines.append("── End Pre-fetched Tools ──")

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