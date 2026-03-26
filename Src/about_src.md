# goldtrader Agent Architecture

## Overview
**ReAct+LLM trading agent** for gold market analysis. 3-module design:
- **Data Engine**: Fetch + compute (orchestrator.py)
- **Agent Core**: LLM reasoning + prompt building
- **LLM Clients**: Multi-provider abstraction (Gemini, Claude, OpenAI, Groq, DeepSeek)

---

## Key Components

### 1. **Data Pipeline** (data_engine/)
```
fetcher.py + indicators.py + newsfetcher.py → orchestrator.py → latest.json
```
**GoldTradingOrchestrator** assembles:
- Market data (spot USD, USD/THB forex, Thai gold THB)
- Technical indicators (RSI, MACD, Bollinger, ATR, Trend)
- News (by category: gold, forex, commodities)

**Outputs**: JSON payload w/ `meta`, `market_data`, `technical_indicators`, `news`

---

### 2. **Agent Core** (agent_core/)

#### A. **LLMClient** (llm/client.py)
Abstract factory for multi-provider support:
- **GeminiClient**: Google Gemini API (default: `gemini-2.5-flash`)
- **OpenAIClient**: OpenAI GPT (default: `gpt-4o-mini`)
- **ClaudeClient**: Anthropic Claude (default: `claude-opus-4-1`)
- **GroqClient**: Groq LPU (default: `llama-3.3-70b-versatile`)
- **DeepSeekClient**: DeepSeek API
- **MockClient**: Testing (no API call)

**Interface**:
```python
client = LLMClientFactory.create("gemini")  # or "claude", "openai", "groq", "deepseek", "mock"
response = client.call(PromptPackage(system="...", user="...", step_label="THOUGHT_1"))
```

#### B. **PromptBuilder** (core/prompt.py)
Generates ReAct prompts:
- **Thought**: Step-by-step reasoning → JSON action
- **Final Decision**: BUY/SELL/HOLD w/ confidence, entry, stop_loss, take_profit

**Registries**:
- `SkillRegistry`: Load from `skills.json` → `get_tools_for_skills()`
- `RoleRegistry`: Load from `roles.json` → get system prompts

#### C. **ReactOrchestrator** (core/react.py)
ReAct loop: Thought → Action → Observation → repeat
- Max iterations: configurable
- Tool execution: registry-based
- State machine: tracks iterations, tool calls, react_trace

**Returns**:
```json
{
  "final_decision": {
    "signal": "BUY|SELL|HOLD",
    "confidence": 0.0-1.0,
    "entry_price": null|float,
    "stop_loss": null|float,
    "take_profit": null|float,
    "rationale": "string"
  },
  "react_trace": [{"step": "...", "iteration": N, "response": {...}}, ...],
  "iterations_used": int,
  "tool_calls_used": int
}
```

---

### 3. **Configuration** (agent_core/config/)

**roles.json**
```json
{
  "roles": [
    {
      "name": "analyst",
      "title": "Gold Market Analyst",
      "available_skills": ["market_analysis"],
      "system_prompt_template": "You are a {role_title}..."
    },
    {
      "name": "risk_manager",
      "title": "Risk Manager",
      "available_skills": ["risk_assessment"],
      "system_prompt_template": "..."
    }
  ]
}
```

**skills.json**
```json
{
  "skills": [
    {
      "name": "market_analysis",
      "description": "Analyze market conditions and trends",
      "tools": ["get_news", "run_calculator"],
      "constraints": {"max_calls": 2}
    }
  ]
}
```

---

## Workflow

### Entry Point: main.py
```bash
python main.py --provider gemini                    # Fetch fresh + run agent
python main.py --provider groq --skip-fetch         # Use cached data
python main.py --iterations 10 --output result.json # Custom output
```

**Flow**:
1. **Data fetch** (GoldTradingOrchestrator) → agent_core/data/latest.json
2. **Load config** (skills.json, roles.json)
3. **Create LLM client** (LLMClientFactory)
4. **Run ReAct loop** (ReactOrchestrator.run())
5. **Save result** (JSON to Output/)

---

## Class Hierarchy

```
LLMClient (ABC)
├── GeminiClient
├── OpenAIClient
├── ClaudeClient
├── GroqClient
├── DeepSeekClient
└── MockClient

PromptBuilder
├── RoleRegistry → RoleDefinition (system_prompt_template)
└── SkillRegistry → Skill (tools, constraints)

ReactOrchestrator
├── llm_client (LLMClient)
├── prompt_builder (PromptBuilder)
├── tool_registry (dict[str, Callable])
└── config (ReactConfig: max_iterations, max_tool_calls)

GoldTradingOrchestrator
├── GoldDataFetcher
├── TechnicalIndicators
└── GoldNewsFetcher
```

---

## Key Data Models

**PromptPackage** (prompt.py, client.py)
```python
@dataclass
class PromptPackage:
    system: str
    user: str
    step_label: str  # e.g., "THOUGHT_1", "THOUGHT_FINAL"
```

**ToolResult** (react.py)
```python
@dataclass
class ToolResult:
    tool_name: str
    status: str  # "success" | "error"
    data: dict
    error: Optional[str]
```

**ReactState** (react.py)
```python
@dataclass
class ReactState:
    market_state: dict
    tool_results: list[ToolResult]
    iteration: int = 0
    tool_call_count: int = 0
    react_trace: list = field(default_factory=list)
```

**ReactConfig** (react.py)
```python
@dataclass
class ReactConfig:
    max_iterations: int = 5
    max_tool_calls: int = 0  # 0 = data pre-loaded
    timeout_seconds: Optional[int] = None
```

---

## Error Handling

**LLM Exceptions** (client.py)
- `LLMException`: Base
- `LLMProviderError`: API call failed
- `LLMUnavailableError`: Missing key, package, or connection

**JSON Parsing** (react.py)
- Robust `extract_json()`: Handles markdown fences, malformed JSON
- Fallback: `_fallback_decision(reason)` → HOLD

---

## LLM Provider Defaults

| Provider | Model | Speed | Cost |
|----------|-------|-------|------|
| Gemini | gemini-2.5-flash | ⚡⚡⚡ | $ |
| Claude | claude-opus-4-1 | ⚡⚡ | $$ |
| OpenAI | gpt-4o-mini | ⚡⚡ | $ |
| Groq | llama-3.3-70b | ⚡⚡⚡ | $ |
| DeepSeek | deepseek-chat | ⚡⚡⚡ | $ |

---

## Configuration Variables

```python
# ReactConfig (in main.py)
ReactConfig(
    max_iterations=5,       # Thought steps
    max_tool_calls=0,       # 0 = pre-loaded data (no tool calls)
    timeout_seconds=None    # None = no timeout
)

# GoldTradingOrchestrator (in orchestrator.py)
GoldTradingOrchestrator(
    history_days=90,        # OHLCV lookback
    interval="1d",          # Timeframe: 1m, 5m, 15m, 1h, 1d
    max_news_per_cat=5,     # Max news per category
    output_dir="..."        # JSON save directory
)

# LLM Clients
GeminiClient(api_key="...", model="gemini-2.5-flash", use_mock=False)
ClaudeClient(api_key="...", model="claude-opus-4-1", max_tokens=2048)
OpenAIClient(api_key="...", model="gpt-4o-mini", temperature=0.7)
GroqClient(api_key="...", model="llama-3.3-70b-versatile", temperature=0.5)
DeepSeekClient(api_key="...", model="deepseek-chat", temperature=0.7)
```

---

## Environment Variables

```bash
export GEMINI_API_KEY="..."
export OPENAI_API_KEY="..."
export ANTHROPIC_API_KEY="..."
export GROQ_API_KEY="..."
export DEEPSEEK_API_KEY="..."
```

---

## File Structure

```
Src/
├── agent_core/
│   ├── config/
│   │   ├── roles.json
│   │   └── skills.json
│   ├── core/
│   │   ├── __init__.py
│   │   ├── prompt.py      (PromptBuilder, SkillRegistry, RoleRegistry)
│   │   └── react.py       (ReactOrchestrator, extract_json, etc.)
│   ├── data/
│   │   ├── latest.json    (cached market state)
│   │   └── payload_*.json
│   └── llm/
│       ├── __init__.py
│       ├── client.py      (All LLM clients + factory)
│       └── test_client.py
├── data_engine/
│   ├── fetcher.py
│   ├── indicators.py
│   ├── newsfetcher.py
│   └── orchestrator.py
├── main.py                (Entry point)
└── requirements.txt
```

---

## Usage Examples

**Basic Run**
```bash
python main.py --provider gemini
```

**With Custom Options**
```bash
python main.py \
  --provider claude \
  --iterations 7 \
  --skip-fetch \
  --output my_result.json
```

**Testing with Mock**
```bash
python main.py --provider mock
```

**Multi-Provider Comparison**
```bash
for p in gemini openai groq claude deepseek; do
  echo "Testing $p..."
  python main.py --provider $p --skip-fetch
done
```

---

## Design Principles

1. **Dependency Injection**: All components injected → testable, swappable
2. **Token Efficiency**: Data pre-loaded (no tool calls) → minimal API costs
3. **Multi-Provider Abstraction**: LLMClient factory allows easy provider switching
4. **Deterministic Parsing**: `extract_json()` handles noise robustly
5. **Configurable Reasoning**: Max iterations, max tool calls tunable
6. **Stateless Prompts**: Each prompt is self-contained (no conversation history)

---

## Notes

- **Market State**: Pre-computed in latest.json (fresh on each run or cached)
- **Tools**: Currently disabled (max_tool_calls=0) → data fully pre-loaded in prompt
- **JSON Output**: Single valid JSON per LLM response (no markdown fences)
- **Trace**: Full ReAct trace logged → debug-friendly
- **Roles**: Extensible via roles.json (analyst, risk_manager, trader, etc.)
- **Skills**: Each role has available_skills → tool filtering per role