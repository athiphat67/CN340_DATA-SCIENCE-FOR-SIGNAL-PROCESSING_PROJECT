import React from 'react';
import { Target, Activity, Clock, XCircle, TrendingUp, TrendingDown } from 'lucide-react';

export const PortfolioActivePositions = () => {
  // มั่นใจว่าชื่อตัวแปรคือ positions เพื่อให้เงื่อนไขด้านล่างทำงาน
  const positions = [
    { id: 'POS-089', asset: 'XAU/THB', type: 'BUY', size: '10 Baht', entry: 41200, current: 41450, tp: 42000, sl: 40800, openTime: '15 Apr, 14:20', duration: '9h 15m', pnl: 2500, pnlPercent: 0.61 },
    { id: 'POS-090', asset: 'XAU/THB', type: 'BUY', size: '40 Baht', entry: 41350, current: 41450, tp: 42500, sl: 41000, openTime: '15 Apr, 21:05', duration: '2h 30m', pnl: 4000, pnlPercent: 0.24 },
    { id: 'POS-092', asset: 'XAU/THB', type: 'SELL', size: '5 Baht', entry: 41550, current: 41450, tp: 41000, sl: 41800, openTime: '16 Apr, 00:15', duration: '15m', pnl: 500, pnlPercent: 0.12 },
  ];

  return (
    <div className="bg-white rounded-[24px] shadow-sm border border-gray-100 overflow-hidden font-sans flex flex-col h-[480px]">
      {/* 1. กำหนด h-[480px] ตายตัวเพื่อให้สูงพอดีกับกล่องด้านข้าง */}
      
      <div className="p-5 border-b border-gray-50 flex items-center justify-between shrink-0 bg-white">
         <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-500">
               <Activity size={20} />
            </div>
            <div>
               <h3 className="text-sm font-bold text-gray-900">Active Positions</h3>
               <p className="text-[11px] text-gray-400 font-medium tracking-tight">Current market exposure</p>
            </div>
         </div>
         <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-3 py-1.5 rounded-full uppercase tracking-wider border border-emerald-100">
            {positions.length} Running
         </span>
      </div>

      {/* Columns Header - ปรับช่องให้กระชับขึ้น */}
      <div className="grid grid-cols-[1.2fr_0.5fr_1fr_1fr_1fr_0.5fr] bg-gray-50/50 text-[10px] font-bold text-gray-400 uppercase tracking-wider p-4 border-b border-gray-100 shrink-0">
        <span>Asset</span>
        <span className="text-center">Side</span>
        <span className="text-right">Size/Entry</span>
        <span className="text-right">Target</span>
        <span className="text-right">P&L</span>
        <span className="text-right pr-2"></span>
      </div>

      <div className="divide-y divide-gray-50 overflow-y-auto flex-1">
        {positions.length > 0 ? (
          positions.map((pos) => (
            <div key={pos.id} className="grid grid-cols-[1.2fr_0.5fr_1fr_1fr_1fr_0.5fr] items-center p-4 hover:bg-gray-50/50 transition-all">
               <div className="flex items-center gap-2">
                  <div className={`w-1 h-6 rounded-full ${pos.pnl > 0 ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                  <div>
                     <p className="text-xs font-black text-gray-900">{pos.asset}</p>
                     <p className="text-[9px] text-gray-400 font-medium">{pos.openTime}</p>
                  </div>
               </div>
               <div className="flex justify-center">
                  <span className={`text-[9px] font-black px-2 py-0.5 rounded-md border ${pos.type === 'BUY' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-rose-50 text-rose-600 border-rose-100'}`}>
                     {pos.type}
                  </span>
               </div>
               <div className="text-right">
                  <p className="text-[11px] font-bold text-gray-900">{pos.size}</p>
                  <p className="text-[9px] text-gray-500 font-medium">@{pos.entry.toLocaleString()}</p>
               </div>
               <div className="text-right">
                  <p className="text-[9px] font-bold text-emerald-600">TP: {pos.tp.toLocaleString()}</p>
                  <p className="text-[9px] font-bold text-rose-400 mt-0.5">SL: {pos.sl.toLocaleString()}</p>
               </div>
               <div className="text-right">
                  <div className={`flex items-center justify-end gap-1 text-[13px] font-black ${pos.pnl > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                     {pos.pnl > 0 ? '+' : ''}{pos.pnl.toLocaleString()}
                  </div>
                  <p className={`text-[9px] font-bold ${pos.pnl > 0 ? 'text-emerald-500/70' : 'text-rose-400/70'}`}>
                     {pos.pnlPercent}%
                  </p>
               </div>
               <div className="text-right pr-2">
                  <button className="text-gray-300 hover:text-rose-500"><XCircle size={16} /></button>
               </div>
            </div>
          ))
        ) : (
          <div className="h-full flex flex-col items-center justify-center py-20 opacity-40">
             <Activity size={40} className="text-gray-300 mb-2" />
             <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest text-center">No Active Positions<br/><span className="lowercase font-medium">Monitoring market...</span></p>
          </div>
        )}
      </div>

      <div className="px-6 py-3 bg-gray-50/80 border-t border-gray-100 flex justify-between items-center shrink-0">
         <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Total Unrealized</p>
         <p className="text-sm font-black text-emerald-600">+7,000 ฿</p>
      </div>
    </div>
  );
};