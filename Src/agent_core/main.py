# --------------------------- guideline main ---------------------

from agent_core.llm.client import LLMClientFactory
# from agent_core.core.react import ReactOrchestrator, ReactConfig
# from agent_core.core.prompt import SkillRegistry, RoleRegistry, PromptBuilder, AIRole

# A: Create LLM Client
# ถ้าอยากใช้ Ai agent เปลี่ยน "use_mock = False" ระวังเรื่อง token
# llm = LLMClientFactory.create("gemini", use_mock=True)

# C: Setup Prompt System
# skill_registry = SkillRegistry()
# skill_registry.load_from_json("config/skills.json")

# role_registry = RoleRegistry(skill_registry)
# ... register roles ...

# prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)

# B: Create ReAct Loop
# orchestrator = ReactOrchestrator(
#     llm_client=llm,
#     prompt_builder=prompt_builder,
#     tool_registry=TOOL_REGISTRY,
#     config=ReactConfig(max_iterations=10, max_tool_calls=5),
# )

# Run
# result = orchestrator.run(market_state)