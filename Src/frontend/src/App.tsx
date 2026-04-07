import { useState, useEffect } from 'react';
import { LineChart, BarChart3, Activity, History, Briefcase, Zap } from 'lucide-react';
import api from './api';

import HomeTab from './components/HomeTab';
import AnalysisTab from './components/AnalysisTab';
import ChartTab from './components/ChartTab';
import HistoryTab from './components/HistoryTab';
import PortfolioTab from './components/PortfolioTab';

export default function App() {
  const [activeTab, setActiveTab] = useState('analysis');
  const [config, setConfig] = useState<any>(null);

  useEffect(() => {
    api.get('/config').then(res => setConfig(res.data)).catch(console.error);
  }, []);

  const tabs = [
    { id: 'home', icon: Activity, label: 'Overview' },
    { id: 'analysis', icon: Zap, label: 'Live Analysis' },
    { id: 'chart', icon: LineChart, label: 'Chart' },
    { id: 'history', icon: History, label: 'Run History' },
    { id: 'portfolio', icon: Briefcase, label: 'Portfolio' },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      {/* Background decoration */}
      <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] bg-blue-600/20 rounded-full blur-[120px]" />
        <div className="absolute top-[20%] right-[-10%] w-[40%] h-[60%] bg-amber-500/10 rounded-full blur-[100px]" />
      </div>

      <div className="relative z-10 flex h-screen overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 glass border-r border-slate-800/50 flex flex-col bg-slate-900/40">
          <div className="p-6">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-amber-400 to-yellow-200 bg-clip-text text-transparent flex items-center gap-2">
              <BarChart3 className="w-6 h-6 text-amber-400" />
              GoldTrader
            </h1>
            <p className="text-xs text-slate-500 mt-1 uppercase tracking-wider font-semibold">AI Agent V3.4</p>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-2">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${
                    isActive 
                      ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20 shadow-[0_0_15px_rgba(59,130,246,0.1)]' 
                      : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isActive ? 'text-blue-400' : 'text-slate-500'}`} />
                  <span className="font-medium">{tab.label}</span>
                </button>
              );
            })}
          </nav>
          
          <div className="p-4 border-t border-slate-800/50">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              API Connected
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto w-full p-8 custom-scrollbar">
          <header className="mb-8 flex justify-between items-center">
            <div>
              <h2 className="text-3xl font-bold tracking-tight text-white mb-2">
                {tabs.find(t => t.id === activeTab)?.label}
              </h2>
              <p className="text-slate-400">
                {activeTab === 'analysis' && 'Execute multi-step reasoning and generate trading signals.'}
                {activeTab === 'portfolio' && 'Manage your Aom NOW simulated portfolio state.'}
                {activeTab === 'history' && 'Review past agent executions and reasoning traces.'}
                {activeTab === 'chart' && 'Real-time XAU/USD technical analysis tools.'}
                {activeTab === 'home' && 'System status and high-level performance metrics.'}
              </p>
            </div>
          </header>

          <div className="glass rounded-2xl p-6 min-h-[400px] border border-slate-800 bg-slate-900/30 shadow-2xl">
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              {activeTab === 'home'      && <HomeTab />}
              {activeTab === 'analysis'  && <AnalysisTab config={config} />}
              {activeTab === 'chart'     && <ChartTab config={config} />}
              {activeTab === 'history'   && <HistoryTab />}
              {activeTab === 'portfolio' && <PortfolioTab />}
            </div>
          </div>
        </main>
      </div>
      
      {/* Global generic CSS for scrollbars etc. embedded simply */}
      <style>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background-color: rgba(51, 65, 85, 0.5);
          border-radius: 20px;
        }
      `}</style>
    </div>
  );
}
