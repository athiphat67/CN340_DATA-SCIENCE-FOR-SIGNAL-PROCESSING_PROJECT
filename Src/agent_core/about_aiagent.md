# 🤖 AI Trading Agent — Gold Trading System

> Autonomous gold-trading agent for **Aom NOW (Hua Seng Heng)** platform.  
> Fixed capital: **฿1,500 THB** — no top-ups, no margin.

---

## Overview

The AI Trading Agent uses a Large Language Model (LLM) as its decision core, wrapped in a **ReAct (Reasoning + Acting)** loop. It analyzes real-time market data and issues trading signals: **BUY**, **SELL**, or **HOLD**.

All risk calculations (Stop Loss, Take Profit) are handled automatically by the `RiskManager` using ATR — the LLM never computes price levels itself.

---

## Architecture

```
Market Data
    │
    ▼
PromptBuilder  ──►  LLMClient  ──►  ReactOrchestrator
    │                                      │
    └──────────────────────────────────────┘
                                           │
                                      RiskManager
                                           │
                                    Final Decision
```

| Component | Role | File |
|-----------|------|------|
| `LLMClient` | Sends prompts to AI providers, returns `LLMResponse` | `client.py` |
| `PromptBuilder` | Builds `PromptPackage` for each ReAct iteration | `prompt.py` |
| `ReactOrchestrator` | Controls Thought → Action → Observation loop | `react.py` |
| `RiskManager` | Validates signals, sizes positions, computes SL/TP | `risk.py` |
| `RoleRegistry` | Loads agent persona & rules from `roles.json` | `prompt.py` |
| `SkillRegistry` | Manages available tools per role from `skills.json` | `prompt.py` |

---

## Platform Constraints

| Item | Value |
|------|-------|
| Min position | ฿1,000 THB per trade |
| Trading hours | Mon–Fri 06:15–02:00 / Sat–Sun 09:30–17:30 |
| Danger zone | 01:30–01:59 — SELL if holding |
| Dead zone | 02:00–06:14 — no trades at all |
| Round-trip cost | ~฿9 per ฿1,000 position (~0.9%) |

---

## Trading Rules

### Capital

- Starting capital: **฿1,500 THB**
- Bust threshold: **฿1,000 THB** — stop trading if portfolio hits this
- Min cash to BUY: **฿1,010 THB**
- Max loss per trade: **฿150 THB**

### Take-Profit (SELL when ANY triggers)

| Rule | Condition | Reason |
|------|-----------|--------|
| TP1 | PnL ≥ +฿300 | Lock profit now |
| TP2 | PnL ≥ +฿150 AND RSI > 65 | Overbought — exit |
| TP3 | PnL ≥ +฿100 AND MACD hist < 0 | Momentum fading |

### Stop-Loss (SELL when ANY triggers)

| Rule | Condition | Reason |
|------|-----------|--------|
| SL1 | PnL ≤ -฿150 | Hard stop, no exceptions |
| SL2 | PnL ≤ -฿80 AND RSI < 35 | Breakdown confirmed |
| SL3 | Holding gold AND time 01:30–01:59 | Market closes at 02:00 |

### BUY Conditions (ALL must be true)

1. Cash ≥ ฿1,010 THB
2. Gold position = 0g (not already holding)
3. Time NOT in danger zone (01:30–01:59) or dead zone (02:00–06:14)
4. At least 2 of 3 bullish signals:
   - RSI 40–60 or RSI < 35 (oversold)
   - MACD histogram > 0
   - Price > EMA20
5. LLM confidence ≥ 0.65

---

## Supported LLM Providers

| Provider | Model | Notes |
|----------|-------|-------|
| Gemini | gemini-2.5-flash-lite | Default |
| Claude | claude-opus-4-1 | Highest reasoning |
| OpenAI | gpt-4o-mini | Balanced |
| Groq | llama-3.3-70b-versatile | Fastest |
| DeepSeek | deepseek-chat | Cost-efficient |
| Ollama | qwen3.5:9b | Local / offline |
| OpenRouter | meta-llama/llama-3-8b | Gateway |
| Mock | — | Testing only |

All providers share the same `LLMClient` interface — swapping providers requires only a config change.

`FallbackChainClient` chains multiple providers and auto-switches on failure.

---

## Risk Manager

Validates every LLM decision through 3 gates before execution:

1. **Confidence Filter** — rejects if confidence < 0.60
2. **Daily Loss Limit** — halts trading if cumulative loss ≥ ฿500 THB for the day
3. **Signal Checks** — SELL requires gold held; BUY requires position ≥ ฿1,000

### Position Sizing

- Portfolio < ฿2,000 (micro): fixed **฿1,000** (platform minimum)
- Portfolio ≥ ฿2,000: `cash × 0.50 × confidence`

### ATR-Based SL/TP

```
Stop Loss   = entry_price − (ATR × 2.0)
Take Profit = entry_price + (SL_distance × 1.5)
```

---

## Configuration

**`roles.json`** — agent persona, system prompt, trading rules  
**`skills.json`** — available tools per skill group

### Environment Variables

| Variable | Required For |
|----------|-------------|
| `GEMINI_API_KEY` | GeminiClient |
| `ANTHROPIC_API_KEY` | ClaudeClient |
| `OPENAI_API_KEY` | OpenAIClient |
| `GROQ_API_KEY` | GroqClient |
| `DEEPSEEK_API_KEY` | DeepSeekClient |
| `OPENROUTER_API_KEY` | OpenRouterClient |
| `OLLAMA_BASE_URL` | Ollama (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Ollama (default: `qwen3.5:9b`) |

---

## Version History

| Version | Changes |
|---------|---------|
| v2.1 | Full system prompt in `build_final_decision()` · Daily loss limit · ATR unit validation · `deepcopy` in `_reject_signal` |
| v2.0 | `LLMResponse` dataclass · Token tracking · `FallbackChainClient` · DI for RiskManager |
| v1.0 | Initial ReAct loop · Gemini-only |
