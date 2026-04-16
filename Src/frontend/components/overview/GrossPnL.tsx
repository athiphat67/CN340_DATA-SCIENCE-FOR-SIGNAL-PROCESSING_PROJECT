import React from 'react';
import { Activity, Brain, PieChart, TrendingUp, Minus, TrendingDown } from 'lucide-react';

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

export const GrossPnL = () => {
  return (
    <div className="flex flex-col gap-4 h-full">
      
      {/* 1. กล่อง Agent Conviction (ใส่ flex-1 เพื่อให้สูงเท่า Live Portfolio) */}
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

        {/* AI Reasoning */}
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

      {/* 2. กล่อง Market Bias (ใส่ flex-1 ทำให้ขอบล่างไปชนขอบล่างของ Gold Inventory เป๊ะ) */}
      <div className="flex-1 bg-white rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-50 flex flex-col justify-between">
        
        <div className="flex items-center justify-between mb-2">
           <h2 className="text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
             <PieChart size={16} className="text-gray-400" />
             Market Bias
          </h2>
        </div>

        {/* Stacked Bar แบบใหญ่ขึ้นเพื่อให้เด่น */}
        <div className="my-2">
            <div className="h-6 flex rounded-full overflow-hidden shadow-inner mb-2">
               <div className="bg-gradient-to-r from-emerald-400 to-emerald-500 h-full relative" style={{ width: '75%' }}>
                  <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white/80">75%</span>
               </div>
               <div className="bg-gradient-to-r from-amber-300 to-yellow-400 h-full relative" style={{ width: '20%' }}></div>
               <div className="bg-gradient-to-r from-rose-400 to-rose-500 h-full relative" style={{ width: '5%' }}></div>
            </div>
        </div>

        {/* Breakdown List - ช่วยเติมเต็มพื้นที่แนวตั้งให้สวยงาม */}
        <div className="space-y-3 mt-auto">
            <div className="flex items-center justify-between p-3 rounded-[16px] bg-emerald-50/50 border border-emerald-50 hover:border-emerald-100 transition-colors">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shadow-sm">
                        <TrendingUp size={18} />
                    </div>
                    <div>
                        <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Bullish</p>
                        <p className="text-sm font-bold text-gray-900 leading-none">BUY Signals</p>
                    </div>
                </div>
                <span className="text-xl font-black text-emerald-600">75%</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-[16px] bg-yellow-50/50 border border-yellow-50 hover:border-yellow-100 transition-colors">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-yellow-100 text-yellow-600 flex items-center justify-center shadow-sm">
                        <Minus size={18} />
                    </div>
                    <div>
                        <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Neutral</p>
                        <p className="text-sm font-bold text-gray-900 leading-none">HOLD Signals</p>
                    </div>
                </div>
                <span className="text-xl font-black text-yellow-600">20%</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-[16px] bg-rose-50/50 border border-rose-50 hover:border-rose-100 transition-colors">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center shadow-sm">
                        <TrendingDown size={18} />
                    </div>
                    <div>
                        <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Bearish</p>
                        <p className="text-sm font-bold text-gray-900 leading-none">SELL Signals</p>
                    </div>
                </div>
                <span className="text-xl font-black text-rose-600">5%</span>
            </div>
        </div>

      </div>

    </div>
  );
};