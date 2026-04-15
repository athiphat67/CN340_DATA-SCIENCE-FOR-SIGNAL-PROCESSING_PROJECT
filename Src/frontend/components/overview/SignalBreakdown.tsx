import React, { useState } from 'react';
import { ArrowUpRight } from 'lucide-react';

export const SignalBreakdown = () => {
  const [grossFilter, setGrossFilter] = useState<string>('All');
  const barHeights = [40, 55, 72, 50, 65, 85, 100, 78, 60, 45];

  return (
    <div className="bg-white rounded-[24px] p-6 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full">
      <div className="flex items-center justify-between mb-1">
        <h2 className="text-lg font-semibold text-gray-900">Signal Breakdown</h2>
        <button className="w-7 h-7 rounded-full border border-gray-200 flex items-center justify-center text-gray-400 hover:text-gray-600 transition">
          <ArrowUpRight size={14} />
        </button>
      </div>
      <p className="text-xs text-gray-400 mb-1">Accuracy this month</p>
      <p className="text-4xl font-semibold text-gray-900 mb-5">
        85.4%
        <span className="text-base font-normal text-emerald-500 ml-2">↑ +3.2%</span>
      </p>

      {/* Bar chart */}
      <div className="relative" style={{ height: 200 }}>
        <div className="absolute left-0 top-0 h-full flex flex-col justify-between text-xs text-gray-300 pr-3" style={{ width: 32 }}>
          <span>100%</span><span>80%</span><span>60%</span><span>40%</span><span>20%</span><span></span>
        </div>
        
        <div className="absolute left-8 right-0 bottom-0 top-0 flex items-end gap-1.5 pb-0">
          {barHeights.slice(0, 7).map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-t-md"
              style={{
                height: `${h}%`,
                background: 'linear-gradient(180deg, #824199 0%, #5c2d6b 100%)',
                opacity: 0.7,
              }}
            />
          ))}
          {/* Highlighted last bars */}
          <div className="relative flex gap-1.5 items-end">
            <div
              className="absolute text-center whitespace-nowrap z-10 rounded-xl px-3 py-1.5 text-xs text-white font-medium shadow-lg"
              style={{ background: '#1a0a24', bottom: '110%', left: '50%', transform: 'translateX(-50%)', marginBottom: 4 }}
            >
              85% <span className="text-white/50">confidence</span> · <span className="text-[#f9d443]">today</span>
            </div>
            <div
              className="rounded-t-md"
              style={{ height: 180, width: 36, background: 'linear-gradient(180deg, #824199 0%, #5c2d6b 100%)' }}
            />
            <div
              className="rounded-t-md"
              style={{ height: 148, width: 36, background: 'linear-gradient(180deg, #f9d443 0%, #d97706 100%)' }}
            />
          </div>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
        {['All', 'BUY', 'SELL', 'HOLD'].map((f) => (
          <button
            key={f}
            onClick={() => setGrossFilter(f)}
            className={`text-xs px-3 py-1 rounded-full cursor-pointer transition-all ${
              grossFilter === f
                ? 'bg-gray-900 text-white font-semibold'
                : 'text-gray-400 hover:text-gray-600'
            }`}
          >
            {f}
          </button>
        ))}
      </div>
    </div>
  );
};