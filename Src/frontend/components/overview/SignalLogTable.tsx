import React, { useState } from 'react';
import { Download } from 'lucide-react';

type SignalType = 'BUY' | 'HOLD' | 'SELL';

// Sub-component สำหรับวาดป้ายกำกับสถานะ (Pill)
const SignalPill = ({ signal }: { signal: SignalType }) => {
  const styles: Record<SignalType, string> = {
    BUY:  'bg-emerald-100 text-emerald-700',
    HOLD: 'bg-amber-100 text-amber-700',
    SELL: 'bg-red-100 text-red-700',
  };
  return (
    <span className={`text-xs font-bold px-3 py-1 rounded-full ${styles[signal]}`}>
      {signal}
    </span>
  );
};

export const SignalLogTable = () => {
  const [logFilter, setLogFilter] = useState<'Weekly' | 'Monthly'>('Weekly');

  const signalLogs = [
    { date: '14 Apr 2026', signalId: 'SIG_...A7Kx', asset: 'Thai Gold 96.5%', confidence: 85, entryPrice: '72,000 ฿', signal: 'BUY' as SignalType,  pnl: '+3,600 ฿', positive: true  },
    { date: '12 Apr 2026', signalId: 'SIG_...B3Nv', asset: 'Thai Gold 96.5%', confidence: 78, entryPrice: '71,200 ฿', signal: 'SELL' as SignalType, pnl: '+1,440 ฿', positive: true  },
    { date: '10 Apr 2026', signalId: 'SIG_...C9Lp', asset: 'Thai Gold 96.5%', confidence: 62, entryPrice: '70,800 ฿', signal: 'HOLD' as SignalType, pnl: '–',          positive: false },
    { date: '08 Apr 2026', signalId: 'SIG_...D2Ym', asset: 'Thai Gold 96.5%', confidence: 91, entryPrice: '69,500 ฿', signal: 'BUY' as SignalType,  pnl: '+5,200 ฿', positive: true  },
  ];

  return (
    <div className="bg-white rounded-[24px] p-6 shadow-[0_4px_20px_rgba(0,0,0,0.04)]">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-gray-900">Signal Log</h2>
        <div className="flex items-center gap-2">
          {(['Weekly', 'Monthly'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setLogFilter(f)}
              className={`px-4 py-1.5 text-sm rounded-full transition-all ${
                logFilter === f ? 'bg-gray-900 text-white font-medium' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              {f}
            </button>
          ))}
          <button className="flex items-center gap-1.5 text-sm text-gray-600 border border-gray-200 rounded-full px-4 py-1.5 hover:bg-gray-50 transition">
            <Download size={14} />
            Export CSV
          </button>
        </div>
      </div>

      {/* Table header */}
      <div className="grid grid-cols-7 text-xs text-gray-400 font-medium pb-2 border-b border-gray-100 mb-2">
        <span>Date</span>
        <span>Signal ID</span>
        <span>Asset</span>
        <span>Entry Price</span>
        <span>Signal</span>
        <span>Confidence</span>
        <span>P&amp;L</span>
      </div>

      {/* Rows */}
      <div className="divide-y divide-gray-50">
        {signalLogs.map((row, i) => (
          <div key={i} className="grid grid-cols-7 text-sm text-gray-700 py-3.5 items-center hover:bg-gray-50/50 transition-colors rounded-lg">
            <span className="text-gray-500">{row.date}</span>
            <span className="font-mono text-gray-400 text-xs">{row.signalId}</span>
            <span className="font-medium text-gray-800">{row.asset}</span>
            <span className="font-semibold text-gray-900">{row.entryPrice}</span>
            <span><SignalPill signal={row.signal} /></span>
            <span>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 rounded-full bg-gray-100 max-w-[80px]">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${row.confidence}%`,
                      background: 'linear-gradient(90deg, #824199, #a855f7)',
                    }}
                  />
                </div>
                <span className="text-xs font-semibold text-[#824199]">{row.confidence}%</span>
              </div>
            </span>
            <span className={`font-semibold ${row.positive ? 'text-emerald-600' : 'text-gray-400'}`}>
              {row.pnl}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};