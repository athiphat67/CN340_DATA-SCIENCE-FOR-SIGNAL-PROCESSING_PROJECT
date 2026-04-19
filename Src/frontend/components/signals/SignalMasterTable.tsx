import React, { useState, useEffect } from 'react';
import { Brain, Search, Database, Zap, ChevronDown, ChevronUp, Clock, Crosshair, ShieldX } from 'lucide-react';

type SignalType = 'BUY' | 'HOLD' | 'SELL';

// 1. กำหนด Interface ให้ตรงกับที่ API ส่งมา
interface SignalLog {
  id: number;
  logged_at: string;
  interval_tf: string;
  entry_price: number | null;
  take_profit: number | null;
  stop_loss: number | null;
  signal: SignalType | null;
  confidence: number;
  rationale?: string; // เผื่อ API ในอนาคตส่งเหตุผลการตัดสินใจมาด้วย
  trace_json?: string;
  filter: string;
}

export const SignalMasterTable = ({ filter }: SignalMasterTableProps) => {
  // State สำหรับจัดการข้อมูล API
  const [logFilter, setLogFilter] = useState<'Recent' | 'All'>('Recent');
  const [signalLogs, setSignalLogs] = useState<SignalLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // State สำหรับเก็บ ID ของแถวที่กำลังเปิด Trace อยู่
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const toggleTrace = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // 2. ดึงข้อมูลจาก Backend แบบเดียวกับ SignalLogTable
  useEffect(() => {
    const fetchLogs = async () => {
      setIsLoading(true);
      try {
        const limit = logFilter === 'Recent' ? 10 : 50;
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/recent-signals?limit=${limit}`);

        if (response.ok) {
          const data = await response.json();
          setSignalLogs(data);
        } else {
          console.error(`Error: Received status ${response.status} from API`);
        }
      } catch (error) {
        console.error("Failed to fetch signal logs:", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchLogs();
  }, [logFilter]);

  // ฟังก์ชันแปลงวันที่
  const formatDate = (isoString: string) => {
    if (!isoString) return 'Unknown';
    const date = new Date(isoString);
    return date.toLocaleString('en-GB', {
      day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
    }).replace(',', '');
  };

  const renderTraceSteps = (traceJson?: string) => {
    if (!traceJson) return <p className="text-xs text-gray-400">No trace data available for this signal.</p>;

    try {
      const steps = JSON.parse(traceJson);
      return steps.map((step: any, idx: number) => (
        <div key={idx} className="flex gap-4">
          <div className="flex flex-col items-center">
            <div className="w-7 h-7 rounded-full bg-white border border-gray-100 shadow-sm flex items-center justify-center text-[#824199] z-10">
              {step.step === 'TOOL_EXECUTION' ? <Search size={14} /> : step.step.includes('THOUGHT') ? <Brain size={14} /> : <Zap size={14} />}
            </div>
            {idx !== steps.length - 1 && <div className="w-0.5 h-full bg-gray-200 -mt-1 mb-1" />}
          </div>
          <div className="pb-4 pt-1">
            <h5 className="text-[10px] font-black text-gray-900 uppercase tracking-tighter">
              {step.step === 'TOOL_EXECUTION' ? `Tool: ${step.tool_name}` : step.step}
            </h5>
            <p className="text-[11px] text-gray-500 font-medium mt-0.5 line-clamp-2">
              {step.response?.thought || step.observation?.error || "Processing iteration..."}
            </p>
          </div>
        </div>
      ));
    } catch (e) {
      return <p className="text-xs text-rose-400">Error parsing trace logs.</p>;
    }
  };

  const filteredLogs = filter === 'All' 
    ? signalLogs 
    : signalLogs.filter(log => log.signal === filter);

  return (
    <div className="bg-white rounded-[32px] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-100 overflow-hidden font-sans">

      {/* 🔴 Top Bar: Filter Controls */}
      <div className="flex items-center justify-between p-6 pb-2">
        <div>
          <h2 className="text-lg font-bold text-gray-900 tracking-tight">Intelligence History</h2>
          <p className="text-xs text-gray-400 mt-0.5">Track record of recent agent decisions</p>
        </div>

        <div className="bg-gray-50 p-1 rounded-xl border border-gray-100 flex items-center">
          {(['Recent', 'All'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setLogFilter(f)}
              className={`px-4 py-1.5 text-xs rounded-lg transition-all font-bold ${logFilter === f ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-400 hover:text-gray-600'
                }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* 🔴 Header */}
      <div className="grid grid-cols-[0.4fr_1fr_0.5fr_0.8fr_3.2fr_1.2fr] bg-gray-50/80 text-[10px] font-black text-gray-400 uppercase tracking-widest p-5 border-y border-gray-100 items-center mt-2">
        <input type="checkbox" className="rounded-md border-gray-300 text-[#824199]" />
        <span>Date & ID</span>
        <span className="text-center">TF</span>
        <span className="text-center">Action</span>
        <span className="pl-2">AI Analysis & Metrics</span>
        <span className="text-right">Intelligence Trace</span>
      </div>

      <div className="divide-y divide-gray-50/80">
        {isLoading ? (
          <div className="py-16 flex justify-center items-center">
            <span className="text-sm font-medium text-gray-400 animate-pulse flex items-center gap-2">
              <Brain className="animate-spin text-purple-400" size={16} /> Loading intelligence data...
            </span>
          </div>
        ) : filteredLogs.length === 0 ? (
          
          <div className="py-16 flex justify-center items-center">
            <span className="text-sm font-medium text-gray-400">No intelligence history found.</span>
          </div>
          
        ) : (
          filteredLogs.map((row) => {
            
            const safeSignal = row.signal || 'HOLD';
            // แปลง Confidence ให้เป็น % (เผื่อ API ส่งมาเป็น 0.85 แทน 85)
            const confPercent = row.confidence <= 1 ? Math.round(row.confidence * 100) : row.confidence;
            // สร้าง Dummy Rationale ถ้า API ยังไม่ส่งมา
            const displayRationale = row.rationale || `Algorithm executed quantitative analysis on ${row.interval_tf} timeframe. Multiple indicators triggered a ${safeSignal} bias.`;

            return (
              <React.Fragment key={row.id}>
                {/* 🔴 Main Row */}
                <div className={`grid grid-cols-[0.4fr_1fr_0.5fr_0.8fr_3.2fr_1.2fr] items-center p-5 transition-all ${expandedId === row.id ? 'bg-purple-50/30' : 'hover:bg-gray-50/50'}`}>

                  <input type="checkbox" className="rounded-md border-gray-300 text-[#824199]" />

                  <div>
                    <p className="text-[13px] font-bold text-gray-900 flex items-center gap-1.5">
                      <Clock size={12} className="text-gray-400" /> {formatDate(row.logged_at)}
                    </p>
                    <p className="text-[10px] text-gray-400 font-mono">#{row.id}</p>
                  </div>

                  <div className="flex justify-center">
                    <span className="bg-white text-gray-500 text-[10px] font-bold px-2.5 py-1 rounded-lg border border-gray-100 shadow-sm">{row.interval_tf || '-'}</span>
                  </div>

                  <div className="flex justify-center">
                    <span className={`text-[10px] font-black px-3 py-1.5 rounded-full border tracking-widest ${safeSignal === 'BUY' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                        safeSignal === 'SELL' ? 'bg-rose-50 text-rose-600 border-rose-100' :
                          'bg-amber-50 text-amber-600 border-amber-100'
                      }`}>
                      {safeSignal}
                    </span>
                  </div>

                  <div className="pl-2 pr-6">
                    <p className="text-xs text-gray-700 font-medium line-clamp-1 mb-2">"{displayRationale}"</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[9px] font-bold bg-purple-50 text-[#824199] px-2 py-0.5 rounded-md border border-purple-100">CONFIDENCE: {confPercent}%</span>

                      {row.entry_price && (
                        <span className="text-[9px] font-bold bg-gray-100 text-gray-600 px-2 py-0.5 rounded-md border border-gray-200">ENTRY: {row.entry_price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</span>
                      )}

                      {row.take_profit && (
                        <span className="text-[9px] font-bold bg-emerald-50 text-emerald-600 flex items-center gap-1 px-2 py-0.5 rounded-md border border-emerald-100">
                          <Crosshair size={10} /> TP: {row.take_profit.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* ปุ่มกดเปิด Trace ใต้แถว */}
                  <div className="text-right flex justify-end">
                    <button
                      onClick={() => toggleTrace(row.id)}
                      className={`inline-flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest transition-all px-4 py-2 rounded-xl border ${expandedId === row.id
                        ? 'bg-[#824199] text-white border-[#824199] shadow-lg shadow-purple-200'
                        : 'text-gray-400 hover:text-[#824199] border-transparent'
                        }`}
                    >
                      {expandedId === row.id ? 'Close Trace' : 'View Trace'}
                      {expandedId === row.id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </button>
                  </div>
                </div>

                {/* 🟢 Sub-column (Trace Log) ที่กางออกมาใต้แถวที่กด */}
                {expandedId === row.id && (
                  <div className="bg-gray-100/60 border-x-4 border-[#824199]/20 shadow-inner animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="p-8 grid grid-cols-12 gap-8">

                      {/* ฝั่งซ้าย: Rationale */}
                      <div className="col-span-12 md:col-span-5 lg:col-span-4">
                        <div className="bg-[#13071a] p-6 rounded-[24px] text-white relative overflow-hidden h-full shadow-lg">
                          <Brain className="absolute -right-4 -bottom-4 opacity-10" size={80} />
                          <p className="text-[10px] font-bold text-purple-300 uppercase tracking-[0.2em] mb-3">Final Agent Rationale</p>
                          <p className="text-sm italic font-medium leading-relaxed relative z-10">"{displayRationale}"</p>
                        </div>
                      </div>

                      {/* ฝั่งขวา: Execution Steps */}
                      <div className="col-span-12 md:col-span-7 lg:col-span-8 space-y-5">
                        <h4 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] mb-2">Execution Steps</h4>
                        <TraceItem icon={<Search size={14} />} title="Market Scan" desc={`Ingesting multi-source market data on ${row.interval_tf || 'default'} timeframe.`} />
                        <TraceItem icon={<Database size={14} />} title="Pattern Recognition" desc="Analyzing current trend, volume support, and historical resistance." />
                        <TraceItem icon={<Brain size={14} />} title="Inference" desc={`Quantitative conditions met. Confidence parameter at ${confPercent}%.`} />
                        <div className="col-span-12 md:col-span-7 lg:col-span-8 space-y-5">
                          <h4 className="text-[10px] font-black text-gray-500 uppercase tracking-[0.2em] mb-2">Execution Steps</h4>
                          {renderTraceSteps(row.trace_json)}
                        </div>
                      </div>

                    </div>
                  </div>
                )}
              </React.Fragment>
            );
          })
        )}
      </div>
    </div>
  );
};

// Component สำหรับ Timeline ฝั่งขวา
const TraceItem = ({ icon, title, desc, isLast }: { icon: React.ReactNode, title: string, desc: string, isLast?: boolean }) => (
  <div className="flex gap-4">
    <div className="flex flex-col items-center">
      <div className="w-7 h-7 rounded-full bg-white border border-gray-100 shadow-sm flex items-center justify-center text-gray-400 z-10">
        {icon}
      </div>
      {!isLast && <div className="w-0.5 h-full bg-gray-200 -mt-1 mb-1" />}
    </div>
    <div className="pb-4 pt-1">
      <h5 className="text-[10px] font-black text-gray-900 uppercase tracking-tighter">{title}</h5>
      <p className="text-[11px] text-gray-500 font-medium mt-0.5">{desc}</p>
    </div>
  </div>
);