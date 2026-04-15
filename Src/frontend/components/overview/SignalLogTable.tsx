import React, { useState } from 'react';
import { Crosshair, ShieldX, Clock } from 'lucide-react';

type SignalType = 'BUY' | 'HOLD' | 'SELL';

const SignalPill = ({ signal }: { signal: SignalType }) => {
  const styles: Record<SignalType, string> = {
    BUY:  'bg-emerald-100/80 text-emerald-700 border-emerald-200',
    HOLD: 'bg-amber-100/80 text-amber-700 border-amber-200',
    SELL: 'bg-rose-100/80 text-rose-700 border-rose-200',
  };
  return (
    <span className={`text-[11px] font-black px-3 py-1 rounded-full border tracking-wider ${styles[signal]}`}>
      {signal}
    </span>
  );
};

export const SignalLogTable = () => {
  const [logFilter, setLogFilter] = useState<'Recent' | 'All'>('Recent');

  const signalLogs = [
    { date: '15 Apr 14:00', tf: '4H', entryPrice: 2450.50, tp: 2480.00, sl: 2435.00, signal: 'BUY' as SignalType,  confidence: 85, pnl: '+3,600 ฿', status: 'won'  },
    { date: '14 Apr 09:30', tf: '1H', entryPrice: 2465.20, tp: 2450.00, sl: 2475.00, signal: 'SELL' as SignalType, confidence: 78, pnl: '+1,440 ฿', status: 'won'  },
    { date: '13 Apr 11:00', tf: '4H', entryPrice: 2440.00, tp: null,    sl: null,    signal: 'HOLD' as SignalType, confidence: 62, pnl: '–',          status: 'pending' },
    { date: '12 Apr 16:15', tf: '1D', entryPrice: 2420.80, tp: 2460.00, sl: 2400.00, signal: 'BUY' as SignalType,  confidence: 91, pnl: '-1,200 ฿', status: 'lost'  },
  ];

  return (
    <div className="bg-white rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-50 mt-4 font-sans">
      <div className="flex items-center justify-between mb-6">
        <div>
           <h2 className="text-lg font-bold text-gray-900 tracking-tight">Intelligence History</h2>
           <p className="text-xs text-gray-400 mt-0.5">Track record of recent agent decisions</p>
        </div>
        
        <div className="bg-gray-50 p-1 rounded-xl border border-gray-100 flex items-center">
          {(['Recent', 'All'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setLogFilter(f)}
              className={`px-4 py-1.5 text-xs rounded-lg transition-all font-bold ${
                logFilter === f ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Table Header - แบ่งเป็น 7 ส่วนเท่าๆ กัน */}
      <div className="grid grid-cols-7 text-[11px] text-gray-400 font-bold uppercase tracking-wider pb-3 border-b border-gray-100 mb-3">
        <span className="col-span-1">Date & Time</span>
        <span className="col-span-1 text-center">TF</span>
        <span className="col-span-1 text-center">Action</span>
        <span className="col-span-2 text-center">Price Targets (THB/g)</span>
        <span className="col-span-1 text-center">Confidence</span>
        <span className="col-span-1 text-right pr-4">Est. P&L</span>
      </div>

      {/* Table Rows */}
      <div className="divide-y divide-gray-50/50">
        {signalLogs.map((row, i) => (
          <div key={i} className="grid grid-cols-7 text-sm py-4 items-center hover:bg-gray-50/50 transition-colors rounded-xl px-2 -mx-2">
            
            {/* Date */}
            <span className="col-span-1 text-gray-500 font-medium text-xs flex items-center gap-2">
               <Clock size={12} className="text-gray-300" />
               {row.date}
            </span>
            
            {/* Timeframe - จัดให้อยู่ตรงกลางคอลัมน์ */}
            <div className="col-span-1 flex justify-center">
                <span className="font-mono text-gray-500 text-xs bg-gray-100 px-2 py-0.5 rounded-md">
                   {row.tf}
                </span>
            </div>
            
            {/* Signal - จัดให้อยู่ตรงกลางคอลัมน์ */}
            <div className="col-span-1 flex justify-center">
                <SignalPill signal={row.signal} />
            </div>
            
            {/* Price Targets - กินพื้นที่ 2 คอลัมน์ และจัดให้อยู่ตรงกลาง */}
            <div className="col-span-2 flex flex-col items-center gap-1">
               <div className="flex items-center gap-2 text-sm font-black text-gray-900">
                  {row.entryPrice.toLocaleString('en-US', { minimumFractionDigits: 2 })} <span className="text-[10px] text-gray-400 font-bold">ENTRY</span>
               </div>
               {row.signal !== 'HOLD' && (
                  <div className="flex items-center justify-center gap-3 text-[10px] font-bold">
                     <span className="flex items-center gap-1 text-emerald-600"><Crosshair size={10}/> {row.tp?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                     <span className="flex items-center gap-1 text-rose-500"><ShieldX size={10}/> {row.sl?.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                  </div>
               )}
            </div>
            
            {/* Confidence Bar - จัดให้อยู่ตรงกลางคอลัมน์ */}
            <div className="col-span-1 flex justify-center items-center gap-3">
                <div className="w-16 xl:w-20 h-2 bg-gray-100 rounded-full overflow-hidden shadow-inner flex-shrink-0">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[#824199] to-[#c084fc]"
                    style={{ width: `${row.confidence}%` }}
                  />
                </div>
                <span className="text-[11px] font-black text-gray-700 w-8">{row.confidence}%</span>
            </div>
            
            {/* P&L */}
            <span className={`col-span-1 text-right pr-2 font-black text-sm ${row.status === 'won' ? 'text-emerald-500' : row.status === 'lost' ? 'text-rose-500' : 'text-gray-400'}`}>
              {row.pnl}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};