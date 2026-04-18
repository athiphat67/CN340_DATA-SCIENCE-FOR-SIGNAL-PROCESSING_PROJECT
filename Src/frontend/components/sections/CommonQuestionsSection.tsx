import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const faqData = [
  { id: 1, question: "How accurate are the AI signals?", answer: "ระบบของเรามีความแม่นยำเฉลี่ยที่ 85% โดยวิเคราะห์จากข้อมูล Real-time และ Sentiment Analysis เพื่อให้ได้จุดเข้าเทรดที่ได้เปรียบที่สุด" },
  { id: 2, question: "ระบบทำการเทรดให้เลยหรือไม่ / เงินทุนปลอดภัยไหม?", answer: "เงินทุนของคุณปลอดภัย 100% เพราะเราเป็นเพียง 'ระบบผู้ช่วยวิเคราะห์และส่งสัญญาณ (Signal Provider)' ไม่มีการเชื่อมต่อกับพอร์ตลงทุนของคุณเพื่อเทรดแทน คุณจะเป็นผู้กดคำสั่งซื้อขายด้วยตนเองเสมอ" },
  { id: 3, question: "Can I cancel my subscription anytime?", answer: "แน่นอน คุณสามารถยกเลิกการสมาชิกได้ทุกเมื่อผ่านหน้าการตั้งค่าพอร์ตของคุณ โดยไม่มีข้อผูกมัดหรือค่าธรรมเนียมเพิ่มเติม" },
];

export const CommonQuestionsSection = () => {
  const [openId, setOpenId] = useState<number | null>(null);

  const handleToggle = (id: number) => setOpenId((prev) => (prev === id ? null : id));

  return (
    <section id="faq" className="relative flex flex-col items-center w-full py-24 px-8 bg-transparent scroll-mt-24 z-0 overflow-x-clip overflow-y-visible">
      
      <motion.div animate={{ scale: [1, 1.05, 1], opacity: [0.03, 0.05, 0.03] }} transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }} className="absolute bottom-10 right-[15%] w-[500px] h-[500px] bg-[#824199] rounded-full blur-[100px] pointer-events-none -z-10" />

      <div className="max-w-screen-md w-full flex flex-col gap-12 relative z-10">
        <div className="text-center">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-4xl tracking-tight leading-tight">
            Common Questions
          </h2>
        </div>

        <div className="flex flex-col gap-4">
          {faqData.map((item) => (
            <div key={item.id} className="group flex flex-col bg-white/80 backdrop-blur-xl border border-gray-100/80 rounded-2xl overflow-hidden transition-all duration-300 hover:border-[#824199]/20 shadow-[0_4px_20px_rgba(0,0,0,0.02)]">
              <button type="button" className="flex items-center justify-between p-6 text-left w-full transition-colors group-hover:bg-[#824199]/05" onClick={() => handleToggle(item.id)}>
                <span className="text-gray-900 font-semibold text-base leading-6">{item.question}</span>
                <motion.div animate={{ rotate: openId === item.id ? 180 : 0 }} transition={{ duration: 0.3, ease: "easeInOut" }} className="text-[#824199]">
                  <ChevronDown size={20} />
                </motion.div>
              </button>

              <AnimatePresence>
                {openId === item.id && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease: "easeInOut" }}>
                    <div className="px-6 pb-6 pt-0 text-[#11182780] text-sm leading-relaxed">{item.answer}</div>
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