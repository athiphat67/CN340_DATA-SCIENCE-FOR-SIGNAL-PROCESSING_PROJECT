import React, { useState } from 'react';
import { OverviewHeader } from './OverviewHeader';
import { RecentlySignal } from './RecentlySignal'; // สร้างเพิ่มภายหลัง
import { GrossPnL } from './GrossPnL';             // สร้างเพิ่มภายหลัง
import { StatsStack } from './StatsStack';           // รวม Signals Today, Win Rate, Portfolio
import { SignalLogTable } from './SignalLogTable';   // ตารางด้านล่าง

export const OverviewSection = () => {
  const [activeTab, setActiveTab] = useState('Overview');
  const tabs = ['Overview', 'Signals', 'Portfolio', 'History', 'Reports', 'Settings'] as const;

  return (
    <section id="overview" className="w-full min-h-screen pb-12" style={{ background: '#FCFBF7' }}>
      {/* 1. Header Section */}
      <OverviewHeader 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        tabs={tabs} 
      />

      {/* 2. Main Content Grid */}
      <div className="px-6 mt-8 relative z-20 grid grid-cols-12 gap-4">
        
        {/* Col 1-5: RecentlySignal */}
        <div className="col-span-12 lg:col-span-5">
          <RecentlySignal />
        </div>

        {/* Col 6-9: P&L */}
        <div className="col-span-12 lg:col-span-4">
          <GrossPnL />
        </div>

        {/* Col 10-12: Stats Stack */}
        <div className="col-span-12 lg:col-span-3">
          <StatsStack />
        </div>

        {/* Full Width: Table */}
        <div className="col-span-12">
          <SignalLogTable />
        </div>
      </div>
    </section>
  );
};