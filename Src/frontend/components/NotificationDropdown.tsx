import React, { useState, useRef, useEffect } from 'react';
import { Bell, Target, TrendingUp, AlertTriangle, CheckCircle2 } from 'lucide-react';

export const NotificationDropdown = () => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 🔔 ข้อมูลจำลอง (Mockup Notifications) 
  // ในอนาคตสามารถดึงจาก API หรือ Database มาใส่แทนได้
  const notifications = [
    { id: 1, title: 'Take Profit Hit', desc: 'XAU/THB SELL order closed at 41,450 ฿', time: '2m ago', type: 'success', icon: Target, isRead: false },
    { id: 2, title: 'New Signal Generated', desc: 'Strong Bullish MACD crossover detected.', time: '1h ago', type: 'info', icon: TrendingUp, isRead: false },
    { id: 3, title: 'High Volatility', desc: 'US CPI data released. Expect rapid price action.', time: '3h ago', type: 'warning', icon: AlertTriangle, isRead: true },
    { id: 4, title: 'System Update', desc: 'Agent infrastructure synchronized.', time: '1d ago', type: 'system', icon: CheckCircle2, isRead: true },
  ];

  // 🖱️ ฟังก์ชันสำหรับปิด Pop-up เมื่อคลิกพื้นที่อื่นบนหน้าจอ (Click Outside)
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // นับจำนวนรายการที่ยังไม่ได้อ่าน
  const unreadCount = notifications.filter(n => !n.isRead).length;

  return (
    <div className="relative" ref={dropdownRef}>
      
      {/* --- ปุ่มกระดิ่งแจ้งเตือน --- */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2.5 rounded-2xl bg-white/5 border border-white/10 text-gray-400 hover:text-white hover:bg-white/10 transition-all focus:outline-none focus:ring-2 focus:ring-[#824199]/50"
      >
        <Bell size={20} strokeWidth={2} />
        {/* จุดสีเหลืองแจ้งเตือน (โชว์เมื่อมี Unread) */}
        {unreadCount > 0 && (
          <span className="absolute top-2.5 right-2.5 w-2.5 h-2.5 bg-[#FFD700] rounded-full border-2 border-[#1a0a24] shadow-[0_0_10px_rgba(255,215,0,0.6)]" />
        )}
      </button>

      {/* --- กล่อง Pop-up Dropdown --- */}
      {isOpen && (
        <div className="absolute right-0 mt-4 w-80 sm:w-[380px] bg-[#1a0a24]/95 backdrop-blur-2xl rounded-[24px] border border-white/10 shadow-[0_20px_60px_rgba(0,0,0,0.6)] overflow-hidden z-[100] animate-in fade-in slide-in-from-top-4 duration-200 origin-top-right">
          
          {/* Header ของ Dropdown */}
          <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-white/5 to-transparent">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              Notifications
              {unreadCount > 0 && (
                <span className="bg-[#824199] text-white text-[10px] px-2 py-0.5 rounded-full shadow-sm">
                  {unreadCount} New
                </span>
              )}
            </h3>
            <button className="text-[10px] font-bold text-gray-400 hover:text-white uppercase tracking-widest transition-colors">
              Mark all read
            </button>
          </div>

          {/* รายการแจ้งเตือน */}
          <div className="max-h-[360px] overflow-y-auto custom-scrollbar">
            {notifications.length > 0 ? (
              notifications.map((notif) => (
                <div 
                  key={notif.id} 
                  className={`p-4 border-b border-white/5 flex gap-4 hover:bg-white/5 transition-colors cursor-pointer ${notif.isRead ? 'opacity-60' : 'bg-white/[0.03]'}`}
                >
                  <div className={`w-10 h-10 rounded-2xl flex items-center justify-center shrink-0 border ${
                    notif.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                    notif.type === 'warning' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                    notif.type === 'info' ? 'bg-[#824199]/20 text-[#c084fc] border-[#824199]/30' :
                    'bg-gray-500/10 text-gray-400 border-gray-500/20'
                  }`}>
                    <notif.icon size={18} />
                  </div>
                  <div className="flex-1">
                    <div className="flex justify-between items-start mb-1">
                      <p className={`text-sm font-bold ${notif.isRead ? 'text-gray-300' : 'text-white'}`}>{notif.title}</p>
                      {/* จุดบอกสถานะว่ายังไม่อ่าน */}
                      {!notif.isRead && <span className="w-2 h-2 bg-[#FFD700] rounded-full mt-1.5 shadow-[0_0_8px_rgba(255,215,0,0.5)]" />}
                    </div>
                    <p className="text-xs text-gray-400 leading-relaxed">{notif.desc}</p>
                    <p className="text-[10px] text-gray-500 font-medium mt-2 tracking-widest uppercase">{notif.time}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="p-8 text-center text-gray-500">
                <Bell size={24} className="mx-auto mb-2 opacity-50" />
                <p className="text-sm">No new notifications</p>
              </div>
            )}
          </div>

          {/* Footer ของ Dropdown */}
          <div className="p-3 border-t border-white/5 bg-black/20 text-center hover:bg-black/30 transition-colors cursor-pointer">
            <button className="text-xs font-bold text-[#c084fc] hover:text-white transition-colors uppercase tracking-widest w-full py-2">
              View All History
            </button>
          </div>
        </div>
      )}
    </div>
  );
};