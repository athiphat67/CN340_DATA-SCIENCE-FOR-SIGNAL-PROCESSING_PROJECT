import { useState, useEffect } from 'react';
import { RefreshCw, AlertCircle } from 'lucide-react';
import api from '../api';

interface Interval { label: string; tv: string; }
const TV_MAP: Record<string, string> = {
  '1m': '1', '5m': '5', '15m': '15', '30m': '30',
  '1h': '60', '4h': '240', '1d': 'D', '1w': 'W',
};

function TradingViewWidget({ interval }: { interval: string }) {
  const tv = TV_MAP[interval] ?? '60';
  const html = `
    <div class="tradingview-widget-container" style="height:100%;min-height:400px;">
      <iframe
        src="https://s.tradingview.com/widgetembed/?symbol=OANDA%3AXAUUSD&interval=${tv}&theme=dark&style=1&locale=en&toolbar_bg=%23131722&hide_top_toolbar=0&hide_legend=0&saveimage=0&studies=RSI%40tv-basicstudies%2BMACD%40tv-basicstudies"
        style="width:100%;height:420px;border:none;"
        allowtransparency="true"
        scrolling="no"
        allowfullscreen=""
      ></iframe>
    </div>`;
  return <div dangerouslySetInnerHTML={{ __html: html }} />;
}

function PriceCard({ data }: { data: any }) {
  if (!data || data.status !== 'success') return (
    <div className="text-slate-500 text-sm">{data?.error ?? 'Loading...'}</div>
  );
  const up = data.change_pct >= 0;
  return (
    <div className="space-y-3">
      <div className="flex justify-between text-sm text-slate-500">
        <span>XAU/THB /gram</span>
        <span>{data.fetched_at}</span>
      </div>
      <p className="text-3xl font-black text-white">฿{data.price?.toLocaleString()}</p>
      <p className={`text-lg font-bold ${up ? 'text-emerald-400' : 'text-rose-400'}`}>
        {up ? '▲' : '▼'} {Math.abs(data.change_pct).toFixed(2)}%
      </p>
      <div className="grid grid-cols-2 gap-2 text-xs mt-3">
        {[
          ['Open',  data.open_price],
          ['High',  data.high_price],
          ['Low',   data.low_price],
          ['Prev',  data.prev_close],
        ].map(([label, val]) => (
          <div key={label as string} className="bg-slate-900/50 rounded-lg p-2 border border-slate-800">
            <p className="text-slate-500">{label}</p>
            <p className="text-slate-200 font-semibold">฿{(val as number)?.toLocaleString()}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ProvidersTable({ providers }: { providers: any[] }) {
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-slate-500 uppercase border-b border-slate-700/40">
          <th className="pb-2 text-left">Provider</th>
          <th className="pb-2 text-left">Rate</th>
          <th className="pb-2 text-left">Key</th>
        </tr>
      </thead>
      <tbody>
        {providers.map((p, i) => (
          <tr key={i} className="border-b border-slate-800/40">
            <td className="py-2 text-slate-300">{p.name}</td>
            <td className="py-2 text-slate-500">{p.rate_limit}</td>
            <td className="py-2">
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${p.api_key_set ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                {p.api_key_set ? '✓ SET' : '✗ MISSING'}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ChartTab({ config }: { config: any }) {
  const [interval, setInterval] = useState('1h');
  const [priceData, setPriceData] = useState<any>(null);
  const [providers, setProviders] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchPrice = async () => {
    setLoading(true);
    try {
      const [pr, prov] = await Promise.all([
        api.get('/chart/price'),
        api.get('/chart/providers'),
      ]);
      setPriceData(pr.data);
      setProviders(prov.data.providers ?? []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPrice();
    const t = setInterval(fetchPrice, 60_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={interval}
          onChange={e => setInterval(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        >
          {(config?.intervals ?? Object.keys(TV_MAP)).map((iv: string) => (
            <option key={iv} value={iv}>⏱ {iv}</option>
          ))}
        </select>
        <button
          onClick={fetchPrice}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh Live Price
        </button>
      </div>

      {/* Chart + info */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 glass rounded-2xl p-4 border-slate-700/50 overflow-hidden">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">📈 Live Gold Chart — XAU/USD</h3>
          <TradingViewWidget interval={interval} />
        </div>
        <div className="space-y-4">
          <div className="glass rounded-2xl p-5 border-slate-700/50">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">💰 Gold Price</h3>
            <PriceCard data={priceData} />
          </div>
          <div className="glass rounded-2xl p-5 border-slate-700/50">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">🏦 LLM Providers</h3>
            {providers.length > 0 ? <ProvidersTable providers={providers} /> : <p className="text-slate-500 text-sm">Loading...</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
