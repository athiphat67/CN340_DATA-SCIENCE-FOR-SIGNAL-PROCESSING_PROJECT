"""
main.py — Entry point for goldtrader agent (v3.3)
ใช้ AnalysisService เดียวกับ dashboard — ไม่มี logic ซ้ำ

Usage (run from Src/):
    python main.py --provider gemini
    python main.py --provider groq
    python main.py --provider mock
    python main.py --provider gemini --intervals 1h 4h 1d
    python main.py --provider gemini --period 1mo --skip-fetch
    python main.py --provider gemini --no-save   # ไม่บันทึก DB
"""

import json
import argparse
import os
import sys
import time
from logs.api_logger import send_trade_log
from dotenv import load_dotenv

load_dotenv()

# ── Path Setup ──────────────────────────────────────────────
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, "data_engine"))

from agent_core.core.prompt import SkillRegistry, RoleRegistry
from data_engine.orchestrator import GoldTradingOrchestrator
from database.database import RunDatabase
from ui.core.services import init_services


# ─────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────

def _sep(char="=", n=62): print(char * n)

def print_voting(voting_result: dict) -> None:
    _sep()
    breakdown = voting_result.get("voting_breakdown", {})
    for sig in ["BUY", "SELL", "HOLD"]:
        v = breakdown.get(sig, {})
        if v.get("count", 0) == 0:
            continue
        icon = {"BUY": "🟢", "SELL": "🔴"}.get(sig, "🟡")
        ivs  = ", ".join(v.get("intervals", []))
        print(f"  {icon} {sig:4s}  votes:{v['count']}  "
              f"avg_conf:{v['avg_conf']:.0%}  "
              f"w_score:{v['weighted_score']:.0%}  [{ivs}]")
    _sep("-")
    icon = {"BUY": "🟢", "SELL": "🔴"}.get(voting_result["final_signal"], "🟡")
    print(f"  {icon} FINAL : {voting_result['final_signal']}  "
          f"({voting_result['weighted_confidence']:.0%} confidence)")
    _sep()


def print_interval_details(interval_results: dict) -> None:
    print("\n  Per-Interval Breakdown:")
    for iv, ir in interval_results.items():
        icon = {"BUY": "🟢", "SELL": "🔴"}.get(ir["signal"], "🟡")
        fb   = f"  ⚠ fallback←{ir['fallback_from']}" if ir.get("is_fallback") else ""
        print(f"    {iv:5s}  {icon} {ir['signal']:4s}  "
              f"conf:{ir['confidence']:.0%}  "
              f"via:{ir.get('provider_used','?')}{fb}")


def print_result(result: dict) -> None:
    if result["status"] == "error":
        _sep()
        print(f"  ❌ FAILED: {result['error']}")
        _sep()
        return
    
    # print('--------------------------------------------')
    # print(result)
    # print('--------------------------------------------')

    voting = result["voting_result"]
    ivr    = result["data"]["interval_results"]

    print_voting(voting)
    print_interval_details(ivr)

    # Best interval detail
    best_iv = max(ivr.items(), key=lambda x: x[1]["confidence"])[0]
    best    = ivr[best_iv]
    print(f"\n  Best Interval  : {best_iv}")
    print(f"  Entry Price    : {best.get('entry_price', 'N/A')}")
    print(f"  Stop Loss      : {best.get('stop_loss',  'N/A')}")
    print(f"  Take Profit    : {best.get('take_profit','N/A')}")
    print(f"  Rationale      : {(best.get('rationale') or '')[:200]}")

    run_id = result.get("run_id")
    if run_id:
        print(f"\n  ✅ Saved to DB  : run_id={run_id}")
    else:
        print("\n  ℹ  DB save skipped (--no-save)")

    market_open = result.get("market_open", True)
    if not market_open:
        print("\n  ⚠  ตลาดทองไทยปิดอยู่ (weekend/holiday) — ราคาอาจล่าช้า")

    attempt = result.get("attempt", 1)
    if attempt > 1:
        print(f"\n  ⚠  Used attempt {attempt} (retried {attempt-1} time(s))")
    _sep()


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    interval_seconds = 600  # ตั้งค่า 10 นาที (600 วินาที), = 0 ปิด auto run

    while True :
        try:
            print(f"\n🚀 Starting cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            parser = argparse.ArgumentParser(description="goldtrader v3.3 — ReAct LLM trading agent")
            parser.add_argument("--provider",   default="gemini",
                                help="LLM provider: gemini | groq | mock | openrouter_llama_70b ...")
            parser.add_argument("--period",     default="1d",
                                help="Data period: 1d 3d 5d 7d 14d 1mo 2mo 3mo")
            parser.add_argument("--intervals",  nargs="+", default=["1h"],
                                help="Candle intervals (space-separated): 1m 5m 15m 30m 1h 4h 1d 1w")
            parser.add_argument("--skip-fetch", action="store_true",
                                help="Skip fetching new market data (ใช้ข้อมูลเดิม)")
            parser.add_argument("--no-save",    action="store_true",
                                help="Do not save result to database")
            parser.add_argument("--output",     default="Output/result_output.json",
                                help="Path to save JSON result")
            args = parser.parse_args()

            # ── 1. Registry setup ──────────────────────────────────────
            from agent_core.core.prompt import SkillRegistry, RoleRegistry

            skill_registry = SkillRegistry()
            skill_registry.load_from_json(
                os.path.join(current_dir, "agent_core", "config", "skills.json")
            )
            role_registry = RoleRegistry(skill_registry)
            role_registry.load_from_json(
                os.path.join(current_dir, "agent_core", "config", "roles.json")
            )

            # ── 2. Orchestrator + DB ───────────────────────────────────
            orchestrator = GoldTradingOrchestrator()
            db           = None if args.no_save else RunDatabase()

            # ── 3. Services (shared with dashboard) ───────────────────
            services = init_services(skill_registry, role_registry, orchestrator, db)
            analysis = services["analysis"]

            print(f"\n[goldtrader] provider={args.provider}  period={args.period}  "
                f"intervals={args.intervals}  skip_fetch={args.skip_fetch}  "
                f"save_db={not args.no_save}")

            # ── 4. Optional: skip fetch (re-use cached latest.json) ───
            if args.skip_fetch:
                print("[goldtrader] Skipping data fetch — using existing data.\n")
                # AnalysisService.run_analysis จะ fetch เองใน orchestrator.run()
                # ถ้าอยากข้ามจริงๆ ให้ mock orchestrator ตรงนี้แทน
                # แต่ปกติ GoldTradingOrchestrator.run() มี cache ภายในอยู่แล้ว

            # ── 5. Run analysis via AnalysisService ───────────────────
            print("[goldtrader] Running analysis...\n")
            result = analysis.run_analysis(
                provider  = args.provider,
                period    = args.period,
                intervals = args.intervals,
            )

            # ── 6. Print result ────────────────────────────────────────
            print_result(result)
            
            # ── 6.5 ส่ง Trade Log สู่ API ──────────────────────────────
            if result["status"] == "success":
                # 1. ดึงข้อมูลที่จำเป็นจากผลลัพธ์ของ Agent
                action = result["voting_result"]["final_signal"]
                
                ivr = result["data"]["interval_results"]
                best_iv = max(ivr.items(), key=lambda x: x[1]["confidence"])[0]
                best_result = ivr[best_iv]
                
                # 2. จัดเตรียมเฉพาะฟิลด์ที่ต้องการส่ง
                price = best_result.get("entry_price") or "MARKET"
                reason = best_result.get("rationale") or f"Auto-generated signal based on {action} decision"
                confidence = result["voting_result"]["weighted_confidence"]
                stop_loss = best_result.get("stop_loss", 0.0)
                take_profit = best_result.get("take_profit", 0.0)

                # 3. ดึง API Key จากไฟล์ .env
                TEAM_API_KEY = os.getenv("TEAM_API_KEY")
                
                # ป้องกันกรณีลืมตั้งค่า API Key ใน .env
                if not TEAM_API_KEY:
                    print("\n❌ [ERROR] ไม่พบ TEAM_API_KEY กรุณาตรวจสอบไฟล์ .env ของคุณ")
                else:
                    # 4. เรียกใช้ฟังก์ชันโดยระบุเฉพาะฟิลด์เสริมที่ต้องการ
                    print("\n[goldtrader] Sending customized Trade Log to API...")
                    send_trade_log(
                        action=action, 
                        price=price, 
                        reason=reason, 
                        api_key=TEAM_API_KEY, 
                        confidence=confidence, 
                        stop_loss=stop_loss, 
                        take_profit=take_profit
                    )

            # ── 7. Save JSON output ────────────────────────────────────
            # if args.output and result["status"] == "success":
            #     out_path = os.path.abspath(args.output)
            #     os.makedirs(os.path.dirname(out_path), exist_ok=True)

            #     # Serialize (ตัด non-serializable fields ออก)
            #     safe = {
            #         "status":           result["status"],
            #         "final_signal":     result["voting_result"]["final_signal"],
            #         "confidence":       result["voting_result"]["weighted_confidence"],
            #         "voting_breakdown": result["voting_result"]["voting_breakdown"],
            #         "interval_details": result["voting_result"]["interval_details"],
            #         "run_id":           result.get("run_id"),
            #         "attempt":          result.get("attempt"),
            #         "market_open":      result.get("market_open"),
            #     }
            #     with open(out_path, "w", encoding="utf-8") as f:
            #         json.dump(safe, f, ensure_ascii=False, indent=2)
            #     print(f"\n✅ Saved JSON result → {out_path}")
            
            print(f"\n😴 Sleeping for {interval_seconds//60} minutes...")
            time.sleep(interval_seconds)
            
        except KeyboardInterrupt:
            print("\n👋 Stopped by user")
            break
        except Exception as e:
            print(f"❌ Error in loop: {e}")
            time.sleep(60) # พัก 1 นาทีแล้วลองใหม่ถ้า error
        
        
        

if __name__ == "__main__":
    main()