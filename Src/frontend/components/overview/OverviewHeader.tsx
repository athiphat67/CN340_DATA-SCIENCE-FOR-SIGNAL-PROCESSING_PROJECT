import React, { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { NotificationDropdown } from '../NotificationDropdown';

export const OverviewHeader = () => {
    // ใช้ Router แทน Props
    const navigate = useNavigate();
    const location = useLocation(); 
    
    // 1. สร้าง State สำหรับเก็บเวลาปัจจุบัน
    const [currentTime, setCurrentTime] = useState(new Date());

    // 2. ใช้ useEffect เพื่อสร้าง Timer อัปเดตเวลาทุกวินาที
    useEffect(() => {
        const timer = setInterval(() => {
            setCurrentTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    // 3. Format วันที่และเวลา
    const formattedDate = currentTime.toLocaleDateString('en-GB', {
        weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
    });
    const formattedTime = currentTime.toLocaleTimeString('en-GB', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    });

    // 4. ตั้งค่า Tabs และ Path ของแต่ละหน้า
    const navTabs = [
        { name: 'Overview', path: '/overview' },
        { name: 'Signals', path: '/signals' },
        { name: 'Analytics', path: '/analytics' },
        { name: 'Portfolio', path: '/portfolio' },
        { name: 'History', path: '/history' },
        { name: 'Settings', path: '/settings' }
    ];

    return (
        <div
            className="relative pt-8 pb-4 z-[100]"
            style={{
                background: 'linear-gradient(135deg, #1a0a24 0%, #2d1040 40%, #1a0a24 100%)',
                minHeight: '300px',
            }}
        >
            {/* Background Silk Waves */}
            <div className="absolute overflow-hidden inset-0 opacity-40 pointer-events-none">
                <svg viewBox="0 0 700 260" className="w-full h-full">
                    <path d="M0 80 Q200 20 400 120 T700 60" stroke="#ffffff15" strokeWidth="1.5" fill="none" />
                    <path d="M0 140 Q220 80 420 170 T700 130" stroke="#f9d44315" strokeWidth="1.5" fill="none" />
                </svg>
            </div>

            <div className="relative z-10 px-8 flex flex-col h-full justify-between">
                {/* Top Bar */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4">
                        <p className="font-['Newsreader'] font-light text-white/40 text-[13px] md:text-sm tracking-[0.05em]">
                            {formattedDate}
                        </p>
                        <span className="hidden md:block w-1 h-1 bg-white/20 rounded-full" />
                        <p className="font-mono text-[#f9d443] text-[13px] md:text-sm opacity-80 tracking-widest">
                            {formattedTime} <span className="text-[10px] ml-1 opacity-50 font-sans">UTC +7</span>
                        </p>
                    </div>

                    <div className="flex items-center gap-4 font-sans">
                        <div className="hidden md:flex items-center gap-3 bg-white/5 border border-white/10 px-4 py-2.5 rounded-xl backdrop-blur-md">
                            <Search size={16} className="text-white/40" />
                            <input type="text" placeholder="Search signal ID..." className="bg-transparent text-sm text-white outline-none w-48 placeholder:text-white/30" />
                        </div>

                        <NotificationDropdown />

                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-yellow-400 to-orange-500 flex items-center justify-center font-bold text-[#1a0a24] text-sm shadow-lg border border-yellow-300/50">
                            NA
                        </div>
                    </div>
                </div>

                {/* Greeting Section */}
                <div className="mb-10 mt-2">
                    <h1 className="font-['Newsreader'] text-5xl md:text-[64px] text-white/90 leading-[1.1] tracking-tight">
                        Good Evening, <br className="hidden md:block" />
                        <span className="italic text-[#f9d443] font-normal">NAKKHUTTHONG</span> Agent.
                    </h1>
                    <p className="font-['Newsreader'] italic text-white/40 text-xl md:text-2xl mt-4 tracking-wide font-light">
                        Welcome back to your intelligence dashboard.
                    </p>
                </div>

                {/* Navigation Tabs - เปลี่ยนหน้าด้วย Router */}
                <nav className="flex items-center gap-10 border-b border-white/5 w-full font-sans overflow-x-auto">
                    {navTabs.map((tab) => {
                        // เช็คว่า URL ปัจจุบันมีคำของ Tab นี้อยู่ไหม
                        const isActive = location.pathname.includes(tab.path);
                        
                        return (
                            <button
                                key={tab.name}
                                onClick={() => navigate(tab.path)}
                                className={`relative pb-5 text-base md:text-lg font-medium transition-all duration-300 whitespace-nowrap ${
                                    isActive ? 'text-white' : 'text-white/30 hover:text-white/60'
                                }`}
                            >
                                {tab.name}

                                {/* เส้นขีดล่างสีทองสำหรับหน้าที่กำลังเปิดอยู่ */}
                                {isActive && (
                                    <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-[#f9d443] shadow-[0_-4px_12px_rgba(249,212,67,0.5)]" />
                                )}
                            </button>
                        );
                    })}
                </nav>
            </div>
        </div>
    );
};