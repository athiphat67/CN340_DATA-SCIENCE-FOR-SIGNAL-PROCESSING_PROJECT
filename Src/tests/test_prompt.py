"""
test_prompt.py — Unit tests for PromptBuilder, RoleRegistry, SkillRegistry
Tests: loading configs, building prompts, formatting market state with/without portfolio.
"""

import os
import pytest

from agent_core.core.prompt import (
    PromptBuilder,
    PromptPackage,
    RoleRegistry,
    SkillRegistry,
    AIRole,
    Skill,
    RoleDefinition,
)


# ─── SkillRegistry ───────────────────────────────────────────────────────────

class TestSkillRegistry:

    def test_register_and_get(self):
        reg = SkillRegistry()
        skill = Skill(name="test_skill", description="A test skill", tools=["tool_a"])
        reg.register(skill)
        assert reg.get("test_skill") is skill

    def test_get_nonexistent_returns_none(self):
        reg = SkillRegistry()
        assert reg.get("nonexistent") is None

    def test_load_from_json(self, skills_json_path):
        if not os.path.exists(skills_json_path):
            pytest.skip("skills.json not found")
        reg = SkillRegistry()
        reg.load_from_json(skills_json_path)
        assert len(reg.skills) > 0

    def test_get_tools_for_skills(self):
        reg = SkillRegistry()
        reg.register(Skill(name="s1", description="d1", tools=["t1", "t2"]))
        reg.register(Skill(name="s2", description="d2", tools=["t2", "t3"]))
        tools = reg.get_tools_for_skills(["s1", "s2"])
        assert set(tools) == {"t1", "t2", "t3"}

    def test_skill_to_prompt_text(self):
        skill = Skill(name="analysis", description="Analyze market", tools=["rsi", "macd"])
        text = skill.to_prompt_text()
        assert "analysis" in text
        assert "rsi" in text


# ─── RoleRegistry ────────────────────────────────────────────────────────────

class TestRoleRegistry:

    def test_register_and_get(self):
        skill_reg = SkillRegistry()
        role_reg = RoleRegistry(skill_reg)
        role_def = RoleDefinition(
            name=AIRole.ANALYST,
            title="Gold Analyst",
            system_prompt_template="You are a {role_title}. Tools: {available_tools}",
            available_skills=[],
        )
        role_reg.register(role_def)
        assert role_reg.get(AIRole.ANALYST) is role_def

    def test_get_nonexistent_returns_none(self):
        skill_reg = SkillRegistry()
        role_reg = RoleRegistry(skill_reg)
        assert role_reg.get(AIRole.TRADER) is None

    def test_load_from_json(self, skills_json_path, roles_json_path):
        if not os.path.exists(roles_json_path):
            pytest.skip("roles.json not found")
        skill_reg = SkillRegistry()
        if os.path.exists(skills_json_path):
            skill_reg.load_from_json(skills_json_path)
        role_reg = RoleRegistry(skill_reg)
        role_reg.load_from_json(roles_json_path)
        assert len(role_reg.roles) > 0
        assert role_reg.get(AIRole.ANALYST) is not None

    def test_role_system_prompt_template(self):
        skill_reg = SkillRegistry()
        role_reg = RoleRegistry(skill_reg)
        role_def = RoleDefinition(
            name=AIRole.ANALYST,
            title="Gold Analyst",
            system_prompt_template="You are a {role_title}. Tools: {available_tools}",
            available_skills=[],
        )
        role_reg.register(role_def)
        prompt = role_def.get_system_prompt({
            "role_title": "Gold Analyst",
            "available_tools": "none",
        })
        assert "Gold Analyst" in prompt


# ─── PromptBuilder ───────────────────────────────────────────────────────────

class TestPromptBuilder:

    @pytest.fixture
    def builder(self, skills_json_path, roles_json_path):
        """Create a PromptBuilder with loaded configs (if available)."""
        skill_reg = SkillRegistry()
        if os.path.exists(skills_json_path):
            skill_reg.load_from_json(skills_json_path)

        role_reg = RoleRegistry(skill_reg)
        if os.path.exists(roles_json_path):
            role_reg.load_from_json(roles_json_path)
        else:
            # Fallback: register minimal analyst role
            role_reg.register(RoleDefinition(
                name=AIRole.ANALYST,
                title="Gold Analyst",
                system_prompt_template="You are a {role_title}. Tools: {available_tools}",
                available_skills=[],
            ))

        return PromptBuilder(role_reg, AIRole.ANALYST)

    def test_build_thought_returns_prompt_package(self, builder, sample_market_state):
        result = builder.build_thought(sample_market_state, [], 1)
        assert isinstance(result, PromptPackage)
        assert result.step_label == "THOUGHT_1"
        assert len(result.system) > 0
        assert len(result.user) > 0

    def test_build_thought_contains_market_data(self, builder, sample_market_state):
        result = builder.build_thought(sample_market_state, [], 1)
        assert "2300" in result.user  # spot price
        assert "RSI" in result.user

    def test_build_thought_contains_portfolio(self, builder, sample_market_state_with_portfolio):
        result = builder.build_thought(sample_market_state_with_portfolio, [], 1)
        assert "Portfolio" in result.user
        assert "1,500" in result.user or "1500" in result.user

    def test_build_final_decision_format(self, builder, sample_market_state):
        result = builder.build_final_decision(sample_market_state, [])
        assert isinstance(result, PromptPackage)
        assert result.step_label == "THOUGHT_FINAL"
        assert "FINAL_DECISION" in result.system or "final" in result.system.lower()

    def test_format_market_state_without_portfolio(self, builder, sample_market_state):
        text = builder._format_market_state(sample_market_state)
        assert "Gold:" in text or "2300" in text
        assert "Portfolio" not in text  # No portfolio key in this fixture

    def test_format_market_state_with_portfolio(self, builder, sample_market_state_with_portfolio):
        text = builder._format_market_state(sample_market_state_with_portfolio)
        assert "Portfolio" in text
        assert "can_buy" in text
        assert "can_sell" in text

    def test_build_thought_iteration_number(self, builder, sample_market_state):
        for i in [1, 3, 5]:
            result = builder.build_thought(sample_market_state, [], i)
            assert f"Iteration {i}" in result.user
            assert result.step_label == f"THOUGHT_{i}"
