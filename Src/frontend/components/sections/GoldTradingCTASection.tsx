import React from 'react';
import { ArrowUpRight } from 'lucide-react';

export const GoldTradingCTASection = () => {
  const handleGoToOverview = () => window.location.href = '/overview';

  return (
    <section className="flex flex-col items-center w-full py-12 px-6 bg-transparent">
      <div className="relative flex flex-col items-center w-full max-w-screen-xl bg-[#1a0a24] rounded-[40px] p-12 md:p-20 overflow-hidden shadow-[0_20px_50px_rgba(26,10,36,0.15)] border border-purple-500/20">
        
        <div className="absolute -top-20 -right-20 w-80 h-80 bg-[#824199]/40 rounded-full blur-[80px] pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-64 h-64 bg-emerald-500/10 rounded-full blur-[60px] pointer-events-none" />
        
        <div className="relative z-10 flex flex-col items-center gap-8 text-center">
          <h2 className="font-['Newsreader'] font-normal text-white text-4xl md:text-5xl leading-tight tracking-tight max-w-2xl">
            Ready to join the <br /> <span className="italic text-[#f9d443]">future</span> of Gold trading?
          </h2>
          <p className="font-medium text-gray-300 text-sm max-w-lg leading-relaxed">
            ปลดล็อกศักยภาพการเทรดด้วย AI Agent ที่พร้อมวิเคราะห์ตลาด 
            และแนะนำจุดเข้า-ออกที่แม่นยำให้คุณตัดสินใจทำกำไรได้ทันที
          </p>
          <button onClick={handleGoToOverview} className="mt-2 bg-white text-[#1a0a24] px-8 py-3.5 rounded-full text-sm font-black shadow-xl hover:bg-gray-100 hover:scale-105 transition-all flex items-center gap-2">
            Get Signal Alerts <ArrowUpRight size={16} />
          </button>
        </div>
      </div>

      <div className="max-w-3xl text-center mt-10 px-4">
        <p className="text-gray-400 text-[10px] leading-relaxed font-medium uppercase tracking-wider">
          Disclaimer: การลงทุนมีความเสี่ยง ข้อมูลและสัญญาณเป็นเพียงเครื่องมือช่วยตัดสินใจทางคณิตศาสตร์ ไม่มีการันตีผลกำไร <br className="hidden md:block" /> ผลการดำเนินงานในอดีตมิได้เป็นสิ่งยืนยันถึงผลการดำเนินงานในอนาคต
        </p>
      </div>
    </section>
  );
};