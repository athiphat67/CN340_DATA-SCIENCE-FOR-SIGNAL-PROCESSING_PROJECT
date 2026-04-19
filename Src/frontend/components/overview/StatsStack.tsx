import React, { useState, useEffect } from 'react';
import { 
  Wallet, Brain, Target, Activity, 
  ArrowUpRight, ArrowDownRight, BarChart3, 
  Zap, PieChart, Coins, AlertCircle, Clock
} from 'lucide-react';

// 📈 Area Chart พร้อม Effect เรืองแสงและจุด (Dot) แสดงค่าล่าสุด
const ConfidenceAreaChart = ({ data }: { data: number[] }) => {
  // สร้างพิกัดให้เส้นกราฟ (X: 0-100, Y: 0-100)
  const points = data.map((h, i) => `${(i * (100 / (Math.max(data.length - 1, 1))))} ${100 - h}`).join(', ');
  
  // พิกัดของจุดสุดท้าย
  const lastPointX = 100;
  const lastPointY = 100 - data[data.length - 1];

  return (
    <div className="w-full h-24 mt-4 relative bg-purple-50/20 rounded-xl border border-purple-100/50 p-1 overflow-hidden">
      <svg viewBox="0 0 100 100" className="w-full h-full preserve-3d overflow-visible" preserveAspectRatio="none">
        <defs>
          <linearGradient id="grad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style={{ stopColor: '#824199', stopOpacity: 0.4 }} />
            <stop offset="100%" style={{ stopColor: '#824199', stopOpacity: 0 }} />
          </linearGradient>
          {/* Effect เงาเรืองแสง */}
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>
        
        {/* พื้นที่สี Gradient ใต้กราฟ */}
        <polyline fill="url(#grad)" stroke="none" points={`0 100, ${points}, 100 100`} />
        
        {/* เส้นกราฟหลัก */}
        <polyline 
          fill="none" 
          stroke="#824199" 
          strokeWidth="2.5" 
          points={points} 
          strokeLinejoin="round" 
          filter="url(#glow)" 
        />
        
        {/* จุด (Dot) ที่ค่าล่าสุด พร้อม Animation กระพริบ */}
        <circle 
          cx={lastPointX} 
          cy={lastPointY} 
          r="2.5" 
          fill="#fff" 
          stroke="#824199" 
          strokeWidth="1.5" 
          className="animate-pulse shadow-lg" 
        />
      </svg>
    </div>
  );
};

export const StatsStack = () => {
  const [portfolioData, setPortfolioData] = useState({
    available_cash: 0,
    unrealized_pnl: 0,
    pnl_percent: 0,
    trades_today: 0
  });

  const [signalData, setSignalData] = useState({
    confidence: 50,
    rationale: "Waiting for agent analysis...",
    signal: "HOLD"
  });

  // เก็บ History ของ Confidence 10 ค่าล่าสุด เพื่อวาดกราฟ
  const [confidenceHistory, setConfidenceHistory] = useState<number[]>(Array(10).fill(50));
  
  // สถานะการโหลดและ Error
  const [isSyncing, setIsSyncing] = useState(true);
  const [isError, setIsError] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsSyncing(true);
      setIsError(false);
      
      try {
        const [portRes, sigRes] = await Promise.all([
          fetch(`${import.meta.env.VITE_API_URL}/api/portfolio`),
          fetch(`${import.meta.env.VITE_API_URL}/api/latest-signal`)
        ]);

        if (portRes.ok) {
          const pData = await portRes.json();
          setPortfolioData(pData);
        } else {
          throw new Error('Portfolio API Error');
        }

        if (sigRes.ok) {
          const sData = await sigRes.json();
          const newConfidence = sData.confidence <= 1 ? Math.round(sData.confidence * 100) : sData.confidence;
          
          setSignalData({
            confidence: newConfidence,
            rationale: sData.rationale || "No rationale provided.",
            signal: sData.signal || "HOLD"
          });

          // อัปเดตกราฟ: เลื่อนกราฟไปทางซ้าย โดยตัดตัวแรกทิ้ง และเอาตัวใหม่ต่อท้าย
          setConfidenceHistory(prev => {
            const newHistory = [...prev.slice(1), newConfidence];
            return newHistory;
          });
        } else {
          throw new Error('Signal API Error');
        }

        setLastUpdated(new Date());
      } catch (error) {
        console.error("Failed to fetch dashboard data:", error);
        setIsError(true);
      } finally {
        setTimeout(() => setIsSyncing(false), 800);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000); // อัปเดตทุก 30 วินาที
    return () => clearInterval(interval);
  }, []);

  const isPositivePnl = portfolioData.unrealized_pnl >= 0;
  const PnlIcon = isPositivePnl ? ArrowUpRight : ArrowDownRight;

  // สีและ Effect ของปุ่ม Action
  const actionStyles = {
    BUY: 'text-emerald-600 bg-emerald-50 border-emerald-400 shadow-[0_0_15px_rgba(16,185,129,0.3)] animate-pulse',
    SELL: 'text-rose-600 bg-rose-50 border-rose-400 shadow-[0_0_15px_rgba(244,63,94,0.3)] animate-pulse',
    HOLD: 'text-gray-600 bg-gray-50 border-gray-200'
  };
  const currentActionStyle = actionStyles[signalData.signal as keyof typeof actionStyles] || actionStyles.HOLD;

  // Format เวลา Last Updated
  const timeString = lastUpdated 
    ? lastUpdated.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '--:--:--';

  return (
    <div className="flex flex-col gap-4 h-full font-sans">

      {/* 🟢 1. Live Portfolio */}
      <div className="flex-[1.5] bg-white rounded-[24px] p-6 shadow-[0_25px_60px_-12px_rgba(0,0,0,0.12)] border-2 border-emerald-200 ring-4 ring-emerald-50/60 flex flex-col relative overflow-hidden transition-all duration-300">
        
        {/* Header Section */}
        <div className="relative z-10 flex items-center justify-between mb-6">
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 bg-emerald-50 rounded-xl border border-emerald-100 shadow-sm">
              <Wallet size={20} className="text-emerald-600" />
            </div>
            <h2 className="text-[14px] font-bold text-gray-900 uppercase tracking-widest">Live Portfolio</h2>
          </div>
          
          {/* สถานะการ Sync พร้อม Timestamp และ Error Handling */}
          {isError ? (
            <span className="text-[10px] font-bold text-rose-700 bg-rose-100/50 px-3 py-1.5 rounded-lg border border-rose-200 flex items-center gap-1.5">
              <AlertCircle size={12} /> OFFLINE
            </span>
          ) : (
            <span className={`text-[10px] font-bold text-emerald-700 bg-emerald-100/50 px-3 py-1.5 rounded-lg border border-emerald-200 flex items-center gap-1.5`}>
              <span className={`w-2 h-2 bg-emerald-500 rounded-full shadow-[0_0_8px_rgba(16,185,129,0.5)] ${isSyncing ? 'animate-pulse' : ''}`} /> 
              {isSyncing ? 'SYNCING...' : `SYNCED ${timeString}`}
            </span>
          )}
        </div>
        
        <div className="relative z-10 space-y-6 flex-grow flex flex-col justify-between">
          
          {/* Main Balance Section */}
          <div className="bg-gradient-to-r from-emerald-50/50 to-transparent p-4 rounded-2xl border-l-4 border-emerald-500">
            <p className="text-[10px] text-gray-500 font-semibold uppercase tracking-[0.15em] mb-1">Available Cash</p>
            <div className="flex items-baseline gap-2">
              {!lastUpdated && isSyncing ? (
                <div className="h-10 w-48 bg-gray-200 animate-pulse rounded-lg" />
              ) : (
                <>
                  <p className="text-4xl font-black text-gray-900 tracking-tight">
                    {portfolioData.available_cash.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                  <span className="text-xl font-bold text-gray-400">฿</span>
                </>
              )}
            </div>
          </div>

          {/* 📊 Asset Allocation Detail */}
          <div className="space-y-3">
            <div className="flex justify-between items-end">
              <div className="flex items-center gap-2">
                <PieChart size={14} className="text-emerald-500" />
                <span className="text-[11px] font-bold text-gray-700 uppercase tracking-wider">Asset Allocation</span>
              </div>
              <span className="text-[10px] font-semibold text-gray-400 uppercase">Risk Level: Low</span>
            </div>
            <div className="h-3 w-full bg-gray-100 rounded-full overflow-hidden flex shadow-inner border border-gray-200/50">
              <div className="h-full bg-gradient-to-r from-emerald-400 to-emerald-600 w-[90%] shadow-[4px_0_10px_rgba(16,185,129,0.2)] transition-all duration-1000" />
              <div className="h-full bg-gray-200 w-[10%]" />
            </div>
            <div className="flex justify-between text-[10px] font-semibold">
              <span className="text-emerald-600 flex items-center gap-1"><Coins size={10}/> Gold (96.5%) · 90%</span>
              <span className="text-gray-400">Cash · 10%</span>
            </div>
          </div>

          {/* Metrics Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className={`p-4 rounded-2xl border-2 shadow-sm transition-colors duration-500 ${isPositivePnl ? 'bg-emerald-50/80 border-emerald-100' : 'bg-rose-50/80 border-rose-100'}`}>
              <div className="flex items-center justify-between mb-1">
                <p className={`text-[10px] font-bold uppercase ${isPositivePnl ? 'text-emerald-600/70' : 'text-rose-600/70'}`}>Floating PnL</p>
                <PnlIcon size={14} className={isPositivePnl ? 'text-emerald-500' : 'text-rose-500'} />
              </div>
              {!lastUpdated && isSyncing ? (
                 <div className="h-6 w-24 bg-gray-200/50 animate-pulse rounded" />
              ) : (
                <p className={`text-[18px] font-black ${isPositivePnl ? 'text-emerald-800' : 'text-rose-800'}`}>
                  {isPositivePnl ? '+' : ''}{portfolioData.unrealized_pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span className="text-[11px] font-bold">฿</span>
                </p>
              )}
            </div>
            <div className="bg-gray-50/80 p-4 rounded-2xl border-2 border-gray-100 shadow-sm">
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] font-bold text-gray-400 uppercase">Trades Today</p>
                <Activity size={14} className="text-gray-400" />
              </div>
               {!lastUpdated && isSyncing ? (
                 <div className="h-6 w-16 bg-gray-200 animate-pulse rounded" />
              ) : (
                <p className="text-[18px] font-black text-gray-800">{portfolioData.trades_today} <span className="text-[11px] font-bold text-gray-500">Orders</span></p>
              )}
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

      {/* 🟣 2. Decision Pulse */}
      <div className="flex-1 bg-white rounded-[24px] p-6 shadow-[0_20px_50px_-12px_rgba(0,0,0,0.1)] border-2 border-purple-200 ring-4 ring-purple-50/60 flex flex-col relative overflow-hidden transition-all duration-300">
        
        <div className="relative z-10 flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-purple-50 rounded-lg border border-purple-100 shadow-sm">
              <Brain size={18} className="text-[#824199]" />
            </div>
            <h2 className="text-[13px] font-bold text-gray-800 uppercase tracking-widest">Decision Pulse</h2>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-gray-400 bg-gray-50 px-2 py-1 rounded-md border border-gray-100">
             <Activity size={12} className="text-purple-400 animate-pulse" /> AI ENGINE
          </div>
        </div>

        <div className="relative z-10 flex flex-col flex-grow justify-between">
          
          <div className="flex items-center justify-between">
            <div>
               <p className="text-[9px] text-gray-400 font-semibold uppercase tracking-widest mb-1">Signal Confidence</p>
               <div className="flex items-baseline gap-1">
                 {!lastUpdated && isSyncing ? (
                    <div className="h-10 w-16 bg-gray-200 animate-pulse rounded-lg" />
                 ) : (
                   <p className="text-4xl font-black text-gray-900 tracking-tight transition-all duration-500">{signalData.confidence}<span className="text-xl text-purple-400">%</span></p>
                 )}
               </div>
            </div>
            
            {/* กล่อง Action เรืองแสง */}
            <div className={`text-center px-5 py-2 rounded-xl border-2 transition-all duration-500 ${currentActionStyle}`}>
               <p className="text-[16px] font-black tracking-wide">{signalData.signal}</p>
               <p className="text-[9px] font-bold uppercase opacity-80">Action</p>
            </div>
          </div>

          {/* Area Chart: ดึง History จริงมาแสดงผล */}
          <ConfidenceAreaChart data={confidenceHistory} />

        </div>
      </div>

    </div>
  );
};