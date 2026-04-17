import React from 'react';
import { TrendingUp, Zap, MinusCircle, AlertTriangle, Clock } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Dot } from 'recharts';

export const SignalPerformanceChart = () => {
  // 1. จำลองข้อมูลที่มีหลายสัญญาณในหนึ่งวัน (อิงจากโครงสร้าง run_at ใน database.py)
  const data = [
    { time: '15 Apr 09:00', profit: 12000, signalId: 590, action: 'BUY' },
    { time: '15 Apr 10:30', profit: 11800, signalId: 591, action: 'HOLD' },
    { time: '15 Apr 13:15', profit: 14500, signalId: 592, action: 'SELL' },
    { time: '15 Apr 16:45', profit: 14500, signalId: 593, action: 'HOLD' },
    { time: '15 Apr 20:00', profit: 18400, signalId: 594, action: 'BUY' },
    { time: '16 Apr 08:00', profit: 18000, signalId: 595, action: 'HOLD' },
    { time: '16 Apr 11:20', profit: 22500, signalId: 596, action: 'SELL' },
    { time: '16 Apr 14:00', profit: 21000, signalId: 597, action: 'SELL' },
    { time: 'Today 09:15', profit: 25200, signalId: 598, action: 'BUY' },
    { time: 'Today 10:45', profit: 25200, signalId: 599, action: 'HOLD' },
  ];

  // 2. Custom Tooltip ที่ละเอียดขึ้น บอกเวลาชัดเจน
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const info = payload[0].payload;
      return (
        <div className="bg-[#1a0a24]/95 backdrop-blur-xl p-5 rounded-[24px] border border-white/10 shadow-2xl transition-all">
          <div className="flex items-center justify-between gap-8 mb-3">
            <div className="flex items-center gap-2 text-gray-400">
               <Clock size={12} />
               <p className="text-[10px] font-bold uppercase tracking-widest">{info.time}</p>
            </div>
            <span className="text-[10px] font-mono text-purple-300 bg-white/5 px-2 py-0.5 rounded-md border border-white/5">
                ID: #{info.signalId}
            </span>
          </div>
          
          <p className="text-2xl font-black text-white mb-3 leading-none">
             {payload[0].value.toLocaleString()} <span className="text-sm font-normal text-white/40">฿</span>
          </p>

          <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-black uppercase border shadow-lg ${
            info.action === 'BUY' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
            info.action === 'SELL' ? 'bg-rose-500/20 text-rose-400 border-rose-500/30' :
            'bg-amber-500/20 text-amber-400 border-amber-500/30'
          }`}>
            {info.action === 'BUY' && <Zap size={12} fill="currentColor" />}
            {info.action === 'SELL' && <AlertTriangle size={12} fill="currentColor" />}
            {info.action === 'HOLD' && <MinusCircle size={12} fill="currentColor" />}
            {info.action} SIGNAL
          </div>
        </div>
      );
    }
    return null;
  };

  const renderCustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    let dotFill = payload.action === 'BUY' ? '#10b981' : payload.action === 'SELL' ? '#f43f5e' : '#f59e0b';

    return (
      <Dot 
        cx={cx} cy={cy} r={4.5} fill={dotFill} stroke="#fff" strokeWidth={2} 
        className="drop-shadow-[0_0_4px_rgba(0,0,0,0.2)]" 
      />
    );
  };

  return (
    <div className="bg-white p-8 md:p-10 rounded-[48px] border border-gray-100 shadow-[0_20px_60px_rgba(0,0,0,0.03)] mb-10 font-sans group">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-12 gap-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
             <div className="w-1.5 h-6 bg-[#824199] rounded-full shadow-[0_0_12px_rgba(130,65,153,0.4)]" />
             <h3 className="text-base font-black text-gray-900 tracking-tight">Intelligence Performance Trace</h3>
          </div>
          <p className="text-[11px] text-gray-400 font-bold mt-1 uppercase tracking-[0.2em] pl-4.5">
            High-frequency signal mapping (Time-Series)
          </p>
        </div>
        <div className="flex bg-gray-50/80 backdrop-blur-sm p-1.5 rounded-2xl border border-gray-100 shadow-inner">
            <LegendItem color="bg-emerald-500" label="BUY" />
            <LegendItem color="bg-amber-500" label="HOLD" />
            <LegendItem color="bg-rose-500" label="SELL" />
        </div>
      </div>

      <div className="h-[350px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#824199" stopOpacity={0.15}/>
                <stop offset="95%" stopColor="#824199" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" opacity={0.6}/>
            <XAxis 
              dataKey="time" 
              axisLine={false} 
              tickLine={false} 
              tick={{ fontSize: 9, fill: '#94a3b8', fontWeight: 700 }}
              dy={15}
              // 🚀 ปรับให้แสดง label เฉพาะจุดที่เหมาะสมเพื่อไม่ให้แน่นเกินไป
              interval="preserveStartEnd"
              minTickGap={50}
            />
            <YAxis 
              axisLine={false} 
              tickLine={false} 
              tick={{ fontSize: 10, fill: '#94a3b8', fontWeight: 600 }}
              tickFormatter={(value) => `${(value / 1000)}k`}
              dx={-15}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#824199', strokeWidth: 1.5, strokeDasharray: '6 6' }} />
            <Area 
              type="monotone" 
              dataKey="profit" 
              stroke="#824199" 
              strokeWidth={4}
              fillOpacity={1} 
              fill="url(#colorProfit)"
              dot={renderCustomDot}
              activeDot={{ r: 7, strokeWidth: 4, stroke: '#fff', fill: '#824199', className: 'shadow-2xl' }}
              style={{ filter: 'drop-shadow(0px 12px 15px rgba(130,65,153,0.3))' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

const LegendItem = ({ color, label }: any) => (
    <div className="flex items-center gap-2 px-3 py-1.5">
        <div className={`w-2 h-2 rounded-full ${color} shadow-[0_0_8px_rgba(0,0,0,0.1)]`} />
        <span className="text-[10px] font-black text-gray-500 tracking-widest uppercase">{label}</span>
    </div>
);