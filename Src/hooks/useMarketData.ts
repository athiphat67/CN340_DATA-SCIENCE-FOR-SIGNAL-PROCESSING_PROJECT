import { useState, useEffect } from 'react';

// ─── Type Definitions ────────────────────────────────────────────────────────
export interface OHLCPoint {
  x: number; // Timestamp (Milliseconds)
  y: [number, number, number, number]; // [Open, High, Low, Close]
}

export interface TimeSeriesPoint {
  x: number; // Timestamp
  y: number; // Value
}

export interface TechDataPoint {
  x: number;
  bb_pct_b: number;    // Bollinger Bands %B
  atr_thb: number;     // Average True Range (Market Volatility)
  rsi: number;         // Relative Strength Index
  macd_line: number;   // MACD Line
  macd_hist: number;   // MACD Histogram
  confidence: number;  // AI Confidence Score
  ai_signal: string;   // 'BUY' | 'SELL' | 'HOLD'
}

// ─── Custom Hook ──────────────────────────────────────────────────────────────
export const useMarketData = () => {
  const [ohlcData, setOhlcData] = useState<OHLCPoint[]>([]);
  const [usdThbData, setUsdThbData] = useState<TimeSeriesPoint[]>([]);
  const [techData, setTechData] = useState<TechDataPoint[]>([]);
  const [currentStats, setCurrentStats] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [timeframe, setTimeframe] = useState<'1H' | '4H' | '1D' | '1W'>('4H');

  useEffect(() => {
    setIsLoading(true);

    // 🛠️ ฟังก์ชันจำลองการสร้างข้อมูลขนาดใหญ่ (อิงจาก Random Walk) 
    // *เมื่อทำ Backend เสร็จ สามารถเปลี่ยนฟังก์ชันนี้เป็นการ fetch() ข้อมูลจาก Database ได้เลย
    const generateRealisticData = (tf: string) => {
      let dataPointsCount = 0;
      let intervalMs = 0;

      // กำหนดปริมาณแท่งเทียนและระยะห่างของเวลาตาม Timeframe
      switch (tf) {
        case '1H': dataPointsCount = 168; intervalMs = 60 * 60 * 1000; break; // ย้อนหลัง 7 วัน
        case '4H': dataPointsCount = 180; intervalMs = 4 * 60 * 60 * 1000; break; // ย้อนหลัง 1 เดือน
        case '1D': dataPointsCount = 365; intervalMs = 24 * 60 * 60 * 1000; break; // ย้อนหลัง 1 ปี
        case '1W': dataPointsCount = 156; intervalMs = 7 * 24 * 60 * 60 * 1000; break; // ย้อนหลัง 3 ปี
        default: dataPointsCount = 100; intervalMs = 4 * 60 * 60 * 1000;
      }

      // เวลาเริ่มต้น (นับย้อนหลังจากปัจจุบัน)
      let currentTime = new Date('2026-04-18T00:00:00Z').getTime() - (dataPointsCount * intervalMs);
      
      // ตัวแปรราคาเริ่มต้น
      let currentGoldPrice = 38500; 
      let currentUsdThb = 35.80;
      let currentRsi = 50;

      const generatedOhlc: OHLCPoint[] = [];
      const generatedUsdThb: TimeSeriesPoint[] = [];
      const generatedTech: TechDataPoint[] = [];

      for (let i = 0; i < dataPointsCount; i++) {
        // --- 1. จำลองราคาทอง (OHLC) ---
        const volatility = tf === '1D' || tf === '1W' ? 400 : 150; 
        const open = currentGoldPrice;
        const high = open + (Math.random() * volatility);
        const low = open - (Math.random() * volatility);
        const close = low + Math.random() * (high - low); // ราคาปิดสุ่มอยู่ระหว่าง H-L

        generatedOhlc.push({
          x: currentTime,
          y: [
            Math.round(open), 
            Math.round(high), 
            Math.round(low), 
            Math.round(close)
          ]
        });

        currentGoldPrice = close + ((Math.random() - 0.5) * 50); // อัปเดตราคาเปิดแท่งถัดไป

        // --- 2. จำลองอัตราแลกเปลี่ยน (USD/THB) ---
        const fxVolatility = tf === '1D' || tf === '1W' ? 0.15 : 0.05;
        currentUsdThb = currentUsdThb + ((Math.random() - 0.5) * fxVolatility);
        
        generatedUsdThb.push({
          x: currentTime,
          y: Number(currentUsdThb.toFixed(3))
        });

        // --- 3. จำลอง Technical Indicators & AI Signals ---
        currentRsi = Math.max(10, Math.min(90, currentRsi + ((Math.random() - 0.5) * 15)));
        const bb_pct = 0.5 + (Math.sin(i / 5) * 0.6) + (Math.random() * 0.2); // Bollinger %B (-0.2 ถึง 1.2)
        const atr = tf === '1D' ? 450 + (Math.random() * 200) : 150 + (Math.random() * 100);
        const macdLine = (Math.sin(i / 10) * 10) + (Math.random() * 2);
        const macdHist = (Math.cos(i / 5) * 5) + (Math.random() * 1);
        const conf = 50 + (Math.random() * 45); // ความมั่นใจ 50-95%
        
        // AI Logic เบื้องต้นในการแจก Signal ให้ตรงกับกราฟ
        let signal = 'HOLD';
        if (currentRsi > 70 || bb_pct > 1) signal = 'SELL';
        else if (currentRsi < 30 || bb_pct < 0) signal = 'BUY';

        generatedTech.push({
          x: currentTime,
          bb_pct_b: Number(bb_pct.toFixed(2)),
          atr_thb: Number(atr.toFixed(0)),
          rsi: Number(currentRsi.toFixed(1)),
          macd_line: Number(macdLine.toFixed(2)),
          macd_hist: Number(macdHist.toFixed(2)),
          confidence: Number(conf.toFixed(0)),
          ai_signal: signal
        });

        currentTime += intervalMs;
      }

      return { generatedOhlc, generatedUsdThb, generatedTech };
    };

    // ⏳ จำลองการโหลดข้อมูลจาก API (Delay 0.8 วินาที)
    setTimeout(() => {
      const { generatedOhlc, generatedUsdThb, generatedTech } = generateRealisticData(timeframe);
      
      // ดึงค่าของแท่งสุดท้าย (Current State) มาโชว์บน Header
      const latestGold = generatedOhlc[generatedOhlc.length - 1].y[3];
      const latestFx = generatedUsdThb[generatedUsdThb.length - 1].y;

      setOhlcData(generatedOhlc);
      setUsdThbData(generatedUsdThb);
      setTechData(generatedTech);
      
      setCurrentStats({
        current_thb: Math.round(latestGold),
        current_usd: Math.round(latestGold / latestFx * 1.9), // คำนวณ USD/oz แบบคร่าวๆ (อิงตามสูตรแปลงน้ำหนัก)
        usd_thb: Number(latestFx.toFixed(2)),
        trend: latestGold > generatedOhlc[generatedOhlc.length - 5].y[3] ? "BULLISH" : "BEARISH",
        market_status: "LIVE DATA",
        is_weekend: false
      });

      setIsLoading(false);
    }, 800);

  }, [timeframe]); // Trigger ใหม่อีกครั้งเมื่อ User กดเปลี่ยน Timeframe

  // ส่งข้อมูลทั้งหมดออกไปให้หน้า UI ใช้งาน
  return { 
    ohlcData, 
    usdThbData, 
    techData, 
    currentStats, 
    isLoading, 
    timeframe, 
    setTimeframe 
  };
};