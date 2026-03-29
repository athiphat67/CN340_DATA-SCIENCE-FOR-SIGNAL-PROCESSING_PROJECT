# Thai Gold Backtest - Signal Accuracy Only (MVP)

## Overview

Fast MVP (Minimum Viable Product) backtest engine for Thai Gold (ออม NOW) trading signals without portfolio simulation. Focuses on **signal accuracy and sensitivity**.

**Key Features:**
- ✅ Load 1-minute Thai gold data (OHLCV)
- ✅ Aggregate to 1H or 4H candles  
- ✅ Generate signals from 5 providers (Gemini, Groq, Buy&Hold, Random, MA Crossover)
- ✅ Validate signals against next candle direction
- ✅ Include realistic costs: Spread (30 THB) + Commission (3 THB per trade)
- ✅ Export results to CSV (Summary + Detailed Signal Log)

---

## Metrics Calculated

### 1. **Directional Accuracy** (%)
```
Formula: (Correct Signals / Total Active Signals) × 100

Example:
  Total signals: 50
  Correct (matched direction): 34
  Directional Accuracy = (34 / 50) × 100 = 68%
```

**What it means:** How often the signal guessed the right direction (up/down)

### 2. **Signal Sensitivity** (%)
```
Formula: (BUY + SELL signals / Total Candles) × 100

Example:
  Total candles: 100
  Active signals (BUY+SELL): 45
  Signal Sensitivity = (45 / 100) × 100 = 45%
```

**What it means:** How "aggressive" the model is (higher % = more trading, not always better)

### 3. **Net Profit/Loss** (THB)
```
Formula: Price Change - Spread (30 THB) - Commission (3 THB)
       = Price Change - 33 THB

Example:
  Next candle close: 66500
  Current candle close: 66450
  Price change: +50 THB
  Net P&L = 50 - 33 = +17 THB ✓ PROFITABLE
  
  OR
  Price change: +20 THB
  Net P&L = 20 - 33 = -13 THB ✗ LOSS (too small move)
```

**What it means:** Real profit/loss after costs

### 4. **Additional Metrics**
- `total_signals`: Count of active (non-HOLD) signals
- `correct_signals`: Count of signals that matched direction
- `correct_profitable`: Signals that were both correct AND profitable after costs
- `avg_confidence`: Average confidence score (0.0-1.0)
- `avg_net_pnl_thb`: Average P&L when signal was correct

---

## Directory Structure

```
/home/claude/
├── backtest_signal_only.py           # Core engine (main logic)
├── run_backtest_signal.py             # CLI entry point
│
├── Src/backtest/
│   └── data_XAU_THB/
│       ├── thai_gold_1m_dataset.csv   # Your real data (you need to provide)
│       └── sample_thai_gold_1m_dataset.csv  # Sample for testing
│
└── backtest_results/                  # Output directory (auto-created)
    ├── backtest_signal_only_1h_20260328_xxxxxx.csv
    └── backtest_signal_only_4h_20260328_xxxxxx.csv
```

---

## Usage

### Quick Start (Using Sample Data)
```bash
# Test with 1H timeframe, 1 day, all providers
python run_backtest_signal.py \
  --csv Src/backtest/data_XAU_THB/sample_thai_gold_1m_dataset.csv \
  --timeframe 1h \
  --days 15 \
  --providers gemini,groq,buy_hold,random,ma_crossover
```

### With Real Data (Once You Upload CSV)
```bash
# Test with actual data
python run_backtest_signal.py \
  --csv Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv \
  --timeframe 1h \
  --days 30
```

### Advanced Options

```bash
# 4H timeframe, last 90 days, Gemini vs Groq only
python run_backtest_signal.py \
  --timeframe 4h \
  --days 90 \
  --providers gemini,groq

# Custom output filename
python run_backtest_signal.py \
  --timeframe 1h \
  --days 30 \
  --filename my_backtest_results.csv \
  --output-dir my_results/
```

### CLI Arguments

| Argument | Default | Options | Description |
|----------|---------|---------|-------------|
| `--csv` | Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv | path | Path to CSV file |
| `--timeframe` | 1h | 1h, 4h | Aggregation timeframe |
| `--days` | 30 | 15, 30, 90 | Lookback period |
| `--providers` | all | gemini, groq, buy_hold, random, ma_crossover | Comma-separated providers |
| `--output-dir` | backtest_results | path | Output directory |
| `--filename` | auto-generated | string | Custom output filename |

---

## Output CSV Format

The output CSV has **two sections**:

### Section 1: Summary Metrics
```
metric,gemini,groq,buy_hold,random,ma_crossover
directional_accuracy_pct,68.5,54.2,N/A,48.0,62.1
signal_sensitivity_pct,45.2,38.5,2.0,50.0,48.0
total_signals,52,52,2,52,52
correct_signals,35,28,2,25,32
correct_profitable,28,18,1,15,26
avg_confidence,0.618,0.512,1.000,0.500,0.680
avg_net_pnl_thb,42.15,18.32,150.00,5.23,38.75
```

### Section 2: Detailed Signal Log
```
timestamp,close_thai,actual_direction,price_change,net_profit_loss,gemini_signal,gemini_confidence,gemini_correct,gemini_profitable,...
2026-02-26 08:00:00,66575.96,UP,20.55,-12.45,HOLD,0.500,False,False,...
2026-02-26 09:00:00,66605.97,UP,30.18,-2.82,BUY,0.680,True,False,...
2026-02-26 10:00:00,66585.80,DOWN,-20.17,-53.17,SELL,0.720,True,True,...
...
```

---

## Understanding the Metrics

### Example Interpretation

```
Provider: Gemini
├─ Directional Accuracy: 68.5%
│  └─ Guessed right direction 68.5% of the time ✓ Good
│
├─ Signal Sensitivity: 45.2%
│  └─ Trades 45% of available candles (active, not lazy) ✓ Good
│
├─ Total Signals: 52
│  └─ Made 52 trading signals in the period
│
├─ Correct Signals: 35
│  └─ 35 out of 52 were directionally correct (68.5%)
│
├─ Correct Profitable: 28
│  └─ Only 28 correct signals actually made profit (after costs!)
│     Why? Because some price moves were too small to cover spread + commission
│
├─ Avg Net P&L: 42.15 THB
│  └─ On average, when Gemini was correct, profit was +42.15 THB
│
└─ Avg Confidence: 0.618
   └─ Gemini was fairly confident (scale: 0-1)
```

### Comparing Providers

```
Directional Accuracy (Higher is Better):
  Gemini:      68.5% ← Best at picking direction
  MA Crossover: 62.1%
  Groq:        54.2%
  Random:      48.0%

Signal Sensitivity (Moderate is Better):
  Random:       50.0% ← Most active (but worst accuracy!)
  Gemini:       45.2% ← Good balance
  MA Crossover: 48.0%
  Groq:         38.5% ← Too conservative (fewer signals)

Correct Profitable (More is Better):
  Gemini:        28 ✓ Most signals actually made money
  MA Crossover:  26
  Groq:          18
  Buy&Hold:       1 ← Only 1 profitable trade

Recommendation: Gemini wins overall (best accuracy + profitable)
```

---

## Cost Impact Analysis

The costs matter! Here's why:

```
Scenario: Price moves up by 20 THB

Without costs:
  Entry: 66500
  Exit: 66520
  Profit: 20 THB ✓ Win

With realistic costs (Spread 30 THB + Commission 3 THB = 33 THB):
  Entry: 66500 + 30 (spread) = 66530
  Exit: 66520 - 30 (spread) = 66490
  Net: 66490 - 66530 = -40 THB ✗ LOSS!

That's why avg_net_pnl_thb is often lower than you'd expect!
This is the "real world" view.
```

---

## Next Steps (Phase 2)

Once you have these signal accuracy results, you can:

1. **Add Portfolio Simulation** (Full Virtual Trading)
   - Track actual PnL, Win Rate, Sharpe Ratio
   - See how much you'd make/lose

2. **Integrate with Actual LLM Providers**
   - Replace mock signals with real API calls (Gemini, Groq)
   - Remove artificial trading constraints

3. **Optimize Parameters**
   - Test different technical indicators
   - Tune EMA periods, RSI thresholds

4. **Compare with Real Trading**
   - A/B test signals against actual ออม NOW trading

---

## Tips for Interpreting Results

✅ **Good Signal** = Directional Accuracy > 60% + Profitable
❌ **Bad Signal** = Accuracy < 55% or mostly unprofitable
⚠️ **Lazy Signal** = Sensitivity < 20% (all HOLD)
⚠️ **Overactive Signal** = Sensitivity > 60% + Low accuracy

---

## Troubleshooting

### Error: "File not found: Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv"

**Solution:** You need to upload your real CSV file or use the sample:
```bash
python run_backtest_signal.py \
  --csv Src/backtest/data_XAU_THB/sample_thai_gold_1m_dataset.csv
```

### Error: "No active signals (all HOLD)"

**Reason:** A provider generated only HOLD signals  
**Solution:** Check the signal generation logic (e.g., RSI/EMA thresholds)

### Result shows "correct_profitable = 0" even if "directional_accuracy = 80%"

**Reason:** Price movements were too small to overcome 33 THB costs  
**Solution:** This is realistic! Very tight price moves lose money after costs.

---

## Files in This Module

1. **backtest_signal_only.py** (600+ lines)
   - `SignalOnlyBacktest` class with full pipeline
   - Load CSV → Aggregate → Generate Signals → Validate → Calculate Metrics
   - Mock signal generators (Gemini, Groq, MA Crossover, Random, Buy&Hold)

2. **run_backtest_signal.py** (100+ lines)
   - CLI wrapper with argparse
   - Pretty formatted output and error handling
   - Easy to run from command line

3. **README.md** (this file)
   - Documentation and usage guide

---

## Contact / Support

For issues or questions:
- Check the example CSV format in `Src/backtest/data_XAU_THB/sample_thai_gold_1m_dataset.csv`
- Verify CSV columns: `timestamp, gold_spot_usd, usd_thb_rate, open_thai, high_thai, low_thai, close_thai`
- Ensure CSV is sorted by timestamp (oldest first)

---

**Version:** 1.0 (MVP - Signal Accuracy Only)  
**Last Updated:** 2026-03-28  
**Status:** ✅ Ready for testing
