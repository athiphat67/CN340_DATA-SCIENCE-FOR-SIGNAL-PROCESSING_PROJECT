import React, { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { NotificationDropdown } from '../NotificationDropdown';

export const OverviewHeader = () => {
    const navigate = useNavigate();
    const location = useLocation(); 
    
    const [currentTime, setCurrentTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    const formattedDate = currentTime.toLocaleDateString('en-GB', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    });
    const formattedTime = currentTime.toLocaleTimeString('en-GB', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    });

    const navTabs = [
        { name: 'Overview', path: '/overview' },
        { name: 'Signals', path: '/signals' },
        { name: 'Market', path: '/market' },
        { name: 'Portfolio', path: '/portfolio' },
        { name: 'History', path: '/history' },
        { name: 'BackTest', path: '/backtest' },
    ];

    return (
        <div
            className="relative pt-6 z-[100] flex flex-col justify-between"
            style={{
                // 💡 เอา minHeight: 300px ออก เพื่อให้ความสูงพอดีกับเนื้อหา
                background: 'linear-gradient(135deg, #1a0a24 0%, #2d1040 40%, #1a0a24 100%)',
            }}
        >
            {/* Background Silk Waves */}
            <div className="absolute inset-0 overflow-hidden opacity-40 pointer-events-none">
                <svg viewBox="0 0 700 200" preserveAspectRatio="none" className="w-full h-full">
                    <path d="M0 60 Q200 10 400 90 T700 40" stroke="#ffffff15" strokeWidth="1.5" fill="none" />
                    <path d="M0 110 Q220 50 420 130 T700 90" stroke="#f9d44315" strokeWidth="1.5" fill="none" />
                </svg>
            </div>

            <div className="relative z-10 px-8">
                {/* Top Bar - 💡 ลด mb-6 เหลือ mb-4 */}
                <div className="flex items-center justify-between mb-4">
                    <div className="flex flex-col md:flex-row md:items-center gap-1 md:gap-4">
                        <p className="font-['Newsreader'] font-light text-white/40 text-[12px] md:text-sm tracking-[0.05em]">
                            {formattedDate}
                        </p>
                        <span className="hidden md:block w-1 h-1 bg-white/20 rounded-full" />
                        <p className="font-mono text-[#f9d443] text-[12px] md:text-sm opacity-80 tracking-widest">
                            {formattedTime} <span className="text-[10px] ml-1 opacity-50 font-sans">UTC +7</span>
                        </p>
                    </div>

                    <div className="flex items-center gap-4 font-sans">
                        {/* 💡 ปรับ Search Box ให้เล็กลงนิดหน่อย (py-2) */}
                        <div className="hidden md:flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-2 rounded-xl backdrop-blur-md">
                            <Search size={14} className="text-white/40" />
                            <input type="text" placeholder="Search signal ID..." className="bg-transparent text-[13px] text-white outline-none w-40 placeholder:text-white/30" />
                        </div>

                        <NotificationDropdown />

                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center font-bold text-[#1a0a24] text-xs shadow-lg border border-yellow-300/50">
                            NA
                        </div>
                    </div>
                </div>

                {/* Greeting Section - 💡 ลด Margin และ ขนาด Font ลง, เอา <br> ออกให้อยู่บรรทัดเดียวกัน */}
                <div className="mb-6 mt-1">
                    <h1 className="font-['Newsreader'] text-4xl md:text-5xl text-white/90 leading-tight tracking-tight flex flex-wrap items-baseline gap-x-2.5">
                        <span>Good Evening,</span>
                        <span className="italic text-[#f9d443] font-normal">NAKKHUTTHONG</span> 
                        <span>Agent.</span>
                    </h1>
                    <p className="font-['Newsreader'] italic text-white/40 text-lg md:text-xl mt-1 tracking-wide font-light">
                        Welcome back to your intelligence dashboard.
                    </p>
                </div>

                {/* Navigation Tabs - 💡 ปรับ Padding Bottom ให้บางลง (pb-3) */}
                <nav className="flex items-center gap-8 border-b border-white/5 w-full font-sans overflow-x-auto">
                    {navTabs.map((tab) => {
                        const isActive = location.pathname.includes(tab.path);
                        return (
                            <button
                                key={tab.name}
                                onClick={() => navigate(tab.path)}
                                className={`relative pb-3 text-sm md:text-base font-medium transition-all duration-300 whitespace-nowrap ${
                                    isActive ? 'text-white' : 'text-white/40 hover:text-white/70'
                                }`}
                            >
                                {tab.name}
                                {isActive && (
                                    <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#f9d443] shadow-[0_-2px_8px_rgba(249,212,67,0.5)]" />
                                )}
                            </button>
                        );
                    })}
                </nav>
            </div>
        </div>
    );
};