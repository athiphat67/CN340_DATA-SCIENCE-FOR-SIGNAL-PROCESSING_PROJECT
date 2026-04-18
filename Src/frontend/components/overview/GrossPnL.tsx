import React from 'react';
import { PieChart, TrendingUp, TrendingDown, Globe, RefreshCcw, ArrowUpRight, ArrowDownLeft, Clock, BarChart3, Activity } from 'lucide-react';

// 1. สร้าง Interface ให้ตรงกับข้อมูลที่ส่งมาจาก FastAPI (Supabase)
interface GoldData {
  hsh_sell?: number;
  hsh_buy?: number;
  spot_xau?: number;
  usd_thb?: number;
}

export const GrossPnL = () => {
  // 2. สร้าง State สำหรับเก็บข้อมูลราคาทอง
  const [goldData, setGoldData] = useState<GoldData | null>(null);
  const [loading, setLoading] = useState(true);

  // 3. ฟังก์ชันดึงข้อมูลจาก FastAPI
  const fetchGoldPrice = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/gold-prices'); // เช็ค Port ให้ชัวร์
      const data = await response.json();
      console.log("Data from API:", data); // ดูใน Console ว่าชื่อ field ตรงกันไหม เช่น hsh_sell หรือ HSH_SELL
      setGoldData(data);
    } catch (error) {
      console.error("Fetch Error:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGoldPrice();
    // ดึงข้อมูลใหม่ทุกๆ 1 นาที
    const interval = setInterval(fetchGoldPrice, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col gap-4 h-full font-sans">

      {/* 🔄 Market Snapshot */}
      <div className="flex-1 rounded-[24px] p-6 shadow-xl border border-[#824199]/40 bg-gradient-to-br from-[#1e102a] to-[#36174d] flex flex-col justify-center relative overflow-hidden font-sans">
        <div className="relative z-10 flex items-center justify-between mb-6">
          <div className="flex flex-col">
            <h2 className="text-xs font-bold text-purple-300/80 uppercase tracking-[0.2em] mb-1">Hua Seng Heng</h2>
            <h2 className="text-[15px] font-black text-white uppercase tracking-widest flex items-center gap-2">
              <Globe size={16} className="text-purple-400" />
              Market Snapshot
            </h2>
          </div>
          <button className="bg-white/10 backdrop-blur-md border border-white/20 p-2.5 rounded-xl text-white hover:bg-white/20 transition-all shadow-md">
            <RefreshCcw size={16} />
          </button>
        </div>

        <div className="relative z-10 my-auto grid grid-cols-2 gap-4">
          <div className="bg-white/10 border border-white/10 rounded-2xl p-4 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.12)]">
            <p className="text-[11px] text-purple-200 font-bold mb-2 uppercase tracking-widest flex items-center gap-1.5 opacity-90">
              <ArrowUpRight size={14} className="text-rose-400" /> HSH Sell
            </p>
            <div className="flex items-baseline gap-1.5">
              <p className="text-[28px] font-bold text-white tracking-normal leading-none">
                {goldData && goldData.hsh_sell !== undefined
                  ? goldData.hsh_sell.toLocaleString()
                  : '---'}
              </p>
              <span className="text-sm text-purple-300 font-bold">฿</span>
            </div>
          </div>

          <div className="bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md shadow-[0_8px_32px_rgba(0,0,0,0.12)]">
            <p className="text-[11px] text-purple-200 font-bold mb-2 uppercase tracking-widest flex items-center gap-1.5 opacity-90">
              <ArrowDownLeft size={14} className="text-emerald-400" /> HSH Buy
            </p>
            <div className="flex items-baseline gap-1.5">
              <p className="text-[28px] font-bold text-white tracking-normal leading-none">
                {goldData && goldData.hsh_buy !== undefined
                  ? goldData.hsh_buy.toLocaleString()
                  : '---'}
              </p>
              <span className="text-sm text-purple-300 font-bold">฿</span>
            </div>
          </div>
        </div>

        <div className="relative z-10 mt-6 grid grid-cols-2 gap-4 bg-black/20 p-3.5 rounded-xl border border-white/5 shadow-inner">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-purple-200/70 uppercase tracking-widest mb-1">Spot (XAU/USD)</span>
            <span className="text-[15px] font-bold text-white tracking-wide">$2,350.50</span>
          </div>
          <div className="flex flex-col border-l border-white/10 pl-4">
            <span className="text-[10px] font-bold text-purple-200/70 uppercase tracking-widest mb-1">USD/THB</span>
            <span className="text-[15px] font-bold text-white tracking-wide">36.75 <span className="text-[11px] text-purple-300">฿</span></span>
          </div>
        </div>
      </div>

      {/* 🔄 2. เปลี่ยนเป็นกล่อง MARKET STATE: พร้อม Double Border เข้มชัดเจน */}
      <div className="flex-1 bg-white rounded-[24px] p-6 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.1)] flex flex-col border-2 border-purple-200 ring-4 ring-purple-100/50 transition-all duration-300">
        
        {/* Header ส่วน MARKET STATE */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[14px] font-black text-gray-900 uppercase tracking-widest flex items-center gap-2">
            <Activity size={18} className="text-[#824199]" />
            Market State
          </h2>
          <div className="flex items-center gap-1.5 text-[10px] font-bold text-gray-400 bg-gray-50 px-2 py-1 rounded-md border border-gray-100">
             <Clock size={12} /> 16:44 | 15m
          </div>
        </div>

        {/* Technical Summary Bars */}
        <div className="space-y-4 overflow-y-auto pr-1">
          
          {/* Prices Section */}
          <div className="bg-gray-50/80 rounded-xl p-3 border border-gray-100 shadow-sm">
            <div className="flex justify-between items-end mb-2">
               <span className="text-[10px] font-bold text-gray-400 uppercase tracking-tighter">Gold (USD)</span>
               <span className="text-sm font-black text-[#824199]">$4,833.95/oz</span>
            </div>
            <div className="flex justify-between items-center pt-2 border-t border-gray-200/50">
               <div className="flex flex-col">
                 <span className="text-[9px] font-bold text-emerald-600 uppercase">Buy Now</span>
                 <span className="text-[15px] font-black text-gray-900">฿73,100</span>
               </div>
               <div className="flex flex-col items-end">
                 <span className="text-[9px] font-bold text-rose-500 uppercase">Sell Now</span>
                 <span className="text-[15px] font-black text-gray-900">฿72,900</span>
               </div>
            </div>
          </div>

          {/* Technical Indicators Grid */}
          <div className="grid grid-cols-2 gap-2">
             <div className="bg-rose-50/50 border border-rose-100 rounded-xl p-3">
                <span className="text-[9px] font-bold text-rose-400 uppercase block mb-1">RSI(14)</span>
                <div className="flex items-center gap-2">
                   <span className="text-lg font-black text-rose-600">27.78</span>
                   <span className="text-[8px] bg-rose-600 text-white px-1.5 py-0.5 rounded uppercase font-black">Oversold</span>
                </div>
             </div>
             <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-3">
                <span className="text-[9px] font-bold text-emerald-400 uppercase block mb-1">Trend</span>
                <div className="flex items-center gap-2">
                   <TrendingUp size={14} className="text-emerald-600" />
                   <span className="text-[12px] font-black text-emerald-700 uppercase">Uptrend</span>
                </div>
             </div>
          </div>

          {/* Extended Technicals */}
          <div className="bg-white border-2 border-gray-50 rounded-xl p-3 shadow-sm">
             <div className="flex items-center gap-2 mb-2">
                <BarChart3 size={14} className="text-purple-400" />
                <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">Indicator Details</span>
             </div>
             <div className="space-y-2">
                <div className="flex justify-between text-[11px]">
                   <span className="text-gray-400 font-medium">MACD Hist</span>
                   <span className="text-rose-500 font-bold">-6.0807 [Bearish]</span>
                </div>
                <div className="flex justify-between text-[11px]">
                   <span className="text-gray-400 font-medium">EMA 20/50</span>
                   <span className="text-gray-700 font-bold">4871 / 4862</span>
                </div>
                <div className="flex justify-between text-[11px]">
                   <span className="text-gray-400 font-medium">Bollinger Upper</span>
                   <span className="text-gray-700 font-bold">4904.41</span>
                </div>
             </div>
          </div>

        </div>

        {/* Footer Info */}
        <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between opacity-60">
           <span className="text-[9px] font-bold text-gray-400 uppercase">Spread ≈ 200.0 THB</span>
           <span className="text-[9px] font-mono text-gray-400 italic">Snapshot: 2026-04-18</span>
        </div>

      </div>

    </div>
  );
};