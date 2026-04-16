import React from 'react';
import { Search } from 'lucide-react';

export const GrossPnL = () => {
  const pnlItems = [
    { label: 'BUY Signals',   value: '+28,400 ฿', pct: 78, color: '#10b981' },
    { label: 'SELL Signals',  value: '+11,200 ฿', pct: 48, color: '#824199' },
    { label: 'HOLD Signals',  value: '±0 ฿',      pct: 22, color: '#f9d443' },
    { label: 'Stopped Loss',  value: '-3,600 ฿',  pct: 12, color: '#ef4444' },
  ];

  return (
    <div className="bg-white rounded-[24px] p-6 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Gross P&amp;L</h2>
        <span className="text-xs text-[#824199] bg-[#8241991a] px-3 py-1 rounded-full font-medium">Live</span>
      </div>

      <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 mb-5">
        <Search size={14} className="text-gray-400" />
        <input className="bg-transparent text-sm text-gray-500 outline-none flex-1 placeholder-gray-400" placeholder="Filter by asset..." />
      </div>

      <div className="space-y-4">
        {pnlItems.map((item) => (
          <div key={item.label}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm text-gray-700 font-medium">{item.label}</span>
              <span className="text-sm font-semibold text-gray-900">{item.value}</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden bg-gray-100">
              <div className="h-full rounded-full" style={{ width: `${item.pct}%`, background: item.color }} />
            </div>
            <div className="h-1 rounded-full overflow-hidden bg-gray-50 mt-0.5">
              <div className="h-full rounded-full opacity-30" style={{ width: `${item.pct * 0.7}%`, background: item.color }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};