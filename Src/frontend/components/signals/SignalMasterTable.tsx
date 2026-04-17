import React, { useState } from 'react';
import { Brain, Search, Database, Zap, ChevronDown, ChevronUp, Clock } from 'lucide-react';

export const SignalMasterTable = ({ signals }: any) => {
  // เก็บ ID ของแถวที่กำลังเปิด Trace อยู่
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const toggleTrace = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="bg-white rounded-[32px] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-100 overflow-hidden font-sans">

      {/* Header */}
      <div className="grid grid-cols-[0.4fr_1fr_0.5fr_0.8fr_3.2fr_1.2fr] bg-gray-50/80 text-[10px] font-black text-gray-400 uppercase tracking-widest p-5 border-b border-gray-100 items-center">
        <input type="checkbox" className="rounded-md border-gray-300 text-[#824199]" />
        <span>Date & ID</span>
        <span className="text-center">TF</span>
        <span className="text-center">Action</span>
        <span className="pl-2">AI Analysis & Technicals</span>
        <span className="text-right">Intelligence Trace</span>
      </div>

      <div className="divide-y divide-gray-50/80">
        {signals.map((sig: any) => (
          <React.Fragment key={sig.id}>
            {/* Main Row */}
            <div className={`grid grid-cols-[0.4fr_1fr_0.5fr_0.8fr_3.2fr_1.2fr] items-center p-5 transition-all ${expandedId === sig.id ? 'bg-purple-50/30' : 'hover:bg-gray-50/50'}`}>

              <input type="checkbox" className="rounded-md border-gray-300 text-[#824199]" />

              <div>
                <p className="text-[13px] font-bold text-gray-900 flex items-center gap-1.5">
                  <Clock size={12} className="text-gray-400" /> {sig.date}
                </p>
                <p className="text-[10px] text-gray-400 font-mono">#{sig.id}</p>
              </div>

              <div className="flex justify-center">
                <span className="bg-white text-gray-500 text-[10px] font-bold px-2.5 py-1 rounded-lg border border-gray-100 shadow-sm">{sig.tf}</span>
              </div>

              <div className="flex justify-center">
                <span className={`text-[10px] font-black px-3 py-1.5 rounded-full border tracking-widest ${sig.signal === 'BUY' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                    sig.signal === 'SELL' ? 'bg-rose-50 text-rose-600 border-rose-100' : 'bg-amber-50 text-amber-600 border-amber-100'
                  }`}>
                  {sig.signal}
                </span>
              </div>

              <div className="pl-2 pr-6">
                <p className="text-xs text-gray-700 font-medium line-clamp-1 mb-2">"{sig.rationale}"</p>
                <div className="flex flex-wrap gap-2">
                  <span className="text-[9px] font-bold bg-purple-50 text-[#824199] px-2 py-0.5 rounded-md border border-purple-100">CONFIDENCE: {sig.confidence}%</span>
                  <span className="text-[9px] font-bold bg-blue-50 text-blue-600 px-2 py-0.5 rounded-md border border-blue-100">RSI: 42.5</span>
                </div>
              </div>

              {/* ปุ่มกดเปิด Trace ใต้แถว */}
              <div className="text-right">
                <button
                  onClick={() => toggleTrace(sig.id)}
                  className={`inline-flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest transition-all px-4 py-2 rounded-xl border ${expandedId === sig.id
                      ? 'bg-[#824199] text-white border-[#824199] shadow-lg shadow-purple-200'
                      : 'text-gray-400 hover:text-[#824199] border-transparent'
                    }`}
                >
                  {expandedId === sig.id ? 'Close Trace' : 'View Trace'}
                  {expandedId === sig.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>
            </div>

            {/* 🟢 Sub-column (Trace Log) ที่กางออกมาใต้แถวที่กด */}
            {expandedId === sig.id && (
              <div className="bg-gray-100/60 border-x-4 border-[#824199]/20 shadow-inner animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="p-8 grid grid-cols-12 gap-8">

                  {/* ฝั่งซ้าย: Rationale (ปรับให้สีเข้มขึ้นเพื่อให้ตัดกับพื้นหลังใหม่) */}
                  <div className="col-span-4">
                    <div className="bg-[#13071a] p-6 rounded-[24px] text-white relative overflow-hidden h-full shadow-lg">
                      <Brain className="absolute -right-4 -bottom-4 opacity-10" size={80} />
                      <p className="text-[10px] font-bold text-purple-300 uppercase tracking-[0.2em] mb-3">Final Agent Rationale</p>
                      <p className="text-sm italic font-medium leading-relaxed relative z-10">"{sig.rationale}"</p>
                    </div>
                  </div>

                  {/* ฝั่งขวา: Execution Steps */}
                  <div className="col-span-8 space-y-5">
                    <h4 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] mb-2">Execution Steps</h4>
                    <TraceItem icon={<Brain size={14} />} title="Thought" desc="Analyzing current trend and volume support." />
                    <TraceItem icon={<Search size={14} />} title="Action" desc="Fetching technical data from Binance & TradingView." />
                    <TraceItem icon={<Database size={14} />} title="Observation" desc="Strong support found at 41,000 THB. MACD shows divergence." />
                    <TraceItem icon={<Zap size={14} className="text-emerald-500" />} title="Decision" desc={`Generate ${sig.signal} Signal with ${sig.confidence}% confidence.`} isLast />
                  </div>

                </div>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
};

const TraceItem = ({ icon, title, desc, isLast }: any) => (
  <div className="flex gap-4">
    <div className="flex flex-col items-center">
      <div className="w-7 h-7 rounded-full bg-white border border-gray-100 shadow-sm flex items-center justify-center text-gray-400 z-10">
        {icon}
      </div>
      {!isLast && <div className="w-0.5 h-full bg-gray-100 -mt-1 mb-1" />}
    </div>
    <div className="pb-4">
      <h5 className="text-[10px] font-black text-gray-900 uppercase tracking-tighter">{title}</h5>
      <p className="text-[11px] text-gray-500 font-medium">{desc}</p>
    </div>
  </div>
);