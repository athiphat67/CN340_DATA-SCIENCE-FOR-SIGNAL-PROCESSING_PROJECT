import React from 'react';
import { History, ArrowDownRight, ArrowUpRight, PlusCircle } from 'lucide-react';

export const PortfolioRecentActivity = () => {
  const activities = [
    { id: 1, type: 'Close', asset: 'XAU/THB', detail: 'Closed BUY at Target', time: '2h ago', amount: '+4,500 ฿', color: 'text-emerald-500', bg: 'bg-emerald-50' },
    { id: 2, type: 'Open', asset: 'XAU/THB', detail: 'Opened new BUY', time: '5h ago', amount: '40 Baht', color: 'text-blue-500', bg: 'bg-blue-50' },
    { id: 3, type: 'Deposit', asset: 'THB', detail: 'Fund added via Bank', time: '1d ago', amount: '+100,000 ฿', color: 'text-[#824199]', bg: 'bg-[#824199]/10' },
    { id: 4, type: 'Close', asset: 'XAU/THB', detail: 'Closed SELL at Stop', time: '2d ago', amount: '-1,200 ฿', color: 'text-rose-500', bg: 'bg-rose-50' },
  ];

  return (
    <div className="bg-white rounded-[24px] shadow-sm border border-gray-100 overflow-hidden font-sans h-full flex flex-col">
      <div className="p-6 border-b border-gray-50 flex items-center justify-between">
         <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <History size={18} className="text-gray-400" />
            Recent Activity
         </h3>
         <button className="text-[10px] font-bold text-[#824199] hover:underline uppercase tracking-wider">
            View All
         </button>
      </div>

      <div className="p-6 flex-1 overflow-y-auto">
        <div className="space-y-6 relative">
          {/* Vertical Timeline Line */}
          <div className="absolute left-[15px] top-2 bottom-2 w-px bg-gray-100 -z-10"></div>

          {activities.map((act) => (
            <div key={act.id} className="flex gap-4 relative z-10 bg-white">
              <div className={`w-8 h-8 rounded-full ${act.bg} ${act.color} flex items-center justify-center shrink-0 border-4 border-white`}>
                {act.type === 'Close' && <ArrowDownRight size={14} />}
                {act.type === 'Open' && <ArrowUpRight size={14} />}
                {act.type === 'Deposit' && <PlusCircle size={14} />}
              </div>
              <div className="flex-1 pb-1">
                <div className="flex justify-between items-start mb-0.5">
                  <p className="text-sm font-bold text-gray-900">{act.type} {act.asset}</p>
                  <p className={`text-xs font-black ${act.color}`}>{act.amount}</p>
                </div>
                <div className="flex justify-between items-center">
                  <p className="text-[11px] text-gray-500 font-medium">{act.detail}</p>
                  <p className="text-[10px] text-gray-400 font-bold">{act.time}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};