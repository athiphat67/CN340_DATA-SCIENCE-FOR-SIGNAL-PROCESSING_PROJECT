"""
report.py — Text Report Generator for Backtesting
Generates summary reports with VC settlement, trade logs, and strategy comparison.
"""

from datetime import datetime
from typing import Optional


def generate_report(
    result: dict,
    metrics,
    strategy_name: str = "Strategy",
    benchmark_result: Optional[dict] = None,
    benchmark_metrics=None,
    benchmark_name: str = "Buy-and-Hold",
) -> str:
    """
    Generate a full text report from backtest results.

    Parameters
    ----------
    result : dict from Backtester.run()
    metrics : PerformanceMetrics
    strategy_name : str
    benchmark_result : optional dict from benchmark Backtester.run()
    benchmark_metrics : optional PerformanceMetrics for benchmark
    benchmark_name : str

    Returns
    -------
    str : formatted text report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("  GOLD TRADING BACKTEST REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)

    # ── Project Rules ────────────────────────────────────────────────────
    lines.append("")
    lines.append("── Project Rules ──")
    lines.append(f"  Initial Capital (VC)  : ฿{result['initial_capital']:,.2f}")
    lines.append(f"  Trading Period        : {_get_date_range(result)}")
    lines.append(f"  Min Buy Amount        : ฿1,000 (ออม NOW)")
    lines.append(f"  Strategy              : {strategy_name}")
    lines.append("")

    # ── Portfolio Summary ────────────────────────────────────────────────
    lines.append("── Portfolio Summary ──")
    lines.append(f"  Final Balance         : ฿{result['final_balance']:,.2f}")
    lines.append(f"  Total PnL             : ฿{metrics.total_pnl_thb:,.2f}")
    lines.append(f"  Total Return          : {metrics.total_return_pct:+.2f}%")
    lines.append("")

    # ── VC Settlement ────────────────────────────────────────────────────
    settlement = result.get("settlement")
    if settlement:
        lines.append("── VC Settlement ──")
        lines.append(f"  {settlement.summary()}")
        if settlement.is_profit:
            lines.append(f"  Your profit share     : ฿{settlement.keep_profit:,.2f}")
        lines.append("")

    # ── Performance Metrics ──────────────────────────────────────────────
    lines.append("── Performance Metrics ──")
    lines.append(f"  Total Signals         : {metrics.total_signals}")
    lines.append(f"    BUY                 : {metrics.buy_count}")
    lines.append(f"    SELL                : {metrics.sell_count}")
    lines.append(f"    HOLD                : {metrics.hold_count}")
    lines.append(f"  Total Trades (pairs)  : {metrics.total_trades}")
    lines.append(f"  Win Rate              : {metrics.win_rate:.1%}")
    lines.append(f"  Avg Risk-Reward       : {metrics.avg_rr:.2f}")
    lines.append(f"  Max Drawdown          : {metrics.max_drawdown_pct:.2f}% (฿{metrics.max_drawdown_thb:,.2f})")
    lines.append(f"  Sharpe Ratio          : {metrics.sharpe_ratio:.4f}")
    lines.append(f"  Sortino Ratio         : {metrics.sortino_ratio:.4f}")
    if metrics.total_trades > 0:
        lines.append(f"  Avg Trade PnL         : ฿{metrics.avg_trade_pnl:,.2f}")
        lines.append(f"  Best Trade            : ฿{metrics.best_trade_pnl:,.2f}")
        lines.append(f"  Worst Trade           : ฿{metrics.worst_trade_pnl:,.2f}")
        pf_str = f"{metrics.profit_factor:.2f}" if metrics.profit_factor != float("inf") else "∞"
        lines.append(f"  Profit Factor         : {pf_str}")
    lines.append("")

    # ── Benchmark Comparison ─────────────────────────────────────────────
    if benchmark_result and benchmark_metrics:
        lines.append("── Strategy Comparison ──")
        lines.append(f"  {'Metric':<24} {'Strategy':>12} {'Benchmark':>12}")
        lines.append(f"  {'-'*24} {'-'*12} {'-'*12}")

        rows = [
            ("Final Balance", f"฿{result['final_balance']:,.2f}", f"฿{benchmark_result['final_balance']:,.2f}"),
            ("Total PnL", f"฿{metrics.total_pnl_thb:,.2f}", f"฿{benchmark_metrics.total_pnl_thb:,.2f}"),
            ("Return %", f"{metrics.total_return_pct:+.2f}%", f"{benchmark_metrics.total_return_pct:+.2f}%"),
            ("Win Rate", f"{metrics.win_rate:.1%}", f"{benchmark_metrics.win_rate:.1%}"),
            ("Max Drawdown", f"{metrics.max_drawdown_pct:.2f}%", f"{benchmark_metrics.max_drawdown_pct:.2f}%"),
            ("Sharpe Ratio", f"{metrics.sharpe_ratio:.4f}", f"{benchmark_metrics.sharpe_ratio:.4f}"),
            ("Sortino Ratio", f"{metrics.sortino_ratio:.4f}", f"{benchmark_metrics.sortino_ratio:.4f}"),
        ]
        for label, strat_val, bench_val in rows:
            lines.append(f"  {label:<24} {strat_val:>12} {bench_val:>12}")

        # Winner
        strat_better = metrics.total_pnl_thb > benchmark_metrics.total_pnl_thb
        winner = strategy_name if strat_better else benchmark_name
        lines.append(f"\n  Winner: {winner}")
        lines.append("")

    # ── Trade Log ────────────────────────────────────────────────────────
    trades = result.get("trades", [])
    if trades:
        lines.append("── Trade Log ──")
        lines.append(f"  {'#':<4} {'Date':<12} {'Action':<6} {'Grams':>10} {'Price/g':>12} {'Amount':>12} {'Cash After':>12}")
        lines.append(f"  {'-'*4} {'-'*12} {'-'*6} {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
        for i, t in enumerate(trades, 1):
            lines.append(
                f"  {i:<4} {t.date:<12} {t.action:<6} "
                f"{t.gold_grams:>10.4f} {t.price_per_gram:>12.2f} "
                f"{t.amount_thb:>12.2f} {t.cash_after:>12.2f}"
            )
        lines.append("")

    # ── Daily Snapshots ──────────────────────────────────────────────────
    snapshots = result.get("snapshots", [])
    if snapshots:
        lines.append("── Daily Portfolio ──")
        lines.append(f"  {'Date':<12} {'Signal':<12} {'Cash':>12} {'Gold(g)':>10} {'Gold Value':>12} {'Total':>12}")
        lines.append(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*10} {'-'*12} {'-'*12}")
        for s in snapshots:
            lines.append(
                f"  {s.date:<12} {s.signal:<12} "
                f"{s.cash_balance:>12.2f} {s.gold_grams:>10.4f} "
                f"{s.gold_value_thb:>12.2f} {s.total_value:>12.2f}"
            )
        lines.append("")

    lines.append("=" * 70)
    lines.append("  END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


def _get_date_range(result: dict) -> str:
    """Extract date range from snapshots."""
    snapshots = result.get("snapshots", [])
    if not snapshots:
        return "N/A"
    return f"{snapshots[0].date} → {snapshots[-1].date}"


def save_report(report_text: str, filepath: str) -> None:
    """Save report text to file."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)
