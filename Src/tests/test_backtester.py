"""
test_backtester.py — Unit tests for the backtest engine core.
Tests: SimulatedPortfolio constraints, VC settlement, next-day execution,
       Buy-and-Hold behavior, and forced liquidation on the last day.
"""

import pandas as pd
import pytest

from backtest.backtester import Backtester, MIN_BUY_THB, SimulatedPortfolio
from backtest.strategies import BuyAndHoldStrategy


def _make_backtest_df(
    buy_prices: list[float],
    sell_prices: list[float] | None = None,
) -> pd.DataFrame:
    """Create a minimal price DataFrame accepted by Backtester."""
    if sell_prices is None:
        sell_prices = buy_prices

    dates = pd.date_range("2025-01-01", periods=len(buy_prices), freq="D")
    close_prices = [(buy + sell) / 2 for buy, sell in zip(buy_prices, sell_prices)]

    return pd.DataFrame(
        {
            "open": close_prices,
            "high": [price + 1 for price in close_prices],
            "low": [price - 1 for price in close_prices],
            "close": close_prices,
            "usd_thb": [35.0] * len(buy_prices),
            "buy_per_gram": buy_prices,
            "sell_per_gram": sell_prices,
            "thai_gold_buy_thb": [price * 15.244 for price in buy_prices],
            "thai_gold_sell_thb": [price * 15.244 for price in sell_prices],
        },
        index=dates,
    )


class SequenceStrategy:
    """Return a predefined signal sequence, then HOLD."""

    def __init__(self, signals: list[dict]):
        self.signals = list(signals)
        self.calls: list[str] = []

    def get_signal(self, market_state: dict, portfolio) -> dict:
        self.calls.append(market_state["date"])
        if self.signals:
            return self.signals.pop(0)
        return {"signal": "HOLD", "rationale": "No more signals"}


def test_buy_below_minimum_rejected():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)

    trade = portfolio.buy(999.0, price_per_gram=100.0)

    assert trade is None
    assert portfolio.cash_balance == 1500.0
    assert portfolio.gold_grams == 0.0
    assert portfolio.cost_basis_thb == 0.0
    assert portfolio.trades == []


def test_buy_at_minimum_accepted():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)

    trade = portfolio.buy(MIN_BUY_THB, price_per_gram=100.0)

    assert trade is not None
    assert trade.amount_thb == MIN_BUY_THB
    assert portfolio.cash_balance == pytest.approx(500.0)
    assert portfolio.gold_grams == pytest.approx(10.0)
    assert portfolio.cost_basis_thb == pytest.approx(MIN_BUY_THB)


def test_buy_more_than_cash_uses_all_cash():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)

    trade = portfolio.buy(9999.0, price_per_gram=100.0)

    assert trade is not None
    assert trade.amount_thb == pytest.approx(1500.0)
    assert portfolio.cash_balance == pytest.approx(0.0)
    assert portfolio.gold_grams == pytest.approx(15.0)
    assert portfolio.cost_basis_thb == pytest.approx(1500.0)


def test_sell_zero_gold_returns_none():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)

    trade = portfolio.sell(grams=1.0, price_per_gram=100.0)

    assert trade is None
    assert portfolio.cash_balance == 1500.0
    assert portfolio.gold_grams == 0.0


def test_sell_partial_grams():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)
    portfolio.buy(1000.0, price_per_gram=100.0, fee_pct=0.0)

    trade = portfolio.sell(grams=4.0, price_per_gram=120.0, fee_pct=0.0)

    assert trade is not None
    assert trade.amount_thb == pytest.approx(480.0)
    assert portfolio.cash_balance == pytest.approx(980.0)
    assert portfolio.gold_grams == pytest.approx(6.0)
    assert portfolio.cost_basis_thb == pytest.approx(600.0)


def test_force_sell_all_clears_position():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)
    portfolio.buy(1000.0, price_per_gram=100.0, fee_pct=0.0)

    trade = portfolio.force_sell_all(price_per_gram=110.0, date="2025-01-03")

    assert trade is not None
    assert trade.action == "SELL"
    assert trade.rationale == "Force sell — last day"
    assert portfolio.cash_balance == pytest.approx(1600.0)
    assert portfolio.gold_grams == 0.0
    assert portfolio.cost_basis_thb == 0.0


def test_vc_settlement_profit_splits_50_50():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)

    settlement = portfolio.compute_vc_settlement(final_balance=1800.0)

    assert settlement.is_profit is True
    assert settlement.profit_loss == pytest.approx(300.0)
    assert settlement.return_to_vc == pytest.approx(1650.0)
    assert settlement.keep_profit == pytest.approx(150.0)


def test_vc_settlement_loss_returns_all():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)

    settlement = portfolio.compute_vc_settlement(final_balance=1200.0)

    assert settlement.is_profit is False
    assert settlement.profit_loss == pytest.approx(-300.0)
    assert settlement.return_to_vc == pytest.approx(1200.0)
    assert settlement.keep_profit == pytest.approx(0.0)


def test_vc_settlement_zero_pnl():
    portfolio = SimulatedPortfolio(initial_capital=1500.0)

    settlement = portfolio.compute_vc_settlement(final_balance=1500.0)

    assert settlement.is_profit is False
    assert settlement.profit_loss == pytest.approx(0.0)
    assert settlement.return_to_vc == pytest.approx(1500.0)
    assert settlement.keep_profit == pytest.approx(0.0)


def test_next_day_execution_no_lookahead():
    data = _make_backtest_df([100.0, 110.0, 120.0], [99.0, 109.0, 119.0])
    strategy = SequenceStrategy(
        [
            {"signal": "BUY", "amount_thb": 1500.0, "rationale": "Buy today"},
            {"signal": "HOLD", "rationale": "Hold"},
        ]
    )
    result = Backtester(data, strategy, initial_capital=1500.0, fee_pct=0.0).run()

    first_snapshot = result["snapshots"][0]
    second_snapshot = result["snapshots"][1]
    buy_trade = result["trades"][0]

    assert first_snapshot.trade_executed is False
    assert first_snapshot.signal == "BUY"
    assert first_snapshot.gold_grams == 0.0

    assert second_snapshot.trade_executed is True
    assert buy_trade.date == "2025-01-02"
    assert buy_trade.price_per_gram == pytest.approx(110.0)
    assert buy_trade.gold_grams == pytest.approx(1500.0 / 110.0)


def test_buyandhold_buys_on_first_day():
    data = _make_backtest_df([100.0, 105.0, 110.0], [99.0, 104.0, 109.0])
    result = Backtester(
        data,
        BuyAndHoldStrategy(),
        initial_capital=1500.0,
        fee_pct=0.0,
    ).run()

    first_snapshot = result["snapshots"][0]
    first_trade = result["trades"][0]

    assert first_snapshot.date == "2025-01-01"
    assert first_snapshot.signal == "BUY"
    assert first_snapshot.trade_executed is False
    assert first_trade.action == "BUY"
    assert first_trade.date == "2025-01-02"


def test_force_sell_on_last_day():
    data = _make_backtest_df([100.0, 110.0, 120.0], [99.0, 109.0, 119.0])
    strategy = SequenceStrategy(
        [
            {"signal": "BUY", "amount_thb": 1500.0, "rationale": "Enter"},
            {"signal": "HOLD", "rationale": "Hold"},
        ]
    )
    result = Backtester(data, strategy, initial_capital=1500.0, fee_pct=0.0).run()

    last_snapshot = result["snapshots"][-1]
    last_trade = result["trades"][-1]

    assert last_snapshot.date == "2025-01-03"
    assert last_snapshot.signal == "FORCE_SELL"
    assert last_snapshot.trade_executed is True
    assert last_trade.action == "SELL"
    assert last_trade.rationale == "Force sell — last day"
    assert result["final_balance"] == pytest.approx((1500.0 / 110.0) * 119.0)
    assert strategy.calls == ["2025-01-01", "2025-01-02"]
