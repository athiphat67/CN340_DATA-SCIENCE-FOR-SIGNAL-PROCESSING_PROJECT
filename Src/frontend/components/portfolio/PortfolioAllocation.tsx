import React from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import { PieChart as PieChartIcon } from 'lucide-react';

export const PortfolioAllocation = () => {
  const data = [
    { name: 'Available Cash', value: 845200, color: '#e5e7eb' }, // สีเทาอ่อน
    { name: 'Active Gold Positions', value: 400000, color: '#f9d443' }, // สีทอง
  ];

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-xl border border-gray-100 shadow-lg">
          <p className="text-[11px] font-bold text-gray-500 mb-1">{payload[0].name}</p>
          <p className="text-sm font-black text-gray-900">
            {payload[0].value.toLocaleString()} ฿
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white p-6 rounded-[24px] border border-gray-100 shadow-sm flex flex-col h-full">
      <div className="flex items-center gap-2 mb-6">
         <PieChartIcon size={18} className="text-[#824199]" />
         <h3 className="text-sm font-bold text-gray-900">Asset Allocation</h3>
      </div>
      
      <div className="w-full h-[250px] relative flex items-center justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              innerRadius={60}
              outerRadius={80}
              paddingAngle={5}
              dataKey="value"
              stroke="none"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        {/* ตรงกลางกราฟโดนัท */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
           <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Exposure</p>
           <p className="text-xl font-black text-gray-900">32%</p>
        </div>
      </div>

      {/* Legend */}
      <div className="flex justify-center gap-6 mt-4">
         {data.map((item, i) => (
            <div key={i} className="flex items-center gap-2">
               <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
               <p className="text-[11px] font-bold text-gray-500">{item.name}</p>
            </div>
         ))}
      </div>
    </div>
  );
};