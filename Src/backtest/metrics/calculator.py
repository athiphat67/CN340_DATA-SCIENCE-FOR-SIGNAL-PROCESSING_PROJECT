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
from typing import List, Optional

logger = logging.getLogger(__name__)


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
    largest_win  = max(all_pnl) if all_pnl else 0.0
    largest_loss = min(all_pnl) if all_pnl else 0.0

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
