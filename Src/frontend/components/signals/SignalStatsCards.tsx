import React from 'react';
import { Target, TrendingUp, Activity, BarChart2 } from 'lucide-react';

export const SignalStatsCards = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 font-sans">

      {/* 🟣 Card 1: Net P&L (เพิ่ม Hover Effect สว่างขึ้น และ Text Gradient) */}
      <div className="group bg-gradient-to-br from-[#fdfaff] via-[#f5eefc] to-[#ede4f5] p-6 rounded-[24px] border-2 border-purple-200 hover:border-purple-400 ring-4 ring-transparent hover:ring-purple-100/60 shadow-lg hover:shadow-2xl flex flex-col justify-between relative overflow-hidden transition-all duration-500 hover:-translate-y-1.5 cursor-default">
        {/* Animated Glow */}
        <div className="absolute -top-10 -right-10 w-32 h-32 bg-[#824199]/15 rounded-full blur-3xl pointer-events-none transition-transform duration-700 group-hover:scale-150 group-hover:bg-[#824199]/25" />

        <div className="flex items-center justify-between mb-4 relative z-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center text-[#824199] border-2 border-purple-100 group-hover:border-purple-300 shadow-sm transition-colors duration-300">
              <BarChart2 size={16} strokeWidth={2.5} />
            </div>
            <p className="text-[11px] font-black text-purple-900 uppercase tracking-[0.15em]">Net P&L (Period)</p>
          </div>
        </div>

        <div className="relative z-10">
          <div className="flex items-baseline gap-2">
            {/* Text Gradient */}
            <p className="text-4xl font-black bg-clip-text text-transparent bg-gradient-to-r from-purple-900 to-purple-500 tracking-tight drop-shadow-sm">
              +45,200
            </p>
            <span className="text-xl font-black text-purple-700">฿</span>
          </div>
          <p className="text-[10px] text-purple-800/60 font-black mt-1 uppercase tracking-tighter">Based on closed positions</p>
        </div>
      </div>

      {/* 🟢 Card 2: Win Rate (ปรับขอบให้ละมุนขึ้น และ Progress bar เรืองแสงตอน Hover) */}
      <div className="group bg-gradient-to-br from-emerald-50 to-white p-6 rounded-[24px] border-2 border-emerald-300 hover:border-emerald-500 ring-4 ring-transparent hover:ring-emerald-50/80 shadow-lg hover:shadow-2xl flex flex-col justify-between relative overflow-hidden transition-all duration-500 hover:-translate-y-1.5 cursor-default">
        <div className="flex items-center gap-2 mb-4 relative z-10">
          <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center text-emerald-600 border border-emerald-100 group-hover:border-emerald-300 shadow-sm transition-colors duration-300">
            <TrendingUp size={16} />
          </div>
          <p className="text-[11px] font-black text-emerald-700/70 uppercase tracking-widest">Estimated Win Rate</p>
        </div>
        <div className="relative z-10">
          <div className="flex items-baseline gap-1.5">
            <p className="text-4xl font-black text-emerald-600 tracking-tight group-hover:scale-105 transition-transform duration-300 origin-left">
              72.5
            </p>
            <span className="text-xl font-bold text-emerald-500">%</span>
          </div>
          {/* Mini Progress Bar */}
          <div className="w-full h-2 bg-emerald-100/50 rounded-full mt-3 overflow-hidden border border-emerald-100">
            <div 
              className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.4)] group-hover:shadow-[0_0_12px_rgba(16,185,129,0.8)] transition-all duration-500 relative" 
              style={{ width: '72.5%' }}
            >
              {/* Highlight sweep effect */}
              <div className="absolute top-0 left-0 w-full h-full bg-white/20 -skew-x-12 -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]" />
            </div>
          </div>
        </div>
      </div>

      {/* 🔵 Card 3: Total Signals (ให้ลายน้ำขยับได้เวลาชี้) */}
      <div className="group bg-gradient-to-br from-blue-50 via-white to-indigo-50/50 p-6 rounded-[24px] border-2 border-blue-200 hover:border-blue-400 ring-4 ring-transparent hover:ring-blue-50/80 shadow-lg hover:shadow-2xl flex flex-col justify-between relative overflow-hidden transition-all duration-500 hover:-translate-y-1.5 cursor-default">
        <div className="flex items-center justify-between mb-4 relative z-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center text-blue-600 border border-blue-100 group-hover:border-blue-300 shadow-sm transition-colors duration-300">
              <Target size={16} />
            </div>
            <p className="text-[11px] font-black text-blue-600/70 uppercase tracking-widest">Total Signals</p>
          </div>
          <span className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-white px-2.5 py-1 rounded-lg border border-emerald-100 font-bold uppercase tracking-wider shadow-sm transition-colors duration-300 group-hover:border-emerald-300">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_4px_rgba(16,185,129,0.5)]"></span>
            2 Active
          </span>
        </div>
        <div className="relative z-10">
          <p className="text-4xl font-black text-gray-900 tracking-tight group-hover:text-blue-900 transition-colors duration-300">
            124
          </p>
          <div className="flex items-center gap-1 mt-1">
            <span className="text-[10px] text-blue-600 font-black px-1.5 py-0.5 bg-blue-100/50 rounded-md">+12</span>
            <span className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">signals this week</span>
          </div>
        </div>
        {/* Background Activity Graphic - Animated on Hover */}
        <div className="absolute -bottom-6 -right-6 text-blue-100/40 pointer-events-none transform rotate-12 transition-all duration-700 ease-out group-hover:scale-125 group-hover:-rotate-6 group-hover:text-blue-200/40">
          <Activity size={140} strokeWidth={1} />
        </div>
      </div>

    </div>
  );
};