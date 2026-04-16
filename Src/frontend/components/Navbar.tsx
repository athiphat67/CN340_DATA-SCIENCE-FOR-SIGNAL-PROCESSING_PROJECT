import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
// เพิ่ม Icon ง่ายๆ (ถ้าไม่ได้ใช้ Lucide-react ให้เปลี่ยนเป็น SVG ปกติได้ครับ)
import { Menu, X } from 'lucide-react';

export const Navbar = () => {
    const [activeSection, setActiveSection] = useState('home');
    const [isOpen, setIsOpen] = useState(false); // สถานะเปิด/ปิดเมนูมือถือ

    const scrollToSection = (e: React.MouseEvent, id: string) => {
        e.preventDefault();
        setIsOpen(false); // ปิดเมนูเมื่อกดเลือก (สำคัญมากบนมือถือ)

        const lenis = (window as any).lenis;
        if (lenis) {
            lenis.scrollTo(id, {
                offset: -100,
                duration: 2.5,
                easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
            });
        } else {
            const element = document.querySelector(id);
            element?.scrollIntoView({ behavior: 'smooth' });
        }
    };

    // ... (useEffect ตัวเดิมของคุณคงไว้เหมือนเดิมได้เลย) ...
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
        <>
            <nav className="fixed top-2 left-2 right-2 z-[100] flex items-center justify-between px-5 py-2.5 bg-white/80 backdrop-blur-xl border border-white/20 rounded-full shadow-lg">

                {/* ฝั่งซ้าย: Logo */}
                <div
                    className="flex items-center gap-2.5 cursor-pointer group z-[101]"
                    onClick={(e) => scrollToSection(e, '#home')}
                >
                    <div className="w-8 h-8 md:w-9 md:h-9 border-2 border-[#824199] rounded-full flex items-center justify-center bg-white transition-all group-hover:scale-105">
                        <div className="w-4 h-4 md:w-5 md:h-5 bg-white rounded-full flex items-center justify-center">
                            <div className="w-2 md:w-2.5 h-2 md:h-2.5 bg-yellow-400 rounded-full shadow-[0_0_8px_rgba(250,204,21,0.5)]" />
                        </div>
                    </div>
                    <span className="font-bold text-sm md:text-lg tracking-tight text-gray-900">
                        NAKKHUTTHONG
                    </span>
                </div>

                {/* ฝั่งกลาง: Menu Links (Desktop เท่านั้น) */}
                <div className="hidden md:flex items-center gap-2 text-[13px] font-medium text-gray-400">
                    {menuItems.map((item) => (
                        <a
                            key={item.id}
                            href={item.href}
                            onClick={(e) => scrollToSection(e, item.href)}
                            className={`relative px-4 py-2 transition-colors duration-300 hover:text-[#824199] ${activeSection === item.id ? 'text-[#824199]' : ''}`}
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

                {/* ฝั่งขวา: ปุ่ม Start Now & Hamburger */}
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => window.location.href = '/overview'} // เปลี่ยนตรงนี้
                        className="hidden sm:block bg-[#824199] text-white px-5 md:px-7 py-2 md:py-2.5 rounded-full text-[10px] md:text-xs font-bold shadow-[0_10px_20px_-5px_rgba(130,65,153,0.4)] hover:bg-[#6d3580] transition-all active:scale-95"
                    >
                        Start now
                    </button>

                    {/* Toggle Menu บนมือถือ */}
                    <button
                        className="p-2 md:hidden text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
                        onClick={() => setIsOpen(!isOpen)}
                    >
                        {isOpen ? <X size={24} /> : <Menu size={24} />}
                    </button>
                </div>
            </nav>

            {/* Mobile Menu Overlay */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                        className="fixed top-20 left-4 right-4 z-[90] bg-white/95 backdrop-blur-2xl border border-gray-100 rounded-3xl shadow-2xl p-6 flex flex-col gap-4 md:hidden"
                    >
                        {menuItems.map((item) => (
                            <a
                                key={item.id}
                                href={item.href}
                                onClick={(e) => scrollToSection(e, item.href)}
                                className={`text-lg font-semibold px-4 py-3 rounded-2xl transition-all ${activeSection === item.id
                                    ? 'bg-[#824199] text-white'
                                    : 'text-gray-500 hover:bg-gray-50'
                                    }`}
                            >
                                {item.name}
                            </a>
                        ))}
                        <button
                            onClick={() => window.location.href = '/overview'} // เปลี่ยนตรงนี้
                            className="w-full bg-[#824199] text-white py-4 rounded-2xl font-bold mt-2"
                        >
                            Start Now
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
};