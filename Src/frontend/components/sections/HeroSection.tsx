import { motion } from 'framer-motion';
import { TrendingUp, Activity, BarChart2, ArrowUpRight, Sparkles, BrainCircuit, BellRing } from 'lucide-react';
import logoImg from '../../images/logo.png';

const fadeInUp = {
  initial: { opacity: 0, y: 15 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] }
};

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.1 } }
};

const ActiveSignalWidget = () => (
  <div className="flex flex-col gap-3">
    <div className="bg-white rounded-[24px] p-5 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-100 w-[240px] -rotate-2 hover:rotate-0 transition-transform duration-300">
      <div className="flex items-center justify-between mb-4">
        <span className="text-[11px] font-black text-gray-900 uppercase tracking-widest">Active Signal</span>
        <Activity size={14} className="text-[#824199]" />
      </div>
      <div className="flex gap-2">
        <span className="bg-[#824199] text-white text-[10px] font-bold px-3 py-1.5 rounded-lg shadow-md shadow-purple-500/20">BUY</span>
        <span className="bg-purple-50 text-[#824199] text-[10px] font-bold px-3 py-1.5 rounded-lg">HOLD</span>
        <span className="bg-gray-50 text-gray-400 text-[10px] font-bold px-3 py-1.5 rounded-lg">SELL</span>
      </div>
    </div>
    <div className="bg-[#1a0a24] rounded-[24px] p-5 shadow-[0_8px_30px_rgb(130,65,153,0.15)] border border-purple-500/20 w-[240px]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[10px] font-black text-purple-300 uppercase tracking-widest">Confidence</span>
        <BrainCircuit size={14} className="text-emerald-400" />
      </div>
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-gradient-to-br from-emerald-400 to-emerald-600 rounded-full flex items-center justify-center text-xs font-black text-white shadow-lg">85%</div>
        <p className="text-[10px] text-gray-300 font-medium leading-tight">Strong upward<br/>momentum detected.</p>
      </div>
    </div>
  </div>
);

const GoldPriceWidget = () => (
  <div className="bg-white rounded-[28px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-100 w-[260px] h-full flex flex-col justify-between">
    <div>
      <div className="flex items-center justify-between mb-6">
        <span className="text-[11px] font-black text-gray-900 uppercase tracking-widest">Thai Gold 96.5%</span>
        <div className="p-1.5 bg-yellow-50 rounded-lg text-yellow-600"><TrendingUp size={14} /></div>
      </div>
      <div className="bg-gray-50 rounded-xl p-3 mb-8 flex items-center justify-between border border-gray-100">
        <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider">Live Oracle</span>
        <div className="flex items-center gap-1.5 bg-white px-2 py-1 rounded-md shadow-sm border border-gray-50">
          <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
          <span className="text-[9px] font-mono text-emerald-600 font-bold">Syncing</span>
        </div>
      </div>
    </div>
    <div>
      <span className="text-3xl font-black text-gray-900 tracking-tighter">41,200 ฿</span>
      <div className="flex items-center gap-2 mt-1">
        <span className="text-xs font-bold text-emerald-500 bg-emerald-50 px-2 py-0.5 rounded-md">+350 ฿</span>
        <span className="text-[10px] font-bold text-gray-400">Today</span>
      </div>
    </div>
  </div>
);

const SignalAccuracyWidget = () => (
  <div className="bg-white rounded-[28px] p-6 shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-100 w-[260px]">
    <div className="flex items-center justify-between mb-6">
      <span className="text-[11px] font-black text-gray-900 uppercase tracking-widest">Signal Accuracy</span>
      <BarChart2 size={14} className="text-gray-400" />
    </div>
    <div className="text-center mb-6">
      <p className="text-2xl font-black text-[#824199]">84.2%</p>
      <p className="text-[9px] font-bold text-gray-400 uppercase tracking-widest mt-1">Win Rate (Last 30 Days)</p>
    </div>
    <div className="flex items-end justify-between gap-2 h-[60px]">
      {[30, 45, 25, 70, 50, 90, 60].map((h, i) => (
        <div key={i} className="flex-1 bg-purple-50 rounded-t-sm relative hover:bg-purple-100 transition-colors" style={{ height: `${h}%` }}>
          {i === 5 && <div className="absolute inset-0 bg-[#824199] rounded-t-sm shadow-sm" />}
        </div>
      ))}
    </div>
  </div>
);

export const HeroSection = () => {
  const handleGoToOverview = () => window.location.href = '/overview';

  return (
    <motion.section id="home" initial="initial" animate="animate" variants={staggerContainer} className="relative w-full flex flex-col items-center pt-8 pb-10 px-6 overflow-hidden bg-transparent scroll-mt-24">
      <motion.div animate={{ scale: [1, 1.05, 1], opacity: [0.03, 0.05, 0.03] }} transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }} className="absolute top-10 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-[#824199] rounded-full blur-[100px] pointer-events-none -z-10" />

      <motion.div variants={fadeInUp} className="mb-6 z-10">
        <img src={logoImg} alt="Logo" className="h-40 w-auto mx-auto drop-shadow-sm" />
      </motion.div>

      <motion.div variants={fadeInUp} className="z-10 text-center mb-6 max-w-4xl">
        <h1 className="font-['Newsreader'] font-normal text-gray-900 text-6xl md:text-[72px] leading-[1.05] tracking-tight">
          The Next Era <br /> of <span className="font-['Newsreader'] italic text-[#824199]">Thai gold</span> Intelligence
        </h1>
      </motion.div>

      <motion.p variants={fadeInUp} className="z-10 text-center text-gray-500 text-sm md:text-base leading-relaxed mb-10 max-w-2xl font-medium">
        รับสัญญาณเทรดทองคำแท้ 96.5% สุดแม่นยำ ด้วย AI Agent ที่วิเคราะห์ตลาดแบบ Real-time <br className="hidden md:block" /> แจ้งเตือนจุด Buy, Sell, Hold ให้คุณตัดสินใจทำกำไรได้ทันที
      </motion.p>

      <motion.div variants={fadeInUp} whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="z-10 mb-16">
        <button onClick={handleGoToOverview} className="flex items-center gap-3 bg-[#1a0a24] text-white px-8 py-3.5 rounded-full text-sm font-bold shadow-[0_10px_30px_rgba(26,10,36,0.2)] hover:shadow-[0_10px_40px_rgba(130,65,153,0.3)] transition-all border border-purple-500/20">
          <Sparkles size={16} className="text-[#f9d443]" /> Get Signal Alerts <ArrowUpRight size={16} className="text-gray-400" />
        </button>
      </motion.div>

      <motion.div variants={staggerContainer} className="z-10 flex items-stretch gap-6 flex-wrap justify-center">
        <motion.div variants={fadeInUp}><ActiveSignalWidget /></motion.div>
        <motion.div variants={fadeInUp}><GoldPriceWidget /></motion.div>
        <motion.div variants={fadeInUp}><SignalAccuracyWidget /></motion.div>
      </motion.div>
    </motion.section>
  );
};