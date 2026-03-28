"""
metrics.py — Performance Metrics Calculator for Backtesting
Computes: total_signals, win_rate, avg_rr, total_pnl, max_drawdown, sharpe_ratio, sortino_ratio.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class PerformanceMetrics:
    """Container for all backtest performance metrics."""
    # Signal counts
    total_signals: int = 0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0

    # Trade performance
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # Risk-reward
    avg_rr: float = 0.0  # Average Risk-Reward Ratio

    # PnL
    total_pnl_thb: float = 0.0
    total_return_pct: float = 0.0

    # Drawdown
    max_drawdown_pct: float = 0.0
    max_drawdown_thb: float = 0.0

    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Additional
    avg_trade_pnl: float = 0.0
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    profit_factor: float = 0.0


def compute_metrics(
    trades: list,
    snapshots: list,
    initial_capital: float = 1500.0,
    risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    """
    Compute all performance metrics from backtest results.

    Parameters
    ----------
    trades : list[Trade]
        List of executed trades from backtester.
    snapshots : list[DailySnapshot]
        Daily portfolio snapshots.
    initial_capital : float
        Starting capital in THB.
    risk_free_rate : float
        Annualized risk-free rate (default 0 for short-term).

    Returns
    -------
    PerformanceMetrics
    """
    m = PerformanceMetrics()

    if not snapshots:
        return m

    # ── Signal counts ────────────────────────────────────────────────────────
    for snap in snapshots:
        m.total_signals += 1
        sig = snap.signal.upper()
        if sig == "BUY":
            m.buy_count += 1
        elif sig in ("SELL", "FORCE_SELL"):
            m.sell_count += 1
        else:
            m.hold_count += 1

    # ── Trade PnL (pair BUY → SELL) ──────────────────────────────────────────
    trade_pnls = _compute_trade_pnls(trades)
    m.total_trades = len(trade_pnls)

    if trade_pnls:
        m.winning_trades = sum(1 for p in trade_pnls if p > 0)
        m.losing_trades = sum(1 for p in trade_pnls if p < 0)
        m.win_rate = m.winning_trades / m.total_trades if m.total_trades > 0 else 0.0
        m.avg_trade_pnl = sum(trade_pnls) / len(trade_pnls)
        m.best_trade_pnl = max(trade_pnls)
        m.worst_trade_pnl = min(trade_pnls)

        # Profit Factor
        gross_profit = sum(p for p in trade_pnls if p > 0)
        gross_loss = abs(sum(p for p in trade_pnls if p < 0))
        m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # ── Average Risk-Reward Ratio ────────────────────────────────────────────
    m.avg_rr = _compute_avg_rr(trade_pnls)

    # ── Total PnL ────────────────────────────────────────────────────────────
    final_value = snapshots[-1].total_value
    m.total_pnl_thb = final_value - initial_capital
    m.total_return_pct = (m.total_pnl_thb / initial_capital) * 100 if initial_capital > 0 else 0.0

    # ── Max Drawdown ─────────────────────────────────────────────────────────
    portfolio_values = [s.total_value for s in snapshots]
    m.max_drawdown_pct, m.max_drawdown_thb = _compute_max_drawdown(portfolio_values)

    # ── Daily returns for Sharpe / Sortino ───────────────────────────────────
    daily_returns = _compute_daily_returns(portfolio_values)

    if len(daily_returns) > 1:
        m.sharpe_ratio = _compute_sharpe(daily_returns, risk_free_rate)
        m.sortino_ratio = _compute_sortino(daily_returns, risk_free_rate)

    return m


def _compute_trade_pnls(trades: list) -> list[float]:
    """
    Pair BUY→SELL trades and compute PnL for each round-trip.
    Uses FIFO matching.
    """
    buy_queue = []  # [(grams, cost_per_gram)]
    pnls = []

    for t in trades:
        if t.action == "BUY":
            buy_queue.append((t.gold_grams, t.price_per_gram))
        elif t.action == "SELL":
            remaining_sell = t.gold_grams
            sell_price = t.price_per_gram
            round_pnl = 0.0

            while remaining_sell > 1e-10 and buy_queue:
                buy_grams, buy_price = buy_queue[0]
                matched = min(remaining_sell, buy_grams)
                round_pnl += matched * (sell_price - buy_price)
                remaining_sell -= matched

                if matched >= buy_grams - 1e-10:
                    buy_queue.pop(0)
                else:
                    buy_queue[0] = (buy_grams - matched, buy_price)

            pnls.append(round_pnl)

    return pnls


def _compute_avg_rr(trade_pnls: list[float]) -> float:
    """Average Risk-Reward Ratio: avg_win / avg_loss."""
    wins = [p for p in trade_pnls if p > 0]
    losses = [abs(p) for p in trade_pnls if p < 0]
    if not wins or not losses:
        return 0.0
    avg_win = sum(wins) / len(wins)
    avg_loss = sum(losses) / len(losses)
    return avg_win / avg_loss if avg_loss > 0 else float("inf")


def _compute_max_drawdown(values: list[float]) -> tuple[float, float]:
    """
    Compute maximum drawdown.
    Returns (max_drawdown_pct, max_drawdown_thb).
    """
    if not values:
        return 0.0, 0.0

    peak = values[0]
    max_dd_pct = 0.0
    max_dd_thb = 0.0

    for v in values:
        if v > peak:
            peak = v
        dd_thb = peak - v
        dd_pct = (dd_thb / peak) * 100 if peak > 0 else 0.0
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
            max_dd_thb = dd_thb

    return round(max_dd_pct, 4), round(max_dd_thb, 2)


def _compute_daily_returns(values: list[float]) -> list[float]:
    """Compute daily percentage returns from portfolio values."""
    if len(values) < 2:
        return []
    returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            r = (values[i] - values[i - 1]) / values[i - 1]
            returns.append(r)
    return returns


def _compute_sharpe(daily_returns: list[float], risk_free_rate: float = 0.0) -> float:
    """
    Sharpe Ratio (annualized from daily returns).
    Sharpe = (mean_return - rf) / std_return * sqrt(252)
    """
    if not daily_returns:
        return 0.0
    arr = np.array(daily_returns)
    mean_r = arr.mean()
    std_r = arr.std(ddof=1)
    if std_r == 0:
        return 0.0
    daily_rf = risk_free_rate / 252
    sharpe = (mean_r - daily_rf) / std_r * math.sqrt(252)
    return round(sharpe, 4)


def _compute_sortino(daily_returns: list[float], risk_free_rate: float = 0.0) -> float:
    """
    Sortino Ratio (annualized, only downside deviation).
    Sortino = (mean_return - rf) / downside_std * sqrt(252)
    """
    if not daily_returns:
        return 0.0
    arr = np.array(daily_returns)
    mean_r = arr.mean()
    daily_rf = risk_free_rate / 252
    downside = arr[arr < daily_rf]
    if len(downside) == 0:
        return float("inf") if mean_r > daily_rf else 0.0
    downside_std = downside.std(ddof=1)
    if downside_std == 0:
        return 0.0
    sortino = (mean_r - daily_rf) / downside_std * math.sqrt(252)
    return round(sortino, 4)
