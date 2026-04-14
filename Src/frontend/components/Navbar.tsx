import React from 'react';
import { Pickaxe, LineChart, HelpCircle } from 'lucide-react';

export const Navbar = () => {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-4 bg-white/80 backdrop-blur-md border-b border-gray-100 max-w-screen-xl mx-auto rounded-b-3xl shadow-sm">
      
      {/* ฝั่งซ้าย: Logo "NAKKHUTTONG" */}
      <div className="flex items-center gap-2 cursor-pointer">
        <div className="w-10 h-10 bg-[#824199] rounded-full flex items-center justify-center shadow-md">
          <Pickaxe size={20} className="text-white" strokeWidth={2.5} />
        </div>
        <span className="font-bold text-xl tracking-tighter text-[#1a1a1a]">
          NAKKHUTTONG
        </span>
      </div>

      {/* ฝั่งกลาง: Menu Links */}
      <div className="hidden md:flex items-center gap-8 text-sm font-medium text-gray-500">
        <a href="#home" className="hover:text-[#824199] transition-colors">Home</a>
        <a href="#features" className="hover:text-[#824199] transition-colors">Features</a>
        <a href="#how-it-works" className="hover:text-[#824199] transition-colors">How it Works</a>
        
        {/* เมนูที่มีไอคอนประกอบ */}
        <a href="#performance" className="flex items-center gap-1 hover:text-[#824199] transition-colors">
          <LineChart size={16} />
          Performance
        </a>
        <a href="#faq" className="flex items-center gap-1 hover:text-[#824199] transition-colors">
          <HelpCircle size={16} />
          FAQ
        </a>
      </div>

      {/* ฝั่งขวา: ปุ่ม Start Now */}
      <button className="bg-[#824199] text-white px-6 py-2.5 rounded-full text-sm font-semibold shadow-[0_4px_14px_0_rgba(130,65,153,0.39)] hover:bg-[#6d3580] transition-all transform hover:scale-105 active:scale-95">
        Start now
      </button>
    </nav>
  );
};