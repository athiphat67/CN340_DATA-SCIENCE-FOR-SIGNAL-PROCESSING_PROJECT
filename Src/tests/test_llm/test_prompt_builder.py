"""
test_prompt_builder.py — Tests สำหรับ prompt.py

ครอบคลุม:
  1. PromptPackage    — dataclass fields, default step_label
  2. Skill            — to_prompt_text(), to_prompt_text() เมื่อ tools ว่าง
  3. SkillRegistry    — register, get, get_tools_for_skills, unknown skill
  4. RoleDefinition   — get_system_prompt() แทนที่ placeholder
  5. RoleRegistry     — register, get, load_from_json (mock file)
  6. PromptBuilder    — build_thought() / build_final_decision() มี required fields
                       _format_market_state() → timestamp, dead zone warning, portfolio
                       _format_tool_results() → empty vs. non-empty
                       _require_role() raise ถ้า role ไม่ถูก register

Strategy: 100% real (ไม่มี mock) + mock roles.json open
"""

import json
import pytest
from unittest.mock import patch, mock_open

from agent_core.core.prompt import (
    PromptPackage,
    AIRole,
    Skill,
    SkillRegistry,
    RoleDefinition,
    RoleRegistry,
    PromptBuilder,
)


# ══════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════

def _make_skill_registry() -> SkillRegistry:
    sr = SkillRegistry()
    sr.register(Skill(name="analysis", description="Analyze market", tools=["get_news", "run_calculator"]))
    sr.register(Skill(name="trading",  description="Execute trade",  tools=["place_order"]))
    return sr


def _make_role_registry(sr: SkillRegistry) -> RoleRegistry:
    rr = RoleRegistry(sr)
    rr.register(RoleDefinition(
        name=AIRole.ANALYST,
        title="Gold Analyst",
        system_prompt_template="You are {role_title}. Tools: {available_tools}",
        available_skills=["analysis"],
    ))
    return rr


def _minimal_market_state() -> dict:
    return {
        "market_data": {
            "spot_price_usd": {"price_usd_per_oz": 2350.0},
            "forex": {"usd_thb": 34.5},
            "thai_gold_thb": {"sell_price_thb": 45000, "buy_price_thb": 44800},
        },
        "technical_indicators": {
            "rsi": {"period": 14, "value": 55.0, "signal": "neutral"},
            "macd": {"macd_line": 0.5, "signal_line": 0.3, "histogram": 0.2},
            "trend": {"ema_20": 44900, "ema_50": 44600, "trend": "uptrend"},
            "bollinger": {"upper": 45500, "lower": 44300},
            "atr": {"value": 150.0},
        },
    }


# ══════════════════════════════════════════════════════════════════
# 1. PromptPackage
# ══════════════════════════════════════════════════════════════════


class TestPromptPackage:
    def test_fields_stored_correctly(self):
        p = PromptPackage(system="sys", user="usr", step_label="STEP_1")
        assert p.system == "sys"
        assert p.user == "usr"
        assert p.step_label == "STEP_1"

    def test_default_step_label(self):
        p = PromptPackage(system="s", user="u")
        assert p.step_label == "THOUGHT"

    def test_empty_strings_allowed(self):
        p = PromptPackage(system="", user="")
        assert p.system == ""
        assert p.user == ""


# ══════════════════════════════════════════════════════════════════
# 2. Skill
# ══════════════════════════════════════════════════════════════════


class TestSkill:
    def test_to_prompt_text_includes_name_and_description(self):
        s = Skill(name="analysis", description="Analyze gold market", tools=["get_news"])
        text = s.to_prompt_text()
        assert "analysis" in text
        assert "Analyze gold market" in text

    def test_to_prompt_text_includes_tools(self):
        s = Skill(name="trading", description="Trade", tools=["place_order", "get_news"])
        text = s.to_prompt_text()
        assert "place_order" in text
        assert "get_news" in text

    def test_to_prompt_text_empty_tools(self):
        s = Skill(name="readonly", description="Read only", tools=[])
        text = s.to_prompt_text()
        assert "none" in text.lower()

    def test_constraints_optional(self):
        s = Skill(name="s", description="d", tools=[], constraints={"max": 5})
        assert s.constraints == {"max": 5}

    def test_no_constraints_is_none(self):
        s = Skill(name="s", description="d", tools=[])
        assert s.constraints is None


# ══════════════════════════════════════════════════════════════════
# 3. SkillRegistry
# ══════════════════════════════════════════════════════════════════


class TestSkillRegistry:
    def test_register_and_get(self):
        sr = SkillRegistry()
        skill = Skill(name="trading", description="Trade", tools=["place_order"])
        sr.register(skill)
        assert sr.get("trading") is skill

    def test_get_unknown_returns_none(self):
        sr = SkillRegistry()
        assert sr.get("nonexistent") is None

    def test_get_tools_for_known_skills(self):
        sr = _make_skill_registry()
        tools = sr.get_tools_for_skills(["analysis"])
        assert "get_news" in tools
        assert "run_calculator" in tools

    def test_get_tools_for_multiple_skills_merged(self):
        sr = _make_skill_registry()
        tools = sr.get_tools_for_skills(["analysis", "trading"])
        assert "get_news" in tools
        assert "place_order" in tools

    def test_get_tools_for_unknown_skill_skips(self):
        sr = _make_skill_registry()
        tools = sr.get_tools_for_skills(["nonexistent"])
        assert tools == []

    def test_get_tools_sorted(self):
        sr = _make_skill_registry()
        tools = sr.get_tools_for_skills(["analysis", "trading"])
        assert tools == sorted(tools)

    def test_overwrite_existing_skill(self):
        sr = SkillRegistry()
        s1 = Skill(name="s", description="first", tools=[])
        s2 = Skill(name="s", description="second", tools=[])
        sr.register(s1)
        sr.register(s2)
        assert sr.get("s").description == "second"


# ══════════════════════════════════════════════════════════════════
# 4. RoleDefinition
# ══════════════════════════════════════════════════════════════════


class TestRoleDefinition:
    def test_get_system_prompt_replaces_placeholders(self):
        rd = RoleDefinition(
            name=AIRole.ANALYST,
            title="Gold Analyst",
            system_prompt_template="Role: {role_title} | Tools: {available_tools}",
            available_skills=[],
        )
        result = rd.get_system_prompt({"role_title": "Senior Analyst", "available_tools": "get_news"})
        assert "Senior Analyst" in result
        assert "get_news" in result

    def test_get_system_prompt_no_placeholders(self):
        rd = RoleDefinition(
            name=AIRole.TRADER,
            title="Trader",
            system_prompt_template="Fixed system prompt.",
            available_skills=[],
        )
        result = rd.get_system_prompt({})
        assert result == "Fixed system prompt."

    def test_get_system_prompt_multiple_placeholders(self):
        rd = RoleDefinition(
            name=AIRole.ANALYST,
            title="A",
            system_prompt_template="{a} and {b} and {a}",
            available_skills=[],
        )
        # str.replace แทนที่ทุก occurrence
        result = rd.get_system_prompt({"a": "X", "b": "Y"})
        assert "X" in result
        assert "Y" in result


# ══════════════════════════════════════════════════════════════════
# 5. RoleRegistry
# ══════════════════════════════════════════════════════════════════


class TestRoleRegistry:
    def test_register_and_get(self):
        sr = SkillRegistry()
        rr = RoleRegistry(sr)
        rd = RoleDefinition(name=AIRole.ANALYST, title="A", system_prompt_template="s", available_skills=[])
        rr.register(rd)
        assert rr.get(AIRole.ANALYST) is rd

    def test_get_unknown_returns_none(self):
        sr = SkillRegistry()
        rr = RoleRegistry(sr)
        assert rr.get(AIRole.TRADER) is None

    def test_load_from_json(self):
        """load_from_json() ต้องสร้าง RoleDefinition จากข้อมูล JSON"""
        sr = SkillRegistry()
        rr = RoleRegistry(sr)

        fake_json = json.dumps({
            "roles": [{
                "name": "analyst",
                "title": "Gold Analyst",
                "system_prompt_template": "You are {role_title}.",
                "available_skills": [],
            }]
        })

        with patch("builtins.open", mock_open(read_data=fake_json)):
            rr.load_from_json("fake/path/roles.json")

        role = rr.get(AIRole.ANALYST)
        assert role is not None
        assert role.title == "Gold Analyst"

    def test_load_from_json_invalid_role_name_raises(self):
        """role name ที่ไม่อยู่ใน AIRole enum → ValueError"""
        sr = SkillRegistry()
        rr = RoleRegistry(sr)

        fake_json = json.dumps({
            "roles": [{"name": "invalid_role", "title": "X", "system_prompt_template": "s", "available_skills": []}]
        })

        with patch("builtins.open", mock_open(read_data=fake_json)):
            with pytest.raises(ValueError):
                rr.load_from_json("fake/path/roles.json")


# ══════════════════════════════════════════════════════════════════
# 6. PromptBuilder
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def builder():
    sr = _make_skill_registry()
    rr = _make_role_registry(sr)
    return PromptBuilder(role_registry=rr, current_role=AIRole.ANALYST)


class TestPromptBuilderBuildThought:
    """build_thought() สร้าง PromptPackage ที่มี system + user prompt"""

    def test_returns_prompt_package(self, builder):
        result = builder.build_thought(_minimal_market_state(), [], iteration=1)
        assert isinstance(result, PromptPackage)

    def test_step_label_includes_iteration(self, builder):
        result = builder.build_thought(_minimal_market_state(), [], iteration=3)
        assert result.step_label == "THOUGHT_3"

    def test_system_prompt_not_empty(self, builder):
        result = builder.build_thought(_minimal_market_state(), [], iteration=1)
        assert len(result.system) > 0

    def test_user_prompt_contains_iteration(self, builder):
        result = builder.build_thought(_minimal_market_state(), [], iteration=2)
        assert "2" in result.user

    def test_user_prompt_contains_market_state(self, builder):
        result = builder.build_thought(_minimal_market_state(), [], iteration=1)
        # _format_market_state ต้องถูกเรียก — ราคาทองต้องอยู่ใน user prompt
        assert "45000" in result.user or "2350" in result.user

    def test_user_prompt_contains_final_decision_template(self, builder):
        result = builder.build_thought(_minimal_market_state(), [], iteration=1)
        assert "FINAL_DECISION" in result.user

    def test_system_prompt_cached_on_second_call(self, builder):
        """_get_system() ควร cache ไว้ ไม่สร้างใหม่ทุกครั้ง"""
        r1 = builder.build_thought(_minimal_market_state(), [], iteration=1)
        r2 = builder.build_thought(_minimal_market_state(), [], iteration=2)
        assert r1.system == r2.system


class TestPromptBuilderBuildFinalDecision:
    """build_final_decision() ใช้ full system prompt (FIX v2.1)"""

    def test_returns_prompt_package(self, builder):
        result = builder.build_final_decision(_minimal_market_state(), [])
        assert isinstance(result, PromptPackage)

    def test_step_label_is_thought_final(self, builder):
        result = builder.build_final_decision(_minimal_market_state(), [])
        assert result.step_label == "THOUGHT_FINAL"

    def test_uses_same_system_as_build_thought(self, builder):
        """FIX v2.1: system prompt ต้องเหมือนกับ build_thought()"""
        thought = builder.build_thought(_minimal_market_state(), [], iteration=1)
        final = builder.build_final_decision(_minimal_market_state(), [])
        assert final.system == thought.system

    def test_user_prompt_contains_market_state(self, builder):
        result = builder.build_final_decision(_minimal_market_state(), [])
        assert "45000" in result.user or "2350" in result.user

    def test_user_prompt_mentions_position_size(self, builder):
        result = builder.build_final_decision(_minimal_market_state(), [])
        assert "1000" in result.user


class TestPromptBuilderRequireRole:
    """_require_role() ควร raise ถ้า role ไม่ถูก register"""

    def test_unregistered_role_raises(self):
        sr = SkillRegistry()
        rr = RoleRegistry(sr)
        # ไม่ register ใดๆ เลย
        pb = PromptBuilder(role_registry=rr, current_role=AIRole.TRADER)

        with pytest.raises(ValueError, match="not registered"):
            pb.build_thought({}, [], iteration=1)


class TestFormatMarketState:
    """_format_market_state() ต้อง format ข้อมูลถูกต้อง"""

    def test_contains_spot_price(self, builder):
        state = _minimal_market_state()
        result = builder._format_market_state(state)
        assert "2350" in result

    def test_contains_usd_thb(self, builder):
        result = builder._format_market_state(_minimal_market_state())
        assert "34.5" in result

    def test_contains_thai_gold_prices(self, builder):
        result = builder._format_market_state(_minimal_market_state())
        assert "45000" in result
        assert "44800" in result

    def test_contains_rsi(self, builder):
        result = builder._format_market_state(_minimal_market_state())
        assert "RSI" in result
        assert "55" in result

    def test_dead_zone_warning_02_00(self, builder):
        """timestamp 02:00 → dead zone warning"""
        state = _minimal_market_state()
        state["timestamp"] = "2026-04-08T02:00:00"
        result = builder._format_market_state(state)
        assert "Dead zone" in result or "dead zone" in result

    def test_danger_zone_warning_01_30(self, builder):
        """timestamp 01:30 → danger zone warning (SL3)"""
        state = _minimal_market_state()
        state["timestamp"] = "2026-04-08T01:30:00"
        result = builder._format_market_state(state)
        assert "01:30" in result or "WARNING" in result

    def test_no_warning_normal_time(self, builder):
        """timestamp 10:00 → ไม่มี warning"""
        state = _minimal_market_state()
        state["timestamp"] = "2026-04-08T10:00:00"
        result = builder._format_market_state(state)
        assert "Dead zone" not in result
        assert "WARNING" not in result

    def test_portfolio_section_shown_when_present(self, builder):
        """ถ้ามี portfolio ใน state → แสดงใน format"""
        state = _minimal_market_state()
        state["portfolio"] = {
            "cash_balance": 1500.0,
            "gold_grams": 0.5,
            "unrealized_pnl": 50.0,
            "trades_today": 1,
            "cost_basis_thb": 1000.0,
            "current_value_thb": 1050.0,
        }
        result = builder._format_market_state(state)
        assert "Portfolio" in result or "Cash" in result
        assert "1,500" in result or "1500" in result

    def test_tp1_status_shown_for_large_pnl(self, builder):
        """unrealized_pnl >= 300 → แสดง TP1 TRIGGERED"""
        state = _minimal_market_state()
        state["portfolio"] = {
            "cash_balance": 500.0,
            "gold_grams": 1.0,
            "unrealized_pnl": 350.0,
            "trades_today": 1,
            "cost_basis_thb": 1000.0,
            "current_value_thb": 1350.0,
        }
        result = builder._format_market_state(state)
        assert "TP1" in result

    def test_sl1_status_shown_for_large_loss(self, builder):
        """unrealized_pnl <= -150 → แสดง SL1 TRIGGERED"""
        state = _minimal_market_state()
        state["portfolio"] = {
            "cash_balance": 500.0,
            "gold_grams": 1.0,
            "unrealized_pnl": -200.0,
            "trades_today": 1,
            "cost_basis_thb": 1000.0,
            "current_value_thb": 800.0,
        }
        result = builder._format_market_state(state)
        assert "SL1" in result

    def test_empty_market_state_does_not_crash(self, builder):
        """empty dict → ไม่ crash"""
        result = builder._format_market_state({})
        assert isinstance(result, str)

    def test_missing_news_graceful(self, builder):
        """ไม่มี news key → ไม่ crash"""
        state = _minimal_market_state()
        result = builder._format_market_state(state)
        assert "News Highlights" in result  # header ยังมี แต่ไม่มี items


class TestFormatToolResults:
    """_format_tool_results() format tool results ถูกต้อง"""

    def test_empty_list_returns_no_results_message(self, builder):
        result = builder._format_tool_results([])
        assert "No tool results" in result or "pre-loaded" in result

    def test_non_empty_list_stringified(self, builder):
        result = builder._format_tool_results(["tool output 1", "tool output 2"])
        assert "tool output 1" in result
        assert "tool output 2" in result

    def test_tool_result_with_tool_name_attr(self, builder):
        """object ที่มี tool_name attribute → format เป็น [tool_name] status: data"""
        class FakeResult:
            tool_name = "get_news"
            status = "success"
            data = "gold bullish"
            error = None

        result = builder._format_tool_results([FakeResult()])
        assert "get_news" in result
        assert "gold bullish" in result
