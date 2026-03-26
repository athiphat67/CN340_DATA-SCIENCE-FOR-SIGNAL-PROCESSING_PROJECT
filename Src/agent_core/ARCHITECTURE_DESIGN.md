# LLM ReAct Orchestrator - Architecture Design
## A, B, C แบ่งหน้าที่ชัดเจน

---

## 📋 Overview

โปรเจค goldtrader ต้องการแบ่งความ responsibility ออกเป็น 3 ส่วนหลัก:

- **A: LLM Client** - ให้ยืดหยุ่นรับหลาย AI providers
- **B: ReAct Loop** - Orchestration logic สำหรับ thought→action→observation
- **C: Prompt & Role System** - Template, role definitions, skill management

---

# 🔵 PART A: LLM Client (Provider Abstraction)

## 🎯 Purpose
สร้าง abstract interface ที่ให้ react loop เรียก LLM ได้โดยไม่รู้ว่ามันเป็น Gemini / OpenAI / Claude / Mock

## 📦 Class Structure

```python
from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass

@dataclass
class PromptPackage:
    """ข้อมูล prompt ที่ common ทุก provider"""
    system: str              # System instructions
    user: str                # User message
    step_label: str          # Label สำหรับ step (e.g. "THOUGHT_1")
    
class LLMClient(ABC):
    """Base class สำหรับ LLM providers"""
    
    @abstractmethod
    def call(self, prompt_package: PromptPackage) -> str:
        """
        Call LLM และ return raw text response
        - Input: PromptPackage (system + user + step_label)
        - Output: JSON string (expected)
        - Raises: LLMException if error
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """ตรวจสอบว่า LLM พร้อมใช้งาน (API key, connection)"""
        pass
```

## 🔧 Implementations Required

### 1. GeminiClient (ปรับปรุงเดิม)
```python
class GeminiClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None, use_mock: bool = False):
        self.use_mock = use_mock
        if not use_mock:
            from google import genai
            self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
    
    def call(self, prompt_package: PromptPackage) -> str:
        if self.use_mock:
            return self._mock_response(prompt_package)
        
        full_prompt = f"SYSTEM:\n{prompt_package.system}\n\nUSER:\n{prompt_package.user}"
        response = self._client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt
        )
        return response.text
    
    def is_available(self) -> bool:
        if self.use_mock:
            return True
        try:
            # Quick API test
            return self._client is not None
        except:
            return False
    
    def _mock_response(self, prompt: PromptPackage) -> str:
        # ใช้ step_label เพื่อ return mock response ที่เหมาะสม
        # (เก็บเดิมจาก main.py)
        ...
```

### 2. OpenAIClient (ใหม่)
```python
class OpenAIClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4-turbo"):
        from openai import OpenAI
        self.model = model
        self._client = OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])
    
    def call(self, prompt_package: PromptPackage) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": prompt_package.system},
                {"role": "user", "content": prompt_package.user},
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content
    
    def is_available(self) -> bool:
        try:
            return self._client is not None
        except:
            return False
```

### 3. ClaudeClient (ใหม่)
```python
class ClaudeClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-opus-4-1"):
        from anthropic import Anthropic
        self.model = model
        self._client = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
    
    def call(self, prompt_package: PromptPackage) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=prompt_package.system,
            messages=[
                {"role": "user", "content": prompt_package.user},
            ],
        )
        return response.content[0].text
    
    def is_available(self) -> bool:
        try:
            return self._client is not None
        except:
            return False
```

### 4. MockClient (ใหม่ - สำหรับ testing)
```python
class MockClient(LLMClient):
    def __init__(self, response_map: Optional[dict] = None):
        """
        response_map: dict mapping step_label → mock response
        ถ้า None ให้ใช้ defaults
        """
        self.response_map = response_map or DEFAULT_MOCK_RESPONSES
    
    def call(self, prompt_package: PromptPackage) -> str:
        return self.response_map.get(
            prompt_package.step_label,
            '{"action": "FINAL_DECISION", "signal": "HOLD"}'
        )
    
    def is_available(self) -> bool:
        return True
```

## 🏭 Factory Pattern

```python
class LLMClientFactory:
    """สร้าง LLM client ตามชื่อ provider"""
    
    @staticmethod
    def create(provider: str, **kwargs) -> LLMClient:
        """
        provider: "gemini", "openai", "claude", "mock"
        kwargs: api_key, model, use_mock เป็นต้น
        """
        providers = {
            "gemini": GeminiClient,
            "openai": OpenAIClient,
            "claude": ClaudeClient,
            "mock": MockClient,
        }
        
        if provider not in providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        return providers[provider](**kwargs)
```

## 📍 Location & Interface
- **File**: `agent_core/llm/client.py`
- **Base class**: `LLMClient`
- **Factory**: `LLMClientFactory.create(provider_name)`
- **Input**: `PromptPackage(system, user, step_label)`
- **Output**: `str` (JSON)

---

# 🟠 PART B: ReAct Loop (Orchestration)

## 🎯 Purpose
สร้าง loop ที่ไม่รู้ provider นั้น คือ Gemini / OpenAI / Claude
และไม่รู้ prompt builder คืออะไร ให้ dependency injection แล้ว request ตัวแปร

## 📦 Class Structure

```python
from typing import Callable, Any, Optional
from dataclasses import dataclass

@dataclass
class ToolResult:
    """Result จากการ execute tool"""
    tool_name: str
    status: str              # "success" or "error"
    data: dict              # ข้อมูลจาก tool
    error: Optional[str] = None

@dataclass
class ReactState:
    """State ที่เปลี่ยนไปใน loop"""
    market_state: dict
    tool_results: list[ToolResult]  # accumulated results
    iteration: int
    tool_call_count: int
    react_trace: list[dict]         # เก็บ trace ทุก step

class ReactOrchestrator:
    """
    Main orchestrator สำหรับ ReAct loop
    
    Design: fully dependency-injected
    - LLM client ส่งเข้ามา (A)
    - Prompt builder ส่งเข้ามา (C)
    - Tool registry ส่งเข้ามา
    - Config ส่งเข้ามา
    """
    
    def __init__(
        self,
        llm_client: LLMClient,                    # from A
        prompt_builder: "PromptBuilder",          # from C
        tool_registry: dict[str, Callable],
        config: ReactConfig,
    ):
        self.llm = llm_client
        self.prompt_builder = prompt_builder
        self.tools = tool_registry
        self.config = config
    
    def run(
        self,
        market_state: dict,
        initial_observation: Optional[ToolResult] = None,
    ) -> dict:
        """
        Run เต็มๆ ReAct loop
        
        Returns:
            {
                "final_decision": {...},
                "react_trace": [...],
                "iterations_used": int,
                "tool_calls_used": int,
            }
        """
        state = ReactState(
            market_state=market_state,
            tool_results=[initial_observation] if initial_observation else [],
            iteration=0,
            tool_call_count=0,
            react_trace=[],
        )
        
        final_decision = None
        
        while state.iteration < self.config.max_iterations:
            state.iteration += 1
            
            # STEP 1: Thought - LLM analyzes
            prompt = self.prompt_builder.build_thought(
                state.market_state,
                state.tool_results,
                state.iteration,
            )
            response = self.llm.call(prompt)
            thought = self._parse_response(response)
            
            state.react_trace.append({
                "step": "THOUGHT",
                "iteration": state.iteration,
                "response": thought,
            })
            
            # STEP 2: Action - ตัดสินใจว่าทำอะไร
            action = thought.get("action")  # "CALL_TOOL" or "FINAL_DECISION"
            
            if action == "FINAL_DECISION":
                final_decision = thought
                break
            
            elif action == "CALL_TOOL":
                if state.tool_call_count >= self.config.max_tool_calls:
                    # Max tool calls reached
                    final_decision = self._fallback_decision()
                    break
                
                # STEP 3: Observation - Execute tool
                tool_name = thought.get("tool_name")
                tool_args = thought.get("tool_args", {})
                
                observation = self._execute_tool(tool_name, tool_args)
                state.tool_results.append(observation)
                state.tool_call_count += 1
                
                state.react_trace.append({
                    "step": "TOOL_EXECUTION",
                    "iteration": state.iteration,
                    "tool_name": tool_name,
                    "observation": observation,
                })
                
                # Loop back to Thought
                continue
            
            else:
                # Unknown action
                final_decision = self._fallback_decision()
                break
        
        # STEP 4: Build output
        return {
            "final_decision": final_decision or self._fallback_decision(),
            "react_trace": state.react_trace,
            "iterations_used": state.iteration,
            "tool_calls_used": state.tool_call_count,
        }
    
    def _execute_tool(self, tool_name: str, tool_args: dict) -> ToolResult:
        """
        Execute tool จาก registry
        
        Returns:
            ToolResult with status, data, error
        """
        if tool_name not in self.tools:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                data={},
                error=f"Tool '{tool_name}' not found",
            )
        
        try:
            result = self.tools[tool_name](**tool_args)
            return ToolResult(
                tool_name=tool_name,
                status="success",
                data=result,
            )
        except Exception as e:
            return ToolResult(
                tool_name=tool_name,
                status="error",
                data={},
                error=str(e),
            )
    
    def _parse_response(self, raw_response: str) -> dict:
        """ใช้ extract_json จาก utils"""
        return extract_json(raw_response)
    
    def _fallback_decision(self) -> dict:
        """Return HOLD signal as fallback"""
        return {
            "action": "FINAL_DECISION",
            "signal": "HOLD",
            "confidence": 0.0,
        }

@dataclass
class ReactConfig:
    """Config สำหรับ ReAct loop"""
    max_iterations: int = 10
    max_tool_calls: int = 5
    timeout_seconds: Optional[int] = None
```

## 🔄 ReAct Loop Flow

```
┌─────────────────────────────────────────────────────┐
│                  START                              │
│          (market_state, initial observation?)       │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  iteration < max?   │
        └────┬───────────┬────┘
             │ NO        │ YES
             ▼           ▼
         RETURN      ┌──────────────────────┐
                     │  Thought             │
                     │  (LLM call)          │
                     │  PromptBuilder       │
                     │  → response          │
                     └──────────┬───────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Parse action from     │
                    │  LLM response          │
                    └─┬──────────────────────┘
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
   TOOL_CALL   FINAL_DECISION   ERROR/UNKNOWN
       │              │              │
       ▼              ▼              ▼
   Observation   RETURN          FALLBACK
   (Execute)      DECISION        DECISION
       │
       └─────────────────┐
                         │
            ┌────────────▼────────────┐
            │  Accumulate result      │
            │  to tool_results        │
            └────────────┬────────────┘
                         │
                         │ ┌─────────────────────┐
                         └─│ Loop back to Thought│
                           └─────────────────────┘
```

## 📍 Location & Interface
- **File**: `agent_core/core/react.py`
- **Main class**: `ReactOrchestrator`
- **Input**:
  - `llm_client`: LLMClient instance (from A)
  - `prompt_builder`: PromptBuilder instance (from C)
  - `tool_registry`: dict[str, Callable]
  - `market_state`: dict
- **Output**:
  ```python
  {
      "final_decision": dict,
      "react_trace": list[dict],
      "iterations_used": int,
      "tool_calls_used": int,
  }
  ```

---

# 🔴 PART C: Prompt & Role System

## 🎯 Purpose
จัดการ prompt templates, role definitions, skills
ทำให้ง่ายต่อการสร้าง prompt ที่ context-aware กับ role และ available skills

## 📦 Class Structure

```python
from enum import Enum
from typing import Optional
from dataclasses import dataclass

class AIRole(Enum):
    """Role definitions ตัวบอกว่า AI เล่นบทบาทอะไร"""
    ANALYST = "analyst"           # วิเคราะห์ข้อมูล
    RISK_MANAGER = "risk_manager" # จัดการ risk
    TRADER = "trader"             # ตัดสินใจซื้อขาย

@dataclass
class Skill:
    """Definition ของ skill หนึ่ง"""
    name: str                      # "market_analysis", "risk_assessment"
    description: str               # อธิบายว่า skill นี้ทำอะไร
    tools: list[str]               # ["get_news", "run_calculator"]
    constraints: Optional[dict] = None  # {"max_calls": 3}
    
    def to_prompt_text(self) -> str:
        """แปลง skill เป็น text สำหรับ prompt"""
        tools_str = ", ".join(self.tools)
        return f"- {self.name}: {self.description}\n  Available tools: {tools_str}"

@dataclass
class RoleDefinition:
    """Definition ของ role หนึ่ง"""
    name: AIRole
    title: str                     # "Market Analyst"
    system_prompt_template: str    # Template สำหรับ system message
    available_skills: list[str]    # ["market_analysis", "risk_assessment"]
    
    def get_system_prompt(self, context: dict) -> str:
        """
        Generate system prompt สำหรับ role นี้
        context: dict ที่มี {role_title, available_tools, ...}
        """
        return self.system_prompt_template.format(**context)

class SkillRegistry:
    """
    เก็บรวม skill definitions
    สามารถ load from JSON, add dynamically, etc.
    """
    
    def __init__(self):
        self.skills: dict[str, Skill] = {}
    
    def register(self, skill: Skill) -> None:
        """Register new skill"""
        self.skills[skill.name] = skill
    
    def get(self, name: str) -> Optional[Skill]:
        """Get skill by name"""
        return self.skills.get(name)
    
    def get_tools_for_skills(self, skill_names: list[str]) -> list[str]:
        """
        ให้ list skill names → return list of tools
        """
        tools = set()
        for name in skill_names:
            skill = self.get(name)
            if skill:
                tools.update(skill.tools)
        return list(tools)
    
    def load_from_json(self, filepath: str) -> None:
        """Load skills from JSON file"""
        import json
        with open(filepath) as f:
            data = json.load(f)
            for skill_data in data.get("skills", []):
                skill = Skill(**skill_data)
                self.register(skill)

class RoleRegistry:
    """
    เก็บรวม role definitions
    """
    
    def __init__(self, skill_registry: SkillRegistry):
        self.roles: dict[AIRole, RoleDefinition] = {}
        self.skills = skill_registry
    
    def register(self, role_def: RoleDefinition) -> None:
        """Register new role"""
        self.roles[role_def.name] = role_def
    
    def get(self, role: AIRole) -> Optional[RoleDefinition]:
        """Get role definition"""
        return self.roles.get(role)
    
    def build_system_prompt(self, role: AIRole, context: dict) -> str:
        """
        Build system prompt สำหรับ role
        context: ข้อมูล เช่น available_tools, market_state, ...
        """
        role_def = self.get(role)
        if not role_def:
            raise ValueError(f"Role {role} not found")
        
        return role_def.get_system_prompt(context)

class PromptBuilder:
    """
    Main class ที่ react loop ใช้เพื่อ build prompts
    
    วิธีใช้:
        builder = PromptBuilder(role_registry, current_role)
        prompt = builder.build_thought(market_state, tool_results)
    """
    
    def __init__(
        self,
        role_registry: RoleRegistry,
        current_role: AIRole,
    ):
        self.roles = role_registry
        self.role = current_role
    
    def build_thought(
        self,
        market_state: dict,
        tool_results: list[dict],
        iteration: int,
    ) -> PromptPackage:
        """
        Build prompt สำหรับ "Thought" step
        
        Returns:
            PromptPackage(system, user, step_label)
        """
        # Get role definition
        role_def = self.roles.get(self.role)
        
        # Build context
        context = {
            "role_title": role_def.title,
            "available_tools": self._format_tools(),
            "iteration": iteration,
        }
        
        # Build system prompt from template
        system_prompt = role_def.get_system_prompt(context)
        
        # Build user prompt
        user_prompt = f"""
MARKET STATE:
{self._format_market_state(market_state)}

PREVIOUS RESULTS:
{self._format_tool_results(tool_results)}

TASK:
You are a {role_def.title}. Analyze the market state and either:
1. Call a tool to gather more information
2. Make a FINAL_DECISION

Respond in JSON format with 'action' and other relevant fields.
"""
        
        return PromptPackage(
            system=system_prompt,
            user=user_prompt,
            step_label=f"THOUGHT_{iteration}",
        )
    
    def build_final_decision(
        self,
        market_state: dict,
        tool_results: list[dict],
    ) -> PromptPackage:
        """Build prompt สำหรับ final decision step"""
        role_def = self.roles.get(self.role)
        
        system_prompt = f"""
You are a {role_def.title}. 
Make a final trading decision based on all available information.
Return JSON with: action, signal (BUY/SELL/HOLD), confidence, rationale.
"""
        
        user_prompt = f"""
MARKET STATE:
{self._format_market_state(market_state)}

ANALYSIS RESULTS:
{self._format_tool_results(tool_results)}

Make your FINAL_DECISION now.
"""
        
        return PromptPackage(
            system=system_prompt,
            user=user_prompt,
            step_label="THOUGHT_FINAL",
        )
    
    def _format_market_state(self, state: dict) -> str:
        """Format market state for prompt"""
        return "\n".join(f"- {k}: {v}" for k, v in state.items())
    
    def _format_tool_results(self, results: list[dict]) -> str:
        """Format tool results for prompt"""
        if not results:
            return "(No results yet)"
        return "\n".join(str(r) for r in results)
    
    def _format_tools(self) -> str:
        """Format available tools for this role"""
        # ใช้ role_def.available_skills เพื่อ get tools
        role_def = self.roles.get(self.role)
        tools = self.roles.skills.get_tools_for_skills(role_def.available_skills)
        return ", ".join(tools)
```

## 📄 Configuration Files (JSON)

### `skills.json`
```json
{
  "skills": [
    {
      "name": "market_analysis",
      "description": "Analyze market conditions and trends",
      "tools": ["get_news", "run_calculator"],
      "constraints": {"max_calls": 2}
    },
    {
      "name": "risk_assessment",
      "description": "Assess trading risks",
      "tools": ["run_calculator"],
      "constraints": null
    }
  ]
}
```

### `roles.json` (or hardcoded in Python)
```json
{
  "roles": [
    {
      "name": "analyst",
      "title": "Market Analyst",
      "available_skills": ["market_analysis"],
      "system_prompt_template": "You are a {role_title}..."
    }
  ]
}
```

## 🔧 Initialization Example

```python
# Setup
skill_registry = SkillRegistry()
skill_registry.load_from_json("skills.json")

role_registry = RoleRegistry(skill_registry)
# Register roles...

# Create prompt builder
prompt_builder = PromptBuilder(
    role_registry=role_registry,
    current_role=AIRole.ANALYST,
)

# Use in ReAct loop
orchestrator = ReactOrchestrator(
    llm_client=llm,
    prompt_builder=prompt_builder,
    tool_registry=TOOL_REGISTRY,
    config=ReactConfig(max_iterations=10),
)

result = orchestrator.run(market_state)
```

## 📍 Location & Interface
- **File**: `agent_core/core/prompt.py`
- **Main classes**:
  - `SkillRegistry` - manages skills
  - `RoleRegistry` - manages roles
  - `PromptBuilder` - builds prompts
- **Output**: `PromptPackage(system, user, step_label)`

---

# 🔗 Integration Flow

## Sequence: Initialize → Run → Output

```
1. INITIALIZE
   │
   ├─ Create LLMClient via Factory (A)
   │  └─ LLMClientFactory.create("gemini", use_mock=True)
   │
   ├─ Load Skills & Roles (C)
   │  ├─ SkillRegistry.load_from_json("skills.json")
   │  └─ RoleRegistry.register(role_definitions)
   │
   └─ Create PromptBuilder (C)
      └─ PromptBuilder(role_registry, AIRole.ANALYST)

2. RUN LOOP (B)
   │
   ├─ ReactOrchestrator(llm_client, prompt_builder, tools, config)
   │
   └─ orchestrator.run(market_state)
      │
      └─ Loop:
         │
         ├─ Thought:
         │  ├─ prompt_builder.build_thought(...)
         │  │  └─ Returns PromptPackage with role-aware system msg
         │  │
         │  └─ llm_client.call(prompt_package)
         │     └─ Calls Gemini/OpenAI/Claude
         │
         ├─ Action:
         │  ├─ CALL_TOOL
         │  │  ├─ orchestrator._execute_tool(...)
         │  │  └─ Loop back to Thought
         │  │
         │  └─ FINAL_DECISION
         │     └─ Break and return

3. OUTPUT
   └─ {
        "final_decision": {...},
        "react_trace": [...],
        "iterations_used": 3,
        "tool_calls_used": 2,
      }
```

---

# 🎯 Key Design Principles

## 1. Separation of Concerns
- **A (LLM Client)**: Only knows how to call API
- **B (ReAct Loop)**: Only knows how to orchestrate and loop
- **C (Prompt System)**: Only knows how to build prompts

## 2. Dependency Injection
- B ไม่ hardcode A หรือ C
- ส่งเข้ามาเป็น constructor parameters
- ทำให้ง่ายต่อ testing และ swapping implementations

## 3. Extensibility
- สามารถ add new LLM provider ได้โดยสร้าง class extends `LLMClient`
- สามารถ add new role/skill ได้โดย register ในะ registry
- Loop logic ไม่เปลี่ยน

## 4. Configuration
- ทุกตัวแปร (API keys, model names, role definitions) ไม่ hardcode ใน code
- อ่านจาก env vars, JSON files, config classes

---

# 📝 Development Checklist

## A: LLM Client
- [ ] Create `LLMClient` base class with `call()` method
- [ ] Implement `GeminiClient` (ปรับปรุง)
- [ ] Implement `OpenAIClient`
- [ ] Implement `ClaudeClient`
- [ ] Implement `MockClient` (reuse from main.py logic)
- [ ] Create `LLMClientFactory`
- [ ] Test each provider individually

## B: ReAct Loop
- [ ] Create `ReactOrchestrator` class
- [ ] Implement loop logic (thought→action→observation)
- [ ] Implement tool execution
- [ ] Implement error handling and fallback
- [ ] Create `ReactConfig` dataclass
- [ ] Test with mock client

## C: Prompt System
- [ ] Create `Skill`, `RoleDefinition`, `SkillRegistry`, `RoleRegistry` classes
- [ ] Create `PromptBuilder` class with templates
- [ ] Create `skills.json` configuration
- [ ] Implement template rendering with context
- [ ] Test prompt generation for different roles

## Integration
- [ ] Update `main.py` to use new A + B + C
- [ ] Remove hardcoded GeminiClient from main
- [ ] Remove hardcoded _mock_response logic
- [ ] Run end-to-end tests

---

# 💡 Example Usage (New main.py)

```python
from agent_core.llm.client import LLMClientFactory
from agent_core.core.react import ReactOrchestrator, ReactConfig
from agent_core.core.prompt import SkillRegistry, RoleRegistry, PromptBuilder, AIRole

# A: Create LLM Client
llm = LLMClientFactory.create("gemini", use_mock=True)

# C: Setup Prompt System
skill_registry = SkillRegistry()
skill_registry.load_from_json("config/skills.json")

role_registry = RoleRegistry(skill_registry)
# ... register roles ...

prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)

# B: Create ReAct Loop
orchestrator = ReactOrchestrator(
    llm_client=llm,
    prompt_builder=prompt_builder,
    tool_registry=TOOL_REGISTRY,
    config=ReactConfig(max_iterations=10, max_tool_calls=5),
)

# Run
result = orchestrator.run(market_state)
```

---

## Summary

| Component | A (LLM) | B (ReAct) | C (Prompt) |
|-----------|---------|----------|-----------|
| **Purpose** | Abstract LLM provider | Orchestrate loop | Manage prompts & roles |
| **Classes** | `LLMClient`, `GeminiClient`, `OpenAIClient`, `ClaudeClient`, `MockClient` | `ReactOrchestrator`, `ReactState`, `ToolResult` | `SkillRegistry`, `RoleRegistry`, `PromptBuilder` |
| **Key Method** | `call(PromptPackage)` | `run(market_state)` | `build_thought(...)`, `build_final_decision(...)` |
| **Input** | `PromptPackage` | `market_state, llm, prompts, tools` | Role, skills, context |
| **Output** | `str` (JSON) | `dict` with decision + trace | `PromptPackage` |
| **File** | `agent_core/llm/client.py` | `agent_core/core/react.py` | `agent_core/core/prompt.py` |
