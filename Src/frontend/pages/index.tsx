import { CommonQuestionsSection } from "../components/sections/CommonQuestionsSection";
import { GoldPortfolioInsightsSection } from "../components/sections/GoldPortfolioInsightsSection";
import { GoldTradingCTASection } from "../components/sections/GoldTradingCTASection";
import { HowItWorksStepsSection } from "../components/sections/HowItWorksStepsSection";
import { TransparentRationaleSection } from "../components/sections/TransparentRationaleSection";
import { Navbar } from "../components/Navbar"; // นำ Navbar มาใช้
import "../styles/tailwind.css";

import { createRoot } from 'react-dom/client';

export const MainAppContainer= () => {
  return (
    <div className="flex flex-col max-w-screen-xl min-h-screen items-center pt-0 pb-[61px] px-0 relative [background:radial-gradient(50%_50%_at_50%_25%,rgba(254,249,231,1)_0%,rgba(255,254,248,1)_60%)]">
      
      {/* 1. ใส่ Navbar แทนที่รูปภาพ */}
      <Navbar />

      {/* 2. ห่อหุ้มเนื้อหาที่เหลือ และเว้นระยะด้านบน (mt-24) เพื่อไม่ให้โดน Navbar บัง */}
      <div className="flex flex-col items-center gap-[50px] w-full mt-24">
        
        <img
          className="relative w-64 md:w-80 lg:w-[200px] h-auto object-contain mx-auto mt-12"
          alt="Hero section"
          src="/logo.png" 
        />
        
        <img
          className="grid grid-cols-12 grid-rows-[367px] max-w-6xl w-[1192.52px] h-[467px] gap-6 pt-0 pb-[35px] px-8"
          alt="Widgets grid"
          src="" // ใส่ไรก็ไม่รุ้
        />

        <GoldPortfolioInsightsSection />
        <HowItWorksStepsSection />
        <TransparentRationaleSection />
        <CommonQuestionsSection />
        <GoldTradingCTASection />
        
      </div>
    </div>
  );
};

const rootElement = document.getElementById("root");
if (rootElement) {
  const root = createRoot(rootElement);
  root.render(<MainAppContainer />);
}