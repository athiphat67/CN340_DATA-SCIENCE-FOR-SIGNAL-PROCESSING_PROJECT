import { useState, useEffect } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import api from '../api';

function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4 flex flex-col gap-1">
      <p className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">{label}</p>
      <p className="text-2xl font-black text-white">{value}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function SignalCard({ data }: { data: any }) {
  if (!data) return null;
  const { signal, confidence, provider, run_at } = data;
  const cfg: Record<string, { color: string; bg: string; icon: any }> = {
    BUY:  { color: 'text-emerald-400', bg: 'border-emerald-500/30 bg-emerald-500/5', icon: TrendingUp },
    SELL: { color: 'text-rose-400',    bg: 'border-rose-500/30 bg-rose-500/5',       icon: TrendingDown },
    HOLD: { color: 'text-amber-400',   bg: 'border-amber-500/30 bg-amber-500/5',     icon: Minus },
  };
  const c = cfg[signal] ?? cfg.HOLD;
  const Icon = c.icon;
  const bar = Math.round(confidence * 100);

  return (
    <div className={`rounded-2xl border p-6 ${c.bg}`}>
      <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-3">📊 Latest Signal</p>
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${c.color} bg-slate-800`}>
          <Icon size={22} />
        </div>
        <span className={`text-4xl font-black ${c.color}`}>{signal}</span>
      </div>
      <div className="mb-1 text-xs text-slate-500 uppercase tracking-wider">Confidence</div>
      <div className="h-1.5 bg-slate-700 rounded-full mb-1">
        <div className="h-1.5 rounded-full bg-current transition-all duration-700" style={{ width: `${bar}%`, color: c.color.replace('text-', '') }} />
      </div>
      <p className={`text-2xl font-black ${c.color}`}>{bar}%</p>
      <div className="flex gap-4 mt-4 pt-3 border-t border-slate-700/50 text-xs text-slate-500">
        <span>🤖 {provider}</span>
        <span>🕐 {run_at}</span>
      </div>
    </div>
  );
}

function GoldPriceCard({ data }: { data: any }) {
  if (!data || data.status !== 'success') {
    return (
      <div className="rounded-2xl border border-slate-700/50 bg-slate-800/40 p-6">
        <p className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">💰 Gold Price · XAU/THB</p>
        <p className="text-slate-400 text-sm">{data?.error ?? 'Fetching...'}</p>
      </div>
    );
  }
  const { price, change_pct, fetched_at } = data;
  const up = change_pct >= 0;
  return (
    <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-6">
      <p className="text-[10px] uppercase tracking-widest text-blue-400 mb-3">💰 Gold Price · XAU/THB</p>
      <p className="text-4xl font-black text-white">฿{price?.toLocaleString()}</p>
      <p className={`text-xl font-bold mt-1 ${up ? 'text-emerald-400' : 'text-rose-400'}`}>
        {up ? '▲' : '▼'} {Math.abs(change_pct).toFixed(2)}%
      </p>
      <p className="text-xs text-slate-500 mt-1">per gram · updated {fetched_at}</p>
    </div>
  );
}

function PortfolioCard({ data }: { data: any }) {
  if (!data) return null;
  const cash = parseFloat(data.cash_balance ?? 0);
  const gold = parseFloat(data.gold_grams ?? 0);
  const pnl  = parseFloat(data.unrealized_pnl ?? 0);
  const cur_val = parseFloat(data.current_value_thb ?? 0);
  const total = cash + cur_val;

  return (
    <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-6">
      <p className="text-[10px] uppercase tracking-widest text-violet-400 mb-3">💼 Portfolio Snapshot</p>
      <p className="text-3xl font-black text-white mb-1">฿{total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
      <p className="text-xs text-slate-500 mb-4">total equity</p>
      <div className="space-y-2 text-sm">
        {[
          { label: 'Cash',       val: `฿${cash.toLocaleString(undefined, {minimumFractionDigits: 2})}` },
          { label: 'Gold Held',  val: `${gold.toFixed(4)} g` },
          { label: 'Gold Value', val: `฿${cur_val.toLocaleString(undefined, {minimumFractionDigits: 2})}` },
          { label: 'PnL',        val: `${pnl >= 0 ? '▲' : '▼'} ฿${Math.abs(pnl).toLocaleString(undefined, {minimumFractionDigits: 2})}`,
            color: pnl >= 0 ? 'text-emerald-400' : 'text-rose-400' },
        ].map(row => (
          <div key={row.label} className="flex justify-between border-b border-slate-700/30 pb-2">
            <span className="text-slate-500">{row.label}</span>
            <span className={`font-semibold ${row.color ?? 'text-slate-200'}`}>{row.val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentRunsCard({ runs }: { runs: any[] }) {
  const SIG: Record<string, string> = { BUY: 'text-emerald-400', SELL: 'text-rose-400', HOLD: 'text-amber-400' };
  return (
    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-6">
      <p className="text-[10px] uppercase tracking-widest text-amber-400 mb-4">📜 Recent Runs</p>
      {runs.length === 0 ? (
        <p className="text-slate-500 text-sm">No runs yet.</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 uppercase border-b border-slate-700/40">
              <th className="pb-2 text-left">Signal</th>
              <th className="pb-2 text-left">Conf</th>
              <th className="pb-2 text-left">Provider</th>
              <th className="pb-2 text-right">Time</th>
            </tr>
          </thead>
          <tbody>
            {runs.slice(0, 7).map((r, i) => (
              <tr key={i} className="border-b border-slate-800/40 hover:bg-white/5 transition-colors">
                <td className={`py-2 font-bold ${SIG[r.signal] ?? 'text-slate-300'}`}>● {r.signal}</td>
                <td className="py-2 text-slate-400">{(parseFloat(r.confidence) * 100).toFixed(0)}%</td>
                <td className="py-2 text-slate-500">{(r.provider ?? '—').slice(0, 10)}</td>
                <td className="py-2 text-slate-600 text-right whitespace-nowrap">{r.run_at?.slice(0, 16) ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function HomeTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetch = async () => {
    setLoading(true);
    try {
      const res = await api.get('/home');
      setData(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
    const t = setInterval(fetch, 60_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-xl font-bold text-white">Gold Intelligence Platform</h2>
          <p className="text-slate-400 text-sm mt-0.5">Real-time AI Trading System · Auto-refreshes every 60s</p>
        </div>
        <button onClick={fetch} className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-slate-200 transition-colors text-sm">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Market status bar */}
      {data && (
        <div className={`flex items-center gap-3 px-4 py-2 rounded-xl border text-sm font-medium ${data.market_open ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'}`}>
          <span className={`w-2 h-2 rounded-full animate-pulse ${data.market_open ? 'bg-emerald-400' : 'bg-rose-400'}`} />
          {data.market_open ? 'ตลาดทองไทยเปิด (Market Open)' : 'ตลาดทองไทยปิด (Market Closed)'}
          <span className="ml-auto text-slate-500 text-xs">{new Date().toLocaleTimeString()}</span>
        </div>
      )}

      {/* KPI row */}
      {data?.kpi && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Total Runs"     value={String(data.kpi.total_runs)} />
          <KpiCard label="Win Rate (BUY)" value={`${(data.kpi.win_rate * 100).toFixed(0)}%`} />
          <KpiCard label="Avg Confidence" value={`${(data.kpi.avg_confidence * 100).toFixed(0)}%`} />
          <KpiCard label="Market"         value={data.kpi.market_status} />
        </div>
      )}

      {/* Signal (full width) */}
      {data?.latest_signal && <SignalCard data={data.latest_signal} />}

      {/* Price + Portfolio */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GoldPriceCard data={data?.gold_price} />
        <PortfolioCard data={data?.portfolio} />
      </div>

      {/* Recent runs */}
      {data?.recent_runs && <RecentRunsCard runs={data.recent_runs} />}
    </div>
  );
}
