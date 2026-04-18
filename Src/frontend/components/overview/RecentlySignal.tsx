import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom'; // 1. นำเข้า useNavigate
import { ArrowUpRight, Target, ShieldX, Zap, Clock3, Brain, Timer, ShieldAlert } from 'lucide-react';

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
                const response = await fetch(`${import.meta.env.VITE_API_URL}/api/latest-signal`);
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

    const getSignalIcon = (signal: string | null) => {
        switch (signal) {
            case 'BUY': return <Zap className="size-12 md:size-16 opacity-90" strokeWidth={2.5} />;
            case 'HOLD': return <Timer className="size-12 md:size-16 opacity-90" strokeWidth={2.5} />;
            case 'SELL': return <ShieldAlert className="size-12 md:size-16 opacity-90" strokeWidth={2.5} />;
            default: return <Zap className="size-12 md:size-16 opacity-90" strokeWidth={2.5} />;
        }
    };

    return (
        /* ✨ Fixed Container: Added overflow-hidden to prevent the BUY text from leaking */
        <div className="bg-white rounded-[24px] p-8 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.1)] border-2 border-purple-200 ring-4 ring-purple-100/50 flex flex-col h-full relative overflow-hidden transition-all duration-300">

            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div className="z-10">
                    <h2 className="text-xl font-bold text-gray-950">Recently Signal</h2>
                    <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500 font-mono bg-gray-50 px-3 py-1 rounded-full border border-gray-100">
                        <Clock3 size={14} className="text-gray-400" />
                        <span>Logged at: {timeFormatted} (UTC +7)</span>
                    </div>
                </div>
                <button
                    onClick={() => navigate(`/signals/${latestSignal.id}`)}
                    className="z-10 w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-gray-400 hover:text-gray-950 hover:bg-gray-100 transition-all border border-gray-100 shadow-sm"
                >
                    <ArrowUpRight size={20} />
                </button>
            </div>

            {/* ✨ Fixed Hero Signal: Set a concrete height and used flex-grow to stop overlapping */}
            <div className={`flex-grow flex flex-col items-center justify-center rounded-[32px] border-2 ${config.borderColor} ${config.bgColor} p-8 mb-8 relative min-h-[200px]`}>

                <div className="flex flex-col items-center relative z-10 w-full">
                    <p className={`text-xs font-bold uppercase tracking-[0.2em] ${config.textColor} mb-6`}>
                        LLM DECISION
                    </p>

                    {/* ✨ Container หลักที่จัดทุกอย่างไว้กึ่งกลาง (Center Alignment) */}
                    <div className="flex items-center justify-center gap-5 mb-6 w-full">
                        {/* ✨ ไอคอนจะเปลี่ยนไปตามค่าของ latestSignal.signal */}
                        <div className={config.textColor}>
                            {getSignalIcon(latestSignal.signal)}
                        </div>

                        <h1 className={`text-7xl md:text-8xl font-extrabold tracking-tighter ${config.textColor} leading-none`}>
                            {latestSignal.signal}
                        </h1>
                    </div>

                    {/* Confidence Badge */}
                    <div className={`inline-flex items-center gap-2 px-5 py-2 rounded-full ${config.textColor} bg-white border ${config.borderColor} font-bold text-[12px] shadow-sm`}>
                        <span className="relative flex h-2 w-2">
                            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-20`}></span>
                            <span className={`relative inline-flex rounded-full h-2 w-2 bg-current`}></span>
                        </span>
                        {config.statusText} • {latestSignal.confidence}%
                    </div>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-3 gap-3 mb-8">
                <MetricBox label="Entry Price" value={latestSignal.entry_price} color="text-purple-700" icon={<Zap size={18} />} unit="฿" />
                <MetricBox label="Target (TP)" value={latestSignal.take_profit} color="text-emerald-700" icon={<Target size={18} />} />
                <MetricBox label="Stop Loss (SL)" value={latestSignal.stop_loss} color="text-rose-700" icon={<ShieldX size={18} />} />
            </div>

            {/* Rationale Block */}
            <div className="bg-gray-50/50 border border-gray-100 rounded-2xl p-5">
                <h4 className="text-[11px] font-bold text-purple-800 mb-2 flex items-center gap-2 uppercase tracking-wider">
                    <Brain size={14} className="text-purple-500" /> Agent Rationale
                </h4>
                <p className="text-xs leading-relaxed text-gray-600 font-medium italic">
                    "{latestSignal.rationale}"
                </p>
            </div>
        </div>
    );
};

/* ✨ Updated Sub-component for smaller, cleaner metrics */
const MetricBox = ({ label, value, color, icon, unit = "" }: any) => (
    <div className="bg-gray-50/50 rounded-2xl p-4 border border-gray-100 flex flex-col items-center text-center gap-2">
        <div className={`w-8 h-8 rounded-lg bg-white shadow-sm flex items-center justify-center ${color}`}>{icon}</div>
        <div>
            <p className="text-[9px] text-gray-400 uppercase font-black tracking-tighter mb-1">{label}</p>
            <p className={`text-base font-black ${color}`}>
                {value ? value.toLocaleString() : '—'}
                {unit && <span className="text-[10px] ml-0.5 opacity-50 font-sans">{unit}</span>}
            </p>
        </div>
    </div>
);