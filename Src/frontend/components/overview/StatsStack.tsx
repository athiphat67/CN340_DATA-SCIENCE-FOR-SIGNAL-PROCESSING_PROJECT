import React from 'react';
import { Wallet, Globe, ArrowUpRight, ArrowDownLeft, RefreshCcw } from 'lucide-react';

export const StatsStack = () => {
  return (
    <div className="flex flex-col gap-4 h-full">
      
      {/* กล่อง 1: Live Portfolio (เขียว) */}
      <div className="flex-1 bg-gradient-to-br from-white to-emerald-50/30 rounded-[24px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.03)] border border-emerald-100/50 relative overflow-hidden flex flex-col justify-center">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[13px] font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
             <Wallet size={16} className="text-emerald-500" />
             Live Portfolio
          </h2>
          <span className="flex items-center gap-1.5 text-[10px] text-emerald-700 bg-emerald-100/50 border border-emerald-200/50 px-2 py-1 rounded-full font-bold uppercase tracking-wider">
             <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
             Syncing
          </span>
        </div>
        
        <div className="my-auto">
            <p className="text-xs text-gray-400 font-medium mb-1 uppercase tracking-widest">Available Cash</p>
            <p className="text-4xl font-black text-gray-900 tracking-tight">
               25,000 <span className="text-2xl text-gray-400 font-medium">฿</span>
            </p>
        </div>

        <div className="mt-4 pt-4 border-t border-emerald-100/50 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-500">Unrealized P&L</span>
          <div className="flex items-center gap-1 text-emerald-600 bg-emerald-50 px-2.5 py-1.5 rounded-lg border border-emerald-100 shadow-sm">
             <ArrowUpRight size={16} strokeWidth={2.5} />
             <span className="text-sm font-bold">+3,600 ฿ (14.4%)</span>
          </div>
        </div>
      </div>

      {/* กล่อง 2: HSH Market Snapshot (ปรับให้อ่านง่ายและคมชัดขึ้น) */}
      <div className="flex-1 rounded-[24px] p-6 shadow-xl border border-[#824199]/40 bg-gradient-to-br from-[#1e102a] to-[#36174d] flex flex-col justify-center relative overflow-hidden font-sans">
        
        {/* Header - ทำให้ดูสว่างและคมชัดขึ้น */}
        <div className="relative z-10 flex items-center justify-between mb-6">
          <div className="flex flex-col">
            <h2 className="text-xs font-bold text-purple-300 uppercase tracking-[0.15em] mb-1">Hua Seng Heng</h2>
            <h2 className="text-[15px] font-bold text-white uppercase tracking-widest flex items-center gap-2">
               <Globe size={16} className="text-purple-300" />
               Market Snapshot
            </h2>
          </div>
          <button className="bg-purple-500/20 border border-purple-400/30 p-2.5 rounded-xl text-purple-100 hover:bg-purple-500/30 transition-colors">
             <RefreshCcw size={16} />
          </button>
        </div>

        {/* Buy/Sell Grid - ขยายพื้นที่และลดความเบียดของตัวเลข */}
        <div className="relative z-10 my-auto grid grid-cols-2 gap-4">
            {/* HSH Sell (ขายออก) */}
            <div className="bg-white/10 border border-white/20 rounded-2xl p-4 backdrop-blur-md shadow-inner">
                <p className="text-[11px] text-purple-100 font-bold mb-2 uppercase tracking-widest flex items-center gap-1.5 opacity-90">
                    <ArrowUpRight size={14} className="text-rose-400" /> HSH Sell
                </p>
                <div className="flex items-baseline gap-1.5">
                    {/* ใช้ tracking-normal และเอา font-black ออกเปลี่ยนเป็น font-bold เพื่อไม่ให้ตัวหนาจนเบียดกัน */}
                    <p className="text-[28px] font-bold text-white tracking-normal leading-none">44,250</p>
                    <span className="text-sm text-purple-300 font-bold">฿</span>
                </div>
            </div>

            {/* HSH Buy (รับซื้อ) */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-4 backdrop-blur-md shadow-inner">
                <p className="text-[11px] text-purple-100 font-bold mb-2 uppercase tracking-widest flex items-center gap-1.5 opacity-90">
                    <ArrowDownLeft size={14} className="text-emerald-400" /> HSH Buy
                </p>
                <div className="flex items-baseline gap-1.5">
                    <p className="text-[28px] font-bold text-white tracking-normal leading-none">44,150</p>
                    <span className="text-sm text-purple-300 font-bold">฿</span>
                </div>
            </div>
        </div>

        {/* ค่าเงินและราคาสปอต - จัดระเบียบให้อ่านง่ายขึ้น */}
        <div className="relative z-10 mt-6 grid grid-cols-2 gap-4 bg-black/20 p-3.5 rounded-xl border border-white/5">
            <div className="flex flex-col">
                <span className="text-[10px] font-bold text-purple-200 uppercase tracking-widest mb-1">Spot (XAU/USD)</span>
                <span className="text-[15px] font-bold text-white tracking-wide">$2,350.50</span>
            </div>
            <div className="flex flex-col border-l border-white/10 pl-4">
                <span className="text-[10px] font-bold text-purple-200 uppercase tracking-widest mb-1">USD/THB</span>
                <span className="text-[15px] font-bold text-white tracking-wide">36.75 <span className="text-[11px] text-purple-300">฿</span></span>
            </div>
        </div>
      </div>

    </div>
  );
};