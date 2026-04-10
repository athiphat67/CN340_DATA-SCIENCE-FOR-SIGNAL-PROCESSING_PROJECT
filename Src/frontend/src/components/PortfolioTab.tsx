import { useState, useEffect } from 'react';
import { Briefcase, Save, DollarSign } from 'lucide-react';
import api from '../api';

export default function PortfolioTab() {
  const [data, setData] = useState({
    cash: 1500,
    gold: 0,
    cost: 0,
    cur_val: 0,
    pnl: 0,
    trades: 0,
  });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchPortfolio();
  }, []);

  const fetchPortfolio = async () => {
    setLoading(true);
    try {
      const res = await api.get('/portfolio');
      setData({
        cash: res.data.cash_balance,
        gold: res.data.gold_grams,
        cost: res.data.cost_basis_thb,
        cur_val: res.data.current_value_thb,
        pnl: res.data.unrealized_pnl,
        trades: res.data.trades_today,
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const savePortfolio = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post('/portfolio', data);
      alert('Portfolio saved successfully!');
      fetchPortfolio();
    } catch (err) {
       alert('Failed to save portfolio.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* View Portfolio */}
      <div className="space-y-6">
        <div className="glass p-6 rounded-2xl border-slate-700/50 bg-gradient-to-br from-slate-900 to-slate-800">
          <div className="flex items-center gap-3 mb-6">
            <Briefcase className="w-6 h-6 text-amber-400" />
            <h3 className="text-xl font-bold">Aom NOW Portfolio</h3>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800">
              <p className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Cash Balance</p>
              <p className="text-2xl font-mono text-emerald-400">฿{data.cash.toLocaleString()}</p>
            </div>
            <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800">
              <p className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Gold Holdings</p>
              <p className="text-2xl font-mono text-amber-400">{data.gold.toFixed(4)} <span className="text-sm">g</span></p>
            </div>
            <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800">
              <p className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Unrealized PNL</p>
              <p className={`text-2xl font-mono ${data.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {data.pnl > 0 ? '+' : ''}{data.pnl.toLocaleString()}
              </p>
            </div>
            <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800">
              <p className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Total Equity</p>
              <p className="text-2xl font-mono text-blue-400">฿{(data.cash + data.cur_val).toLocaleString()}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Edit Form */}
      <div className="glass rounded-2xl p-6 border-slate-700/50">
        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-slate-400" /> 
          Update Portfolio State
        </h3>
        <form onSubmit={savePortfolio} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Cash (THB)</label>
              <input type="number" step="0.01" value={data.cash} onChange={e => setData({...data, cash: parseFloat(e.target.value)})} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Gold (Grams)</label>
              <input type="number" step="0.0001" value={data.gold} onChange={e => setData({...data, gold: parseFloat(e.target.value)})} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Cost Basis (THB)</label>
              <input type="number" step="0.01" value={data.cost} onChange={e => setData({...data, cost: parseFloat(e.target.value)})} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1.5">Current Value (THB)</label>
              <input type="number" step="0.01" value={data.cur_val} onChange={e => setData({...data, cur_val: parseFloat(e.target.value)})} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all font-mono" />
            </div>
          </div>
          
          <button type="submit" disabled={saving} className="w-full mt-6 flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition-colors disabled:opacity-50">
            <Save size={18} />
            {saving ? 'Saving...' : 'Save Portfolio State'}
          </button>
        </form>
      </div>
    </div>
  );
}
