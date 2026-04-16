import React from 'react';
import { ArrowUpRight, ArrowDownRight, Target, ShieldAlert, Zap, User } from 'lucide-react';

export const TradeHistoryTable = () => {
  // เพิ่ม Mockup Data ให้ยาวขึ้นและสมจริงขึ้น
  const history = [
    { id: 'TRD-452', asset: 'XAU/THB', type: 'BUY', entry: 41100, exit: 41450, date: '15 Apr 2026', time: '10:30', pnl: 3500, pnlPercent: 0.85, reason: 'TARGET HIT', icon: <Target size={14}/> },
    { id: 'TRD-451', asset: 'XAU/THB', type: 'SELL', entry: 41600, exit: 41450, date: '14 Apr 2026', time: '22:15', pnl: 1500, pnlPercent: 0.36, reason: 'TREND REVERSAL', icon: <Zap size={14}/> },
    { id: 'TRD-450', asset: 'XAU/THB', type: 'BUY', entry: 41500, exit: 41400, date: '14 Apr 2026', time: '15:20', pnl: -1000, pnlPercent: -0.24, reason: 'STOP LOSS', icon: <ShieldAlert size={14}/> },
    { id: 'TRD-449', asset: 'XAU/THB', type: 'BUY', entry: 41000, exit: 41500, date: '13 Apr 2026', time: '09:45', pnl: 5000, pnlPercent: 1.22, reason: 'MANUAL CLOSE', icon: <User size={14}/> },
    { id: 'TRD-448', asset: 'XAU/THB', type: 'SELL', entry: 41250, exit: 41100, date: '12 Apr 2026', time: '18:10', pnl: 1500, pnlPercent: 0.36, reason: 'TARGET HIT', icon: <Target size={14}/> },
    { id: 'TRD-447', asset: 'XAU/THB', type: 'BUY', entry: 40900, exit: 41200, date: '11 Apr 2026', time: '14:30', pnl: 3000, pnlPercent: 0.73, reason: 'TARGET HIT', icon: <Target size={14}/> },
    { id: 'TRD-446', asset: 'XAU/THB', type: 'SELL', entry: 41400, exit: 41550, date: '10 Apr 2026', time: '11:20', pnl: -1500, pnlPercent: -0.36, reason: 'STOP LOSS', icon: <ShieldAlert size={14}/> },
    { id: 'TRD-445', asset: 'XAU/THB', type: 'BUY', entry: 41150, exit: 41400, date: '09 Apr 2026', time: '16:45', pnl: 2500, pnlPercent: 0.61, reason: 'TREND REVERSAL', icon: <Zap size={14}/> },
    { id: 'TRD-444', asset: 'XAU/THB', type: 'BUY', entry: 40800, exit: 41050, date: '08 Apr 2026', time: '20:15', pnl: 2500, pnlPercent: 0.61, reason: 'TARGET HIT', icon: <Target size={14}/> },
    { id: 'TRD-443', asset: 'XAU/THB', type: 'SELL', entry: 41500, exit: 41300, date: '07 Apr 2026', time: '08:05', pnl: 2000, pnlPercent: 0.48, reason: 'MANUAL CLOSE', icon: <User size={14}/> },
  ];

  return (
    <div className="bg-white rounded-[32px] shadow-sm border border-gray-100 overflow-hidden flex flex-col h-[650px]">
      {/* 🚀 ปรับ h-[650px] เพื่อให้กล่องยาวขึ้นตามต้องการ */}
      
      {/* Table Header */}
      <div className="grid grid-cols-[1.5fr_0.8fr_1.2fr_1.2fr_1.2fr_1fr] bg-gray-50/50 text-[10px] font-bold text-gray-400 uppercase tracking-widest p-6 border-b border-gray-100 shrink-0">
        <span>Trade Details</span>
        <span className="text-center">Side</span>
        <span className="text-right">Entry / Exit</span>
        <span className="text-right">Closed Date</span>
        <span className="text-right">Realized P&L</span>
        <span className="text-right pr-4">Exit Reason</span>
      </div>

      {/* Table Body with Scroll */}
      <div className="divide-y divide-gray-50 overflow-y-auto flex-1 custom-scrollbar">
        {history.map((trade) => (
          <div key={trade.id} className="grid grid-cols-[1.5fr_0.8fr_1.2fr_1.2fr_1.2fr_1fr] items-center p-6 hover:bg-gray-50/40 transition-all group">
            
            {/* Asset Info */}
            <div className="flex items-center gap-4">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110 ${trade.pnl > 0 ? 'bg-emerald-50 text-emerald-500' : 'bg-rose-50 text-rose-500'}`}>
                {trade.pnl > 0 ? <ArrowUpRight size={20} /> : <ArrowDownRight size={20} />}
              </div>
              <div>
                <p className="text-sm font-black text-gray-900">{trade.asset}</p>
                <p className="text-[10px] text-gray-400 font-mono mt-0.5 tracking-tight">{trade.id}</p>
              </div>
            </div>

            {/* Side Badge */}
            <div className="flex justify-center">
              <span className={`text-[10px] font-black px-3 py-1 rounded-md border shadow-sm ${trade.type === 'BUY' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-rose-50 text-rose-600 border-rose-100'}`}>
                {trade.type}
              </span>
            </div>

            {/* Price Info */}
            <div className="text-right">
              <p className="text-sm font-bold text-gray-900">{trade.exit.toLocaleString()}</p>
              <p className="text-[10px] text-gray-400 font-medium mt-1 uppercase tracking-tighter">from {trade.entry.toLocaleString()}</p>
            </div>

            {/* DateTime */}
            <div className="text-right">
              <p className="text-xs font-bold text-gray-800">{trade.date}</p>
              <p className="text-[10px] text-gray-400 font-bold mt-1 uppercase">{trade.time}</p>
            </div>

            {/* P&L Info */}
            <div className="text-right">
              <p className={`text-sm font-black ${trade.pnl > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                {trade.pnl > 0 ? '+' : ''}{trade.pnl.toLocaleString()} <span className="text-[10px]">฿</span>
              </p>
              <p className={`text-[10px] font-bold mt-1 ${trade.pnl > 0 ? 'text-emerald-500/70' : 'text-rose-400/70'}`}>
                {trade.pnlPercent}% Return
              </p>
            </div>

            {/* Exit Reason with Icon */}
            <div className="text-right pr-4">
              <div className="inline-flex items-center gap-1.5 bg-gray-100 px-3 py-1.5 rounded-lg text-[9px] font-bold text-gray-500 uppercase tracking-tighter hover:bg-gray-200 transition-colors cursor-default">
                {trade.icon}
                {trade.reason}
              </div>
            </div>

          </div>
        ))}
      </div>

      {/* Table Footer - สรุปสั้นๆ ท้ายตาราง */}
      <div className="p-4 bg-gray-50/80 border-t border-gray-100 flex justify-center items-center shrink-0">
         <p className="text-[10px] font-bold text-gray-400 uppercase tracking-[0.3em]">End of Records</p>
      </div>
    </div>
  );
};