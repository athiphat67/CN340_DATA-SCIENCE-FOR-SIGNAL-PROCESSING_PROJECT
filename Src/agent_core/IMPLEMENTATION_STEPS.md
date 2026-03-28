# ReAct Loop: Detailed Flow & Implementation Steps

---

## 📊 Detailed Flow Diagram (Text Version)

```
┌──────────────────────────────────────────────────────────────────┐
│                     INITIALIZATION                               │
│  (Happens ONCE at startup)                                       │
└────────────────┬─────────────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
    ┌───────────┐   ┌──────────────────────────┐
    │  Load A   │   │  Load C (Skills, Roles)  │
    │(LLM Client)   │                          │
    │           │   │  - SkillRegistry         │
    │ provider: │   │  - RoleRegistry          │
    │"gemini"   │   │  - PromptBuilder         │
    └─────┬─────┘   └────────┬─────────────────┘
          │                  │
          └────────┬─────────┘
                   │
                   ▼
          ┌──────────────────────┐
          │  Load B              │
          │(ReactOrchestrator)   │
          │  - inject A + C      │
          │  - inject tools      │
          │  - inject config     │
          └──────────┬───────────┘
                     │
                     ▼
         ┌────────────────────────────┐
         │  Pass market_state to loop │
         │  (JSON file or mock data)  │
         └────────────────┬───────────┘
                          │
                          ▼
                 ┌─────────────────────┐
                 │  START REACT LOOP   │
                 └────────────┬────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │  ITERATION N (while iteration < max)    │
        │                                         │
        │  1. THOUGHT: LLM analyzes               │
        │     ├─ PromptBuilder.build_thought()   │
        │     │   ├─ Apply role context          │
        │     │   ├─ Add available tools         │
        │     │   ├─ Add market state            │
        │     │   └─ Add previous results        │
        │     │                                  │
        │     └─ LLMClient.call(prompt)          │
        │        ├─ For Gemini: genai.generate   │
        │        ├─ For OpenAI: chat.completion  │
        │        ├─ For Claude: messages.create  │
        │        └─ For Mock: return preset JSON │
        │                                        │
        │  2. PARSE: Extract JSON from response  │
        │     ├─ Try direct JSON parse           │
        │     ├─ Try markdown code block         │
        │     └─ Try regex extraction            │
        │                                        │
        │  3. ACTION: Determine next step        │
        │     │                                  │
        │     ├─ action == "CALL_TOOL"?          │
        │     │  ├─ tool_call_count < max?       │
        │     │  │  ├─ YES: Continue to 4        │
        │     │  │  └─ NO: Fallback HOLD         │
        │     │  │                              │
        │     │  └─ tool_name = thought[...]    │
        │     │     tool_args = thought[...]    │
        │     │                                 │
        │     ├─ action == "FINAL_DECISION"?    │
        │     │  └─ Break loop, return decision │
        │     │                                 │
        │     └─ Else (unknown action)?         │
        │        └─ Fallback HOLD               │
        │                                       │
        │  4. OBSERVATION: Execute tool         │
        │     ├─ Check tool in registry         │
        │     ├─ Call: tools[tool_name](**args)│
        │     ├─ Catch exceptions → error obs   │
        │     └─ Append to tool_results[]       │
        │                                       │
        │  5. STORE: Append to react_trace      │
        │     ├─ step: "THOUGHT_N"              │
        │     ├─ response: parsed JSON          │
        │     ├─ tool_execution: if occurred    │
        │     └─ observation: if occurred       │
        │                                       │
        │  6. LOOP BACK to 1 (Thought)          │
        │                                       │
        └────────────────┬────────────────────┘
                         │
        ┌────────────────┴──────────────────┐
        ▼                                   ▼
    ┌──────────────────┐           ┌─────────────────┐
    │ Max iterations?  │           │ FINAL_DECISION? │
    │ Max tool calls?  │           │ error?          │
    │ Unknown action?  │           │                 │
    └────────┬─────────┘           └────────┬────────┘
             │                              │
             ▼                              ▼
         FALLBACK                      NORMAL RETURN
         HOLD signal                   with decision
             │                              │
             └──────────┬───────────────────┘
                        │
                        ▼
        ┌─────────────────────────────────────┐
        │  BUILD OUTPUT DICT:                 │
        │  {                                  │
        │    "final_decision": {...},         │
        │    "react_trace": [all steps],      │
        │    "iterations_used": 3,            │
        │    "tool_calls_used": 2,            │
        │  }                                  │
        └─────────────┬───────────────────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │  RETURN from loop    │
           │  (write JSON output) │
           └──────────────────────┘
```

---

## 🔍 Example Execution Trace

Suppose we call:
```python
result = orchestrator.run(market_state={
    "gold_price": 3025.40,
    "rsi": 28.5,
    "dxy": 103.72,
})
```

### Iteration 1: Thought 1

**Prompt Builder** creates:
```
SYSTEM:
You are a Market Analyst.
You have access to these tools: get_news, run_calculator
Analyze the market state and decide: CALL_TOOL or FINAL_DECISION

USER:
MARKET STATE:
- gold_price: 3025.40
- rsi: 28.5
- dxy: 103.72

PREVIOUS RESULTS:
(No results yet)

Respond in JSON format.
```

**LLM Response** (Gemini, Mock, etc.):
```json
{
  "thought": "RSI is 28.5 (oversold). Need more context from news about FED.",
  "action": "CALL_TOOL",
  "tool_name": "get_news",
  "tool_args": {
    "keywords": ["FED interest rate"],
    "max_results": 3
  }
}
```

**Action**: CALL_TOOL → move to Observation

**Tool Execution**:
- Call: `tools["get_news"](keywords=["FED interest rate"], max_results=3)`
- Result:
  ```python
  ToolResult(
    tool_name="get_news",
    status="success",
    data={
      "articles": [
        {"title": "FED hints rate cut", "sentiment": 0.72},
        ...
      ]
    }
  )
  ```

**React Trace Entry 1**:
```python
{
  "step": "THOUGHT_1",
  "iteration": 1,
  "response": {...}  # parsed JSON
}
```

**React Trace Entry 2**:
```python
{
  "step": "TOOL_EXECUTION",
  "iteration": 1,
  "tool_name": "get_news",
  "tool_args": {...},
  "observation": ToolResult(...)
}
```

**Loop Back** to Iteration 2

---

### Iteration 2: Thought 2

**tool_results** now has 1 item (from get_news)

**Prompt Builder** creates:
```
SYSTEM:
You are a Market Analyst...

USER:
MARKET STATE:
- gold_price: 3025.40
...

PREVIOUS RESULTS:
1. get_news: sentiment=0.72 (bullish), FED likely to cut rates

Respond in JSON format.
```

**LLM Response**:
```json
{
  "thought": "Bullish signals from FED + oversold RSI = good BUY setup",
  "action": "FINAL_DECISION",
  "signal": "BUY",
  "confidence": 0.82,
  "entry_price": 3025.40,
  "stop_loss": 2998.00,
  "take_profit": 3078.00,
  "rationale": "RSI oversold + FED dovish = bullish"
}
```

**Action**: FINAL_DECISION → BREAK LOOP

**React Trace Entry 3**:
```python
{
  "step": "THOUGHT_2",
  "iteration": 2,
  "response": {...}
}
```

---

### Final Output

```python
{
  "final_decision": {
    "signal": "BUY",
    "confidence": 0.82,
    "entry_price": 3025.40,
    "stop_loss": 2998.00,
    "take_profit": 3078.00,
    "rationale": "RSI oversold + FED dovish = bullish",
  },
  "react_trace": [
    {"step": "THOUGHT_1", ...},
    {"step": "TOOL_EXECUTION", ...},
    {"step": "THOUGHT_2", ...},
  ],
  "iterations_used": 2,
  "tool_calls_used": 1,
}
```

---

## 🛠️ Step-by-Step Implementation Order

### Phase 1: A (LLM Client) - 1-2 days

**File: `agent_core/llm/client.py`**

1. Define `PromptPackage` dataclass
2. Define `LLMClient` abstract base class with `call()` and `is_available()`
3. Implement `MockClient` first (easiest, for testing)
   - Return hardcoded responses based on step_label
4. Refactor existing `GeminiClient`
   - Keep existing logic, just make it inherit `LLMClient`
5. Implement `OpenAIClient` (copy-paste from docs, adapt)
6. Implement `ClaudeClient` (copy-paste from Anthropic docs)
7. Create `LLMClientFactory` with `create(provider, **kwargs)`

**Test**:
```python
# Test each client independently
mock_client = LLMClientFactory.create("mock")
response = mock_client.call(PromptPackage(system="...", user="...", step_label="THOUGHT_1"))
assert "HOLD" in response or "BUY" in response
```

---

### Phase 2: B (ReAct Loop) - 1-2 days

**File: `agent_core/core/react.py`**

1. Define `ToolResult`, `ReactState`, `ReactConfig` dataclasses
2. Define `ReactOrchestrator` class with:
   - `__init__(llm_client, prompt_builder, tool_registry, config)`
   - `run(market_state, initial_observation=None)` method
   - `_execute_tool(tool_name, tool_args)` helper
   - `_parse_response(raw_text)` helper
   - `_fallback_decision()` helper

3. Implement core loop:
   - While loop checking max iterations
   - Thought step: call `prompt_builder.build_thought()`
   - Parse response
   - Check action and decide next step
   - If CALL_TOOL: execute and append to tool_results
   - If FINAL_DECISION: break
   - Append to react_trace

**Test**:
```python
# Test with mock client and dummy tools
mock_llm = LLMClientFactory.create("mock")
mock_prompt = MockPromptBuilder()  # returns static prompts
orchestrator = ReactOrchestrator(mock_llm, mock_prompt, {}, ReactConfig())
result = orchestrator.run({"gold_price": 3000})
assert "final_decision" in result
assert "react_trace" in result
```

---

### Phase 3: C (Prompt System) - 1-2 days

**File: `agent_core/core/prompt.py`**

1. Define `Skill`, `RoleDefinition` dataclasses
2. Implement `SkillRegistry`:
   - `register(skill)`, `get(name)`, `load_from_json(filepath)`
3. Implement `RoleRegistry`:
   - `register(role)`, `get(role_name)`, `build_system_prompt(role, context)`
4. Implement `PromptBuilder`:
   - `__init__(role_registry, current_role)`
   - `build_thought(market_state, tool_results, iteration)`
   - `build_final_decision(market_state, tool_results)`
   - Helper methods for formatting

**Configuration Files**:
- Create `config/skills.json`:
  ```json
  {
    "skills": [
      {
        "name": "market_analysis",
        "description": "Analyze market trends",
        "tools": ["get_news", "run_calculator"]
      }
    ]
  }
  ```

**Test**:
```python
skill_reg = SkillRegistry()
skill_reg.load_from_json("config/skills.json")
role_reg = RoleRegistry(skill_reg)

builder = PromptBuilder(role_reg, AIRole.ANALYST)
prompt = builder.build_thought({"gold_price": 3000}, [], 1)
assert prompt.system  # Not empty
assert prompt.user    # Has market state
```

---

### Phase 4: Integration - 1 day

**File: `main.py` (update)**

1. Remove hardcoded `GeminiClient` class definition
2. Remove `_mock_response()` method
3. Import from new modules:
   ```python
   from agent_core.llm.client import LLMClientFactory
   from agent_core.core.react import ReactOrchestrator, ReactConfig
   from agent_core.core.prompt import SkillRegistry, RoleRegistry, PromptBuilder, AIRole
   ```
4. In `main()`:
   ```python
   # A
   llm = LLMClientFactory.create("gemini", use_mock=args.mock)
   
   # C
   skill_registry = SkillRegistry()
   skill_registry.load_from_json("config/skills.json")
   role_registry = RoleRegistry(skill_registry)
   prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)
   
   # B
   orchestrator = ReactOrchestrator(llm, prompt_builder, TOOL_REGISTRY, config)
   result = orchestrator.run(market_state)
   ```

---

## 🏗️ Directory Structure After Implementation

```
agent_core/
├── llm/
│   ├── __init__.py
│   └── client.py           ← A (LLM Client)
│       ├── PromptPackage
│       ├── LLMClient (base)
│       ├── GeminiClient
│       ├── OpenAIClient
│       ├── ClaudeClient
│       ├── MockClient
│       └── LLMClientFactory
│
├── core/
│   ├── __init__.py
│   ├── react.py            ← B (ReAct Loop)
│   │   ├── ToolResult
│   │   ├── ReactState
│   │   ├── ReactConfig
│   │   └── ReactOrchestrator
│   │
│   └── prompt.py           ← C (Prompt System)
│       ├── Skill
│       ├── RoleDefinition
│       ├── SkillRegistry
│       ├── RoleRegistry
│       └── PromptBuilder
│
├── config/
│   ├── skills.json
│   └── roles.json (optional)
│
└── tools/
    └── (existing tool implementations)

main.py                     ← Updated to use A + B + C
```

---

## 🔑 Key Points to Remember

### LLMClient Interface (A)
- **One method**: `call(PromptPackage) -> str`
- **Two implementations contract**:
  1. Real API calls (Gemini, OpenAI, Claude)
  2. Mock responses (for testing)
- **Factory pattern** for easy switching

### ReAct Loop (B)
- **Fully dependency-injected**: LLM, Prompt Builder, Tools all passed in
- **State machine**: Thought → Action → Observation → Repeat
- **No hardcoded providers or prompts**
- **Error handling**: Fallback to HOLD signal if anything fails

### Prompt System (C)
- **Role-aware**: Different prompts for Analyst vs Trader
- **Skill-based**: Tools available based on assigned skills
- **Templated**: Easy to change prompt format without touching code
- **Dynamic**: Can load new skills at runtime

### Integration
- **Bootstrap**:
  1. Create LLM client (A)
  2. Load skills & roles (C)
  3. Create ReAct orchestrator (B)
  4. Run loop
- **No circular dependencies**: A doesn't know B or C, B only injects them

---

## ⚠️ Common Pitfalls to Avoid

1. **A knows about B**: LLMClient should NOT import ReactOrchestrator
2. **B hardcodes prompts**: Inject prompt builder instead of creating inside
3. **C doesn't validate tools**: Always check tool exists before adding to available_tools
4. **Missing error handling**: Tool execution should catch ALL exceptions
5. **State not isolated**: Each iteration should have clean state copies
6. **Circular loop**: Missing "break on FINAL_DECISION" → infinite loop
7. **Tool registry empty**: Verify tools are registered before loop starts
8. **Max iterations 0**: Config should have sensible defaults

---

## ✅ Validation Checklist

After implementation:

- [ ] A: All 4 LLM clients implement same interface
- [ ] A: Factory creates instances correctly
- [ ] A: Mock client returns valid JSON
- [ ] B: Loop stops on FINAL_DECISION (not stuck)
- [ ] B: Tool execution catches errors gracefully
- [ ] B: react_trace has all iterations
- [ ] B: Falls back to HOLD on max iterations
- [ ] C: SkillRegistry loads from JSON without error
- [ ] C: RoleRegistry has at least 1 role registered
- [ ] C: PromptBuilder respects role context (different prompts for different roles)
- [ ] Integration: main.py creates A + B + C correctly
- [ ] Integration: End-to-end run produces valid output JSON
- [ ] Integration: Can switch providers without changing loop logic
