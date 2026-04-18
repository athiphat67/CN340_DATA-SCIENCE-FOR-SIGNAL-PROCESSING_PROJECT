import { useState, useEffect } from 'react';
import { ArchiveSummary, TradeRecord } from '../types/history';

export const useTradeHistory = () => {
  const [summary, setSummary] = useState<ArchiveSummary | null>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // 💡 อนาคตเปลี่ยนตรงนี้เป็นการ fetch('/api/history')
    const fetchHistory = async () => {
      setIsLoading(true);
      
      // Mockup Data (Aggregated)
      const mockSummary: ArchiveSummary = {
        total_pnl_thb: 145200.50,
        win_rate: 0.84, // 84% Signal Accuracy
        total_trades: 142,
        growth_pct: 8.4,
        sync_status: "Verified & Locked"
      };

      // Mockup Data (Joined: trade_log + runs)
      const mockTrades: TradeRecord[] = [
        { 
          id: 452, run_id: 1201, action: 'SELL', price_thb: 41450.00, gold_grams: 0.50, pnl_thb: 3500.00, pnl_pct: 0.0085, executed_at: '2026-04-15 10:30', note: 'User executed at Target Hit',
          rationale: 'Signal generated: Price broke above 41,000 resistance with high volume confirmation.', confidence: 0.88, provider: 'OpenAI (GPT-4o)', iterations_used: 3, tool_calls_used: 5,
          rsi: 72.5, macd_line: 12.5, trend: 'BULLISH', gold_usd: 2380.50, gold_thb: 41400.00, is_weekend: false, data_quality: 'Good'
        },
        { 
          id: 450, run_id: 1198, action: 'SELL', price_thb: 41400.00, gold_grams: 1.20, pnl_thb: -1000.00, pnl_pct: -0.0024, executed_at: '2026-04-14 15:20', note: 'User executed to Stop Loss',
          rationale: 'Signal generated: Unexpected volatility spike detected. Recommendation to limit exposure.', confidence: 0.92, provider: 'Anthropic (Claude 3.5)', iterations_used: 2, tool_calls_used: 3,
          rsi: 45.2, macd_line: -5.2, trend: 'BEARISH', gold_usd: 2365.10, gold_thb: 41500.00, is_weekend: false, data_quality: 'Good'
        },
        { 
          id: 449, run_id: null, action: 'BUY', price_thb: 41500.00, gold_grams: 2.00, pnl_thb: null, pnl_pct: null, executed_at: '2026-04-13 09:00', note: 'Independent Manual Buy',
          rationale: 'No AI signal. User independently executed buy order.', confidence: 1.0, provider: 'Manual Action', iterations_used: 0, tool_calls_used: 0,
          rsi: 50.0, macd_line: 0.0, trend: 'NEUTRAL', gold_usd: 2370.00, gold_thb: 41500.00, is_weekend: false, data_quality: 'Unknown'
        }
      ];

      // Simulate network delay
      setTimeout(() => {
        setSummary(mockSummary);
        setTrades(mockTrades);
        setIsLoading(false);
      }, 800);
    };

    fetchHistory();
  }, []);

  return { summary, trades, isLoading };
};