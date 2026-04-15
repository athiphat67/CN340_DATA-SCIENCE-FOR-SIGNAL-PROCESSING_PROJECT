import React, { useState } from 'react';
import { OverviewHeader } from '../overview/OverviewHeader'; 
import { SignalsHeader } from './SignalsHeader';
import { SignalStatsCards } from './SignalStatsCards';
import { SignalAnalytics } from './SignalAnalytics'; // New!
import { SignalPerformanceChart } from './SignalPerformanceChart'; // New!
import { SignalFilterBar } from './SignalFilterBar';
import { SignalMasterTable } from './SignalMasterTable';

export const SignalsSection = () => {
  const [activeFilter, setActiveFilter] = useState('All');

  // ข้อมูลจำลองที่ระบุ status ชัดเจน (Active / Won / Lost)
  const mockSignals = [
    { id: 597, date: '15 Apr 2026', tf: '4H', signal: 'BUY', entry: 2450.5, tp: 2480.0, sl: 2435.0, rationale: 'Detected strong bullish MACD crossover on 4H.', status: 'Active' },
    { id: 598, date: '15 Apr 2026', tf: '1H', signal: 'SELL', entry: 2460.0, tp: 2445.0, sl: 2470.0, rationale: 'RSI overbought on 1H timeframe.', status: 'Active' },
    { id: 596, date: '14 Apr 2026', tf: '1H', signal: 'SELL', entry: 2465.2, tp: 2450.0, sl: 2475.0, rationale: 'Bearish engulfing candle confirmed.', status: 'Won' },
    { id: 595, date: '13 Apr 2026', tf: '4H', signal: 'HOLD', entry: 2440.0, tp: null, sl: null, rationale: 'Market consolidation. Waiting for breakout.', status: 'Closed' },
  ];

  return (
    <section className="w-full min-h-screen pb-12" style={{ background: '#FCFBF7' }}>
      <OverviewHeader /> 

      <div className="px-6 mt-8 relative z-20 max-w-7xl mx-auto">
        <SignalsHeader />
        
        {/* Row 1: Dashboard Stats */}
        <SignalStatsCards />
        
        {/* Row 2: Deep Analytics Insights */}
        <SignalAnalytics />

        {/* Row 3: Performance Growth Chart */}
        <SignalPerformanceChart />

        {/* Row 4: Master Signal Table with Live/History Tabs */}
        <div className="mt-12 mb-6">
            <h2 className="text-xl font-black text-gray-900 mb-2">Signals Master Log</h2>
            <p className="text-sm text-gray-400 font-medium">Full archive of agent signals with complete rationale tracing.</p>
        </div>
        <SignalFilterBar activeFilter={activeFilter} setActiveFilter={setActiveFilter} />
        <SignalMasterTable signals={mockSignals} />
      </div>
    </section>
  );
};