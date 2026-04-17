import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const faqData = [
  { id: 1, q: "How accurate are the AI signals?", a: "ระบบของเรามีความแม่นยำเฉลี่ยที่ 84% โดยวิเคราะห์จากข้อมูล Real-time ทั้งเชิงเทคนิค (Technical) และปัจจัยพื้นฐาน (Fundamental) เพื่อให้ได้จุดเข้าเทรดที่ได้เปรียบที่สุด" },
  { id: 2, q: "ระบบทำการเทรดให้เลยหรือไม่ / เงินทุนปลอดภัยไหม?", a: "เงินทุนของคุณปลอดภัย 100% เพราะเราเป็นเพียง 'ระบบผู้ช่วยวิเคราะห์และส่งสัญญาณ (Signal Provider)' ไม่มีการเชื่อมต่อกับพอร์ตลงทุนของคุณเพื่อเทรดแทน และไม่สามารถยุ่งเกี่ยวกับเงินของคุณได้ คุณจะเป็นผู้กดคำสั่งซื้อขายด้วยตนเองเสมอ" },
  { id: 3, q: "Can I cancel my subscription anytime?", a: "แน่นอน คุณสามารถยกเลิกการรับสัญญาณ (Signal Alerts) ได้ทุกเมื่อผ่านหน้าการตั้งค่าบัญชีของคุณ โดยไม่มีข้อผูกมัดหรือค่าธรรมเนียมเพิ่มเติม" },
];

export const CommonQuestionsSection = () => {
  const [openId, setOpenId] = useState<number | null>(null);

  return (
    <section id="faq" className="flex flex-col items-center w-full py-12 px-6 bg-transparent scroll-mt-24">
      <div className="max-w-3xl w-full flex flex-col gap-8">
        <h2 className="font-['Newsreader'] font-normal text-center text-gray-900 text-4xl tracking-tight leading-tight">
          Common Questions
        </h2>
        <div className="flex flex-col gap-3">
          {faqData.map((item) => (
            <div key={item.id} className="bg-white border border-gray-100 rounded-[20px] overflow-hidden shadow-sm hover:border-purple-100 transition-colors">
              <button className="flex items-center justify-between p-5 text-left w-full" onClick={() => setOpenId(openId === item.id ? null : item.id)}>
                <span className="text-gray-900 font-bold text-sm">{item.q}</span>
                <motion.div animate={{ rotate: openId === item.id ? 180 : 0 }} className="text-gray-400"><ChevronDown size={18} /></motion.div>
              </button>
              <AnimatePresence>
                {openId === item.id && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                    <div className="px-5 pb-5 text-gray-500 text-xs leading-relaxed font-medium">{item.a}</div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};