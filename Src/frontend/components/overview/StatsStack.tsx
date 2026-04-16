import React from 'react';
import { Wallet, Globe, ArrowUpRight, ArrowDownLeft, RefreshCcw, Activity, Brain} from 'lucide-react';

// MiniBar component สำหรับใช้ใน Agent Conviction
const MiniBar = ({ heights }: { heights: number[] }) => (
  <div className="flex items-end gap-1 h-10">
    {heights.map((h, i) => (
      <div key={i} className="relative group w-1.5 h-full flex items-end">
         <span
           className="w-full rounded-sm transition-all duration-300"
           style={{
             height: `${h}%`,
             background: h > 75 ? 'linear-gradient(to top, #824199, #a855f7)' : '#f3f4f6',
             boxShadow: h > 75 ? '0 0 8px rgba(168, 85, 247, 0.3)' : 'none'
           }}
         />
      </div>
    ))}
  </div>
);

export const StatsStack = () => {
  return (
    <div className="flex flex-col gap-4 h-full">

      {/* กล่อง 1: Live Portfolio (เขียว) */}
      <div className="flex-1 bg-gradient-to-br from-white to-emerald-50/30 rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.03)] border border-emerald-100/50 relative overflow-hidden flex flex-col justify-center">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
            <Wallet size={16} className="text-emerald-500" />
            Live Portfolio
          </h2>
          <span className="flex items-center gap-1.5 text-[10px] text-emerald-700 bg-emerald-100/50 border border-emerald-200/50 px-2 py-1 rounded-full font-bold uppercase tracking-wider">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            Syncing
          </span>
        </div>

        <div className="my-auto">
          <p className="text-xs text-gray-400 font-medium mb-1 uppercase tracking-widest">Available Cash</p>
          <p className="text-4xl font-black text-gray-900 tracking-tight">
            25,000 <span className="text-2xl text-gray-400 font-medium">฿</span>
          </p>
        </div>

        <div className="mt-4 pt-4 border-t border-emerald-100/50 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-500">Unrealized P&L</span>
          <div className="flex items-center gap-1 text-emerald-600 bg-emerald-50 px-2.5 py-1.5 rounded-lg border border-emerald-100 shadow-sm">
            <ArrowUpRight size={16} strokeWidth={2.5} />
            <span className="text-sm font-bold">+3,600 ฿ (14.4%)</span>
          </div>
        </div>
      </div>

      <div className="flex-1 bg-white rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-50 relative overflow-hidden flex flex-col justify-between">
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-[#824199]/5 to-transparent rounded-bl-full pointer-events-none" />
        
        <div className="flex items-center justify-between relative z-10">
          <h2 className="text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
             <Activity size={16} className="text-[#824199]" />
             Agent Conviction
          </h2>
          <span className="px-2.5 py-1 bg-gray-50 text-gray-600 text-[10px] font-bold rounded-lg border border-gray-100 shadow-sm">
             TRADES TODAY: 4
          </span>
        </div>

        <div className="flex items-end justify-between relative z-10 my-4">
          <div>
             <div className="flex items-baseline gap-1">
               <p className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight">85</p>
               <span className="text-2xl font-bold text-gray-400">%</span>
             </div>
             <p className="text-xs text-gray-400 mt-1 font-medium">Average Confidence Level</p>
          </div>
          <MiniBar heights={[30, 50, 45, 70, 60, 90, 100, 80, 55, 85]} />
        </div>

        <div className="bg-gradient-to-br from-[#824199]/5 to-[#824199]/10 rounded-xl p-4 border border-[#824199]/10 relative z-10">
           <div className="flex items-center gap-2 mb-2 text-[#824199]">
              <Brain size={14} />
              <span className="text-[11px] font-bold uppercase tracking-wider">AI Reasoning</span>
           </div>
           <p className="text-sm text-gray-700 font-medium leading-relaxed italic line-clamp-2">
             "Detected strong bullish MACD crossover on the 4H timeframe. Price holding above 2350."
           </p>
        </div>
      </div>

    </div>
  );
};