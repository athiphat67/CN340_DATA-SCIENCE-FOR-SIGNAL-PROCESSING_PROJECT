import React from 'react';
import { Activity, Brain, Wifi, Clock, Zap, Target } from 'lucide-react';

export const AgentHealthMonitor = () => {
  // Mock data for the system status
  const systemStatus = {
    latency: 1240,         // in milliseconds
    iterations: 3,         // decision layers
    dataQuality: 'High',   // market data integrity
    lastUpdate: '1s ago'   // freshness of data
  };

  return (
    <div className="relative bg-white rounded-[32px] border border-gray-100 shadow-[0_15px_35px_rgba(0,0,0,0.025)] p-6 overflow-hidden group hover:border-purple-200 transition-all duration-500 hover:shadow-[0_20px_50px_rgba(130,65,153,0.05)]">
      
      {/* Subtle Background Glow */}
      <div className="absolute top-0 right-0 w-48 h-48 bg-[#824199]/5 blur-[90px] rounded-full pointer-events-none" />

      <div className="flex flex-col gap-6 relative z-10">
        {/* Header Layout ใหม่: เน้นสถานะและไอคอนที่ดู professional */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-50 border border-emerald-100/60 rounded-full w-fit mb-2">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <p className="text-[10px] font-black text-emerald-600 uppercase tracking-widest">Active & Optimized</p>
            </div>
            <h3 className="text-sm font-black text-gray-900 tracking-tight">Neural Engine</h3>
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Version 3.2.0 <span className="text-gray-200">|</span> {systemStatus.lastUpdate}</p>
          </div>
          
          {/* ไอคอนที่ดู Professional และขนาดพอดี */}
          <div className="relative group/icon">
            <div className="absolute inset-0 bg-purple-500/10 blur-xl rounded-full opacity-50 group-hover/icon:opacity-100 animate-pulse" />
            <div className="w-14 h-14 rounded-3xl bg-gray-50 flex items-center justify-center border border-gray-100 group-hover:border-[#824199]/10 group-hover:bg-white transition-all duration-300 relative shadow-inner">
              <Brain size={28} className="text-gray-300 group-hover:text-[#824199] transition-colors" />
            </div>
            {/* สัญลักษณ์ความเร็วเล็กๆ */}
            <div className="absolute -bottom-2 -left-2 w-6 h-6 bg-white rounded-full flex items-center justify-center border border-gray-100 shadow-sm">
                <Zap size={12} className="text-amber-400 fill-amber-400" />
            </div>
          </div>
        </div>

        {/* ส่วนข้อมูลหลัก: ปรับเป็นแถวเรียบๆ เหมือนกล่องด้านล่าง */}
        <div className="space-y-3">
          {[
            { icon: <Clock size={14} />, label: 'Latency (Avg)', value: `${(systemStatus.latency / 1000).toFixed(1)}s`, color: 'text-purple-400' },
            { icon: <Wifi size={14} />, label: 'Market API Stream', value: 'Stable', color: 'text-emerald-400' },
            { icon: <Activity size={14} />, label: 'Logic Steps', value: `${systemStatus.iterations} Layers`, color: 'text-blue-400' },
            { icon: <Target size={14} />, label: 'Objective Accuracy', value: '98.5%', color: 'text-rose-400' }
          ].map((item, i) => (
            <div key={i} className="flex items-center justify-between p-4 bg-gray-50/50 rounded-2xl hover:bg-gray-100 transition-colors border border-gray-100/50">
              <div className="flex items-center gap-3.5">
                <div className={`${item.color} w-8 h-8 rounded-xl bg-white flex items-center justify-center shadow-inner border border-gray-100`}>
                    {item.icon}
                </div>
                <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">{item.label}</p>
              </div>
              <p className="text-xs font-black text-gray-900 pr-2">{item.value}</p>
            </div>
          ))}
        </div>

        {/* ส่วนสถานะ Data Quality ด้านล่าง */}
        <div className="pt-3 border-t border-gray-100/50 mt-1">
          <div className="flex justify-between items-center text-[10px] font-bold uppercase tracking-widest mb-3">
            <span className="text-gray-400 flex items-center gap-1.5"><Activity size={12} className="text-gray-300"/> Data Quality Score</span>
            <span className="text-emerald-500 font-extrabold">{systemStatus.dataQuality}</span>
          </div>
          <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden p-[2px]">
             <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full w-[95%] shadow-[0_0_10px_rgba(16,185,129,0.3)]"></div>
          </div>
        </div>
      </div>
    </div>
  );
};