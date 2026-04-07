"""
test_calculator.py — Pytest สำหรับทดสอบ calculate_trade_metrics + add_calmar

Strategy: 100% Real (ไม่มี mock)
- ฟังก์ชันรับ list ของ ClosedTrade objects → คืน dict
- ไม่มี I/O ใดๆ ทั้งสิ้น
- ใช้ mock ClosedTrade objects (lightweight dataclass แทน import จริง)

ครอบคลุม:
  1. Empty trades → default dict
  2. All wins / All losses
  3. Mixed trades → win_rate, profit_factor, expectancy
  4. Consecutive streaks (max_consec_wins, max_consec_losses)
  5. Edge cases — 1 trade, inf profit_factor
  6. add_calmar — calmar_ratio คำนวณถูก
"""

import pytest
from dataclasses import dataclass

from backtest.metrics.calculator import calculate_trade_metrics, add_calmar


# ══════════════════════════════════════════════════════════════════
# Mock ClosedTrade — lightweight version สำหรับ test
# ══════════════════════════════════════════════════════════════════


@dataclass
class MockTrade:
    """
    จำลอง ClosedTrade — ต้องมี .pnl_thb, .cost_thb, .is_win
    เหตุผลที่ไม่ import ClosedTrade จริง: ClosedTrade ต้องการ fields เยอะ
    (entry_price, exit_price, gold_grams...) ซึ่งไม่จำเป็นสำหรับ calculator
    """

    pnl_thb: float
    cost_thb: float = 6.0  # default = 2 * commission
    is_win: bool = False

    def __post_init__(self):
        self.is_win = self.pnl_thb > 0


def _make_trades(*pnl_list, cost=6.0):
    """สร้าง list ของ MockTrade จาก PnL values"""
    return [MockTrade(pnl_thb=pnl, cost_thb=cost) for pnl in pnl_list]


# ══════════════════════════════════════════════════════════════════
# 1. Empty Trades
# ══════════════════════════════════════════════════════════════════


class TestEmptyTrades:
    """ไม่มี trade เลย → ต้องคืน default dict ที่เป็น 0 ทั้งหมด"""

    def test_returns_dict(self):
        result = calculate_trade_metrics([])
        assert isinstance(result, dict)

    def test_zero_counts(self):
        result = calculate_trade_metrics([])
        assert result["total_trades"] == 0
        assert result["winning_trades"] == 0
        assert result["losing_trades"] == 0

    def test_zero_rates(self):
        result = calculate_trade_metrics([])
        assert result["win_rate_pct"] == 0.0
        assert result["profit_factor"] == 0.0
        assert result["expectancy_thb"] == 0.0

    def test_has_note(self):
        result = calculate_trade_metrics([])
        assert "note" in result


# ══════════════════════════════════════════════════════════════════
# 2. All Wins
# ══════════════════════════════════════════════════════════════════


class TestAllWins:
    """Trade ทั้งหมดเป็น win"""

    def test_win_rate_100(self):
        trades = _make_trades(100, 50, 200)
        result = calculate_trade_metrics(trades)
        assert result["win_rate_pct"] == 100.0
        assert result["winning_trades"] == 3
        assert result["losing_trades"] == 0

    def test_profit_factor_inf(self):
        """ไม่มี loss → profit_factor = inf"""
        trades = _make_trades(100, 50)
        result = calculate_trade_metrics(trades)
        assert result["profit_factor"] == float("inf")

    def test_avg_loss_zero(self):
        trades = _make_trades(100, 50)
        result = calculate_trade_metrics(trades)
        assert result["avg_loss_thb"] == 0.0

    def test_max_consec_wins(self):
        trades = _make_trades(10, 20, 30)
        result = calculate_trade_metrics(trades)
        assert result["max_consec_wins"] == 3
        assert result["max_consec_losses"] == 0


# ══════════════════════════════════════════════════════════════════
# 3. All Losses
# ══════════════════════════════════════════════════════════════════


class TestAllLosses:
    """Trade ทั้งหมดเป็น loss"""

    def test_win_rate_0(self):
        trades = _make_trades(-100, -50, -200)
        result = calculate_trade_metrics(trades)
        assert result["win_rate_pct"] == 0.0
        assert result["winning_trades"] == 0

    def test_profit_factor_zero(self):
        """ไม่มี win → gross_profit = 0 → profit_factor = 0"""
        trades = _make_trades(-100, -50)
        result = calculate_trade_metrics(trades)
        assert result["profit_factor"] == 0.0

    def test_net_pnl_negative(self):
        trades = _make_trades(-100, -50)
        result = calculate_trade_metrics(trades)
        assert result["net_pnl_thb"] == -150.0

    def test_max_consec_losses(self):
        trades = _make_trades(-10, -20, -30, -5)
        result = calculate_trade_metrics(trades)
        assert result["max_consec_losses"] == 4


class TestBreakevenTrade:
    """pnl_thb = 0 → is_win = False → นับเป็น loss"""

    def test_breakeven_is_loss(self):
        trades = _make_trades(100, 0, -50)
        result = calculate_trade_metrics(trades)
        assert result["winning_trades"] == 1
        assert result["losing_trades"] == 2

    def test_breakeven_not_in_gross_profit(self):
        trades = _make_trades(0)
        result = calculate_trade_metrics(trades)
        assert result["gross_profit_thb"] == 0.0
        assert result["profit_factor"] == float(
            "inf"
        )  # gross_profit=0, abs_loss=0 → inf


# ══════════════════════════════════════════════════════════════════
# 4. Mixed Trades — Win Rate & Profit Factor
# ══════════════════════════════════════════════════════════════════


class TestMixedTrades:
    """Win + Loss ปน → ทดสอบสูตรหลัก"""

    @pytest.fixture
    def mixed_result(self):
        """3 wins + 2 losses"""
        trades = _make_trades(120, -80, 200, -50, 90)
        return calculate_trade_metrics(trades)

    def test_total_trades(self, mixed_result):
        assert mixed_result["total_trades"] == 5

    def test_winning_losing_count(self, mixed_result):
        assert mixed_result["winning_trades"] == 3
        assert mixed_result["losing_trades"] == 2

    def test_win_rate(self, mixed_result):
        """win_rate = 3/5 = 60%"""
        assert mixed_result["win_rate_pct"] == 60.0

    def test_profit_factor(self, mixed_result):
        """profit_factor = gross_profit / abs(gross_loss)
        gross_profit = 120+200+90 = 410
        gross_loss = -80 + -50 = -130
        PF = 410/130 = 3.154"""
        assert abs(mixed_result["profit_factor"] - (410 / 130)) < 0.01

    def test_avg_win(self, mixed_result):
        """avg_win = (120+200+90) / 3 = 136.67"""
        assert abs(mixed_result["avg_win_thb"] - 136.67) < 0.01

    def test_largest_win_loss(self, mixed_result):
        assert mixed_result["largest_win_thb"] == 200.0
        assert mixed_result["largest_loss_thb"] == -80.0

    def test_expectancy_positive(self, mixed_result):
        """มีกำไร → expectancy > 0"""
        assert mixed_result["expectancy_thb"] > 0

    def test_largest_loss_is_min_pnl_even_all_wins(self):
        """all wins → largest_loss = smallest win (min of all_pnl)"""
        trades = _make_trades(50, 100, 200)
        result = calculate_trade_metrics(trades)
        assert result["largest_loss_thb"] == 50.0  # min(all_pnl) ไม่ใช่ 0

    def test_profit_factor_rounded_to_3_decimal(self):
        """PF = 100/33 = 3.030303... → round(3) = 3.030"""
        trades = _make_trades(100, -33)
        result = calculate_trade_metrics(trades)
        assert result["profit_factor"] == 3.030

    def test_avg_loss(self, mixed_result):
        """avg_loss = (-80+-50) / 2 = -65"""
        assert mixed_result["avg_loss_thb"] == -65.0

    def test_net_pnl(self, mixed_result):
        """net = 120-80+200-50+90 = 280"""
        assert mixed_result["net_pnl_thb"] == 280.0

    def test_total_cost(self, mixed_result):
        """5 trades × 6 THB cost = 30"""
        assert mixed_result["total_cost_thb"] == 30.0


# ══════════════════════════════════════════════════════════════════
# 5. Consecutive Streaks
# ══════════════════════════════════════════════════════════════════


class TestStreaks:
    """ทดสอบ max_consec_wins / max_consec_losses"""

    def test_streak_pattern(self):
        """W W L L L W → max_wins=2, max_losses=3"""
        trades = _make_trades(10, 20, -5, -10, -15, 30)
        result = calculate_trade_metrics(trades)
        assert result["max_consec_wins"] == 2
        assert result["max_consec_losses"] == 3

    def test_alternating(self):
        """W L W L W L → max_wins=1, max_losses=1"""
        trades = _make_trades(10, -5, 10, -5, 10, -5)
        result = calculate_trade_metrics(trades)
        assert result["max_consec_wins"] == 1
        assert result["max_consec_losses"] == 1

    def test_single_trade_win(self):
        trades = _make_trades(50)
        result = calculate_trade_metrics(trades)
        assert result["max_consec_wins"] == 1
        assert result["max_consec_losses"] == 0


# ══════════════════════════════════════════════════════════════════
# 6. add_calmar
# ══════════════════════════════════════════════════════════════════


class TestAddCalmar:
    """ทดสอบ add_calmar — Calmar ratio = annualized_return / abs(mdd)"""

    def test_basic_calmar(self):
        """ann_return=18.5, mdd=-12.3 → calmar = 18.5/12.3 ≈ 1.504"""
        trade_m = calculate_trade_metrics(_make_trades(100))
        risk = {"annualized_return_pct": 18.5, "mdd_pct": -12.3}
        result = add_calmar(trade_m, risk)
        assert "calmar_ratio" in result
        assert abs(result["calmar_ratio"] - 1.504) < 0.01

    def test_calmar_zero_mdd(self):
        """mdd = 0 + positive return → calmar = inf"""
        trade_m = calculate_trade_metrics(_make_trades(100))
        risk = {"annualized_return_pct": 10.0, "mdd_pct": 0.0}
        result = add_calmar(trade_m, risk)
        assert result["calmar_ratio"] == float("inf")

    def test_calmar_zero_mdd_negative_return(self):
        """mdd = 0 + negative return → calmar = 0"""
        trade_m = calculate_trade_metrics(_make_trades(-100))
        risk = {"annualized_return_pct": -5.0, "mdd_pct": 0.0}
        result = add_calmar(trade_m, risk)
        assert result["calmar_ratio"] == 0.0

    def test_calmar_does_not_modify_original(self):
        """add_calmar ต้องไม่แก้ไข dict ต้นฉบับ"""
        trade_m = calculate_trade_metrics(_make_trades(100))
        risk = {"annualized_return_pct": 10.0, "mdd_pct": -5.0}
        result = add_calmar(trade_m, risk)
        assert "calmar_ratio" not in trade_m  # original unchanged
        assert "calmar_ratio" in result
