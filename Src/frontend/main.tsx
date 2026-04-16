import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

// 1. นำเข้าหน้า Overview จากโฟลเดอร์ overview
import { OverviewSection } from './components/overview/OverviewSection';

// 2. นำเข้าหน้า Signals และ Detail จากโฟลเดอร์ signals
import { SignalsSection } from './components/signals/SignalsSection';
import { SignalDetail } from './components/signals/SignalDetail'; 

// 3. นำเข้า Navbar (อยู่ระดับเดียวกับโฟลเดอร์ overview/signals)
import { Navbar } from './components/Navbar';

function App() {
  return (
    <BrowserRouter>
      {/* วาง Navbar ไว้ด้านบนสุด */}
      <Navbar /> 
      
      <Routes>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewSection />} />
        <Route path="/signals" element={<SignalsSection />} />
        <Route path="/signals/:id" element={<SignalDetail />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;