// frontend/components/analytics/LiveAnalysis.tsx
import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
("lucide-react");

import {
  Activity,
  Target,
  ShieldAlert,
  Zap,
  ChevronDown,
  Cpu,
  TrendingUp,
  CheckCircle2,
  BrainCircuit,
  Brain,
  Search,
  Database,
  Clock,
  ArrowLeft,
} from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface AnalysisResult {
  voting_result?: {
    final_signal: string;
    weighted_confidence: number;
  };
  data?: {
    market_state?: {
      market_data?: {
        spot_price_usd: { price_usd_per_oz: number };
        forex: { usd_thb: number };
        thai_gold_thb: { 
          buy_price_thb: number; 
          sell_price_thb: number; 
          spread_thb: number; 
        };
      };
      technical_indicators?: {
        rsi: { value: number; signal: string };
        macd: { macd_line: number; histogram: number; signal: string };
        trend: { trend: string };
      };
      portfolio?: {
        cash_balance: number;
        gold_grams: number; // รองรับระบบที่เพิ่งปรับให้คำนวณเป็นหน่วยกรัม
        unrealized_pnl: number;
      };
    };
    interval_results: Record<
      string,
      {
        signal: string;
        confidence: number;
        rationale: string;
        entry_price?: number | null;
        take_profit?: number | null;
        stop_loss?: number | null;
        elapsed_ms?: number;
        token_total?: number;
        trace: any[]; // เก็บ Array ของขั้นตอนการคิด
      }
    >;
  };
}

interface AIModel {
  id: string;
  name: string;
}

export default function LiveAnalysis() {
  const navigate = useNavigate();
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loadingText, setLoadingText] = useState("");

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  // 1. เพิ่ม State สำหรับเก็บเวลา Cooldown (หน่วยเป็นวินาที)
  const [cooldownTime, setCooldownTime] = useState(0);

  // 2. ใช้ useEffect เพื่อลดเวลาลงเรื่อยๆ ทุก 1 วินาที
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (cooldownTime > 0) {
      timer = setTimeout(() => setCooldownTime(prev => prev - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [cooldownTime]);

  const [models, setModels] = useState<AIModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>(
    "gemini-3.1-flash-lite-preview",
  );

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await fetch(`${API_URL}/api/models`);
        const data = await res.json();
        if (data.models) {
          setModels(data.models);
        }
      } catch (err) {
        console.error("Failed to fetch models:", err);
      }
    };
    fetchModels();
  }, []);

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setResult(null);

    const loadingSteps = [
        "Initializing System Services & Database...",
        "Syncing Real-time Market Data (OHLCV & Spot)...",
        "Injecting News Sentiment & Economic Calendar...",
        "Executing Logic Chain via ReAct Engine...",
        "Finalizing Strategy & Syncing Ledger...",
      ];

    let step = 0;
    setLoadingText(loadingSteps[0]);
    const interval = setInterval(() => {
      step = (step + 1) % loadingSteps.length;
      setLoadingText(loadingSteps[step]);
    }, 2500);

    try {
      const response = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: selectedModel,
          period: "7d",
          intervals: ["15m"],
        }),
      });

      if (!response.ok) throw new Error("Network response was not ok");
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error("Analysis failed:", error);
      alert("System Error: ไม่สามารถเชื่อมต่อระบบ AI ได้");
    } finally {
      clearInterval(interval);
      setIsAnalyzing(false);
    }
  };

  const finalSignal = result?.voting_result?.final_signal || "HOLD";
  const confidence = result?.voting_result?.weighted_confidence
    ? (result.voting_result.weighted_confidence * 100).toFixed(1)
    : "0.0";

  const isBuy = finalSignal === "BUY";
  const isSell = finalSignal === "SELL";

  // ปรับ Theme สีสำหรับกล่องผลลัพธ์ เน้นพื้นขาว ขอบ/text ตามสถานะ
  const themeConfig = {
    color: isBuy
      ? "text-emerald-600"
      : isSell
        ? "text-rose-600"
        : "text-amber-600",
    bg: "bg-white",
    border: isBuy
      ? "border-emerald-100"
      : isSell
        ? "border-rose-100"
        : "border-amber-100",
    gradient: isBuy
      ? "from-emerald-50/50 to-white"
      : isSell
        ? "from-rose-50/50 to-white"
        : "from-amber-50/50 to-white",
    icon: isBuy ? (
      <TrendingUp size={80} className="text-emerald-500/20" />
    ) : isSell ? (
      <TrendingUp size={80} className="text-rose-500/20 rotate-180" />
    ) : (
      <Activity size={80} className="text-amber-500/20" />
    ),
  };

  const bestInterval = result?.data?.interval_results
    ? Object.values(result.data.interval_results)[0]
    : null;

  return (
    <div className="min-h-[80vh] bg-[#fcfcfd] font-sans pb-24 pt-8 selection:bg-[#824199]/20 selection:text-[#824199]">
      <div className="max-w-6xl mx-auto px-6">

        {/* 🔙 ปุ่มย้อนกลับ (Back Button) */}
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-400 hover:text-[#824199] transition-colors duration-300 mb-6 group"
        >
          <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform duration-300" />
          <span className="text-sm font-semibold tracking-wide">Back to Dashboard</span>
        </button>

        {/* Page Header */}
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-2">
            <span className="px-3 py-1 bg-white border border-[#824199]/20 text-[#824199] rounded-full text-[10px] font-bold tracking-widest uppercase shadow-sm">
              Live Engine
            </span>
          </div>
          <h1 className="font-['Newsreader'] text-4xl md:text-5xl font-medium text-gray-900 tracking-tight mt-4">
            Market <span className="italic text-[#824199]">Analysis.</span>
          </h1>
          <p className="text-gray-500 mt-2 text-sm md:text-base font-medium">
            Deploy on-demand intelligence with your selected engine.
          </p>
        </div>

        <div className="space-y-8">
          {/* Control Panel (Luxury Card) */}
          <div className="bg-white p-6 md:p-8 rounded-[32px] shadow-sm border border-purple-100 flex flex-col md:flex-row justify-between items-center gap-6 relative z-30 overflow-visible group">
            <div className="absolute inset-0 bg-gradient-to-r from-[#824199]/0 via-[#824199]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none rounded-[32px]"></div>

            {/* Custom Dropdown: ส่วนเลือก Engine ที่มี Dropout สวยงาม */}
            <div className="w-full md:w-auto flex-1 relative z-40">
              <label className="block text-[10px] font-bold text-[#824199]/70 uppercase tracking-widest mb-2 flex items-center gap-2">
                <Cpu size={12} className="text-[#824199]" />
                Select AI Engine
              </label>

              <div className="relative w-full max-w-sm">
                {/* ส่วนปุ่มกด Dropdown */}
                <button
                  onClick={() =>
                    !isAnalyzing && setIsDropdownOpen(!isDropdownOpen)
                  }
                  disabled={isAnalyzing}
                  className={`w-full flex items-center justify-between bg-purple-50 border border-purple-200 text-[#4a2559] py-3 px-4 rounded-2xl text-sm font-semibold transition-all shadow-sm ${
                    isAnalyzing
                      ? "opacity-50 cursor-not-allowed"
                      : "hover:border-purple-300 focus:ring-4 focus:ring-purple-100"
                  }`}
                >
                  <span className="truncate">
                    {models.find((m) => m.id === selectedModel)?.name ||
                      "Select Engine"}
                  </span>
                  <div
                    className={`w-6 h-6 bg-purple-100 rounded-full flex items-center justify-center transition-transform duration-300 ${isDropdownOpen ? "rotate-180" : ""}`}
                  >
                    <ChevronDown className="text-[#824199]" size={14} />
                  </div>
                </button>

                {/* Dropout Menu (Custom List) */}
                {isDropdownOpen && (
                  <>
                    {/* Overlay สำหรับคลิกปิดข้างนอก */}
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setIsDropdownOpen(false)}
                    ></div>

                    <ul className="absolute top-full left-0 w-full mt-2 bg-white border border-purple-100 rounded-2xl shadow-[0_10px_40px_-10px_rgba(130,65,153,0.2)] py-2 z-20 overflow-hidden animate-[fadeInDown_0.2s_ease-out]">
                      {models.map((m) => (
                        <li key={m.id}>
                          <button
                            onClick={() => {
                              setSelectedModel(m.id);
                              setIsDropdownOpen(false);
                            }}
                            className={`w-full text-left px-4 py-3 text-sm font-medium transition-colors flex items-center justify-between ${
                              selectedModel === m.id
                                ? "bg-purple-50 text-[#824199]"
                                : "text-gray-600 hover:bg-purple-50/50 hover:text-[#824199]"
                            }`}
                          >
                            {m.name}
                            {selectedModel === m.id && (
                              <CheckCircle2
                                size={14}
                                className="text-[#824199]"
                              />
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            </div>

            {/* ปุ่ม Run Analysis: สีม่วงพรีเมียม ไม่เอาสีดำ */}
            <button
              onClick={handleAnalyze}
              disabled={isAnalyzing}
              className={`relative z-10 overflow-hidden px-8 py-4 rounded-2xl text-base font-bold transition-all duration-300 min-w-[220px] w-full md:w-auto group/btn ${
                isAnalyzing
                  ? "bg-purple-50 text-purple-300 cursor-not-allowed border border-purple-100"
                  : "bg-[#824199] text-white hover:shadow-[0_8px_25px_-5px_rgba(130,65,153,0.4)] border border-[#6b357e] hover:-translate-y-0.5"
              }`}
            >
              {!isAnalyzing && (
                <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover/btn:animate-[shimmer_1.5s_infinite]" />
              )}

              <span className="relative z-10 flex items-center justify-center gap-2 tracking-wide">
                {isAnalyzing ? (
                  <>
                    <svg
                      className="animate-spin h-4 w-4 text-purple-400"
                      viewBox="0 0 24 24"
                      fill="none"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
                    Processing...
                  </>
                ) : (
                  <>
                    <Zap size={18} className="text-[#f9d443]" />
                    Run Analysis
                  </>
                )}
              </span>
            </button>
          </div>

          {/* Loading State */}
          {isAnalyzing && (
            <div className="bg-white p-16 rounded-[32px] shadow-sm border border-gray-100 flex flex-col items-center justify-center text-center animate-[fadeIn_0.3s_ease-out]">
              <div className="relative w-16 h-16 mb-6">
                <div className="absolute inset-0 border-2 border-gray-50 rounded-full"></div>
                <div className="absolute inset-0 border-2 border-[#824199] rounded-full border-t-transparent animate-spin"></div>
                <div className="absolute inset-3 bg-[#824199]/5 rounded-full flex items-center justify-center">
                  <BrainCircuit
                    size={16}
                    className="text-[#824199] animate-pulse"
                  />
                </div>
              </div>
              <h3 className="font-['Newsreader'] text-2xl font-semibold text-gray-900 italic mb-2">
                Analyzing Data...
              </h3>
              <p className="text-gray-400 text-sm font-mono">{loadingText}</p>
            </div>
          )}

          {/* Results State */}
          {result && !isAnalyzing && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-[fadeIn_0.5s_ease-out]">
              {/* Left Column: Logic & Trace */}
              <div className="lg:col-span-2 space-y-8">
                {/* Hero Result Section */}
                <div
                  className={`bg-gradient-to-br ${themeConfig.gradient} border ${themeConfig.border} rounded-[32px] shadow-sm overflow-hidden flex flex-col md:flex-row`}
                >
                  <div className="md:w-2/5 p-10 flex flex-col justify-center relative border-b md:border-b-0 md:border-r border-gray-100 bg-white">
                    <div className="absolute right-4 bottom-4 pointer-events-none">
                      {themeConfig.icon}
                    </div>
                    <div className="relative z-10">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-2">
                        Decision
                      </p>
                      <h2
                        className={`text-6xl font-black tracking-tight ${themeConfig.color}`}
                      >
                        {finalSignal}
                      </h2>
                    </div>
                  </div>

                  <div className="md:w-3/5 p-10 bg-white/50 backdrop-blur-sm grid grid-cols-2 gap-x-8 gap-y-8">
                    <div>
                      <p className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1.5 mb-2">
                        <Activity size={12} className="text-[#824199]" />{" "}
                        Confidence
                      </p>
                      <p className="text-3xl font-black text-gray-900">
                        {confidence}%
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1.5 mb-2">
                        <Target size={12} className="text-gray-400" /> Entry
                        Trigger
                      </p>
                      <p className="text-2xl font-mono font-bold text-gray-800">
                        {bestInterval?.entry_price || "MARKET"}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Logic Process Block */}
                <div className="bg-white border border-gray-100 rounded-[32px] p-8 shadow-sm">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-10 h-10 bg-[#824199]/10 rounded-xl flex items-center justify-center text-[#824199]">
                      <Brain size={20} />
                    </div>
                    <h2 className="text-xl font-bold text-gray-900">
                      Thought Process
                    </h2>
                  </div>

                  <div className="space-y-6">
                    <p className="text-gray-600 leading-relaxed italic border-l-4 border-[#824199]/20 pl-6 py-2">
                      "
                      {bestInterval?.rationale ||
                        "No rationale provided by the agent."}
                      "
                    </p>

                    {/* Simulation of Trace Logic (If trace_json exists) */}
                    {result.trace_json && (
                      <div className="space-y-5 mt-8 relative before:absolute before:inset-y-0 before:left-[15px] before:w-[2px] before:bg-gray-100">
                        {formatTraceSteps(result.trace_json).map(
                          (step, idx) => (
                            <div key={step.id} className="relative pl-10">
                              <div
                                className={`absolute left-0 top-0 w-8 h-8 rounded-full flex items-center justify-center z-10 
                                      ${step.type === "DECISION" ? "bg-[#824199] text-white shadow-md ring-4 ring-white" : "bg-white border-2 border-gray-200 text-gray-400"}`}
                              >
                                {step.icon}
                              </div>
                              <div className="bg-white border border-gray-100 shadow-sm rounded-2xl p-4 transition-all hover:border-gray-200 hover:shadow-md">
                                <h4 className="text-sm font-bold text-gray-900 mb-1.5">
                                  {step.title}
                                </h4>
                                <div className="text-xs text-gray-600 leading-relaxed font-light">
                                  {step.desc}
                                </div>
                              </div>
                            </div>
                          ),
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Right Column: Technical Context & Risk Management */}
              <div className="space-y-6">
                {/* Risk Management Block */}
                <div className="bg-white border border-gray-100 rounded-[32px] p-8 shadow-sm">
                  <h3 className="text-lg font-bold mb-6 flex items-center gap-3 text-gray-900">
                    <div className="w-8 h-8 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center text-gray-600">
                      <ShieldAlert size={16} />
                    </div>
                    Risk Management
                  </h3>
                  <div className="space-y-6">
                    <div className="bg-emerald-50/50 border border-emerald-100 p-4 rounded-2xl">
                      <p className="text-[10px] text-emerald-600 uppercase font-bold tracking-widest flex items-center gap-1.5 mb-1">
                        <CheckCircle2 size={12} /> Hard-Coded TP
                      </p>
                      <p className="text-xl font-mono font-bold text-emerald-700">
                        {bestInterval?.take_profit || "N/A"}
                      </p>
                    </div>
                    <div className="bg-rose-50/50 border border-rose-100 p-4 rounded-2xl">
                      <p className="text-[10px] text-rose-600 uppercase font-bold tracking-widest flex items-center gap-1.5 mb-1">
                        <ShieldAlert size={12} /> Hard-Coded SL
                      </p>
                      <p className="text-xl font-mono font-bold text-rose-600">
                        {bestInterval?.stop_loss || "N/A"}
                      </p>
                    </div>
                    <div className="bg-gray-50 border border-gray-100 p-4 rounded-2xl">
                      <p className="text-[10px] text-gray-500 uppercase font-bold tracking-widest mb-1">
                        System Unit Target
                      </p>
                      <p className="text-base font-semibold text-gray-700">
                        Calculated in Grams (g)
                      </p>
                    </div>
                  </div>
                </div>

                {/* Execution Details Block */}
                <div className="bg-white border border-gray-100 rounded-[32px] p-8 shadow-sm">
                  <h4 className="font-bold text-gray-900 mb-6 flex items-center gap-2">
                    <Clock size={18} className="text-[#824199]" />
                    Execution Context
                  </h4>
                  <div className="space-y-4">
                    <MetaItem
                      label="Model Provider"
                      value={selectedModel.split("/")[1] || selectedModel}
                    />
                    <MetaItem label="Timeframe Tested" value="15m (Primary)" />
                    <MetaItem
                      label="Execution Time"
                      value={
                        result.elapsed_ms ? `${result.elapsed_ms}ms` : "N/A"
                      }
                    />
                    <MetaItem
                      label="Tokens Used"
                      value={
                        result.token_total
                          ? result.token_total.toLocaleString()
                          : "N/A"
                      }
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper Components & Functions
// ---------------------------------------------------------------------------

const MetaItem = ({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) => (
  <div className="flex justify-between items-center py-2.5 border-b border-gray-50 last:border-0">
    <span className="text-xs text-gray-400 font-medium">{label}</span>
    <span className="text-xs text-gray-900 font-bold truncate max-w-[150px] text-right">
      {value}
    </span>
  </div>
);

const formatTraceSteps = (traceJsonString: string) => {
  if (!traceJsonString) return [];

  try {
    const rawSteps = JSON.parse(traceJsonString);
    const formattedSteps: any[] = [];

    rawSteps.forEach((stepItem: any, index: number) => {
      // 1. THOUGHT
      if (stepItem.step.startsWith("THOUGHT") && stepItem.response?.thought) {
        formattedSteps.push({
          id: `thought-${index}`,
          type: "THOUGHT",
          title: `Iteration ${stepItem.iteration} Analysis`,
          desc: stepItem.response.thought,
          icon: <Brain size={16} />,
        });
      }

      // 2. TOOL_EXECUTION
      if (stepItem.step === "TOOL_EXECUTION") {
        const cleanToolName = stepItem.tool_name
          .replace(/_/g, " ")
          .replace(/\b\w/g, (l: string) => l.toUpperCase());

        let toolDetails: React.ReactNode = "Executed tool successfully.";

        if (stepItem.observation?.data) {
          const obsData = stepItem.observation.data;

          // กรณี: get_htf_trend
          if (stepItem.tool_name === "get_htf_trend") {
            if (obsData.status === "error") {
              toolDetails = (
                <span className="text-rose-600 font-medium bg-rose-50 px-2 py-1 rounded-md text-[11px]">
                  ⚠️ {obsData.message}
                </span>
              );
            } else {
              const { status, ...restData } = obsData;
              toolDetails = (
                <div className="mt-2 bg-purple-50/50 border border-purple-100/50 rounded-xl p-3 shadow-sm">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-2">
                    {Object.entries(restData).map(([key, value]) => (
                      <div
                        key={key}
                        className="text-[11px] flex justify-between items-center border-b border-purple-50 pb-1 last:border-0 last:pb-0"
                      >
                        <span className="text-[#824199]/70 capitalize font-medium">
                          {key.replace(/_/g, " ")}
                        </span>
                        <span className="font-bold text-gray-900">
                          {String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            }
          }
          // กรณี: get_deep_news_by_category
          else if (
            stepItem.tool_name === "get_deep_news_by_category" &&
            obsData.articles
          ) {
            toolDetails = (
              <div className="mt-3 bg-white border border-gray-100 rounded-xl p-3 shadow-sm">
                <p className="text-[10px] font-bold text-[#824199] uppercase tracking-wider mb-3 flex items-center gap-1.5">
                  <Search size={12} />
                  Analyzed {obsData.articles.length} Articles
                </p>
                <ul className="space-y-3 border-l-2 border-[#824199]/20 pl-3">
                  {obsData.articles.map((article: any, i: number) => (
                    <li
                      key={i}
                      className="text-[11px] leading-relaxed text-gray-600"
                    >
                      <span className="font-bold text-gray-900 block mb-0.5 leading-tight">
                        {article.title}
                      </span>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span className="text-gray-400 font-mono bg-gray-50 px-1.5 py-0.5 rounded text-[9px] border border-gray-100 uppercase">
                          {article.source}
                        </span>
                        {article.sentiment !== undefined &&
                          article.sentiment !== null && (
                            <span
                              className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                                article.sentiment > 0
                                  ? "text-emerald-700 bg-emerald-50 border border-emerald-100"
                                  : article.sentiment < 0
                                    ? "text-rose-700 bg-rose-50 border border-rose-100"
                                    : "text-gray-500 bg-gray-100 border border-gray-200"
                              }`}
                            >
                              Score: {article.sentiment}
                            </span>
                          )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            );
          }
          // กรณี: เครื่องมืออื่นๆ นอกเหนือจาก 2 ตัวนี้
          else {
            const { status, ...restData } = obsData;
            toolDetails = (
              <div className="mt-2">
                <pre className="text-[10px] bg-gray-50 p-3 rounded-xl border border-gray-100 text-gray-600 overflow-x-auto font-mono shadow-inner">
                  {JSON.stringify(restData, null, 2)}
                </pre>
              </div>
            );
          }
        } else if (stepItem.observation?.error) {
          toolDetails = (
            <span className="text-rose-600 font-medium bg-rose-50 px-2 py-1 rounded-md text-[11px]">
              ❌ Error: {stepItem.observation.error}
            </span>
          );
        }

        formattedSteps.push({
          id: `tool-${index}`,
          type: "ACTION",
          title: `Tool: ${cleanToolName}`,
          desc: toolDetails,
          icon: <Search size={16} />,
        });
      }

      // 3. FINAL_DECISION
      if (stepItem.response?.action === "FINAL_DECISION") {
        formattedSteps.push({
          id: `final-${index}`,
          type: "DECISION",
          title: `Final Decision: ${stepItem.response.signal}`,
          desc: stepItem.response.rationale,
          icon: <Database size={16} />,
        });
      }
    });

    return formattedSteps;
  } catch (error) {
    console.error("Failed to parse trace_json", error);
    return [];
  }
};
