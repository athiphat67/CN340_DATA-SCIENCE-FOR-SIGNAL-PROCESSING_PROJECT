import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, BarChart3, Brain, Cpu, Sparkles } from 'lucide-react';

const rationaleData = [
  {
    id: 1,
    signal: "BUY",
    confidence: "85%",
    color: "#10b981", // Emerald-500
    text: "Technicals confirm strong upward momentum. RSI has entered the oversold territory (< 35), and MACD exhibits a clear bullish divergence.",
    indicators: ["Technical: Oversold", "Momentum: MACD Bullish", "Fed Policy: Favorable"]
  },
  {
    id: 2,
    signal: "HOLD",
    confidence: "62%",
    color: "#f59e0b", // Amber-500
    text: "Market is currently consolidating near major resistance levels. Waiting for a clear breakout above $2,350 before increasing position size.",
    indicators: ["Resistance: $2,350", "Volume: Decreasing", "Volatility: High"]
  },
  {
    id: 3,
    signal: "SELL",
    confidence: "78%",
    color: "#ef4444", // Red-500
    text: "Bearish engulfing pattern detected on daily timeframe. Significant profit taking observed following the recent non-farm payroll data.",
    indicators: ["Pattern: Bearish Engulfing", "Data: NFP Strong", "Trend: Overextended"]
  }
];

export const TransparentRationaleSection = () => {
  const [index, setIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  const updateIndex = (newIndex: number) => {
    setIndex((newIndex + rationaleData.length) % rationaleData.length);
  };

  // ระบบ Auto Play ทุก 3 วินาที
  useEffect(() => {
    if (isHovered) return;

    const interval = setInterval(() => {
      updateIndex(index + 1);
    }, 3000);

    return () => clearInterval(interval);
  }, [index, isHovered]);

  return (
    <section
      id="performance"
      className="flex flex-col items-center w-full py-12 px-6 overflow-hidden bg-transparent scroll-mt-24"
    >

      {/* 🌌 Background Elements: เพิ่มมิติแสงสีม่วงอ่อนๆ คุมโทน */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-[#824199]/5 rounded-full blur-[120px] pointer-events-none -z-10" />

      <div className="max-w-screen-xl w-full flex flex-col items-center gap-16 relative z-10">

        {/* ✨ Header Section */}
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles size={16} className="text-[#824199] animate-pulse" />
            <p className="text-[10px] font-black text-[#824199] uppercase tracking-[0.3em]">AI Reasoning Process</p>
          </div>
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-5xl md:text-6xl tracking-tight leading-tight">
            Transparent <span className="italic text-transparent bg-clip-text bg-gradient-to-r from-[#824199] to-[#c084fc]">Rationale</span>
          </h2>
          <p className="text-gray-500 text-base font-medium mt-2">
            สัมผัสเบื้องลึกกระบวนการตัดสินใจของ AI แบบเรียลไทม์
          </p>
        </div>

        {/* ✨ Carousel Container */}
        <div
          className="relative w-full flex items-center justify-center h-[600px] md:h-[550px]"
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          <div className="relative w-full max-w-4xl flex items-center justify-center">
            <AnimatePresence initial={false}>
              {rationaleData.map((card, i) => {
                let position = i - index;
                if (position < -1) position += rationaleData.length;
                if (position > 1) position -= rationaleData.length;

                const isCenter = position === 0;
                const isLeft = position === -1;
                const isRight = position === 1;

                if (!isCenter && !isLeft && !isRight) return null;

                return (
                  <motion.div
                    key={card.id}
                    animate={{
                      x: position * (window.innerWidth < 768 ? 280 : 350),
                      scale: isCenter ? 1 : 0.85,
                      opacity: isCenter ? 1 : 0.3,
                      zIndex: isCenter ? 30 : 10,
                      rotateY: position * 15,
                    }}
                    transition={{ type: "spring", stiffness: 200, damping: 25 }}
                    onClick={() => updateIndex(i)}
                    className={`absolute w-full max-w-3xl rounded-[40px] p-8 md:p-12 cursor-pointer overflow-hidden border ${isCenter
                        ? 'bg-gradient-to-br from-[#1a0a24] to-[#2d1040] shadow-[0_30px_80px_rgba(130,65,153,0.25)] border-white/10'
                        : 'bg-white/80 backdrop-blur-xl shadow-xl border-[#824199]/10'
                      }`}
                  >
                    {/* Decorative Blur Background inside the active card */}
                    {isCenter && <div className="absolute -top-24 -right-24 w-64 h-64 bg-purple-500/20 rounded-full blur-[80px] pointer-events-none" />}
                    {isCenter && <Brain size={250} className="absolute -bottom-10 -right-10 text-white/[0.03] pointer-events-none" />}

                    <div className="flex flex-col gap-8 md:gap-10 relative z-10">

                      {/* Top Bar: Signal, Asset & Confidence */}
                      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 md:gap-8">
                        <div className="flex items-center gap-5">
                          {/* Signal Badge */}
                          <div
                            className={`px-6 py-2.5 rounded-2xl text-xl font-black tracking-widest ${isCenter ? 'text-white shadow-lg' : 'text-white'}`}
                            style={{
                              backgroundColor: card.color,
                              boxShadow: isCenter ? `0 10px 30px -10px ${card.color}` : 'none'
                            }}
                          >
                            {card.signal}
                          </div>
                          <div className="flex flex-col text-left">
                            <span className={`text-[10px] font-black tracking-[0.2em] uppercase mb-0.5 ${isCenter ? 'text-purple-300' : 'text-gray-400'}`}>Provider : AI</span>
                            <span className={`text-xl font-black uppercase ${isCenter ? 'text-white' : 'text-gray-900'}`}>Thai Gold 96.5%</span>
                          </div>
                        </div>

                        <div className="flex flex-col items-start md:items-end w-full md:w-auto border-t md:border-none pt-4 md:pt-0 border-white/10">
                          <span className={`text-[10px] font-black tracking-[0.2em] uppercase mb-1 ${isCenter ? 'text-purple-300' : 'text-gray-400'}`}>Confidence Score</span>
                          <span className={`font-['Newsreader'] font-bold text-5xl ${isCenter ? 'text-[#f9d443]' : 'text-[#824199]'}`}>
                            {card.confidence}
                          </span>
                        </div>
                      </div>

                      {/* Inner Box: AI Reasoning Terminal */}
                      <div className={`rounded-[28px] p-6 md:p-8 flex flex-col gap-6 text-left border ${isCenter ? 'bg-black/20 border-white/5 shadow-inner' : 'bg-gray-50 border-gray-100'
                        }`}>
                        <div className="flex justify-between items-center">
                          <div className="flex items-center gap-3">
                            <Terminal size={18} className={isCenter ? 'text-[#f9d443]' : 'text-[#824199]'} />
                            <span className={`text-[10px] font-black tracking-[0.15em] uppercase ${isCenter ? 'text-gray-300' : 'text-gray-600'}`}>
                              AI Agent Reasoning System
                            </span>
                          </div>
                          {isCenter && <Cpu size={16} className="text-purple-400/50" />}
                        </div>

                        <div className="flex flex-col gap-6">
                          <p className={`font-['Newsreader'] text-xl md:text-2xl leading-[1.6] italic ${isCenter ? 'text-purple-50' : 'text-gray-800'}`}>
                            "{card.text}"
                          </p>

                          <div className={`pt-6 border-t grid grid-cols-1 sm:grid-cols-3 gap-4 ${isCenter ? 'border-white/10' : 'border-gray-200'}`}>
                            {card.indicators.map((ind, idx) => (
                              <div key={idx} className="flex items-center gap-3">
                                <div className="w-1.5 h-1.5 rounded-full shadow-sm" style={{ backgroundColor: card.color }} />
                                <span className={`text-[10px] font-bold uppercase tracking-wide ${isCenter ? 'text-gray-400' : 'text-gray-500'}`}>
                                  {ind}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        </div>

        {/* ✨ Indicators (จุด Navigation ด้านล่าง) */}
        <div className="flex items-center gap-3 -mt-6 z-20">
          {rationaleData.map((_, i) => (
            <button
              key={i}
              onClick={() => updateIndex(i)}
              className={`h-2 rounded-full transition-all duration-500 ${i === index ? "w-10 bg-[#824199] shadow-[0_0_10px_rgba(130,65,153,0.5)]" : "w-2 bg-gray-300 hover:bg-gray-400"
                }`}
            />
          ))}
        </div>
      </div>
    </section>
  );
};