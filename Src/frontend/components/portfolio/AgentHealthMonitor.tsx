import React from 'react';
import { Activity, Brain, Wifi, ShieldCheck, Clock } from 'lucide-react';

export const AgentHealthMonitor = () => {
  // ข้อมูลจาก Database (เหมือนเดิม แต่เราจะแสดงผลให้เข้าใจง่ายขึ้น)
  const systemStatus = {
    latency: 1240,         // ms
    tokens: 1550,          // tokens
    iterations: 3,         // cycles
    dataQuality: 'Good',   
    isWeekend: false,      
  };

  return (
    <div className="relative bg-gradient-to-br from-[#1a0a24]/90 via-[#0f172a]/95 to-[#1a0a24]/90 backdrop-blur-xl p-6 rounded-[32px] border border-white/10 shadow-2xl overflow-hidden flex flex-col h-full group">
      
      {/* Background Glow */}
      <div className="absolute -top-20 -right-20 w-48 h-48 bg-purple-500/10 blur-[60px] rounded-full pointer-events-none" />
      <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-emerald-500/5 blur-[50px] rounded-full pointer-events-none" />

      {/* Header - เปลี่ยนเป็นคำที่เป็นมิตรขึ้น */}
      <div className="flex items-center justify-between mb-6 relative z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
            <Brain size={16} className="text-purple-400" />
          </div>
          <h3 className="text-sm font-bold text-white/90 tracking-wide">AI Agent Status</h3>
        </div>
        <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Online</span>
        </div>
      </div>

      {/* Primary Metrics - แปลเป็นภาษาคน */}
      <div className="grid grid-cols-2 gap-4 relative z-10 mb-6">
        <div className="bg-white/5 border border-white/5 p-4 rounded-2xl hover:bg-white/10 transition-all">
          <p className="text-[9px] font-bold text-white/40 uppercase tracking-widest mb-1 flex items-center gap-1.5">
            <Clock size={10} /> Thinking Time
          </p>
          <div className="flex items-baseline gap-1">
             <p className="text-2xl font-black text-white">{(systemStatus.latency / 1000).toFixed(1)}</p>
             <span className="text-[10px] text-white/50 font-bold uppercase">Seconds</span>
          </div>
          <p className="text-[9px] text-emerald-400 mt-1">Fast & Responsive</p>
        </div>
        
        <div className="bg-white/5 border border-white/5 p-4 rounded-2xl hover:bg-white/10 transition-all">
          <p className="text-[9px] font-bold text-white/40 uppercase tracking-widest mb-1 flex items-center gap-1.5">
            <Activity size={10} /> Data Processed
          </p>
          <div className="flex items-baseline gap-1">
             <p className="text-2xl font-black text-white">~3</p>
             <span className="text-[10px] text-white/50 font-bold uppercase">Pages / Min</span>
          </div>
          <p className="text-[9px] text-purple-400 mt-1">Deep Analysis Mode</p>
        </div>
      </div>

      {/* Infrastructure Details - ลดความ Tech ลง */}
      <div className="space-y-3 relative z-10 flex-1 flex flex-col justify-end">
        <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
           <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-md bg-white/5 flex items-center justify-center">
                 <Wifi size={12} className="text-white/50" />
              </div>
              <div>
                 <p className="text-[10px] font-bold text-white/70 uppercase">Market Connection</p>
                 <p className="text-[9px] text-white/40">Real-time data feed</p>
              </div>
           </div>
           <p className="text-[10px] font-black text-emerald-400 uppercase">Stable</p>
        </div>

        <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
           <div className="flex items-center gap-3">
              <div className="w-6 h-6 rounded-md bg-white/5 flex items-center justify-center">
                 <Brain size={12} className="text-white/50" />
              </div>
              <div>
                 <p className="text-[10px] font-bold text-white/70 uppercase">Decision Steps</p>
                 <p className="text-[9px] text-white/40">Cross-checking logic</p>
              </div>
           </div>
           <p className="text-[10px] font-black text-white">{systemStatus.iterations} Steps</p>
        </div>

        {/* Data Quality Bar */}
        <div className="pt-3 border-t border-white/5 mt-1">
          <div className="flex justify-between items-center text-[9px] font-bold uppercase tracking-widest mb-2">
            <span className="text-white/40 flex items-center gap-1"><ShieldCheck size={10}/> Market Data Quality</span>
            <span className="text-emerald-400">{systemStatus.dataQuality}</span>
          </div>
          <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
             <div className="h-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)] w-[100%]" />
          </div>
        </div>
      </div>

    </div>
  );
};