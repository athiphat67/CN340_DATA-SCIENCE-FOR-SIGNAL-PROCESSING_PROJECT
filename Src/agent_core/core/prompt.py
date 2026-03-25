# Skill
# RoleDefinition
# SkillRegistry
# RoleRegistry
# PromptBuilder

# --------------------------- guideline -------------------------
# from enum import Enum
# from typing import Optional
# from dataclasses import dataclass

# class AIRole(Enum):
#     """Role definitions ตัวบอกว่า AI เล่นบทบาทอะไร"""
#     ANALYST = "analyst"           # วิเคราะห์ข้อมูล
#     RISK_MANAGER = "risk_manager" # จัดการ risk
#     TRADER = "trader"             # ตัดสินใจซื้อขาย

# @dataclass
# class Skill:
#     """Definition ของ skill หนึ่ง"""
#     name: str                      # "market_analysis", "risk_assessment"
#     description: str               # อธิบายว่า skill นี้ทำอะไร
#     tools: list[str]               # ["get_news", "run_calculator"]
#     constraints: Optional[dict] = None  # {"max_calls": 3}
    
#     def to_prompt_text(self) -> str:
#         """แปลง skill เป็น text สำหรับ prompt"""
#         tools_str = ", ".join(self.tools)
#         return f"- {self.name}: {self.description}\n  Available tools: {tools_str}"

# @dataclass
# class RoleDefinition:
#     """Definition ของ role หนึ่ง"""
#     name: AIRole
#     title: str                     # "Market Analyst"
#     system_prompt_template: str    # Template สำหรับ system message
#     available_skills: list[str]    # ["market_analysis", "risk_assessment"]
    
#     def get_system_prompt(self, context: dict) -> str:
#         """
#         Generate system prompt สำหรับ role นี้
#         context: dict ที่มี {role_title, available_tools, ...}
#         """
#         return self.system_prompt_template.format(**context)

# class SkillRegistry:
#     """
#     เก็บรวม skill definitions
#     สามารถ load from JSON, add dynamically, etc.
#     """
    
#     def __init__(self):
#         self.skills: dict[str, Skill] = {}
    
#     def register(self, skill: Skill) -> None:
#         """Register new skill"""
#         self.skills[skill.name] = skill
    
#     def get(self, name: str) -> Optional[Skill]:
#         """Get skill by name"""
#         return self.skills.get(name)
    
#     def get_tools_for_skills(self, skill_names: list[str]) -> list[str]:
#         """
#         ให้ list skill names → return list of tools
#         """
#         tools = set()
#         for name in skill_names:
#             skill = self.get(name)
#             if skill:
#                 tools.update(skill.tools)
#         return list(tools)
    
#     def load_from_json(self, filepath: str) -> None:
#         """Load skills from JSON file"""
#         import json
#         with open(filepath) as f:
#             data = json.load(f)
#             for skill_data in data.get("skills", []):
#                 skill = Skill(**skill_data)
#                 self.register(skill)

# class RoleRegistry:
#     """
#     เก็บรวม role definitions
#     """
    
#     def __init__(self, skill_registry: SkillRegistry):
#         self.roles: dict[AIRole, RoleDefinition] = {}
#         self.skills = skill_registry
    
#     def register(self, role_def: RoleDefinition) -> None:
#         """Register new role"""
#         self.roles[role_def.name] = role_def
    
#     def get(self, role: AIRole) -> Optional[RoleDefinition]:
#         """Get role definition"""
#         return self.roles.get(role)
    
#     def build_system_prompt(self, role: AIRole, context: dict) -> str:
#         """
#         Build system prompt สำหรับ role
#         context: ข้อมูล เช่น available_tools, market_state, ...
#         """
#         role_def = self.get(role)
#         if not role_def:
#             raise ValueError(f"Role {role} not found")
        
#         return role_def.get_system_prompt(context)

# class PromptBuilder:
#     """
#     Main class ที่ react loop ใช้เพื่อ build prompts
    
#     วิธีใช้:
#         builder = PromptBuilder(role_registry, current_role)
#         prompt = builder.build_thought(market_state, tool_results)
#     """
    
#     def __init__(
#         self,
#         role_registry: RoleRegistry,
#         current_role: AIRole,
#     ):
#         self.roles = role_registry
#         self.role = current_role
    
#     def build_thought(
#         self,
#         market_state: dict,
#         tool_results: list[dict],
#         iteration: int,
#     ) -> PromptPackage:
#         """
#         Build prompt สำหรับ "Thought" step
        
#         Returns:
#             PromptPackage(system, user, step_label)
#         """
#         # Get role definition
#         role_def = self.roles.get(self.role)
        
#         # Build context
#         context = {
#             "role_title": role_def.title,
#             "available_tools": self._format_tools(),
#             "iteration": iteration,
#         }
        
#         # Build system prompt from template
#         system_prompt = role_def.get_system_prompt(context)
        
#         # Build user prompt
#         user_prompt = f"""
# MARKET STATE:
# {self._format_market_state(market_state)}

# PREVIOUS RESULTS:
# {self._format_tool_results(tool_results)}

# TASK:
# You are a {role_def.title}. Analyze the market state and either:
# 1. Call a tool to gather more information
# 2. Make a FINAL_DECISION

# Respond in JSON format with 'action' and other relevant fields.
# """
        
#         return PromptPackage(
#             system=system_prompt,
#             user=user_prompt,
#             step_label=f"THOUGHT_{iteration}",
#         )
    
#     def build_final_decision(
#         self,
#         market_state: dict,
#         tool_results: list[dict],
#     ) -> PromptPackage:
#         """Build prompt สำหรับ final decision step"""
#         role_def = self.roles.get(self.role)
        
#         system_prompt = f"""
# You are a {role_def.title}. 
# Make a final trading decision based on all available information.
# Return JSON with: action, signal (BUY/SELL/HOLD), confidence, rationale.
# """
        
#         user_prompt = f"""
# MARKET STATE:
# {self._format_market_state(market_state)}

# ANALYSIS RESULTS:
# {self._format_tool_results(tool_results)}

# Make your FINAL_DECISION now.
# """
        
#         return PromptPackage(
#             system=system_prompt,
#             user=user_prompt,
#             step_label="THOUGHT_FINAL",
#         )
    
#     def _format_market_state(self, state: dict) -> str:
#         """Format market state for prompt"""
#         return "\n".join(f"- {k}: {v}" for k, v in state.items())
    
#     def _format_tool_results(self, results: list[dict]) -> str:
#         """Format tool results for prompt"""
#         if not results:
#             return "(No results yet)"
#         return "\n".join(str(r) for r in results)
    
#     def _format_tools(self) -> str:
#         """Format available tools for this role"""
#         # ใช้ role_def.available_skills เพื่อ get tools
#         role_def = self.roles.get(self.role)
#         tools = self.roles.skills.get_tools_for_skills(role_def.available_skills)
#         return ", ".join(tools)