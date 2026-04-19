// src/components/history/HistorySection.tsx
import React from 'react';
import { OverviewHeader } from '../overview/OverviewHeader';
import { TradeHistoryHeader } from './TradeHistoryHeader';
import { ArchiveViewer } from './ArchiveViewer'; // เปลี่ยนชื่อให้สื่อความหมาย
import { useArchiveData } from '../../../hooks/useArchiveData';
import { TrendingUp, Database, Loader2 } from 'lucide-react';

export const HistorySection = () => {
  const { summary, trades, signals, logs, isLoading } = useArchiveData();

  return (
    <section className="w-full min-h-screen pb-12 relative overflow-hidden" style={{ background: '#FCFBF7' }}>
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-[#824199]/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[10%] right-[-5%] w-[400px] h-[400px] bg-emerald-500/5 rounded-full blur-[100px] pointer-events-none" />

      <OverviewHeader />
      
      <div className="px-6 mt-12 relative z-20 max-w-7xl mx-auto">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-[60vh] text-[#824199]">
            <Loader2 className="animate-spin mb-4" size={40} />
            <p className="text-sm font-bold uppercase tracking-widest text-gray-500">Syncing Data Archive...</p>
          </div>
        ) : (
          <>
            <TradeHistoryHeader summary={summary} />
            
            <div className="mb-10 p-5 bg-white/60 backdrop-blur-md rounded-[24px] border border-white shadow-sm flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-[#824199] flex items-center justify-center text-white shadow-lg shadow-[#824199]/20">
                   <Database size={20} />
                </div>
                <div>
                   <p className="text-sm text-gray-900 font-bold">Comprehensive Archive Hub</p>
                   <p className="text-xs text-gray-500 font-medium mt-0.5">
                     Database contains <span className="font-bold text-[#824199]">{summary?.total_trades} user executions</span> and <span className="font-bold text-blue-600">{signals.length} AI recommendations</span>. State is <span className="font-bold text-emerald-600">{summary?.sync_status}</span>.
                   </p>
                </div>
              </div>
            </div>

            {/* ส่งข้อมูลทั้งหมดไปให้ ArchiveViewer จัดการเรื่อง Tab */}
            <ArchiveViewer trades={trades} signals={signals} logs={logs} />
          </>
        )}
      </div>
    </section>
  );
};