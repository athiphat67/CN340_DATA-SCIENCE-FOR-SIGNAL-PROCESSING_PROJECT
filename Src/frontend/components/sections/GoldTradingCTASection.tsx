import React from 'react';

export const GoldTradingCTASection = () => {
  return (
    <div className="inline-flex flex-col h-[521px] items-center gap-10 relative">
      <div className="flex flex-col w-[1088px] h-[465px] items-center gap-8 p-20 relative bg-[#824199] rounded-[40px] overflow-hidden">
        <div className="absolute -top-32 -right-32 w-64 h-64 bg-[#f9d4431a] rounded-full" />
        <div className="absolute -left-24 -bottom-24 w-48 h-48 bg-[#ffffff0d] rounded-full" />
        <div className="flex flex-col items-center relative self-stretch w-full flex-[0_0_auto]">
          <p className="relative w-fit mt-[-1.00px] [font-family:'Newsreader-Regular',Helvetica] font-normal text-transparent text-6xl text-center tracking-[0] leading-[60px]">
            <span className="text-white">
              Ready to join the
              <br />
            </span>
            <span className="[font-family:'Newsreader-Italic',Helvetica] italic text-[#f9d443]">
              future
            </span>
            <span className="text-white"> of Gold trading?</span>
          </p>
        </div>
        <div className="flex flex-col max-w-lg w-[512px] items-center relative flex-[0_0_auto]">
          <p className="w-fit mt-[-1.00px] text-[#ffffff99] text-lg text-center leading-7 relative [font-family:'Inter-Regular',Helvetica] font-normal tracking-[0]">
            ปลดล็อกศักยภาพการเทรดด้วย AI Agent ที่พร้อมวิเคราะห์ตลาด
            <br />
            และจัดการความเสี่ยงให้คุณอัตโนมัติ เริ่มต้นใช้งานได้เลย
          </p>
        </div>
        <div className="flex items-center justify-center gap-4 pt-4 pb-0 px-0 relative self-stretch w-full flex-[0_0_auto] mb-[-7.00px]">
          <button className="all-[unset] box-border inline-flex flex-col items-center justify-center px-10 py-4 relative flex-[0_0_auto] bg-white rounded-full">
            <div className="absolute w-full h-full top-0 left-0 bg-[#ffffff01] rounded-full shadow-[0px_8px_10px_-6px_#0000001a,0px_20px_25px_-5px_#0000001a]" />
            <div className="relative justify-center w-fit mt-[-1.00px] [font-family:'Inter-SemiBold',Helvetica] font-semibold text-[#824199] text-base text-center tracking-[0] leading-6 flex items-center whitespace-nowrap">
              Get Started Now
            </div>
          </button>
        </div>
        <div className="relative max-w-lg w-[512px] h-14 mb-[-80.00px]" />
      </div>
      <p className="flex items-center justify-center w-[1070px] mb-[-39.00px] text-[#000000b2] text-lg text-center leading-7 relative [font-family:'Inter-Regular',Helvetica] font-normal tracking-[0]">
        การลงทุนในทองคำมีความเสี่ยง ข้อมูลและสัญญาณจาก GoldTrader Agent
        เป็นเพียงเครื่องมือช่วยตัดสินใจทางคณิตศาสตร์
        ผู้ลงทุนควรศึกษาข้อมูลและยอมรับความเสี่ยงก่อนตัดสินใจลงทุน
        ผลการดำเนินงานในอดีตมิได้เป็นสิ่งยืนยันถึงผลการดำเนินงานในอนาคต
      </p>
    </div>
  );
};
