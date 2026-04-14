import { motion } from 'framer-motion';
import { TrendingUp, Activity, BarChart2, ArrowUpRight } from 'lucide-react';
import logoImg from '../../images/logo.png';

// --- Animation Variants (ตัวกำหนดจังหวะ) ---
const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } // Ease-out expo ให้ความรู้สึกนุ่มนวล
};

const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.1 // ให้ลูกๆ ค่อยๆ ปรากฏห่างกัน 0.1 วินาที
    }
  }
};


const ActiveSignalWidget = () => (
  <div className="flex flex-col gap-4">
    <div className="bg-white rounded-[32px] p-6 shadow-[0px_20px_40px_rgba(0,0,0,0.04)] border border-gray-50 w-[240px] -rotate-3 transition-transform hover:rotate-0 duration-500">
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm font-bold text-gray-900">Active Signal</span>
        <div className="text-[#824199] opacity-60">
           <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 8V4m0 0L10 6m2-2l2 2m-2 14v4m0 0l-2-2m2 2l2-2M4 12H0m0 0l2 2m-2-2l2-2m20 2h4m0 0l-2 2m2-2l-2-2"/></svg>
        </div>
      </div>
      <div className="flex gap-3">
        <span className="bg-[#824199] text-white text-[10px] font-bold px-4 py-2 rounded-full shadow-lg shadow-[#824199]/20">BUY</span>
        <span className="bg-[#824199]/20 text-[#824199] text-[10px] font-bold px-4 py-2 rounded-full">HOLD</span>
        <span className="bg-[#824199]/10 text-[#824199]/40 text-[10px] font-bold px-4 py-2 rounded-full">SELL</span>
      </div>
    </div>

    <div className="bg-white rounded-[32px] p-6 shadow-[0px_20px_40px_rgba(0,0,0,0.04)] border border-gray-50 w-[240px]">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-bold text-gray-900">Agent Confidence</span>
      </div>
      <div className="flex items-start gap-3">
        <div className="flex -space-x-2">
          <div className="w-8 h-8 bg-[#824199] border-2 border-white rounded-full flex items-center justify-center text-[10px] font-bold text-white">85</div>
        </div>
        <div className="flex flex-col">
          <span className="text-xs font-bold text-gray-900">85% Confidence</span>
          <p className="text-[10px] text-gray-400">USD weakness detected.</p>
        </div>
      </div>
    </div>
  </div>
);

const GoldPriceWidget = () => (
  <div className="bg-white rounded-[40px] p-8 shadow-[0px_30px_60px_rgba(0,0,0,0.04)] border border-gray-50 w-[280px] h-full flex flex-col justify-between">
    <div>
      <div className="flex items-center justify-between mb-8">
        <span className="text-sm font-bold text-gray-900">Thai Gold 96.5%</span>
        <div className="p-2 bg-gray-50 rounded-lg text-[#824199]">
           <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="2" y="5" width="20" height="14" rx="2"/><path d="M20 12h.01"/></svg>
        </div>
      </div>
      <div className="bg-gray-50/50 rounded-2xl p-4 mb-12 flex items-center justify-between">
        <span className="text-[10px] font-medium text-gray-400">Wallet 1</span>
        <div className="flex items-center gap-1.5 bg-white px-2 py-1 rounded-full shadow-sm">
          <div className="w-1.5 h-1.5 bg-yellow-400 rounded-full" />
          <span className="text-[9px] font-mono text-gray-400">0x24534...</span>
        </div>
      </div>
    </div>
    <div>
      <span className="text-[32px] font-bold text-gray-900 tracking-tight">72,000 ฿</span>
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-[#824199]/50">3,600 ฿</span>
        <span className="text-lg font-bold text-yellow-500">+5%</span>
      </div>
    </div>
  </div>
);

const SignalAccuracyWidget = () => (
  <div className="bg-white rounded-[40px] p-8 shadow-[0px_30px_60px_rgba(0,0,0,0.04)] border border-gray-50 w-[280px]">
    <div className="flex items-center justify-between mb-6">
      <span className="text-sm font-bold text-gray-900">Signal Accuracy</span>
    </div>
    <div className="text-center mb-8">
      <p className="text-lg font-bold text-gray-900">6,900 ฿</p>
      <p className="text-[10px] font-bold text-gray-300 uppercase tracking-widest">Mar 2026</p>
    </div>
    <div className="flex items-end justify-between gap-3 h-[100px]">
      {[30, 60, 100, 45].map((h, i) => (
        <div key={i} className="flex-1 bg-gray-50 rounded-full relative" style={{ height: `${h}%` }}>
          {i === 2 && <div className="absolute inset-0 bg-[#824199] rounded-full shadow-lg shadow-[#824199]/30" />}
        </div>
      ))}
    </div>
  </div>
);

export const HeroSection = () => {
    return (
        <motion.section
            id="home"
            initial="initial"
            animate="animate"
            variants={staggerContainer}
            className="relative w-full flex flex-col items-center pt-0 pb-24 px-8 overflow-hidden"
        >
            {/* 1. Background Blobs - มี Animation หายใจเบาๆ */}
            <motion.div 
                animate={{ 
                    scale: [1, 1.05, 1],
                    opacity: [0.06, 0.08, 0.06]
                }}
                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
                className="absolute top-20 left-1/2 -translate-x-1/2 w-[650px] h-[650px] bg-[#824199] rounded-full blur-3xl pointer-events-none" 
            />
            <motion.div 
                animate={{ 
                    x: [0, 20, 0],
                    y: [0, -20, 0]
                }}
                transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
                className="absolute top-32 left-[15%] w-56 h-56 bg-[#f9d443] opacity-[0.12] rounded-full blur-2xl pointer-events-none" 
            />

            {/* 2. Logo - ค่อยๆ เฟดลงมา */}
            <motion.div variants={fadeInUp} className="mb-4 z-10">
                <img 
                    src={logoImg} 
                    alt="NAKKHUTTONG Logo" 
                    className="h-45 w-auto mx-auto drop-shadow-md" 
                />

            </motion.div>

            {/* 3. Headline - แยกบรรทัดให้ดูมีมิติ */}
            <motion.div variants={fadeInUp} className="z-10 text-center mb-8 max-w-5xl">
                <h1 className="font-['Newsreader'] font-normal text-gray-900 text-[76px] leading-[1.05] tracking-tight">
                    The Next Era
                    <br />
                    of{' '}
                    <span className="font-['Newsreader'] italic text-[#824199]">
                        Thai gold
                    </span>{' '}
                    Intelligence
                </h1>
            </motion.div>

            {/* 4. Subtitle */}
            <motion.p 
                variants={fadeInUp}
                className="z-10 text-center text-[#11182780] text-base leading-[1.7] mb-12 max-w-xl mx-auto font-light"
            >
                วิเคราะห์ทองคำแท้ 96.5% ด้วย AI Agent ที่วิเคราะห์และตัดสินใจแบบ Real-time
                <br className="hidden md:block" /> 
                ให้คุณเข้าถึงสัญญาณ Buy, Hold, Sell ที่แม่นยำที่สุด
            </motion.p>

            {/* 5. CTA Button */}
            <motion.div 
                variants={fadeInUp}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="z-10 mb-20"
            >
                <button className="flex items-center gap-3 bg-[#824199] text-white px-10 py-4 rounded-full text-base font-semibold shadow-[0_6px_25px_rgba(130,65,153,0.4)] hover:bg-[#6d3580] transition-all">
                    <span className="w-5 h-5 rounded-full bg-white/20 flex items-center justify-center text-[12px]">▶</span>
                    Start free trial
                </button>
            </motion.div>

            {/* 6. Widget Cards - ค่อยๆ โผล่ขึ้นมาพร้อมความหน่วง */}
            <motion.div 
                variants={staggerContainer}
                className="z-10 flex items-start gap-8 flex-wrap justify-center scale-105"
            > 
                <motion.div variants={fadeInUp}>
                    <ActiveSignalWidget />
                </motion.div>
                <motion.div variants={fadeInUp}>
                    <GoldPriceWidget />
                </motion.div>
                <motion.div variants={fadeInUp}>
                    <SignalAccuracyWidget />
                </motion.div>
            </motion.div>
        </motion.section>
    );
};