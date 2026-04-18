import React from 'react';
import { motion } from 'framer-motion';
import { Network, BrainCircuit, ShieldCheck, BellRing } from 'lucide-react';

const steps = [
  { icon: Network, bgColor: "bg-[#f5e6fa]", step: "STEP 1", title: "Data Ingestion", description: "ดึงราคาทองคำ XAU/USD, อินดิเคเตอร์ทางเทคนิค และประเมิน Sentiment ข่าวเศรษฐกิจโลกแบบเรียลไทม์" },
  { icon: BrainCircuit, bgColor: "bg-[#fef9e7]", step: "STEP 2", title: "AI Brain & ReAct Loop", description: "สมองกล AI วิเคราะห์สถานการณ์ และเลือกใช้เครื่องมือซ้ำแล้วซ้ำเล่า จนกว่าจะมั่นใจมากที่สุด ก่อนตัดสินใจ" },
  { icon: ShieldCheck, bgColor: "bg-[#f5e6fa]", step: "STEP 3", title: "Risk Gate", description: "ตรวจสอบเวลาเปิด-ปิดตลาด, ล็อกเพดานขาดทุนรายวัน และคำนวณแนะนำ SL/TP ด้วยค่าความผันผวนจริง" },
  { icon: BellRing, bgColor: "bg-[#fef9e7]", step: "STEP 4", title: "Smart Alerts", description: "ส่งสัญญาณเตือนเข้ามือถือคุณทันที พร้อมอธิบายลอจิกและเหตุผลเบื้องหลัง อย่างโปร่งใส" },
];

export const HowItWorksStepsSection = () => {
  return (
    <section id="how-it-works" className="relative w-full py-24 px-8 flex flex-col items-center bg-transparent scroll-mt-24 z-0 overflow-x-clip overflow-y-visible">
      
      <motion.div animate={{ scale: [1, 1.05, 1], opacity: [0.03, 0.05, 0.03] }} transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }} className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-[#824199] rounded-full blur-[120px] pointer-events-none -z-10" />

      <div className="max-w-screen-xl w-full flex flex-col items-center gap-20 relative z-10">
        <div className="flex flex-col items-center gap-4 text-center">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-5xl tracking-tight leading-tight">
            How it <span className="text-[#824199]">Works</span>
          </h2>
          <p className="text-[#11182780] text-base font-normal max-w-lg">
            Our multi-layered AI architecture ensures precision and speed.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 w-full gap-y-12 lg:gap-y-0 relative">
          {steps.map((item, index) => (
            <div key={index} className="flex flex-col items-center text-center px-6 relative">
              {index < steps.length - 1 && (
                <div className="hidden lg:block absolute top-8 left-[65%] w-[70%] h-0 border-t-2 border-dashed border-[#824199]/20 -z-10" />
              )}
              <div className={`w-16 h-16 ${item.bgColor} rounded-2xl flex items-center justify-center shadow-sm mb-6 transition-transform hover:scale-110`}>
                <item.icon size={24} className="text-[#824199]" strokeWidth={2} />
              </div>
              <span className="text-[#824199]/40 text-[10px] font-bold tracking-[0.15em] mb-3">{item.step}</span>
              <h3 className="text-gray-900 text-lg font-semibold mb-3">{item.title}</h3>
              <p className="text-[#11182799] text-xs leading-[1.8] max-w-[220px]">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};