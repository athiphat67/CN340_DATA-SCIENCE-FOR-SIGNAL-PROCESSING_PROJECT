"""
backtest/llm_backtest_runner.py
รัน Portfolio Backtest Engine โดยสร้างสัญญาณจาก LLM จริงหรือ mock

Examples (run from Src/):
    python -m backtest.llm_backtest_runner --providers gemini groq
    python -m backtest.llm_backtest_runner --providers gemini --use-mock
"""

from __future__ import annotations

import argparse
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.insert(0, src_dir)

from backtest.llm_signal_generator import LLMBacktestSignalGenerator, UsageSummary
from backtest.portfolio_engine import PortfolioBacktestEngine, PortfolioSignal
from backtest.prepare_backtest_data import create_walk_forward_windows, load_and_merge


def generate_hold_signals(dates: list[str], model_name: str, reason: str) -> list[PortfolioSignal]:
    return [
        PortfolioSignal(
            date=date_str,
            signal="HOLD",
            confidence=0.0,
            model_name=model_name,
            rationale=reason,
        )
        for date_str in dates
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM portfolio backtest runner")
    parser.add_argument(
        "--providers",
        nargs="+",
        default=["gemini", "groq"],
        help="รายชื่อ provider ที่จะทดสอบ",
    )
    parser.add_argument(
        "--lookback-bars",
        type=int,
        default=10,
        help="จำนวนแท่งย้อนหลังที่ส่งให้ LLM เห็นต่อวัน",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="temperature สำหรับ provider ที่รองรับ",
    )
    parser.add_argument(
        "--use-mock",
        action="store_true",
        help="ใช้ mock mode สำหรับ Gemini แทน API จริง",
    )
    parser.add_argument(
        "--model-override",
        action="append",
        default=[],
        help="override model เป็นรูปแบบ provider=model เช่น gemini=gemini-2.5-flash-lite",
    )
    return parser.parse_args()


def parse_model_overrides(items: list[str]) -> dict[str, str]:
    overrides = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid model override: {item!r}. Expected provider=model")
        provider, model = item.split("=", 1)
        overrides[provider.strip().lower()] = model.strip()
    return overrides


def build_signals(
    model_name: str,
    train_data,
    test_data,
    model_overrides: dict[str, str],
    lookback_bars: int,
    temperature: float,
    use_mock: bool,
) -> tuple[list[PortfolioSignal], UsageSummary]:
    dates = [d.strftime("%Y-%m-%d") for d in test_data["date"]]

    try:
        generator = LLMBacktestSignalGenerator(
            provider=model_name,
            model=model_overrides.get(model_name),
            temperature=temperature,
            lookback_bars=lookback_bars,
            use_mock=use_mock,
        )
        return generator.generate_signals(train_data=train_data, test_data=test_data)
    except Exception as exc:
        usage = UsageSummary(
            provider=model_name,
            model=model_overrides.get(model_name, model_name),
            total_calls=len(dates),
            failed_calls=len(dates),
            last_error=str(exc),
        )
        return (
            generate_hold_signals(dates, model_name, f"LLM unavailable: {exc}"),
            usage,
        )


def main() -> None:
    args = parse_args()
    model_overrides = parse_model_overrides(args.model_override)

    print("Loading data...")
    df = load_and_merge()

    header_lines = []
    header_lines.append(f"Data loaded: {len(df)} bars (XAUUSD + USDTHB merged)")
    header_lines.append(
        f"Date range: {df['date'].iloc[0].date()} -> {df['date'].iloc[-1].date()}"
    )
    header_lines.append(
        f"Price range: {df['price_per_gram'].min():.2f} -> {df['price_per_gram'].max():.2f} THB/gram"
    )
    header_lines.append("Signal source: llm")
    header_lines.append(f"Providers: {', '.join(args.providers)}")
    header_lines.append("")

    windows = create_walk_forward_windows(df)
    header_lines.append(f"Walk-forward windows: {len(windows)}")
    header_lines.append("")

    engine = PortfolioBacktestEngine(
        initial_capital=1500.0,
        spread_pct=0.003,
        min_trade_thb=1000.0,
        force_liquidation=True,
    )
    header_lines.append("Engine config:")
    header_lines.append(f"  Initial capital  : {engine.initial_capital:.2f} THB")
    header_lines.append(f"  Spread           : {engine.spread_pct * 100:.1f}%")
    header_lines.append(f"  Min trade        : {engine.min_trade_thb:.2f} THB")
    header_lines.append(f"  Force liquidation: {engine.force_liquidation}")
    header_lines.append("")

    all_rows: list[dict] = []
    model_logs = {provider: list(header_lines) for provider in args.providers}

    for window in windows:
        year = window["year"]
        month = window["month"]
        quarter = window["quarter"]
        train_data = window["train_data"]
        test_data = window["test_data"]

        window_header = []
        window_header.append("=" * 78)
        window_header.append(f"  WALK-FORWARD WINDOW: {quarter} {year} (Month {month})")
        window_header.append(
            f"  Train: {window['train_start']} -> {window['train_end']} ({window['train_bars']} bars)"
        )
        window_header.append(
            f"  Test:  {window['test_start']} -> {window['test_end']} ({window['test_bars']} bars)"
        )
        window_header.append("=" * 78)
        window_header.append("")

        for model_name in args.providers:
            model_logs[model_name].extend(window_header)
            signals, usage = build_signals(
                model_name=model_name,
                train_data=train_data,
                test_data=test_data,
                model_overrides=model_overrides,
                lookback_bars=args.lookback_bars,
                temperature=args.temperature,
                use_mock=args.use_mock,
            )

            summary = engine.run(
                price_data=test_data,
                signals=signals,
                model_name=model_name,
                window_year=year,
            )

            row = {
                "model_name": model_name,
                "quarter": quarter,
                "window_year": year,
                "final_value": summary.final_value,
                "total_return_pct": summary.total_return_pct,
                "max_drawdown_thb": summary.max_drawdown_thb,
                "sharpe_ratio": summary.sharpe_ratio,
                "vc_return": summary.vc_settlement["return_to_vc"],
                "usage": usage.to_dict(),
            }
            all_rows.append(row)

            ml = model_logs[model_name]
            ml.append(f"  --- {model_name} ---")
            ml.append(f"  Initial Capital : {summary.initial_capital:.2f} THB")
            ml.append(f"  Final Value     : {summary.final_value:.2f} THB")
            ml.append(
                f"  Return          : {summary.total_return_thb:+.2f} THB ({summary.total_return_pct:+.2f}%)"
            )
            ml.append(
                f"  Trades          : {summary.total_trades} (Buy={summary.buy_count}, Sell={summary.sell_count})"
            )
            ml.append(
                f"  Hold/Rejected   : {summary.hold_count} / {summary.rejected_count}"
            )
            ml.append(
                f"  Max Drawdown    : {summary.max_drawdown_thb:.2f} THB ({summary.max_drawdown_pct:.2f}%)"
            )
            ml.append(f"  Sharpe Ratio    : {summary.sharpe_ratio:.4f}")
            ml.append(f"  Spread Cost     : {summary.spread_cost_total:.2f} THB")
            ml.append("  Usage Summary:")
            ml.append(f"    Provider      : {usage.provider}")
            ml.append(f"    Model         : {usage.model}")
            ml.append(f"    Calls         : {usage.total_calls}")
            ml.append(
                f"    Success/Fail  : {usage.successful_calls} / {usage.failed_calls}"
            )
            ml.append(f"    Prompt tokens : {usage.prompt_tokens}")
            ml.append(f"    Output tokens : {usage.completion_tokens}")
            ml.append(f"    Total tokens  : {usage.total_tokens}")
            ml.append(f"    Input cost    : ${usage.input_cost_usd:.6f}")
            ml.append(f"    Output cost   : ${usage.output_cost_usd:.6f}")
            ml.append(f"    Total cost    : ${usage.total_cost_usd:.6f}")
            ml.append(f"    Avg latency   : {usage.avg_latency_ms:.2f} ms")
            if usage.pricing_source:
                ml.append(f"    Pricing src   : {usage.pricing_source}")
            elif usage.total_tokens > 0:
                ml.append("    Pricing src   : unavailable for this model")
            if usage.last_error:
                ml.append(f"    Last error    : {usage.last_error}")
            ml.append("")

    summary_lines = list(header_lines)
    summary_lines.append("=" * 148)
    summary_lines.append("  WALK-FORWARD COMPARISON")
    summary_lines.append("=" * 148)
    header = (
        f"{'Model':<10} {'Q/Year':>8} {'Final':>10} {'Return(%)':>10} "
        f"{'MaxDD':>10} {'Sharpe':>8} {'Calls':>7} {'Tokens':>12} "
        f"{'Cost(USD)':>10} {'AvgLat(ms)':>11} {'VC Return':>10}"
    )
    summary_lines.append(header)
    summary_lines.append("-" * len(header))

    for row in all_rows:
        usage = row["usage"]
        q_year = f"{row['quarter']}/{row['window_year']}"
        summary_lines.append(
            f"{row['model_name']:<10} {q_year:>8} "
            f"{row['final_value']:>10.2f} "
            f"{row['total_return_pct']:>+8.2f}% "
            f"{row['max_drawdown_thb']:>10.2f} "
            f"{row['sharpe_ratio']:>8.4f} "
            f"{usage['total_calls']:>7} "
            f"{usage['total_tokens']:>12} "
            f"{usage['total_cost_usd']:>10.6f} "
            f"{usage['avg_latency_ms']:>11.2f} "
            f"{row['vc_return']:>10.2f}"
        )
        if usage["last_error"]:
            summary_lines.append(f"  note: {row['model_name']} -> {usage['last_error']}")
        elif usage["total_tokens"] > 0 and not usage["pricing_available"]:
            summary_lines.append(
                f"  note: {row['model_name']} -> pricing unavailable for model {usage['model']}"
            )
    summary_lines.append("=" * 148)
    summary_lines.append("")
    summary_lines.append("BACKTEST RUN COMPLETE")

    for model_name in args.providers:
        model_file = os.path.join(current_dir, f"llm_backtest_result_{model_name}.txt")
        with open(model_file, "w", encoding="utf-8") as f:
            f.write("\n".join(model_logs[model_name]))
        print(f"Model log saved: {model_file}")

    summary_file = os.path.join(current_dir, "llm_backtest_result_summary.txt")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    print(f"\nSummary log saved: {summary_file}")


if __name__ == "__main__":
    main()
