import { useState, useEffect, useCallback } from 'react';
import { AlertCircle } from 'lucide-react';
import api from '../api';

interface Config {
  providers: [string, string][];
  periods: string[];
  intervals: string[];
  auto_run_intervals: Record<string, number>;
  default_auto_run: string;
}

function LlmTrace({ trace }: { trace: any[] }) {
  const SIG_COLOR: Record<string, string> = { BUY: '#4caf50', SELL: '#f44336', HOLD: '#ff9800' };
  if (!trace?.length) return (
    <p className="text-slate-500 text-sm p-4">กด ▶ Run Analysis เพื่อดู LLM logs</p>
  );
  const llmSteps = trace.filter(s => s.step_type?.startsWith('THOUGHT') || s.prompt_text);
  const totalIn  = llmSteps.reduce((a, s) => a + (s.token_input  ?? 0), 0);
  const totalOut = llmSteps.reduce((a, s) => a + (s.token_output ?? 0), 0);
  const totalAll = llmSteps.reduce((a, s) => a + (s.token_total  ?? 0), 0);

  return (
    <div style={{ fontFamily: "'JetBrains Mono',Consolas,monospace", background: '#0d1117', borderRadius: 12, padding: 16 }}>
      {/* Summary banner */}
      <div style={{ background:'#1c2128', border:'1px solid #30363d', borderRadius:8, padding:'12px 16px', marginBottom:14, display:'flex', gap:24, flexWrap:'wrap', alignItems:'center' }}>
        <span style={{ color:'#fff', fontWeight:'bold' }}>🧠 {llmSteps.length} LLM calls</span>
        <span style={{ color:'#90caf9' }}>📥 {totalIn.toLocaleString()} in</span>
        <span style={{ color:'#90caf9' }}>📤 {totalOut.toLocaleString()} out</span>
        <span style={{ color:'#fff', fontWeight:'bold' }}>🔢 {totalAll.toLocaleString()} total tokens</span>
      </div>
      {llmSteps.map((step, idx) => {
        const stepLabel = step.step_type ?? `STEP_${idx}`;
        const sig       = step.response?.signal ?? '';
        const conf      = step.response?.confidence;
        const labelColor = stepLabel.includes('FINAL') ? '#4caf50' : stepLabel.startsWith('THOUGHT') ? '#42a5f5' : '#ff9800';
        const sigColor   = SIG_COLOR[sig] ?? '#999';
        return (
          <div key={idx} style={{ background:'#161b22', border:'1px solid #30363d', borderRadius:8, padding:14, marginBottom:10 }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap' }}>
              <span style={{ fontWeight:'bold', color:labelColor, fontSize:'0.9em' }}>{stepLabel}</span>
              <span style={{ background:'#21262d', color:'#8b949e', borderRadius:12, padding:'1px 8px', fontSize:'0.78em' }}>iter {step.iteration ?? '—'}</span>
              {sig && <span style={{ background:sigColor, color:'#fff', borderRadius:4, padding:'2px 8px', fontWeight:'bold', fontSize:'0.85em' }}>{sig}{conf != null ? ` ${(conf*100).toFixed(0)}%` : ''}</span>}
            </div>
            {step.token_total > 0 && (
              <div style={{ display:'flex', gap:12, margin:'8px 0', fontSize:'0.82em', color:'#90caf9' }}>
                <span>📥 {(step.token_input??0).toLocaleString()} in</span>
                <span>📤 {(step.token_output??0).toLocaleString()} out</span>
                <span style={{ color:'#fff', fontWeight:'bold' }}>🔢 {(step.token_total??0).toLocaleString()} total</span>
                <span style={{ color:'#78909c' }}>· {step.model} ({step.provider})</span>
              </div>
            )}
            {step.prompt_text && (
              <details style={{ marginTop:10 }}>
                <summary style={{ cursor:'pointer', color:'#80cbc4', fontSize:'0.85em' }}>📋 Full Prompt ({step.prompt_text.length.toLocaleString()} chars)</summary>
                <pre style={{ background:'#0d1117', border:'1px solid #30363d', borderRadius:6, padding:12, marginTop:6, fontSize:'0.75em', color:'#c9d1d9', whiteSpace:'pre-wrap', wordBreak:'break-all', maxHeight:300, overflowY:'auto' }}>{step.prompt_text}</pre>
              </details>
            )}
            {step.response_raw && (
              <details style={{ marginTop:6 }}>
                <summary style={{ cursor:'pointer', color:'#ce93d8', fontSize:'0.85em' }}>💬 Raw Response ({step.response_raw.length.toLocaleString()} chars)</summary>
                <pre style={{ background:'#0d1117', border:'1px solid #30363d', borderRadius:6, padding:12, marginTop:6, fontSize:'0.75em', color:'#c9d1d9', whiteSpace:'pre-wrap', wordBreak:'break-all', maxHeight:300, overflowY:'auto' }}>{step.response_raw}</pre>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function AnalysisTab({ config }: { config: Config | null }) {
  const [provider, setProvider]         = useState<string>('');
  const [period, setPeriod]             = useState<string>('7d');
  const [interval, setIntervalVal]      = useState<string>('1h');
  const [autoInterval, setAutoInterval] = useState<string>('15');
  const [autoRun, setAutoRun]           = useState(false);
  const [loading, setLoading]           = useState(false);
  const [result, setResult]             = useState<any>(null);

  // Set defaults once config loads
  useEffect(() => {
    if (config && !provider) {
      setProvider(config.providers[0]?.[1] ?? 'gemini');
      setPeriod(config.periods[0] ?? '7d');
      setIntervalVal(config.intervals.includes('1h') ? '1h' : config.intervals[0]);
    }
  }, [config]);

  const runAnalysis = useCallback(async () => {
    if (!provider) return;
    setLoading(true);
    try {
      const res = await api.post('/analysis', { provider, period, intervals: [interval] });
      setResult(res.data);
    } catch (e: any) {
      console.error(e);
      alert(`Analysis failed: ${e?.response?.data?.detail ?? e.message}`);
    } finally {
      setLoading(false);
    }
  }, [provider, period, interval]);

  // Auto-run timer
  useEffect(() => {
    if (!autoRun) return;
    const sec = (config?.auto_run_intervals[autoInterval] ?? 900) * 1000;
    const t = setInterval(runAnalysis, sec);
    return () => clearInterval(t);
  }, [autoRun, autoInterval, config, runAnalysis]);

  const voting  = result?.voting_result;
  const ivResults = result?.data?.interval_results ?? {};
  const bestIv  = voting ? Object.entries(ivResults).sort(([, a]: any, [, b]: any) => b.confidence - a.confidence)[0]?.[0] : null;
  const bestIr  = bestIv ? ivResults[bestIv] : null;
  const md      = result?.data?.market_state?.market_data ?? {};
  const usdThb  = md.forex?.usd_thb ?? 0;
  const toThb   = (usdOz: number) => usdThb && usdOz ? Math.round(usdOz / 31.1035 * usdThb) : null;

  const SIG_COLOR: Record<string, string> = { BUY: 'text-emerald-400', SELL: 'text-rose-400', HOLD: 'text-amber-400' };

  return (
    <div className="space-y-6">
      {/* Controls row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass rounded-xl p-5 border-slate-700/50 space-y-3">
          <h4 className="text-sm font-bold text-slate-300">🤖 Model Settings</h4>
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider block mb-1">LLM Provider</label>
            <select value={provider} onChange={e => setProvider(e.target.value)} className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
              {config?.providers.map(([name, val]) => <option key={val} value={val}>{name}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Data Period</label>
            <select value={period} onChange={e => setPeriod(e.target.value)} className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
              {config?.periods.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>

        <div className="glass rounded-xl p-5 border-slate-700/50 space-y-3">
          <h4 className="text-sm font-bold text-slate-300">⚙️ Execution</h4>
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Candle Interval</label>
            <select value={interval} onChange={e => setIntervalVal(e.target.value)} className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
              {config?.intervals.map(iv => <option key={iv} value={iv}>{iv}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wider block mb-1">Auto-run every</label>
            <select value={autoInterval} onChange={e => setAutoInterval(e.target.value)} className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
              {Object.keys(config?.auto_run_intervals ?? {}).map(k => <option key={k} value={k}>{k} minutes</option>)}
            </select>
          </div>
        </div>

        <div className="glass rounded-xl p-5 border-slate-700/50 space-y-3">
          <h4 className="text-sm font-bold text-slate-300">🚀 Controls</h4>
          <button onClick={runAnalysis} disabled={loading || !provider}
            className="w-full py-3 bg-gradient-to-r from-amber-500 to-yellow-400 text-amber-950 font-bold rounded-xl shadow-lg hover:shadow-amber-500/20 hover:-translate-y-0.5 disabled:opacity-50 disabled:translate-y-0 transition-all">
            {loading ? '⏳ Analyzing...' : '▶ Run Analysis'}
          </button>
          <label className="flex items-center gap-3 cursor-pointer">
            <input type="checkbox" checked={autoRun} onChange={e => setAutoRun(e.target.checked)} className="w-4 h-4 accent-amber-400" />
            <span className="text-sm text-slate-300">⏰ Auto-run</span>
          </label>
          {autoRun && <p className="text-xs text-emerald-400">✅ Running every {autoInterval} min</p>}
        </div>
      </div>

      {/* Info banner */}
      <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 flex gap-4 items-start">
        <AlertCircle className="w-5 h-5 text-blue-400 shrink-0 mt-0.5" />
        <p className="text-sm text-blue-200/70">Fetches real-time market data, technical indicators, and news sentiment, then runs the LLM ReAct reasoning loop to generate a final decision.</p>
      </div>

      {/* Loading spinner */}
      {loading && (
        <div className="flex flex-col items-center py-12 gap-4">
          <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin" />
          <p className="text-slate-400 animate-pulse">Running AI pipeline...</p>
        </div>
      )}

      {/* Results */}
      {!loading && result && (
        <div className="space-y-6 animate-in fade-in duration-500">
          {/* 📊 Multi-Interval Weighted Voting */}
          <div className="glass rounded-2xl p-6 border-slate-700/50">
            <h3 className="text-sm text-slate-500 uppercase tracking-widest mb-5">🗳️ Multi-Interval Weighted Voting</h3>

            <div className="flex flex-col lg:flex-row gap-6">

              {/* ── LEFT: Per-Interval Results + Vote Tally ── */}
              <div className="flex-1 space-y-5">

                {/* Section 1: Per-Interval Results */}
                <div>
                  <p className="text-xs font-semibold text-slate-400 mb-3">📊 Per-Interval Results</p>
                  <div className="space-y-2">
                    {(voting?.interval_details ?? Object.entries(ivResults).map(([iv, ir]: [string, any]) => ({
                      interval: iv, signal: ir.signal, confidence: ir.confidence, weight: ir.weight ?? null
                    }))).map((detail: any) => {
                      const icon = detail.signal === 'BUY' ? '🟢' : detail.signal === 'SELL' ? '🔴' : '🟡';
                      const sigColor = detail.signal === 'BUY' ? 'text-emerald-400' : detail.signal === 'SELL' ? 'text-rose-400' : 'text-amber-400';
                      const conf = detail.confidence ?? 0;
                      const weight = detail.weight ?? null;
                      return (
                        <div key={detail.interval} className="flex items-center gap-3 font-mono text-sm bg-slate-900/40 rounded-lg px-4 py-2 border border-slate-800/60">
                          <span className="text-slate-400 w-8 shrink-0">{detail.interval}</span>
                          <span className="text-slate-600">→</span>
                          <span>{icon}</span>
                          <span className={`font-bold w-12 ${sigColor}`}>{detail.signal}</span>
                          <span className="text-slate-500 text-xs">conf:</span>
                          <span className="text-slate-200 w-12">{(conf * 100).toFixed(1)}%</span>
                          <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden max-w-[80px]">
                            <div className={`h-full rounded-full ${detail.signal === 'BUY' ? 'bg-emerald-400' : detail.signal === 'SELL' ? 'bg-rose-400' : 'bg-amber-400'}`}
                              style={{ width: `${conf * 100}%` }} />
                          </div>
                          {weight != null && (
                            <>
                              <span className="text-slate-500 text-xs">weight:</span>
                              <span className="text-slate-300 text-xs">{(weight * 100).toFixed(1)}%</span>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Section 2: Vote Tally */}
                {voting?.voting_breakdown && (
                  <div className="pt-4 border-t border-slate-700/40">
                    <p className="text-xs font-semibold text-slate-400 mb-3">🎯 Vote Tally</p>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {(['BUY', 'SELL', 'HOLD'] as const).map(sig => {
                        const data = voting.voting_breakdown[sig];
                        if (!data || data.count === 0) return null;
                        const icon = sig === 'BUY' ? '🟢' : sig === 'SELL' ? '🔴' : '🟡';
                        const borderColor = sig === 'BUY' ? 'border-emerald-500/30' : sig === 'SELL' ? 'border-rose-500/30' : 'border-amber-500/30';
                        const bgColor = sig === 'BUY' ? 'bg-emerald-500/5' : sig === 'SELL' ? 'bg-rose-500/5' : 'bg-amber-500/5';
                        const textColor = sig === 'BUY' ? 'text-emerald-400' : sig === 'SELL' ? 'text-rose-400' : 'text-amber-400';
                        return (
                          <div key={sig} className={`rounded-xl p-4 border ${borderColor} ${bgColor} space-y-1 font-mono text-xs`}>
                            <p className={`text-base font-black mb-2 ${textColor}`}>{icon} {sig}</p>
                            <div className="flex justify-between text-slate-400"><span>Votes</span><span className="text-slate-200">{data.count}</span></div>
                            <div className="flex justify-between text-slate-400"><span>Avg conf</span><span className="text-slate-200">{((data.avg_conf ?? 0) * 100).toFixed(1)}%</span></div>
                            <div className="flex justify-between text-slate-400"><span>Total weight</span><span className="text-slate-200">{((data.total_weight ?? 0) * 100).toFixed(1)}%</span></div>
                            <div className="flex justify-between text-slate-400"><span>Weighted score</span><span className={`font-bold ${textColor}`}>{((data.weighted_score ?? 0) * 100).toFixed(1)}%</span></div>
                            {data.intervals?.length > 0 && (
                              <p className="text-slate-600 text-[10px] pt-1">Intervals: {data.intervals.join(', ')}</p>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              {/* ── RIGHT: Final Decision panel ── */}
              <div className={`lg:w-64 flex flex-col items-center justify-center rounded-2xl p-6 border text-center shrink-0 ${
                voting?.final_signal === 'BUY'
                  ? 'bg-emerald-500/10 border-emerald-500/30'
                  : voting?.final_signal === 'SELL'
                  ? 'bg-rose-500/10 border-rose-500/30'
                  : 'bg-amber-500/10 border-amber-500/30'
              }`}>
                <p className="text-xs text-slate-500 uppercase tracking-widest mb-3">🎯 Final Decision</p>

                {/* Big signal badge */}
                <p className="text-6xl mb-2">
                  {voting?.final_signal === 'BUY' ? '🟢' : voting?.final_signal === 'SELL' ? '🔴' : '🟡'}
                </p>
                <p className={`text-4xl font-black tracking-wide mb-4 ${SIG_COLOR[voting?.final_signal] ?? 'text-slate-300'}`}>
                  {voting?.final_signal}
                </p>

                {/* Confidence */}
                <div className="w-full space-y-1 mb-4">
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>Weighted Confidence</span>
                    <span className="text-white font-bold">{((voting?.weighted_confidence ?? 0) * 100).toFixed(1)}%</span>
                  </div>
                  <div className="w-full h-2.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-700 ${
                      voting?.final_signal === 'BUY' ? 'bg-emerald-400' :
                      voting?.final_signal === 'SELL' ? 'bg-rose-400' : 'bg-amber-400'
                    }`} style={{ width: `${(voting?.weighted_confidence ?? 0) * 100}%` }} />
                  </div>
                </div>

                {/* Strength + recommendation */}
                <p className={`text-xs font-semibold mb-1 ${
                  voting?.final_signal === 'BUY' ? 'text-emerald-400' :
                  voting?.final_signal === 'SELL' ? 'text-rose-400' : 'text-amber-400'
                }`}>
                  {(voting?.weighted_confidence ?? 0) >= 0.9 ? '💪 Very Strong' :
                   (voting?.weighted_confidence ?? 0) >= 0.75 ? '💪 Strong' :
                   (voting?.weighted_confidence ?? 0) >= 0.6 ? '👍 Moderate' :
                   (voting?.weighted_confidence ?? 0) >= 0.4 ? '🤔 Weak' : '❓ Very Weak'}
                </p>
                <p className="text-[11px] text-slate-500 leading-snug">
                  {voting?.final_signal === 'BUY'
                    ? (voting?.weighted_confidence ?? 0) >= 0.8 ? 'Strong BUY — Good entry point' : 'BUY — Consider entry with caution'
                    : voting?.final_signal === 'SELL'
                    ? (voting?.weighted_confidence ?? 0) >= 0.8 ? 'Strong SELL — Good exit point' : 'SELL — Consider exit with caution'
                    : (voting?.weighted_confidence ?? 0) >= 0.5 ? 'Market is indecisive' : 'Insufficient signal, wait for clarity'}
                </p>
              </div>

            </div>
          </div>


          {/* Market state + ReAct trace */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="glass rounded-2xl p-5 border-slate-700/50">
              <h4 className="text-sm font-semibold text-slate-300 mb-3">🌐 Market State</h4>
              <pre className="text-xs text-slate-400 whitespace-pre-wrap overflow-auto max-h-64 custom-scrollbar">
                {JSON.stringify(result?.data?.market_state, null, 2)?.slice(0, 1500)}
              </pre>
            </div>
            <div className="glass rounded-2xl p-5 border-slate-700/50">
              <h4 className="text-sm font-semibold text-slate-300 mb-3">🧠 ReAct Trace — {bestIv} ({bestIr?.trace?.length ?? 0} steps)</h4>
              <div className="max-h-64 overflow-y-auto custom-scrollbar space-y-2">
                {bestIr?.trace?.map((step: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg bg-slate-900/50 border border-slate-800/50">
                    <p className="text-xs text-amber-500 font-mono uppercase mb-1">{step.step_type}</p>
                    <p className="text-xs text-slate-300 whitespace-pre-wrap">{step.content?.slice(0, 300)}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* LLM Call Logs */}
          <div className="glass rounded-2xl p-5 border-slate-700/50">
            <h4 className="text-sm font-semibold text-slate-300 mb-4">🪵 LLM Call Logs — Prompt · Response · Tokens</h4>
            <div className="max-h-[500px] overflow-y-auto custom-scrollbar">
              <LlmTrace trace={bestIr?.trace ?? []} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
