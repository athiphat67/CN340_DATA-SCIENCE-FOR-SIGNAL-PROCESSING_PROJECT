"""
main.py — Entry point for goldtrader agent
Wires: LLMClient (A) + ReactOrchestrator (B) + PromptBuilder (C)

Usage:
    python main.py --input data/latest.json --mock
    python main.py --input data/latest.json --provider gemini
    python main.py --input data/latest.json --provider claude
"""

import json
import argparse

from llm.client import LLMClientFactory
from core.react import ReactOrchestrator, ReactConfig
from core.prompt import SkillRegistry, RoleRegistry, PromptBuilder, AIRole

# ─────────────────────────────────────────────
# Tool Registry (empty — data pre-loaded from latest.json)
# ─────────────────────────────────────────────
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
    print("\nFull output (JSON):")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="goldtrader — ReAct LLM trading agent")
    parser.add_argument("--input",    default="data/latest.json",  help="Path to latest.json")
    parser.add_argument("--provider", default="gemini",            help="LLM provider")
    parser.add_argument("--mock",     action="store_true",         help="Use MockClient (no API calls)")
    parser.add_argument("--iterations", type=int, default=5,       help="Max ReAct iterations")
    args = parser.parse_args()

    # ── A: LLM Client ───────────────────────────
    llm = LLMClientFactory.create(args.provider, use_mock=args.mock)
    print(f"[goldtrader] Provider: {'mock' if args.mock else args.provider}")

    # ── C: Prompt System ────────────────────────
    skill_registry = SkillRegistry()
    skill_registry.load_from_json("config/skills.json")

    role_registry = RoleRegistry(skill_registry)
    role_registry.load_from_json("config/roles.json")

    prompt_builder = PromptBuilder(role_registry, AIRole.ANALYST)

    # ── B: ReAct Orchestrator ───────────────────
    orchestrator = ReactOrchestrator(
        llm_client=llm,
        prompt_builder=prompt_builder,
        tool_registry=TOOL_REGISTRY,
        config=ReactConfig(
            max_iterations=args.iterations,
            max_tool_calls=0,       # data pre-loaded → no tools needed
        ),
    )

    # ── Run ─────────────────────────────────────
    market_state = load_market_state(args.input)
    print(f"[goldtrader] Loaded market state from: {args.input}")
    print(f"[goldtrader] Running ReAct loop (max {args.iterations} iterations)...\n")

    result = orchestrator.run(market_state)
    print_result(result)


if __name__ == "__main__":
    main()