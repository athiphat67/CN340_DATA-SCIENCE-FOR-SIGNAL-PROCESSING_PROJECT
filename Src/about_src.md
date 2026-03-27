# GoldTrader — Complete Agent Architecture Documentation v3.1

---

## Executive Summary

**GoldTrader** is a production-grade **ReAct+LLM trading agent** for automated gold market analysis on the ออม NOW (Hua Seng Heng) platform. It combines multi-step AI reasoning, real-time technical indicators, and portfolio-aware constraints to generate BUY/SELL/HOLD signals.

- **LLM Engines**: Gemini, Claude, OpenAI, Groq, DeepSeek (pluggable)
- **Data**: Live OHLCV (yfinance) + Technical Indicators + News Feed
- **UI**: Gradio Dashboard with 4 tabs (Analysis, History, Portfolio, Trace)
- **Persistence**: PostgreSQL (trading history + portfolio snapshots)
- **Platform**: ออม NOW (minimum buy ฿1,000, trades in grams)

---

## 1. System Overview

### 1.1 Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    UI Layer (Gradio Dashboard)                   │
│  Tab 1: Live Analysis | Tab 2: History | Tab 3: Portfolio       │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────────┐
│              Agent Orchestration Layer (ReAct Loop)              │
│  ReactOrchestrator → PromptBuilder → LLMClient → Decision       │
└────────────────────────┬────────────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│ Data Engine  │  │  Prompt System  │  │ LLM Clients  │
│ (yfinance)   │  │ (Template +     │  │ (6 providers)│
│ + Indicators │  │  Role-based)    │  │              │
│ + News       │  │  + Skills       │  │              │
└──────────────┘  └─────────────────┘  └──────────────┘
    │                   │                    │
    └───────────────────┼────────────────────┘
                        │
                        ▼
            ┌─────────────────────────┐
            │   Database Layer        │
            │  PostgreSQL             │
            │  - runs (history)       │
            │  - portfolio (1 row)    │
            └─────────────────────────┘
```

### 1.2 Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Dependency Injection** | All components accept dependencies → testable, swappable |
| **Token Efficiency** | Data pre-loaded in prompt (0 tool calls per default) |
| **Multi-Provider** | LLMClientFactory supports 6 LLM providers |
| **Stateless Design** | Each prompt self-contained, no conversation memory |
| **Portfolio Awareness** | LLM sees real cash/gold/constraints before deciding |
| **Deterministic Output** | `extract_json()` robust to LLM formatting noise |
| **Configuration as Code** | Roles/Skills defined in JSON, not hardcoded |

---

## 2. Project Structure

```
Src/
│
├── agent_core/                          # AI Agent Core
│   ├── config/
│   │   ├── roles.json                   # Role definitions (analyst, risk_manager)
│   │   └── skills.json                  # Skill → Tool registry
│   │
│   ├── core/
│   │   ├── prompt.py                    # PromptBuilder, RoleRegistry, SkillRegistry
│   │   │                                  Builds thought/final_decision prompts
│   │   │                                  Formats market_state including portfolio
│   │   │
│   │   └── react.py                     # ReactOrchestrator
│   │                                      Thought → Action → Observation loop
│   │                                      Handles tool calls, JSON parsing
│   │
│   ├── data/
│   │   ├── latest.json                  # Current market snapshot (auto-updated)
│   │   └── payload_*.json               # Historical data dumps
│   │
│   └── llm/
│       ├── client.py                    # 6 LLMClient implementations + Factory
│       │                                  Classes: Gemini, Claude, OpenAI, Groq, DeepSeek, Mock
│       │
│       └── test_client.py
│
├── data_engine/                         # Market Data Collection
│   ├── fetcher.py                       # GoldDataFetcher (yfinance wrapper)
│   │                                      OHLCV, Spot Price, Forex (USDTHB)
│   │
│   ├── indicators.py                    # TechnicalIndicators
│   │                                      RSI, MACD, EMA, Bollinger Bands, etc.
│   │
│   ├── newsfetcher.py                   # GoldNewsFetcher (Phase 2.1 — Refactored)
│   │                                      Sources: yfinance (metadata) + RSS feeds
│   │                                      Sentiment: FinBERT via Hugging Face Inference API
│   │                                        → HTTP POST (per-item + retry) · requires HF_TOKEN
│   │                                      Context Guard: Greedy Packing (token budget)
│   │                                      Performance: Parallel ThreadPoolExecutor
│   │                                      Tokenizer: tiktoken (cl100k_base) + fallback
│   │                                      Categories: 8 (gold_price, usd_thb, fed_policy,
│   │                                        inflation, geopolitics, dollar_index,
│   │                                        thai_economy, thai_gold_market)
│   │
│   └── orchestrator.py                  # GoldTradingOrchestrator
│                                          Combines fetcher + indicators + news
│                                          → market_state JSON payload
│
├── Output/
│   └── result_output.json               # Agent decision (generated after run)
│
├── logs/
│   ├── system.log                       # Application events
│   ├── llm_trace.log                    # LLM request/response pairs (detailed)
│   └── (auto-generated per session)
│
├── dashboard.py                         # Gradio UI (v3.1)
│                                          4-panel display: Analysis, History, Portfolio, Trace
│                                          Provider/interval selection
│                                          Portfolio CRUD
│
├── database.py                          # RunDatabase (PostgreSQL ORM)
│                                          - save_run() → runs table
│                                          - save_portfolio() → portfolio table (UPSERT)
│                                          - get_portfolio() → portfolio dict
│                                          - signal_stats() → aggregates
│
├── main.py                              # CLI entry point
│                                          argparse: --provider, --iterations, --skip-fetch
│
├── logger_setup.py                      # Logging configuration
│                                          Custom THTimeFormatter (UTC+7)
│                                          sys_logger, llm_logger
│
├── requirements.txt                     # Python dependencies
│
└── .env                                 # Environment variables (not in repo)
    DATABASE_URL=postgresql://...
    GEMINI_API_KEY=...
    OPENAI_API_KEY=...
    ANTHROPIC_API_KEY=...
    GROQ_API_KEY=...
    DEEPSEEK_API_KEY=...
```

---

## 3. End-to-End Data Flow

### 3.1 Complete Request → Response Flow

```
USER INITIATES
  ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA COLLECTION (GoldTradingOrchestrator)          │
└─────────────────────────────────────────────────────────────┘

  Step 1.1: Price Fetching (GoldDataFetcher)
  ├─ yfinance.download('GC=F', period='90d', interval='1d')
  ├─ Extract: Spot Price (USD/oz), OHLCV, Forex (USDTHB)
  └─ Output: DataFrame[open, high, low, close, volume]

  Step 1.2: Technical Indicators (TechnicalIndicators)
  ├─ RSI(14), MACD(12,26,9), EMA(20,50), Bollinger Bands
  ├─ Trend classification (uptrend/downtrend/neutral)
  ├─ Calculate on last 90 candles
  └─ Output: Dict[indicator_name → {value, signal}]

  Step 1.3: News Fetching (GoldNewsFetcher — Phase 2.1)
  ├─ Parallel fetch (ThreadPoolExecutor, max 10 threads) per category:
  │  ├─ yfinance metadata (ticker symbols per category, no body scraping)
  │  └─ RSS feeds (feedparser + requests timeout=10s, keyword-filtered)
  ├─ 8 categories: gold_price, usd_thb, fed_policy, inflation,
  │  geopolitics, dollar_index, thai_economy, thai_gold_market
  ├─ Greedy Packing (token budget): select articles by impact priority
  │  (direct > high > medium) within max_total_articles + token_budget
  ├─ FinBERT via Hugging Face Inference API (HF_TOKEN): per-item HTTP POST,
  │  retry × 3, 429 rate-limit → sleep 10s, 503 cold start → sleep estimated_time,
  │  polite sleep 0.5s between items → [+conf, -conf, 0.0]
  ├─ Token estimation: tiktoken (cl100k_base) × 1.10 overhead, or len//4 fallback
  └─ Output: NewsFetchResult{fetched_at, total_articles, token_estimate, by_category, errors}

  Step 1.4: Market State Assembly
  ├─ Combine market_data + indicators + news
  ├─ Optimize token count (~40% reduction)
  ├─ Recent 5-candle price action snapshot
  └─ Output: market_state JSON

                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: PORTFOLIO INTEGRATION (NEW in v3)                  │
└─────────────────────────────────────────────────────────────┘

  Step 2.1: Retrieve User Portfolio
  ├─ db.get_portfolio() → {cash_balance, gold_grams, cost_basis_thb, ...}
  └─ If not set, default: {cash: 1500, gold: 0, ...}

  Step 2.2: Compute Constraints
  ├─ can_buy = cash_balance >= 1000 (ออม NOW minimum)
  ├─ can_sell = gold_grams > 0 (no short selling)
  └─ trades_today (enforce min 1 trade per day)

  Step 2.3: Merge into market_state
  ├─ market_state["portfolio"] = portfolio
  └─ PromptBuilder includes in system message

                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: PROMPT GENERATION (PromptBuilder)                  │
└─────────────────────────────────────────────────────────────┘

  Step 3.1: Load Role Definition
  ├─ RoleRegistry.get(AIRole.ANALYST)
  ├─ Extract: title, system_prompt_template, available_skills
  └─ Resolve available tools via SkillRegistry

  Step 3.2: Format Market Context
  ├─ _format_market_state():
  │  ├─ Spot price, RSI, MACD, EMA trend
  │  ├─ Top news (1 per category)
  │  ├─ Portfolio section ← [NEW]
  │  │  ├─ Cash balance, Gold grams
  │  │  ├─ Cost basis, Current value, PnL
  │  │  ├─ Trades today
  │  │  ├─ can_buy: YES/NO
  │  │  └─ can_sell: YES/NO
  │  └─ Optimized ~200 tokens
  │
  └─ Output: formatted_state (markdown-like format)

  Step 3.3: Build Final Decision Prompt
  ├─ system message (role, constraints, output schema)
  ├─ user message (market state + portfolio)
  └─ Output: PromptPackage(system, user, step_label)

                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: LLM REASONING (ReactOrchestrator + LLMClient)       │
└─────────────────────────────────────────────────────────────┘

  Step 4.1: Select LLM Client
  ├─ LLMClientFactory.create(provider)
  │  ├─ Gemini (default)
  │  ├─ Claude, OpenAI, Groq, DeepSeek, Mock
  │  └─ All implement abstract LLMClient.call()
  │
  └─ Output: LLMClient instance

  Step 4.2: Execute ReAct Loop (max_iterations=5, max_tool_calls=0)
  ├─ Iteration 1: build_thought() → llm.call() → parse JSON
  │  └─ action: "FINAL_DECISION" (data pre-loaded, no tools)
  │
  ├─ [IF max_tool_calls > 0]
  │  │ Could call external tools (but default=0)
  │  │ tool_results logged, loop continues
  │  │
  │  └─ More iterations until FINAL_DECISION or max reached
  │
  └─ Output: final_decision dict + react_trace list

  Step 4.3: JSON Extraction
  ├─ extract_json(): Strip markdown, find first {}, parse
  ├─ Fallback to HOLD if malformed
  └─ Output: {"signal": "BUY|SELL|HOLD", "confidence": 0.65, ...}

                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 5: PERSISTENCE (RunDatabase)                          │
└─────────────────────────────────────────────────────────────┘

  Step 5.1: Save Run Record
  ├─ db.save_run(provider, result, market_state, interval, period)
  ├─ Columns: signal, confidence, entry_price, stop_loss, take_profit
  ├─ Also: gold_price, rsi, macd_line, trend, react_trace
  └─ Output: run_id (auto-increment)

  Step 5.2: Update Portfolio (Optional)
  ├─ User executes trade in ออม NOW app
  ├─ Returns to dashboard, updates Portfolio tab
  ├─ db.save_portfolio({cash_balance, gold_grams, ...})
  ├─ Uses UPSERT (id=1 always)
  └─ Available for next analysis run

                            ↓
RESPONSE GENERATED & DISPLAYED
  ├─ Dashboard Tab 1: Final Decision, Market State, ReAct Trace
  ├─ Dashboard Tab 2: 50 most recent runs (sortable)
  ├─ Dashboard Tab 3: Current portfolio snapshot
  └─ Output/result_output.json saved
```

### 3.2 Data Models at Each Phase

#### Phase 1: Market State (After Orchestrator)

```python
market_state = {
    "meta": {
        "agent": "gold-trading-agent",
        "version": "1.1.0",
        "generated_at": "2026-03-27T12:34:56Z",
        "history_days": 90,
        "interval": "1d"
    },
    "data_sources": {
        "price": "yfinance",
        "news": "yfinance_metadata + rss"
    },
    "market_data": {
        "spot_price_usd": {
            "price_usd_per_oz": 4445.50,
            "timestamp": "2026-03-27T...",
            "source": "yfinance"
        },
        "forex": {
            "USDTHB": 35.8,
            "timestamp": "...",
            "source": "yfinance"
        },
        "thai_gold_thb": {
            "spot_price_thb": 159_000,
            "source": "calculated"
        },
        "recent_price_action": [
            {"time": "2026-03-23", "open": 4410, "high": 4440, "low": 4405, "close": 4430, "volume": 1_000_000},
            ...
        ]
    },
    "technical_indicators": {
        "rsi": {"value": 54.55, "period": 14, "signal": "neutral"},
        "macd": {
            "macd_line": 2.1722,
            "signal_line": -4.7625,
            "histogram": 6.9347,
            "signal": "bullish_cross"
        },
        "trend": {
            "ema_20": 4440.78,
            "ema_50": 4452.78,
            "trend": "downtrend"
        }
    },
    "news": {
        "summary": {
            "total_articles": 15,
            "fetched_at": "2026-03-27T12:30:00Z"
        },
        "by_category": {
            "FED": {
                "sentiment": "mixed",
                "articles": [
                    {
                        "title": "Fed Pauses Rate Hikes",
                        "sentiment_score": 0.45,
                        "source": "Reuters"
                    }
                ]
            }
        }
    }
}
```

#### Phase 2: Portfolio (User's Account)

```python
portfolio = {
    "cash_balance": 1500.00,              # ฿ (remaining buying power)
    "gold_grams": 0.0,                    # g (gold holdings)
    "cost_basis_thb": 0.00,               # ฿ (total cost)
    "current_value_thb": 0.00,            # ฿ (market value)
    "unrealized_pnl": 0.00,               # ฿ (profit/loss)
    "trades_today": 0,                    # count
    "updated_at": "2026-03-27T12:00:00Z"  # UTC timestamp
}

# merged into market_state before sending to LLM
market_state["portfolio"] = portfolio
```

#### Phase 3: Prompt Package

```python
prompt_package = PromptPackage(
    system="""You are a professional Gold Market Analyst...
    Trading Rules (MUST follow):
    - Minimum buy amount is 1,000 THB. If can_buy=NO, you MUST NOT signal BUY.
    - can_sell check: If can_sell=NO, you MUST NOT signal SELL.
    - Output Rules: Always output a single valid JSON object — no markdown...""",
    
    user="""## Market State
Gold: $4445.5 | RSI(14): 54.55 [neutral]
MACD: 2.1722/-4.7625 hist:6.9347
Trend: EMA20=4440.78 EMA50=4452.78 [downtrend]

── Portfolio ──
  Cash:       ฿1,500.00
  Gold:       0.0000 g
  can_buy:  YES
  can_sell: NO (gold_grams = 0)
── End Portfolio ──""",
    
    step_label="THOUGHT_FINAL"
)
```

#### Phase 4: Final Decision (LLM Output)

```python
final_decision = {
    "signal": "BUY",                      # BUY | SELL | HOLD
    "confidence": 0.65,                   # 0.0–1.0
    "entry_price": 4445.5,                # THB (not USD!)
    "stop_loss": 4438.0,                  # THB
    "take_profit": 4455.0,                # THB
    "rationale": "Strong MACD bullish cross with positive histogram..."
}

# complete agent result
result = {
    "final_decision": final_decision,
    "react_trace": [
        {
            "step": "THOUGHT_FINAL",
            "iteration": 1,
            "response": final_decision
        }
    ],
    "iterations_used": 1,
    "tool_calls_used": 0
}
```

---

## 4. Core Components Detailed

### 4.1 GoldTradingOrchestrator (data_engine/orchestrator.py)

**Purpose**: Fetch, compute, assemble → JSON payload

**Public Method**:
```python
orchestrator = GoldTradingOrchestrator(
    history_days=90,
    interval="1d",  # "1m", "5m", "15m", "1h", "1d"
    max_news_per_cat=5,
    output_dir="./output"
)

market_state = orchestrator.run(save_to_file=True)
# Returns: market_state dict
# Side effect: saves to latest.json + timestamped backup
```

**Internal Flow**:
1. `GoldDataFetcher().fetch_all()` → OHLCV DataFrame
2. `TechnicalIndicators(df).to_dict()` → RSI, MACD, EMA, etc.
3. `GoldNewsFetcher().to_dict()` → news by category
4. Assemble JSON → market_state
5. Save to `agent_core/data/latest.json`

**Key Outputs**:
- `market_data.spot_price_usd` — current gold price
- `technical_indicators.*` — all computed signals
- `news.by_category` — sentiment + articles
- `market_data.recent_price_action` — last 5 candles

---

### 4.2 PromptBuilder (agent_core/core/prompt.py)

**Purpose**: Construct system + user prompts from market_state + portfolio

**Key Methods**:

```python
builder = PromptBuilder(role_registry, current_role=AIRole.ANALYST)

# Build final decision prompt (no tool calls)
prompt_pkg = builder.build_final_decision(market_state={...}, tool_results=[])
# Returns: PromptPackage(system, user, "THOUGHT_FINAL")

# Internal: Format market state with portfolio
formatted = builder._format_market_state(market_state)
# Returns: String ~200 tokens including:
#   - Spot price, RSI, MACD, EMA
#   - News highlights (1 per category)
#   - Portfolio section [NEW]
```

**Portfolio Integration**:
```python
def _format_market_state(self, state: dict) -> str:
    portfolio = state.get("portfolio", {})
    if portfolio:
        can_buy  = "YES" if portfolio["cash_balance"] >= 1000 else f"NO (฿{cash} < ฿1000)"
        can_sell = "YES" if portfolio["gold_grams"] > 0 else "NO (gold_grams = 0)"
        
        # Include in formatted output:
        # ── Portfolio ──
        # Cash:       ฿X,XXX.XX
        # Gold:       X.XXXX g
        # can_buy:    {can_buy}
        # can_sell:   {can_sell}
        # ── End Portfolio ──
```

---

### 4.3 ReactOrchestrator (agent_core/core/react.py)

**Purpose**: Execute Thought → Action → Observation loop

**Config**:
```python
config = ReactConfig(
    max_iterations=5,
    max_tool_calls=0,     # 0 = no tools, data pre-loaded
    timeout_seconds=None
)

orchestrator = ReactOrchestrator(
    llm_client=client,
    prompt_builder=builder,
    tool_registry={},     # empty when max_tool_calls=0
    config=config
)
```

**Main Loop** (simplified):
```python
result = orchestrator.run(market_state=market_state)

# If max_tool_calls=0:
#   1. build_final_decision(market_state, [])
#   2. llm_client.call(prompt)
#   3. extract_json(response)
#   4. return final_decision + trace

# If max_tool_calls > 0:
#   1. loop i in range(max_iterations):
#       build_thought() → llm.call() → parse
#       if action == "FINAL_DECISION": break
#       elif action == "CALL_TOOL": execute_tool() → observation, continue
#   2. if not finalized: force build_final_decision()
```

**Output**:
```python
{
    "final_decision": {
        "signal": "BUY",
        "confidence": 0.65,
        "entry_price": 4445.5,
        "stop_loss": 4438.0,
        "take_profit": 4455.0,
        "rationale": "..."
    },
    "react_trace": [
        {"step": "THOUGHT_1", "iteration": 1, "response": {...}},
        ...
        {"step": "THOUGHT_FINAL", "iteration": 1, "response": {...}}
    ],
    "iterations_used": 1,
    "tool_calls_used": 0
}
```

---

### 4.4 LLMClientFactory (agent_core/llm/client.py)

**Purpose**: Abstract LLM provider selection

**Supported Providers**:

| Provider | Model | Speed | Cost | Best For |
|----------|-------|-------|------|----------|
| **Gemini** | gemini-2.5-flash | ⚡⚡⚡ | $ | Fast, cheap |
| **Claude** | claude-opus-4-1 | ⚡⚡ | $$ | Accurate reasoning |
| **OpenAI** | gpt-4o-mini | ⚡⚡ | $ | Reliable |
| **Groq** | llama-3.3-70b | ⚡⚡⚡ | $ | Ultra-fast |
| **DeepSeek** | deepseek-chat | ⚡⚡⚡ | $ | Cost-effective |
| **Mock** | — | ⚡⚡⚡⚡ | Free | Testing |

**Usage**:
```python
# Factory pattern
client = LLMClientFactory.create("gemini")
client = LLMClientFactory.create("claude", model="claude-opus-4-1")
client = LLMClientFactory.create("mock")

# Abstract contract
class LLMClient(ABC):
    def call(self, prompt_package: PromptPackage) -> str: ...
    def is_available(self) -> bool: ...

# All clients implement same interface → swappable
response = client.call(prompt_package)
# Returns: raw string (JSON expected)
```

**Error Handling**:
```python
@with_retry(max_attempts=3, delay=2.0)
def call(self, prompt_package):
    try:
        return self._client.models.generate_content(...)
    except Exception as e:
        raise LLMProviderError(f"Gemini API error: {e}") from e

# Exceptions:
# - LLMProviderError: API call failed → retry
# - LLMUnavailableError: Key missing or package not installed
# - LLMException: Base exception
```

---

### 4.5 RunDatabase (database.py)

**Purpose**: PostgreSQL persistence for runs + portfolio

**Tables**:

```sql
CREATE TABLE runs (
    id              SERIAL PRIMARY KEY,
    run_at          TEXT,           -- UTC ISO timestamp
    provider        TEXT,           -- "gemini", "claude", etc.
    interval_tf     TEXT,           -- "1d", "1h", etc.
    signal          TEXT,           -- "BUY", "SELL", "HOLD"
    confidence      REAL,           -- 0.0–1.0
    entry_price     REAL,           -- THB
    stop_loss       REAL,           -- THB
    take_profit     REAL,           -- THB
    gold_price      REAL,           -- USD/oz
    rsi             REAL,           -- 0–100
    macd_line       REAL,           -- value
    signal_line     REAL,           -- value
    trend           TEXT,           -- "uptrend", "downtrend"
    rationale       TEXT,           -- explanation
    react_trace     TEXT,           -- JSON array
    market_snapshot TEXT            -- full market_state JSON
);

CREATE TABLE portfolio (
    id                SERIAL PRIMARY KEY,
    cash_balance      REAL,          -- ฿
    gold_grams        REAL,          -- g
    cost_basis_thb    REAL,          -- ฿
    current_value_thb REAL,          -- ฿
    unrealized_pnl    REAL,          -- ฿
    trades_today      INTEGER,       -- count
    updated_at        TEXT           -- UTC ISO timestamp
);
```

**API**:
```python
db = RunDatabase()

# Save analysis result
run_id = db.save_run(
    provider="gemini",
    result={...},
    market_state={...},
    interval_tf="1d",
    period="90d"
)

# Get recent runs
rows = db.get_recent_runs(limit=50)
# Returns: List[dict] with signal, confidence, price, etc.

# Get detailed run
detail = db.get_run_detail(run_id=1)
# Returns: Full dict including react_trace (parsed JSON), market_snapshot

# Portfolio CRUD
db.save_portfolio({
    "cash_balance": 1500.0,
    "gold_grams": 0.5,
    "cost_basis_thb": 18_000,
    "current_value_thb": 18_500,
    "unrealized_pnl": 500,
    "trades_today": 1
})

portfolio = db.get_portfolio()
# Returns: dict (or default if not set)

# Stats
stats = db.get_signal_stats()
# Returns: {"total": 100, "buy_count": 30, "sell_count": 20, "hold_count": 50, "avg_confidence": 0.65}
```

### 4.6 GoldNewsFetcher (data_engine/newsfetcher.py) — Phase 2.1

**Purpose**: Multi-source news collection, sentiment scoring, and token-aware article selection

**Key Classes & Dataclasses**:
```python
@dataclass
class NewsArticle:
    title:           str
    url:             str
    source:          str
    published_at:    str       # ISO 8601 UTC
    ticker:          str       # yfinance symbol or "rss"
    category:        str       # e.g. "fed_policy"
    impact_level:    str       # "direct" | "high" | "medium"
    sentiment_score: float     # +conf (positive), -conf (negative), 0.0 (neutral)

    def estimated_tokens(self) -> int:
        # tiktoken (cl100k_base × 1.10) or len(text)//4 fallback

@dataclass
class NewsFetchResult:
    fetched_at:     str
    total_articles: int
    token_estimate: int
    by_category:    dict   # {cat_key: {label, impact, tickers, count, articles}}
    errors:         list   # ["{cat_key}: {error_message}"]
```

**8 News Categories** (NEWS_CATEGORIES):

| Key | Label | Impact | Sources |
|-----|-------|--------|---------|
| `gold_price` | ราคาทองคำโลก | direct | Kitco RSS, Investing.com RSS, yfinance |
| `usd_thb` | ค่าเงิน USD/THB | direct | FXStreet RSS, yfinance |
| `fed_policy` | นโยบายดอกเบี้ย Fed | high | Reuters RSS, FXStreet RSS, yfinance |
| `inflation` | เงินเฟ้อ / CPI | high | Reuters RSS, yfinance |
| `geopolitics` | ภูมิรัฐศาสตร์ / Safe Haven | high | Kitco RSS, Reuters World RSS, yfinance |
| `dollar_index` | ดัชนีค่าเงินดอลลาร์ (DXY) | medium | FXStreet RSS, yfinance |
| `thai_economy` | เศรษฐกิจไทย / ตลาดหุ้นไทย | medium | Bangkok Post RSS, yfinance |
| `thai_gold_market` | ตลาดทองไทย | direct | Kitco RSS, Bangkok Post RSS, yfinance |

**Usage**:
```python
fetcher = GoldNewsFetcher(
    max_per_category   = 5,        # articles per category (before packing)
    max_total_articles = 30,       # hard cap across all categories
    token_budget       = 3_000,    # greedy packing limit (tokens)
    target_date        = None,     # defaults to today (Thai TZ UTC+7)
)

result: NewsFetchResult = fetcher.fetch_all()
# or as dict:
data = fetcher.to_dict()
```

**fetch_all() Pipeline**:
```
1. ThreadPoolExecutor(max_workers=10)
   └─ fetch_category(cat_key) per category in parallel
       ├─ _fetch_yfinance_raw(symbol) → parse → NewsArticle
       └─ _fetch_rss(feed_url, keywords, category) → keyword filter → NewsArticle

2. _apply_global_limit() — Greedy Packing
   ├─ Sort: (published_at DESC, impact priority ASC)
   ├─ Select articles while token_estimate + est ≤ token_budget
   └─ Enforce max_total_articles hard cap

3. score_sentiment_batch([titles of surviving articles])
   └─ Hugging Face Inference API (ProsusAI/finbert)
       Endpoint: https://router.huggingface.co/hf-inference/models/ProsusAI/finbert
       Auth: Bearer HF_TOKEN (from .env / environment variable)
       Per-item loop (API ไม่รองรับ batch):
         - retry × 3 per item
         - 429 Rate Limit → sleep 10s
         - 503 Cold Start → sleep estimated_time
         - polite sleep 0.5s between items
       positive → +confidence
       negative → -confidence
       neutral  → 0.0

4. Map scores back → article.sentiment_score
5. Return NewsFetchResult
```

**Sentiment Model**:
```python
# Model: ProsusAI/finbert — via Hugging Face Inference API (ไม่ต้องติดตั้ง torch/transformers)
# Endpoint: https://router.huggingface.co/hf-inference/models/ProsusAI/finbert
# Requires: HF_TOKEN set in .env or environment variable

# If HF_TOKEN missing → returns [0.0] * len(texts) with warning
# Per-item HTTP POST (API does not support batch input):
#   payload = {"inputs": text[:512]}
#   Retry × 3 per item; 429 → sleep 10s; 503 → sleep estimated_time
#   Polite sleep 0.5s between items to avoid ban

scores = score_sentiment_batch(["Gold hits record high", "Fed rate hike fears grow"])
# Returns: [0.9231, -0.8745]
```

---

## 5. Installation & Environment Setup

### 5.1 Prerequisites

- **Python**: 3.9+
- **PostgreSQL**: 12+ (for persistence)
- **API Keys**: Gemini / Claude / OpenAI / Groq / DeepSeek (choose at least 1)

### 5.2 Virtual Environment Setup

```bash
# Navigate to project
cd Src

# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate          # macOS/Linux
# OR
venv\Scripts\activate             # Windows

# Verify
which python  # should show .../venv/bin/python
```

### 5.3 Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install all requirements
pip install -r requirements.txt

# Key packages:
# - yfinance: OHLCV + news metadata fetching
# - feedparser + requests: RSS feed parsing (newsfetcher Phase 2.1)
# - tiktoken: Production-grade token estimation (cl100k_base)
# - pandas, numpy: data manipulation
# - gradio: UI dashboard
# - psycopg2-binary: PostgreSQL driver
# - google-genai, openai, anthropic, groq: LLM APIs
# - python-dotenv: environment variable management (incl. HF_TOKEN)
# NOTE: transformers/torch NOT required — FinBERT runs via HF Inference API
```

**requirements.txt** (example):
```
yfinance>=0.2.28
pandas>=1.5.0
numpy>=1.23.0
feedparser>=6.0.10
requests>=2.31.0
tiktoken>=0.6.0
gradio>=3.40.0
psycopg2-binary>=2.9.0
python-dotenv>=0.21.0
google-genai>=0.3.0
openai>=1.0.0
anthropic>=0.7.0
groq>=0.4.0
```

### 5.4 Environment Variables

Create `.env` file in `Src/` directory:

```bash
# Required: At least ONE LLM API key
GEMINI_API_KEY="your-gemini-api-key"
OPENAI_API_KEY="your-openai-api-key"
ANTHROPIC_API_KEY="your-anthropic-api-key"
GROQ_API_KEY="your-groq-api-key"
DEEPSEEK_API_KEY="your-deepseek-api-key"

# Required: Hugging Face Inference API (FinBERT sentiment)
HF_TOKEN="your-huggingface-token"

# Required: Database connection
DATABASE_URL="postgresql://username:password@localhost:5432/goldtrader"

# Optional
LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
```

### 5.5 Database Initialization

```bash
# Connect to PostgreSQL
psql -U postgres -d postgres

# Create database
CREATE DATABASE goldtrader;

# Exit psql
\q

# Update DATABASE_URL in .env
DATABASE_URL="postgresql://username:password@localhost:5432/goldtrader"

# Tables auto-created on first run
# (_init_db() called in RunDatabase.__init__)
```

---

## 6. How to Run

### 6.1 CLI Mode (Command Line)

```bash
# Basic run (default: Gemini, latest market data)
python main.py

# With specific provider
python main.py --provider gemini
python main.py --provider claude
python main.py --provider mock

# Advanced options
python main.py \
    --provider openai \
    --iterations 7 \
    --skip-fetch \
    --output Output/my_result.json

# Full help
python main.py --help
```

**Arguments**:
- `--provider`: LLM provider (default: gemini)
- `--iterations`: Max ReAct iterations (default: 5)
- `--skip-fetch`: Use cached latest.json instead of fetching new data
- `--output`: Save result to custom path
- `--period`: yfinance period (default: 90d)
- `--interval`: Timeframe (default: 1d)

**Example Output**:
```
═══ Orchestrator — Building LLM Payload (1d Timeframe) ═══
Step 1: Fetching price data (Interval: 1d)...
Step 2: Computing indicators on 90 candles...
Step 3: Fetching news via yfinance + RSS (parallel, 8 categories)...
═══ Payload ready — 15 news articles ═══

--- LLM REQUEST [THOUGHT_FINAL] ---
--- LLM RESPONSE [THOUGHT_FINAL] ---

✅ FINAL DECISION: BUY (Confidence: 0.65)
Entry Price: ฿4,445.50 | Stop Loss: ฿4,438.00 | Take Profit: ฿4,455.00
Rationale: Strong MACD bullish cross with positive histogram...

Run ID saved to database: 1234
```

### 6.2 Dashboard Mode (Gradio UI)

```bash
# Start dashboard (runs on port 10000)
python dashboard.py
```

Open browser: **http://localhost:10000**

**Tab 1: 📊 Live Analysis**
1. Select **Provider**: Gemini, Claude, OpenAI, Groq, DeepSeek
2. Select **Period**: 30d, 60d, 90d (default)
3. Select **Interval**: 1h, 4h, 1d (default)
4. **[▶ Run Analysis]** button
5. See results:
   - **Signal**: BUY/SELL/HOLD + confidence
   - **Market State**: Current spot price, RSI, MACD, EMA, news
   - **ReAct Trace**: Step-by-step AI reasoning
   - **Explain**: Full rationale

**Tab 2: 📜 Run History**
- Table of recent 50 runs
- Sort by: ID, Time, Provider, Signal, Confidence, Price
- Click row to view detailed trace + market snapshot

**Tab 3: 💼 Portfolio** [NEW]
1. **Input Fields**:
   - Cash Balance (฿): Current spending power
   - Gold (g): Current holdings
   - Cost Basis (฿): Total amount invested
   - Current Value (฿): Market value now
   - Unrealized PnL (฿): Profit/loss
   - Trades Today: Number of executed trades

2. **[บันทึก]** Save portfolio to database
3. Portfolio data used in next analysis run:
   - LLM sees `can_buy` / `can_sell` constraints
   - Adjusts BUY/SELL signals accordingly

**Tab 4: 🔍 Detailed Trace** (Auto-populated)
- Shows full ReAct loop execution
- Each step color-coded:
  - Blue: THOUGHT iteration
  - Gold: TOOL_EXECUTION
  - Green: FINAL_DECISION
- Expands to show full JSON responses

---

## 7. Configuration Files

### 7.1 roles.json (agent_core/config/roles.json)

Defines AI roles and their system prompts:

```json
{
  "roles": [
    {
      "name": "analyst",
      "title": "Gold Market Analyst",
      "available_skills": ["market_analysis"],
      "system_prompt_template": "You are a professional {role_title}...\n\nTrading Rules (MUST follow):\n- Minimum buy amount is 1,000 THB...\n- entry_price, stop_loss, take_profit must be in THB (Thai Baht), not USD.\n\nOutput Rules:\n- Always output a single valid JSON object — no markdown..."
    },
    {
      "name": "risk_manager",
      "title": "Risk Manager",
      "available_skills": ["risk_assessment"],
      "system_prompt_template": "You are a {role_title}. Evaluate trading risk..."
    }
  ]
}
```

**Template Variables**:
- `{role_title}`: Replaced with role.title
- `{available_tools}`: Replaced with resolved tool names

### 7.2 skills.json (agent_core/config/skills.json)

Maps skills to tools (for future tool-calling):

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

---

## 8. Trading Constraints & Rules

### 8.1 Hard Constraints (Enforced by System Prompt)

| Rule | Enforcement |
|------|-------------|
| **Minimum Buy** | ฿1,000 per transaction (ออม NOW platform limit) |
| **can_buy Check** | `if cash_balance < 1000: can_buy = NO` → LLM cannot signal BUY |
| **can_sell Check** | `if gold_grams == 0: can_sell = NO` → LLM cannot signal SELL |
| **Starting Capital** | ฿1,500 initial |
| **Price Unit** | All prices in THB (not USD) — `entry_price`, `stop_loss`, `take_profit` |
| **Capital Preservation** | Do not risk >50% per trade |
| **Daily Activity** | Must make ≥1 trade per day (BUY or SELL) |
| **HOLD Conditions** | Only acceptable if `can_buy=NO AND can_sell=NO` |

### 8.2 Soft Constraints (LLM Reasoning)

- Consider trend direction (uptrend: prefer BUY, downtrend: prefer SELL)
- Use RSI for overbought/oversold signals
- Check MACD momentum before entry
- Risk/reward ratio (take_profit - entry_price) > (entry_price - stop_loss)

---

## 9. Logging & Debugging

### 9.1 Log Files

Generated in `Src/logs/` directory:

```
logs/
├── system.log          # Application events, database ops, errors
├── llm_trace.log       # LLM request/response pairs (verbose)
└── (rotating, auto-managed)
```

### 9.2 Viewing Logs

```bash
# Follow system.log in real-time
tail -f logs/system.log

# View LLM trace (requests + responses)
tail -f logs/llm_trace.log

# Count BUY signals
grep "signal.*BUY" logs/system.log | wc -l

# Find errors
grep "ERROR\|Exception" logs/system.log
```

### 9.3 Log Format

```
[2026-03-27 12:34:56] [INFO] [orchestrator.py:run] - === Orchestrator — Building LLM Payload (1d Timeframe) ===
[2026-03-27 12:34:57] [DEBUG] [client.py:call] - --- LLM REQUEST [THOUGHT_FINAL] ---
[2026-03-27 12:35:01] [INFO] [client.py:call] - --- LLM RESPONSE [THOUGHT_FINAL] ---
[2026-03-27 12:35:02] [INFO] [database.py:save_run] - Saved run successfully with ID: 1234
```

---

## 10. Error Handling & Troubleshooting

### 10.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `LLMUnavailableError: GEMINI_API_KEY not found` | API key not set | Add to `.env` or export in shell |
| `DATABASE_URL is not set` | PostgreSQL URL missing | Set `DATABASE_URL` in `.env` |
| `psycopg2.OperationalError: connection refused` | PostgreSQL not running | Start PostgreSQL service |
| JSON parse error in LLM response | Malformed LLM output | `extract_json()` fallback to HOLD |
| `[THOUGHT_FINAL] signal: HOLD, confidence: 0.0` | No usable data | Check fetcher, verify yfinance access |

### 10.2 Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL="DEBUG"
python main.py --provider gemini

# Or in code
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 11. Performance & Optimization

### 11.1 Token Efficiency

**Prompt Optimization** (40% reduction):
- Only latest spot price (not historical)
- Top 1 news article per category (not all)
- 5-candle recent price action (not full OHLCV)
- No conversation history (stateless)

**Typical Token Usage**:
- System prompt: ~300 tokens
- User context: ~200 tokens
- Response: ~150 tokens
- **Total per run**: ~650 tokens (vs 1500+ without optimization)

### 11.2 Caching

- `agent_core/data/latest.json` caches last run data
- Use `--skip-fetch` to skip new data collection
- Useful for testing multiple LLMs on same data

### 11.3 Database Indexes

Recommended PostgreSQL indexes:

```sql
CREATE INDEX idx_runs_provider ON runs(provider);
CREATE INDEX idx_runs_signal ON runs(signal);
CREATE INDEX idx_runs_run_at ON runs(run_at DESC);
```

---

## 12. Extensibility

### 12.1 Adding New LLM Provider

```python
# 1. Create new client class in agent_core/llm/client.py
class MyLLMClient(LLMClient):
    def call(self, prompt_package: PromptPackage) -> str:
        # Implement API call logic
        pass
    
    def is_available(self) -> bool:
        return self._client is not None

# 2. Register with factory
LLMClientFactory.register("mymodel", MyLLMClient)

# 3. Use it
client = LLMClientFactory.create("mymodel", api_key="...")
```

### 12.2 Adding New Technical Indicator

```python
# In data_engine/indicators.py
def calculate_roc(self) -> dict:
    """Rate of Change indicator"""
    roc = self.df['close'].pct_change(periods=12) * 100
    return {
        "value": roc.iloc[-1],
        "signal": "positive" if roc.iloc[-1] > 0 else "negative"
    }

# Add to to_dict()
def to_dict(self) -> dict:
    return {
        ...existing indicators...,
        "roc": self.calculate_roc()
    }
```

### 12.3 Adding New Skill/Tool

```json
// In skills.json
{
  "name": "sentiment_analysis",
  "description": "Analyze market sentiment from news",
  "tools": ["get_sentiment_score"],
  "constraints": {"max_calls": 5}
}
```

---

## 13. API Reference

### Core Classes

```python
# Orchestrator
GoldTradingOrchestrator(history_days=90, interval="1d", max_news_per_cat=5)
  .run(save_to_file=True) → dict

# Prompt Builder
PromptBuilder(role_registry, current_role)
  .build_final_decision(market_state, tool_results) → PromptPackage
  .build_thought(market_state, tool_results, iteration) → PromptPackage

# ReAct Orchestrator
ReactOrchestrator(llm_client, prompt_builder, tool_registry, config)
  .run(market_state, initial_observation=None) → dict

# Database
RunDatabase()
  .save_run(provider, result, market_state, interval_tf, period) → run_id
  .get_recent_runs(limit=50) → list[dict]
  .save_portfolio(data) → None
  .get_portfolio() → dict

# LLM Factory
LLMClientFactory.create(provider, **kwargs) → LLMClient
LLMClientFactory.available_providers() → list[str]
```

---

## 14. Summary of Key Improvements (v3.1)

| Feature | Status | Impact |
|---------|--------|--------|
| Portfolio awareness | ✅ | LLM makes buy/sell decisions based on actual cash/gold |
| Constraint enforcement | ✅ | System prompt includes can_buy/can_sell flags |
| Multi-provider LLM | ✅ | Switch between 6 providers with 1 parameter |
| Database persistence | ✅ | Track all decisions + portfolio state |
| Gradio dashboard | ✅ | No-code UI for non-technical users |
| Token optimization | ✅ | ~40% reduction via smart data selection |
| Error resilience | ✅ | Retry logic, fallback to HOLD |
| Logging & tracing | ✅ | Full audit trail in logs/llm_trace.log |
| **NewsFetcher Phase 2.1** | ✅ | Multi-source (yfinance metadata + RSS) — no body scraping, no blocking |
| **HF Inference API** | ✅ | FinBERT via API — ไม่ต้องติดตั้ง torch/transformers, รองรับ cloud deploy |
| **Greedy Packing** | ✅ | Token-budget-aware article selection by impact priority |
| **Parallel RSS fetch** | ✅ | ThreadPoolExecutor (up to 10 threads) with per-request timeout |
| **tiktoken integration** | ✅ | Production-grade token estimation; Grok/Gemini compatible |

---

**Last Updated**: 2026-03-27  
**Version**: 3.1  
**Author**: PM Team