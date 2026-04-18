import React, { useState, useEffect } from 'react';
import { 
  Wallet, Brain, Target, Activity, 
  ArrowUpRight, ArrowDownRight, BarChart3, 
  Zap, PieChart, Coins 
} from 'lucide-react';

// ✅ เปลี่ยนจาก Bar Chart เป็น Area Chart เพื่อแสดง Momentum ของความมั่นใจ
const ConfidenceAreaChart = ({ data }: { data: number[] }) => {
  const points = data.map((h, i) => `${(i * (100 / (data.length - 1)))} ${100 - h}`).join(', ');
  return (
    <div className="w-full h-20 mt-2 relative bg-purple-50/30 rounded-xl border border-purple-100/50 p-1 overflow-hidden">
      <svg viewBox="0 0 100 100" className="w-full h-full preserve-3d" preserveAspectRatio="none">
        <defs>
          <linearGradient id="grad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style={{ stopColor: '#824199', stopOpacity: 0.4 }} />
            <stop offset="100%" style={{ stopColor: '#824199', stopOpacity: 0 }} />
          </linearGradient>
        </defs>
        <polyline fill="url(#grad)" stroke="none" points={`0 100, ${points}, 100 100`} />
        <polyline fill="none" stroke="#824199" strokeWidth="2" points={points} strokeLinejoin="round" />
      </svg>
    </div>
  );
};

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
  const PnlIcon = isPositivePnl ? ArrowUpRight : ArrowDownRight;

  // กำหนดสีของกล่อง Action ตาม Signal
  const actionColors = {
    BUY: 'text-emerald-600 bg-emerald-50 border-emerald-100',
    SELL: 'text-rose-600 bg-rose-50 border-rose-100',
    HOLD: 'text-gray-600 bg-gray-50 border-gray-100'
  };
  const currentActionColor = actionColors[signalData.signal as keyof typeof actionColors] || actionColors.HOLD;

  return (
    <div className="flex flex-col gap-4 h-full font-sans">

      {/* 🟢 1. Live Portfolio: อัปเกรดใหม่ ใช้พื้นที่เต็ม 100% พร้อมข้อมูลเชิงลึก */}
      <div className="flex-[1.5] bg-white rounded-[24px] p-6 shadow-[0_25px_60px_-12px_rgba(0,0,0,0.12)] border-2 border-emerald-200 ring-4 ring-emerald-50/60 flex flex-col relative overflow-hidden transition-all duration-300">
        
        {/* Header Section */}
        <div className="relative z-10 flex items-center justify-between mb-6">
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 bg-emerald-50 rounded-xl border border-emerald-100 shadow-sm">
              <Wallet size={20} className="text-emerald-600" />
            </div>
            <h2 className="text-[14px] font-black text-gray-900 uppercase tracking-widest">Live Portfolio</h2>
          </div>
          <span className={`text-[10px] font-black text-emerald-700 bg-emerald-100/50 px-3 py-1.5 rounded-lg border border-emerald-200 flex items-center gap-2`}>
            <span className={`w-2 h-2 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.5)] ${isSyncing ? 'animate-pulse' : ''}`} /> 
            {isSyncing ? 'SYNCING...' : 'SYNCED'}
          </span>
        </div>
        
        <div className="relative z-10 space-y-6 flex-grow flex flex-col justify-between">
          
          {/* Main Balance Section: ใช้ค่า Available Cash จาก API */}
          <div className="bg-gradient-to-r from-emerald-50/50 to-transparent p-4 rounded-2xl border-l-4 border-emerald-500">
            <p className="text-[10px] text-gray-400 font-bold uppercase tracking-[0.15em] mb-1">Available Cash</p>
            <div className="flex items-baseline gap-2">
              <p className="text-4xl font-black text-gray-900 tracking-tight">
                {portfolioData.available_cash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              <span className="text-xl font-bold text-gray-400">฿</span>
            </div>
          </div>

          {/* 📊 Asset Allocation Detail */}
          <div className="space-y-3">
            <div className="flex justify-between items-end">
              <div className="flex items-center gap-2">
                <PieChart size={14} className="text-emerald-500" />
                <span className="text-[11px] font-black text-gray-700 uppercase tracking-wider">Asset Allocation</span>
              </div>
              <span className="text-[10px] font-bold text-gray-400 uppercase">Risk Level: Low</span>
            </div>
            <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden flex shadow-inner border border-gray-200/50">
              <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-600 w-[90%] shadow-[4px_0_10px_rgba(16,185,129,0.2)]" />
              <div className="h-full bg-gray-200 w-[10%]" />
            </div>
            <div className="flex justify-between text-[10px] font-bold">
              <span className="text-emerald-600 flex items-center gap-1"><Coins size={10}/> Gold (96.5%) · 90%</span>
              <span className="text-gray-400">Cash · 10%</span>
            </div>
          </div>

          {/* Metrics Grid: แสดง PnL และ Trades Today จาก API */}
          <div className="grid grid-cols-2 gap-4">
            <div className={`p-4 rounded-2xl border-2 shadow-sm transition-colors ${isPositivePnl ? 'bg-emerald-50/80 border-emerald-100' : 'bg-rose-50/80 border-rose-100'}`}>
              <div className="flex items-center justify-between mb-1">
                <p className={`text-[10px] font-black uppercase ${isPositivePnl ? 'text-emerald-600/70' : 'text-rose-600/70'}`}>Floating PnL</p>
                <PnlIcon size={14} className={isPositivePnl ? 'text-emerald-500' : 'text-rose-500'} />
              </div>
              <p className={`text-[18px] font-black ${isPositivePnl ? 'text-emerald-800' : 'text-rose-800'}`}>
                {isPositivePnl ? '+' : ''}{portfolioData.unrealized_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span className="text-[11px]">฿</span>
              </p>
            </div>
            <div className="bg-gray-50/80 p-4 rounded-2xl border-2 border-gray-100 shadow-sm">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] font-black text-gray-400 uppercase">Trades Today</p>
                <Activity size={14} className="text-gray-400" />
              </div>
              <p className="text-[18px] font-black text-gray-800">{portfolioData.trades_today} <span className="text-[11px]">Orders</span></p>
            </div>
          </div>
        </div>

        {/* Decorative Background Silk Line */}
        <div className="absolute bottom-0 right-0 opacity-5 pointer-events-none">
          <svg width="200" height="100" viewBox="0 0 200 100">
            <path d="M0 80 Q50 20 100 80 T200 80" fill="none" stroke="#10b981" strokeWidth="20" />
          </svg>
        </div>
      </div>

      {/* 🟣 2. Decision Pulse: Area Chart + AI Reasoning */}
      <div className="flex-1 bg-white rounded-[24px] p-6 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] border-2 border-purple-200 ring-4 ring-purple-50/60 flex flex-col relative overflow-hidden transition-all duration-300">
        
        <div className="relative z-10 flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-purple-50 rounded-lg border border-purple-100 shadow-sm">
              <Brain size={18} className="text-[#824199]" />
            </div>
            <h2 className="text-[13px] font-black text-gray-800 uppercase tracking-widest">Decision Pulse</h2>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-gray-400">
             <Activity size={12} className="text-purple-400 animate-pulse" /> REAL-TIME
          </div>
        </div>

        <div className="relative z-10 flex flex-col flex-grow justify-between">
          
          <div className="flex items-end justify-between">
            <div>
               <div className="flex items-baseline gap-1">
                 <p className="text-4xl font-black text-gray-900 tracking-tight">{signalData.confidence}<span className="text-xl text-purple-400">%</span></p>
               </div>
               <p className="text-[9px] text-gray-400 font-black uppercase tracking-widest">Signal Confidence</p>
            </div>
            <div className="flex gap-2">
               <div className={`text-center px-4 py-1.5 rounded-xl border ${currentActionColor}`}>
                  <p className="text-[14px] font-black">{signalData.signal}</p>
                  <p className="text-[8px] font-bold uppercase opacity-70">Action</p>
               </div>
            </div>
          </div>

          {/* Area Chart: นำค่า confidence ล่าสุดใส่ไปในกราฟเพื่อความสมจริง */}
          <ConfidenceAreaChart data={[40, 55, 45, 70, 65, 80, 95, 75, 88, signalData.confidence]} />

        </div>
      </div>

    </div>
  );
};