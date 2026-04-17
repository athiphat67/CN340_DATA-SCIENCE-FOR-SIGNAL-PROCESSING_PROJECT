import React from 'react';
import { Network, BrainCircuit, ShieldCheck, Zap } from 'lucide-react';

const steps = [
  { icon: Network, step: "01", title: "Data Ingestion", desc: "ดึงราคาทองคำ XAU/USD, อินดิเคเตอร์ทางเทคนิค และประเมิน Sentiment ข่าวแบบเรียลไทม์", color: "text-[#824199] bg-purple-50" },
  { icon: BrainCircuit, step: "02", title: "AI Brain & ReAct", desc: "สมองกล AI วิเคราะห์สถานการณ์ และเลือกใช้เครื่องมือซ้ำแล้วซ้ำเล่า ก่อนตัดสินใจ", color: "text-emerald-600 bg-emerald-50" },
  { icon: ShieldCheck, step: "03", title: "Risk Gate", desc: "ตรวจสอบเวลาตลาด, ล็อกเพดานขาดทุน และคำนวณ SL/TP อัตโนมัติด้วย ATR", color: "text-blue-600 bg-blue-50" },
  { icon: Zap, step: "04", title: "Execution", desc: "ส่งคำสั่งอัตโนมัติพร้อมแจ้งเตือนผ่านระบบ อธิบายลอจิกทุกการตัดสินใจโปร่งใส", color: "text-amber-600 bg-amber-50" },
];

export const HowItWorksStepsSection = () => {
  return (
    <section id="how-it-works" className="w-full py-12 px-6 flex flex-col items-center bg-transparent relative z-10">
      <div className="max-w-screen-xl w-full flex flex-col items-center gap-12">
        <div className="flex flex-col items-center gap-3 text-center">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-4xl md:text-5xl tracking-tight leading-tight">
            How it <span className="italic text-[#824199]">Works</span>
          </h2>
          <p className="text-gray-500 text-sm font-medium max-w-lg">Our multi-layered AI architecture ensures precision and speed.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 w-full gap-6">
          {steps.map((item, index) => (
            <div key={index} className="flex flex-col p-6 bg-white rounded-[24px] border border-gray-100 shadow-sm hover:shadow-lg hover:border-purple-100 transition-all relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-6 text-5xl font-['Newsreader'] font-bold text-gray-50 group-hover:text-gray-100 transition-colors z-0">
                {item.step}
              </div>
              <div className="relative z-10">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center mb-5 ${item.color}`}>
                  <item.icon size={20} strokeWidth={2.5} />
                </div>
                <h3 className="text-gray-900 text-base font-bold mb-2 uppercase tracking-tight">{item.title}</h3>
                <p className="text-gray-500 text-xs leading-relaxed font-medium">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};