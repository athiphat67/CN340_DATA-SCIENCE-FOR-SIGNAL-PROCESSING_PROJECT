import React from 'react';
import { Activity, Brain, Target } from 'lucide-react';

export const SignalAnalytics = () => {
  // ข้อมูลเหล่านี้ดึงมาจาก get_pnl_summary() และ get_signal_stats() ใน database.py ได้ทันที
  const stats = [
    { 
        label: 'Average P&L per Trade', 
        value: '+0.45%', 
        desc: 'Mean return across all executed trades', 
        icon: Activity, 
        color: 'text-emerald-600', 
        bg: 'bg-emerald-50' 
    },
    { 
        label: 'AI Avg. Confidence', 
        value: '82.4%', 
        desc: 'Historical prediction certainty', 
        icon: Brain, 
        color: 'text-[#824199]', 
        bg: 'bg-[#824199]/10' 
    },
    { 
        label: 'Total Executed Trades', 
        value: '142', 
        desc: 'Total BUY and SELL actions recorded', 
        icon: Target, 
        color: 'text-blue-600', 
        bg: 'bg-blue-50' 
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
      {stats.map((item, i) => (
        <div key={i} className="bg-white p-5 rounded-[20px] border border-gray-100 flex items-center gap-4 hover:shadow-md transition-shadow">
          <div className={`w-12 h-12 ${item.bg} ${item.color} rounded-2xl flex items-center justify-center shrink-0`}>
            <item.icon size={22} />
          </div>
          <div>
            <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-0.5">{item.label}</p>
            <p className="text-lg font-black text-gray-900 leading-tight">{item.value}</p>
            <p className="text-[11px] text-gray-500 font-medium">{item.desc}</p>
          </div>
        </div>
      ))}
    </div>
  );
};