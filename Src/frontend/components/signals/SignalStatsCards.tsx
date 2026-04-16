import React from 'react';
import { Target, TrendingUp, Activity, BarChart2 } from 'lucide-react';

export const SignalStatsCards = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      
      {/* 🔄 [ตำแหน่งใหม่] Card 1: Net P&L (กล่องม่วงดำพรีเมียม) */}
      <div className="bg-gradient-to-br from-[#1a0a24] to-[#2d1040] p-6 rounded-[24px] border border-[#824199]/20 shadow-[0_8px_30px_rgb(130,65,153,0.15)] flex flex-col justify-between relative overflow-hidden">
        <div className="absolute -top-10 -right-10 w-32 h-32 bg-[#824199]/40 rounded-full blur-3xl pointer-events-none" />
        
        <div className="flex items-center justify-between mb-4 relative z-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-white/10 backdrop-blur-sm flex items-center justify-center text-purple-300 border border-white/10">
              <BarChart2 size={16} />
            </div>
            <p className="text-[11px] font-bold text-purple-300/70 uppercase tracking-widest">Net P&L (Period)</p>
          </div>
        </div>
        
        <div className="relative z-10">
          <div className="flex items-baseline gap-2">
            <p className="text-4xl font-black text-white tracking-tight">+45,200</p>
            <span className="text-xl font-bold text-purple-400">฿</span>
          </div>
          <p className="text-xs text-purple-300/50 font-medium mt-1">Based on closed positions</p>
        </div>
      </div>

      {/* Card 2: Win Rate (ตำแหน่งเดิม) */}
      <div className="bg-gradient-to-br from-emerald-50 to-teal-50/30 p-6 rounded-[24px] border border-emerald-100/50 shadow-[0_8px_30px_rgb(16,185,129,0.05)] flex flex-col justify-between relative overflow-hidden">
        <div className="flex items-center gap-2 mb-4 relative z-10">
          <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 shadow-sm">
            <TrendingUp size={16} />
          </div>
          <p className="text-[11px] font-bold text-emerald-700/70 uppercase tracking-widest">Estimated Win Rate</p>
        </div>
        <div className="relative z-10">
          <div className="flex items-baseline gap-1.5">
            <p className="text-4xl font-black text-emerald-600 tracking-tight">72.5</p>
            <span className="text-xl font-bold text-emerald-500">%</span>
          </div>
          {/* Mini Progress Bar */}
          <div className="w-full h-1.5 bg-emerald-100 rounded-full mt-3 overflow-hidden">
             <div className="h-full bg-emerald-500 rounded-full" style={{ width: '72.5%' }}></div>
          </div>
        </div>
      </div>

      {/* 🔄 [ตำแหน่งใหม่] Card 3: Total Signals & Activity */}
      <div className="bg-white p-6 rounded-[24px] border border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] flex flex-col justify-between relative overflow-hidden">
        <div className="flex items-center justify-between mb-4 relative z-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-purple-50 flex items-center justify-center text-[#824199]">
              <Target size={16} />
            </div>
            <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Total Signals</p>
          </div>
          <span className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full font-bold uppercase tracking-wider">
             <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
             2 Active
          </span>
        </div>
        <div className="relative z-10">
          <p className="text-4xl font-black text-gray-900 tracking-tight">124</p>
          <p className="text-xs text-gray-400 font-medium mt-1">+12 this week</p>
        </div>
        {/* Background Graphic */}
        <div className="absolute -bottom-4 -right-4 text-gray-50/50 pointer-events-none">
           <Activity size={120} strokeWidth={1} />
        </div>
      </div>

    </div>
  );
};