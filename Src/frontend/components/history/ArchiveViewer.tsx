// src/components/history/ArchiveViewer.tsx
import React, { useState } from 'react';
import { TradeRecord, SignalRecord, LogRecord } from '../../../types/archive';
import {
  ArrowUpRight, ArrowDownRight, Brain, Database, Activity, Target, Zap, Clock, Code, TerminalSquare, AlertCircle
} from 'lucide-react';

interface Props {
  trades: TradeRecord[];
  signals: SignalRecord[];
  logs: LogRecord[];
}

export const ArchiveViewer: React.FC<Props> = ({ trades, signals, logs }) => {
  const [activeTab, setActiveTab] = useState<'TRADES' | 'SIGNALS' | 'LOGS'>('TRADES');

  return (
    <div className="bg-white rounded-[32px] shadow-sm border border-gray-100 overflow-hidden flex flex-col h-[750px] font-sans">
      
      {/* 🟢 Navigation Tabs */}
      <div className="flex items-center gap-2 p-4 border-b border-gray-100 bg-gray-50/50">
        <TabButton active={activeTab === 'TRADES'} onClick={() => setActiveTab('TRADES')} icon={<Activity size={16} />} label="User Executed Trades" count={trades.length} color="emerald" />
        <TabButton active={activeTab === 'SIGNALS'} onClick={() => setActiveTab('SIGNALS')} icon={<Brain size={16} />} label="AI Signal Records" count={signals.length} color="purple" />
        <TabButton active={activeTab === 'LOGS'} onClick={() => setActiveTab('LOGS')} icon={<TerminalSquare size={16} />} label="System Event Logs" count={logs.length} color="blue" />
      </div>

      {/* 🟢 Content Area */}
      <div className="overflow-y-auto flex-1 custom-scrollbar bg-white">
        
        {/* --- View: User Trades (trade_log) --- */}
        {activeTab === 'TRADES' && (
          <div className="divide-y divide-gray-50">
            <div className="grid grid-cols-[1.5fr_1fr_1fr_1fr_1.5fr] bg-gray-50/80 text-[10px] font-black text-gray-400 uppercase tracking-widest p-6 shrink-0 sticky top-0 backdrop-blur-md">
              <span>Trade Asset & ID</span>
              <span className="text-center">Executed Side</span>
              <span className="text-right">Exec. Price (THB)</span>
              <span className="text-right">Timestamp</span>
              <span className="text-right">Realized P&L</span>
            </div>
            {trades.map((trade) => (
              <div key={trade.id} className="grid grid-cols-[1.5fr_1fr_1fr_1fr_1.5fr] items-center p-6 hover:bg-gray-50/40 transition-all group">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${trade.pnl_thb !== null && trade.pnl_thb > 0 ? 'bg-emerald-50 text-emerald-500' : 'bg-rose-50 text-rose-500'}`}>
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
                  <p className="text-[10px] text-gray-400 font-medium">{trade.gold_grams.toFixed(2)} g</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-bold text-gray-800">{trade.executed_at.split(' ')[0]}</p>
                  <p className="text-[10px] text-gray-400 font-bold uppercase">{trade.executed_at.split(' ')[1]}</p>
                </div>
                <div className="text-right">
                  {trade.pnl_thb !== null ? (
                    <>
                      <p className={`text-sm font-black ${trade.pnl_thb > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                        {trade.pnl_thb > 0 ? '+' : ''}{trade.pnl_thb.toLocaleString()} ฿
                      </p>
                      <p className={`text-[10px] font-bold mt-0.5 ${trade.pnl_thb > 0 ? 'text-emerald-500/70' : 'text-rose-400/70'}`}>
                        {(trade.pnl_pct! * 100).toFixed(2)}% Return
                      </p>
                    </>
                  ) : <p className="text-[10px] font-bold text-gray-400 uppercase">Holding</p>}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* --- View: AI Signals (runs) --- */}
        {activeTab === 'SIGNALS' && (
          <div className="divide-y divide-gray-50">
            <div className="grid grid-cols-[1.5fr_1fr_1.5fr_1fr_1.5fr] bg-gray-50/80 text-[10px] font-black text-gray-400 uppercase tracking-widest p-6 shrink-0 sticky top-0 backdrop-blur-md">
              <span>Analysis ID & Time</span>
              <span className="text-center">Recommended</span>
              <span className="text-center">Target Entry</span>
              <span className="text-center">Confidence</span>
              <span className="text-right">Trend Analysis</span>
            </div>
            {signals.map((sig) => (
              <div key={sig.id} className="grid grid-cols-[1.5fr_1fr_1.5fr_1fr_1.5fr] items-center p-6 hover:bg-purple-50/20 transition-all">
                 <div>
                    <p className="text-xs font-bold text-gray-900">{sig.run_at}</p>
                    <p className="text-[10px] text-gray-400 font-mono mt-0.5">RUN_ID: {sig.id}</p>
                 </div>
                 <div className="flex justify-center">
                    <span className={`text-[10px] font-black px-3 py-1 rounded-md border ${sig.signal === 'BUY' ? 'bg-blue-50 text-blue-600 border-blue-200' : sig.signal === 'SELL' ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 'bg-gray-100 text-gray-500 border-gray-200'}`}>
                      {sig.signal} SIGNAL
                    </span>
                 </div>
                 <div className="text-center">
                    <p className="text-xs font-bold text-gray-800">{sig.entry_price.toLocaleString()} ฿</p>
                    <p className="text-[9px] font-bold text-gray-400 mt-0.5">SL: {sig.stop_loss} | TP: {sig.take_profit}</p>
                 </div>
                 <div className="text-center">
                    <p className="text-sm font-black text-[#824199]">{(sig.confidence * 100).toFixed(0)}%</p>
                 </div>
                 <div className="text-right">
                    <p className="text-xs text-gray-600 font-medium truncate max-w-[200px] ml-auto">{sig.rationale}</p>
                 </div>
              </div>
            ))}
          </div>
        )}

        {/* --- View: System Logs (llm_logs) --- */}
        {activeTab === 'LOGS' && (
          <div className="divide-y divide-gray-50 p-6 space-y-4 bg-gray-50/30">
            {logs.map((log) => (
              <div key={log.id} className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex flex-col gap-3">
                 <div className="flex items-center justify-between border-b border-gray-50 pb-3">
                    <div className="flex items-center gap-3">
                       <Code size={16} className="text-gray-400" />
                       <span className={`text-[10px] font-black px-2 py-1 rounded uppercase tracking-widest ${log.step_type === 'THOUGHT_FINAL' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>
                         {log.step_type}
                       </span>
                    </div>
                    <div className="flex items-center gap-4 text-[10px] font-bold text-gray-400">
                       <span className="flex items-center gap-1"><Clock size={12} /> {log.elapsed_ms}ms</span>
                       <span className="flex items-center gap-1"><Database size={12} /> {log.token_total} tokens</span>
                       <span>{log.logged_at}</span>
                    </div>
                 </div>
                 <p className="text-xs text-gray-700 font-mono leading-relaxed bg-gray-50 p-3 rounded-lg border border-gray-100">
                    {log.trace_preview}
                 </p>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
};

// 🟢 Component ปุ่ม Tab
const TabButton = ({ active, onClick, icon, label, count, color }: any) => {
  const colorMap: Record<string, string> = {
    emerald: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    purple: 'text-[#824199] bg-purple-50 border-purple-200',
    blue: 'text-blue-700 bg-blue-50 border-blue-200',
  };

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-[11px] font-black uppercase tracking-widest transition-all border
        ${active ? colorMap[color] : 'text-gray-500 bg-white border-transparent hover:bg-gray-100'}
      `}
    >
      {icon} {label}
      <span className={`ml-2 px-2 py-0.5 rounded-full text-[9px] ${active ? 'bg-white/50' : 'bg-gray-200 text-gray-500'}`}>
        {count}
      </span>
    </button>
  );
};