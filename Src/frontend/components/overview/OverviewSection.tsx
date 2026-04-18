import React, { useState } from 'react';
import { OverviewHeader } from './OverviewHeader';
import { RecentlySignal } from './RecentlySignal';
import { GrossPnL } from './GrossPnL';
import { StatsStack } from './StatsStack';
import { SignalLogTable } from './SignalLogTable';

export const OverviewSection = () => {
  return (
    <section id="overview" className="w-full min-h-screen pb-12" style={{ background: '#FCFBF7' }}>
      
      {/* 1. Header Section */}
      <OverviewHeader />

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