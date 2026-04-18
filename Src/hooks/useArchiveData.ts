// src/hooks/useArchiveData.ts
import { useState, useEffect } from 'react';
import { ArchiveSummary, TradeRecord, SignalRecord, LogRecord } from '../types/archive';

export const useArchiveData = () => {
  const [summary, setSummary] = useState<ArchiveSummary | null>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [signals, setSignals] = useState<SignalRecord[]>([]);
  const [logs, setLogs] = useState<LogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchArchive = async () => {
      setIsLoading(true);
      
      // 1. Mock Summary
      const mockSummary: ArchiveSummary = {
        total_pnl_thb: 145200.50, win_rate: 0.84, total_trades: 142, growth_pct: 8.4, sync_status: "Verified & Locked"
      };

      // 2. Mock User Trades (trade_log)
      const mockTrades: TradeRecord[] = [
        { id: 452, run_id: 1201, action: 'SELL', price_thb: 41450, gold_grams: 0.50, pnl_thb: 3500, pnl_pct: 0.0085, executed_at: '2026-04-15 10:30', note: 'User executed manually', rationale: 'AI recommended SELL due to resistance breakout.', confidence: 0.88 },
        { id: 450, run_id: 1198, action: 'SELL', price_thb: 41400, gold_grams: 1.20, pnl_thb: -1000, pnl_pct: -0.0024, executed_at: '2026-04-14 15:20', note: 'User executed at Stop Loss', rationale: 'AI detected volatility spike.', confidence: 0.92 }
      ];

      // 3. Mock AI Signals (runs) - รวม HOLD ที่ไม่ได้เทรดด้วย
      const mockSignals: SignalRecord[] = [
        { id: 1201, run_at: '2026-04-15 10:25', signal: 'SELL', confidence: 0.88, entry_price: 41450, stop_loss: 41600, take_profit: 41000, rationale: 'Price broke above 41,000 resistance.', provider: 'OpenAI (GPT-4o)', trend: 'BEARISH' },
        { id: 1200, run_at: '2026-04-15 09:00', signal: 'HOLD', confidence: 0.65, entry_price: 41300, stop_loss: 41000, take_profit: 41500, rationale: 'Market is moving sideways. Await clearer trend.', provider: 'Anthropic (Claude)', trend: 'NEUTRAL' }
      ];

      // 4. Mock System Logs (llm_logs)
      const mockLogs: LogRecord[] = [
        { id: 5021, logged_at: '2026-04-15 10:25:01', step_type: 'THOUGHT_FINAL', provider: 'OpenAI (GPT-4o)', token_total: 1540, elapsed_ms: 2300, trace_preview: 'Concluded SELL signal based on MACD crossover.' },
        { id: 5020, logged_at: '2026-04-15 10:24:58', step_type: 'OBSERVATION', provider: 'System', token_total: 800, elapsed_ms: 150, trace_preview: 'Received spot price: 41450 THB. RSI: 72.5' }
      ];

      setTimeout(() => {
        setSummary(mockSummary); setTrades(mockTrades); setSignals(mockSignals); setLogs(mockLogs);
        setIsLoading(false);
      }, 800);
    };

    fetchArchive();
  }, []);

  return { summary, trades, signals, logs, isLoading };
};