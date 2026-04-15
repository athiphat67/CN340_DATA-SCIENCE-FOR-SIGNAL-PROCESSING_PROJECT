import React from 'react';
import { Zap, BarChart, ShieldCheck } from 'lucide-react';

export const SignalAnalytics = () => {
  const stats = [
    { 
        // เปลี่ยนเป็นเรื่องความปลอดภัยของพอร์ต
        label: 'Max Drawdown', 
        value: '4.2%', 
        desc: 'Largest historical drop (Very Safe)', 
        icon: ShieldCheck, 
        color: 'text-emerald-600', 
        bg: 'bg-emerald-50' 
    },
    { 
        label: 'Avg. Risk/Reward', 
        value: '1 : 2.45', 
        desc: 'Target profit vs risk per trade', 
        icon: BarChart, 
        color: 'text-blue-600', 
        bg: 'bg-blue-50' 
    },
    { 
        label: 'Avg. Holding', 
        value: '18.5 Hours', 
        desc: 'Average trade duration', 
        icon: Zap, 
        color: 'text-amber-600', 
        bg: 'bg-amber-50' 
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