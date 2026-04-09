"""
test_portfolio.py — Pytest สำหรับทดสอบ SimPortfolio

Strategy: 100% Real (ไม่มี mock)
- SimPortfolio เป็น pure stateful computation
- ไม่มี external I/O ใดๆ (ไม่มี API, DB, file)
- ทดสอบด้วยค่าจริงที่คำนวณมือได้

ครอบคลุม:
  1. _calc_spread / _calc_spread_from_grams — สูตร proportional spread
  2. SimPortfolio init & state
  3. execute_buy — spread, commission, cash deduction
  4. execute_sell — proceeds, closed trade logging, PnL
  5. Bust detection — threshold check
  6. Edge cases — ซื้อซ้ำ, เงินไม่พอ, ขายตอนไม่มีทอง
  7. ClosedTrade — is_win, to_dict
  8. Portfolio queries — total_value, unrealized_pnl, summary
"""

import pytest

from backtest.engine.portfolio import (
    SimPortfolio,
    ClosedTrade,
    PortfolioBustException,
    _calc_spread,
    _calc_spread_from_grams,
    GOLD_GRAM_PER_BAHT,
    SPREAD_PER_BAHT,
    COMMISSION_THB,
    DEFAULT_CASH,
    BUST_THRESHOLD,
)


# ══════════════════════════════════════════════════════════════════
# Constants สำหรับ test — ราคาทอง ออม NOW จริง
# ══════════════════════════════════════════════════════════════════

PRICE = 71_950.0  # THB per baht weight (ราคาขาย)
POS = 1_000.0  # position size THB


# ══════════════════════════════════════════════════════════════════
# 1. Spread Calculation (pure functions)
# ══════════════════════════════════════════════════════════════════


class TestCalcSpread:
    """ทดสอบ _calc_spread — สูตร proportional ต่อบาทน้ำหนัก"""

    def test_basic_calculation(self):
        """position=1000, price=71950 → spread ≈ 1.67 THB"""
        spread = _calc_spread(POS, PRICE)
        # baht_weight = 1000/71950 = 0.01390
        # spread = 0.01390 * 120 = 1.668
        expected = (POS / PRICE) * SPREAD_PER_BAHT
        assert abs(spread - expected) < 0.01
        assert 1.5 < spread < 2.0  # sanity check

    def test_larger_position(self):
        """position ใหญ่ขึ้น → spread ใหญ่ขึ้น proportional"""
        s1 = _calc_spread(1000, PRICE)
        s5 = _calc_spread(5000, PRICE)
        assert abs(s5 - s1 * 5) < 0.01

    def test_zero_price_returns_zero(self):
        """ราคา = 0 → spread = 0 (ป้องกัน divide by zero)"""
        assert _calc_spread(1000, 0.0) == 0.0

    def test_negative_price_returns_zero(self):
        """ราคาติดลบ → spread = 0"""
        assert _calc_spread(1000, -100.0) == 0.0


class TestCalcSpreadFromGrams:
    """ทดสอบ _calc_spread_from_grams — ใช้ตอน SELL"""

    def test_basic(self):
        """gold_grams → baht_weight → spread"""
        grams = 1.0
        spread = _calc_spread_from_grams(grams, PRICE)
        # baht_weight = 1.0 / 15.244 = 0.06561
        # spread = 0.06561 * 120 = 7.87
        expected = (grams / GOLD_GRAM_PER_BAHT) * SPREAD_PER_BAHT
        assert abs(spread - expected) < 0.01

    def test_zero_price(self):
        assert _calc_spread_from_grams(1.0, 0.0) == 0.0


# ══════════════════════════════════════════════════════════════════
# 2. SimPortfolio Init & State
# ══════════════════════════════════════════════════════════════════


class TestPortfolioInit:
    """ทดสอบ state เริ่มต้น"""

    def test_default_cash(self):
        p = SimPortfolio()
        assert p.cash_balance == DEFAULT_CASH
        assert p.gold_grams == 0.0
        assert p.trades_today == 0
        assert p.bust_flag is False

    def test_custom_cash(self):
        p = SimPortfolio(initial_cash=5000.0)
        assert p.cash_balance == 5000.0

    def test_can_buy_initially(self):
        """เริ่มต้น 1500 > bust_threshold 1000 → can_buy = True"""
        p = SimPortfolio()
        assert p.can_buy() is True

    def test_cannot_sell_initially(self):
        """เริ่มต้นไม่มีทอง → can_sell = False"""
        p = SimPortfolio()
        assert p.can_sell() is False

    def test_reset_daily(self):
        """เปลี่ยนวัน → trades_today reset เป็น 0"""
        p = SimPortfolio()
        p.trades_today = 5
        p.reset_daily("2026-04-06")
        assert p.trades_today == 0


# ══════════════════════════════════════════════════════════════════
# 3. Execute BUY
# ══════════════════════════════════════════════════════════════════


class TestExecuteBuy:
    """ทดสอบ execute_buy — ซื้อทอง"""

    def test_buy_success(self):
        """ซื้อ 1000 THB สำเร็จ — cash ลดลงถูกต้อง"""
        p = SimPortfolio()
        ok = p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        assert ok is True
        assert p.gold_grams > 0
        assert p.trades_today == 1

    def test_buy_cash_deduction(self):
        """cash ลด = position + spread + commission"""
        p = SimPortfolio()
        cash_before = p.cash_balance
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")

        spread = _calc_spread(POS, PRICE)
        expected_cash = cash_before - POS - spread - COMMISSION_THB
        assert abs(p.cash_balance - expected_cash) < 0.01

    def test_buy_gold_grams_correct(self):
        """gold_grams = (position / price) * GOLD_GRAM_PER_BAHT"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        expected_grams = (POS / PRICE) * GOLD_GRAM_PER_BAHT
        assert abs(p.gold_grams - expected_grams) < 0.0001

    def test_buy_sets_cost_basis(self):
        """cost_basis_thb = exec_price"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        assert p.cost_basis_thb == PRICE

    def test_buy_insufficient_cash(self):
        """เงินไม่พอ → return False, state ไม่เปลี่ยน"""
        p = SimPortfolio(initial_cash=100.0)  # น้อยกว่า position
        ok = p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        assert ok is False
        assert p.gold_grams == 0.0
        assert p.cash_balance == 100.0

    def test_buy_with_hsh_sell_no_spread(self):
        """ส่ง hsh_sell → spread = 0 (รวมใน HSH price แล้ว)"""
        p = SimPortfolio()
        cash_before = p.cash_balance
        p.execute_buy(PRICE, POS, "2026-04-05 10:00", hsh_sell=72000.0)
        # cost = position + 0 spread + commission only
        expected_cash = cash_before - POS - COMMISSION_THB
        assert abs(p.cash_balance - expected_cash) < 0.01

    def test_buy_creates_open_trade(self):
        """ซื้อแล้วต้องมี _open_trade"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        assert p._open_trade is not None
        assert p._open_trade.entry_price == PRICE

    def test_double_buy_overwrites_open_trade(self):
        """ซื้อซ้ำ 2 ครั้ง → _open_trade เก็บรอบล่าสุด, gold สะสม"""
        p = SimPortfolio()
        p.execute_buy(PRICE, 500, "T1")
        g1 = p.gold_grams
        p.execute_buy(PRICE, 500, "T2")
        assert p.gold_grams > g1
        assert p._open_trade.entry_time == "T2"


# ══════════════════════════════════════════════════════════════════
# 4. Execute SELL
# ══════════════════════════════════════════════════════════════════


class TestExecuteSell:
    """ทดสอบ execute_sell — ขายทองทั้งหมด"""

    def _buy_then_sell(self, buy_price, sell_price, pos=POS):
        """Helper: ซื้อแล้วขาย"""
        p = SimPortfolio()
        p.execute_buy(buy_price, pos, "2026-04-05 10:00")
        p.execute_sell(sell_price, "2026-04-05 11:00")
        return p

    def test_sell_success(self):
        """ขายสำเร็จ — gold_grams = 0"""
        p = self._buy_then_sell(PRICE, PRICE + 500)
        assert p.gold_grams == 0.0
        assert p.can_sell() is False

    def test_sell_creates_closed_trade(self):
        """ขายแล้วต้องมี closed_trade 1 รายการ"""
        p = self._buy_then_sell(PRICE, PRICE + 500)
        assert len(p.closed_trades) == 1

    def test_sell_winning_trade(self):
        """ราคาขึ้น 700 THB → net PnL เป็นบวก (หลังหัก cost)"""
        p = self._buy_then_sell(PRICE, PRICE + 700)
        t = p.closed_trades[0]
        assert t.is_win is True
        assert t.pnl_thb > 0
        assert t.gross_pnl > 0

    def test_sell_losing_trade(self):
        """ราคาลง 500 THB → net PnL เป็นลบ"""
        p = self._buy_then_sell(PRICE, PRICE - 500)
        t = p.closed_trades[0]
        assert t.is_win is False
        assert t.pnl_thb < 0

    def test_sell_cost_includes_both_legs(self):
        """cost_thb = spread(buy) + comm(buy) + spread(sell) + comm(sell)"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        grams = p.gold_grams
        p.execute_sell(PRICE, "2026-04-05 11:00")
        t = p.closed_trades[0]

        spread_buy = _calc_spread(POS, PRICE)
        spread_sell = _calc_spread_from_grams(grams, PRICE)
        expected_cost = (spread_buy + COMMISSION_THB) + (spread_sell + COMMISSION_THB)
        assert abs(t.cost_thb - expected_cost) < 0.01

    def test_sell_no_gold_returns_false(self):
        """ไม่มีทอง → return False"""
        p = SimPortfolio()
        assert p.execute_sell(PRICE, "2026-04-05 11:00") is False

    def test_sell_clears_open_trade(self):
        """ขายแล้ว _open_trade = None"""
        p = self._buy_then_sell(PRICE, PRICE)
        assert p._open_trade is None

    def test_sell_increments_trades_today(self):
        """BUY + SELL = trades_today = 2"""
        p = self._buy_then_sell(PRICE, PRICE)
        assert p.trades_today == 2


# ══════════════════════════════════════════════════════════════════
# 5. Bust Detection
# ══════════════════════════════════════════════════════════════════


class TestBustDetection:
    """ทดสอบ bust threshold — equity < 1000 → raise exception"""

    def test_bust_on_heavy_loss(self):
        """ราคาลงหนักจนพอร์ต < 1000 → PortfolioBustException"""
        p = SimPortfolio(initial_cash=1200.0)
        p.execute_buy(PRICE, 1000.0, "2026-04-05 10:00")

        with pytest.raises(PortfolioBustException):
            # ราคาลงมาก → total_value ต่ำกว่า threshold
            p.execute_sell(PRICE * 0.5, "2026-04-05 11:00")

    def test_bust_flag_set(self):
        """bust แล้ว → bust_flag = True"""
        p = SimPortfolio(initial_cash=1200.0)
        p.execute_buy(PRICE, 1000.0, "2026-04-05 10:00")
        try:
            p.execute_sell(PRICE * 0.5, "2026-04-05 11:00")
        except PortfolioBustException:
            pass
        assert p.bust_flag is True
        assert p.bust_at is not None

    def test_no_bust_when_healthy(self):
        """พอร์ตแข็งแรง → ไม่ bust"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        p.execute_sell(PRICE + 500, "2026-04-05 11:00")
        assert p.bust_flag is False


# ══════════════════════════════════════════════════════════════════
# 6. ClosedTrade Dataclass
# ══════════════════════════════════════════════════════════════════


class TestClosedTrade:
    """ทดสอบ ClosedTrade dataclass"""

    def test_is_win_positive_pnl(self):
        t = ClosedTrade(
            entry_price=PRICE,
            exit_price=PRICE + 500,
            gold_grams=0.2,
            entry_time="10:00",
            exit_time="11:00",
            position_thb=1000,
            gross_pnl=10,
            cost_thb=5,
            pnl_thb=5,
        )
        assert t.is_win is True

    def test_is_win_negative_pnl(self):
        t = ClosedTrade(
            entry_price=PRICE,
            exit_price=PRICE - 500,
            gold_grams=0.2,
            entry_time="10:00",
            exit_time="11:00",
            position_thb=1000,
            gross_pnl=-10,
            cost_thb=5,
            pnl_thb=-15,
        )
        assert t.is_win is False

    def test_to_dict_keys(self):
        t = ClosedTrade(
            entry_price=PRICE,
            exit_price=PRICE,
            gold_grams=0.2,
            entry_time="10:00",
            exit_time="11:00",
            position_thb=1000,
            gross_pnl=0,
            cost_thb=5,
            pnl_thb=-5,
        )
        d = t.to_dict()
        assert "entry_price" in d
        assert "pnl_thb" in d
        assert "is_win" in d


# ══════════════════════════════════════════════════════════════════
# 7. Portfolio Query Methods
# ══════════════════════════════════════════════════════════════════


class TestPortfolioQueries:
    """ทดสอบ total_value, unrealized_pnl, summary"""

    def test_total_value_no_gold(self):
        """ไม่มีทอง → total_value = cash"""
        p = SimPortfolio()
        assert p.total_value(PRICE) == DEFAULT_CASH

    def test_total_value_with_gold(self):
        """มีทอง → total = cash + gold_value"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        tv = p.total_value(PRICE)
        assert tv > 0
        # total ≈ initial_cash - costs (ต้องน้อยกว่าเริ่มต้นเพราะมี spread)
        assert tv < DEFAULT_CASH

    def test_unrealized_pnl_no_gold(self):
        """ไม่มีทอง → unrealized = 0"""
        p = SimPortfolio()
        assert p.unrealized_pnl(PRICE) == 0.0

    def test_unrealized_pnl_price_up(self):
        """ราคาขึ้น → unrealized > 0"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        assert p.unrealized_pnl(PRICE + 5000) > 0

    def test_unrealized_pnl_price_down(self):
        """ราคาลง → unrealized < 0"""
        p = SimPortfolio()
        p.execute_buy(PRICE, POS, "2026-04-05 10:00")
        assert p.unrealized_pnl(PRICE - 5000) < 0

    def test_total_return_pct(self):
        """return % = (total_value - initial) / initial * 100"""
        p = SimPortfolio()
        ret = p.total_return_pct(PRICE)
        assert ret == 0.0  # ไม่มีทอง = ไม่มี return

    def test_is_winner(self):
        """total_value > win_threshold → is_winner"""
        p = SimPortfolio()
        assert p.is_winner(PRICE) is False  # 1500 ไม่ > 1500
        p2 = SimPortfolio(initial_cash=2000.0)
        assert p2.is_winner(PRICE) is True  # 2000 > 1500

    def test_summary_keys(self):
        """summary() ต้องมี keys ครบ"""
        p = SimPortfolio()
        s = p.summary(PRICE)
        expected_keys = {
            "initial_cash_thb",
            "final_cash_thb",
            "final_gold_grams",
            "final_total_value",
            "total_return_pct",
            "is_winner",
            "bust_flag",
            "bust_at",
            "bust_equity",
            "total_closed_trades",
        }
        assert expected_keys.issubset(s.keys())

    def test_to_market_state_dict(self):
        """to_market_state_dict() สำหรับ LLM prompt"""
        p = SimPortfolio()
        d = p.to_market_state_dict(PRICE)
        assert "cash_balance" in d
        assert "can_buy" in d
        assert "YES" in d["can_buy"]


# ══════════════════════════════════════════════════════════════════
# 8. Multiple Trades (Round Trips)
# ══════════════════════════════════════════════════════════════════


class TestMultipleTrades:
    """ทดสอบหลายรอบการเทรด"""

    def test_two_round_trips(self):
        """BUY-SELL 2 รอบ → closed_trades = 2"""
        p = SimPortfolio()
        p.execute_buy(PRICE, 500, "T1")
        p.execute_sell(PRICE + 300, "T2")
        p.execute_buy(PRICE, 500, "T3")
        p.execute_sell(PRICE + 300, "T4")
        assert len(p.closed_trades) == 2
        assert p.trades_today == 4

    def test_cash_decreases_from_costs(self):
        """เทรดหลายรอบ → cash ค่อยๆ ลด เพราะ spread + commission"""
        p = SimPortfolio()
        initial = p.cash_balance
        # Buy-sell ที่ราคาเท่ากัน (breakeven gross) → net loss จาก cost
        p.execute_buy(PRICE, 500, "T1")
        p.execute_sell(PRICE, "T2")
        assert p.cash_balance < initial
