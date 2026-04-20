/**
 * Deterministic fixtures — ใช้ทั้งใน MSW handlers และ tests โดยตรง
 * ห้ามมี random / Date.now() / side effect ใดๆ
 */

export const signalDetailFixture = {
  id: 597,
  logged_at: '2026-04-19T10:00:00Z',
  interval_tf: '5m',
  entry_price: 45000.0,
  stop_loss: 44500.0,
  take_profit: 45500.0,
  signal: 'BUY',
  confidence: 0.85,
  rationale: 'Bullish trend confirmed by RSI divergence',
  trace_json: JSON.stringify([
    {
      step: 'THOUGHT_1',
      iteration: 1,
      response: { thought: 'Checking macro trend', action: 'CALL_TOOL' },
    },
    {
      step: 'FINAL_DECISION',
      response: {
        action: 'FINAL_DECISION',
        signal: 'BUY',
        rationale: 'Bullish trend confirmed by RSI divergence',
      },
    },
  ]),
  token_total: 1234,
  elapsed_ms: 2500,
  iteration: 2,
  provider: 'Gemini 3 Flash',
};

export const portfolioFixture = {
  available_cash: 1500.0,
  unrealized_pnl: 250.5,
  pnl_percent: 2.5,
  trades_today: 3,
  total_equity: 10250.5,
};

export const latestSignalFixture = {
  id: 600,
  signal: 'BUY',
  confidence: 0.75,  // float [0,1] — UI จะ × 100
  rationale: 'MACD bullish cross',
  provider: 'AI AGENT',
};

// ตรงตาม interface BacktestSummary ใน Src/frontend/components/backtest/BacktestSection.tsx
export const backtestSummaryFixture = {
  model_name: 'gemini-3-flash',
  run_date: '2026-04-19',
  trade_net_pnl_thb: 5200.0,
  risk_total_return_pct: 5.2,
  trade_win_rate_pct: 55.0,
  trade_winning_trades: 27,
  trade_losing_trades: 23,
  risk_mdd_pct: 8.0,
  trade_profit_factor: 1.8,
  trade_expectancy_thb: 104.0,
  risk_sharpe_ratio: 1.42,
  risk_sortino_ratio: 1.8,
  risk_annualized_return_pct: 12.5,
  risk_initial_portfolio_thb: 100000.0,
  risk_final_portfolio_thb: 105200.0,
  trade_total_trades: 50,
  trade_gross_profit_thb: 10000.0,
  trade_gross_loss_thb: -4800.0,
  trade_calmar_ratio: 1.56,
  llm_directional_accuracy_pct: 62.0,
  final_directional_accuracy_pct: 58.0,
  session_compliance_compliance_pct: 95.0,
  risk_candles_total: 1500,
};

export const equityCurveFixture = [
  {
    date: '4/19 10:00',
    value: 10000,
    signal: 'HOLD',
    pnl: 0,
    price: 45000,
    raw_ts: '2026-04-19T10:00:00Z',
    profitable: false,
  },
  {
    date: '4/19 11:00',
    value: 10150,
    signal: 'BUY',
    pnl: 150,
    price: 45100,
    raw_ts: '2026-04-19T11:00:00Z',
    profitable: true,
  },
];

export const tradesFixture = [
  {
    timestamp: '19 Apr 10:00',
    signal: 'BUY',
    confidence: 0.85,
    pnl: 150.0,
    position_size: 1000.0,
    stop_loss: 44500.0,
    take_profit: 45500.0,
    rationale: 'Bullish momentum',
    llm_signal: 'BUY',
    llm_confidence: 0.9,
    correct: true,
    profitable: true,
    rejection_reason: '',
    portfolio_value: 10150.0,
    price: 45100.0,
  },
];
