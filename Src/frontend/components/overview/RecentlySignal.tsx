import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowUpRight, Target, ShieldX, Zap, Clock3, Sparkles, Bot } from 'lucide-react';

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

interface MetricBoxProps {
    label: string;
    value: number | null;
    color: string;
    icon: React.ReactNode;
    unit?: string;
}

// 💡 แก้ไข: ใส่ Full Tailwind Classes เพื่อป้องกันปัญหา Purge ตอน Build Production
const signalConfigs = {
    BUY: { 
        bgColor: 'bg-emerald-50', textColor: 'text-emerald-700', borderColor: 'border-emerald-200', 
        pingColor: 'bg-emerald-400', dotColor: 'bg-emerald-500', statusText: 'Bullish Entry' 
    },
    SELL: { 
        bgColor: 'bg-rose-50', textColor: 'text-rose-700', borderColor: 'border-rose-200', 
        pingColor: 'bg-rose-400', dotColor: 'bg-rose-500', statusText: 'Bearish Exit' 
    },
    HOLD: { 
        bgColor: 'bg-amber-50', textColor: 'text-amber-700', borderColor: 'border-amber-200', 
        pingColor: 'bg-amber-400', dotColor: 'bg-amber-500', statusText: 'Neutral / Wait' 
    },
};

// 💡 เพิ่ม Helper Function จัดฟอร์แมตตัวเลข (ให้มีทศนิยมสวยๆ)
const formatPrice = (price: number | null) => {
    if (!price) return '—';
    return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
};

export const RecentlySignal = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [latestSignal, setLatestSignal] = useState<SignalLogEntry | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false); // 💡 เพิ่ม State บอกจังหวะ Auto-refresh

    useEffect(() => {
        const fetchLatestSignal = async () => {
            setIsRefreshing(true);
            try {
                const response = await fetch(`${import.meta.env.VITE_API_URL}/api/latest-signal`);
                const signalData = await response.json();

                if (signalData && !signalData.detail) {
                    const formatted: SignalLogEntry = {
                        ...signalData,
                        provider: signalData.provider || 'AI AGENT',
                        confidence: signalData.confidence <= 1 ? Math.round(signalData.confidence * 100) : signalData.confidence,
                    };
                    setLatestSignal(formatted);
                }
            } catch (error) {
                console.error("Fetch error:", error);
            } finally {
                setIsLoading(false);
                setTimeout(() => setIsRefreshing(false), 500); // ดีเลย์ให้เห็นแอนิเมชันกระพริบนิดนึง
            }
        };

        fetchLatestSignal();
        const interval = setInterval(fetchLatestSignal, 30000);
        return () => clearInterval(interval);
    }, [id]);

    // 💡 ปรับปรุง: Skeleton Loading ดูพรีเมียมกว่าการหมุนๆ เฉยๆ
    if (isLoading) {
        return (
            <div className="bg-white rounded-[24px] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full flex flex-col min-h-[500px]">
                <div className="flex justify-between mb-8">
                    <div className="space-y-3">
                        <div className="h-6 w-40 bg-gray-200 rounded-md animate-pulse" />
                        <div className="h-4 w-32 bg-gray-100 rounded-md animate-pulse" />
                    </div>
                    <div className="w-10 h-10 bg-gray-100 rounded-xl animate-pulse" />
                </div>
                <div className="flex-1 rounded-[32px] bg-gray-50 border-2 border-gray-100 p-8 mb-8 flex flex-col items-center justify-center animate-pulse">
                    <div className="h-4 w-24 bg-gray-200 rounded-full mb-4" />
                    <div className="h-24 w-48 bg-gray-200 rounded-xl mb-6" />
                    <div className="h-8 w-40 bg-gray-200 rounded-full" />
                </div>
                <div className="grid grid-cols-3 gap-6">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-24 bg-gray-50 rounded-2xl animate-pulse" />
                    ))}
                </div>
            </div>
        );
    }

    if (!latestSignal) {
        return (
            <div className="bg-white rounded-[24px] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full flex flex-col items-center justify-center min-h-[500px] text-gray-400">
                <Bot size={48} className="mb-4 opacity-50" />
                <span className="font-medium">No signals found in database.</span>
            </div>
        );
    }

    const safeSignal = latestSignal.signal || 'HOLD';
    const config = signalConfigs[safeSignal as keyof typeof signalConfigs];
    const timeFormatted = new Date(latestSignal.logged_at).toLocaleTimeString('th-TH', {
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });

    return (
        // 💡 เพิ่ม Entry Animation: animate-in fade-in slide-in-from-bottom-4
        <div className="bg-white rounded-[24px] p-8 shadow-[0_4px_20px_rgba(0,0,0,0.04)] h-full flex flex-col animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
            
            {/* Header */}
            <div className="flex items-center justify-between mb-8">
                <div>
                    <div className="flex items-center gap-3 mb-2">
                        <h2 className="text-xl font-bold text-gray-950">Recently Signal</h2>
                        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-md shadow-sm">
                            <Sparkles size={12} className="text-blue-600 animate-pulse" />
                            <span className="text-[10px] font-black text-blue-900 tracking-wider">
                                {latestSignal.provider}
                            </span>
                        </div>
                    </div>

                    <div className={`flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-full border w-fit shadow-inner transition-colors duration-300 ${isRefreshing ? 'bg-blue-50 border-blue-100 text-blue-500' : 'bg-gray-50 border-gray-100 text-gray-500'}`}>
                        <Clock3 size={14} className={isRefreshing ? 'animate-spin-slow' : ''} />
                        <span>Logged at: {timeFormatted}</span>
                    </div>
                </div>

                <button
                    onClick={() => navigate(`/signals/${latestSignal.id}`)}
                    className="w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center text-gray-400 hover:text-[#824199] hover:bg-[#824199]/10 transition-all border border-gray-100 shadow-sm active:scale-95 group"
                    title="View full log"
                >
                    <ArrowUpRight size={20} className="group-hover:scale-110 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                </button>
            </div>

            {/* Hero Signal Section */}
            {/* 💡 เพิ่ม transition-all เพื่อให้ตอนค่าเปลี่ยน สีเปลี่ยนแบบสมูท */}
            <div className={`flex-1 flex flex-col items-center justify-center rounded-[32px] border-2 ${config.borderColor} ${config.bgColor} p-8 mb-8 relative overflow-hidden transition-all duration-700`}>
                {/* 💡 ลูกเล่น: พื้นหลังไอคอนใหญ่ๆ หมุนช้าๆ */}
                <Zap className={`absolute -right-4 -bottom-4 size-56 ${config.textColor} opacity-[0.03] rotate-12`} />
                
                <div className="text-center relative z-10 hover:scale-105 transition-transform duration-500">
                    <p className={`text-sm font-bold uppercase tracking-[0.2em] ${config.textColor} mb-2 opacity-80`}>LLM DECISION</p>
                    <h1 className={`text-7xl md:text-8xl font-black tracking-tighter ${config.textColor} mb-4 drop-shadow-sm`}>
                        {safeSignal}
                    </h1>
                    
                    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${config.textColor} bg-white/80 backdrop-blur-sm border ${config.borderColor} font-semibold text-sm shadow-sm`}>
                        <span className="relative flex h-2.5 w-2.5">
                            {/* 💡 ใช้ค่าสีจาก Config ที่ถูกแก้บั๊กแล้ว */}
                            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${config.pingColor} opacity-75`}></span>
                            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${config.dotColor}`}></span>
                        </span>
                        {config.statusText} 
                        <span className="opacity-40 px-1">•</span> 
                        {latestSignal.confidence}% Confidence
                    </div>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                <MetricBox label="Entry Price" value={latestSignal.entry_price} color="text-[#824199]" icon={<Zap size={18} strokeWidth={2.5} />} unit="฿" />
                <MetricBox label="Target (TP)" value={latestSignal.take_profit} color="text-emerald-700" icon={<Target size={18} strokeWidth={2.5} />} unit="฿" />
                <MetricBox label="Stop Loss" value={latestSignal.stop_loss} color="text-rose-700" icon={<ShieldX size={18} strokeWidth={2.5} />} unit="฿" />
            </div>

            {/* Rationale Block */}
            <div className="bg-gray-50/50 border border-gray-100 rounded-2xl p-6 relative overflow-hidden group hover:bg-gray-50 transition-colors">
                <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-[#824199]/5 to-transparent rounded-bl-[100px] pointer-events-none transition-transform group-hover:scale-110" />
                
                <h4 className="text-[13px] font-bold text-[#824199] mb-3 flex items-center gap-2 relative z-10 uppercase tracking-wide">
                    <Bot size={16} className="text-[#824199]" />
                    Agent Rationale
                </h4>
                {/* 💡 ปรับ Typography ของ Text ให้อ่านง่ายขึ้นคล้ายๆ Terminal Quote */}
                <p className="text-sm leading-relaxed text-gray-600 font-medium relative z-10 pl-4 border-l-2 border-[#824199]/20">
                    {latestSignal.rationale}
                </p>
            </div>
        </div>
    );
};

const MetricBox = ({ label, value, color, icon, unit = "" }: MetricBoxProps) => (
    <div className="bg-white rounded-2xl p-4 border border-gray-100 flex items-center gap-4 transition-all hover:border-gray-300 hover:shadow-md hover:-translate-y-1">
        <div className={`w-12 h-12 rounded-[14px] bg-gray-50 border border-gray-100 flex items-center justify-center ${color}`}>
            {icon}
        </div>
        <div>
            <p className="text-[10px] text-gray-400 uppercase font-bold tracking-wider mb-0.5">{label}</p>
            <p className={`text-xl font-black ${color} tracking-tight`}>
                {formatPrice(value)} {/* 💡 ใช้ Helper Format ราคา */}
                {value && unit && <span className="text-xs font-bold ml-1 opacity-60">{unit}</span>}
            </p>
        </div>
    </div>
);