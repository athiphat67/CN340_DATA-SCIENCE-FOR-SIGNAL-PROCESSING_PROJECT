import React from 'react';
import { Network, BrainCircuit, ShieldCheck, Zap } from 'lucide-react';

const steps = [
  {
    icon: Network, // Data Ingestion
    bgColor: "bg-[#f5e6fa]",
    step: "STEP 1",
    title: "Data Ingestion",
    description: "ดึงราคาทองคำ XAU/USD, อินดิเคเตอร์ทางเทคนิค และประเมิน Sentiment ข่าวเศรษฐกิจโลก 8 หมวดหมู่แบบเรียลไทม์",
  },
  {
    icon: BrainCircuit, // AI Brain & ReAct Loop
    bgColor: "bg-[#fef9e7]",
    step: "STEP 2",
    title: "AI Brain & ReAct Loop",
    description: "สมองกล AI วิเคราะห์สถานการณ์ และเลือกใช้เครื่องมือซ้ำแล้วซ้ำเล่า จนกว่าจะมั่นใจมากที่สุด ก่อนตัดสินใจ",
  },
  {
    icon: ShieldCheck, // Risk Gate
    bgColor: "bg-[#f5e6fa]",
    step: "STEP 3",
    title: "Risk Gate",
    description: "ตรวจสอบเวลาเปิด-ปิดตลาด, ล็อกเพดานขาดทุนรายวัน และคำนวณ SL/TP อัตโนมัติด้วยค่าความผันผวนจริง (ATR)",
  },
  {
    icon: Zap, // Insightful Execution
    bgColor: "bg-[#fef9e7]",
    step: "STEP 4",
    title: "Insightful Execution",
    description: "ส่งคำสั่งอัตโนมัติพร้อมแจ้งเตือนผ่านระบบ โดยอธิบายลอจิกและเหตุผลเบื้องหลัง ทุกการตัดสินใจอย่างโปร่งใส",
  },
];

export const HowItWorksStepsSection = () => {
  return (
    <section id="how-it-works" className="w-full py-24 px-8 flex flex-col items-center bg-transparent">
      <div className="max-w-screen-xl w-full flex flex-col items-center gap-20">
        
        {/* Header */}
        <div className="flex flex-col items-center gap-4 text-center">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-5xl tracking-tight leading-tight">
            How it <span className="text-[#824199]">Works</span>
          </h2>
          <p className="text-[#11182780] text-base font-normal max-w-lg">
            Our multi-layered AI architecture ensures precision and speed.
          </p>
        </div>

        {/* Steps Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 w-full gap-y-12 lg:gap-y-0 relative">
          {steps.map((item, index) => (
            <div key={index} className="flex flex-col items-center text-center px-6 relative">
              
              {/* Connector Line (Desktop Only) */}
              {index < steps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-[65%] w-[70%] h-0 border-t-2 border-dashed border-[#824199]/20 -z-10" />
              )}

              {/* Icon Box */}
              <div className={`w-16 h-16 ${item.bgColor} rounded-2xl flex items-center justify-center shadow-sm mb-6 transition-transform hover:scale-110`}>
                <item.icon size={24} className="text-[#824199]" strokeWidth={2} />
              </div>

              {/* Step Label */}
              <span className="text-[#824199]/40 text-[10px] font-bold tracking-[0.15em] mb-3">
                {item.step}
              </span>

              {/* Title */}
              <h3 className="text-gray-900 text-lg font-semibold mb-3">
                {item.title}
              </h3>

              {/* Description */}
              <p className="text-[#11182799] text-xs leading-[1.8] max-w-[220px]">
                {item.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};