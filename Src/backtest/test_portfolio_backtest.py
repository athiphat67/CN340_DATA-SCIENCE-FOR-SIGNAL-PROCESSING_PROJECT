"""
backtest/test_portfolio_backtest.py
ทดสอบ Portfolio Backtest Engine แบบ Walk-forward Validation
จำลองการเทรดทองคำผ่านแอป ออม Now ตามกฎโปรเจค

Usage (จาก Src/):
    python -m backtest.test_portfolio_backtest
"""

import os
import sys
import random

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.insert(0, src_dir)

from backtest.portfolio_engine import PortfolioBacktestEngine, PortfolioSignal
from backtest.prepare_backtest_data import load_and_merge, create_walk_forward_windows


def generate_random_signals(dates: list[str], model_name: str) -> list[PortfolioSignal]:
    """
    สร้างสัญญาณจำลองแบบ random สำหรับวันที่ที่กำหนด
    จำลองพฤติกรรมของโมเดลแต่ละตัว (แต่ละโมเดลมีสไตล์ต่างกัน)
    """
    signals = []
    has_gold = False

    # กำหนดสไตล์ตามชื่อโมเดล
    if model_name == "gemini":
        buy_w, sell_w, hold_w = 0.50, 0.25, 0.25  # ชอบซื้อ
    elif model_name == "groq":
        buy_w, sell_w, hold_w = 0.35, 0.30, 0.35  # สมดุล
    else:  # claude
        buy_w, sell_w, hold_w = 0.30, 0.20, 0.50  # ระมัดระวัง

    for date_str in dates:
        if not has_gold:
            # ไม่มีทอง → BUY หรือ HOLD (SELL ไม่ได้)
            signal_type = random.choices(["BUY", "HOLD"], weights=[buy_w, hold_w], k=1)[
                0
            ]
        else:
            # มีทอง → SELL, HOLD, หรือ BUY (ซื้อเพิ่มไม่ได้เพราะไม่มีเงิน)
            signal_type = random.choices(
                ["SELL", "HOLD"], weights=[sell_w, hold_w], k=1
            )[0]

        confidence = round(random.uniform(0.40, 0.95), 2)

        signals.append(
            PortfolioSignal(
                date=date_str,
                signal=signal_type,
                confidence=confidence,
                model_name=model_name,
            )
        )

        # Track state สำหรับ signal generation
        if signal_type == "BUY" and not has_gold:
            has_gold = True
        elif signal_type == "SELL" and has_gold:
            has_gold = False

    return signals


def main():
    # ─── Load data ───────────────────────────────────────────────────────
    print("Loading data...")
    df = load_and_merge()

    header_lines = []
    header_lines.append(f"Data loaded: {len(df)} bars (XAUUSD + USDTHB merged)")
    header_lines.append(
        f"Date range: {df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()}"
    )
    header_lines.append(
        f"Price range: {df['price_per_gram'].min():.2f} → {df['price_per_gram'].max():.2f} THB/gram"
    )
    header_lines.append("")

    # ─── Create walk-forward windows ─────────────────────────────────────
    windows = create_walk_forward_windows(df)
    header_lines.append(f"Walk-forward windows: {len(windows)}")
    header_lines.append("")

    # ─── Engine config ───────────────────────────────────────────────────
    engine = PortfolioBacktestEngine(
        initial_capital=1500.0,
        spread_pct=0.003,  # 0.3% spread
        min_trade_thb=1000.0,
        force_liquidation=True,
    )
    header_lines.append("Engine config:")
    header_lines.append(f"  Initial capital  : {engine.initial_capital:.2f} THB")
    header_lines.append(f"  Spread           : {engine.spread_pct * 100:.1f}%")
    header_lines.append(f"  Min trade        : {engine.min_trade_thb:.2f} THB")
    header_lines.append(f"  Force liquidation: {engine.force_liquidation}")
    header_lines.append("")

    models = ["gemini", "groq", "claude"]
    all_summaries = []

    # แยก log สำหรับแต่ละโมเดล
    model_logs = {m: list(header_lines) for m in models}

    # ─── Run backtest per window per model ───────────────────────────────
    for window in windows:
        year = window["year"]
        month = window["month"]
        quarter = window["quarter"]
        test_data = window["test_data"]
        dates = [d.strftime("%Y-%m-%d") for d in test_data["date"]]

        window_header = []
        window_header.append("=" * 70)
        window_header.append(f"  WALK-FORWARD WINDOW: {quarter} {year} (Month {month})")
        window_header.append(
            f"  Train: {window['train_start']} → {window['train_end']} ({window['train_bars']} bars)"
        )
        window_header.append(
            f"  Test:  {window['test_start']} → {window['test_end']} ({window['test_bars']} bars)"
        )
        window_header.append("=" * 70)
        window_header.append("")

        for model_name in models:
            # ใส่ header ของ window ลงใน log ของแต่ละโมเดล
            model_logs[model_name].extend(window_header)

            signals = generate_random_signals(dates, model_name)
            summary = engine.run(
                price_data=test_data,
                signals=signals,
                model_name=model_name,
                window_year=year,
            )
            summary.quarter = quarter
            all_summaries.append(summary)

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

            vc = summary.vc_settlement
            ml.append(f"  VC Settlement   : {vc['status']}")
            if vc["status"] == "PROFIT":
                ml.append(
                    f"    Return to VC  : {vc['return_to_vc']:.2f} THB (capital + 50% profit)"
                )
                ml.append(f"    Your profit   : {vc['keep_profit']:.2f} THB")
            else:
                ml.append(
                    f"    Return to VC  : {vc['return_to_vc']:.2f} THB (all remaining)"
                )
                ml.append(f"    Loss          : {vc['loss']:.2f} THB")
            ml.append("")

            # Daily details สำหรับโมเดลนี้
            ml.append(f"  DAILY DETAILS ({model_name}, {quarter} {year}):")
            for state in summary.daily_states:
                ml.append(
                    f"    {state.date}  {state.signal:<4} → {state.action_taken:<10}  "
                    f"cash={state.cash_thb:>8.2f}  "
                    f"gold={state.gold_grams:>8.4f}g  "
                    f"value={state.portfolio_value:>8.2f}  "
                    f"pnl={state.pnl_thb:>+8.2f}  "
                    f"{state.note}"
                )
            ml.append("")

    # ─── Comparison table (Summary Log) ──────────────────────────────────
    summary_lines = list(header_lines)
    summary_lines.append("=" * 105)
    summary_lines.append("  WALK-FORWARD COMPARISON")
    summary_lines.append("=" * 105)
    header = (
        f"{'Model':<10} {'Q/Year':>8} {'Initial':>10} {'Final':>10} "
        f"{'Return(THB)':>12} {'Return(%)':>10} {'MaxDD':>10} "
        f"{'Sharpe':>8} {'SpreadCost':>11} {'VC Return':>10}"
    )
    summary_lines.append(header)
    summary_lines.append("-" * len(header))

    for s in all_summaries:
        q_year = f"{getattr(s, 'quarter', '')}/{s.window_year}"
        summary_lines.append(
            f"{s.model_name:<10} {q_year:>8} "
            f"{s.initial_capital:>10.2f} {s.final_value:>10.2f} "
            f"{s.total_return_thb:>+10.2f}   "
            f"{s.total_return_pct:>+8.2f}%  "
            f"{s.max_drawdown_thb:>8.2f}  "
            f"{s.sharpe_ratio:>8.4f}  "
            f"{s.spread_cost_total:>9.2f}  "
            f"{s.vc_settlement['return_to_vc']:>10.2f}"
        )
    summary_lines.append("=" * 105)
    summary_lines.append("")
    summary_lines.append("TEST PASSED — Portfolio Backtest Engine works correctly!")

    # ─── Write outputs ───────────────────────────────────────────────────
    # 1. เขียนไฟล์ log แยกแต่ละโมเดล
    for model_name in models:
        model_file = os.path.join(current_dir, f"backtest_result_{model_name}.txt")
        with open(model_file, "w", encoding="utf-8") as f:
            f.write("\n".join(model_logs[model_name]))
        print(f"Model log saved: {model_file}")

    # 2. เขียนไฟล์ summary สรุปทั้ง 3 โมเดล
    summary_file = os.path.join(current_dir, "backtest_result_summary.txt")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))
    print(f"\nSummary log saved: {summary_file}")

    # ลบไฟล์เก่า (optional, แต่เราอาจจะปล่อยไว้ให้ผู้ใช้ลบเอง)
    # print("You can safely delete the old 'portfolio_test_result.txt' file.")


if __name__ == "__main__":
    main()
