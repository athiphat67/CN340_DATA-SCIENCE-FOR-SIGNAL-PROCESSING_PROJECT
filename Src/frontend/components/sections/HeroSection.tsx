import { motion } from 'framer-motion';
import { TrendingUp, Activity, BarChart2, ArrowUpRight, Sparkles } from 'lucide-react';
import logoImg from '../../images/logo.png';

const fadeInUp = {
  initial: { opacity: 0, y: 15 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] } 
};

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.1 } }
};

const ActiveSignalWidget = () => (
  // ✨ ขยายระยะห่างแนวตั้งเป็น gap-6 และขยายกล่องเป็น w-[280px] ถึง 300px
  <div className="flex flex-col gap-6">
    <div className="bg-white rounded-[32px] p-6 shadow-[0px_20px_40px_rgba(0,0,0,0.03)] border border-gray-100/80 w-[280px] lg:w-[300px] -rotate-3 transition-transform hover:rotate-0 duration-500">
      <div className="flex items-center justify-between mb-6">
        <span className="text-sm font-bold text-gray-900">Active Signal</span>
        <div className="text-[#824199] opacity-70">
          <Activity size={20} strokeWidth={2.5} />
        </div>
      </div>
      <div className="flex gap-3">
        <span className="bg-[#824199] text-white text-[10px] font-bold px-5 py-2 rounded-full shadow-lg shadow-[#824199]/20">BUY</span>
        <span className="bg-[#824199]/20 text-[#824199] text-[10px] font-bold px-5 py-2 rounded-full">HOLD</span>
        <span className="bg-[#824199]/10 text-[#824199]/40 text-[10px] font-bold px-5 py-2 rounded-full">SELL</span>
      </div>
    </div>
    <div className="bg-white rounded-[32px] p-6 shadow-[0px_20px_40px_rgba(0,0,0,0.03)] border border-gray-100/80 w-[280px] lg:w-[300px]">
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-bold text-gray-900">Agent Confidence</span>
      </div>
      <div className="flex items-start gap-4">
        <div className="flex -space-x-2">
          <div className="w-10 h-10 bg-[#824199] border-2 border-white rounded-full flex items-center justify-center text-[11px] font-bold text-white">85</div>
        </div>
        <div className="flex flex-col mt-0.5">
          <span className="text-xs font-bold text-gray-900">85% Confidence</span>
          <p className="text-[10px] text-gray-400 mt-0.5">USD weakness detected.</p>
        </div>
      </div>
    </div>
  </div>
);

const GoldPriceWidget = () => (
  // ✨ ขยายกล่องเป็น w-[300px] ถึง 360px และเพิ่ม Padding เป็น p-10 ในจอใหญ่
  <div className="bg-white rounded-[40px] p-8 lg:p-10 shadow-[0px_30px_60px_rgba(0,0,0,0.04)] border border-gray-100/80 w-[300px] lg:w-[360px] h-full flex flex-col justify-between relative overflow-hidden">
    <div className="absolute top-0 right-0 w-40 h-40 bg-[#f9d443]/[0.08] rounded-full blur-2xl pointer-events-none" />
    <div>
      <div className="flex items-center justify-between mb-8 relative z-10">
        <span className="text-base font-bold text-gray-900 whitespace-nowrap">Thai Gold 96.5%</span>
        <div className="p-2 bg-gray-50 rounded-xl text-[#824199] border border-gray-100">
          <TrendingUp size={20} strokeWidth={2.5} />
        </div>
      </div>
      <div className="bg-gray-50/70 backdrop-blur-sm rounded-2xl p-4 mb-14 flex items-center justify-between border border-gray-100 relative z-10">
        <span className="text-[11px] font-medium text-gray-400">Live Oracle</span>
        <div className="flex items-center gap-2 bg-white px-3 py-1.5 rounded-full shadow-sm border border-gray-50">
          <div className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse" />
          <span className="text-[10px] font-mono text-gray-400">Syncing...</span>
        </div>
      </div>
    </div>
    <div className="relative z-10">
      <span className="text-[36px] font-bold text-gray-900 tracking-tight leading-none">41,200 ฿</span>
      <div className="flex items-center justify-between mt-2">
        <span className="text-base font-semibold text-[#824199]/50">3,600 ฿</span>
        <span className="text-lg font-bold text-yellow-500 bg-yellow-50 px-3 py-1 rounded-lg shadow-sm">+5%</span>
      </div>
    </div>
  </div>
);

const SignalAccuracyWidget = () => (
  // ✨ ขยายกล่องเป็น w-[300px] ถึง 360px และเพิ่ม Padding เป็น p-10 ในจอใหญ่
  <div className="bg-white rounded-[40px] p-8 lg:p-10 shadow-[0px_30px_60px_rgba(0,0,0,0.04)] border border-gray-100/80 w-[300px] lg:w-[360px]">
    <div className="flex items-center justify-between mb-8">
      <span className="text-base font-bold text-gray-900">Signal Accuracy</span>
      <BarChart2 size={20} className="text-gray-400" />
    </div>
    <div className="text-center mb-10">
      <p className="text-2xl font-bold text-gray-900">84.2%</p>
      <p className="text-[11px] font-bold text-gray-300 uppercase tracking-widest mt-1.5">Win Rate (Last 30 Days)</p>
    </div>
    <div className="flex items-end justify-between gap-4 h-[110px]">
      {[30, 60, 100, 45].map((h, i) => (
        <div key={i} className="flex-1 bg-gray-50 rounded-full relative hover:bg-gray-100 transition-colors" style={{ height: `${h}%` }}>
          {i === 2 && <div className="absolute inset-0 bg-[#824199] rounded-full shadow-lg shadow-[#824199]/30" />}
        </div>
      ))}
    </div>
  </div>
);

export const HeroSection = () => {
  const handleGoToOverview = () => window.location.href = '/overview';

  return (
    <motion.section 
      id="home" 
      initial="initial" 
      animate="animate" 
      variants={staggerContainer} 
      className="relative w-full min-h-screen flex flex-col items-center pt-10 pb-24 px-8 bg-transparent z-0 overflow-x-clip overflow-y-visible"
    >
      <motion.div animate={{ scale: [1, 1.05, 1], opacity: [0.05, 0.08, 0.05] }} transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }} className="absolute -top-20 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-[#824199] rounded-full blur-[150px] pointer-events-none -z-10" />
      <motion.div animate={{ x: [0, 30, 0], y: [0, -30, 0], opacity: [0.08, 0.12, 0.08] }} transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }} className="absolute top-40 right-[15%] w-72 h-72 bg-[#f9d443] rounded-full blur-[120px] pointer-events-none -z-10" />

      {/* โลโก้ขนาดใหญ่ที่เพิ่งปรับปรุงไป */}
      <motion.div variants={fadeInUp} className="mb-8 z-20 mt-4">
        <img 
          src={logoImg} 
          alt="NAKKHUTTONG Logo" 
          className="h-44 md:h-52 w-auto mx-auto mix-blend-multiply object-contain" 
        />
      </motion.div>

      <motion.div variants={fadeInUp} className="z-20 text-center mb-6 max-w-5xl">
        <h1 className="font-['Newsreader'] font-normal text-gray-900 text-6xl md:text-[76px] leading-[1.05] tracking-tight">
          The Next Era <br /> of <span className="font-['Newsreader'] italic text-[#824199]">Thai gold</span> Intelligence
        </h1>
      </motion.div>

      <motion.p variants={fadeInUp} className="z-20 text-center text-[#11182790] text-sm md:text-base leading-[1.8] mb-10 max-w-2xl mx-auto font-medium">
        รับสัญญาณเทรดทองคำแท้ 96.5% สุดแม่นยำ ด้วย AI Agent ที่วิเคราะห์ตลาดแบบ <span className="whitespace-nowrap">Real-time</span><br className="hidden md:block" /> แจ้งเตือนจุด Buy, Sell, Hold ให้คุณตัดสินใจทำกำไรได้ทันที
      </motion.p>

      <motion.div variants={fadeInUp} whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} className="z-20 mb-16">
        <button onClick={handleGoToOverview} className="flex items-center gap-3.5 bg-[#824199] text-white px-10 py-4 rounded-full text-base font-bold shadow-[0_10px_30px_rgba(130,65,153,0.3)] hover:shadow-[0_15px_40px_rgba(130,65,153,0.4)] hover:bg-[#6d3580] transition-all border border-[#824199]/10">
          <Sparkles size={18} className="text-[#f9d443]" /> Get Signal Alerts <ArrowUpRight size={18} className="text-white/80" />
        </button>
      </motion.div>

      {/* ✨ ขยาย max-w ให้กว้างขึ้น และเพิ่มระยะ gap-10 (ประมาณ 40px) ระหว่างกล่อง */}
      <motion.div variants={staggerContainer} className="z-20 flex items-stretch gap-6 lg:gap-10 flex-wrap justify-center w-full max-w-[1300px] mt-6">
        <motion.div variants={fadeInUp}><ActiveSignalWidget /></motion.div>
        <motion.div variants={fadeInUp}><GoldPriceWidget /></motion.div>
        <motion.div variants={fadeInUp}><SignalAccuracyWidget /></motion.div>
      </motion.div>
    </motion.section>
  );
};