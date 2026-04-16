import React, { useState } from 'react';
import { OverviewHeader } from '../overview/OverviewHeader'; 
import { SignalsHeader } from './SignalsHeader';
import { SignalStatsCards } from './SignalStatsCards';
import { SignalAnalytics } from './SignalAnalytics'; 
import { SignalPerformanceChart } from './SignalPerformanceChart'; 
import { SignalFilterBar } from './SignalFilterBar';
import { SignalMasterTable } from './SignalMasterTable';

export const SignalsSection = () => {
  const [activeFilter, setActiveFilter] = useState('All');

  // ข้อมูลจำลองนี้อิงจาก get_recent_runs() ใน database.py 100%
  const mockSignals = [
    { 
      id: 597, 
      date: '15 Apr 2026', 
      tf: '4H', 
      signal: 'BUY', 
      entry: 41200.0, 
      tp: 41500.0, 
      sl: 40800.0, 
      rationale: 'Detected strong bullish MACD crossover on 4H.',
      confidence: 88
    },
    { 
      id: 598, 
      date: '15 Apr 2026', 
      tf: '1H', 
      signal: 'SELL', 
      entry: 41600.0, 
      tp: 41200.0, 
      sl: 41800.0, 
      rationale: 'RSI overbought on 1H timeframe. Trend reversal expected.',
      confidence: 75
    },
    { 
      id: 596, 
      date: '14 Apr 2026', 
      tf: '1H', 
      signal: 'SELL', 
      entry: 41550.0, 
      tp: 41100.0, 
      sl: 41750.0, 
      rationale: 'Bearish engulfing candle confirmed near resistance.',
      confidence: 92
    },
    { 
      id: 595, 
      date: '13 Apr 2026', 
      tf: '4H', 
      signal: 'HOLD', 
      entry: 41400.0, 
      tp: null, 
      sl: null, 
      rationale: 'Market consolidation. Waiting for breakout before action.',
      confidence: 60
    },
  ];

  return (
    <section className="w-full min-h-screen pb-12" style={{ background: '#FCFBF7' }}>
      <OverviewHeader /> 

      <div className="px-6 mt-8 relative z-20 max-w-7xl mx-auto">
        <SignalsHeader />
        <SignalStatsCards />
        <SignalAnalytics />
        <SignalPerformanceChart />

        <div className="mt-12 mb-6">
            <h2 className="text-xl font-black text-gray-900 mb-2">Signals Master Log</h2>
            <p className="text-sm text-gray-400 font-medium">Full archive of agent signals with complete rationale tracing.</p>
        </div>
        <SignalFilterBar activeFilter={activeFilter} setActiveFilter={setActiveFilter} />
        
        {/* ส่งข้อมูลที่ตรงสเปคเข้าตาราง */}
        <SignalMasterTable signals={mockSignals} />
      </div>
    </section>
  );
};