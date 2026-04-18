import React from 'react';
import { Target, TrendingUp, Activity, BarChart2 } from 'lucide-react';

export const SignalStatsCards = () => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 font-sans">

      {/* 🟣 Card 1: Net P&L (เพิ่มความเข้มของขอบและตัวหนังสือ) */}
      <div className="bg-gradient-to-br from-[#fdfaff] via-[#f5eefc] to-[#ede4f5] p-6 rounded-[24px] border-2 border-purple-400 ring-4 ring-purple-100/40 shadow-xl flex flex-col justify-between relative overflow-hidden transition-all duration-300">
        <div className="absolute -top-10 -right-10 w-32 h-32 bg-[#824199]/15 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center justify-between mb-4 relative z-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center text-[#824199] border-2 border-purple-200 shadow-sm">
              <BarChart2 size={16} strokeWidth={2.5} />
            </div>
            {/* ✨ ปรับสีตัวหนังสือให้เป็น Purple-900 เพื่อความเข้มชัดเจน */}
            <p className="text-[11px] font-black text-purple-900 uppercase tracking-[0.15em]">Net P&L (Period)</p>
          </div>
        </div>

        <div className="relative z-10">
          <div className="flex items-baseline gap-2">
            <p className="text-4xl font-black text-gray-900 tracking-tight">+45,200</p>
            <span className="text-xl font-black text-purple-700">฿</span>
          </div>
          <p className="text-[10px] text-purple-800/60 font-black mt-1 uppercase tracking-tighter">Based on closed positions</p>
        </div>
      </div>

      {/* 🟢 Card 2: Win Rate (เพิ่มขอบสีเขียวเข้มและมิติขอบสองชั้น) */}
      <div className="bg-gradient-to-br from-emerald-50 to-white p-6 rounded-[24px] border-2 border-emerald-600 ring-4 ring-emerald-50 shadow-xl flex flex-col justify-between relative overflow-hidden transition-all duration-300">
        <div className="flex items-center gap-2 mb-4 relative z-10">
          <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center text-emerald-600 border border-emerald-200 shadow-sm">
            <TrendingUp size={16} />
          </div>
          <p className="text-[11px] font-black text-emerald-700/70 uppercase tracking-widest">Estimated Win Rate</p>
        </div>
        <div className="relative z-10">
          <div className="flex items-baseline gap-1.5">
            <p className="text-4xl font-black text-emerald-600 tracking-tight">72.5</p>
            <span className="text-xl font-bold text-emerald-500">%</span>
          </div>
          {/* Mini Progress Bar */}
          <div className="w-full h-2 bg-emerald-100/50 rounded-full mt-3 overflow-hidden border border-emerald-100">
            <div className="h-full bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.4)]" style={{ width: '72.5%' }}></div>
          </div>
        </div>
      </div>

      {/* 🔵 Card 3: Total Signals (อัปเกรดให้เด่นเท่ากันด้วยโทน Blue-Indigo) */}
      <div className="bg-gradient-to-br from-blue-50 via-white to-indigo-50/50 p-6 rounded-[24px] border-2 border-blue-200 ring-4 ring-blue-50/60 shadow-xl flex flex-col justify-between relative overflow-hidden transition-all duration-300">
        <div className="flex items-center justify-between mb-4 relative z-10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-white flex items-center justify-center text-blue-600 border border-blue-100 shadow-sm">
              <Target size={16} />
            </div>
            <p className="text-[11px] font-black text-blue-600/70 uppercase tracking-widest">Total Signals</p>
          </div>
          <span className="flex items-center gap-1.5 text-[10px] text-emerald-600 bg-white px-2.5 py-1 rounded-lg border border-emerald-100 font-bold uppercase tracking-wider shadow-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            2 Active
          </span>
        </div>
        <div className="relative z-10">
          <p className="text-4xl font-black text-gray-900 tracking-tight">124</p>
          <div className="flex items-center gap-1 mt-1">
            <span className="text-[10px] text-blue-600 font-black">+12</span>
            <span className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">signals this week</span>
          </div>
        </div>
        {/* Background Activity Graphic */}
        <div className="absolute -bottom-6 -right-6 text-blue-100/30 pointer-events-none transform rotate-12">
          <Activity size={140} strokeWidth={1} />
        </div>
      </div>

    </div>
  );
};