import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom'; // 1. นำเข้า useNavigate
import { ArrowUpRight, Target, ShieldX, Zap, Clock3 } from 'lucide-react';

// 1. Interface สำหรับจัดการข้อมูลจาก DB
export interface SignalLogEntry {
    id: number;
    logged_at: string;
    signal: 'BUY' | 'SELL' | 'HOLD' | null;
    confidence: number;
    entry_price: number | null;
    stop_loss: number | null;
    take_profit: number | null;
    rationale: string;
}

const signalConfigs = {
    BUY: { color: 'emerald', bgColor: 'bg-emerald-50', textColor: 'text-emerald-700', borderColor: 'border-emerald-200', statusText: 'Bullish Entry' },
    SELL: { color: 'rose', bgColor: 'bg-rose-50', textColor: 'text-rose-700', borderColor: 'border-rose-200', statusText: 'Bearish Exit' },
    HOLD: { color: 'amber', bgColor: 'bg-amber-50', textColor: 'text-amber-700', borderColor: 'border-amber-200', statusText: 'Neutral / Wait' },
};

export const RecentlySignal = () => {
    const navigate = useNavigate(); // 2. ประกาศตัวแปร navigate
    const [latestSignal, setLatestSignal] = useState<SignalLogEntry | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchLatestSignal = async () => {
            try {
                const response = await fetch('http://127.0.0.1:8000/api/latest-signal');
                const data = await response.json();

                if (data && !data.detail) {
                    const formatted: SignalLogEntry = {
                        ...data,
                        confidence: data.confidence <= 1 ? Math.round(data.confidence * 100) : data.confidence,
                    };
                    setLatestSignal(formatted);
                }
            } catch (error) {
                console.error("Fetch error:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchLatestSignal();
        const interval = setInterval(fetchLatestSignal, 30000);
        return () => clearInterval(interval);
    }, []);

    if (isLoading) return <div className="p-8 text-center text-gray-400 animate-pulse bg-white rounded-[24px]">Connecting to Agent...</div>;
    if (!latestSignal) return <div className="p-8 text-center text-gray-400 bg-white rounded-[24px]">No signals found in DB.</div>;

    const config = signalConfigs[latestSignal.signal as keyof typeof signalConfigs];
    const timeFormatted = new Date(latestSignal.logged_at).toLocaleTimeString('th-TH', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });

    return (
        <div className="bg-white rounded-[24px] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h2 className="text-xl font-bold text-gray-950">Recently Signal</h2>
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500 font-mono bg-gray-50 px-3 py-1 rounded-full border border-gray-100">
                        <Clock3 size={14} className="text-gray-400" />
                        <span>Logged at: {timeFormatted} (UTC +7)</span>
                    </div>
                </div>
                {/* 3. เพิ่ม onClick เพื่อพาไปหน้า Detail */}
                <button 
                    onClick={() => navigate(`/signals/${latestSignal.id}`)}
                    title="View Intelligence Trace"
                    className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-gray-400 hover:text-gray-950 hover:bg-gray-100 transition-all border border-gray-100 active:scale-95 shadow-sm"
                >
                    <ArrowUpRight size={20} />
                </button>
            </div>

            {/* ... (Hero Section และ Metrics Grid เหมือนเดิม) ... */}

            {/* Hero Signal Section */}
            <div className={`flex-1 flex flex-col items-center justify-center rounded-[32px] border-2 ${config.borderColor} ${config.bgColor} p-8 mb-8 relative overflow-hidden`}>
                <Zap className={`absolute -right-10 -bottom-10 size-48 ${config.textColor} opacity-5`} />
                <div className="text-center relative z-10">
                    <p className={`text-sm font-bold uppercase tracking-[0.2em] ${config.textColor} mb-2`}>LLM DECISION</p>
                    <h1 className={`text-8xl font-extrabold tracking-tighter ${config.textColor} mb-3`}>{latestSignal.signal}</h1>
                    <div className={`inline-flex items-center gap-2 px-4 py-1.5 rounded-full ${config.textColor} bg-white border ${config.borderColor} font-semibold text-sm shadow-sm`}>
                        <span className="relative flex h-2 w-2">
                            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-${config.color}-400 opacity-75`}></span>
                            <span className={`relative inline-flex rounded-full h-2 w-2 bg-${config.color}-500`}></span>
                        </span>
                        {config.statusText} • Confidence: {latestSignal.confidence}%
                    </div>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <MetricBox label="Entry Price" value={latestSignal.entry_price} color="text-[#824199]" icon={<Zap size={24}/>} unit="฿" />
                <MetricBox label="Target (TP)" value={latestSignal.take_profit} color="text-emerald-700" icon={<Target size={24}/>} />
                <MetricBox label="Stop Loss (SL)" value={latestSignal.stop_loss} color="text-rose-700" icon={<ShieldX size={24}/>} />
            </div>

            {/* Rationale Block */}
            <div className="bg-gray-50 border border-gray-100 rounded-2xl p-6">
                <h4 className="text-sm font-semibold text-[#824199] mb-3 flex items-center gap-2">
                    <div className="bg-[#824199]/10 p-1.5 rounded-lg"><Zap size={14} /></div> Agent Rationale
                </h4>
                <p className="text-sm leading-relaxed text-gray-600 font-light">{latestSignal.rationale}</p>
            </div>
        </div>
    );
};

// Sub-component เพื่อให้ Code สะอาดขึ้น
const MetricBox = ({ label, value, color, icon, unit = "" }: any) => (
    <div className="bg-gray-50 rounded-2xl p-5 border border-gray-100 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-white border border-gray-100 flex items-center justify-center text-current">{icon}</div>
        <div>
            <p className="text-[10px] text-gray-500 uppercase font-bold tracking-wider mb-0.5">{label}</p>
            <p className={`text-2xl font-bold ${color}`}>
                {value ? value.toLocaleString() : '—'}{unit && <span className="text-sm text-gray-400 font-medium ml-1">{unit}</span>}
            </p>
        </div>
    </div>
);