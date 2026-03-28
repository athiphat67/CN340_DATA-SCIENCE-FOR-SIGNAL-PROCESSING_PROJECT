"""
test_metrics.py — Unit tests for backtest performance metrics.
Tests: drawdown, Sharpe/Sortino, FIFO PnL matching, and edge cases.
"""

import math

import pytest

from backtest.backtester import DailySnapshot, Trade
from backtest.metrics import _compute_max_drawdown, _compute_trade_pnls, compute_metrics


def _trade(action: str, grams: float, price_per_gram: float) -> Trade:
    """Create a minimal Trade suitable for metrics tests."""
    amount_thb = grams * price_per_gram
    return Trade(
        date="2025-01-01",
        action=action,
        amount_thb=amount_thb,
        gold_grams=grams,
        price_per_gram=price_per_gram,
        cash_after=0.0,
        gold_after=0.0,
        rationale="test",
    )


def _snapshot(total_value: float, signal: str = "HOLD") -> DailySnapshot:
    """Create a minimal DailySnapshot with a given total value."""
    return DailySnapshot(
        date="2025-01-01",
        cash_balance=total_value,
        gold_grams=0.0,
        gold_value_thb=0.0,
        total_value=total_value,
        signal=signal,
        trade_executed=False,
    )


def test_max_drawdown_flat_portfolio():
    max_drawdown_pct, max_drawdown_thb = _compute_max_drawdown(
        [1500.0, 1500.0, 1500.0]
    )

    assert max_drawdown_pct == pytest.approx(0.0)
    assert max_drawdown_thb == pytest.approx(0.0)


def test_max_drawdown_known_values():
    max_drawdown_pct, max_drawdown_thb = _compute_max_drawdown(
        [1500.0, 1450.0, 1500.0]
    )

    assert max_drawdown_pct == pytest.approx(3.3333)
    assert max_drawdown_thb == pytest.approx(50.0)


def test_sharpe_positive_for_positive_returns():
    metrics = compute_metrics(
        trades=[],
        snapshots=[
            _snapshot(1500.0),
            _snapshot(1515.0),
            _snapshot(1545.0),
            _snapshot(1560.0),
        ],
    )

    assert metrics.sharpe_ratio > 0


def test_sortino_higher_than_sharpe_no_downside():
    metrics = compute_metrics(
        trades=[],
        snapshots=[
            _snapshot(1500.0),
            _snapshot(1510.0),
            _snapshot(1530.0),
            _snapshot(1540.0),
        ],
    )

    assert math.isinf(metrics.sortino_ratio)
    assert metrics.sortino_ratio > metrics.sharpe_ratio


def test_fifo_matching_two_trades():
    pnls = _compute_trade_pnls(
        [
            _trade("BUY", grams=100.0, price_per_gram=10.0),
            _trade("SELL", grams=100.0, price_per_gram=12.0),
        ]
    )

    assert pnls == pytest.approx([200.0])


def test_fifo_matching_partial_sell():
    pnls = _compute_trade_pnls(
        [
            _trade("BUY", grams=100.0, price_per_gram=10.0),
            _trade("SELL", grams=50.0, price_per_gram=12.0),
        ]
    )

    assert pnls == pytest.approx([100.0])


def test_empty_trades_returns_zero_metrics():
    metrics = compute_metrics(trades=[], snapshots=[])

    assert metrics.total_signals == 0
    assert metrics.total_trades == 0
    assert metrics.total_pnl_thb == pytest.approx(0.0)
    assert metrics.max_drawdown_pct == pytest.approx(0.0)
    assert metrics.profit_factor == pytest.approx(0.0)


def test_all_losing_trades_profit_factor_zero():
    metrics = compute_metrics(
        trades=[
            _trade("BUY", grams=100.0, price_per_gram=10.0),
            _trade("SELL", grams=100.0, price_per_gram=8.0),
        ],
        snapshots=[_snapshot(1300.0)],
    )

    assert metrics.total_trades == 1
    assert metrics.losing_trades == 1
    assert metrics.profit_factor == pytest.approx(0.0)


def test_all_winning_trades_profit_factor_infinite():
    metrics = compute_metrics(
        trades=[
            _trade("BUY", grams=100.0, price_per_gram=10.0),
            _trade("SELL", grams=100.0, price_per_gram=12.0),
        ],
        snapshots=[_snapshot(1700.0)],
    )

    assert metrics.total_trades == 1
    assert metrics.winning_trades == 1
    assert math.isinf(metrics.profit_factor)
