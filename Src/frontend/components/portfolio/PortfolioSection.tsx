import React from 'react';
import { OverviewHeader } from '../overview/OverviewHeader';
import { PortfolioHeader } from './PortfolioHeader';

// นำเข้า Component อื่นๆ (สังเกตว่าจะไม่มี PortfolioSummaryCards แล้ว)
import { PortfolioAllocation } from './PortfolioAllocation';
import { PortfolioMargin } from './PortfolioMargin';
import { PortfolioMarketBias } from './PortfolioMarketBias';
import { PortfolioActivePositions } from './PortfolioActivePositions';
import { PortfolioRecentActivity } from './PortfolioRecentActivity';

// นำเข้า Icon สำหรับกล่องสรุปด้านบน
import { Wallet, DollarSign, Activity, Percent } from 'lucide-react';

export const PortfolioSection = () => {
  return (
    <section className="w-full min-h-screen pb-12" style={{ background: '#FCFBF7' }}>
      <OverviewHeader />

      <div className="px-6 mt-8 relative z-20 max-w-7xl mx-auto">
        <PortfolioHeader />

        {/* 🚀 BENTO BOX MASTER GRID 🚀 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

          {/* ======================================================== */}
          {/* COLUMN 1: FINANCIALS & ACTIONS (ฝั่งซ้าย - กินพื้นที่ 8/12) */}
          {/* ======================================================== */}
          <div className="lg:col-span-8 flex flex-col gap-6">
            
            {/* 1. MAIN EQUITY (ดึงดูดสายตาสุด) */}
            <div className="bg-gradient-to-br from-[#1a0a24] to-[#2d1040] p-8 rounded-[24px] border border-[#824199]/20 shadow-lg relative overflow-hidden">
              <div className="absolute top-0 right-0 w-64 h-64 bg-[#824199]/30 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/3" />
              <div className="flex items-center gap-3 mb-6 relative z-10">
                <div className="w-10 h-10 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center text-yellow-400 border border-white/10">
                  <Wallet size={20} />
                </div>
                <p className="text-xs font-bold text-white/70 uppercase tracking-widest">Total Equity</p>
              </div>
              <div className="relative z-10">
                <div className="flex items-baseline gap-2">
                  <p className="text-5xl font-black text-white tracking-tight">1,245,200</p>
                  <span className="text-2xl font-bold text-[#f9d443]">฿</span>
                </div>
                <p className="text-sm text-emerald-400 font-medium mt-2 flex items-center gap-1.5">
                  <Activity size={14} /> +12.4% All Time Return
                </p>
              </div>
            </div>

            {/* 2. CASH & P&L (กล่องเล็กคู่กัน แบ่งครึ่งพอดี) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {/* Cash */}
              <div className="bg-white p-6 rounded-[24px] border border-gray-100 shadow-sm flex flex-col justify-between">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Available Cash</p>
                  <div className="w-8 h-8 rounded-full bg-gray-50 flex items-center justify-center">
                    <DollarSign size={16} className="text-gray-400" />
                  </div>
                </div>
                <div>
                  <p className="text-3xl font-black text-gray-900">845,200 <span className="text-base text-gray-400">฿</span></p>
                  <p className="text-xs text-gray-500 font-medium mt-1">Ready for deployment</p>
                </div>
              </div>
              
              {/* P&L */}
              <div className="bg-emerald-50/50 p-6 rounded-[24px] border border-emerald-100 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-[11px] font-bold text-emerald-700/70 uppercase tracking-widest">Floating P&L</p>
                  <div className="w-8 h-8 rounded-full bg-emerald-100/50 flex items-center justify-center">
                    <Percent size={16} className="text-emerald-600" />
                  </div>
                </div>
                <div>
                  <p className="text-3xl font-black text-emerald-600">+12,500 <span className="text-base">฿</span></p>
                  <p className="text-xs text-emerald-600/70 font-bold mt-1">From 2 Active Positions</p>
                </div>
              </div>
            </div>

            {/* 3. ACTIVE POSITIONS TABLE (ขยายเต็มพื้นที่ด้านล่าง) */}
            <div className="flex-1 min-h-[400px]">
              <PortfolioActivePositions />
            </div>

          </div>


          {/* ======================================================== */}
          {/* COLUMN 2: INSIGHTS & RISK (ฝั่งขวา - กินพื้นที่ 4/12) */}
          {/* ======================================================== */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            
            {/* RISK CENTER: ถูกดันมาอยู่ขวาบน เพื่อบาลานซ์กล่องสีดำซ้ายบน! */}
            <div className="h-auto">
              <PortfolioMargin />
            </div>

            <div className="h-auto">
              <PortfolioMarketBias />
            </div>

            <div className="h-auto">
              <PortfolioAllocation />
            </div>

            {/* RECENT ACTIVITY: เป็น Feed แนวตั้งสวยๆ */}
            <div className="flex-1 min-h-[300px]">
              <PortfolioRecentActivity />
            </div>

          </div>

        </div>
      </div>
    </section>
  );
};