import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";

const faqData = [
  {
    id: 1,
    question: "How accurate are the AI signals?",
    answer: "ระบบของเรามีความแม่นยำเฉลี่ยที่ 85% โดยวิเคราะห์จากข้อมูล Real-time และ Sentiment Analysis เพื่อให้ได้จุดเข้าเทรดที่ได้เปรียบที่สุด",
  },
  {
    id: 2,
    question: "Is my wallet data secure?",
    answer: "ปลอดภัย 100% ระบบของเราเป็นแบบ Non-custodial และใช้การเชื่อมต่อผ่าน API ที่จำกัดสิทธิ์เฉพาะการอ่านข้อมูลเท่านั้น ไม่สามารถถอนเงินออกได้",
  },
  {
    id: 3,
    question: "Can I cancel my subscription anytime?",
    answer: "แน่นอน คุณสามารถยกเลิกการสมาชิกได้ทุกเมื่อผ่านหน้าการตั้งค่าพอร์ตของคุณ โดยไม่มีข้อผูกมัดหรือค่าธรรมเนียมเพิ่มเติม",
  },
];

export const CommonQuestionsSection = () => {
  const [openId, setOpenId] = useState<number | null>(null);

  const handleToggle = (id: number) => {
    setOpenId((prev) => (prev === id ? null : id));
  };

  return (
    <section id="faq" className="flex flex-col items-center w-full py-24 px-8 bg-transparent">
      <div className="max-w-screen-md w-full flex flex-col gap-12">
        
        {/* Header */}
        <div className="text-center">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-4xl tracking-tight leading-tight">
            Common Questions
          </h2>
        </div>

        {/* FAQ List */}
        <div className="flex flex-col gap-4">
          {faqData.map((item) => (
            <div
              key={item.id}
              className="group flex flex-col bg-white/60 backdrop-blur-xl border border-gray-100 rounded-2xl overflow-hidden transition-all duration-300 hover:border-[#824199]/20 shadow-[0_4px_20px_rgba(0,0,0,0.02)]"
            >
              <button
                type="button"
                className="flex items-center justify-between p-6 text-left w-full transition-colors group-hover:bg-[#824199]/05"
                onClick={() => handleToggle(item.id)}
              >
                <span className="text-gray-900 font-semibold text-base leading-6">
                  {item.question}
                </span>
                
                {/* Animated Arrow Icon */}
                <motion.div
                  animate={{ rotate: openId === item.id ? 180 : 0 }}
                  transition={{ duration: 0.3, ease: "easeInOut" }}
                  className="text-[#824199]"
                >
                  <ChevronDown size={20} />
                </motion.div>
              </button>

              {/* Animated Answer Section */}
              <AnimatePresence>
                {openId === item.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: "easeInOut" }}
                  >
                    <div className="px-6 pb-6 pt-0 text-[#11182780] text-sm leading-relaxed">
                      {item.answer}
                    </div>
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