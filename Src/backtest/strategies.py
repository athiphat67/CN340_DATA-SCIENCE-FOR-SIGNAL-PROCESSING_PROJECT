"""
strategies.py — Trading Strategy Definitions for Backtesting
BuyAndHold (benchmark), AIAgent (LLM-based), Technical (RSI+MACD rule-based).
"""

import logging
import os
import sys
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Strategy interface for backtester."""

    @abstractmethod
    def get_signal(self, market_state: dict, portfolio) -> dict:
        """
        Produce a trading signal.

        Returns
        -------
        dict with keys:
            signal     : "BUY" | "SELL" | "HOLD"
            amount_thb : float (for BUY — how much THB to spend)
            grams      : float (for SELL — how many grams to sell)
            rationale  : str
        """
        ...


class BuyAndHoldStrategy(BaseStrategy):
    """
    Benchmark: buy on the first day, hold until the last day.
    The backtester handles force_sell on the last day automatically.
    """

    def __init__(self):
        self._bought = False

    def get_signal(self, market_state: dict, portfolio) -> dict:
        if not self._bought and portfolio.can_buy:
            self._bought = True
            return {
                "signal": "BUY",
                "amount_thb": portfolio.cash_balance,
                "rationale": "Buy-and-Hold: buy on first opportunity",
            }
        return {"signal": "HOLD", "rationale": "Buy-and-Hold: holding position"}


class TechnicalStrategy(BaseStrategy):
    """
    Rule-based strategy using RSI + MACD signals.
    - BUY  when RSI < 35 AND MACD bullish cross
    - SELL when RSI > 65 AND MACD bearish cross
    - HOLD otherwise
    """

    def __init__(self, rsi_buy: float = 35, rsi_sell: float = 65):
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell

    def get_signal(self, market_state: dict, portfolio) -> dict:
        lookback_df = market_state.get("lookback_df")
        if lookback_df is None or len(lookback_df) < 26:
            return {"signal": "HOLD", "rationale": "Insufficient data for indicators"}

        close = lookback_df["close"]

        # RSI (14)
        rsi_val = self._compute_rsi(close, 14)

        # MACD crossover
        macd_cross = self._compute_macd_crossover(close)

        # Decision
        if rsi_val < self.rsi_buy and macd_cross == "bullish" and portfolio.can_buy:
            return {
                "signal": "BUY",
                "amount_thb": portfolio.cash_balance,
                "rationale": f"RSI={rsi_val:.1f}<{self.rsi_buy} + MACD bullish cross",
            }
        elif rsi_val > self.rsi_sell and macd_cross == "bearish" and portfolio.can_sell:
            return {
                "signal": "SELL",
                "grams": portfolio.gold_grams,
                "rationale": f"RSI={rsi_val:.1f}>{self.rsi_sell} + MACD bearish cross",
            }
        return {
            "signal": "HOLD",
            "rationale": f"RSI={rsi_val:.1f}, MACD={macd_cross} — no clear signal",
        }

    @staticmethod
    def _compute_rsi(close: pd.Series, period: int = 14) -> float:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = (100 - (100 / (1 + rs))).fillna(50)
        return float(rsi.iloc[-1])

    @staticmethod
    def _compute_macd_crossover(close: pd.Series) -> str:
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal_line
        if len(hist) < 2:
            return "none"
        prev, curr = hist.iloc[-2], hist.iloc[-1]
        if prev < 0 and curr >= 0:
            return "bullish"
        elif prev > 0 and curr <= 0:
            return "bearish"
        return "none"


class AIAgentStrategy(BaseStrategy):
    """
    Uses the existing LLM ReAct agent to generate trading signals.
    Requires: LLM client, PromptBuilder, ReactOrchestrator from agent_core.
    """

    def __init__(self, provider: str = "mock"):
        self.provider = provider
        self._init_agent()

    def _init_agent(self):
        """Lazy-initialize agent components."""
        src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        data_engine_dir = os.path.join(src_dir, "data_engine")
        if data_engine_dir not in sys.path:
            sys.path.insert(0, data_engine_dir)

        from agent_core.llm.client import LLMClientFactory
        from agent_core.core.react import ReactOrchestrator, ReactConfig
        from agent_core.core.prompt import (
            PromptBuilder,
            RoleRegistry,
            SkillRegistry,
            AIRole,
        )
        from agent_core.core.risk_manager import RiskManager, RiskConfig

        self.llm = LLMClientFactory.create(self.provider)

        skill_registry = SkillRegistry()
        skill_path = os.path.join(src_dir, "agent_core", "config", "skills.json")
        if os.path.exists(skill_path):
            skill_registry.load_from_json(skill_path)

        role_registry = RoleRegistry(skill_registry)
        role_path = os.path.join(src_dir, "agent_core", "config", "roles.json")
        if os.path.exists(role_path):
            role_registry.load_from_json(role_path)

        self.prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)
        self.react = ReactOrchestrator(
            llm_client=self.llm,
            prompt_builder=self.prompt_builder,
            tool_registry={},
            config=ReactConfig(max_iterations=5, max_tool_calls=0),
        )
        self.risk_manager = RiskManager()

    def _compute_price_trend(self, lookback_df) -> dict:
        """Compute recent price trend summary for AI context."""
        if lookback_df is None or len(lookback_df) < 2:
            return {}
        close = lookback_df["close"]
        current_price = float(close.iloc[-1])
        prev_price = float(close.iloc[-2])
        daily_change_pct = ((current_price - prev_price) / prev_price) * 100

        trend_info = {
            "current_close_usd": round(current_price, 2),
            "prev_close_usd": round(prev_price, 2),
            "daily_change_pct": round(daily_change_pct, 2),
        }

        # 5-day trend if available
        if len(close) >= 5:
            price_5d_ago = float(close.iloc[-5])
            trend_info["5d_change_pct"] = round(
                ((current_price - price_5d_ago) / price_5d_ago) * 100, 2
            )

        # 10-day trend if available
        if len(close) >= 10:
            price_10d_ago = float(close.iloc[-10])
            trend_info["10d_change_pct"] = round(
                ((current_price - price_10d_ago) / price_10d_ago) * 100, 2
            )

        # Recent highs/lows
        window = close.iloc[-min(10, len(close)) :]
        trend_info["10d_high"] = round(float(window.max()), 2)
        trend_info["10d_low"] = round(float(window.min()), 2)

        return trend_info

    def get_signal(self, market_state: dict, portfolio) -> dict:
        """Run the AI agent on market_state to get a signal."""
        # Build agent-compatible market_state
        current = market_state.get("current", {})
        lookback_df = market_state.get("lookback_df")

        # Compute price trend for richer context
        price_trend = self._compute_price_trend(lookback_df)

        agent_state = {
            "market_data": {
                "spot_price_usd": {
                    "price_usd_per_oz": current.get("close", 0),
                    "source": "backtest",
                },
                "forex": {"usd_thb": current.get("usd_thb", 0)},
                "thai_gold_thb": {
                    "buy_price_thb": current.get("thai_gold_buy_thb", 0),
                    "sell_price_thb": current.get("thai_gold_sell_thb", 0),
                },
                "price_trend": price_trend,
            },
            "technical_indicators": {},
            "news": {"summary": {}, "by_category": {}},
            "portfolio": {
                "cash_balance": portfolio.cash_balance,
                "gold_grams": portfolio.gold_grams,
                "cost_basis_thb": portfolio.cost_basis_thb,
                "unrealized_pnl": 0.0,
                "trades_today": 0,
            },
            "backtest_directive": (
                "You are in BACKTEST mode. You MUST make a decisive trading call. "
                "Analyze the technical indicators and price trend carefully. "
                "If RSI < 40 or price is near 10d low with bullish momentum, signal BUY. "
                "If RSI > 60 or price is near 10d high with bearish momentum, signal SELL. "
                "Only signal HOLD if indicators are truly mixed with no clear direction. "
                "Do NOT default to HOLD out of caution — this is a backtest, not real money."
            ),
        }

        # Compute indicators if lookback data available
        if lookback_df is not None and len(lookback_df) >= 26:
            try:
                src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                sys.path.insert(0, os.path.join(src_dir, "data_engine"))
                from indicators import TechnicalIndicators

                calc = TechnicalIndicators(lookback_df)
                agent_state["technical_indicators"] = calc.to_dict()
            except Exception as e:
                logger.warning(f"Failed to compute indicators: {e}")

        try:
            result = self.react.run(agent_state)
            raw_decision = result.get("final_decision", {})

            # Use RiskManager to validate
            current_price = current.get("close", 0)
            validated_decision = self.risk_manager.validate_and_adjust(
                decision=raw_decision,
                portfolio_state=agent_state["portfolio"],
                current_price=current_price,
            )

            signal = validated_decision.get("signal", "HOLD").upper()
            if signal not in ("BUY", "SELL", "HOLD"):
                signal = "HOLD"

            out = {
                "signal": signal,
                "rationale": validated_decision.get("rationale", ""),
            }
            if validated_decision.get("risk_adjusted"):
                risk_notes = "; ".join(validated_decision.get("risk_notes", []))
                out["rationale"] = f"{out['rationale']} [Risk Adj: {risk_notes}]"

            if signal == "BUY":
                out["amount_thb"] = validated_decision.get(
                    "amount_thb", portfolio.cash_balance
                )
            elif signal == "SELL":
                out["grams"] = validated_decision.get("grams", portfolio.gold_grams)
            return out

        except Exception as e:
            logger.error(f"AI Agent error: {e}")
            return {"signal": "HOLD", "rationale": f"Error: {str(e)}"}
