import React from 'react';
import { Target, Activity, Clock, XCircle, TrendingUp, TrendingDown } from 'lucide-react';

export const PortfolioActivePositions = () => {
  // ข้อมูลจำลองที่สมจริงยิ่งขึ้น
  const positions = [
    { 
      id: 'POS-089', 
      asset: 'XAU/THB', 
      type: 'BUY', 
      size: '10 Baht', 
      entry: 41200, 
      current: 41450, 
      tp: 42000,
      sl: 40800,
      openTime: '15 Apr, 14:20',
      duration: '9h 15m',
      pnl: 2500, 
      pnlPercent: 0.61 
    },
    { 
      id: 'POS-090', 
      asset: 'XAU/THB', 
      type: 'BUY', 
      size: '40 Baht', 
      entry: 41350, 
      current: 41450, 
      tp: 42500,
      sl: 41000,
      openTime: '15 Apr, 21:05',
      duration: '2h 30m',
      pnl: 4000, 
      pnlPercent: 0.24 
    },
    { 
      id: 'POS-092', 
      asset: 'XAU/THB', 
      type: 'SELL', 
      size: '5 Baht', 
      entry: 41550, 
      current: 41450, 
      tp: 41000,
      sl: 41800,
      openTime: '16 Apr, 00:15',
      duration: '15m',
      pnl: 500, 
      pnlPercent: 0.12 
    },
  ];

  return (
    <div className="bg-white rounded-[24px] shadow-sm border border-gray-100 overflow-hidden font-sans h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-50 flex items-center justify-between shrink-0 bg-white z-10">
         <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-500">
               <Activity size={20} />
            </div>
            <div>
               <h3 className="text-sm font-bold text-gray-900">Active Positions</h3>
               <p className="text-[11px] text-gray-400 font-medium">Real-time market exposure</p>
            </div>
         </div>
         <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-full uppercase tracking-wider border border-emerald-100">
            {positions.length} Positions Running
         </span>
      </div>

      {/* Table Columns */}
      <div className="grid grid-cols-[1.5fr_0.6fr_1.2fr_1.2fr_1.2fr_0.8fr] bg-gray-50/50 text-[10px] font-bold text-gray-400 uppercase tracking-wider p-4 border-b border-gray-100 shrink-0">
        <span>Asset & Opening</span>
        <span className="text-center">Side</span>
        <span className="text-right">Size & Entry</span>
        <span className="text-right">TP / SL</span>
        <span className="text-right">Live P&L</span>
        <span className="text-right pr-2">Action</span>
      </div>

      {/* Table Body */}
      <div className="divide-y divide-gray-50 overflow-y-auto flex-1">
        {positions.map((pos) => (
          <div key={pos.id} className="grid grid-cols-[1.5fr_0.6fr_1.2fr_1.2fr_1.2fr_0.8fr] items-center p-4 hover:bg-gray-50/50 transition-all group">
            
            {/* Asset & Time */}
            <div className="flex items-center gap-3">
               <div className={`w-1.5 h-8 rounded-full ${pos.pnl > 0 ? 'bg-emerald-500' : 'bg-rose-500'}`} />
               <div>
                  <p className="text-sm font-black text-gray-900">{pos.asset}</p>
                  <div className="flex items-center gap-1.5 text-[10px] text-gray-400 mt-0.5 font-medium">
                     <Clock size={10} /> {pos.openTime} ({pos.duration})
                  </div>
               </div>
            </div>
            
            {/* Side */}
            <div className="flex justify-center">
              <span className={`text-[10px] font-black px-2.5 py-1 rounded-md border shadow-sm ${
                pos.type === 'BUY' 
                ? 'bg-emerald-50 text-emerald-600 border-emerald-100' 
                : 'bg-rose-50 text-rose-600 border-rose-100'
              }`}>
                {pos.type}
              </span>
            </div>
            
            {/* Size & Entry */}
            <div className="text-right">
              <p className="text-xs font-bold text-gray-900">{pos.size}</p>
              <p className="text-[10px] text-gray-500 font-medium mt-0.5 tracking-tighter">Entry: {pos.entry.toLocaleString()}</p>
            </div>

            {/* TP / SL */}
            <div className="text-right">
              <p className="text-[10px] font-bold text-emerald-600 tracking-tighter">TP: {pos.tp.toLocaleString()}</p>
              <p className="text-[10px] font-bold text-rose-400 tracking-tighter mt-0.5">SL: {pos.sl.toLocaleString()}</p>
            </div>

            {/* Live P&L */}
            <div className="text-right">
              <div className={`flex items-center justify-end gap-1 text-sm font-black ${pos.pnl > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                 {pos.pnl > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                 {pos.pnl > 0 ? '+' : ''}{pos.pnl.toLocaleString()} ฿
              </div>
              <p className={`text-[10px] font-bold mt-0.5 ${pos.pnl > 0 ? 'text-emerald-500/70' : 'text-rose-400/70'}`}>
                 {pos.pnlPercent}% Return
              </p>
            </div>

            {/* Action */}
            <div className="text-right pr-2">
               <button className="p-2 text-gray-300 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-colors group-hover:scale-110 active:scale-95">
                  <XCircle size={18} />
               </button>
            </div>
          </div>
        ))}
      </div>

      {/* Footer Summary Bar */}
      <div className="px-6 py-3 bg-gray-50/80 border-t border-gray-100 flex justify-between items-center shrink-0">
         <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Total Floating P&L</p>
         <p className="text-sm font-black text-emerald-600">+7,000 ฿</p>
      </div>
    </div>
  );
};