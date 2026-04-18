import React, { useState } from 'react';
import { TradeRecord } from '../../../types/history';
import {
  ArrowUpRight, ArrowDownRight, ChevronDown, ChevronUp, Brain, Database, Activity, Globe, BarChart, Zap
} from 'lucide-react';

interface Props {
  trades: TradeRecord[];
}

export const TradeHistoryTable: React.FC<Props> = ({ trades }) => {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const toggleRow = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (trades.length === 0) {
    return (
      <div className="bg-white rounded-[32px] shadow-sm border border-gray-100 flex items-center justify-center h-[400px]">
        <p className="text-sm font-bold text-gray-400 uppercase tracking-widest">No trade records found</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-[32px] shadow-sm border border-gray-100 overflow-hidden flex flex-col h-[700px] font-sans">
      <div className="grid grid-cols-[1.5fr_0.8fr_1fr_1fr_1fr_1fr] bg-gray-50/80 text-[10px] font-black text-gray-400 uppercase tracking-widest p-6 border-b border-gray-100 shrink-0">
        <span>Execution ID & Asset</span>
        <span className="text-center">Action Side</span>
        <span className="text-right">Execution Price</span>
        <span className="text-right">Timestamp</span>
        <span className="text-right">Realized P&L</span>
        <span className="text-right">Archive Trace</span>
      </div>

      <div className="divide-y divide-gray-50 overflow-y-auto flex-1 custom-scrollbar">
        {trades.map((trade) => (
          <React.Fragment key={trade.id}>
            <div
              onClick={() => toggleRow(trade.id)}
              className={`grid grid-cols-[1.5fr_0.8fr_1fr_1fr_1fr_1fr] items-center p-6 transition-all cursor-pointer ${expandedId === trade.id ? 'bg-purple-50/30' : 'hover:bg-gray-50/40'}`}
            >
              <div className="flex items-center gap-4">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${trade.pnl_thb !== null && trade.pnl_thb > 0 ? 'bg-emerald-50 text-emerald-500' : trade.pnl_thb !== null && trade.pnl_thb < 0 ? 'bg-rose-50 text-rose-500' : 'bg-blue-50 text-blue-500'}`}>
                  {trade.action === 'SELL' ? (trade.pnl_thb! > 0 ? <ArrowUpRight size={20} /> : <ArrowDownRight size={20} />) : <ArrowDownRight size={20} />}
                </div>
                <div>
                  <p className="text-sm font-black text-gray-900">XAU/THB</p>
                  <p className="text-[10px] text-gray-400 font-mono tracking-tighter">#TXN-{trade.id}</p>
                </div>
              </div>

              <div className="flex justify-center">
                <span className={`text-[10px] font-black px-3 py-1 rounded-md border shadow-sm ${trade.action === 'BUY' ? 'bg-blue-50 text-blue-600 border-blue-100' : 'bg-emerald-50 text-emerald-600 border-emerald-100'}`}>
                  {trade.action}
                </span>
              </div>

              <div className="text-right">
                <p className="text-xs font-bold text-gray-900">{trade.price_thb.toLocaleString()} ฿</p>
                <p className="text-[10px] text-gray-400 font-medium">{trade.gold_grams.toFixed(2)} grams</p>
              </div>

              <div className="text-right">
                <p className="text-xs font-bold text-gray-800">{trade.executed_at.split(' ')[0]}</p>
                <p className="text-[10px] text-gray-400 font-bold uppercase">{trade.executed_at.split(' ')[1]}</p>
              </div>

              <div className="text-right relative">
                {trade.pnl_thb !== null ? (
                  <>
                    <div className={`absolute right-[-8px] top-1/2 -translate-y-1/2 w-1 h-8 rounded-full ${trade.pnl_thb > 0 ? 'bg-emerald-400/30' : 'bg-rose-400/30'}`} />
                    <p className={`text-sm font-black ${trade.pnl_thb > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                      {trade.pnl_thb > 0 ? '+' : ''}{trade.pnl_thb.toLocaleString()} ฿
                    </p>
                    <p className={`text-[10px] font-bold mt-0.5 ${trade.pnl_thb > 0 ? 'text-emerald-500/70' : 'text-rose-400/70'}`}>
                      {(trade.pnl_pct! * 100).toFixed(2)}% Return
                    </p>
                  </>
                ) : (
                  <p className="text-[10px] font-bold text-gray-400 uppercase mt-2">Position Open</p>
                )}
              </div>

              <div className="text-right">
                <button className={`inline-flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest transition-all px-3 py-2 rounded-xl border ${expandedId === trade.id ? 'bg-[#824199] text-white border-[#824199]' : 'text-gray-400 border-transparent hover:text-[#824199]'}`}>
                  {expandedId === trade.id ? 'Close Trace' : 'View Record'}
                  {expandedId === trade.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>
            </div>

            {expandedId === trade.id && (
              <div className="bg-gray-50/80 border-x-4 border-[#824199]/10 shadow-inner overflow-hidden">
                <div className="p-8 grid grid-cols-12 gap-10 items-stretch">
                  <div className="col-span-12 lg:col-span-5">
                    <div className="bg-[#0f0514] p-8 rounded-[32px] text-white shadow-2xl relative h-full flex flex-col justify-between border border-white/5">
                      <Brain className="absolute -right-6 -bottom-6 opacity-[0.03] text-purple-400" size={120} />
                      <div className="relative z-10">
                        <div className="flex items-center gap-2 mb-6">
                          <div className="w-1.5 h-5 bg-[#f9d443] rounded-full shadow-[0_0_12px_rgba(249,212,67,0.4)]" />
                          <p className="text-[11px] font-black text-purple-200 uppercase tracking-[0.25em]">Recommended Signal Rationale</p>
                        </div>
                        <p className="text-[16px] leading-[1.8] font-medium text-white/90 italic tracking-wide">
                          "{trade.rationale}"
                        </p>
                      </div>
                      <div className="relative z-10 mt-10 pt-6 border-t border-white/10 grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-[9px] text-purple-400 font-bold uppercase tracking-widest mb-1">Signal Confidence</p>
                          <p className="text-xl font-black text-[#f9d443]">{(trade.confidence * 100).toFixed(0)}%</p>
                        </div>
                        <div className="border-l border-white/10 pl-4">
                          <p className="text-[9px] text-purple-400 font-bold uppercase tracking-widest mb-1">Analysis Provider</p>
                          <p className="text-sm font-black text-white uppercase truncate">{trade.provider}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="col-span-12 lg:col-span-7 flex flex-col">
                    <div className="flex items-center justify-between mb-6">
                      <div className="flex items-center gap-2">
                        <Activity size={14} className="text-[#824199]" />
                        <h4 className="text-[11px] font-black text-gray-500 uppercase tracking-[0.2em]">Archived Market Snapshot</h4>
                      </div>
                      <span className="text-[9px] font-bold text-gray-400 bg-gray-100 px-2 py-1 rounded-md">HISTORY STATE</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
                      <LogCard icon={<BarChart size={14} />} label="Technical Snapshot" desc={`RSI: ${trade.rsi} | MACD Line: ${trade.macd_line}. Trend was flagged as ${trade.trend}.`} />
                      <LogCard icon={<Globe size={14} />} label="Global Context" desc={`Gold USD: $${trade.gold_usd.toLocaleString()}/oz. Market Quality: ${trade.is_weekend ? 'Weekend' : trade.data_quality}.`} />
                      <LogCard icon={<Zap size={14} />} label="Signal Generation Trace" desc={`Agent analyzed data using ${trade.tool_calls_used} tools across ${trade.iterations_used} iterations.`} />
                      <LogCard icon={<Database size={14} className={trade.pnl_thb !== null ? 'text-emerald-500' : 'text-blue-500'} />} label="Record Status" desc={`[${trade.note}] - Trade #${trade.id} linked securely to run_id ${trade.run_id || 'N/A'}.`} />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      <div className="p-4 bg-gray-50/80 border-t border-gray-100 flex justify-center shrink-0">
        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-[0.3em]">End of Archive Records</p>
      </div>
    </div>
  );
};

const LogCard = ({ icon, label, desc }: any) => (
  <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex flex-col gap-3 group hover:border-[#824199]/20 transition-all">
    <div className="flex items-center gap-2">
      <div className="p-2 bg-gray-50 rounded-xl text-gray-400 group-hover:text-[#824199] group-hover:bg-purple-50 transition-colors">
        {icon}
      </div>
      <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">{label}</span>
    </div>
    <p className="text-xs text-gray-600 font-medium leading-relaxed">{desc}</p>
  </div>
);