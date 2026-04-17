import React from 'react';
import { BrainCircuit, ShieldCheck, LineChart, Eye } from 'lucide-react';

const cards = [
  { icon: BrainCircuit, title: "Advanced\nReasoning", desc: "ก้าวข้ามบอทตั้งเงื่อนไขทั่วไป สู่การวิเคราะห์ตลาดแบบองค์รวมด้วย LLM", color: "purple" },
  { icon: ShieldCheck, title: "Ironclad Risk\nManagement", desc: "คำนวณ SL/TP อัตโนมัติตามค่าความผันผวนตลาด (ATR) คุมขาดทุนรัดกุม", color: "emerald" },
  { icon: LineChart, title: "Technical &\nFundamental", desc: "ผสานสัญญาณเชิงเทคนิคเข้ากับการวิเคราะห์ Sentiment ข่าวแบบ Real-time", color: "blue" },
  { icon: Eye, title: "24/5 Vigilance", desc: "เฝ้าระวังพอร์ตตลอดเวลาทำการ พร้อมระบบหลบหลีกช่วง Dead Zone", color: "amber" },
];

export const GoldPortfolioInsightsSection = () => {
  const accents: any = {
      purple: "text-[#824199] bg-purple-50",
      emerald: "text-emerald-600 bg-emerald-50",
      blue: "text-blue-600 bg-blue-50",
      amber: "text-amber-600 bg-amber-50"
  };

  return (
    <section id="features" className="flex flex-col items-center w-full py-12 px-6 bg-transparent scroll-mt-24">
      <div className="max-w-screen-xl w-full flex flex-col gap-10">
        <div className="flex flex-col gap-3">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-4xl md:text-5xl leading-tight tracking-tight">
            Smarter decisions <br /> for <span className="italic text-[#824199]">gold</span> portfolio
          </h2>
          <p className="text-gray-500 text-sm font-medium tracking-wide">Data-driven logic in every single trade.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {cards.map((card, index) => (
            <div key={index} className="group flex flex-col items-start p-6 bg-white rounded-[24px] border border-gray-100 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:shadow-lg transition-all duration-300 hover:-translate-y-1">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-5 transition-transform ${accents[card.color]}`}>
                <card.icon size={18} />
              </div>
              <h3 className="text-lg font-bold text-gray-900 leading-tight mb-2 whitespace-pre-line">{card.title}</h3>
              <p className="text-xs text-gray-500 leading-relaxed font-medium">{card.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};