import { useState, useEffect } from 'react';
import { RefreshCw, Search, Download } from 'lucide-react';
import api from '../api';

function LlmLogsPanel({ logs, trace }: { logs: any[]; trace: any[] }) {
  const items = logs.length > 0 ? logs : trace?.filter(s => s.step_type?.startsWith('THOUGHT') || s.prompt_text) ?? [];
  if (!items.length) return <p className="text-slate-500 text-sm p-4 font-mono">ยังไม่มี LLM log</p>;
  return (
    <div style={{ fontFamily: 'monospace', background: '#0d1117', borderRadius: 12, padding: 12, marginTop: 8, maxHeight: 400, overflowY: 'auto' }}>
      {items.map((item: any, i: number) => {
        const label   = item.step_type ?? item.step ?? `STEP_${i}`;
        const color   = label.includes('FINAL') ? '#4caf50' : label.startsWith('THOUGHT') ? '#42a5f5' : '#ff9800';
        const prompt  = item.full_prompt ?? item.prompt_text ?? '';
        const resp    = item.full_response ?? item.response_raw ?? '';
        const tokTotal = item.token_total ?? 0;
        return (
          <div key={i} style={{ border: '1px solid #30363d', borderRadius: 8, padding: 12, marginBottom: 8 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ color, fontWeight: 'bold', fontSize: '0.88em' }}>{label}</span>
              {item.signal && <span style={{ background: '#4caf50', color: '#fff', borderRadius: 4, padding: '1px 6px', fontSize: '0.78em' }}>{item.signal}</span>}
            </div>
            {tokTotal > 0 && <p style={{ color: '#90caf9', fontSize: '0.78em', margin: '6px 0' }}>🔢 {tokTotal.toLocaleString()} tokens · {item.model ?? item.provider ?? ''}</p>}
            {item.rationale && <p style={{ color: '#b0bec5', fontSize: '0.8em', borderLeft: '3px solid #42a5f5', paddingLeft: 8 }}>{item.rationale.slice(0, 200)}</p>}
            {prompt && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ cursor: 'pointer', color: '#80cbc4', fontSize: '0.82em' }}>📋 Prompt ({prompt.length.toLocaleString()} chars)</summary>
                <pre style={{ background: '#0d1117', color: '#c9d1d9', fontSize: '0.72em', whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto', marginTop: 4, padding: 8, borderRadius: 4, border: '1px solid #30363d' }}>{prompt}</pre>
              </details>
            )}
            {resp && (
              <details style={{ marginTop: 4 }}>
                <summary style={{ cursor: 'pointer', color: '#ce93d8', fontSize: '0.82em' }}>💬 Response ({resp.length.toLocaleString()} chars)</summary>
                <pre style={{ background: '#0d1117', color: '#c9d1d9', fontSize: '0.72em', whiteSpace: 'pre-wrap', maxHeight: 200, overflowY: 'auto', marginTop: 4, padding: 8, borderRadius: 4, border: '1px solid #30363d' }}>{resp}</pre>
              </details>
            )}
          </div>
        );
      })}
    </div>
  );
}

function RunDetail({ run }: { run: any }) {
  const fields = [
    ['Run ID',      `#${run.id}`],
    ['Time',        run.run_at],
    ['Provider',    run.provider],
    ['Interval',    run.interval_tf],
    ['Period',      run.period],
    ['Signal',      run.signal],
    ['Confidence',  `${(run.confidence * 100).toFixed(2)}%`],
    ['Entry Price', run.entry_price ?? '—'],
    ['Stop Loss',   run.stop_loss ?? '—'],
    ['Take Profit', run.take_profit ?? '—'],
    ['Gold Price',  run.gold_price ?? '—'],
    ['RSI',         run.rsi ?? '—'],
    ['MACD',        run.macd_line ?? '—'],
    ['Trend',       run.trend ?? '—'],
    ['Iterations',  run.iterations_used ?? '—'],
    ['Tool Calls',  run.tool_calls_used ?? '—'],
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
      {fields.map(([label, val]) => (
        <div key={label} className="bg-slate-900/50 rounded-lg p-2 border border-slate-800">
          <p className="text-slate-500">{label}</p>
          <p className={`font-semibold ${label === 'Signal' ? (val === 'BUY' ? 'text-emerald-400' : val === 'SELL' ? 'text-rose-400' : 'text-amber-400') : 'text-slate-200'}`}>{String(val)}</p>
        </div>
      ))}
      {run.rationale && (
        <div className="col-span-2 md:col-span-3 bg-slate-900/50 rounded-lg p-3 border border-slate-800">
          <p className="text-slate-500 mb-1">Rationale</p>
          <p className="text-slate-300 text-xs whitespace-pre-wrap">{run.rationale}</p>
        </div>
      )}
    </div>
  );
}

export default function HistoryTab() {
  const [runs, setRuns]       = useState<any[]>([]);
  const [stats, setStats]     = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch]   = useState('');
  const [signal, setSignal]   = useState('ALL');
  const [limit, setLimit]     = useState(50);

  // Run detail state
  const [runIdInput, setRunIdInput] = useState('');
  const [detail, setDetail]         = useState<any>(null);
  const [llmLogs, setLlmLogs]       = useState<any>({ logs: [], trace: [] });
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      if (signal !== 'ALL') params.set('signal', signal);
      if (search) params.set('search', search);
      const res = await api.get(`/history?${params}`);
      setRuns(res.data.runs ?? []);
      setStats(res.data.stats);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadDetail = async () => {
    const id = parseInt(runIdInput.replace('#', ''));
    if (isNaN(id)) return;
    setDetailLoading(true);
    try {
      const [det, logs] = await Promise.all([
        api.get(`/history/${id}`),
        api.get(`/history/${id}/llm-logs`),
      ]);
      setDetail(det.data);
      setLlmLogs(logs.data);
    } catch (e: any) {
      alert(`Not found: ${e?.response?.data?.detail ?? e.message}`);
    } finally { setDetailLoading(false); }
  };

  const exportCsv = () => {
    const header = 'id,signal,confidence,provider,run_at,gold_price';
    const rows = runs.map(r => `${r.id},${r.signal},${r.confidence},${r.provider},${r.run_at},${r.gold_price}`);
    const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'history.csv'; a.click();
  };

  useEffect(() => { fetchHistory(); }, []);
  useEffect(() => { fetchHistory(); }, [signal, limit]);

  const SIG: Record<string, string> = { BUY: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20', SELL: 'bg-rose-500/10 text-rose-400 border-rose-500/20', HOLD: 'bg-amber-500/10 text-amber-400 border-amber-500/20' };

  return (
    <div className="space-y-6">
      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Total Runs', val: stats.total_runs, color: 'text-white' },
            { label: 'BUY',        val: stats.buy_signals,  color: 'text-emerald-400' },
            { label: 'SELL',       val: stats.sell_signals, color: 'text-rose-400' },
            { label: 'Avg Conf',   val: `${(stats.avg_confidence * 100).toFixed(0)}%`, color: 'text-blue-400' },
          ].map(({ label, val, color }) => (
            <div key={label} className="glass rounded-xl p-4 border-slate-700/50">
              <p className="text-xs text-slate-500">{label}</p>
              <p className={`text-2xl font-black ${color}`}>{val}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[180px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search} onChange={e => setSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchHistory()}
            placeholder="Search by signal / provider..."
            className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <select value={signal} onChange={e => setSignal(e.target.value)} className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
          {['ALL', 'BUY', 'SELL', 'HOLD'].map(s => <option key={s}>{s}</option>)}
        </select>
        <select value={limit} onChange={e => setLimit(Number(e.target.value))} className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
          {[10, 20, 50, 100].map(n => <option key={n} value={n}>{n} rows</option>)}
        </select>
        <button onClick={fetchHistory} className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-sm transition-colors">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
        <button onClick={exportCsv} className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-sm transition-colors">
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="glass rounded-xl border border-slate-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-slate-400 uppercase bg-slate-900/50 border-b border-slate-700/50">
              <tr>
                {['ID','Time','Signal','Confidence','Gold Price','Provider',''].map(h => (
                  <th key={h} className="px-4 py-3 text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {runs.map(run => (
                <tr key={run.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-4 py-3 font-mono text-slate-500">#{run.id}</td>
                  <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{run.run_at?.slice(0, 16) ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold border ${SIG[run.signal] ?? 'text-slate-400 border-slate-600'}`}>{run.signal}</span>
                  </td>
                  <td className="px-4 py-3">{(run.confidence * 100).toFixed(0)}%</td>
                  <td className="px-4 py-3 font-mono text-slate-300">{run.gold_price_thb ? `฿${run.gold_price_thb}` : (run.gold_price ?? '—')}</td>
                  <td className="px-4 py-3 text-slate-500">{run.provider ?? '—'}</td>
                  <td className="px-4 py-3">
                    <button onClick={() => { setRunIdInput(String(run.id)); }} className="p-1.5 hover:bg-slate-700 rounded-lg text-blue-400 transition-colors">
                      <Search size={14} />
                    </button>
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">No runs found.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Run Detail Section */}
      <div className="glass rounded-xl p-5 border-slate-700/50 space-y-4">
        <h3 className="text-sm font-bold text-slate-300">🔎 Load Run Detail</h3>
        <div className="flex gap-3">
          <input
            value={runIdInput} onChange={e => setRunIdInput(e.target.value)}
            placeholder="#42"
            className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-4 py-2 text-sm w-32 focus:outline-none focus:border-blue-500"
          />
          <button onClick={loadDetail} disabled={detailLoading} className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors">
            {detailLoading ? '...' : 'Load'}
          </button>
        </div>

        {detail && (
          <div className="space-y-4">
            <RunDetail run={detail} />
            <div>
              <h4 className="text-sm font-semibold text-slate-300 mb-2">🪵 LLM Call Logs</h4>
              <LlmLogsPanel logs={llmLogs.logs ?? []} trace={llmLogs.trace ?? detail.trace ?? []} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
