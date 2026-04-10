"""
backtest/engine/portfolio.py
══════════════════════════════════════════════════════════════════════
SimPortfolio v2 — Stateful portfolio สำหรับ backtest

[FIX v2.1] Spread คิดแบบ proportional ต่อบาทน้ำหนัก (ไม่ใช่ flat per trade)
  ออม NOW จริง: spread = 120 THB ต่อ 1 บาทน้ำหนัก (ตามข้อมูลฮั่วเซ่งเฮง)
  เช่น position ฿1,000 ที่ราคา ฿71,950/บาท
    → บาทน้ำหนัก = 1000/71950 = 0.01390
    → spread cost = 0.01390 × 120 = 1.67 THB (ไม่ใช่ 120 THB!)
    → round trip = 3.34 THB spread + 6 THB commission = ~9.34 THB
    → % ต้นทุน = 0.93% (สมเหตุสมผล, ก่อนหน้า = 24% — ผิด!)

Trading Constants:
  SPREAD_PER_BAHT  = 120 THB / 1 บาทน้ำหนัก  ← ค่าจริงจาก ออม NOW
  COMMISSION_THB   =   3 THB per trade
  GOLD_GRAM_PER_BAHT = 15.244 g
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────
GOLD_GRAM_PER_BAHT  = 15.244
# [FIX] spread คิดต่อบาทน้ำหนัก — ไม่ใช่ flat per trade
SPREAD_PER_BAHT     = 120.0    # THB / 1 บาทน้ำหนัก (ข้อมูลจริงฮั่วเซ่งเฮง ออม NOW)
COMMISSION_THB      = 3.0      # THB per trade (ค่าธรรมเนียมคงที่)
DEFAULT_CASH        = 1_500.0
BUST_THRESHOLD      = 1_000.0
WIN_THRESHOLD       = 1_500.0

# backward compat alias — ใช้ใน _add_validation() ของ run_main_backtest.py
# แต่ค่านี้ไม่ควรใช้ใน portfolio logic แล้ว
SPREAD_THB          = SPREAD_PER_BAHT  # alias เพื่อไม่ให้ import error


def _calc_spread(position_thb: float, price_per_baht: float) -> float:
    """คำนวณ spread จริงตาม position size และราคา
    
    Parameters
    ----------
    position_thb    : เงินที่ลงทุน (THB)
    price_per_baht  : ราคาทองต่อบาทน้ำหนัก (THB/baht)
    
    Returns
    -------
    float : spread cost (THB) สำหรับ 1 ขา
    
    ตัวอย่าง:
      position=1000, price=71950 → baht_weight=0.01390 → spread=1.67 THB
      position=5000, price=71950 → baht_weight=0.06949 → spread=8.34 THB
    """
    if price_per_baht <= 0:
        return 0.0
    baht_weight = position_thb / price_per_baht
    return baht_weight * SPREAD_PER_BAHT


def _calc_spread_from_grams(gold_grams: float, price_per_baht: float) -> float:
    """คำนวณ spread จาก gold_grams ที่ถือ (ใช้ตอน SELL)"""
    if price_per_baht <= 0:
        return 0.0
    baht_weight = gold_grams / GOLD_GRAM_PER_BAHT
    return baht_weight * SPREAD_PER_BAHT


# ══════════════════════════════════════════════════════════════════
# Exception
# ══════════════════════════════════════════════════════════════════


class PortfolioBustException(Exception):
    """Raised เมื่อ portfolio total value < bust_threshold"""

    def __init__(self, equity: float, threshold: float = BUST_THRESHOLD,
                 timestamp: str = ""):
        self.equity    = equity
        self.threshold = threshold
        self.timestamp = timestamp
        super().__init__(
            f"🔴 PORTFOLIO BUST: equity={equity:.2f} THB "
            f"< threshold={threshold:.0f} THB"
            + (f" at {timestamp}" if timestamp else "")
        )


# ══════════════════════════════════════════════════════════════════
# Trade Record
# ══════════════════════════════════════════════════════════════════


@dataclass
class ClosedTrade:
    """1 รอบการเทรดที่ปิดแล้ว (BUY → SELL)"""
    entry_price:  float
    exit_price:   float
    gold_grams:   float
    entry_time:   str
    exit_time:    str
    position_thb: float
    gross_pnl:    float
    cost_thb:     float       # spread + commission รวม 2 ขา (proportional แล้ว)
    pnl_thb:      float
    is_win:       bool = field(init=False)

    def __post_init__(self):
        self.is_win = self.pnl_thb > 0

    def to_dict(self) -> dict:
        return {
            "entry_time":   self.entry_time,
            "exit_time":    self.exit_time,
            "entry_price":  round(self.entry_price, 2),
            "exit_price":   round(self.exit_price, 2),
            "gold_grams":   round(self.gold_grams, 4),
            "position_thb": round(self.position_thb, 2),
            "gross_pnl":    round(self.gross_pnl, 2),
            "cost_thb":     round(self.cost_thb, 2),
            "pnl_thb":      round(self.pnl_thb, 2),
            "is_win":       self.is_win,
        }


@dataclass
class _OpenTrade:
    entry_price:       float
    gold_grams:        float
    entry_time:        str
    position_thb:      float
    cost_at_entry:     float   # spread+commission ที่จ่ายตอน BUY (proportional)
    # [v2.2] เก็บ TP/SL price ที่ RiskManager กำหนดไว้ตอน BUY
    take_profit_price: float = 0.0
    stop_loss_price:   float = 0.0


# ══════════════════════════════════════════════════════════════════
# SimPortfolio v2.1
# ══════════════════════════════════════════════════════════════════


@dataclass
class SimPortfolio:
    """
    Simulated portfolio พร้อม bust detection และ trade logging
    [v2.1] Spread คิดแบบ proportional ต่อบาทน้ำหนัก
    """
    initial_cash:   float = DEFAULT_CASH
    bust_threshold: float = BUST_THRESHOLD
    win_threshold:  float = WIN_THRESHOLD

    cash_balance:   float = field(init=False)
    gold_grams:     float = field(init=False, default=0.0)
    cost_basis_thb: float = field(init=False, default=0.0)
    trades_today:   int   = field(init=False, default=0)
    _last_date:     str   = field(init=False, default="")

    closed_trades:  List[ClosedTrade]    = field(init=False, default_factory=list)
    _open_trade:    Optional[_OpenTrade] = field(init=False, default=None)

    bust_flag:   bool            = field(init=False, default=False)
    bust_at:     Optional[str]   = field(init=False, default=None)
    bust_equity: Optional[float] = field(init=False, default=None)

    def __post_init__(self):
        self.cash_balance = self.initial_cash

    def reset_daily(self, date_str: str):
        if date_str != self._last_date:
            self.trades_today = 0
            self._last_date   = date_str

    def set_open_tp_sl(self, take_profit: float, stop_loss: float):
        """
        [v2.2] บันทึก TP/SL price หลังจาก execute_buy สำเร็จ
        เรียกจาก _apply_to_portfolio ใน run_main_backtest.py
        ค่าเหล่านี้จะถูกส่งไปใน market_state → risk.py อ่านได้ทุก candle
        """
        if self._open_trade is not None:
            self._open_trade.take_profit_price = float(take_profit or 0.0)
            self._open_trade.stop_loss_price   = float(stop_loss  or 0.0)
            logger.debug(
                f"  TP/SL set: TP={self._open_trade.take_profit_price:,.0f} "
                f"SL={self._open_trade.stop_loss_price:,.0f}"
            )

    def can_buy(self) -> bool:
        return self.cash_balance >= self.bust_threshold

    def can_sell(self) -> bool:
        return self.gold_grams > 1e-4

    def execute_buy(
        self,
        price_thb_per_baht: float,
        position_thb: float,
        timestamp: str = "",
        hsh_sell: float = 0.0,
    ) -> bool:
        """
        ซื้อทอง — spread คำนวณ proportional ต่อบาทน้ำหนัก
        
        [FIX v2.1] spread = (position_thb / exec_price) * SPREAD_PER_BAHT
        ไม่ใช่ flat SPREAD_THB อีกต่อไป
        """
        exec_price = hsh_sell if hsh_sell > 0 else price_thb_per_baht

        # [FIX] proportional spread
        if hsh_sell > 0:
            # ถ้ามีราคา HSH จริง spread รวมใน hsh_sell แล้ว จ่ายแค่ commission
            spread_cost = 0.0
        else:
            spread_cost = _calc_spread(position_thb, exec_price)

        trade_cost = spread_cost + COMMISSION_THB
        total_cost = position_thb + trade_cost

        if self.cash_balance < total_cost:
            logger.debug(
                f"  BUY skipped: cash={self.cash_balance:.2f} < "
                f"need={total_cost:.2f} (pos={position_thb:.0f} + "
                f"spread={spread_cost:.2f} + comm={COMMISSION_THB})"
            )
            return False

        grams = (position_thb / exec_price) * GOLD_GRAM_PER_BAHT
        self.cash_balance   -= total_cost
        self.gold_grams     += grams
        self.cost_basis_thb  = exec_price
        self.trades_today   += 1

        self._open_trade = _OpenTrade(
            entry_price=exec_price,
            gold_grams=grams,
            entry_time=timestamp,
            position_thb=position_thb,
            cost_at_entry=trade_cost,
        )

        logger.debug(
            f"  BUY: {grams:.4f}g @ {exec_price:,.0f} | "
            f"spread={spread_cost:.2f} comm={COMMISSION_THB} | "
            f"cash={self.cash_balance:.2f}"
        )
        self._check_bust(exec_price, timestamp)
        return True

    def execute_sell(
        self,
        price_thb_per_baht: float,
        timestamp: str = "",
        hsh_buy: float = 0.0,
    ) -> bool:
        """
        ขายทองทั้งหมด — spread คำนวณ proportional ต่อบาทน้ำหนัก

        [FIX v2.1] spread = (gold_grams / GOLD_GRAM_PER_BAHT) * SPREAD_PER_BAHT
        """
        if not self.can_sell():
            return False

        exec_price = hsh_buy if hsh_buy > 0 else price_thb_per_baht

        # [FIX] proportional spread ตาม gold ที่ถือ
        if hsh_buy > 0:
            spread_cost = 0.0
        else:
            spread_cost = _calc_spread_from_grams(self.gold_grams, exec_price)

        trade_cost   = spread_cost + COMMISSION_THB
        proceeds     = (self.gold_grams / GOLD_GRAM_PER_BAHT) * exec_price
        net_proceeds = proceeds - trade_cost
        self.cash_balance += net_proceeds
        self.trades_today += 1

        if self._open_trade:
            ot = self._open_trade
            gross_pnl        = (ot.gold_grams / GOLD_GRAM_PER_BAHT) * (exec_price - ot.entry_price)
            total_cost_trade = ot.cost_at_entry + trade_cost
            net_pnl          = gross_pnl - total_cost_trade

            self.closed_trades.append(ClosedTrade(
                entry_price=ot.entry_price,
                exit_price=exec_price,
                gold_grams=ot.gold_grams,
                entry_time=ot.entry_time,
                exit_time=timestamp,
                position_thb=ot.position_thb,
                gross_pnl=gross_pnl,
                cost_thb=total_cost_trade,
                pnl_thb=net_pnl,
            ))
            logger.debug(
                f"  SELL: {ot.gold_grams:.4f}g @ {exec_price:,.0f} | "
                f"spread={spread_cost:.2f} comm={COMMISSION_THB} | "
                f"gross={gross_pnl:+.2f} net={net_pnl:+.2f} | "
                f"cash={self.cash_balance:.2f}"
            )

        self.gold_grams     = 0.0
        self.cost_basis_thb = 0.0
        self._open_trade    = None  # [v2.2] clears TP/SL too (stored in _open_trade)

        self._check_bust(price_thb_per_baht, timestamp)
        return True

    def _check_bust(self, price: float, timestamp: str = ""):
        tv = self.total_value(price)
        if tv < self.bust_threshold:
            self.bust_flag   = True
            self.bust_at     = timestamp
            self.bust_equity = round(tv, 2)
            raise PortfolioBustException(tv, self.bust_threshold, timestamp)

    def current_value(self, price: float) -> float:
        return (self.gold_grams / GOLD_GRAM_PER_BAHT) * price

    def unrealized_pnl(self, price: float) -> float:
        if self.gold_grams <= 1e-4:
            return 0.0
        return self.current_value(price) - (
            (self.gold_grams / GOLD_GRAM_PER_BAHT) * self.cost_basis_thb
        )

    def total_value(self, price: float) -> float:
        return self.cash_balance + self.current_value(price)

    def total_return_pct(self, price: float) -> float:
        if self.initial_cash <= 0:
            return 0.0
        return (self.total_value(price) - self.initial_cash) / self.initial_cash * 100

    def is_winner(self, price: float) -> bool:
        return self.total_value(price) > self.win_threshold

    def to_market_state_dict(self, price: float) -> dict:
        can_buy  = (
            f"YES (cash={self.cash_balance:.0f})"
            if self.can_buy()
            else f"NO (cash={self.cash_balance:.0f} < {self.bust_threshold:.0f})"
        )
        can_sell = (
            f"YES ({self.gold_grams:.4f}g)"
            if self.can_sell()
            else "NO (no gold held)"
        )
        unrealized = self.unrealized_pnl(price)
        # [v2.2] ดึง TP/SL price จาก open trade (ถ้าไม่มีให้ส่ง 0.0)
        tp_price = self._open_trade.take_profit_price if self._open_trade else 0.0
        sl_price = self._open_trade.stop_loss_price   if self._open_trade else 0.0
        return {
            "cash_balance":      round(self.cash_balance, 2),
            "gold_grams":        round(self.gold_grams, 4),
            "cost_basis_thb":    round(self.cost_basis_thb, 2),
            "current_value_thb": round(self.current_value(price), 2),
            "unrealized_pnl":    round(unrealized, 2),
            "trades_today":      self.trades_today,
            "can_buy":           can_buy,
            "can_sell":          can_sell,
            # [v2.2] TP/SL price สำหรับให้ risk.py check ราคาจริง
            "take_profit_price": round(tp_price, 2),
            "stop_loss_price":   round(sl_price, 2),
        }

    def summary(self, current_price: float) -> dict:
        return {
            "initial_cash_thb":    round(self.initial_cash, 2),
            "final_cash_thb":      round(self.cash_balance, 2),
            "final_gold_grams":    round(self.gold_grams, 4),
            "final_total_value":   round(self.total_value(current_price), 2),
            "total_return_pct":    round(self.total_return_pct(current_price), 2),
            "is_winner":           self.is_winner(current_price),
            "bust_flag":           self.bust_flag,
            "bust_at":             self.bust_at,
            "bust_equity":         self.bust_equity,
            "total_closed_trades": len(self.closed_trades),
        }


# ── Self-test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(message)s")
    print("=" * 60)
    print("SimPortfolio v2.1 — Proportional Spread Self Test")
    print("=" * 60)

    price = 71950.0  # ราคาขายออก ออม NOW

    p = SimPortfolio()
    ok = p.execute_buy(price, 1000.0, "2026-04-05 10:00")
    assert ok

    # คำนวณ spread ที่ควรเป็น
    bw = 1000 / price
    expected_spread = bw * SPREAD_PER_BAHT
    expected_cost = expected_spread + COMMISSION_THB
    expected_cash = 1500 - 1000 - expected_cost
    print(f"After BUY 1000 THB @ {price:,.0f}:")
    print(f"  baht_weight    = {bw:.6f}")
    print(f"  spread cost    = {expected_spread:.2f} THB  (ไม่ใช่ 120!)")
    print(f"  commission     = {COMMISSION_THB} THB")
    print(f"  total cost     = {expected_cost:.2f} THB")
    print(f"  cash remaining = {p.cash_balance:.2f} THB (expected ~{expected_cash:.2f})")
    assert abs(p.cash_balance - expected_cash) < 0.01, f"Cash mismatch: {p.cash_balance} vs {expected_cash}"

    # SELL ที่ราคาสูงกว่า 672 THB
    sell_price = 71950 + 700  # ขยับ 700 THB > break-even ~672
    p.execute_sell(sell_price, "2026-04-05 11:00")
    t = p.closed_trades[0]
    print(f"\nAfter SELL @ {sell_price:,.0f}:")
    print(f"  gross_pnl = {t.gross_pnl:+.2f} THB")
    print(f"  cost_thb  = {t.cost_thb:.2f} THB  (spread×2 + commission×2)")
    print(f"  net_pnl   = {t.pnl_thb:+.2f} THB")
    print(f"  is_win    = {t.is_win}")
    assert t.is_win, "Should be a win at +700 THB price move"

    print(f"\n✓ Spread v2.1 works correctly!")
    print(f"  Round-trip cost: {t.cost_thb:.2f} THB ({t.cost_thb/1000*100:.2f}% of position)")
    print(f"  vs OLD flat spread: 246 THB (24.6% of position)")
    print("=" * 60)