import React, { useState } from 'react';
import {
  ArrowUpRight, ArrowDownRight, Target, ShieldAlert,
  Zap, ChevronDown, ChevronUp, Clock, Brain, Search, Database, User, Activity
} from 'lucide-react';

export const TradeHistoryTable = () => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleRow = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // 1. Mock up ข้อมูลชุดใหญ่ให้เหมือนหน้า Signal
  const history = [
    { id: 'TRD-452', asset: 'XAU/THB', type: 'BUY', entry: 41100, exit: 41450, date: '15 Apr 2026', time: '10:30', pnl: 3500, pnlPercent: 0.85, reason: 'TARGET HIT', icon: <Target size={14} />, rationale: 'Price broke above 41,000 resistance with high volume confirmation.', confidence: 88, tech: 'MACD_BULL_CROSS' },
    { id: 'TRD-451', asset: 'XAU/THB', type: 'SELL', entry: 41600, exit: 41450, date: '14 Apr 2026', time: '22:15', pnl: 1500, pnlPercent: 0.36, reason: 'TREND REVERSAL', icon: <Zap size={14} />, rationale: 'RSI overbought at 75. Bearish divergence spotted on 1H chart.', confidence: 75, tech: 'RSI_OVERBOUGHT' },
    { id: 'TRD-450', asset: 'XAU/THB', type: 'BUY', entry: 41500, exit: 41400, date: '14 Apr 2026', time: '15:20', pnl: -1000, pnlPercent: -0.24, reason: 'STOP LOSS', icon: <ShieldAlert size={14} />, rationale: 'Unexpected volatility spike cleared stop loss level before reversal.', confidence: 92, tech: 'VOL_SPIKE' },
    { id: 'TRD-449', asset: 'XAU/THB', type: 'BUY', entry: 41000, exit: 41500, date: '13 Apr 2026', time: '09:00', pnl: 5000, pnlPercent: 1.22, reason: 'MANUAL CLOSE', icon: <User size={14} />, rationale: 'User intervention: Secured profit ahead of high-impact news release.', confidence: 85, tech: 'MANUAL_EXIT' },
    { id: 'TRD-448', asset: 'XAU/THB', type: 'SELL', entry: 41300, exit: 41100, date: '12 Apr 2026', time: '20:45', pnl: 2000, pnlPercent: 0.48, reason: 'TARGET HIT', icon: <Target size={14} />, rationale: 'Bearish continuation pattern confirmed. Price reached supply zone.', confidence: 70, tech: 'SUPPLY_REJECTION' },
    { id: 'TRD-447', asset: 'XAU/THB', type: 'BUY', entry: 40500, exit: 40950, date: '11 Apr 2026', time: '11:10', pnl: 4500, pnlPercent: 1.11, reason: 'TARGET HIT', icon: <Target size={14} />, rationale: 'Golden cross on 4H timeframe. Strong bullish momentum established.', confidence: 80, tech: 'MA_CROSSOVER' },
    { id: 'TRD-446', asset: 'XAU/THB', type: 'SELL', entry: 41000, exit: 41150, date: '10 Apr 2026', time: '23:30', pnl: -1500, pnlPercent: -0.37, reason: 'STOP LOSS', icon: <ShieldAlert size={14} />, rationale: 'False breakout at resistance level. Liquidity grab detected.', confidence: 65, tech: 'FALSE_BREAKOUT' },
    { id: 'TRD-445', asset: 'XAU/THB', type: 'BUY', entry: 40200, exit: 40600, date: '09 Apr 2026', time: '08:15', pnl: 4000, pnlPercent: 1.00, reason: 'TARGET HIT', icon: <Target size={14} />, rationale: 'Oversold RSI condition with Fibonacci 61.8% retracement support.', confidence: 90, tech: 'FIB_RETRACEMENT' },
  ];

  return (
    <div className="bg-white rounded-[32px] shadow-sm border border-gray-100 overflow-hidden flex flex-col h-[700px] font-sans">
      {/* Table Header */}
      <div className="grid grid-cols-[1.5fr_0.8fr_1fr_1fr_1fr_1fr] bg-gray-50/80 text-[10px] font-black text-gray-400 uppercase tracking-widest p-6 border-b border-gray-100 shrink-0">
        <span>Trade Detail & ID</span>
        <span className="text-center">Side</span>
        <span className="text-right">Entry / Exit</span>
        <span className="text-right">Closed At</span>
        <span className="text-right">Realized P&L</span>
        <span className="text-right">Intelligence</span>
      </div>

      {/* Table Body with Scroll */}
      <div className="divide-y divide-gray-50 overflow-y-auto flex-1 custom-scrollbar">
        {history.map((trade) => {
          return (
            <React.Fragment key={trade.id}>
              {/* Main Row: เมื่อคลิกจะเปิดแถบข้างล่าง */}
              <div
                onClick={() => toggleRow(trade.id)}
                className={`grid grid-cols-[1.5fr_0.8fr_1fr_1fr_1fr_1fr] items-center p-6 transition-all cursor-pointer ${expandedId === trade.id ? 'bg-purple-50/30' : 'hover:bg-gray-50/40'}`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${trade.pnl > 0 ? 'bg-emerald-50 text-emerald-500' : 'bg-rose-50 text-rose-500'}`}>
                    {trade.pnl > 0 ? <ArrowUpRight size={20} /> : <ArrowDownRight size={20} />}
                  </div>
                  <div>
                    <p className="text-sm font-black text-gray-900">{trade.asset}</p>
                    <p className="text-[10px] text-gray-400 font-mono tracking-tighter">#{trade.id}</p>
                  </div>
                </div>

                <div className="flex justify-center">
                  <span className={`text-[10px] font-black px-3 py-1 rounded-md border shadow-sm ${trade.type === 'BUY' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-rose-50 text-rose-600 border-rose-100'}`}>
                    {trade.type}
                  </span>
                </div>

                <div className="text-right">
                  <p className="text-xs font-bold text-gray-900">{trade.exit.toLocaleString()}</p>
                  <p className="text-[10px] text-gray-400 font-medium">from {trade.entry.toLocaleString()}</p>
                </div>

                <div className="text-right">
                  <p className="text-xs font-bold text-gray-800">{trade.date}</p>
                  <p className="text-[10px] text-gray-400 font-bold uppercase">{trade.time}</p>
                </div>

                <div className="text-right relative">
                  {/* Visual P&L bar */}
                  <div className={`absolute right-[-8px] top-1/2 -translate-y-1/2 w-1 h-8 rounded-full ${trade.pnl > 0 ? 'bg-emerald-400/30' : 'bg-rose-400/30'}`} />
                  <p className={`text-sm font-black ${trade.pnl > 0 ? 'text-emerald-600' : 'text-rose-500'}`}>
                    {trade.pnl > 0 ? '+' : ''}{trade.pnl.toLocaleString()} ฿
                  </p>
                  <p className={`text-[10px] font-bold mt-0.5 ${trade.pnl > 0 ? 'text-emerald-500/70' : 'text-rose-400/70'}`}>
                    {trade.pnlPercent}% Return
                  </p>
                </div>

                <div className="text-right">
                  <button className={`inline-flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest transition-all px-3 py-2 rounded-xl border ${expandedId === trade.id ? 'bg-[#824199] text-white border-[#824199]' : 'text-gray-400 border-transparent hover:text-[#824199]'}`}>
                    {expandedId === trade.id ? 'Close Trace' : 'View Trace'}
                    {expandedId === trade.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>
              </div>

              {/* 🟢 Intelligence Trace: ฉบับปรับปรุงความอ่านง่ายและ Spacing */}
              {expandedId === trade.id && (
                <div className="bg-gray-50/80 border-x-4 border-[#824199]/10 shadow-inner overflow-hidden">
                  <div className="p-8 grid grid-cols-12 gap-10 items-stretch"> {/* เพิ่ม gap เป็น 10 */}

                    {/* 1. Agent Rationale Box: ปรับ Typography ให้อ่านง่ายขึ้นมาก */}
                    <div className="col-span-12 lg:col-span-5">
                      <div className="bg-[#0f0514] p-8 rounded-[32px] text-white shadow-2xl relative h-full flex flex-col justify-between border border-white/5">
                        <Brain className="absolute -right-6 -bottom-6 opacity-[0.03] text-purple-400" size={120} />

                        <div className="relative z-10">
                          <div className="flex items-center gap-2 mb-6">
                            <div className="w-1.5 h-5 bg-[#f9d443] rounded-full shadow-[0_0_12px_rgba(249,212,67,0.4)]" />
                            <p className="text-[11px] font-black text-purple-200 uppercase tracking-[0.25em]">Strategic Rationale</p>
                          </div>

                          {/* 💡 ปรับปรุง: เพิ่ม Line-height และตัวหนาปานกลางเพื่อให้ข้อความเด่นขึ้น */}
                          <p className="text-[16px] leading-[1.8] font-medium text-white/90 italic tracking-wide">
                            "{trade.rationale}"
                          </p>
                        </div>

                        <div className="relative z-10 mt-10 pt-6 border-t border-white/10 grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-[9px] text-purple-400 font-bold uppercase tracking-widest mb-1">Confidence Score</p>
                            <p className="text-xl font-black text-[#f9d443]">{trade.confidence}%</p>
                          </div>
                          <div className="border-l border-white/10 pl-4">
                            <p className="text-[9px] text-purple-400 font-bold uppercase tracking-widest mb-1">Analysis Mode</p>
                            <p className="text-sm font-black text-white uppercase truncate">{trade.tech}</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* 2. Process Log: จัดกลุ่มแบบ Card Grid ที่มี Hierarchy ชัดเจน */}
                    <div className="col-span-12 lg:col-span-7 flex flex-col">
                      <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-2">
                          <Activity size={14} className="text-[#824199]" />
                          <h4 className="text-[11px] font-black text-gray-500 uppercase tracking-[0.2em]">Execution Trace Log</h4>
                        </div>
                        <span className="text-[9px] font-bold text-gray-400 bg-gray-100 px-2 py-1 rounded-md">AGENTIC WORKFLOW</span>
                      </div>

                      {/* 💡 ปรับปรุง: เพิ่ม gap และความสูงของ Card ให้สมดุล */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 flex-1">
                        <LogCard
                          icon={<Brain size={14} />}
                          label="Thought"
                          desc="Analyzing 4H timeframe for MACD crossover and volume confirmation." />
                        <LogCard
                          icon={<Search size={14} />}
                          label="Action"
                          desc="Querying real-time market depth and spot prices from exchange." />
                        <LogCard
                          icon={<Database size={14} />}
                          label="Observation"
                          desc={`Protocol check: ${trade.reason}. Support levels verified.`} />
                        <LogCard
                          icon={<Zap size={14} className="text-emerald-500" />}
                          label="Decision"
                          desc="Generated execution signal with high confidence score." />
                      </div>
                    </div>

                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      <div className="p-4 bg-gray-50/80 border-t border-gray-100 flex justify-center shrink-0">
        <p className="text-[10px] font-bold text-gray-400 uppercase tracking-[0.3em]">End of Archive Records</p>
      </div>
    </div>
  );
};

// Reusable Trace Step
const TraceStep = ({ icon, title, desc, isLast }: any) => (
  <div className="flex gap-4">
    <div className="flex flex-col items-center">
      <div className="w-8 h-8 rounded-full bg-white border border-gray-100 shadow-sm flex items-center justify-center text-gray-400 z-10">
        {icon}
      </div>
      {!isLast && <div className="w-0.5 h-full bg-gray-200 -mt-1 mb-1" />}
    </div>
    <div className="pb-4">
      <h5 className="text-[10px] font-black text-gray-900 uppercase tracking-tighter mb-0.5">{title}</h5>
      <p className="text-xs text-gray-500 font-medium leading-relaxed">{desc}</p>
    </div>
  </div>
);

{/* 🛠️ Helper Component: ปรับแต่งให้ดูสะอาดตาและพรีเมียม */ }
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