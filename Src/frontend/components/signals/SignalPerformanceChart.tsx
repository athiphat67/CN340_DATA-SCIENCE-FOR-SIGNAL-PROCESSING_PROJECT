import React from 'react';
import { TrendingUp, Zap, MinusCircle, AlertTriangle, Clock, ChevronDown } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Dot,} from 'recharts';

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
    <div className="relative font-sans group">
      
      {/* ✨ Visual Connector: เส้นประเชื่อมโยงจาก 3 กล่องด้านบน */}
      <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-[90%] h-10 border-x-2 border-t-2 border-dashed border-gray-200 rounded-t-[40px] opacity-40 pointer-events-none" />
      <div className="absolute -top-4 left-1/2 -translate-x-1/2 text-gray-300 pointer-events-none">
        <ChevronDown size={20} className="animate-bounce" />
      </div>

      <div className="bg-white p-8 md:p-10 rounded-[48px] border-2 border-gray-100 shadow-[0_30px_70px_-20px_rgba(0,0,0,0.05)] relative z-10 transition-all">
        
        {/* ✨ Sub-box Header: ปรับให้ดูเป็นรายละเอียดเจาะลึก */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-12 gap-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
               <div className="w-1.5 h-6 bg-gradient-to-b from-purple-400 to-blue-400 rounded-full" />
               <h3 className="text-[13px] font-black text-gray-400 uppercase tracking-[0.2em]">Detailed Trace Analysis</h3>
            </div>
            <h2 className="text-2xl font-black text-gray-900 tracking-tight pl-4.5">
              Intelligence <span className="text-purple-600 italic">Performance</span> Mapping
            </h2>
          </div>

          <div className="flex bg-gray-50/80 backdrop-blur-sm p-1.5 rounded-2xl border border-gray-100 shadow-inner">
              <LegendItem color="bg-emerald-500" label="BUY" />
              <LegendItem color="bg-amber-500" label="HOLD" />
              <LegendItem color="bg-rose-500" label="SELL" />
          </div>
        </div>

        <div className="h-[350px] w-full">
          {/* ... ส่วน ResponsiveContainer และ Chart คงเดิมเพื่อความเสถียร ... */}
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              {/* ✨ ปรับ Gradient ให้ดูละมุนเข้ากับกล่อง P&L ใหม่ */}
              <defs>
                <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#824199" stopOpacity={0.1}/>
                  <stop offset="95%" stopColor="#824199" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" opacity={0.6}/>
              <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: '#94a3b8', fontWeight: 700 }} dy={15} interval="preserveStartEnd" minTickGap={50} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#94a3b8', fontWeight: 600 }} tickFormatter={(value) => `${(value / 1000)}k`} dx={-15} />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#824199', strokeWidth: 1.5, strokeDasharray: '6 6' }} />
              <Area type="monotone" dataKey="profit" stroke="#824199" strokeWidth={4} fillOpacity={1} fill="url(#colorProfit)" dot={renderCustomDot} activeDot={{ r: 7, strokeWidth: 4, stroke: '#fff', fill: '#824199' }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* ✨ Footer: ย้ำความเป็น Sub-box ด้วยการบอกว่าข้อมูลดึงมาจากไหน */}
        <div className="mt-10 pt-6 border-t border-gray-50 flex items-center justify-center gap-6 opacity-50">
           <div className="flex items-center gap-2 text-[10px] font-bold text-gray-400">
              <TrendingUp size={14} /> ANALYZING TRENDS
           </div>
           <div className="w-1 h-1 bg-gray-300 rounded-full" />
           <div className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
              Mapped from Master Log ID #590 - #599
           </div>
        </div>
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