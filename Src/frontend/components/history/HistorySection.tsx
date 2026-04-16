import React from 'react';
import { OverviewHeader } from '../overview/OverviewHeader';
import { TradeHistoryHeader } from './TradeHistoryHeader';
import { TradeHistoryTable } from './TradeHistoryTable';
import { TrendingUp, Sparkles } from 'lucide-react'; // เพิ่มไอคอน Sparkles

export const HistorySection = () => {
  return (
    <section className="w-full min-h-screen pb-12 relative overflow-hidden" style={{ background: '#FCFBF7' }}>
      
      {/* 🪄 เคล็ดลับความสมบูรณ์แบบ: เพิ่ม Background Orbs 🪄 */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-[#824199]/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[10%] right-[-5%] w-[400px] h-[400px] bg-emerald-500/5 rounded-full blur-[100px] pointer-events-none" />

      <OverviewHeader />
      
      <div className="px-6 mt-12 relative z-20 max-w-7xl mx-auto">
        <TradeHistoryHeader />
        
        {/* แถบแจ้งเตือนที่ปรับปรุงให้ดูแพงขึ้น (Glassmorphism) */}
        <div className="mb-10 p-5 bg-white/60 backdrop-blur-md rounded-[24px] border border-white shadow-sm flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-[#824199] flex items-center justify-center text-white shadow-lg shadow-[#824199]/20">
               <Sparkles size={20} />
            </div>
            <div>
               <p className="text-sm text-gray-900 font-bold">Performance Insight</p>
               <p className="text-xs text-gray-500 font-medium mt-0.5">
                 Your AI Agent has executed <span className="font-bold text-[#824199]">142 trades</span> with a success rate of <span className="font-bold text-emerald-600">84%</span>.
               </p>
            </div>
          </div>
          <div className="hidden md:block">
             <TrendingUp className="text-emerald-500 opacity-20" size={40} />
          </div>
        </div>

        {/* ตารางประวัติการเทรด */}
        <TradeHistoryTable />
      </div>
    </section>
  );
};