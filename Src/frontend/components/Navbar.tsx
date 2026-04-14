import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

export const Navbar = () => {
    const [activeSection, setActiveSection] = useState('home');

    // ฟังก์ชันสำหรับการเลื่อนหน้าจอแบบนุ่มนวล (กำหนดความช้าได้)
    const scrollToSection = (e: React.MouseEvent, id: string) => {
        e.preventDefault();

        // เรียกใช้ lenis instance ที่เราประกาศไว้ใน window (จากไฟล์ index.tsx)
        const lenis = (window as any).lenis;

        if (lenis) {
            lenis.scrollTo(id, {
                offset: -100,      // เว้นระยะบนไม่ให้ Navbar บังหัวข้อ
                duration: 2.5,     // ปรับความช้าตรงนี้ (ยิ่งเลขเยอะยิ่งช้า 2.5 คือกำลังพรีเมียม)
                easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // สูตรการเคลื่อนที่แบบ Smooth
            });
        } else {
            // Fallback กรณี lenis ไม่ทำงาน
            const element = document.querySelector(id);
            element?.scrollIntoView({ behavior: 'smooth' });
        }
    };

    useEffect(() => {
        const handleScroll = () => {
            const sections = ['home', 'features', 'how-it-works', 'performance', 'faq'];
            const scrollPosition = window.scrollY + 150;

            sections.forEach((section) => {
                const element = document.getElementById(section);
                if (element &&
                    scrollPosition >= element.offsetTop &&
                    scrollPosition < element.offsetTop + element.offsetHeight) {
                    setActiveSection(section);
                }
            });
        };

        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    const menuItems = [
        { name: 'Home', href: '#home', id: 'home' },
        { name: 'Features', href: '#features', id: 'features' },
        { name: 'How it Works', href: '#how-it-works', id: 'how-it-works' },
        { name: 'Performance', href: '#performance', id: 'performance' },
        { name: 'FAQ', href: '#faq', id: 'faq' },
    ];

    return (
        <nav className="fixed top-4 left-4 right-4 z-50 flex items-center justify-between px-8 py-3 bg-white/70 backdrop-blur-xl border border-white/20 rounded-full shadow-[0_8px_32px_0_rgba(0,0,0,0.05)]">

            {/* ฝั่งซ้าย: Logo (กดแล้วเลื่อนขึ้นบนสุดช้าๆ) */}
            <div
                className="flex items-center gap-2.5 cursor-pointer group"
                onClick={(e) => scrollToSection(e, '#home')}
            >
                <div className="w-9 h-9 border-2 border-[#824199] rounded-full flex items-center justify-center bg-white transition-all group-hover:scale-105">
                    <div className="w-5 h-5 bg-white rounded-full flex items-center justify-center">
                        <div className="w-2.5 h-2.5 bg-yellow-400 rounded-full shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
                    </div>
                </div>
                <span className="font-bold text-lg tracking-tight text-gray-900">
                    NAKKHUTTONG
                </span>
            </div>

            {/* ฝั่งกลาง: Menu Links */}
            <div className="hidden md:flex items-center gap-2 text-[13px] font-medium text-gray-400">
                {menuItems.map((item) => (
                    <a
                        key={item.id}
                        href={item.href}
                        onClick={(e) => scrollToSection(e, item.href)}
                        className={`relative px-4 py-2 transition-colors duration-300 hover:text-[#824199] ${activeSection === item.id ? 'text-[#824199]' : ''
                            }`}
                    >
                        {item.name}
                        {activeSection === item.id && (
                            <motion.div
                                layoutId="activeTab"
                                className="absolute inset-0 bg-[#824199]/5 rounded-full -z-10"
                                transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                            />
                        )}
                    </a>
                ))}
            </div>

            {/* ฝั่งขวา: ปุ่ม Start Now */}
            <button className="bg-[#824199] text-white px-7 py-2.5 rounded-full text-xs font-bold shadow-[0_10px_20px_-5px_rgba(130,65,153,0.4)] hover:bg-[#6d3580] transition-all active:scale-95">
                Start now
            </button>
        </nav>
    );
};