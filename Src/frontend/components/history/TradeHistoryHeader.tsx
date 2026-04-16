import React from 'react';
import { Download, TrendingUp, PieChart, BarChart3, Activity, Sparkles } from 'lucide-react';

export const TradeHistoryHeader = () => {
  return (
    <div className="flex flex-col gap-10 mb-10">
      {/* 1. Page Title & Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
             <Sparkles size={16} className="text-[#824199]" />
             <p className="text-[10px] font-bold text-[#824199] uppercase tracking-[0.3em]">Performance Analytics</p>
          </div>
          <h1 className="text-4xl font-black text-gray-900 tracking-tight">Trade History</h1>
        </div>
        <button className="px-6 py-3 bg-white border border-gray-200 rounded-2xl text-[11px] font-bold text-gray-700 shadow-sm hover:shadow-md transition-all flex items-center gap-2 active:scale-95">
          <Download size={14} /> Export CSV Report
        </button>
      </div>

      {/* 2. Three Distinct Luxury Cards (แยกพาร์ทชัดเจน) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        
        {/* --- Card 1: Total Profit (The Hero Card) --- */}
        <div className="md:col-span-2 relative bg-gradient-to-br from-[#1a0a24] via-[#2d1040] to-[#1a0a24] p-8 rounded-[32px] border border-white/10 shadow-2xl overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
          <div className="relative z-10 flex flex-col h-full justify-between">
            <div className="flex items-center gap-2 mb-6">
               <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                  <Activity size={14} className="text-emerald-400" />
               </div>
               <p className="text-[10px] font-bold text-white/40 uppercase tracking-widest">Total Realized P&L</p>
            </div>
            <div>
              <div className="flex items-baseline gap-2">
                <p className="text-6xl font-black text-white tracking-tighter drop-shadow-lg">145,200</p>
                <span className="text-2xl font-bold text-yellow-400">฿</span>
              </div>
              <p className="text-xs text-emerald-400 font-bold mt-3 flex items-center gap-1.5">
                <TrendingUp size={14} /> +8.4% vs Last Period
              </p>
            </div>
          </div>
        </div>

        {/* --- Card 2: Efficiency (Win Rate) --- */}
        <div className="relative bg-gradient-to-br from-[#0f172a] to-[#1e293b] p-8 rounded-[32px] border border-white/10 shadow-xl overflow-hidden">
           <div className="absolute -bottom-8 -right-8 w-24 h-24 bg-blue-500/10 rounded-full blur-2xl" />
           <div className="relative z-10 flex flex-col h-full">
              <div className="flex items-center gap-2 mb-8">
                 <PieChart size={16} className="text-blue-400" />
                 <p className="text-[10px] font-bold text-white/30 uppercase tracking-widest">Efficiency</p>
              </div>
              <div className="mt-auto">
                 <p className="text-4xl font-black text-white mb-2">84%</p>
                 <p className="text-[10px] text-blue-400/60 font-bold uppercase mb-4 tracking-tighter">Win Rate Score</p>
                 <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)] w-[84%]" />
                 </div>
              </div>
           </div>
        </div>

        {/* --- Card 3: Performance (Avg Profit) --- */}
        <div className="relative bg-gradient-to-br from-[#1a0a24] to-[#2d1040] p-8 rounded-[32px] border border-white/10 shadow-xl overflow-hidden">
           <div className="absolute -bottom-8 -right-8 w-24 h-24 bg-purple-500/10 rounded-full blur-2xl" />
           <div className="relative z-10 flex flex-col h-full">
              <div className="flex items-center gap-2 mb-8">
                 <BarChart3 size={16} className="text-purple-400" />
                 <p className="text-[10px] font-bold text-white/30 uppercase tracking-widest">Performance</p>
              </div>
              <div className="mt-auto">
                 <p className="text-4xl font-black text-white mb-2">3,450 <span className="text-lg font-bold text-white/30">฿</span></p>
                 <p className="text-[10px] text-purple-400/60 font-bold uppercase mb-4 tracking-tighter">Avg. Profit / Trade</p>
                 <div className="flex gap-1">
                    {[...Array(5)].map((_, i) => (
                       <div key={i} className={`h-1 flex-1 rounded-full ${i < 4 ? 'bg-[#824199]' : 'bg-white/5'}`} />
                    ))}
                 </div>
              </div>
           </div>
        </div>

      </div>
    </div>
  );
};