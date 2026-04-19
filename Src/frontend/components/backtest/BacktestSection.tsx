import React, { useState } from 'react';
import { 
  TrendingUp, Target, ShieldAlert, Activity, 
  Download, ArrowUpRight 
} from 'lucide-react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, 
  Tooltip, ResponsiveContainer 
} from 'recharts';
import { OverviewHeader } from '../overview/OverviewHeader';

// ข้อมูล Equity Curve
const backtestData = [
  { date: "09-01", value: 1500.0 }, { date: "09-05", value: 1521.0 },
  { date: "09-15", value: 1515.5 }, { date: "09-30", value: 1580.8 },
  { date: "10-15", value: 1583.1 }, { date: "10-31", value: 1630.0 },
  { date: "11-15", value: 1640.0 }, { date: "11-29", value: 1642.1 }
];

export const BacktestSection = () => {
  return (
    <section 
      id="backtest" 
      // 💜 เปลี่ยน Gradient พื้นหลังให้เป็นโทนม่วงอ่อนๆ (Purple/Fuchsia)
      className="w-full min-h-screen pb-12 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-fuchsia-50 via-white to-slate-50"
    >
      <OverviewHeader />

      <div className="px-6 mt-8 relative z-20 max-w-7xl mx-auto">
        {/* Title & Actions */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-black text-gray-900 tracking-tight">Backtest Report</h2>
            <p className="text-sm text-gray-500 font-medium mt-1">Model: Gemini-3.1-Flash-Lite (30m Interval)</p>
          </div>
          <button className="flex items-center gap-2 bg-gradient-to-r from-purple-900 to-fuchsia-800 text-white px-5 py-2.5 rounded-xl text-sm font-bold hover:shadow-[0_8px_20px_rgba(168,85,247,0.25)] hover:-translate-y-0.5 transition-all duration-300">
            <Download size={16} /> Export CSV
          </button>
        </div>

        {/* KPI Cards Grid */}
        <div className="grid grid-cols-12 gap-5 mb-8">
          <BacktestMetricCard 
            label="Net PnL" 
            value="+142.06" 
            unit="THB"
            subValue="+9.47% Return"
            color="text-emerald-600"
            icon={<TrendingUp size={22} />}
          />
          <BacktestMetricCard 
            label="Win Rate" 
            value="44.04" 
            unit="%"
            subValue="96 / 122 Trades"
            // 💜 เปลี่ยนสี Icon ให้กลมกลืนกับธีม
            color="text-fuchsia-600" 
            icon={<Target size={22} />}
          />
          <BacktestMetricCard 
            label="Max Drawdown" 
            value="-1.14" 
            unit="%"
            subValue="Risk Adjusted: Low"
            color="text-rose-500"
            icon={<ShieldAlert size={22} />}
          />
          <BacktestMetricCard 
            label="Profit Factor" 
            value="1.87" 
            unit="x"
            subValue="Expectancy: 0.65"
            // 💜 เปลี่ยนสี Icon ให้กลมกลืนกับธีม
            color="text-purple-600"
            icon={<Activity size={22} />}
          />
        </div>

        {/* Main Chart Section */}
        <div className="grid grid-cols-12 gap-5">
          {/* 💜 อัปเดต Hover Border เป็นสีม่วง */}
          <div className="col-span-12 relative bg-white/80 backdrop-blur-xl rounded-[28px] p-8 shadow-[0_8px_30px_rgba(0,0,0,0.04)] border border-gray-200/60 hover:border-purple-400/60 transition-colors duration-500 overflow-hidden group">
            
            {/* 🌟 💜 Decorative Gradient Top Border (ไล่สีม่วง) */}
            <div className="absolute top-0 left-0 w-full h-[4px] bg-gradient-to-r from-purple-400 via-fuchsia-500 to-pink-500 opacity-80 group-hover:opacity-100 transition-opacity"></div>
            
            {/* 💜 Ambient Background Glow (แสงสีม่วงฟุ้งๆ) */}
            <div className="absolute -top-32 -right-32 w-96 h-96 bg-gradient-to-br from-purple-100/50 to-transparent rounded-full blur-3xl pointer-events-none"></div>

            <div className="relative z-10 flex items-center justify-between mb-8">
              <div>
                <h3 className="text-xl font-bold text-gray-900 tracking-tight">Portfolio Equity Curve</h3>
                <p className="text-sm text-gray-400 font-medium mt-1">Total Growth over 3 months</p>
              </div>
              {/* 💜 Tag ข้อความสีม่วง */}
              <div className="px-4 py-1.5 bg-white rounded-xl text-[11px] font-black text-purple-700 tracking-wider border border-purple-100 shadow-sm">
                SEPT 2025 - NOV 2025
              </div>
            </div>
            
            <div className="h-[380px] w-full relative z-10">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={backtestData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    {/* 💜 Gradient สีม่วงสำหรับพื้นที่ใต้กราฟ */}
                    <linearGradient id="backtestGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#c026d3" stopOpacity={0.3}/>  {/* fuchsia-600 */}
                      <stop offset="95%" stopColor="#c026d3" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    stroke="#94a3b8" 
                    fontSize={12} 
                    tickLine={false} 
                    axisLine={false} 
                    dy={10}
                  />
                  <YAxis 
                    hide 
                    domain={['dataMin - 20', 'dataMax + 20']} 
                  />
                  <Tooltip 
                    cursor={{ stroke: '#c026d3', strokeWidth: 1, strokeDasharray: '4 4' }}
                    contentStyle={{ 
                      borderRadius: '16px', 
                      border: '1px solid #fae8ff', // fuchsia-100
                      boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)', 
                      fontSize: '13px',
                      fontWeight: 'bold'
                    }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="value" 
                    stroke="#a21caf" // fuchsia-700
                    strokeWidth={4} 
                    fill="url(#backtestGradient)" 
                    dot={{ r: 5, fill: '#fff', strokeWidth: 3, stroke: '#c026d3' }} // ขอบม่วง ไส้ขาว
                    activeDot={{ r: 8, fill: '#86198f', strokeWidth: 2, stroke: '#fff' }} // ขอบขาว ไส้ม่วงเข้ม
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

// 🌟 💜 Component Metric Card โทนม่วง
const BacktestMetricCard = ({ label, value, unit, subValue, color, icon }: any) => (
  <div className="col-span-12 md:col-span-3 relative bg-white/80 backdrop-blur-md rounded-[24px] p-6 
    border border-gray-200/80 shadow-[0_4px_15px_rgba(0,0,0,0.02)] 
    transition-all duration-300 ease-out
    hover:-translate-y-1 hover:shadow-[0_12px_30px_rgba(192,38,211,0.15)] 
    hover:border-purple-300 hover:ring-4 hover:ring-purple-500/10 
    group overflow-hidden cursor-default"
  >
    {/* 💜 เอฟเฟกต์แสงสะท้อน (Glow) ด้านหลัง Card เมื่อ Hover (ม่วงอ่อน) */}
    <div className="absolute -top-10 -right-10 w-28 h-28 bg-gradient-to-br from-fuchsia-100 to-transparent rounded-full blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"></div>

    <div className="relative z-10 flex justify-between items-start mb-5">
      <div className={`p-3.5 rounded-2xl bg-gray-50/80 group-hover:bg-white group-hover:shadow-sm transition-all duration-300 ${color}`}>
        {icon}
      </div>
      <div className="p-2 bg-gray-50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <ArrowUpRight size={16} className="text-gray-400 group-hover:text-purple-500" />
      </div>
    </div>
    
    <div className="relative z-10">
      <p className="text-[11px] text-gray-500 uppercase font-black tracking-widest mb-1.5">{label}</p>
      <div className="flex items-baseline gap-1.5">
        <span className="text-3xl font-black text-gray-900 tracking-tight group-hover:text-purple-950 transition-colors">{value}</span>
        <span className={`text-sm font-bold ${color}`}>{unit}</span>
      </div>
      <p className="text-[12px] font-bold text-gray-400 mt-2 flex items-center gap-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${color.replace('text-', 'bg-')}`}></span>
        {subValue}
      </p>
    </div>
  </div>
);