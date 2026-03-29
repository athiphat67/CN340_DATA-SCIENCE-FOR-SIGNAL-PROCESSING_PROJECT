# Thai Gold Backtest Implementation Summary

## ✅ สิ่งที่สร้างเสร็จแล้ว (MVP - Signal Only)

### 📦 ไฟล์ที่ได้
1. **backtest_signal_only.py** (600+ lines)
   - Core engine สำหรับ signal accuracy backtest
   - Load 1-minute CSV data
   - Aggregate to 1H / 4H candles
   - Generate signals (5 providers: Gemini, Groq, Buy&Hold, Random, MA Crossover)
   - Validate signals vs actual next candle direction
   - Calculate metrics (Directional Accuracy, Signal Sensitivity, Net P&L)
   - Export results to CSV

2. **run_backtest_signal.py** (100+ lines)
   - CLI wrapper สำหรับ easy execution
   - Support command-line arguments
   - Pretty formatted output

3. **BACKTEST_README.md**
   - Documentation ฉบับสมบูรณ์
   - ตัวอย่างการใช้งาน
   - คำอธิบายเมตริกส์
   - Troubleshooting guide

---

## 🎯 Key Features Implemented

### ✅ Metrics Implemented
```
1. Directional Accuracy (%)
   Formula: (Correct Signals / Total Active Signals) × 100
   วัดว่า signal ทายทิศทางได้ถูกกี่เปอร์เซ็นต์
   
2. Signal Sensitivity (%)
   Formula: (BUY+SELL signals / Total Candles) × 100
   วัดว่า model "ขยัน" ออกคำสั่งเท่าไร (ป้องกัน HOLD ตลอด)
   
3. Net Profit/Loss (THB)
   Formula: Price Change - Spread (30 THB) - Commission (3 THB)
   วัดกำไร/ขาดทุนจริงหลังค่าใช้จ่าย
   
4. Additional Metrics
   - total_signals: จำนวน active signals (BUY+SELL)
   - correct_signals: Signals ที่ทายทิศทางถูก
   - correct_profitable: Signals ที่ทายถูก AND กำไร > 0
   - avg_confidence: ค่าความมั่นใจเฉลี่ย
   - avg_net_pnl_thb: กำไรเฉลี่ยเมื่อ signal ถูก
```

### ✅ Cost Handling
```
✓ Spread (30 THB) - รวมใน net_profit_loss
✓ Commission (3 THB) - รวมใน net_profit_loss
✓ Total Cost per Signal = 33 THB

Example:
  Price moves up by 50 THB
  Net after costs = 50 - 33 = 17 THB ✓ PROFITABLE
  
  Price moves up by 20 THB
  Net after costs = 20 - 33 = -13 THB ✗ LOSS
```

### ✅ Timeframe Support
- 1H (1 hour)
- 4H (4 hour)
- User selectable via command-line

### ✅ Time Horizon Support
- 15 days
- 30 days (default)
- 90 days

### ✅ Provider Comparison
Mock signals for:
1. **Gemini** - Smart AI with trend + RSI analysis
2. **Groq** - Conservative, higher thresholds
3. **Buy&Hold** - Baseline (BUY once, HOLD)
4. **Random** - Baseline (random BUY/SELL/HOLD)
5. **MA Crossover** - Technical baseline (EMA 20/50)

---

## 📊 Output Format

CSV file with **2 sections**:

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
timestamp,close_thai,actual_direction,price_change,net_profit_loss,
gemini_signal,gemini_confidence,gemini_correct,gemini_profitable,...
2026-02-26 08:00:00,66575.96,UP,20.55,-12.45,HOLD,0.500,False,False,...
2026-02-26 09:00:00,66605.97,UP,30.18,-2.82,BUY,0.680,True,False,...
...
```

---

## 🚀 How to Use

### Quick Start (Sample Data)
```bash
cd /home/claude

# Test with 1H timeframe
python run_backtest_signal.py \
  --csv Src/backtest/data_XAU_THB/sample_thai_gold_1m_dataset.csv \
  --timeframe 1h \
  --days 15
```

### With Your Real Data (Once uploaded)
```bash
python run_backtest_signal.py \
  --csv Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv \
  --timeframe 1h \
  --days 30
```

### Advanced Examples
```bash
# 4H timeframe, 90 days, Gemini vs Groq only
python run_backtest_signal.py \
  --timeframe 4h \
  --days 90 \
  --providers gemini,groq

# Custom output
python run_backtest_signal.py \
  --timeframe 1h \
  --days 30 \
  --filename my_results.csv \
  --output-dir my_backtest/
```

---

## 📋 CLI Arguments Reference

| Argument | Default | Choices | Example |
|----------|---------|---------|---------|
| `--csv` | Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv | path | `--csv data.csv` |
| `--timeframe` | 1h | 1h, 4h | `--timeframe 4h` |
| `--days` | 30 | 15, 30, 90 | `--days 90` |
| `--providers` | all 5 | comma-sep list | `--providers gemini,groq` |
| `--output-dir` | backtest_results | path | `--output-dir results/` |
| `--filename` | auto-generated | string | `--filename test.csv` |

---

## 🎬 Test Results (Sample Data)

```
TIMEFRAME: 1h
DAYS: 15 days
DATA: 8 candles

RESULTS:
┌─────────────┬──────────────┬───────────────┬───────────────┐
│ Provider    │ Accuracy (%) │ Sensitivity   │ Avg Net P&L   │
├─────────────┼──────────────┼───────────────┼───────────────┤
│ Buy&Hold    │ 100.0        │ 12.5%         │ +375.99 THB ✓ │
│ Random      │ 0.0          │ 50.0%         │ 0.0 THB       │
│ MA Crossover│ 12.5         │ 100.0%        │ -19.91 THB    │
│ Gemini      │ 0.0          │ 0.0%          │ (all HOLD)    │
│ Groq        │ 0.0          │ 0.0%          │ (all HOLD)    │
└─────────────┴──────────────┴───────────────┴───────────────┘

KEY INSIGHTS:
- Buy&Hold won (100% accuracy + biggest profit)
- MA Crossover overtraded (100% sensitivity, low accuracy)
- Random underperformed (0% accuracy on active signals)
- Gemini/Groq stayed HOLD (conservative, no active signals)
```

---

## 🔧 Technical Details

### Data Flow
```
CSV (1-minute) 
  ↓ [Load]
Raw Data (86 rows)
  ↓ [Aggregate 1H]
Hourly Candles (8 candles)
  ↓ [Generate Signals]
5 provider signals per candle
  ↓ [Validate]
Next candle direction checked
  ↓ [Calculate Metrics]
Accuracy, Sensitivity, Net P&L
  ↓ [Export CSV]
Summary + Detailed Log
```

### Signal Generation (Mock)
```python
# Gemini: Aggressive, uses RSI + EMA
if RSI > 70 and EMA20 > EMA50: SELL
elif RSI < 30 and EMA20 < EMA50: BUY
else: varies based on EMA ratio

# Groq: Conservative, high thresholds
if RSI > 75 and EMA20 > EMA50: SELL (strict)
elif RSI < 25 and EMA20 < EMA50: BUY (strict)
else: HOLD

# Buy&Hold: BUY at first, then HOLD forever
first candle: BUY
rest: HOLD

# Random: Coin flip
33% BUY, 33% SELL, 33% HOLD (each candle)

# MA Crossover: EMA 20 vs 50
if EMA20 > EMA50: BUY
else: SELL
```

---

## 📈 Next Steps (Phase 2 - Optional)

Once you validate signal accuracy, you can:

1. **Add Portfolio Simulation** (Full Virtual Trading)
   - Track actual PnL, Win Rate, Max Drawdown, Sharpe Ratio
   - See realistic P&L after virtual trades

2. **Integrate Real LLM APIs**
   - Replace mock signals with actual Gemini/Groq API calls
   - No more hardcoded mock logic

3. **Parameter Optimization**
   - Test different RSI periods, EMA lengths
   - Find best indicator combinations

4. **Risk Analysis**
   - Position sizing strategies
   - Stop loss / Take profit levels

---

## ⚠️ Important Notes

### Cost Impact
The 33 THB total cost (spread 30 + commission 3) is **critical**:
- Small price moves (<50 THB) usually lose money after costs
- Only moves >50 THB are profitable on first trade
- This matches real ออม NOW trading conditions

### Signal Accuracy vs Profitability
```
Possible to have:
✓ High Directional Accuracy BUT Low Profitability
  (because price moves too small to overcome 33 THB costs)

✓ Low Directional Accuracy BUT High Profitability
  (by chance, lucky on big moves)
```

### CSV Requirements
Your real CSV must have columns:
```
timestamp, gold_spot_usd, usd_thb_rate, open_thai, high_thai, low_thai, close_thai
```

Must be sorted by timestamp (oldest first)

---

## 🐛 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `FileNotFoundError` | Provide correct CSV path |
| `No active signals (all HOLD)` | Normal if data range too small |
| `correct_profitable = 0` but accuracy high | Price moves too small to overcome costs |
| `ResampleError: Invalid frequency` | Already fixed (using lowercase 'h') |

---

## 📞 Quick Reference

### Run Tests
```bash
# 1H, 30 days, all providers
python run_backtest_signal.py

# 4H, 90 days, Gemini vs Groq
python run_backtest_signal.py --timeframe 4h --days 90 --providers gemini,groq
```

### Check Results
```bash
ls -lh backtest_results/  # View output files
head -50 backtest_results/*.csv  # Preview results
```

### Integrate into GoldTrader
```python
from backtest_signal_only import SignalOnlyBacktest

backtest = SignalOnlyBacktest(
    csv_path='Src/backtest/data_XAU_THB/thai_gold_1m_dataset.csv'
)
backtest.load_csv()
backtest.aggregate_candles(timeframe='1h', days=30)
backtest.generate_signals(providers=['gemini', 'groq'])
backtest.validate_signals()
metrics = backtest.calculate_metrics()
backtest.export_csv()
```

---

## 📊 Files Summary

| File | Purpose | Lines | Status |
|------|---------|-------|--------|
| backtest_signal_only.py | Core engine | 600+ | ✅ Complete |
| run_backtest_signal.py | CLI wrapper | 100+ | ✅ Complete |
| BACKTEST_README.md | Documentation | 500+ | ✅ Complete |
| sample_thai_gold_1m_dataset.csv | Test data | 86 rows | ✅ Ready |

---

## 🎓 Learning Path

1. **Understand the code**
   - Read backtest_signal_only.py comments
   - Study the metrics calculations

2. **Test with sample data**
   - Run with sample CSV
   - Check output CSV structure

3. **Test with your real data** (when ready)
   - Upload thai_gold_1m_dataset.csv
   - Run full backtest

4. **Integrate with GoldTrader** (optional)
   - Replace mock signals with real LLM calls
   - Add portfolio simulation

---

## 🚀 Status

```
MVP (Signal Only): ✅ COMPLETE & TESTED
├─ Load CSV: ✅
├─ Aggregate 1H/4H: ✅
├─ Generate signals: ✅
├─ Validate signals: ✅
├─ Calculate metrics: ✅
├─ Cost handling: ✅
└─ Export CSV: ✅

Next Phase (Optional):
├─ Portfolio simulation: ⏳ Not started
├─ Real LLM integration: ⏳ Not started
├─ Parameter optimization: ⏳ Not started
└─ Risk analysis: ⏳ Not started
```

---

**Created:** 2026-03-28  
**Version:** 1.0 (MVP)  
**Status:** ✅ Ready for testing
