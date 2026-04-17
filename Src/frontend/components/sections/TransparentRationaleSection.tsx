import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal } from 'lucide-react';

const rationaleData = [
  { id: 1, signal: "BUY", conf: "85%", color: "#10b981", text: "Technicals confirm strong upward momentum. RSI has entered the oversold territory (< 35), and MACD exhibits a clear bullish divergence.", indicators: ["Oversold", "MACD Bullish", "Favorable Data"] },
  { id: 2, signal: "HOLD", conf: "62%", color: "#f59e0b", text: "Market is currently consolidating near major resistance levels. Waiting for a clear breakout above $2,350 before increasing position size.", indicators: ["Resistance Near", "Low Volume", "High Volatility"] },
  { id: 3, signal: "SELL", conf: "78%", color: "#ef4444", text: "Bearish engulfing pattern detected on daily timeframe. Significant profit taking observed following the recent non-farm payroll data.", indicators: ["Bearish Pattern", "NFP Impact", "Overextended"] }
];

export const TransparentRationaleSection = () => {
  const [index, setIndex] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  useEffect(() => {
    if (isHovered) return;
    const interval = setInterval(() => setIndex((i) => (i + 1) % rationaleData.length), 3500);
    return () => clearInterval(interval);
  }, [isHovered]);

  return (
    <section id="performance" className="flex flex-col items-center w-full py-12 px-6 overflow-hidden bg-transparent scroll-mt-24">
      <div className="max-w-screen-xl w-full flex flex-col items-center gap-10">
        
        <div className="flex flex-col items-center gap-3 text-center">
          <h2 className="font-['Newsreader'] font-normal text-gray-900 text-4xl md:text-5xl tracking-tight leading-tight">
            Transparent <span className="italic text-[#824199]">Rationale</span>
          </h2>
          <p className="text-gray-500 text-sm font-medium">
            AI ของเราไม่ได้แค่ส่งสัญญาณ (Signal) ให้คุณ แต่เรายัง "คิดให้คุณ" ดูด้วย
          </p>
        </div>

        <div className="relative w-full flex items-center justify-center h-[450px]" onMouseEnter={() => setIsHovered(true)} onMouseLeave={() => setIsHovered(false)}>
            <AnimatePresence initial={false}>
              {rationaleData.map((card, i) => {
                let pos = i - index;
                if (pos < -1) pos += rationaleData.length;
                if (pos > 1) pos -= rationaleData.length;
                if (pos < -1 || pos > 1) return null;

                const isCenter = pos === 0;

                return (
                  <motion.div key={card.id} animate={{ x: pos * 320, scale: isCenter ? 1 : 0.85, opacity: isCenter ? 1 : 0.4, zIndex: isCenter ? 30 : 10 }} transition={{ type: "spring", stiffness: 250, damping: 25 }} className={`absolute w-full max-w-2xl rounded-[32px] p-8 cursor-pointer border ${isCenter ? 'bg-[#1a0a24] shadow-[0_20px_50px_rgba(26,10,36,0.2)] border-purple-500/20 text-white' : 'bg-white shadow-xl border-gray-100 text-gray-900'}`}>
                    <div className="flex flex-col gap-6">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className={`px-5 py-1.5 rounded-xl text-lg font-black text-white shadow-sm`} style={{ backgroundColor: card.color }}>{card.signal}</div>
                          <span className={`text-sm font-black uppercase ${isCenter ? 'text-white' : 'text-gray-900'}`}>Thai Gold</span>
                        </div>
                        <div className="text-right">
                          <span className={`text-[9px] font-bold uppercase tracking-widest ${isCenter ? 'text-purple-300' : 'text-gray-400'}`}>Confidence</span>
                          <p className={`font-['Newsreader'] font-bold text-4xl ${isCenter ? 'text-[#f9d443]' : 'text-[#824199]'}`}>{card.conf}</p>
                        </div>
                      </div>

                      <div className={`rounded-[20px] p-6 flex flex-col gap-4 border ${isCenter ? 'bg-black/30 border-white/5' : 'bg-gray-50 border-gray-100'}`}>
                        <div className="flex items-center gap-2">
                          <Terminal size={14} className={isCenter ? 'text-[#f9d443]' : 'text-[#824199]'} />
                          <span className={`text-[9px] font-black uppercase tracking-widest ${isCenter ? 'text-gray-400' : 'text-gray-500'}`}>Agent Reasoning</span>
                        </div>
                        <p className={`font-['Newsreader'] text-xl italic leading-relaxed ${isCenter ? 'text-gray-100' : 'text-gray-800'}`}>"{card.text}"</p>
                        <div className={`pt-4 border-t flex gap-3 flex-wrap ${isCenter ? 'border-white/10' : 'border-gray-200'}`}>
                          {card.indicators.map((ind, idx) => (
                            <span key={idx} className={`text-[10px] font-bold uppercase px-2 py-1 rounded-md ${isCenter ? 'bg-white/10 text-gray-300' : 'bg-white text-gray-500 border border-gray-100'}`}>{ind}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
        </div>

        <div className="flex gap-2 -mt-4">
          {rationaleData.map((_, i) => (
            <button key={i} onClick={() => setIndex(i)} className={`h-1.5 rounded-full transition-all duration-300 ${i === index ? "w-8 bg-[#824199]" : "w-2 bg-gray-300"}`} />
          ))}
        </div>
      </div>
    </section>
  );
};