#!/usr/bin/env python3
"""
ATLAST ECP Stress Test — Run All Agents
Runs 6 test agents sequentially, then triggers batch upload and verifies.
"""
import json
import os
import sys
import time

# Ensure SDK is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))
sys.path.insert(0, os.path.dirname(__file__))

from config import OPENROUTER_API_KEY, ECP_SERVER, LLACHAT_API

def check_prerequisites():
    if not OPENROUTER_API_KEY:
        print("❌ OPENROUTER_API_KEY not set")
        print("   export OPENROUTER_API_KEY='sk-or-...'")
        sys.exit(1)

    print("=" * 60)
    print("ATLAST ECP Stress Test Suite")
    print("=" * 60)
    print(f"  OpenRouter: {'✅ configured' if OPENROUTER_API_KEY else '❌ missing'}")
    print(f"  ECP Server: {ECP_SERVER}")
    print(f"  LLaChat:    {LLACHAT_API}")
    print()


def run_all():
    check_prerequisites()

    from agent_01_coding import run as run_coding
    from agent_02_research import run as run_research
    from agent_03_customer_service import run as run_cs
    from agent_04_crewai_team import run as run_crew
    from agent_05_autogen_debate import run as run_debate
    from agent_06_chaos import run as run_chaos

    agents = [
        ("Coding Agent", run_coding),
        ("Research Agent", run_research),
        ("Customer Service", run_cs),
        ("CrewAI Team", run_crew),
        ("AutoGen Debate", run_debate),
        ("Chaos Agent", run_chaos),
    ]

    all_results = []
    total_start = time.time()

    for name, runner in agents:
        print(f"\n{'='*60}")
        agent_start = time.time()
        try:
            result = runner()
            result["duration_s"] = round(time.time() - agent_start, 1)
            result["status"] = "✅"
            all_results.append(result)
        except Exception as e:
            print(f"   ❌ Agent failed: {e}")
            all_results.append({"agent": name, "status": "❌", "error": str(e)})

    # Final batch upload
    print(f"\n{'='*60}")
    print("📦 Triggering final batch upload...")
    try:
        from atlast_ecp.batch import run_batch
        batch_result = run_batch(flush=True)
        print(f"   Batch: {json.dumps(batch_result, indent=2)}")
    except Exception as e:
        print(f"   ⚠️ Batch upload: {e}")

    # Summary
    total_duration = round(time.time() - total_start, 1)
    total_calls = sum(r.get("calls", 0) for r in all_results)

    print(f"\n{'='*60}")
    print("📊 STRESS TEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Total duration: {total_duration}s")
    print(f"  Total LLM calls: {total_calls}")
    print(f"  Agents tested: {len(all_results)}")
    print()

    for r in all_results:
        calls = r.get("calls", "?")
        dur = r.get("duration_s", "?")
        status = r.get("status", "?")
        print(f"  {status} {r.get('agent', '?'):20s} | {calls:>4} calls | {dur}s")

    # Check ECP records on disk
    try:
        from pathlib import Path
        ecp_dir = Path.home() / ".ecp" / "records"
        if ecp_dir.exists():
            files = list(ecp_dir.glob("*.jsonl"))
            total_records = sum(1 for f in files for _ in open(f))
            print(f"\n  📁 Local ECP records: {total_records} across {len(files)} files")
    except Exception:
        pass

    print(f"\n{'='*60}")
    print("Next steps:")
    print("  1. Run: atlast push  (upload all batches)")
    print("  2. Check: curl https://api.weba0.com/v1/stats")
    print(f"  3. Verify: curl {LLACHAT_API}/v1/agent/atlas/profile")
    print(f"{'='*60}")

    # Save results
    with open("stress_test_results.json", "w") as f:
        json.dump({"results": all_results, "total_calls": total_calls,
                   "duration_s": total_duration, "timestamp": time.time()}, f, indent=2)
    print(f"\nResults saved to stress_test_results.json")


if __name__ == "__main__":
    run_all()
