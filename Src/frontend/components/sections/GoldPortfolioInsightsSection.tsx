import React from 'react';
import { BrainCircuit, ShieldCheck, LineChart, Eye } from 'lucide-react';

const cards = [
  {
    icon: BrainCircuit,
    title: "Advanced\nReasoning",
    description: "ก้าวข้ามบอทตั้งเงื่อนไขทั่วไป สู่การวิเคราะห์ตลาดแบบองค์รวมด้วยความฉลาดของ LLM",
  },
  {
    icon: ShieldCheck,
    title: "Ironclad Risk\nManagement",
    description: "คำนวณ SL/TP อัตโนมัติตามค่าความผันผวนตลาด (ATR) พร้อมระบบคุมขีดจำกัดขาดทุนรายวัน",
  },
  {
    icon: LineChart,
    title: "Technical &\nFundamental",
    description: "ผสานสัญญาณเชิงเทคนิคเข้ากับการวิเคราะห์ Sentiment ข่าวเศรษฐกิจโลกแบบ Real-time",
  },
  {
    icon: Eye,
    title: "24/5 Vigilance",
    description: "เฝ้าระวังพอร์ตตลอดเวลาทำการ พร้อมระบบหลบหลีกช่วง Dead Zone เพื่อปกป้องเงินทุน",
  },
];

export const GoldPortfolioInsightsSection = () => {
  return (
    <section
      id="features" // เปลี่ยนตามชื่อเมนู เช่น home, features, faq
      className="flex flex-col items-center w-full py-24 px-8 bg-transparent scroll-mt-24"
    >
      <div className="max-w-screen-xl w-full flex flex-col gap-12">

        {/* Header Section */}
        <div className="flex flex-col gap-4">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-[56px] leading-[1.1] tracking-tight">
            Smarter decisions <br />
            for <span className="italic text-[#824199]">gold</span> portfolio
          </h2>
          <p className="text-[#11182780] text-sm font-medium tracking-wide">
            Data-driven logic in every single trade.
          </p>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {cards.map((card, index) => (
            <div
              key={index}
              className="group flex flex-col items-start p-8 bg-white/60 backdrop-blur-xl rounded-[32px] border border-white shadow-[0_20px_50px_rgba(0,0,0,0.04)] hover:shadow-[0_30px_60px_rgba(130,65,153,0.08)] transition-all duration-500 hover:-translate-y-2"
            >
              {/* Icon Container */}
              <div className="w-12 h-12 bg-[#8241991a] rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                <card.icon size={22} className="text-[#824199]" />
              </div>

              {/* Title */}
              <h3 className="text-xl font-semibold text-gray-900 leading-tight mb-4 whitespace-pre-line">
                {card.title}
              </h3>

              {/* Description */}
              <p className="text-sm text-[#11182799] leading-[1.6] font-normal">
                {card.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};