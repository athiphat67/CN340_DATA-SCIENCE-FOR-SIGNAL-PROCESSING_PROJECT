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

  // 🔄 ปรับข้อมูลให้ตรงกับ SignalPerformanceChart (ความถี่สูงขึ้นและ ID ตรงกัน)
  const mockSignals = [
    { 
      id: 598, 
      date: 'Today 10:45', 
      tf: '1H', 
      signal: 'HOLD', 
      entry: 41650.0, 
      tp: null, 
      sl: null, 
      rationale: 'Market momentum slowing down. AI maintaining current position.',
      confidence: 55
    },
    { 
      id: 597, 
      date: 'Today 09:15', 
      tf: '1H', 
      signal: 'BUY', 
      entry: 41200.0, 
      tp: 41500.0, 
      sl: 40800.0, 
      rationale: 'Strong breakout above 41,000 resistance confirmed by volume.',
      confidence: 88
    },
    { 
      id: 596, 
      date: '16 Apr 14:00', 
      tf: '4H', 
      signal: 'SELL', 
      entry: 41550.0, 
      tp: 41100.0, 
      sl: 41750.0, 
      rationale: 'Double top pattern detected on 4H. Exit to secure profit.',
      confidence: 92
    },
    { 
      id: 595, 
      date: '16 Apr 11:20', 
      tf: '1H', 
      signal: 'SELL', 
      entry: 41600.0, 
      tp: 41200.0, 
      sl: 41800.0, 
      rationale: 'RSI divergence spotted. Short-term bearish reversal likely.',
      confidence: 75
    },
    { 
      id: 594, 
      date: '16 Apr 08:00', 
      tf: '4H', 
      signal: 'HOLD', 
      entry: 41400.0, 
      tp: null, 
      sl: null, 
      rationale: 'Asian market opening with low volatility. No clear entry signal.',
      confidence: 60
    },
  ];

  // กรองข้อมูลตาม Filter Bar
  const filteredSignals = activeFilter === 'All' 
    ? mockSignals 
    : mockSignals.filter(s => s.signal === activeFilter);

  return (
    <section className="w-full min-h-screen pb-12" style={{ background: '#FCFBF7' }}>
      <OverviewHeader /> 

      <div className="px-6 mt-8 relative z-20 max-w-7xl mx-auto">
        <SignalsHeader />
        <SignalStatsCards />
        <SignalAnalytics />
        
        {/* กราฟนี้จะโชว์จุดข้อมูลที่ตรงกับ ID ในตารางด้านล่าง */}
        <SignalPerformanceChart />

        <div className="mt-12 mb-6">
            <h2 className="text-xl font-black text-gray-900 mb-2">Signals Master Log</h2>
            <p className="text-sm text-gray-400 font-medium">Full archive of agent signals with complete rationale tracing.</p>
        </div>
        
        <SignalFilterBar activeFilter={activeFilter} setActiveFilter={setActiveFilter} />
        
        {/* ส่งข้อมูลที่ผ่านการกรองเข้าตาราง */}
        <SignalMasterTable signals={filteredSignals} />
      </div>
    </section>
  );
};