import React from 'react';
import { Wallet, DollarSign, Activity, Percent } from 'lucide-react';

export const PortfolioSummaryCards = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      
      {/* 1. Total Equity (โดดเด่นที่สุด) */}
      <div className="md:col-span-2 bg-gradient-to-br from-[#1a0a24] to-[#2d1040] p-6 rounded-[24px] border border-[#824199]/20 shadow-lg relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 bg-[#824199]/30 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/3" />
        <div className="flex items-center gap-2 mb-4 relative z-10">
          <div className="w-8 h-8 rounded-full bg-white/10 backdrop-blur-md flex items-center justify-center text-yellow-400 border border-white/10">
            <Wallet size={16} />
          </div>
          <p className="text-[11px] font-bold text-white/70 uppercase tracking-widest">Total Equity</p>
        </div>
        <div className="relative z-10">
          <div className="flex items-baseline gap-2">
            <p className="text-4xl font-black text-white tracking-tight">1,245,200</p>
            <span className="text-xl font-bold text-[#f9d443]">฿</span>
          </div>
          <p className="text-xs text-emerald-400 font-medium mt-1.5 flex items-center gap-1">
             <Activity size={12} /> +12.4% All Time
          </p>
        </div>
      </div>

      {/* 2. Available Cash */}
      <div className="bg-white p-6 rounded-[24px] border border-gray-100 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between mb-4">
           <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Available Cash</p>
           <DollarSign size={16} className="text-gray-400" />
        </div>
        <div>
          <p className="text-2xl font-black text-gray-900">845,200 <span className="text-sm text-gray-400">฿</span></p>
          <p className="text-[11px] text-gray-500 font-medium mt-1">Ready for deployment</p>
        </div>
      </div>

      {/* 3. Unrealized P&L (กำไร/ขาดทุนที่ยังไม่ปิด) */}
      <div className="bg-emerald-50/50 p-6 rounded-[24px] border border-emerald-100 flex flex-col justify-between">
        <div className="flex items-center justify-between mb-4">
           <p className="text-[11px] font-bold text-emerald-700/70 uppercase tracking-widest">Floating P&L</p>
           <Percent size={16} className="text-emerald-500" />
        </div>
        <div>
          <p className="text-2xl font-black text-emerald-600">+12,500 <span className="text-sm">฿</span></p>
          <p className="text-[11px] text-emerald-600/70 font-bold mt-1">From 2 Active Positions</p>
        </div>
      </div>

    </div>
  );
};