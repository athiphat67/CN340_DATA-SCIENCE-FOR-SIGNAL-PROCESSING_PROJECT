import React from 'react';
import { Brain, TrendingUp, TrendingDown, Minus } from 'lucide-react';

export const PortfolioMarketBias = () => {
  // ข้อมูลจำลองมุมมองตลาด
  const bias = {
    direction: 'Bullish', // Bullish, Bearish, Neutral
    conviction: 85, // ความมั่นใจ 0-100
    reason: 'Strong support at 41,000 THB and rising MACD momentum.'
  };

  return (
    <div className="bg-gradient-to-br from-[#fcfcfd] to-purple-50/30 p-6 rounded-[24px] border border-[#824199]/10 shadow-sm flex flex-col h-full">
      <div className="flex items-center gap-2 mb-6">
         <Brain size={18} className="text-[#824199]" />
         <h3 className="text-sm font-bold text-gray-900">Agent Market Bias</h3>
      </div>

      <div className="flex-1 flex flex-col justify-center items-center text-center">
        {/* Animated Icon & Direction */}
        <div className="relative mb-3">
          <div className="absolute inset-0 bg-emerald-400 blur-xl opacity-20 rounded-full"></div>
          <div className="w-16 h-16 bg-white rounded-full shadow-md border border-emerald-100 flex items-center justify-center relative z-10 text-emerald-500">
             <TrendingUp size={32} strokeWidth={2.5} />
          </div>
        </div>
        
        <p className="text-2xl font-black text-emerald-600 tracking-tight">{bias.direction}</p>
        
        <div className="flex items-center gap-2 mt-2 bg-white px-3 py-1.5 rounded-full border border-gray-100 shadow-sm">
           <span className="text-[10px] font-bold text-gray-400 uppercase">Conviction Score</span>
           <span className="text-xs font-black text-[#824199]">{bias.conviction}%</span>
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-gray-100/50">
        <p className="text-[11px] text-gray-500 italic leading-relaxed text-center">"{bias.reason}"</p>
      </div>
    </div>
  );
};