"""
run_backtest.py — CLI Entry Point for Gold Trading Backtester
Usage:
    python Src/backtest/run_backtest.py --start 2025-10-01 --end 2025-10-27 --capital 1500
    python Src/backtest/run_backtest.py --source yfinance --start 2026-04-01 --end 2026-04-27
"""

import argparse
import logging
import os
import sys

# Setup path so imports work regardless of cwd
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
_DATA_ENGINE_DIR = os.path.join(_SRC_DIR, "data_engine")
if _DATA_ENGINE_DIR not in sys.path:
    sys.path.insert(0, _DATA_ENGINE_DIR)

from backtest.data_loader import load_backtest_data
from backtest.backtester import Backtester
from backtest.strategies import BuyAndHoldStrategy, TechnicalStrategy, AIAgentStrategy
from backtest.metrics import compute_metrics
from backtest.report import generate_report, save_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

STRATEGY_MAP = {
    "buyhold": ("Buy-and-Hold", BuyAndHoldStrategy),
    "technical": ("Technical (RSI+MACD)", TechnicalStrategy),
    "ai": ("AI Agent (LLM)", AIAgentStrategy),
}


def main():
    parser = argparse.ArgumentParser(description="Gold Trading Backtester")
    parser.add_argument(
        "--start", type=str, default="2025-10-01", help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end", type=str, default="2025-10-27", help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--capital", type=float, default=1500.0, help="Initial capital in THB"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="technical",
        choices=list(STRATEGY_MAP.keys()),
        help="Trading strategy",
    )
    parser.add_argument(
        "--benchmark",
        type=str,
        default="buyhold",
        choices=list(STRATEGY_MAP.keys()),
        help="Benchmark strategy for comparison",
    )
    parser.add_argument(
        "--source",
        type=str,
        default="csv",
        choices=["csv", "yfinance"],
        help="Data source",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="mock",
        help="LLM provider for AI strategy (mock, gemini, groq)",
    )
    parser.add_argument(
        "--fee",
        type=float,
        default=0.0025,
        help="Transaction fee percentage (default 0.25%%)",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Output file path for report"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  GOLD TRADING BACKTESTER")
    print("=" * 60)
    print(f"  Period    : {args.start} → {args.end}")
    print(f"  Capital   : ฿{args.capital:,.2f}")
    print(f"  Strategy  : {args.strategy}")
    print(f"  Benchmark : {args.benchmark}")
    print(f"  Source    : {args.source}")
    print(f"  Fee       : {args.fee:.2%}")
    print(f"  Execution : Next-day (no look-ahead bias)")
    print("=" * 60)

    # ── Load Data ────────────────────────────────────────────────────────
    logger.info("Loading historical data...")
    try:
        data = load_backtest_data(
            start_date=args.start,
            end_date=args.end,
            source=args.source,
        )
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        sys.exit(1)

    print(f"\n  Data loaded: {len(data)} trading days")
    print(f"  Date range: {data.index[0].date()} → {data.index[-1].date()}")

    # ── Run Strategy ─────────────────────────────────────────────────────
    strat_name, strat_cls = STRATEGY_MAP[args.strategy]
    logger.info(f"Running strategy: {strat_name}...")

    if args.strategy == "ai":
        strategy = strat_cls(provider=args.provider)
    else:
        strategy = strat_cls()

    bt = Backtester(data, strategy, initial_capital=args.capital, fee_pct=args.fee)
    result = bt.run()
    metrics = compute_metrics(result["trades"], result["snapshots"], args.capital)

    # ── Run Benchmark ────────────────────────────────────────────────────
    bench_result = None
    bench_metrics = None
    bench_name = ""

    if args.benchmark != args.strategy:
        bench_name, bench_cls = STRATEGY_MAP[args.benchmark]
        logger.info(f"Running benchmark: {bench_name}...")

        if args.benchmark == "ai":
            bench_strategy = bench_cls(provider=args.provider)
        else:
            bench_strategy = bench_cls()

        bench_bt = Backtester(
            data, bench_strategy, initial_capital=args.capital, fee_pct=args.fee
        )
        bench_result = bench_bt.run()
        bench_metrics = compute_metrics(
            bench_result["trades"], bench_result["snapshots"], args.capital
        )

    # ── Generate Report ──────────────────────────────────────────────────
    report = generate_report(
        result=result,
        metrics=metrics,
        strategy_name=strat_name,
        benchmark_result=bench_result,
        benchmark_metrics=bench_metrics,
        benchmark_name=bench_name,
    )

    print("\n" + report)

    # ── Save Report ──────────────────────────────────────────────────────
    if args.output:
        out_path = args.output
    else:
        out_dir = os.path.join(_SCRIPT_DIR)
        os.makedirs(out_dir, exist_ok=True)
        safe_strat = args.strategy.replace(" ", "_")
        out_path = os.path.join(out_dir, f"backtest_result_{safe_strat}.txt")

    save_report(report, out_path)
    print(f"\n✅ Report saved to: {out_path}")

    # ── Also save benchmark report if exists ─────────────────────────────
    if bench_result and bench_metrics:
        bench_report = generate_report(
            result=bench_result,
            metrics=bench_metrics,
            strategy_name=bench_name,
        )
        safe_bench = args.benchmark.replace(" ", "_")
        bench_path = os.path.join(
            os.path.dirname(out_path), f"backtest_result_{safe_bench}.txt"
        )
        save_report(bench_report, bench_path)
        print(f"✅ Benchmark report saved to: {bench_path}")


if __name__ == "__main__":
    main()
