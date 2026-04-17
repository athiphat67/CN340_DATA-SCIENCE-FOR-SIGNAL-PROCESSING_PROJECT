import React, { useState, useEffect } from 'react';
import { Wallet, ArrowUpRight, ArrowDownRight, Activity, Brain } from 'lucide-react';

const MiniBar = ({ heights }: { heights: number[] }) => (
  <div className="flex items-end gap-1 h-10">
    {heights.map((h, i) => (
      <div key={i} className="relative group w-1.5 h-full flex items-end">
         <span
           className="w-full rounded-sm transition-all duration-300"
           style={{
             height: `${h}%`,
             background: h > 75 ? 'linear-gradient(to top, #824199, #a855f7)' : '#f3f4f6',
             boxShadow: h > 75 ? '0 0 8px rgba(168, 85, 247, 0.3)' : 'none'
           }}
         />
      </div>
    ))}
  </div>
);

export const StatsStack = () => {
  // 1. State สำหรับ Portfolio
  const [portfolioData, setPortfolioData] = useState({
    available_cash: 0,
    unrealized_pnl: 0,
    pnl_percent: 0,
    trades_today: 0
  });

  // 2. State สำหรับ Latest Signal (Agent Conviction)
  const [signalData, setSignalData] = useState({
    confidence: 0,
    rationale: "Waiting for agent analysis...",
    signal: "HOLD"
  });

  const [isSyncing, setIsSyncing] = useState(true);

  // 3. ดึงข้อมูลจาก API ทั้ง 2 เส้นพร้อมกัน
  useEffect(() => {
    const fetchData = async () => {
      setIsSyncing(true);
      try {
        const [portRes, sigRes] = await Promise.all([
          fetch(`${import.meta.env.VITE_API_URL}/api/portfolio`),
          fetch(`${import.meta.env.VITE_API_URL}/api/latest-signal`)
        ]);

        if (portRes.ok) {
          const pData = await portRes.json();
          setPortfolioData(pData);
        }

        if (sigRes.ok) {
          const sData = await sigRes.json();
          setSignalData({
            // แปลงจาก 0.65 เป็น 65%
            confidence: sData.confidence <= 1 ? Math.round(sData.confidence * 100) : sData.confidence,
            rationale: sData.rationale || "No rationale provided.",
            signal: sData.signal || "HOLD"
          });
        }
      } catch (error) {
        console.error("Failed to fetch dashboard data:", error);
      } finally {
        setTimeout(() => setIsSyncing(false), 800);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000); // อัปเดตทุก 30 วิ
    return () => clearInterval(interval);
  }, []);

  const isPositivePnl = portfolioData.unrealized_pnl >= 0;
  const pnlColorClass = isPositivePnl ? "text-emerald-600 bg-emerald-50 border-emerald-100" : "text-rose-600 bg-rose-50 border-rose-100";
  const PnlIcon = isPositivePnl ? ArrowUpRight : ArrowDownRight;

  return (
    <div className="flex flex-col gap-4 h-full">

      {/* ================= กล่อง 1: Live Portfolio ================= */}
      <div className="flex-1 bg-gradient-to-br from-white to-emerald-50/30 rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.03)] border border-emerald-100/50 relative overflow-hidden flex flex-col justify-center">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
            <Wallet size={16} className="text-emerald-500" />
            Live Portfolio
          </h2>
          <span className="flex items-center gap-1.5 text-[10px] text-emerald-700 bg-emerald-100/50 border border-emerald-200/50 px-2 py-1 rounded-full font-bold uppercase tracking-wider">
            <span className={`w-1.5 h-1.5 rounded-full bg-emerald-500 ${isSyncing ? 'animate-pulse' : ''}`}></span>
            {isSyncing ? 'Syncing...' : 'Synced'}
          </span>
        </div>

        <div className="my-auto">
          <p className="text-xs text-gray-400 font-medium mb-1 uppercase tracking-widest">Available Cash</p>
          <p className="text-4xl font-black text-gray-900 tracking-tight">
            {portfolioData.available_cash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} 
            <span className="text-2xl text-gray-400 font-medium ml-2">฿</span>
          </p>
        </div>

        <div className="mt-4 pt-4 border-t border-emerald-100/50 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-500">Unrealized P&L</span>
          <div className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border shadow-sm ${pnlColorClass}`}>
            <PnlIcon size={16} strokeWidth={2.5} />
            <span className="text-sm font-bold">
              {isPositivePnl ? '+' : ''}{portfolioData.unrealized_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ฿ ({isPositivePnl ? '+' : ''}{portfolioData.pnl_percent}%)
            </span>
          </div>
        </div>
      </div>

      {/* ================= กล่อง 2: Agent Conviction ================= */}
      <div className="flex-1 bg-white rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-50 relative overflow-hidden flex flex-col justify-between">
        <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-[#824199]/5 to-transparent rounded-bl-full pointer-events-none" />
        
        <div className="flex items-center justify-between relative z-10">
          <h2 className="text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
             <Activity size={16} className="text-[#824199]" />
             Agent Conviction
          </h2>
          <span className="px-2.5 py-1 bg-gray-50 text-gray-600 text-[10px] font-bold rounded-lg border border-gray-100 shadow-sm">
             TRADES TODAY: {portfolioData.trades_today}
          </span>
        </div>

        <div className="flex items-end justify-between relative z-10 my-4">
          <div>
             <div className="flex items-baseline gap-1">
               {/* แสดงค่า Confidence แบบไดนามิก */}
               <p className="text-5xl font-black text-transparent bg-clip-text bg-gradient-to-r from-gray-900 to-gray-600 tracking-tight">
                  {signalData.confidence}
               </p>
               <span className="text-2xl font-bold text-gray-400">%</span>
             </div>
             <p className="text-xs text-gray-400 mt-1 font-medium">Confidence Level ({signalData.signal})</p>
          </div>
          {/* กราฟแท่งตกแต่ง (อาจจะเชื่อมกับประวัติ confidence ในอนาคตได้) */}
          <MiniBar heights={[30, 50, 45, 70, 60, 90, 100, 80, 55, signalData.confidence]} />
        </div>

        <div className="bg-gradient-to-br from-[#824199]/5 to-[#824199]/10 rounded-xl p-4 border border-[#824199]/10 relative z-10">
           <div className="flex items-center gap-2 mb-2 text-[#824199]">
              <Brain size={14} />
              <span className="text-[11px] font-bold uppercase tracking-wider">AI Reasoning</span>
           </div>
           {/* แสดง Rationale โดยใช้ line-clamp-3 เผื่อข้อความยาว (เช่นเคสล่าสุดของคุณที่ยาวมาก) */}
           <p className="text-[13px] text-gray-700 font-medium leading-relaxed italic line-clamp-3" title={signalData.rationale}>
             "{signalData.rationale}"
           </p>
        </div>
      </div>

    </div>
  );
};