import React, { useState } from 'react';
import { Activity, TrendingUp } from 'lucide-react';

// Sub-component สำหรับวาดกราฟแท่งเล็กๆ
const MiniBar = ({ heights, color }: { heights: number[]; color: string }) => (
  <div className="flex items-end gap-0.5 h-12">
    {heights.map((h, i) => (
      <span
        key={i}
        className="rounded-sm"
        style={{
          width: 6,
          height: `${h}%`,
          background: h > 60
            ? color === 'purple' ? '#824199' : '#f9d443'
            : '#e5e7eb',
          display: 'inline-block',
        }}
      />
    ))}
  </div>
);

export const StatsStack = () => {
  const [activeFilter, setActiveFilter] = useState<'Weekly' | 'Daily'>('Weekly');
  const signalBarHeights = [30, 50, 45, 70, 60, 90, 100, 80, 55, 35];
  const weeklyBarHeights = [35, 55, 40, 70, 50, 80, 100, 90, 75, 60, 45, 35];

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* 1. Signals Today */}
      <div className="bg-white rounded-[24px] p-5 shadow-[0_4px_20px_rgba(0,0,0,0.04)]">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-semibold text-gray-900">Signals Today</h2>
          <Activity size={14} className="text-[#824199]" />
        </div>
        <div className="flex items-end justify-between">
          <p className="text-4xl font-bold text-gray-900 leading-none">14</p>
          <MiniBar heights={signalBarHeights} color="purple" />
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-gray-400">Peak: <span className="text-gray-600 font-medium">09:00</span></span>
          <div className="text-right">
            <p className="text-xs text-gray-400">vs yesterday</p>
            <p className="text-sm font-semibold text-emerald-500">+5</p>
          </div>
        </div>
      </div>

      {/* 2. Win Rate */}
      <div className="bg-white rounded-[24px] p-5 shadow-[0_4px_20px_rgba(0,0,0,0.04)]">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-base font-semibold text-gray-900">Win Rate</h2>
          <TrendingUp size={14} className="text-emerald-500" />
        </div>
        <div className="flex items-end justify-between">
          <p className="text-4xl font-bold text-gray-900 leading-none">73%</p>
          <MiniBar heights={[30, 60, 100, 45, 80, 55, 70, 90, 65, 50]} color="gold" />
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-gray-400">Best: <span className="text-gray-600 font-medium">Tue</span></span>
          <div className="text-right">
            <p className="text-xs text-gray-400">vs last period</p>
            <p className="text-sm font-semibold text-emerald-500">+8%</p>
          </div>
        </div>
      </div>

      {/* 3. Portfolio Value */}
      <div className="flex-1 bg-white rounded-[24px] p-5 shadow-[0_4px_20px_rgba(0,0,0,0.04)] flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-900">Portfolio Value</h2>
            <div className="flex items-center gap-1 text-xs">
              {(['Weekly', 'Daily'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setActiveFilter(f)}
                  className={`px-3 py-1 rounded-full transition-all ${
                    activeFilter === f ? 'bg-gray-900 text-white font-medium' : 'text-gray-400 hover:text-gray-600'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-end gap-4 mb-3">
            <div>
              <p className="text-xs text-gray-400">Today</p>
              <p className="text-2xl font-bold text-gray-900">72,000 ฿</p>
            </div>
            <div>
              <p className="text-xs text-gray-400">Entry</p>
              <p className="text-2xl font-bold text-gray-900">68,400 ฿</p>
            </div>
          </div>

          <div className="flex items-end gap-0.5 h-16 mb-3">
            {weeklyBarHeights.map((h, i) => (
              <div
                key={i}
                className="flex-1 rounded-t-sm"
                style={{
                  height: `${h}%`,
                  background: h > 65
                    ? 'linear-gradient(180deg, #f9d443 0%, #d97706 100%)'
                    : 'rgba(249,212,67,0.25)',
                }}
              />
            ))}
          </div>
          <p className="text-xs text-gray-400 mb-3">Entry: <span className="text-gray-600">3 Apr</span> · Now: <span className="text-gray-600">15 Apr</span></p>
        </div>

        <div className="space-y-2 mt-auto">
          {[
            { label: 'Unrealised P&L', value: '+3,600 ฿' },
            { label: 'Realised P&L',   value: '+36,000 ฿' },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between">
              <span className="text-sm text-gray-500">{item.label}</span>
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold text-emerald-600">{item.value}</span>
                <button className="text-xs text-gray-400 border border-gray-200 rounded-full px-3 py-0.5 hover:bg-gray-50 transition">
                  Details
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};