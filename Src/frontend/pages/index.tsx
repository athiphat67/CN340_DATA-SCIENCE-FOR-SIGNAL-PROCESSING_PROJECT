import React, { useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import Lenis from 'lenis'; // อย่าลืม npm install lenis

// Import Components
import { Navbar } from "../components/Navbar";
import { HeroSection } from "../components/sections/HeroSection";
import { GoldPortfolioInsightsSection } from "../components/sections/GoldPortfolioInsightsSection";
import { HowItWorksStepsSection } from "../components/sections/HowItWorksStepsSection";
import { TransparentRationaleSection } from "../components/sections/TransparentRationaleSection";
import { CommonQuestionsSection } from "../components/sections/CommonQuestionsSection";
import { GoldTradingCTASection } from "../components/sections/GoldTradingCTASection";

// Styles
import "../styles/tailwind.css";

export const MainAppContainer = () => {

  // ระบบ Smooth Scroll ขั้นเทพ (Lenis)
  useEffect(() => {
    const lenis = new Lenis({
      duration: 2.5,
      lerp: 0.05,
      smoothWheel: true,
    });

    (window as any).lenis = lenis;

    function raf(time: number) {
      lenis.raf(time);
      requestAnimationFrame(raf);
    }
    requestAnimationFrame(raf);

    return () => {
      lenis.destroy();
      (window as any).lenis = null; // คืนค่าเมื่อปิด
    };
  }, []);

  return (
    <div className="bg-[#FCFBF7] min-h-screen"> {/* ใส่สีพื้นหลังจางๆ ให้ดูแพงแบบใน Figma */}

      {/* Navbar จะลอยอยู่บนสุดเสมอ */}
      <Navbar />

      <main className="flex flex-col items-center w-full">

        {/* ส่วน Header & Hero - ปรับระยะให้พอดีกับ Navbar */}
        <div className="w-full pt-32 flex flex-col items-center">
          {/* โลโก้กลางหน้า - ปรับขนาดและระยะตามความต้องการ */}
          <img
            className="w-[120px] md:w-[150px] lg:w-[180px] h-auto object-contain mb-8 animate-fade-in"
            alt="NAKKHUTTONG Logo"
            src="images/logo.png"
          />

          <HeroSection />
        </div>

        {/* Content Sections - ใช้ gap-32 เพื่อให้แต่ละส่วนมีพื้นที่หายใจ (Negative Space) */}
        <div className="flex flex-col gap-32 w-full max-w-screen-xl">
          <GoldPortfolioInsightsSection />
          <HowItWorksStepsSection />
          <TransparentRationaleSection />
          <CommonQuestionsSection />
          <GoldTradingCTASection />
        </div>

        {/* Footer แบบง่ายๆ เพื่อให้จบหน้าสวยงาม */}
        <footer className="py-12 text-[#11182740] text-xs">
          © 2026 NAKKHUTTONG. All rights reserved.
        </footer>
      </main>
    </div>
  );
};

// Rendering
const rootElement = document.getElementById("root");
if (rootElement) {
  const root = createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <MainAppContainer />
    </React.StrictMode>
  );
}