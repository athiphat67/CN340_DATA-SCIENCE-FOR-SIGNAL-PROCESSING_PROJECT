"""
Walk-Forward Backtest — Nakkhutthong Framework
================================================
ทดสอบตามที่อาจารย์กำหนด:
  รอบ 1: Train ม.ค.68-ธ.ค.68  → Test ม.ค.69
  รอบ 2: Train ม.ค.68-ม.ค.69  → Test ก.พ.69
  รอบ 3: Train ม.ค.68-ก.พ.69  → Test มี.ค.69
  รอบ 4: Train ม.ค.68-มี.ค.68 → Test เม.ย.69

วิธีใช้:
  python walk_forward_backtest.py
  python walk_forward_backtest.py --csv path/to/data.csv
  python walk_forward_backtest.py --csv path/to/data.csv --output results/
"""

import argparse
import os
import json
import math
import warnings
from datetime import date, datetime
from typing import Optional

import pandas as pd
import requests

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────
# Mistral API (เพื่อน Deploy ไว้)
MISTRAL_API_URL = "https://gold-trader-bot.nakkhutong-ai.workers.dev"

# ──────────────────────────────────────────────
# CONSTANTS (ใช้ค่าเดียวกับ portfolio.py ของเพื่อน)
# ──────────────────────────────────────────────
SPREAD_THB       = 0.0   # ตรงกับระบบจริง (ฮั่วเซ่งเฮงออกให้)
COMMISSION_THB   = 0.0   # ตรงกับระบบจริง (SCB EASY ฟรี)
GOLD_GRAM_PER_BAHT = 15.244
INITIAL_CASH     = 1_500.0
BUST_THRESHOLD   = 1_000.0
RISK_FREE_RATE   = 0.015   # อัตราดอกเบี้ยไทย 1.5%

# ──────────────────────────────────────────────
# Walk-Forward Windows (Expanding Window)
# ──────────────────────────────────────────────
WALK_FORWARD_WINDOWS = [
    {
        "round":      1,
        "label":      "Test ม.ค. 69",
        "train_start": "2025-01-01",
        "train_end":   "2025-12-31",
        "test_start":  "2026-01-01",
        "test_end":    "2026-01-31",
        "season_note": "ต้นปี นักลงทุนเปิด position ใหม่",
    },
    {
        "round":      2,
        "label":      "Test ก.พ. 69",
        "train_start": "2025-01-01",
        "train_end":   "2026-01-31",
        "test_start":  "2026-02-01",
        "test_end":    "2026-02-28",
        "season_note": "วาเลนไทน์ / ทองคำเป็นของขวัญ",
    },
    {
        "round":      3,
        "label":      "Test มี.ค. 69",
        "train_start": "2025-01-01",
        "train_end":   "2026-02-28",
        "test_start":  "2026-03-01",
        "test_end":    "2026-03-31",
        "season_note": "ปิดเทอม / สิ้นไตรมาส",
    },
    {
        "round":      4,
        "label":      "Test เม.ย. 69",
        "train_start": "2025-01-01",
        "train_end":   "2026-03-31",
        "test_start":  "2026-04-01",
        "test_end":    "2026-04-30",
        "season_note": "สงกรานต์ / เปิดเทอม",
    },
]


# ──────────────────────────────────────────────
# 1. DATA LOADER
# ──────────────────────────────────────────────

def load_csv(csv_path: str) -> pd.DataFrame:
    """โหลด CSV และคำนวณ Technical Indicators — รองรับทั้ง 2 format"""
    df = pd.read_csv(csv_path)

    # รองรับ format ใหม่ (GLD965_5m: datetime,open,high,low,close)
    # และ format เก่า (Datetime,Open,High,Low,Close,Volume)
    if "datetime" in df.columns:
        df = df.drop(columns=["timestamp"], errors="ignore")  # ลบ column timestamp (เลขลำดับ) ออก
        df = df.rename(columns={"datetime": "timestamp", "close": "close_thai",
                                 "open": "open_thai", "high": "high_thai", "low": "low_thai"})
    elif "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "timestamp", "Close": "close_thai",
                                 "Open": "open_thai", "High": "high_thai",
                                 "Low": "low_thai", "Volume": "volume"})

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # คำนวณ Indicators
    df = _add_indicators(df)

    # ── DATA LEAK PREVENTION ──
    # shift(1) ทุก indicator เพื่อให้แน่ใจว่า candle ปัจจุบัน
    # ใช้ได้เฉพาะข้อมูลที่รู้แล้ว ไม่มี look-ahead bias
    indicator_cols = ["rsi", "macd_line", "signal_line", "macd_hist",
                      "ema_20", "ema_50", "bb_upper", "bb_mid", "bb_lower", "atr"]
    for col in indicator_cols:
        if col in df.columns:
            df[col] = df[col].shift(1)

    # drop warmup bars (~50 แรก)
    df = df.iloc[50:].reset_index(drop=True)
    return df


def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close_thai"]

    # RSI(14)
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / loss.replace(0, float("nan"))
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD(12/26/9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd_line"]   = ema12 - ema26
    df["signal_line"] = df["macd_line"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]   = df["macd_line"] - df["signal_line"]

    # EMA(20/50)
    df["ema_20"] = close.ewm(span=20, adjust=False).mean()
    df["ema_50"] = close.ewm(span=50, adjust=False).mean()

    # Bollinger Bands(20, 2)
    df["bb_mid"]   = close.rolling(20).mean()
    bb_std         = close.rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * bb_std
    df["bb_lower"] = df["bb_mid"] - 2 * bb_std

    # ATR(14)
    high, low = df["high_thai"], df["low_thai"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs()
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    return df


# ──────────────────────────────────────────────
# 2. SIMPLE SIGNAL ENGINE (Rule-based — ไม่ใช้ LLM)
# ──────────────────────────────────────────────

def _rule_prefilter(rsi, macd, close, ema20, ema50) -> str:
    """
    Rule-based pre-filter — กรองเฉพาะ candle ที่น่าสนใจ
    ก่อนส่งให้ Mistral API ตัดสินใจขั้นสุดท้าย
    """
    bullish = sum([rsi < 45, macd > 0, close > ema20, ema20 > ema50])
    bearish = sum([rsi > 55, macd < 0, close < ema20, ema20 < ema50])
    if bullish >= 3: return "BUY_CANDIDATE"
    if bearish >= 3: return "SELL_CANDIDATE"
    return "HOLD"


def generate_signal(row: pd.Series, mode: str = "smart") -> str:
    """
    3 modes:
      rule  — Rule-based อย่างเดียว (เร็ว ไม่เรียก API)
      api   — เรียก Mistral ทุก candle (ช้า แต่ใช้ AI จริง)
      smart — Rule-based กรองก่อน แล้วส่งให้ Mistral เฉพาะ candle น่าสนใจ (แนะนำ)
    """
    rsi   = row.get("rsi", 50)
    macd  = row.get("macd_hist", 0)
    ema20 = row.get("ema_20", 0)
    ema50 = row.get("ema_50", 0)
    close = row.get("close_thai", 0)

    if pd.isna(rsi) or pd.isna(macd):
        return "HOLD"

    # ── MODE: rule ──
    if mode == "rule":
        bullish = sum([rsi < 45, macd > 0, close > ema20, ema20 > ema50])
        bearish = sum([rsi > 55, macd < 0, close < ema20, ema20 < ema50])
        if bullish >= 3: return "BUY"
        if bearish >= 3: return "SELL"
        return "HOLD"

    # ── MODE: smart (แนะนำ) ──
    if mode == "smart":
        prefilter = _rule_prefilter(rsi, macd, close, ema20, ema50)
        if prefilter == "HOLD":
            return "HOLD"  # ไม่ต้องเรียก API เลย
        # เฉพาะ candidate เท่านั้นที่ส่งให้ Mistral
        action_hint = "BUY" if prefilter == "BUY_CANDIDATE" else "SELL"
    else:
        action_hint = None  # mode: api — ส่งทุก candle

    # ── เรียก Mistral API ──
    try:
        prompt = (
            f"ราคาทองคำ 96.5%: {close:.0f} บาท "
            f"RSI: {rsi:.1f} "
            f"MACD Histogram: {macd:.2f} "
            f"EMA20: {ema20:.0f} EMA50: {ema50:.0f}"
        )
        res = requests.post(
            MISTRAL_API_URL,
            json={"prompt": prompt},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        data = res.json().get("data", "").upper()
        if "BUY"  in data: return "BUY"
        if "SELL" in data: return "SELL"
        return "HOLD"
    except Exception:
        # fallback: ใช้ rule hint ถ้า API ไม่ตอบ
        if action_hint: return action_hint
        return "HOLD"


# ──────────────────────────────────────────────
# 3. PORTFOLIO SIMULATOR
# ──────────────────────────────────────────────

class SimPortfolio:
    def __init__(self):
        self.cash        = INITIAL_CASH
        self.gold_grams  = 0.0
        self.cost_basis  = 0.0
        self.closed_trades = []
        self._open_trade = None
        self.bust        = False

    def total_value(self, price: float) -> float:
        return self.cash + (self.gold_grams / GOLD_GRAM_PER_BAHT) * price

    def buy(self, price: float, timestamp):
        if self.gold_grams > 0 or self.cash < INITIAL_CASH * 0.4:
            return False
        pos_size     = self.cash * 0.6
        total_cost   = pos_size + SPREAD_THB + COMMISSION_THB
        if total_cost > self.cash:
            return False
        self.cash       -= total_cost
        self.gold_grams += (pos_size / price) * GOLD_GRAM_PER_BAHT
        self.cost_basis  = price
        self._open_trade = {"entry_price": price, "entry_time": timestamp,
                            "pos_size": pos_size}
        if self.total_value(price) < BUST_THRESHOLD:
            self.bust = True
        return True

    def sell(self, price: float, timestamp):
        if self.gold_grams <= 0:
            return False
        proceeds     = (self.gold_grams / GOLD_GRAM_PER_BAHT) * price
        net_proceeds = proceeds - SPREAD_THB - COMMISSION_THB
        pnl          = net_proceeds - self._open_trade["pos_size"]
        self.closed_trades.append({
            "entry_price":  self._open_trade["entry_price"],
            "exit_price":   price,
            "entry_time":   self._open_trade["entry_time"],
            "exit_time":    timestamp,
            "pnl_thb":      round(pnl, 2),
            "is_win":       pnl > 0,
            "days_held":    (timestamp - self._open_trade["entry_time"]).days
        })
        self.cash       += net_proceeds
        self.gold_grams  = 0.0
        self.cost_basis  = 0.0
        self._open_trade = None
        if self.total_value(price) < BUST_THRESHOLD:
            self.bust = True
        return True


# ──────────────────────────────────────────────
# 4. METRICS CALCULATOR
# ──────────────────────────────────────────────

def calculate_metrics(trades: list, equity_curve: list, risk_free: float = RISK_FREE_RATE) -> dict:
    if not trades:
        return {"error": "ไม่มี closed trades"}

    wins   = [t for t in trades if t["is_win"]]
    losses = [t for t in trades if not t["is_win"]]

    total_profit  = round(sum(t["pnl_thb"] for t in trades), 2)
    win_rate      = round(len(wins) / len(trades) * 100, 2)
    avg_win       = round(sum(t["pnl_thb"] for t in wins) / len(wins), 2) if wins else 0
    avg_loss      = round(sum(t["pnl_thb"] for t in losses) / len(losses), 2) if losses else 0
    profit_factor = round(abs(sum(t["pnl_thb"] for t in wins)) /
                          max(abs(sum(t["pnl_thb"] for t in losses)), 0.01), 2)
    expectancy    = round((win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss), 2)

    # Annualized returns per trade
    ann_returns = []
    for t in trades:
        days = max(t.get("days_held", 1), 1)
        pct  = t["pnl_thb"] / INITIAL_CASH
        ann  = pct * (365 / days)
        ann_returns.append(ann)

    ann_sorted = sorted(ann_returns)
    n = len(ann_sorted)

    # Equity curve metrics
    equity = pd.Series(equity_curve)
    returns = equity.pct_change().dropna()
    mdd     = _max_drawdown(equity)
    sharpe  = _sharpe(returns, risk_free)
    ann_ret = round((equity.iloc[-1] / equity.iloc[0] - 1) * 100, 2) if len(equity) > 1 else 0
    calmar  = round(ann_ret / abs(mdd) if mdd != 0 else 0, 2)

    # XIRR approximation
    xirr_val = round(ann_ret / 100, 4) if ann_ret else 0

    return {
        "Total Closed Trade":          len(trades),
        "Win Rate (%)":                f"{win_rate:.2f}%",
        "Total Profit (THB)":          total_profit,
        "Average Win (THB)":           avg_win,
        "Average Loss (THB)":          avg_loss,
        "Expectancy per Trade (THB)":  expectancy,
        "Profit Factor":               profit_factor,
        "Best Annualized Trade (%)":   f"{max(ann_returns)*100:.2f}%" if ann_returns else "N/A",
        "Worst Annualized Trade (%)":  f"{min(ann_returns)*100:.2f}%" if ann_returns else "N/A",
        "Median Annualized Trade (%)": f"{ann_sorted[n//2]*100:.2f}%" if ann_returns else "N/A",
        "Top 10% Annualized":          f"{ann_sorted[int(n*0.9)]*100:.2f}%" if n >= 2 else "N/A",
        "Bottom 10% Annualized":       f"{ann_sorted[int(n*0.1)]*100:.2f}%" if n >= 2 else "N/A",
        "XIRR (approx)":               f"{xirr_val*100:.2f}%",
        "Max Drawdown (%)":            f"{mdd:.2f}%",
        "Sharpe Ratio":                sharpe,
        "Calmar Ratio":                calmar,
        "Annualized Return (%)":       f"{ann_ret:.2f}%",
    }


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd   = (equity - peak) / peak * 100
    return round(dd.min(), 2)


def _sharpe(returns: pd.Series, risk_free: float) -> float:
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    excess = returns.mean() - risk_free / 252
    return round(excess / returns.std() * math.sqrt(252), 4)


# ──────────────────────────────────────────────
# 5. WALK-FORWARD ENGINE
# ──────────────────────────────────────────────

def run_single_window(df: pd.DataFrame, window: dict, mode: str = "smart") -> dict:
    """รัน Backtest สำหรับ 1 window"""

    # แบ่ง Train / Test — ป้องกัน Data Leak
    train_mask = (df["timestamp"] >= window["train_start"]) & \
                 (df["timestamp"] <= window["train_end"])
    test_mask  = (df["timestamp"] >= window["test_start"]) & \
                 (df["timestamp"] <= window["test_end"])

    df_train = df[train_mask].copy()
    df_test  = df[test_mask].copy()

    print(f"\n{'='*60}")
    print(f"รอบที่ {window['round']}: {window['label']}")
    print(f"  Train: {window['train_start']} → {window['train_end']} ({len(df_train):,} candles)")
    print(f"  Test:  {window['test_start']} → {window['test_end']} ({len(df_test):,} candles)")
    print(f"  ฤดูกาล: {window['season_note']}")

    if len(df_test) == 0:
        print(f"  ⚠️  ไม่มีข้อมูลช่วง Test")
        return {"round": window["round"], "label": window["label"], "error": "ไม่มีข้อมูล Test"}

    # รัน Simulation บน Test data
    portfolio    = SimPortfolio()
    equity_curve = [INITIAL_CASH]
    trade_log    = []

    for _, row in df_test.iterrows():
        if portfolio.bust:
            break

        signal = generate_signal(row, mode=mode)
        price  = row["close_thai"]
        ts     = row["timestamp"]

        if signal == "BUY":
            portfolio.buy(price, ts)
        elif signal == "SELL":
            portfolio.sell(price, ts)

        equity_curve.append(portfolio.total_value(price))

    # เก็บ trade log
    for t in portfolio.closed_trades:
        trade_log.append({
            "round":        window["round"],
            "entry_price":  t["entry_price"],
            "exit_price":   t["exit_price"],
            "entry_time":   str(t["entry_time"]),
            "exit_time":    str(t["exit_time"]),
            "pnl_thb":      t["pnl_thb"],
            "is_win":       t["is_win"],
            "days_held":    t["days_held"],
        })

    metrics = calculate_metrics(portfolio.closed_trades, equity_curve)

    print(f"\n  📊 ผลลัพธ์:")
    for k, v in metrics.items():
        print(f"     {k:<35} {v}")

    return {
        "round":       window["round"],
        "label":       window["label"],
        "season_note": window["season_note"],
        "train_bars":  len(df_train),
        "test_bars":   len(df_test),
        "metrics":     metrics,
        "trade_log":   trade_log,
        "equity_curve": equity_curve,
    }


def run_walk_forward(csv_path: str, output_dir: str = "output", mode: str = "smart"):
    """รัน Walk-Forward Backtest ทั้ง 4 รอบ"""

    print("="*60)
    print("WALK-FORWARD BACKTEST — Nakkhutthong Framework")
    print("="*60)
    print(f"📂 CSV: {csv_path}")
    print(f"⚙️  Mode: {mode.upper()} {'(Rule-based)' if mode=='rule' else '(Mistral API + Rule filter)' if mode=='smart' else '(Mistral API ทุก candle)'}")

    # โหลดข้อมูล
    df = load_csv(csv_path)
    print(f"📊 ข้อมูลทั้งหมด: {len(df):,} candles")
    print(f"   ตั้งแต่: {df['timestamp'].min()} ถึง {df['timestamp'].max()}")

    # รัน 4 รอบ
    all_results = []
    for window in WALK_FORWARD_WINDOWS:
        result = run_single_window(df, window, mode=mode)
        all_results.append(result)

    # สรุปการเปรียบเทียบ 4 เดือน
    print(f"\n{'='*60}")
    print("📈 สรุปเปรียบเทียบทั้ง 4 เดือน")
    print(f"{'='*60}")
    print(f"{'เดือน':<20} {'Win Rate':>10} {'Total Profit':>14} {'Sharpe':>8} {'MDD':>8}")
    print("-"*60)

    for r in all_results:
        if "error" in r:
            print(f"{r['label']:<20} {'ไม่มีข้อมูล':>40}")
            continue
        m = r["metrics"]
        print(f"{r['label']:<20} "
              f"{m.get('Win Rate (%)', 'N/A'):>10} "
              f"{str(m.get('Total Profit (THB)', 'N/A')):>14} "
              f"{str(m.get('Sharpe Ratio', 'N/A')):>8} "
              f"{m.get('Max Drawdown (%)', 'N/A'):>8}")

    # วิเคราะห์ Variation
    _analyze_variation(all_results)

    # Export ผลลัพธ์
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "walk_forward_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        # แปลง equity_curve ออกก่อน save (ข้อมูลเยอะเกินไป)
        save_results = []
        for r in all_results:
            r_copy = r.copy()
            r_copy.pop("equity_curve", None)
            save_results.append(r_copy)
        json.dump(save_results, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n✅ บันทึกผลลัพธ์ที่: {output_path}")

    # Export Trade Log + Summary ตาม format อาจารย์
    export_trade_log(all_results, output_dir)
    export_summary(all_results, output_dir)

    return all_results


def _analyze_variation(results: list):
    """วิเคราะห์ความแตกต่างระหว่างแต่ละเดือน"""
    print(f"\n{'='*60}")
    print("🔍 วิเคราะห์ Variation ระหว่างเดือน")
    print(f"{'='*60}")

    valid = [r for r in results if "metrics" in r]
    if len(valid) < 2:
        print("  ข้อมูลไม่พอวิเคราะห์")
        return

    profits = [r["metrics"].get("Total Profit (THB)", 0) for r in valid]
    labels  = [r["label"] for r in valid]

    max_profit = max(profits)
    min_profit = min(profits)
    variation  = max_profit - min_profit

    print(f"  เดือนที่ดีที่สุด:   {labels[profits.index(max_profit)]} ({max_profit:+.2f} THB)")
    print(f"  เดือนที่แย่ที่สุด:  {labels[profits.index(min_profit)]} ({min_profit:+.2f} THB)")
    print(f"  Variation (ช่วงห่าง): {variation:.2f} THB")

    if variation > 500:
        print("  ⚠️  Variation สูง — ผลลัพธ์แต่ละเดือนต่างกันมาก")
        print("       อาจมีปัจจัยตามฤดูกาลหรือ Event พิเศษ")
    else:
        print("  ✅  Variation ต่ำ — ผลลัพธ์ค่อนข้างสม่ำเสมอ")

    print("\n  ปัจจัยที่ควรวิเคราะห์เพิ่มเติม:")
    for r in valid:
        print(f"    - {r['label']}: {r['season_note']}")


# ──────────────────────────────────────────────
# 6. ENTRY POINT
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# 7. EXPORT — Trade Log + Summary ตาม format อาจารย์
# ──────────────────────────────────────────────

def export_trade_log(all_results: list, output_dir: str = "output"):
    """Export Trade Log รายดีลตาม format อาจารย์"""
    import csv

    os.makedirs(output_dir, exist_ok=True)
    rows = []

    for result in all_results:
        if "trade_log" not in result:
            continue
        for t in result["trade_log"]:
            buy_price   = t["entry_price"]
            sell_price  = t["exit_price"]
            buy_amount  = INITIAL_CASH * 0.6
            buy_weight  = round(buy_amount / buy_price * GOLD_GRAM_PER_BAHT, 4)
            sell_amount = round(buy_weight / GOLD_GRAM_PER_BAHT * sell_price, 2)
            profit      = round(sell_amount - buy_amount, 2)
            days_held   = max(t.get("days_held", 1), 1)
            pct_deal    = round(profit / buy_amount * 100, 2)
            pct_year    = round(pct_deal * (365 / days_held), 2)
            cap_days    = round(buy_amount * days_held / 365, 2)

            rows.append({
                "Round":                   result["label"],
                "Buy_Price/Gold_Baht":     buy_price,
                "Buy Date":                t["entry_time"],
                "Buy Amount (THB)":        round(buy_amount, 2),
                "Buy Weight (g)":          buy_weight,
                "Sell_Price/Gold_Baht":    sell_price,
                "Sell Date":               t["exit_time"],
                "Sell Amount (THB)":       sell_amount,
                "Profit (THB)":            profit,
                "Days Held":               days_held,
                "%Profit/Deal":            f"{pct_deal:.2f}%",
                "%Profit/Year (Annual)":   f"{pct_year:.2f}%",
                "Capital x days/year":     cap_days,
            })

    if not rows:
        print("⚠️  ไม่มี Trade Log ให้ Export")
        return

    path = os.path.join(output_dir, "trade_log.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Export Trade Log: {path} ({len(rows)} trades)")


def export_summary(all_results: list, output_dir: str = "output"):
    """Export Summary Metrics ตาม format อาจารย์"""
    import csv

    os.makedirs(output_dir, exist_ok=True)
    rows = []

    for result in all_results:
        if "metrics" not in result:
            continue
        m = result["metrics"]
        rows.append({
            "Round":                        result["label"],
            "Season":                       result.get("season_note", ""),
            "Total Closed Trade":           m.get("Total Closed Trade", 0),
            "Win Rate (%)":                 m.get("Win Rate (%)", "N/A"),
            "Total Profit (THB)":           m.get("Total Profit (THB)", 0),
            "Unrealized P/L":               "-",
            "Average Win (THB)":            m.get("Average Win (THB)", 0),
            "Average Loss (THB)":           m.get("Average Loss (THB)", 0),
            "Expectancy per Trade (THB)":   m.get("Expectancy per Trade (THB)", 0),
            "Best Annualized Trade (%)":    m.get("Best Annualized Trade (%)", "N/A"),
            "Worst Annualized Trade (%)":   m.get("Worst Annualized Trade (%)", "N/A"),
            "Median Annualized Trade (%)":  m.get("Median Annualized Trade (%)", "N/A"),
            "Top 10% Annualized":           m.get("Top 10% Annualized", "N/A"),
            "Bottom 10% Annualized":        m.get("Bottom 10% Annualized", "N/A"),
            "XIRR":                         m.get("XIRR (approx)", "N/A"),
            "Avg Capital/Year (THB/Year)":  m.get("Annualized Return (%)", "N/A"),
            "Sharpe Ratio":                 m.get("Sharpe Ratio", "N/A"),
            "Max Drawdown (%)":             m.get("Max Drawdown (%)", "N/A"),
            "Calmar Ratio":                 m.get("Calmar Ratio", "N/A"),
        })

    if not rows:
        print("⚠️  ไม่มี Summary ให้ Export")
        return

    path = os.path.join(output_dir, "summary_metrics.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"✅ Export Summary Metrics: {path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Walk-Forward Backtest — Nakkhutthong")
    parser.add_argument("--csv",    default="../Src/backtest/data/MarketState_data/GLD965_5m_20250101_to_20260416.csv",
                        help="Path ไปยังไฟล์ CSV ราคาทอง")
    parser.add_argument("--output", default="output", help="โฟลเดอร์สำหรับบันทึกผล")
    parser.add_argument("--mode",   default="smart",
                        choices=["rule", "smart", "api"],
                        help="rule=Rule-based, smart=Rule+Mistral, api=Mistral ทุก candle")
    args = parser.parse_args()

    run_walk_forward(args.csv, args.output, args.mode)