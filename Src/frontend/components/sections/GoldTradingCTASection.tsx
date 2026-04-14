import React from 'react';

export const GoldTradingCTASection = () => {
  return (
    <section className="flex flex-col items-center w-full py-24 px-8 gap-12 bg-transparent">
      
      {/* Main CTA Card */}
      <div className="relative flex flex-col items-center w-full max-w-screen-xl bg-[#824199] rounded-[48px] p-16 md:p-24 overflow-hidden shadow-[0_24px_48px_rgba(130,65,153,0.3)]">
        
        {/* Decorative Background Blobs */}
        <div className="absolute -top-16 -right-16 w-80 h-80 bg-[#f9d443]/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-64 h-64 bg-white/10 rounded-full blur-2xl pointer-events-none" />
        
        <div className="relative z-10 flex flex-col items-center gap-10 text-center">
          
          {/* Headline */}
          <h2 className="font-['Newsreader'] font-normal text-white text-[56px] md:text-[64px] leading-[1.1] tracking-tight max-w-3xl">
            Ready to join the <br />
            <span className="italic text-[#f9d443]">future</span> of Gold trading?
          </h2>

          {/* Subheadline */}
          <p className="font-light text-white/80 text-lg md:text-xl max-w-lg leading-relaxed">
            ปลดล็อกศักยภาพการเทรดด้วย AI Agent ที่พร้อมวิเคราะห์ตลาด
            และจัดการความเสี่ยงให้คุณอัตโนมัติ เริ่มต้นใช้งานได้เลย
          </p>

          {/* CTA Button */}
          <div className="pt-4">
            <button className="bg-white text-[#824199] px-10 py-4 rounded-full text-base font-bold shadow-xl hover:bg-gray-50 hover:scale-105 transition-all active:scale-95">
              Get Started Now
            </button>
          </div>
        </div>
      </div>

      {/* Disclaimer Section */}
      <div className="max-w-4xl text-center px-4">
        <p className="text-[#11182780] text-sm leading-relaxed font-normal">
          การลงทุนในทองคำมีความเสี่ยง ข้อมูลและสัญญาณจาก GoldTrader Agent เป็นเพียงเครื่องมือช่วยตัดสินใจทางคณิตศาสตร์ 
          ผู้ลงทุนควรศึกษาข้อมูลและยอมรับความเสี่ยงก่อนตัดสินใจลงทุน <br className="hidden md:block" />
          ผลการดำเนินงานในอดีตมิได้เป็นสิ่งยืนยันถึงผลการดำเนินงานในอนาคต
        </p>
      </div>
      
    </section>
  );
};