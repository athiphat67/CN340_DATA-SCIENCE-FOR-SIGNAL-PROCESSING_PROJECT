import React, { useEffect, useState } from 'react';
import { PieChart, TrendingUp, Minus, TrendingDown, Globe, RefreshCcw, ArrowUpRight, ArrowDownLeft } from 'lucide-react';

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
    <div className="flex flex-col gap-4 h-full">

      {/* 🔄 Market Snapshot */}
      <div className="flex-1 rounded-[24px] p-6 shadow-xl border border-[#824199]/40 bg-gradient-to-br from-[#1e102a] to-[#36174d] flex flex-col justify-center relative overflow-hidden font-sans">
        <div className="relative z-10 flex items-center justify-between mb-6">
          <div className="flex flex-col">
            <h2 className="text-xs font-bold text-purple-300 uppercase tracking-[0.15em] mb-1">Hua Seng Heng</h2>
            <h2 className="text-[15px] font-bold text-white uppercase tracking-widest flex items-center gap-2">
              <Globe size={16} className="text-purple-300" />
              Market Snapshot
            </h2>
          </div>
          <button
            onClick={fetchGoldPrice} // กด Refresh เพื่อดึงข้อมูลใหม่
            disabled={loading}
            className={`bg-purple-500/20 border border-purple-400/30 p-2.5 rounded-xl text-purple-100 hover:bg-purple-500/30 transition-colors ${loading ? 'animate-spin' : ''}`}
          >
            <RefreshCcw size={16} />
          </button>
        </div>

        <div className="relative z-10 my-auto grid grid-cols-2 gap-4">
          {/* HSH SELL */}
          <div className="bg-white/10 border border-white/20 rounded-2xl p-4 backdrop-blur-md shadow-inner">
            <p className="text-[11px] text-purple-100 font-bold mb-2 uppercase tracking-widest flex items-center gap-1.5 opacity-90">
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

          {/* HSH BUY */}
          <div className="bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md shadow-inner">
            <p className="text-[11px] text-purple-100 font-bold mb-2 uppercase tracking-widest flex items-center gap-1.5 opacity-90">
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

        <div className="relative z-10 mt-6 grid grid-cols-2 gap-4 bg-black/20 p-3.5 rounded-xl border border-white/5">
          <div className="flex flex-col">
            <span className="text-[10px] font-bold text-purple-200 uppercase tracking-widest mb-1">Spot (XAU/USD)</span>
            <span className="text-[15px] font-bold text-white tracking-wide">
              {goldData?.spot_price !== undefined
                ? `$${goldData.spot_price.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                : '---'}
            </span>
          </div>
          <div className="flex flex-col border-l border-white/10 pl-4">
            <span className="text-[10px] font-bold text-purple-200 uppercase tracking-widest mb-1">USD/THB</span>
            <span className="text-[15px] font-bold text-white tracking-wide">
              {goldData?.usd_thb !== undefined
                ? goldData.usd_thb.toFixed(2)
                : '---'}
            </span>
          </div>
        </div>
      </div>

      {/* 2. กล่อง Market Bias (ใส่ flex-1 ทำให้ขอบล่างไปชนขอบล่างของ Gold Inventory เป๊ะ) */}
      <div className="flex-1 bg-white rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-50 flex flex-col justify-between">

        <div className="flex items-center justify-between mb-2">
          <h2 className="text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
            <PieChart size={16} className="text-gray-400" />
            Market Bias
          </h2>
        </div>

        {/* Stacked Bar แบบใหญ่ขึ้นเพื่อให้เด่น */}
        <div className="my-2">
          <div className="h-6 flex rounded-full overflow-hidden shadow-inner mb-2">
            <div className="bg-gradient-to-r from-emerald-400 to-emerald-500 h-full relative" style={{ width: '75%' }}>
              <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white/80">75%</span>
            </div>
            <div className="bg-gradient-to-r from-amber-300 to-yellow-400 h-full relative" style={{ width: '20%' }}></div>
            <div className="bg-gradient-to-r from-rose-400 to-rose-500 h-full relative" style={{ width: '5%' }}></div>
          </div>
        </div>

        {/* Breakdown List - ช่วยเติมเต็มพื้นที่แนวตั้งให้สวยงาม */}
        <div className="space-y-3 mt-auto">
          <div className="flex items-center justify-between p-3 rounded-[16px] bg-emerald-50/50 border border-emerald-50 hover:border-emerald-100 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center shadow-sm">
                <TrendingUp size={18} />
              </div>
              <div>
                <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Bullish</p>
                <p className="text-sm font-bold text-gray-900 leading-none">BUY Signals</p>
              </div>
            </div>
            <span className="text-xl font-black text-emerald-600">75%</span>
          </div>

          <div className="flex items-center justify-between p-3 rounded-[16px] bg-yellow-50/50 border border-yellow-50 hover:border-yellow-100 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-yellow-100 text-yellow-600 flex items-center justify-center shadow-sm">
                <Minus size={18} />
              </div>
              <div>
                <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Neutral</p>
                <p className="text-sm font-bold text-gray-900 leading-none">HOLD Signals</p>
              </div>
            </div>
            <span className="text-xl font-black text-yellow-600">20%</span>
          </div>

          <div className="flex items-center justify-between p-3 rounded-[16px] bg-rose-50/50 border border-rose-50 hover:border-rose-100 transition-colors">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center shadow-sm">
                <TrendingDown size={18} />
              </div>
              <div>
                <p className="text-[11px] text-gray-400 font-bold uppercase tracking-wider mb-0.5">Bearish</p>
                <p className="text-sm font-bold text-gray-900 leading-none">SELL Signals</p>
              </div>
            </div>
            <span className="text-xl font-black text-rose-600">5%</span>
          </div>
        </div>

      </div>

    </div>
  );
};