import React from 'react';
import { OverviewHeader } from '../overview/OverviewHeader';
import { PortfolioHeader } from './PortfolioHeader';

// Components
import { PortfolioAllocation } from './PortfolioAllocation';
import { PortfolioMargin } from './PortfolioMargin';
import { PortfolioMarketBias } from './PortfolioMarketBias';
import { PortfolioActivePositions } from './PortfolioActivePositions';

// Icons
import { Wallet, DollarSign, Activity, Percent } from 'lucide-react';

export const PortfolioSection = () => {
  return (
    <section className="w-full min-h-screen pb-12" style={{ background: '#FCFBF7' }}>
      <OverviewHeader />

      <div className="px-6 mt-8 relative z-20 max-w-7xl mx-auto">
        <PortfolioHeader />

        {/* 🚀 BENTO BOX GRID SYSTEM 🚀 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">

          {/* ======================================================== */}
          {/* LEFT COLUMN (8/12) - PERFORMANCE & POSITIONS */}
          {/* ======================================================== */}
          <div className="lg:col-span-8 flex flex-col gap-6">

            {/* 1. PROFIT MATRIX DASHBOARD (NEW DESIGN) */}
            <div className="relative bg-gradient-to-br from-[#1a0a24]/95 to-[#0F0A1A]/95 backdrop-blur-xl rounded-[32px] border border-white/10 shadow-[0_20px_50px_rgba(26,10,36,0.3)] overflow-hidden p-8 flex flex-col h-[320px] justify-between group">
              {/* Background Decorative Elements */}
              <div className="absolute top-0 right-0 w-96 h-96 bg-[#824199]/15 rounded-full blur-[120px] -z-10" />
              <div className="absolute bottom-0 left-0 w-48 h-48 bg-emerald-500/5 rounded-full blur-[80px] -z-10" />
              {/* Header Section */}
              <div className="relative z-10 flex justify-between items-start">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    <p className="text-[10px] font-bold text-white/40 uppercase tracking-[0.2em]">Net Equity Value</p>
                  </div>
                  <div className="flex items-baseline gap-2">
                    <p className="text-6xl font-black text-white tracking-tighter drop-shadow-[0_0_15px_rgba(255,255,255,0.2)]">1,245,200</p>
                    <span className="text-2xl font-bold text-yellow-400">฿</span>
                  </div>
                </div>
                <div className="bg-white/5 backdrop-blur-md border border-white/10 p-4 rounded-2xl flex flex-col items-end">
                  <p className="text-[9px] font-bold text-white/40 uppercase mb-1">Success Rate</p>
                  <p className="text-xl font-black text-emerald-400">92.4%</p>
                </div>
              </div>

              {/* Center Matrix Stats */}
              <div className="relative z-10 grid grid-cols-3 gap-8 border-y border-white/5 py-6">
                <div>
                  <p className="text-[9px] font-bold text-white/30 uppercase mb-1 tracking-widest">Monthly Profit</p>
                  <p className="text-lg font-black text-white">+45,200 <span className="text-xs text-white/40 font-bold">฿</span></p>
                </div>
                <div>
                  <p className="text-[9px] font-bold text-white/30 uppercase mb-1 tracking-widest">Avg. RR Ratio</p>
                  <p className="text-lg font-black text-white">1:2.4</p>
                </div>
                <div>
                  <p className="text-[9px] font-bold text-white/30 uppercase mb-1 tracking-widest">Total Trades</p>
                  <p className="text-lg font-black text-white">142 <span className="text-xs text-white/40 font-bold">Orders</span></p>
                </div>
              </div>

              {/* Footer Info */}
              <div className="relative z-10 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex flex-col">
                    <p className="text-[9px] font-bold text-emerald-400 uppercase tracking-tighter">Growth Rate</p>
                    <p className="text-2xl font-black text-emerald-400 drop-shadow-[0_0_10px_rgba(52,211,153,0.3)]">+12.4%</p>
                  </div>
                  <div className="h-8 w-[1px] bg-white/10 mx-2" />
                  <div className="flex flex-col">
                    <p className="text-[9px] font-bold text-white/30 uppercase tracking-tighter">Drawdown</p>
                    <p className="text-lg font-black text-rose-500">-2.1%</p>
                  </div>
                </div>
                <div className="w-24 h-12 opacity-30">
                  <svg viewBox="0 0 100 40" className="w-full h-full">
                    <path d="M0,35 Q20,30 40,20 T80,10 T100,5" fill="none" stroke="#10B981" strokeWidth="3" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
            </div>

            {/* 2. SECONDARY STATS (CASH & P&L) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="bg-white p-5 rounded-[24px] border border-gray-100 shadow-sm flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Cash</p>
                  <p className="text-2xl font-black text-gray-900">845,200 ฿</p>
                </div>
                <div className="w-10 h-10 rounded-full bg-gray-50 flex items-center justify-center text-gray-400"><DollarSign size={20} /></div>
              </div>
              <div className="bg-emerald-50/50 p-5 rounded-[24px] border border-emerald-100 flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold text-emerald-600/70 uppercase tracking-widest">Floating P&L</p>
                  <p className="text-2xl font-black text-emerald-600">+12,500 ฿</p>
                </div>
                <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-500"><Percent size={20} /></div>
              </div>
            </div>

            {/* 3. ACTIVE POSITIONS */}
            <div className="flex-1">
              <PortfolioActivePositions />
            </div>
          </div>

          {/* ======================================================== */}
          {/* RIGHT COLUMN (4/12) - RISK & INTELLIGENCE */}
          {/* ======================================================== */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div className="h-auto">
              <PortfolioMargin />
            </div>
            <div className="h-auto">
              <PortfolioMarketBias />
            </div>
            <div className="flex-1">
              <PortfolioAllocation />
            </div>
          </div>

        </div>
      </div>
    </section>
  );
};