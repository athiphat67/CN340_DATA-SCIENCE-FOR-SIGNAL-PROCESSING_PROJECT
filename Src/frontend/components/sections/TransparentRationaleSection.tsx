import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal, BarChart3, ChevronRight, ChevronLeft } from 'lucide-react';

const rationaleData = [
  {
    id: 1,
    signal: "BUY",
    confidence: "85%",
    color: "#10b981", // Emerald-500
    text: "Technicals confirm strong upward momentum. RSI has entered the oversold territory {'(< 35)'}, and MACD exhibits a clear bullish divergence.",
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
  const [isHovered, setIsHovered] = useState(false); // เพิ่ม state สำหรับเช็คการวางเมาส์

  const updateIndex = (newIndex: number) => {
    setIndex((newIndex + rationaleData.length) % rationaleData.length);
  };

  // ระบบ Auto Play ทุก 3 วินาที
  useEffect(() => {
    if (isHovered) return; // ถ้าวางเมาส์ค้างไว้ ให้หยุดเลื่อนอัตโนมัติ

    const interval = setInterval(() => {
      updateIndex(index + 1);
    }, 3000); // 3000ms = 3 วินาที

    return () => clearInterval(interval); // เคลียร์ interval เมื่อ component ถูกปิด
  }, [index, isHovered]); // ทำงานใหม่ทุกครั้งที่ index เปลี่ยน หรือสถานะ hover เปลี่ยน

  return (
    <section id="performance" className="flex flex-col items-center w-full py-24 px-8 overflow-hidden">
      <div className="max-w-screen-xl w-full flex flex-col items-center gap-16">
        
        {/* Header Section */}
        <div className="flex flex-col items-center gap-4 text-center">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-5xl tracking-tight leading-tight">
            Transparent Rationale
          </h2>
          <p className="text-[#11182780] text-base font-normal">
            สัมผัสเบื้องลึกกระบวนการตัดสินใจของ AI แบบเรียลไทม์
          </p>
        </div>

        {/* Carousel Container */}
        <div 
          className="relative w-full flex items-center justify-center h-[550px]"
          onMouseEnter={() => setIsHovered(true)} // หยุดเลื่อนเมื่อเมาส์เข้า
          onMouseLeave={() => setIsHovered(false)} // เลื่อนต่อเมื่อเมาส์ออก
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
                      x: position * 350, // เพิ่มระยะห่างเล็กน้อย
                      scale: isCenter ? 1 : 0.82,
                      opacity: isCenter ? 1 : 0.35,
                      zIndex: isCenter ? 30 : 10,
                      rotateY: position * 15,
                    }}
                    transition={{ type: "spring", stiffness: 200, damping: 25 }}
                    onClick={() => updateIndex(i)}
                    className="absolute w-full max-w-3xl bg-white/90 backdrop-blur-2xl rounded-[40px] p-10 md:p-12 shadow-[0_25px_60px_rgba(0,0,0,0.05)] border-[1.5px] border-[#824199]/10 cursor-pointer"
                  >
                    {/* เนื้อหาภายในการ์ด (เหมือนเดิม) */}
                    <div className="absolute top-8 right-8 text-[#824199]/10">
                      <BarChart3 size={40} />
                    </div>
                    <div className="flex flex-col gap-10">
                      <div className="flex items-center justify-between gap-8">
                        <div className="flex items-center gap-6">
                          <div 
                            className="text-white px-8 py-3 rounded-2xl text-xl font-bold shadow-[0_20px_60px_rgba(130,65,153,0.06)]"
                            style={{ backgroundColor: card.color }}
                          >
                            {card.signal}
                          </div>
                          <div className="flex flex-col text-left">
                            <span className="text-[#11182766] text-[10px] font-bold tracking-[0.15em] uppercase">Provider : AI</span>
                            <span className="text-gray-900 text-xl font-semibold uppercase">Thai Gold 96.5%</span>
                          </div>
                        </div>
                        <div className="flex flex-col items-end">
                          <span className="text-[#11182766] text-[10px] font-bold tracking-[0.15em] uppercase text-right">Confidence Score</span>
                          <span className="font-['Newsreader'] font-semibold text-[#824199] text-5xl">{card.confidence}</span>
                        </div>
                      </div>

                      <div className="bg-[#11182703] border border-[#1118270d] rounded-3xl p-8 flex flex-col gap-6 text-left">
                        <div className="flex items-center gap-3">
                          <Terminal size={18} className="text-[#824199]" />
                          <span className="text-gray-900 text-xs font-bold tracking-[0.1em] uppercase">AI Agent Reasoning System</span>
                        </div>
                        <div className="flex flex-col gap-6">
                          <p className="font-['Newsreader'] text-gray-800 text-2xl leading-[1.6] italic">
                            "{card.text}"
                          </p>
                          <div className="pt-6 border-t border-gray-200 grid grid-cols-1 md:grid-cols-3 gap-4">
                            {card.indicators.map((ind, idx) => (
                              <div key={idx} className="flex items-center gap-3">
                                <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: card.color }} />
                                <span className="text-[#11182780] text-[11px] font-medium">{ind}</span>
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

        {/* Indicators (จุดเล็กๆ ด้านล่างบอกตำแหน่ง) */}
        <div className="flex gap-2 -mt-4">
          {rationaleData.map((_, i) => (
            <button
              key={i}
              onClick={() => updateIndex(i)}
              className={`w-2 h-2 rounded-full transition-all duration-300 ${
                i === index ? "w-8 bg-[#824199]" : "bg-gray-200"
              }`}
            />
          ))}
        </div>
      </div>
    </section>
  );
};