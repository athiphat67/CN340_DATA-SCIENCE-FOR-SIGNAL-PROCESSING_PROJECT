"""
main2.py — Entry point for goldtrader agent (v3.4)
เหมือน main.py ทุกอย่าง + รองรับ OpenRouter และ multi-model testing

Usage (run from Src/):
    # providers เดิม — ใช้ได้เหมือนเดิมทุกอย่าง
    python main2.py --provider gemini-3.1-flash-lite-preview
    python main2.py --provider groq
    python main2.py --provider mock

    # OpenRouter — ใช้ default model (gemini-2.0-flash)
    python main2.py --provider openrouter

    # OpenRouter + shortcut
    python main2.py --provider openrouter:claude-haiku
    python main2.py --provider openrouter:gpt-5-mini
    python main2.py --provider openrouter:llama-70b
    python main2.py --provider openrouter:grok-mini
    python main2.py --provider openrouter:mistral-small

    # OpenRouter + full model name
    python main2.py --provider openrouter:anthropic/claude-haiku-4-5
    python main2.py --provider openrouter:google/gemini-2.5-flash

    # ดู shortcuts ทั้งหมด
    python main2.py --list-models

    # options เดิม — ใช้ได้ทุกตัว
    python main2.py --provider openrouter:claude-haiku --intervals 1h 4h 1d
    python main2.py --provider openrouter:llama-70b --period 1mo --skip-fetch
    python main2.py --provider openrouter:grok-mini --no-save
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
from agent_core.llm.client import OpenRouterClient
from data_engine.orchestrator import GoldTradingOrchestrator
from database.database import RunDatabase
from ui.core.services import init_services


# ─────────────────────────────────────────────────────────────
# Print helpers  (เหมือน main.py ทุกอย่าง)
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

    voting = result["voting_result"]
    ivr    = result["data"]["interval_results"]

    print_voting(voting)
    print_interval_details(ivr)

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
# Provider helpers  (ส่วนที่เพิ่มใหม่)
# ─────────────────────────────────────────────────────────────

def _resolve_provider_label(provider_str: str) -> str:
    """
    แปลง provider string → label สำหรับ print
    "openrouter:claude-haiku" → "openrouter [anthropic/claude-haiku-4-5]"
    """
    if provider_str.startswith("openrouter:"):
        _, model_part = provider_str.split(":", 1)
        full = OpenRouterClient.resolve_model(model_part)
        return f"openrouter [{full}]"
    if provider_str == "openrouter":
        return f"openrouter [{OpenRouterClient.DEFAULT_MODEL}]"
    return provider_str


# ─────────────────────────────────────────────────────────────
# Arg parser
# ─────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="goldtrader v3.4 — ReAct LLM trading agent",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        default="gemini-3.1-flash-lite-preview",
        metavar="PROVIDER",
        help=(
            "LLM provider (default: gemini-3.1-flash-lite-preview)\n"
            "\n"
            "Direct providers:\n"
            "  gemini | openai | claude | groq | deepseek | ollama | mock\n"
            "\n"
            "OpenRouter (ต้องมี OPENROUTER_API_KEY ใน .env):\n"
            "  openrouter                  — ใช้ default model\n"
            "  openrouter:<shortcut>       — ใช้ shortcut\n"
            "  openrouter:<full/model-id>  — ระบุ full model name\n"
            "\n"
            "OpenRouter shortcuts:\n"
            "  gpt-5o-mini      → openai/gpt-5o-mini\n"
            "  claude-haiku-3-5 → anthropic/claude-3-5-haiku-20241022\n"
            "  nemotron-super   → nvidia/llama-3.1-nemotron-ultra-253b-v1:free\n"
            "  claude-haiku     → anthropic/claude-haiku-4-5\n"
            "  gpt-5-mini       → openai/gpt-5-mini\n"
            "  llama-70b        → meta-llama/llama-3.3-70b-instruct\n"
            "  grok-mini        → x-ai/grok-3-mini\n"
            "  mistral-small    → mistralai/mistral-small-3.2-24b-instruct-2506\n"
            "\n"
            "Examples:\n"
            "  --provider gemini-3.1-flash-lite-preview\n"
            "  --provider openrouter\n"
            "  --provider openrouter:claude-haiku\n"
            "  --provider openrouter:llama-70b\n"
            "  --provider openrouter:anthropic/claude-haiku-4-5\n"
        ),
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="แสดง OpenRouter model shortcuts ทั้งหมด แล้วออก",
    )
    parser.add_argument("--period",     default="3d",
                        help="Data period: 1d 3d 5d 7d 14d 1mo 2mo 3mo")
    parser.add_argument("--intervals",  nargs="+", default=["1h"],
                        help="Candle intervals: 1m 5m 15m 30m 1h 4h 1d 1w")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip fetching new market data (ใช้ข้อมูลเดิม)")
    parser.add_argument("--no-save",    action="store_true",
                        help="Do not save result to database")
    parser.add_argument("--output",     default="Output/result_output.json",
                        help="Path to save JSON result")
    return parser


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    interval_seconds = 600  # ตั้งค่า 10 นาที (600 วินาที), = 0 ปิด auto run

    # parse args ครั้งเดียวนอก loop — ไม่ re-parse ทุก cycle
    parser = _build_parser()
    args   = parser.parse_args()

    # --list-models: แสดงรายการแล้วออกเลย ไม่ต้อง loop
    if args.list_models:
        OpenRouterClient.list_models()
        return
    
    model_list = [
        "openrouter:gpt-5o-mini",
        "openrouter:claude-haiku-3-5",
        "openrouter:nemotron-super",
        "openrouter:claude-haiku",
        "openrouter:gpt-5-mini",
        "openrouter:llama-70b",
        "openrouter:grok-mini",
        "openrouter:mistral-small",
        args.provider  # ตัว Default หรือตัวที่รับมาจาก Command line
    ]

    while True:
        try:
            print(f"\n🚀 Starting cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            parser = argparse.ArgumentParser(description="goldtrader v3.3 — ReAct LLM trading agent")
            parser.add_argument("--provider",   default="gemini-3.1-flash-lite-preview",
                                help="LLM provider: gemini | groq | mock | openrouter_llama_70b ...")
            parser.add_argument("--period",     default="5d",
                                help="Data period: 1d 3d 5d 7d 14d 1mo 2mo 3mo")
            parser.add_argument("--intervals",  nargs="+", default=["30m"],
                                help="Candle intervals (space-separated): 1m 5m 15m 30m 1h 4h 1d 1w")
            parser.add_argument("--skip-fetch", action="store_true",
                                help="Skip fetching new market data (ใช้ข้อมูลเดิม)")
            parser.add_argument("--no-save",    action="store_true",
                                help="Do not save result to database")
            parser.add_argument("--output",     default="Output/result_output.json",
                                help="Path to save JSON result")
            parser.add_argument(
                "--bypass-session-gate",
                action="store_true",
                help="Skip session gate even inside trading session (e.g. testing)",
            )
            args = parser.parse_args()

            # ── 1. Registry setup ──────────────────────────────────────
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

            provider_label = _resolve_provider_label(args.provider)
            print(f"\n[goldtrader] provider={provider_label}  period={args.period}  "
                  f"intervals={args.intervals}  skip_fetch={args.skip_fetch}  "
                  f"save_db={not args.no_save}")

            # ── 4. Optional: skip fetch ────────────────────────────────
            if args.skip_fetch:
                print("[goldtrader] Skipping data fetch — using existing data.\n")

            # ── 5. Run analysis ────────────────────────────────────────
            # ส่ง provider string ตรงๆ ให้ AnalysisService/Factory จัดการ
            # รองรับทั้ง "gemini", "openrouter", "openrouter:claude-haiku"
            print("[goldtrader] Running analysis...\n")
            result = analysis.run_analysis(
                provider  = args.provider,
                period    = args.period,
                intervals = args.intervals,
                bypass_session_gate=args.bypass_session_gate,
            )

            # ── 6. Print result ────────────────────────────────────────
            print_result(result)

            # ── 6.5 ส่ง Trade Log สู่ API ─────────────────────────────
            if result["status"] == "success":
                action = result["voting_result"]["final_signal"]

                ivr     = result["data"]["interval_results"]
                best_iv = max(ivr.items(), key=lambda x: x[1]["confidence"])[0]
                best_result = ivr[best_iv]

                price       = best_result.get("entry_price") or "MARKET"
                reason      = best_result.get("rationale") or f"Auto-generated signal based on {action} decision"
                confidence  = result["voting_result"]["weighted_confidence"]
                stop_loss   = best_result.get("stop_loss",   0.0)
                take_profit = best_result.get("take_profit", 0.0)

                TEAM_API_KEY = os.getenv("TEAM_API_KEY")
                if not TEAM_API_KEY:
                    print("\n❌ [ERROR] ไม่พบ TEAM_API_KEY กรุณาตรวจสอบไฟล์ .env ของคุณ")
                else:
                    print("\n[goldtrader] Sending customized Trade Log to API...")
                    send_trade_log(
                        action      = action,
                        price       = price,
                        reason      = reason,
                        api_key     = TEAM_API_KEY,
                        confidence  = confidence,
                        stop_loss   = stop_loss,
                        take_profit = take_profit,
                    )

            # ── 7. Save JSON output ────────────────────────────────────
            # if args.output and result["status"] == "success":
            #     out_path = os.path.abspath(args.output)
            #     os.makedirs(os.path.dirname(out_path), exist_ok=True)
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

            if interval_seconds == 0:
                break

            print(f"\n😴 Sleeping for {interval_seconds // 60} minutes...")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\n👋 Stopped by user")
            break
        except Exception as e:
            print(f"❌ Error in loop: {e}")
            time.sleep(60)  # พัก 1 นาทีแล้วลองใหม่ถ้า error


if __name__ == "__main__":
    main()
    
    
# ------------------- How to Run -------------------------
   
# python main.py --provider openrouter:claude-haiku-4-5
# python main.py --provider openrouter:claude-haiku-3-5
# python main.py --provider openrouter:claude-sonnet-4-6
# python main.py --provider openrouter:gpt-5-mini
# python main.py --provider openrouter:gpt-5o-mini
# python main.py --provider openrouter:gpt-4o-mini
# python main.py --provider openrouter:llama-70b
# python main.py --provider openrouter:grok-mini
# python main.py --provider openrouter:nemotron-super
# python main.py --provider openrouter:gemini-3.1-flash-lite-preview
# python main.py --provider openrouter:gemini-2.5-flash-lite
# python main.py --provider openrouter:gemini-2.0-flash-lite
# python main.py (gemini 3.1 flash lite preview)

# ดูรายการ
# python main.py --list-models