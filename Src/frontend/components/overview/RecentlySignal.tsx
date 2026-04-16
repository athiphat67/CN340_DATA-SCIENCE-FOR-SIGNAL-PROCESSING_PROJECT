import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowUpRight, Target, ShieldX, Zap, Clock3, Sparkles } from 'lucide-react';

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
    provider: string | null;
}

// 2. Interface สำหรับ MetricBox (ทำ TypeScript ให้สมบูรณ์ขึ้น)
interface MetricBoxProps {
    label: string;
    value: number | null;
    color: string;
    icon: React.ReactNode;
    unit?: string;
}

const signalConfigs = {
    BUY: { color: 'emerald', bgColor: 'bg-emerald-50', textColor: 'text-emerald-700', borderColor: 'border-emerald-200', statusText: 'Bullish Entry' },
    SELL: { color: 'rose', bgColor: 'bg-rose-50', textColor: 'text-rose-700', borderColor: 'border-rose-200', statusText: 'Bearish Exit' },
    HOLD: { color: 'amber', bgColor: 'bg-amber-50', textColor: 'text-amber-700', borderColor: 'border-amber-200', statusText: 'Neutral / Wait' },
};

export const RecentlySignal = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [latestSignal, setLatestSignal] = useState<SignalLogEntry | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchLatestSignal = async () => {
            try {
                // ดึงข้อมูล Signal ล่าสุดเพียงเส้นเดียว
                const response = await fetch(`${import.meta.env.VITE_API_URL}/api/latest-signal`);
                const signalData = await response.json();

                if (signalData && !signalData.detail) {
                    const formatted: SignalLogEntry = {
                        ...signalData,
                        // ใช้ provider จาก DB ถ้าไม่มีให้ใช้ 'AI AGENT' เป็น Default
                        provider: signalData.provider || 'AI AGENT',
                        // แปลงค่าทศนิยม (เช่น 0.65) ให้เป็นเปอร์เซ็นต์ (65)
                        confidence: signalData.confidence <= 1 ? Math.round(signalData.confidence * 100) : signalData.confidence,
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
        // อัปเดตข้อมูลทุกๆ 30 วินาที
        const interval = setInterval(fetchLatestSignal, 30000);
        return () => clearInterval(interval);
    }, [id]);

    // Loading State
    if (isLoading) {
        return (
            <div className="bg-white rounded-[24px] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full flex flex-col items-center justify-center min-h-[400px]">
                <div className="animate-pulse flex flex-col items-center gap-4">
                    <Zap size={32} className="text-gray-300" />
                    <span className="text-gray-400 font-medium tracking-widest uppercase text-sm">Connecting to Agent...</span>
                </div>
            </div>
        );
    }

    // Empty State (ไม่พบข้อมูลใน DB)
    if (!latestSignal) {
        return (
            <div className="bg-white rounded-[24px] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full flex items-center justify-center min-h-[400px]">
                <span className="text-gray-400 font-medium">No signals found in database.</span>
            </div>
        );
    }

    // กันเหนียวกรณี signal เป็น null ให้ใช้สีของ HOLD ไปก่อน
    const safeSignal = latestSignal.signal || 'HOLD';
    const config = signalConfigs[safeSignal as keyof typeof signalConfigs];
    
    // จัด Format เวลา
    const timeFormatted = new Date(latestSignal.logged_at).toLocaleTimeString('th-TH', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });

    return (
        <div className="bg-white rounded-[24px] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <div className="flex items-center gap-3 mb-1.5">
                        <h2 className="text-xl font-bold text-gray-950">Recently Signal</h2>

                        {/* Provider Badge (ดึงข้อมูลจริงจาก DB แล้ว) */}
                        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-lg shadow-sm">
                            <Sparkles size={12} className="text-blue-600 animate-pulse" />
                            <span className="text-[10px] font-black text-blue-900 tracking-wider">
                                {latestSignal.provider}
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs text-gray-500 font-mono bg-gray-50 px-3 py-1 rounded-full border border-gray-100 w-fit shadow-inner">
                        <Clock3 size={14} className="text-gray-400" />
                        <span>Logged at: {timeFormatted}</span>
                    </div>
                </div>

                {/* ปุ่มกดดูรายละเอียดเพิ่มเติม */}
                <button
                    onClick={() => navigate(`/signals/${latestSignal.id}`)}
                    className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-gray-400 hover:text-[#824199] hover:bg-[#824199]/10 transition-all border border-gray-100 shadow-sm active:scale-95 group"
                    title="View full log"
                >
                    <ArrowUpRight size={20} className="group-hover:scale-110 transition-transform" />
                </button>
            </div>

            {/* Hero Signal Section */}
            <div className={`flex-1 flex flex-col items-center justify-center rounded-[32px] border-2 ${config.borderColor} ${config.bgColor} p-8 mb-8 relative overflow-hidden transition-colors duration-500`}>
                <Zap className={`absolute -right-10 -bottom-10 size-48 ${config.textColor} opacity-5`} />
                <div className="text-center relative z-10">
                    <p className={`text-sm font-bold uppercase tracking-[0.2em] ${config.textColor} mb-2`}>LLM DECISION</p>
                    <h1 className={`text-8xl font-extrabold tracking-tighter ${config.textColor} mb-3 drop-shadow-sm`}>{safeSignal}</h1>
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
                <MetricBox label="Entry Price" value={latestSignal.entry_price} color="text-[#824199]" icon={<Zap size={16} />} unit="฿" />
                <MetricBox label="Target (TP)" value={latestSignal.take_profit} color="text-emerald-700" icon={<Target size={16} />} unit="฿" />
                <MetricBox label="Stop Loss (SL)" value={latestSignal.stop_loss} color="text-rose-700" icon={<ShieldX size={16} />} unit="฿" />
            </div>

            {/* Rationale Block */}
            <div className="bg-gray-50 border border-gray-100 rounded-2xl p-6 relative overflow-hidden">
                {/* Decorative element */}
                <div className="absolute top-0 right-0 w-24 h-24 bg-[#824199]/5 rounded-bl-[100px] pointer-events-none" />
                
                <h4 className="text-sm font-semibold text-[#824199] mb-3 flex items-center gap-2 relative z-10">
                    <div className="bg-[#824199]/10 p-1.5 rounded-lg">
                        <Zap size={14} className="text-[#824199]" />
                    </div> 
                    Agent Rationale
                </h4>
                <p className="text-[13px] leading-relaxed text-gray-600 font-medium relative z-10">
                    {latestSignal.rationale}
                </p>
            </div>
        </div>
    );
};

// Sub-component สำหรับกล่องตัวเลข
const MetricBox = ({ label, value, color, icon, unit = "" }: MetricBoxProps) => (
    <div className="bg-gray-50 rounded-2xl p-5 border border-gray-100 flex items-center gap-4 transition-all hover:border-gray-200 hover:shadow-sm">
        <div className={`w-12 h-12 rounded-xl bg-white border border-gray-100 flex items-center justify-center ${color} shadow-sm`}>
            {icon}
        </div>
        <div>
            <p className="text-[10px] text-gray-500 uppercase font-bold tracking-wider mb-0.5">{label}</p>
            <p className={`text-xl font-black ${color}`}>
                {value ? value.toLocaleString() : '—'}
                {value && unit && <span className="text-xs text-gray-400 font-bold ml-1">{unit}</span>}
            </p>
        </div>
    </div>
);