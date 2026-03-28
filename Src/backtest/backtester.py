"""
backtester.py — Core Backtest Engine
SimulatedPortfolio (ออม NOW constraints) + Backtester day-by-day loop.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ออม NOW constraints
MIN_BUY_THB = 1000.0  # ขั้นต่ำซื้อทอง
DEFAULT_FEE_PCT = 0.0025  # 0.25% transaction fee (ออม NOW spread simulation)


@dataclass
class Trade:
    """Record of a single trade."""

    date: str
    action: str  # "BUY" | "SELL"
    amount_thb: float  # จำนวนเงินที่ใช้ซื้อ / ได้จากขาย
    gold_grams: float  # จำนวนกรัมที่ซื้อ / ขาย
    price_per_gram: float
    cash_after: float
    gold_after: float
    rationale: str = ""


@dataclass
class DailySnapshot:
    """Portfolio snapshot at end of each day."""

    date: str
    cash_balance: float
    gold_grams: float
    gold_value_thb: float  # มูลค่าทองที่ถือ (ราคาขาย ณ วันนั้น)
    total_value: float  # cash + gold_value
    signal: str  # signal ที่ได้รับวันนั้น
    trade_executed: bool


@dataclass
class VCSettlement:
    """VC settlement calculation."""

    initial_capital: float
    final_balance: float
    profit_loss: float
    is_profit: bool
    return_to_vc: float
    keep_profit: float

    def summary(self) -> str:
        if self.is_profit:
            return (
                f"กำไร ฿{self.profit_loss:,.2f} → "
                f"คืน VC: ฿{self.return_to_vc:,.2f} (ทุน ฿{self.initial_capital:,.2f} + 50% กำไร ฿{self.profit_loss / 2:,.2f})"
            )
        else:
            return (
                f"ขาดทุน ฿{abs(self.profit_loss):,.2f} → "
                f"คืน VC ทั้งหมด: ฿{self.return_to_vc:,.2f}"
            )


class SimulatedPortfolio:
    """
    Simulates a portfolio on ออม NOW platform.
    Constraints: min buy ฿1,000, trades in grams.
    """

    def __init__(self, initial_capital: float = 1500.0):
        self.initial_capital = initial_capital
        self.cash_balance = initial_capital
        self.gold_grams = 0.0
        self.cost_basis_thb = 0.0  # ต้นทุนทองที่ถืออยู่
        self.trades: list[Trade] = []

    @property
    def can_buy(self) -> bool:
        return self.cash_balance >= MIN_BUY_THB

    @property
    def can_sell(self) -> bool:
        return self.gold_grams > 0

    def buy(
        self,
        amount_thb: float,
        price_per_gram: float,
        date: str = "",
        rationale: str = "",
        fee_pct: float = 0.0,
    ) -> Optional[Trade]:
        """
        Buy gold with specified THB amount.
        Returns Trade if successful, None if constraints not met.
        fee_pct: transaction fee percentage (e.g. 0.0025 = 0.25%)
        """
        if amount_thb < MIN_BUY_THB:
            logger.debug(f"Buy rejected: ฿{amount_thb:.2f} < min ฿{MIN_BUY_THB}")
            return None
        if amount_thb > self.cash_balance:
            amount_thb = self.cash_balance  # ใช้เงินทั้งหมดที่มี
        if amount_thb < MIN_BUY_THB:
            return None

        # Deduct fee from effective buying power
        effective_amount = amount_thb * (1 - fee_pct)
        grams = effective_amount / price_per_gram
        self.cash_balance -= amount_thb
        self.gold_grams += grams
        self.cost_basis_thb += amount_thb

        trade = Trade(
            date=date,
            action="BUY",
            amount_thb=amount_thb,
            gold_grams=grams,
            price_per_gram=price_per_gram,
            cash_after=self.cash_balance,
            gold_after=self.gold_grams,
            rationale=rationale,
        )
        self.trades.append(trade)
        logger.info(
            f"[{date}] BUY {grams:.4f}g @ ฿{price_per_gram:.2f}/g = ฿{amount_thb:.2f}"
        )
        return trade

    def sell(
        self,
        grams: float,
        price_per_gram: float,
        date: str = "",
        rationale: str = "",
        fee_pct: float = 0.0,
    ) -> Optional[Trade]:
        """
        Sell specified grams of gold.
        Returns Trade if successful, None if no gold to sell.
        fee_pct: transaction fee percentage (e.g. 0.0025 = 0.25%)
        """
        if self.gold_grams <= 0:
            return None
        grams = min(grams, self.gold_grams)
        # Deduct fee from sale proceeds
        amount_thb = grams * price_per_gram * (1 - fee_pct)

        # Adjust cost basis proportionally
        if self.gold_grams > 0:
            ratio = grams / self.gold_grams
            self.cost_basis_thb -= self.cost_basis_thb * ratio

        self.cash_balance += amount_thb
        self.gold_grams -= grams

        # Fix floating point
        if self.gold_grams < 1e-10:
            self.gold_grams = 0.0
            self.cost_basis_thb = 0.0

        trade = Trade(
            date=date,
            action="SELL",
            amount_thb=amount_thb,
            gold_grams=grams,
            price_per_gram=price_per_gram,
            cash_after=self.cash_balance,
            gold_after=self.gold_grams,
            rationale=rationale,
        )
        self.trades.append(trade)
        logger.info(
            f"[{date}] SELL {grams:.4f}g @ ฿{price_per_gram:.2f}/g = ฿{amount_thb:.2f}"
        )
        return trade

    def force_sell_all(self, price_per_gram: float, date: str = "") -> Optional[Trade]:
        """Sell all remaining gold (last day settlement)."""
        if self.gold_grams <= 0:
            return None
        return self.sell(
            self.gold_grams, price_per_gram, date, rationale="Force sell — last day"
        )

    def get_total_value(self, sell_price_per_gram: float) -> float:
        """Total portfolio value = cash + gold value at sell price."""
        return self.cash_balance + (self.gold_grams * sell_price_per_gram)

    def compute_vc_settlement(self, final_balance: float) -> VCSettlement:
        """
        Compute VC settlement per project rules:
        - Profit → return ฿1,500 capital + 50% of profit to VC
        - Loss → return all remaining balance to VC
        """
        pnl = final_balance - self.initial_capital
        is_profit = pnl > 0

        if is_profit:
            return_to_vc = self.initial_capital + (pnl * 0.5)
            keep = pnl * 0.5
        else:
            return_to_vc = final_balance
            keep = 0.0

        return VCSettlement(
            initial_capital=self.initial_capital,
            final_balance=final_balance,
            profit_loss=pnl,
            is_profit=is_profit,
            return_to_vc=return_to_vc,
            keep_profit=keep,
        )


class Backtester:
    """
    Runs a strategy day-by-day on historical data.

    Parameters
    ----------
    data : pd.DataFrame
        Must have columns: sell_per_gram, buy_per_gram (from data_loader)
    strategy : object
        Must implement get_signal(market_state, portfolio) → dict
    initial_capital : float
    """

    def __init__(
        self,
        data: pd.DataFrame,
        strategy,
        initial_capital: float = 1500.0,
        fee_pct: float = DEFAULT_FEE_PCT,
    ):
        self.data = data
        self.strategy = strategy
        self.portfolio = SimulatedPortfolio(initial_capital)
        self.fee_pct = fee_pct
        self.snapshots: list[DailySnapshot] = []
        self._pending_signal: Optional[dict] = None  # next-day execution buffer
        self._is_run = False

    def run(self) -> dict:
        """
        Execute backtest. Returns result dict with trades, snapshots, settlement.
        """
        dates = self.data.index.tolist()
        last_day = dates[-1]

        for i, date in enumerate(dates):
            row = self.data.loc[date]
            date_str = str(date.date()) if hasattr(date, "date") else str(date)
            is_last_day = date == last_day

            # ── Step A: Execute PENDING signal from yesterday (next-day execution) ──
            trade_executed = False
            executed_signal = "HOLD"
            buy_price = row["buy_per_gram"]
            sell_price = row["sell_per_gram"]

            if self._pending_signal is not None:
                ps = self._pending_signal
                executed_signal = ps.get("signal", "HOLD")
                rationale = ps.get("rationale", "")

                if executed_signal == "BUY" and self.portfolio.can_buy:
                    amount = ps.get("amount_thb", self.portfolio.cash_balance)
                    amount = min(amount, self.portfolio.cash_balance)
                    trade = self.portfolio.buy(
                        amount, buy_price, date_str, rationale, self.fee_pct
                    )
                    trade_executed = trade is not None

                elif executed_signal == "SELL" and self.portfolio.can_sell:
                    grams = ps.get("grams", self.portfolio.gold_grams)
                    trade = self.portfolio.sell(
                        grams, sell_price, date_str, rationale, self.fee_pct
                    )
                    trade_executed = trade is not None

                self._pending_signal = None

            # ── Step B: Force sell on last day ──
            if is_last_day and self.portfolio.gold_grams > 0:
                self.portfolio.force_sell_all(sell_price, date_str)
                self.snapshots.append(
                    DailySnapshot(
                        date=date_str,
                        cash_balance=self.portfolio.cash_balance,
                        gold_grams=self.portfolio.gold_grams,
                        gold_value_thb=0.0,
                        total_value=self.portfolio.cash_balance,
                        signal="FORCE_SELL",
                        trade_executed=True,
                    )
                )
                continue

            # ── Step C: Strategy decides using TODAY's data → queued for TOMORROW ──
            market_state = self._build_market_state(date, i)
            signal_result = self.strategy.get_signal(market_state, self.portfolio)
            today_signal = signal_result.get("signal", "HOLD")

            # Queue signal for next-day execution
            if today_signal in ("BUY", "SELL"):
                self._pending_signal = signal_result

            # ── Step D: Daily snapshot (reflects execution + valuation) ──
            gold_value = self.portfolio.gold_grams * sell_price
            display_signal = executed_signal if trade_executed else today_signal
            self.snapshots.append(
                DailySnapshot(
                    date=date_str,
                    cash_balance=self.portfolio.cash_balance,
                    gold_grams=self.portfolio.gold_grams,
                    gold_value_thb=gold_value,
                    total_value=self.portfolio.cash_balance + gold_value,
                    signal=display_signal,
                    trade_executed=trade_executed,
                )
            )

        # Settlement
        final_balance = self.portfolio.cash_balance
        settlement = self.portfolio.compute_vc_settlement(final_balance)

        self._is_run = True
        return {
            "trades": self.portfolio.trades,
            "snapshots": self.snapshots,
            "settlement": settlement,
            "final_balance": final_balance,
            "initial_capital": self.portfolio.initial_capital,
        }

    def _build_market_state(self, date, index: int) -> dict:
        """Build a market_state dict from historical data for the strategy."""
        row = self.data.loc[date]
        # Provide lookback window for indicators
        lookback = self.data.iloc[max(0, index - 99) : index + 1]

        return {
            "date": str(date.date()) if hasattr(date, "date") else str(date),
            "current": {
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "usd_thb": float(row["usd_thb"]),
                "buy_per_gram": float(row["buy_per_gram"]),
                "sell_per_gram": float(row["sell_per_gram"]),
                "thai_gold_buy_thb": float(row["thai_gold_buy_thb"]),
                "thai_gold_sell_thb": float(row["thai_gold_sell_thb"]),
            },
            "lookback_df": lookback,
        }
