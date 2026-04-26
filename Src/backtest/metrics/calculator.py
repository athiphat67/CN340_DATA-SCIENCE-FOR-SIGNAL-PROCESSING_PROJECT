"""
backtest/metrics/calculator.py
══════════════════════════════════════════════════════════════════════
คำนวณ trade-based metrics จาก portfolio.closed_trades

ต่างจาก directional_accuracy ที่มีอยู่แล้ว:
  directional_accuracy = LLM ทายทิศทางราคาถูก/ผิด (per candle)
  trade metrics        = กำไร/ขาดทุนจริงจาก closed BUY→SELL cycle

Metrics ที่คำนวณ:
  win_rate          = wins / total_trades
  profit_factor     = sum(winning_pnl) / abs(sum(losing_pnl))
  avg_win_thb       = mean net PnL ของ winning trades
  avg_loss_thb      = mean net PnL ของ losing trades (ค่าลบ)
  max_consec_losses = losing streak ยาวสุด
  calmar_ratio      = annualized_return / abs(mdd_pct)   — ต้องส่ง risk_metrics มาด้วย

Usage:
  from backtest.metrics.calculator import calculate_trade_metrics

  trade_m = calculate_trade_metrics(portfolio.closed_trades)
  calmar  = add_calmar(trade_m, risk_metrics)
══════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime
import math


logger = logging.getLogger(__name__)


def _coerce_datetime(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    to_pydatetime = getattr(value, "to_pydatetime", None)
    if callable(to_pydatetime):
        try:
            return to_pydatetime()
        except Exception:
            pass

    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        try:
            return datetime(value.year, value.month, value.day)
        except Exception:
            pass

    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None

        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except Exception:
            pass

        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
        ):
            try:
                return datetime.strptime(candidate, fmt)
            except Exception:
                continue

    return None


# ── Helper functions for annualized metrics, XIRR, etc. ──────────────────────────
def _safe_days_held(trade) -> Optional[int]:
    for attr in ("days_held", "holding_days"):
        v = getattr(trade, attr, None)
        if v is not None:
            try:
                return max(int(v), 1)
            except Exception:
                pass
    buy_dt = (
        getattr(trade, "buy_date", None)
        or getattr(trade, "entry_date", None)
        or getattr(trade, "entry_time", None)
    )
    sell_dt = (
        getattr(trade, "sell_date", None)
        or getattr(trade, "exit_date", None)
        or getattr(trade, "exit_time", None)
    )
    buy_dt = _coerce_datetime(buy_dt)
    sell_dt = _coerce_datetime(sell_dt)
    if buy_dt and sell_dt:
        try:
            # ใช้ inclusive day-count ให้ตรงกับ sample sheet (buy/sell same day = 1)
            return max((sell_dt - buy_dt).days + 1, 1)
        except Exception:
            return None
    return None


def _safe_buy_amount(trade) -> Optional[float]:
    for attr in (
        "position_thb",
        "buy_amount",
        "principal_thb",
        "notional_thb",
        "entry_value_thb",
    ):
        v = getattr(trade, attr, None)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return None


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals)-1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[f] * (c-k)
    d1 = sorted_vals[c] * (k-f)
    return float(d0+d1)


def _xnpv(rate, cashflows):
    if rate <= -0.999999:
        return float('inf')
    t0 = cashflows[0][0]
    total = 0.0
    for d, amt in cashflows:
        days = (d - t0).days / 365.0
        total += amt / ((1.0 + rate) ** days)
    return total


def _xirr(cashflows):
    if len(cashflows) < 2:
        return 0.0
    amounts = [a for _, a in cashflows]
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return 0.0
    low, high = -0.9999, 1.0
    try:
        f_low = _xnpv(low, cashflows)
        f_high = _xnpv(high, cashflows)

        while f_low * f_high > 0 and high < 1_000_000.0:
            high *= 2.0
            f_high = _xnpv(high, cashflows)

        if f_low * f_high > 0:
            return 0.0

        for _ in range(100):
            mid = (low + high) / 2.0
            f_mid = _xnpv(mid, cashflows)
            if abs(f_mid) < 1e-8:
                return mid
            if f_low * f_mid <= 0:
                high = mid
                f_high = f_mid
            else:
                low = mid
                f_low = f_mid
        return mid
    except Exception:
        return 0.0


def calculate_trade_metrics(closed_trades) -> dict:
    """
    คำนวณ trade-based metrics จาก List[ClosedTrade]

    Parameters
    ----------
    closed_trades : list ของ ClosedTrade objects จาก SimPortfolio.closed_trades

    Returns
    -------
    dict ที่มี key:
      total_trades, winning_trades, losing_trades
      win_rate_pct, profit_factor
      avg_win_thb, avg_loss_thb, expectancy_thb
      max_consec_wins, max_consec_losses
      gross_profit_thb, gross_loss_thb, net_pnl_thb
      total_cost_thb   ← spread + commission รวมทุก trade
      largest_win_thb, largest_loss_thb
    """
    if not closed_trades:
        return {
            "note":            "no closed trades",
            "total_trades":    0,
            "winning_trades":  0,
            "losing_trades":   0,
            "win_rate_pct":    0.0,
            "profit_factor":   0.0,
            "avg_win_thb":     0.0,
            "avg_loss_thb":    0.0,
            "expectancy_thb":  0.0,
            "max_consec_wins": 0,
            "max_consec_losses": 0,
            "gross_profit_thb":  0.0,
            "gross_loss_thb":    0.0,
            "net_pnl_thb":       0.0,
            "total_cost_thb":    0.0,
            "largest_win_thb":   0.0,
            "largest_loss_thb":  0.0,
            "best_annualized_trade_pct": 0.0,
            "worst_annualized_trade_pct": 0.0,
            "median_annualized_pct": 0.0,
            "top10_annualized_trade_pct": 0.0,
            "bottom10_annualized_trade_pct": 0.0,
            "xirr_pct": 0.0,
            "avg_capital_per_year_thb": 0.0,
        }

    n          = len(closed_trades)
    wins       = [t for t in closed_trades if t.is_win]
    losses     = [t for t in closed_trades if not t.is_win]

    win_count  = len(wins)
    loss_count = len(losses)

    # ── PnL aggregates ────────────────────────────────────────────────
    gross_profit = sum(t.pnl_thb for t in wins)          # รวม PnL ของ winning trades
    gross_loss   = sum(t.pnl_thb for t in losses)        # รวม PnL ของ losing trades (ลบ)
    net_pnl      = sum(t.pnl_thb for t in closed_trades)
    total_cost   = sum(t.cost_thb for t in closed_trades)

    # ── Averages ──────────────────────────────────────────────────────
    avg_win  = gross_profit / win_count  if win_count  else 0.0
    avg_loss = gross_loss   / loss_count if loss_count else 0.0   # ค่าลบ

    # Expectancy = กำไรเฉลี่ยที่คาดหวังต่อ 1 trade
    win_rate    = win_count / n
    expectancy  = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)

    # ── Profit Factor ────────────────────────────────────────────────
    # = ผลรวมกำไร / ผลรวมขาดทุน (absolte)
    # > 1.0 = มีกำไรสุทธิ, > 1.5 = ดี, > 2.0 = ดีมาก
    abs_loss = abs(gross_loss)
    profit_factor = round(gross_profit / abs_loss, 3) if abs_loss > 1e-6 else float("inf")

    # ── Consecutive streaks ───────────────────────────────────────────
    max_consec_wins = max_consec_losses = 0
    cur_wins = cur_losses = 0

    for t in closed_trades:
        if t.is_win:
            cur_wins  += 1
            cur_losses = 0
        else:
            cur_losses += 1
            cur_wins   = 0
        max_consec_wins   = max(max_consec_wins,   cur_wins)
        max_consec_losses = max(max_consec_losses, cur_losses)

    # ── Extremes ─────────────────────────────────────────────────────
    all_pnl      = [t.pnl_thb for t in closed_trades]
    largest_win  = max((t.pnl_thb for t in wins), default=0.0)
    largest_loss = min((t.pnl_thb for t in losses), default=0.0)

    # ── Annualized per-trade metrics ──────────────────────────────────────
    annualized_list = []
    capital_days = 0.0
    cashflows = []
    for t in closed_trades:
        days = _safe_days_held(t)
        buy_amt = _safe_buy_amount(t)
        if days and buy_amt and buy_amt > 0:
            capital_days += buy_amt * days
            r = float(getattr(t, "pnl_thb", 0.0)) / buy_amt
            buy_dt = _coerce_datetime(
                getattr(t, "buy_date", None)
                or getattr(t, "entry_date", None)
                or getattr(t, "entry_time", None)
            )
            sell_dt = _coerce_datetime(
                getattr(t, "sell_date", None)
                or getattr(t, "exit_date", None)
                or getattr(t, "exit_time", None)
            )
            if buy_dt and sell_dt:
                cashflows.append((buy_dt, -buy_amt))
                cashflows.append((sell_dt, buy_amt + float(getattr(t, "pnl_thb", 0.0))))
            try:
                ann = ((1.0 + r) ** (365.0 / days) - 1.0) * 100.0
                if math.isfinite(ann):
                    annualized_list.append(ann)
            except Exception:
                pass

    annualized_list.sort()
    best_ann = max(annualized_list) if annualized_list else 0.0
    worst_ann = min(annualized_list) if annualized_list else 0.0
    median_ann = _percentile(annualized_list, 0.5) if annualized_list else 0.0
    top10_ann = _percentile(annualized_list, 0.9) if annualized_list else 0.0
    bottom10_ann = _percentile(annualized_list, 0.1) if annualized_list else 0.0
    xirr_pct = _xirr(sorted(cashflows, key=lambda x: x[0])) * 100.0 if cashflows else 0.0
    avg_capital_year = (capital_days / 365.0) if capital_days > 0 else 0.0

    result = {
        "total_trades":      n,
        "winning_trades":    win_count,
        "losing_trades":     loss_count,
        "win_rate_pct":      round(win_rate * 100, 2),
        "profit_factor":     profit_factor,
        "avg_win_thb":       round(avg_win, 2),
        "avg_loss_thb":      round(avg_loss, 2),    # ค่าลบ
        "expectancy_thb":    round(expectancy, 2),  # คาดหวังต่อ 1 trade
        "max_consec_wins":   max_consec_wins,
        "max_consec_losses": max_consec_losses,
        "gross_profit_thb":  round(gross_profit, 2),
        "gross_loss_thb":    round(gross_loss, 2),  # ค่าลบ
        "net_pnl_thb":       round(net_pnl, 2),
        "total_cost_thb":    round(total_cost, 2),  # spread+commission ทั้งหมด
        "largest_win_thb":   round(largest_win, 2),
        "largest_loss_thb":  round(largest_loss, 2),
        "best_annualized_trade_pct": round(best_ann, 2),
        "worst_annualized_trade_pct": round(worst_ann, 2),
        "median_annualized_pct": round(median_ann, 2),
        "top10_annualized_trade_pct": round(top10_ann, 2),
        "bottom10_annualized_trade_pct": round(bottom10_ann, 2),
        "xirr_pct": round(xirr_pct, 2),
        "avg_capital_per_year_thb": round(avg_capital_year, 2),
    }

    logger.info(
        f"Trade metrics | n={n} | WR={result['win_rate_pct']}% | "
        f"PF={result['profit_factor']} | net={result['net_pnl_thb']:+.2f} THB"
    )
    return result


def add_calmar(trade_metrics: dict, risk_metrics: dict) -> dict:
    """
    เพิ่ม calmar_ratio เข้าไปใน trade_metrics
    Calmar = annualized_return_pct / abs(mdd_pct)
    > 1.0 = ดี, > 2.0 = ดีมาก

    Parameters
    ----------
    trade_metrics : dict จาก calculate_trade_metrics()
    risk_metrics  : dict จาก _compute_risk_metrics() — ต้องมี
                    'annualized_return_pct' และ 'mdd_pct'
    """
    ann_return = risk_metrics.get("annualized_return_pct", 0.0)
    mdd        = risk_metrics.get("mdd_pct", 0.0)

    if abs(mdd) < 1e-6:
        calmar = float("inf") if ann_return > 0 else 0.0
    else:
        calmar = round(ann_return / abs(mdd), 3)

    result = dict(trade_metrics)
    result["calmar_ratio"] = calmar
    return result


# ── Self-test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # สร้าง mock ClosedTrade objects
    from dataclasses import dataclass

    @dataclass
    class MockTrade:
        pnl_thb: float
        cost_thb: float
        is_win: bool = False
        def __post_init__(self):
            self.is_win = self.pnl_thb > 0

    trades = [
        MockTrade(pnl_thb=120.0,  cost_thb=33.0),   # WIN
        MockTrade(pnl_thb=-80.0,  cost_thb=33.0),   # LOSS
        MockTrade(pnl_thb=200.0,  cost_thb=33.0),   # WIN
        MockTrade(pnl_thb=-50.0,  cost_thb=33.0),   # LOSS
        MockTrade(pnl_thb=-30.0,  cost_thb=33.0),   # LOSS
        MockTrade(pnl_thb=90.0,   cost_thb=33.0),   # WIN
    ]

    m = calculate_trade_metrics(trades)
    print("\n=== Trade Metrics ===")
    for k, v in m.items():
        print(f"  {k:<25} {v}")

    # ทดสอบ Calmar
    risk = {"annualized_return_pct": 18.5, "mdd_pct": -12.3}
    m2 = add_calmar(m, risk)
    print(f"\n  calmar_ratio            {m2['calmar_ratio']}")

    # ทดสอบ empty
    m3 = calculate_trade_metrics([])
    print(f"\nEmpty trades: {m3['note']}")

    print("\nDONE ✓")
