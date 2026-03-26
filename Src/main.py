"""
main.py — Entry point for goldtrader agent
Wires: Data Engine (Orchestrator) + LLMClient + ReactOrchestrator + PromptBuilder

Usage (run from Src/):
    python main.py --provider gemini
    python main.py --provider groq
    python main.py --provider gemini --skip-fetch  # ใช้ข้อมูลเดิม ไม่ต้องดึงใหม่
"""

import json
import argparse
import os
import sys

# ── 1. Setup Path ───────────────────────────────────────────
# นำโฟลเดอร์ปัจจุบันและ data_engine เข้าไปใน system path 
# เพื่อให้ import หากันได้โดยไม่เกิด Error: ModuleNotFoundError
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, "data_engine"))

from agent_core.llm.client import LLMClientFactory
from agent_core.core.react import ReactOrchestrator, ReactConfig
from agent_core.core.prompt import SkillRegistry, RoleRegistry, PromptBuilder, AIRole

# Import Orchestrator จาก data_engine
from orchestrator import GoldTradingOrchestrator

TOOL_REGISTRY: dict = {}

def load_market_state(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def print_result(result: dict) -> None:
    fd = result["final_decision"]
    print("\n" + "=" * 60)
    print(f"  DECISION   : {fd['signal']}")
    print(f"  Confidence : {fd['confidence']:.2f}")
    print(f"  Entry      : {fd.get('entry_price', 'N/A')}")
    print(f"  Stop Loss  : {fd.get('stop_loss', 'N/A')}")
    print(f"  Take Profit: {fd.get('take_profit', 'N/A')}")
    print(f"  Rationale  : {fd.get('rationale', '')}")
    print("=" * 60)
    print(f"  Iterations : {result['iterations_used']}")
    print(f"  Tool calls : {result['tool_calls_used']}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="goldtrader — ReAct LLM trading agent")
    parser.add_argument("--provider",   default="gemini",      help="LLM provider (gemini, groq, mock)")
    parser.add_argument("--iterations", type=int, default=5,   help="Max ReAct iterations")
    parser.add_argument("--skip-fetch", action="store_true",   help="Skip fetching new market data")
    args = parser.parse_args()

    # ตั้งค่า Path ปลายทางของข้อมูล
    target_data_dir = os.path.join(current_dir, "agent_core", "data")
    target_input_file = os.path.join(target_data_dir, "latest.json")

    # ── 2. Data Engine (Fetch Data) ─────────────────────────
    if not args.skip_fetch:
        print(f"[goldtrader] Fetching latest market data...")
        orchestrator = GoldTradingOrchestrator(
            history_days=90,
            interval="1d",
            max_news_per_cat=5,
            output_dir=target_data_dir
        )
        # รันการดึงข้อมูลและเซฟลง agent_core/data/latest.json อัตโนมัติ
        orchestrator.run(save_to_file=True)
        print(f"[goldtrader] Data fetch complete.\n")
    else:
        print(f"[goldtrader] Skipping data fetch. Using existing data.\n")

    # ── 3. Agent Core (LLM Logic) ───────────────────────────
    use_mock = (args.provider.lower() == "mock")
    llm = LLMClientFactory.create(args.provider, use_mock=use_mock)
    print(f"[goldtrader] Provider: {'mock' if use_mock else args.provider}")

    skill_registry = SkillRegistry()
    skill_registry.load_from_json(os.path.join(current_dir, "agent_core", "config", "skills.json"))

    role_registry = RoleRegistry(skill_registry)
    role_registry.load_from_json(os.path.join(current_dir, "agent_core", "config", "roles.json"))

    prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)

    react_orchestrator = ReactOrchestrator(
        llm_client=llm,
        prompt_builder=prompt_builder,
        tool_registry=TOOL_REGISTRY,
        config=ReactConfig(
            max_iterations=args.iterations,
            max_tool_calls=0, # data pre-loaded → no tools needed
        ),
    )

    # โหลดไฟล์ล่าสุดมาใช้งาน
    market_state = load_market_state(target_input_file)
    print(f"[goldtrader] Loaded market state from: {target_input_file}")
    print(f"[goldtrader] Running ReAct loop (max {args.iterations} iterations)...\n")

    result = react_orchestrator.run(market_state)
    print_result(result)

if __name__ == "__main__":
    main()