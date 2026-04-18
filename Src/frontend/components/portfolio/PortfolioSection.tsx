import React from 'react';
import { OverviewHeader } from '../overview/OverviewHeader';
import { PortfolioHeader } from './PortfolioHeader';

// Components
import { PortfolioAllocation } from './PortfolioAllocation';
import { AgentHealthMonitor } from './AgentHealthMonitor';
import { PortfolioMarketBias } from './PortfolioMarketBias';
import { PortfolioActivePositions } from './PortfolioActivePositions';

// Icons
import { DollarSign, Percent, TrendingUp, ShieldCheck, Wallet, ArrowUpRight, Globe } from 'lucide-react';

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

            {/* 1. PROFIT MATRIX DASHBOARD (TOTAL NET EQUITY - REDESIGNED) */}
            <div className="relative bg-white/95 backdrop-blur-3xl rounded-[40px] border border-white shadow-[0_30px_70px_rgba(130,65,153,0.08)] overflow-hidden p-10 flex flex-col h-[340px] justify-between group transition-all duration-500 hover:translate-y-[-2px]">

              {/* Background Decor & Watermark */}
              <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-gradient-to-br from-purple-100/40 via-emerald-50/20 to-transparent blur-[110px] rounded-full -mr-32 -mt-32 pointer-events-none" />
              <div className="absolute -bottom-16 -right-16 opacity-[0.03] group-hover:opacity-[0.06] transition-opacity duration-1000 pointer-events-none group-hover:rotate-12 transition-transform">
                <Wallet size={320} strokeWidth={1} className="text-[#824199]" />
              </div>

              <div className="relative z-10">
                <div className="flex items-center justify-between mb-8">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-[#824199] to-[#a855f7] flex items-center justify-center shadow-[0_8px_20px_rgba(130,65,153,0.3)] group-hover:rotate-3 transition-transform">
                      <ShieldCheck size={20} className="text-white" />
                    </div>
                    <div>
                      <p className="text-[11px] font-black text-[#824199] uppercase tracking-[0.2em]">Verified Portfolio</p>
                      <p className="text-[9px] text-gray-400 font-bold uppercase tracking-widest">Global Asset Node</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 border border-emerald-100 rounded-2xl shadow-sm">
                      <TrendingUp size={14} className="text-emerald-500" />
                      <span className="text-[10px] font-black text-emerald-600 uppercase tracking-tighter">+1.2% Today</span>
                    </div>
                  </div>
                </div>

                <div className="ml-2">
                  <p className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.4em] mb-2 opacity-60">Total Net Equity</p>
                  <div className="flex items-baseline gap-3">
                    <p className="text-6xl font-black text-gray-900 tracking-tighter leading-none group-hover:scale-[1.01] transition-transform duration-500">1,245,200</p>
                    <div className="flex flex-col">
                      <span className="text-xl font-black text-[#824199] leading-none mb-1">฿</span>
                      <span className="text-[9px] font-bold text-gray-300 uppercase">THB</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stats Footer - แทนที่กราฟด้วยข้อมูลที่ดูเป็นระบบมากขึ้น */}
              <div className="relative z-10 flex items-end justify-between border-t border-gray-100 pt-8 mt-4 ml-2">
                <div className="flex gap-14">
                  <div className="relative">
                    <p className="text-[10px] font-bold text-gray-400 uppercase mb-2 tracking-widest">Success Rate</p>
                    <div className="flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_12px_rgba(52,211,153,0.6)]" />
                      <p className="text-3xl font-black text-gray-900 tracking-tight">92.4%</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-gray-400 uppercase mb-2 tracking-widest">Total Growth</p>
                    <p className="text-3xl font-black text-emerald-500 tracking-tight">+14.2<span className="text-emerald-300 text-lg font-bold ml-1">%</span></p>
                  </div>
                </div>

                {/* ข้อมูลเสริมที่ทำให้กล่องดูสมดุล (แทนที่กราฟ) */}
                <div className="flex flex-col items-end gap-1">
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-xl border border-gray-100 group-hover:border-purple-100 transition-colors">
                    <Globe size={12} className="text-gray-400 group-hover:text-[#824199]" />
                    <p className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Live Node: TH-BK1</p>
                  </div>
                  <p className="text-[9px] font-bold text-gray-300 uppercase tracking-[0.1em] mr-1">Last Sync: Just now</p>
                </div>
              </div>
            </div>


            {/* 2. SECONDARY STATS (CASH & P&L) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {/* Available Cash Box - คงไว้เหมือนเดิม */}
              <div className="bg-white p-6 rounded-[32px] border border-gray-100 shadow-sm flex items-center justify-between group hover:shadow-md transition-all">
                <div>
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Available Cash</p>
                  <p className="text-2xl font-black text-gray-900">845,200 <span className="text-sm font-bold text-gray-300 ml-1">฿</span></p>
                </div>
                <div className="w-14 h-14 rounded-2xl bg-gray-50 flex items-center justify-center text-gray-400 group-hover:bg-purple-50 group-hover:text-[#824199] transition-all">
                  <DollarSign size={24} />
                </div>
              </div>

              {/* Unrealized P&L Box - เพิ่มขอบสีเขียวเข้ม (border-emerald-500) */}
              <div className="bg-emerald-50/40 p-6 rounded-[32px] border-2 border-emerald-500 flex items-center justify-between group hover:bg-emerald-50 transition-all shadow-[0_4px_20px_rgba(16,185,129,0.1)]">
                <div>
                  <p className="text-[10px] font-bold text-emerald-600/70 uppercase tracking-widest mb-1">Unrealized P&L</p>
                  <p className="text-2xl font-black text-emerald-600">+12,500 <span className="text-sm font-bold text-emerald-400/60 ml-1">฿</span></p>
                </div>
                <div className="w-14 h-14 rounded-2xl bg-emerald-500 flex items-center justify-center text-white group-hover:scale-110 transition-transform duration-500 shadow-lg shadow-emerald-200">
                  <Percent size={24} strokeWidth={3} />
                </div>
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
              <AgentHealthMonitor />
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