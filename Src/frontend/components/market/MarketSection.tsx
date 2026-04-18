import React from 'react';
import Chart from 'react-apexcharts';
import { OverviewHeader } from '../overview/OverviewHeader';
import { useMarketData } from '../../../hooks/useMarketData';
import { Globe, Coins, Activity, TrendingUp, Loader2, Radio } from 'lucide-react';

export const MarketSection = () => {
  // 🟢 เปลี่ยนจาก generatedTech เป็น techData ตามที่ Export ออกมาจาก Hook
  const { ohlcData, usdThbData, techData, currentStats, isLoading, timeframe, setTimeframe } = useMarketData();

  // ⚙️ 1. การตั้งค่ากราฟแท่งเทียน XAU/THB
  const candlestickOptions: any = {
    chart: {
      type: 'candlestick',
      toolbar: { show: true, tools: { download: false, selection: true, zoom: true, pan: true } },
      background: 'transparent',
      animations: { enabled: false }
    },
    title: { text: 'XAU/THB (Thai Gold)', align: 'left', style: { fontSize: '14px', fontWeight: 900, color: '#111827' } },
    xaxis: {
      type: 'datetime',
      labels: { style: { colors: '#9ca3af', fontSize: '10px', fontWeight: 600 } },
      axisBorder: { show: false },
      axisTicks: { show: false }
    },
    yaxis: {
      tooltip: { enabled: true },
      labels: { 
        formatter: (value: number) => `฿${value.toLocaleString()}`,
        style: { colors: '#824199', fontSize: '11px', fontWeight: 700 } 
      }
    },
    plotOptions: {
      candlestick: {
        colors: { upward: '#10b981', downward: '#ef4444' },
        wick: { useFillColor: true }
      }
    },
    grid: { borderColor: '#f1f5f9', strokeDashArray: 4, xaxis: { lines: { show: true } }, yaxis: { lines: { show: true } } },
    tooltip: { theme: 'light', style: { fontSize: '12px', fontFamily: 'inherit' } }
  };

  // ⚙️ 2. การตั้งค่ากราฟเส้น USD/THB
  const lineOptions: any = {
    chart: { type: 'area', toolbar: { show: false }, background: 'transparent', animations: { enabled: false } },
    title: { text: 'USD/THB Exchange Rate', align: 'left', style: { fontSize: '14px', fontWeight: 900, color: '#111827' } },
    colors: ['#3b82f6'],
    fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0, stops: [0, 90, 100] } },
    dataLabels: { enabled: false },
    stroke: { curve: 'smooth', width: 2 },
    xaxis: { type: 'datetime', labels: { style: { colors: '#9ca3af', fontSize: '10px', fontWeight: 600 } }, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis: { labels: { formatter: (value: number) => value.toFixed(2), style: { colors: '#64748b', fontSize: '11px', fontWeight: 700 } } },
    grid: { borderColor: '#f1f5f9', strokeDashArray: 4 },
    tooltip: { theme: 'light', y: { formatter: (val: number) => `฿${val.toFixed(2)}` } }
  };

  return (
    <section className="w-full min-h-screen pb-12 relative overflow-hidden" style={{ background: '#FCFBF7' }}>
      
      {/* Background Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-[#824199]/5 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[10%] right-[-5%] w-[400px] h-[400px] bg-emerald-500/5 rounded-full blur-[100px] pointer-events-none" />

      <OverviewHeader />
      
      <div className="px-6 mt-12 relative z-20 max-w-7xl mx-auto">
        
        {/* 🟢 Header */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
               <Globe size={16} className="text-[#824199]" />
               <p className="text-[10px] font-bold text-[#824199] uppercase tracking-[0.3em]">Advanced Charting</p>
            </div>
            <h1 className="text-4xl font-black text-gray-900 tracking-tight">Market Analytics</h1>
          </div>
          
          {!isLoading && (
            <div className="flex items-center gap-2 px-4 py-2 bg-white rounded-full border border-gray-100 shadow-sm">
              <Radio size={14} className={currentStats?.is_weekend ? 'text-gray-400' : 'text-emerald-500 animate-pulse'} />
              <span className="text-[10px] font-black uppercase tracking-widest text-gray-600">
                {currentStats?.market_status}
              </span>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-[60vh] text-[#824199]">
            <Loader2 className="animate-spin mb-4" size={40} />
            <p className="text-sm font-bold uppercase tracking-widest text-gray-500">Loading Chart Data...</p>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            
            {/* 🟢 Top Row: Live Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <StatCard title="Thai Gold (Sell)" value={`${currentStats?.current_thb.toLocaleString()}`} unit="THB/g" icon={<Coins size={18} />} color="emerald" />
              <StatCard title="Global Spot" value={`$${currentStats?.current_usd.toLocaleString()}`} unit="/ oz" icon={<Globe size={18} />} color="blue" />
              <StatCard title="Exchange Rate" value={`${currentStats?.usd_thb.toFixed(2) || "0.00"}`} unit="THB/USD" icon={<Activity size={18} />} color="purple" />
              <StatCard title="Trend Status" value={currentStats?.trend} unit="" icon={<TrendingUp size={18} />} color="yellow" isText />
            </div>

            {/* 🟢 Main Candlestick Chart (XAU/THB) */}
            <div className="bg-white p-2 rounded-[32px] border border-gray-100 shadow-sm">
              <div className="px-6 pt-6 flex justify-between items-center mb-2">
                <div className="flex bg-gray-50 p-1 rounded-xl border border-gray-100">
                  {(['1H', '4H', '1D', '1W'] as const).map((tf) => (
                    <button 
                      key={tf} onClick={() => setTimeframe(tf)}
                      className={`px-4 py-1.5 rounded-lg text-[10px] font-black tracking-widest transition-all ${
                        timeframe === tf ? 'bg-white text-[#824199] shadow-sm' : 'text-gray-400 hover:text-gray-700'
                      }`}
                    >
                      {tf}
                    </button>
                  ))}
                </div>
              </div>
              
              <Chart options={candlestickOptions} series={[{ name: 'XAU/THB', data: ohlcData }]} type="candlestick" height={450} />
            </div>

            {/* 🟢 Secondary Chart (USD/THB) */}
            <div className="bg-white p-2 rounded-[32px] border border-gray-100 shadow-sm mt-2">
              <Chart options={lineOptions} series={[{ name: 'USD/THB', data: usdThbData }]} type="area" height={250} />
            </div>

            {/* 🟢 Advanced Volatility & Band Width */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
              
              {/* 1. Bollinger Bands %B Chart */}
              <div className="bg-white p-6 rounded-[32px] border border-gray-100 shadow-sm relative">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <Activity size={16} className="text-blue-500" />
                    <h3 className="text-sm font-black text-gray-900 uppercase tracking-widest">Bollinger %B</h3>
                  </div>
                  <div className="flex gap-3 text-[9px] font-bold uppercase tracking-widest">
                    <span className="flex items-center gap-1 text-rose-500"><div className="w-2 h-2 rounded-full bg-rose-200" /> Upper Band (1)</span>
                    <span className="flex items-center gap-1 text-emerald-500"><div className="w-2 h-2 rounded-full bg-emerald-200" /> Lower Band ({'<'}0)</span>
                  </div>
                </div>
                
                <div className="h-[200px] w-full mt-2">
                  <Chart 
                    type="area"
                    height={200}
                    // 🟢 แก้จาก generatedTech เป็น techData
                    series={[{ name: 'BB %B', data: techData.map((d: any) => ({ x: d.x, y: d.bb_pct_b })) }]}                    options={{
                      chart: { toolbar: { show: false }, background: 'transparent', animations: { enabled: false } },
                      colors: ['#3b82f6'],
                      fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.3, opacityTo: 0 } },
                      dataLabels: { enabled: false },
                      stroke: { curve: 'smooth', width: 2 },
                      xaxis: { type: 'datetime', labels: { show: false }, axisBorder: { show: false }, axisTicks: { show: false } },
                      yaxis: { 
                        labels: { style: { colors: '#9ca3af', fontSize: '10px', fontWeight: 600 } },
                        max: 1.5, min: -0.5, tickAmount: 4
                      },
                      grid: { borderColor: '#f1f5f9', strokeDashArray: 4 },
                      annotations: {
                        // 🟢 แก้จาก yAxis เป็น yaxis (พิมพ์เล็กทั้งหมดตามสเปคของ ApexCharts)
                        yaxis: [
                          { y: 1.0, borderColor: '#ef4444', strokeDashArray: 4, label: { text: 'Upper Band', style: { color: '#fff', background: '#ef4444' } } },
                          { y: 0.0, borderColor: '#10b981', strokeDashArray: 4, label: { text: 'Lower Band', style: { color: '#fff', background: '#10b981' } } }
                        ]
                      },
                      tooltip: { theme: 'light' }
                    }}
                  />
                </div>
              </div>

              {/* 2. ATR (Average True Range) Chart */}
              <div className="bg-white p-6 rounded-[32px] border border-gray-100 shadow-sm">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <TrendingUp size={16} className="text-orange-500" />
                    <h3 className="text-sm font-black text-gray-900 uppercase tracking-widest">Market Volatility (ATR)</h3>
                  </div>
                  <span className="text-[9px] font-bold text-gray-400 bg-gray-50 px-2 py-1 rounded-md">THB/GRAM SPREAD</span>
                </div>
                
                <div className="h-[200px] w-full mt-2">
                  <Chart 
                    type="bar"
                    height={200}
                    // 🟢 แก้จาก generatedTech เป็น techData
                    series={[{ name: 'ATR (THB)', data: techData.map((d: any) => ({ x: d.x, y: d.atr_thb })) }]}           options={{
                      chart: { toolbar: { show: false }, background: 'transparent', animations: { enabled: false } },
                      colors: ['#f97316'],
                      plotOptions: { bar: { borderRadius: 2, columnWidth: '60%' } },
                      dataLabels: { enabled: false },
                      xaxis: { type: 'datetime', labels: { show: false }, axisBorder: { show: false }, axisTicks: { show: false } },
                      yaxis: { 
                        labels: { 
                          formatter: (val) => `฿${val.toFixed(0)}`,
                          style: { colors: '#9ca3af', fontSize: '10px', fontWeight: 600 } 
                        }
                      },
                      grid: { borderColor: '#f1f5f9', strokeDashArray: 4 },
                      tooltip: { theme: 'light' }
                    }}
                  />
                </div>
              </div>

            </div>

          </div>
        )}
      </div>
    </section>
  );
};

// --- Helper Component ---
const StatCard = ({ title, value, unit, icon, color, isText = false }: any) => {
  const colors: any = {
    emerald: 'text-emerald-500 bg-emerald-50 border-emerald-100',
    blue: 'text-blue-500 bg-blue-50 border-blue-100',
    purple: 'text-[#824199] bg-purple-50 border-purple-100',
    yellow: 'text-yellow-600 bg-yellow-50 border-yellow-100',
  };

  return (
    <div className="bg-white p-5 rounded-2xl border border-gray-100 shadow-sm flex flex-col justify-between h-[120px]">
      <div className="flex items-center gap-2">
        <div className={`p-2 rounded-xl ${colors[color]}`}>{icon}</div>
        <span className="text-[10px] font-black text-gray-400 uppercase tracking-widest">{title}</span>
      </div>
      <div className="flex items-baseline gap-1 mt-auto">
        <span className={`font-black ${isText ? 'text-2xl text-gray-800' : 'text-3xl text-gray-900'} tracking-tighter`}>{value}</span>
        <span className="text-xs font-bold text-gray-400">{unit}</span>
      </div>
    </div>
  );
};