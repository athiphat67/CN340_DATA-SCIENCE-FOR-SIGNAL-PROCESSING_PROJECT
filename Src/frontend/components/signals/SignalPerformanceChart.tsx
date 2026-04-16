import React from 'react';
import { TrendingUp } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const SignalPerformanceChart = () => {
  // ข้อมูลจำลองการเติบโตของพอร์ต (30 วัน)
  const data = [
    { date: '15 Mar', profit: 0 },
    { date: '20 Mar', profit: 4500 },
    { date: '25 Mar', profit: 3200 },
    { date: '30 Mar', profit: 12500 },
    { date: '04 Apr', profit: 10800 },
    { date: '09 Apr', profit: 24000 },
    { date: '14 Apr', profit: 38500 },
    { date: 'Today', profit: 45200 },
  ];

  // ปรับแต่งกล่องข้อความตอนเอาเมาส์ชี้ (Tooltip) ให้ดูพรีเมียม
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-xl border border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.12)]">
          <p className="text-[11px] font-bold text-gray-400 mb-1">{label}</p>
          <p className="text-sm font-black text-[#824199]">
            + {payload[0].value.toLocaleString()} ฿
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white p-6 rounded-[24px] border border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] mb-8">
      {/* ส่วนหัวของกราฟ */}
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <TrendingUp size={18} className="text-[#824199]" />
            Equity Growth Curve
          </h3>
          <p className="text-[11px] text-gray-400 font-medium mt-0.5 uppercase tracking-wider">
            Cumulative P&L Performance (Last 30 Days)
          </p>
        </div>
        <div className="text-left md:text-right">
          <p className="text-2xl font-black text-emerald-500">+18.4%</p>
          <p className="text-[10px] text-gray-400 font-bold uppercase">Monthly ROI</p>
        </div>
      </div>

      {/* พื้นที่วาดกราฟ */}
      <div className="h-[250px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            {/* สีไล่ระดับของกราฟ */}
            <defs>
              <linearGradient id="colorProfit" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#824199" stopOpacity={0.2}/>
                <stop offset="95%" stopColor="#824199" stopOpacity={0}/>
              </linearGradient>
            </defs>
            
            {/* เส้นตารางพื้นหลัง */}
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
            
            {/* แกน X (วันที่) */}
            <XAxis 
              dataKey="date" 
              axisLine={false} 
              tickLine={false} 
              tick={{ fontSize: 10, fill: '#9ca3af', fontWeight: 600 }}
              dy={10}
            />
            
            {/* แกน Y (จำนวนเงิน) */}
            <YAxis 
              axisLine={false} 
              tickLine={false} 
              tick={{ fontSize: 10, fill: '#9ca3af', fontWeight: 600 }}
              tickFormatter={(value) => `${(value / 1000)}k`} // แปลงตัวเลขยาวๆ เป็นหน่วย k (เช่น 45k)
              dx={-10}
            />
            
            {/* กล่องข้อความเมื่อเอาเมาส์ชี้ */}
            <Tooltip content={<CustomTooltip />} />
            
            {/* เส้นกราฟ */}
            <Area 
              type="monotone" 
              dataKey="profit" 
              stroke="#824199" 
              strokeWidth={3}
              fillOpacity={1} 
              fill="url(#colorProfit)" 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};