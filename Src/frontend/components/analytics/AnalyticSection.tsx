import React from 'react';
import { OverviewHeader } from '../overview/OverviewHeader';
import {
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    Scatter, ComposedChart, Line, Cell, PieChart, Pie, Area, AreaChart
} from 'recharts';
import { Brain, ShieldCheck, Zap, Target, PieChart as PieIcon, Activity, TrendingUp, Sparkles, Fingerprint, Gauge } from 'lucide-react';

export const AnalyticsSection = () => {
    // 1. Data Processing (อิงจาก database.py)
    const winLossData = [
        { name: 'Strategy Success', value: 65, color: '#10b981' },
        { name: 'Manual Override', value: 20, color: '#824199' },
        { name: 'Risk Mitigation', value: 15, color: '#f43f5e' },
    ];

    const agentBias = [
        { label: 'Bullish Intent', value: 70, color: 'bg-emerald-500', icon: <TrendingUp size={12}/> },
        { label: 'Market Observation', value: 20, color: 'bg-gray-400', icon: <Activity size={12}/> },
        { label: 'Bearish Protection', value: 10, color: 'bg-rose-500', icon: <ShieldCheck size={12}/> },
    ];

    const performanceData = [
        { time: '09:00', price: 41000, conf: 45, action: null },
        { time: '10:00', price: 40850, conf: 85, action: 'BUY' },
        { time: '11:00', price: 41000, conf: 60, action: null },
        { time: '12:00', price: 41200, conf: 55, action: null },
        { time: '13:00', price: 41450, conf: 92, action: 'SELL' },
        { time: '14:00', price: 41300, conf: 70, action: null },
        { time: '15:00', price: 41200, conf: 50, action: null },
    ];

    return (
        <section className="w-full min-h-screen pb-20 bg-[#FCFBF7] relative overflow-hidden font-sans">
            {/* Background Luxury Elements */}
            <div className="absolute top-[10%] right-[-5%] w-[600px] h-[600px] bg-[#824199]/5 rounded-full blur-[120px] pointer-events-none" />
            <div className="absolute bottom-[5%] left-[-10%] w-[500px] h-[500px] bg-blue-500/5 rounded-full blur-[100px] pointer-events-none" />
            
            <OverviewHeader />

            <div className="px-8 mt-12 max-w-7xl mx-auto relative z-20">
                {/* Header: Micro-Interaction Style */}
                <div className="flex flex-col md:flex-row md:items-center justify-between mb-12 gap-6">
                    <div>
                        <div className="flex items-center gap-2 mb-2 group cursor-default">
                            <div className="p-1.5 bg-[#824199]/10 rounded-lg group-hover:rotate-12 transition-transform">
                                <Sparkles className="w-4 h-4 text-[#824199]" />
                            </div>
                            <p className="text-[10px] font-bold text-[#824199] uppercase tracking-[0.4em]">Neural Engine v3.4</p>
                        </div>
                        <h1 className="text-5xl font-black text-gray-900 tracking-tighter leading-none">Market <span className="text-[#824199]">DNA</span></h1>
                    </div>
                    
                    <div className="flex bg-white/50 backdrop-blur-sm p-1.5 rounded-2xl border border-gray-100 shadow-inner">
                       {['Overview', 'Technicals', 'Agent Logic'].map(t => (
                           <button key={t} className={`px-5 py-2.5 rounded-xl text-[11px] font-black uppercase tracking-widest transition-all ${t === 'Agent Logic' ? 'bg-[#1a0a24] text-white shadow-lg scale-105' : 'text-gray-400 hover:text-gray-600'}`}>{t}</button>
                       ))}
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch">
                    
                    {/* --- LEFT: The "Brain" (8/12) --- */}
                    <div className="lg:col-span-8 space-y-8">
                        
                        {/* [HERO] Execution Trace with Glow Effect */}
                        <div className="bg-white p-10 rounded-[56px] border border-gray-100 shadow-[0_30px_60px_rgba(0,0,0,0.02)] relative overflow-hidden group">
                            <div className="flex justify-between items-start mb-12 relative z-10">
                                <div>
                                    <h3 className="text-sm font-bold text-gray-900 uppercase tracking-[0.2em] flex items-center gap-3">
                                        <div className="w-1.5 h-6 bg-[#824199] rounded-full" /> Execution Trace Map
                                    </h3>
                                    <p className="text-xs text-gray-400 font-medium mt-1 pl-4 uppercase tracking-tighter">XAU/THB Strategy Mapping</p>
                                </div>
                                <div className="flex gap-4">
                                    <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 rounded-2xl border border-emerald-100">
                                        <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                                        <span className="text-[10px] font-black text-emerald-700 uppercase">BUY</span>
                                    </div>
                                    <div className="flex items-center gap-2 px-4 py-2 bg-rose-50 rounded-2xl border border-rose-100">
                                        <div className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]" />
                                        <span className="text-[10px] font-black text-rose-700 uppercase">SELL</span>
                                    </div>
                                </div>
                            </div>

                            <div className="h-[400px] w-full relative z-10">
                                <ResponsiveContainer width="100%" height="100%">
                                    <ComposedChart data={performanceData}>
                                        <defs>
                                            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                                                <feGaussianBlur stdDeviation="6" result="blur" />
                                                <feComposite in="SourceGraphic" in2="blur" operator="over" />
                                            </filter>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                        <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{fontSize: 10, fill: '#94a3b8', fontWeight: 800}} dy={15} />
                                        <YAxis domain={['auto', 'auto']} axisLine={false} tickLine={false} tick={{fontSize: 10, fill: '#94a3b8'}} dx={-10} />
                                        <Tooltip contentStyle={{borderRadius: '28px', border: 'none', boxShadow: '0 30px 60px rgba(0,0,0,0.12)', padding: '24px'}} />
                                        <Line type="monotone" dataKey="price" stroke="#824199" strokeWidth={5} dot={false} style={{ filter: 'url(#glow)' }} />
                                        <Scatter dataKey="price">
                                            {performanceData.map((entry, index) => (
                                                <Cell key={index} fill={entry.action === 'BUY' ? '#10b981' : entry.action === 'SELL' ? '#f43f5e' : 'transparent'} r={entry.action ? 8 : 0} stroke="#fff" strokeWidth={3} />
                                            ))}
                                        </Scatter>
                                    </ComposedChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* [NEW] Strategy Pulse & Market Assessment */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            <div className="bg-[#1a0a24] p-10 rounded-[48px] border border-white/10 shadow-2xl relative overflow-hidden group">
                                <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-[#824199]/20 rounded-full blur-[60px]" />
                                <h3 className="text-xs font-bold text-white/30 uppercase tracking-[0.3em] mb-10 flex items-center gap-3">
                                    <Brain size={16} className="text-[#824199]" /> Neural Strategy Bias
                                </h3>
                                <div className="space-y-8 relative z-10">
                                    {agentBias.map((item) => (
                                        <div key={item.label}>
                                            <div className="flex justify-between text-[10px] font-black uppercase mb-4 tracking-[0.1em] text-white/60">
                                                <span className="flex items-center gap-2">{item.icon} {item.label}</span>
                                                <span className="text-white">{item.value}%</span>
                                            </div>
                                            <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                                                <div className={`h-full ${item.color} shadow-[0_0_12px_rgba(255,255,255,0.1)] transition-all duration-1000`} style={{ width: `${item.value}%` }} />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="bg-white p-10 rounded-[48px] border border-gray-100 shadow-sm flex flex-col justify-between group hover:shadow-xl transition-all">
                                <div>
                                    <h3 className="text-sm font-bold text-gray-900 uppercase tracking-widest flex items-center gap-3">
                                        <Gauge size={18} className="text-emerald-500" /> Market Volatility Pulse
                                    </h3>
                                    <p className="text-[10px] text-gray-400 font-medium mt-1 uppercase tracking-tighter pl-8">ATR Intelligence Feed</p>
                                </div>
                                <div className="py-12 text-center relative">
                                    <div className="absolute inset-0 flex items-center justify-center opacity-[0.02] pointer-events-none">
                                        <Activity size={200} />
                                    </div>
                                    <p className="text-7xl font-black text-gray-950 tracking-tighter">Low</p>
                                    <p className="text-[11px] text-emerald-500 font-black uppercase mt-4 tracking-[0.4em] flex items-center justify-center gap-3">
                                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" /> Strategic Entry Safe
                                    </p>
                                </div>
                                <div className="flex justify-between items-center pt-8 border-t border-gray-50 px-2">
                                    <MetricUnit label="Market ATR" val="124.50 ฿" />
                                    <MetricUnit label="Data Health" val="Premium" color="text-emerald-500" />
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* --- RIGHT: Performance & Insights (4/12) --- */}
                    <div className="lg:col-span-4 space-y-8">
                        
                        {/* Win Quality Pie with Central Insight */}
                        <div className="bg-white p-10 rounded-[56px] border border-gray-100 shadow-sm relative overflow-hidden flex flex-col items-center">
                            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.3em] mb-12 self-start flex items-center gap-3">
                                <PieIcon size={14} className="text-[#824199]" /> Win Quality Mix
                            </h3>
                            
                            <div className="h-[250px] w-full mb-10 relative">
                                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                    <p className="text-4xl font-black text-gray-900">84%</p>
                                    <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">Efficiency</p>
                                </div>
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie data={winLossData} innerRadius={85} outerRadius={105} paddingAngle={10} dataKey="value" stroke="none">
                                            {winLossData.map((entry, index) => (
                                                <Cell key={index} fill={entry.color} />
                                            ))}
                                        </Pie>
                                        <Tooltip />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>

                            <div className="w-full space-y-3">
                                {winLossData.map((item) => (
                                    <div key={item.name} className="flex justify-between items-center p-4 bg-gray-50/50 rounded-2xl border border-gray-100/50 hover:bg-gray-50 transition-colors cursor-default">
                                        <div className="flex items-center gap-3">
                                            <div className="w-2.5 h-2.5 rounded-full" style={{backgroundColor: item.color}} />
                                            <span className="text-[10px] font-black text-gray-500 uppercase tracking-tighter">{item.name}</span>
                                        </div>
                                        <span className="text-xs font-black text-gray-900">{item.value}%</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* AI Confidence Growth Chart */}
                        <div className="bg-gradient-to-br from-[#824199] to-[#2d1040] p-10 rounded-[56px] shadow-2xl text-white relative overflow-hidden">
                             <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full blur-3xl" />
                             <h3 className="text-xs font-bold text-white/40 uppercase tracking-[0.3em] mb-10">Neural Conviction</h3>
                             <div className="h-[140px] w-full mb-8">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={performanceData}>
                                        <defs>
                                            <linearGradient id="whiteGlow" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#fff" stopOpacity={0.4}/>
                                                <stop offset="95%" stopColor="#fff" stopOpacity={0}/>
                                            </linearGradient>
                                        </defs>
                                        <Area type="monotone" dataKey="conf" stroke="#fff" strokeWidth={3} fill="url(#whiteGlow)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                             </div>
                             <div className="flex justify-between items-end">
                                <div>
                                    <p className="text-xs text-white/50 font-bold uppercase tracking-widest">Avg. Confidence</p>
                                    <p className="text-4xl font-black mt-1">82.4%</p>
                                </div>
                                <Zap className="text-yellow-400 mb-1 animate-pulse" size={24} />
                             </div>
                        </div>

                    </div>
                </div>
            </div>
        </section>
    );
};

// --- High-End Reusable UI Atoms ---

const MetricUnit = ({ label, val, color = "text-gray-900" }: any) => (
    <div className="text-center md:text-left">
        <p className="text-[9px] text-gray-400 font-black uppercase tracking-[0.2em] mb-1">{label}</p>
        <p className={`text-sm font-black ${color} tracking-tight`}>{val}</p>
    </div>
);