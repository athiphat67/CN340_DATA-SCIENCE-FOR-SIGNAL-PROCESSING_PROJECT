import React from 'react';
import { ArrowUpRight, Brain, Target, ShieldX, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export const SignalMasterTable = ({ signals }: any) => {
  const navigate = useNavigate();

  return (
    <div className="bg-white rounded-[24px] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-gray-100 overflow-hidden font-sans">
      
      {/* Header - เพิ่มคอลัมน์ Confidence เข้ามา */}
      <div className="grid grid-cols-[1fr_0.5fr_0.8fr_3fr_1fr_1fr] bg-gray-50/80 text-[11px] font-bold text-gray-400 uppercase tracking-wider p-5 border-b border-gray-100">
        <span>Date & ID</span>
        <span className="text-center">TF</span>
        <span className="text-center">Action</span>
        <span className="pl-2">AI Analysis & Targets</span>
        <span className="text-center">Confidence</span>
        <span className="text-right">Action</span>
      </div>

      {/* Body */}
      <div className="divide-y divide-gray-50/80">
        {signals.map((sig: any) => (
          <div key={sig.id} className="grid grid-cols-[1fr_0.5fr_0.8fr_3fr_1fr_1fr] items-center p-5 hover:bg-gray-50/50 transition-colors group">
            
            {/* 1. Date & ID */}
            <div>
              <p className="text-[13px] font-bold text-gray-900 flex items-center gap-1.5 mb-1">
                 <Clock size={12} className="text-gray-400" /> {sig.date.split(' ')[0]}
              </p>
              <p className="text-[10px] text-gray-400 font-mono uppercase tracking-tighter">Trace: #{sig.id}</p>
            </div>
            
            {/* 2. TF */}
            <div className="flex justify-center">
              <span className="bg-white text-gray-500 text-[10px] font-bold px-2.5 py-1 rounded-md border border-gray-200 shadow-sm">{sig.tf}</span>
            </div>
            
            {/* 3. Action */}
            <div className="flex justify-center">
              <span className={`text-[11px] font-black px-3.5 py-1.5 rounded-full border tracking-wider shadow-sm ${
                sig.signal === 'BUY' ? 'bg-emerald-50 text-emerald-600 border-emerald-200' : 
                sig.signal === 'SELL' ? 'bg-rose-50 text-rose-600 border-rose-200' : 
                'bg-amber-50 text-amber-600 border-amber-200'
              }`}>
                {sig.signal}
              </span>
            </div>
            
            {/* 4. AI Rationale & Targets (ปรับใหม่ให้ดูเป็นกล่อง AI คิด) */}
            <div className="pl-2 pr-6 border-l border-gray-100">
              <div className="bg-gray-50/50 rounded-xl p-3 border border-gray-100/50 group-hover:bg-white group-hover:border-[#824199]/20 transition-colors">
                  <div className="flex items-start gap-2 mb-2">
                     <Brain size={14} className="text-[#824199] mt-0.5 shrink-0" />
                     <p className="text-xs text-gray-600 italic leading-relaxed line-clamp-2">"{sig.rationale}"</p>
                  </div>
                  <div className="flex items-center gap-4 text-[10px] font-bold ml-5">
                    <span className="text-gray-900 bg-white px-2 py-1 rounded-md border border-gray-200 shadow-sm">EP: {sig.entry}</span>
                    {sig.tp && <span className="flex items-center gap-1 text-emerald-600"><Target size={12}/> {sig.tp}</span>}
                    {sig.sl && <span className="flex items-center gap-1 text-rose-500"><ShieldX size={12}/> {sig.sl}</span>}
                  </div>
              </div>
            </div>

            {/* 5. Confidence Bar (ดึงกลับมาโชว์) */}
            <div className="flex justify-center items-center gap-2">
                <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden shadow-inner">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-[#824199] to-[#c084fc]"
                    style={{ width: `${sig.confidence || 80}%` }}
                  />
                </div>
                <span className="text-[11px] font-black text-gray-700">{sig.confidence || 80}%</span>
            </div>
            
            {/* 6. Action Button */}
            <div className="text-right flex items-center justify-end">
              <button 
                onClick={() => navigate(`/signals/${sig.id}`)}
                className="flex items-center gap-1.5 text-[11px] font-bold text-gray-500 hover:text-[#824199] bg-white hover:bg-[#824199]/10 px-4 py-2 rounded-xl transition-all active:scale-95 border border-gray-200 hover:border-[#824199]/20 shadow-sm"
              >
                View Trace <ArrowUpRight size={14} />
              </button>
            </div>

          </div>
        ))}
      </div>
    </div>
  );
};