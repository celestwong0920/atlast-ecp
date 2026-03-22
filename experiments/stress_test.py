#!/usr/bin/env python3
"""
ATLAST ECP Internal Stress Test — 6 Agent Types, Real API Calls

Tests the complete ECP pipeline:
  wrap() → record → chain → signals → batch → verify

Uses OpenRouter with multiple models to simulate real multi-agent workloads.
Boss principle: "1天测试100天效果" — use real models, real chains.

Expected: ~80-120 LLM calls, ~$5-10 on OpenRouter
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

# --- Global Config ---
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

if not OPENROUTER_KEY:
    print("ERROR: Set OPENROUTER_API_KEY")
    sys.exit(1)

# Models — mix of tiers for realistic simulation
MODELS = {
    "fast": "openai/gpt-4o-mini",
    "mid": "anthropic/claude-3.5-haiku",
    "strong": "openai/gpt-4o",
}


def flush_print(msg):
    print(msg, flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 1: Coding Agent (wrap + chain verification)
# ═══════════════════════════════════════════════════════════════════════════════
def run_coding_agent():
    """Test: wrap(), chain integrity, multi-turn conversation."""
    ECP_DIR = "/tmp/ecp-stress-01"
    os.environ["ATLAST_ECP_DIR"] = ECP_DIR
    
    from openai import OpenAI
    from atlast_ecp import wrap
    from atlast_ecp.storage import load_records
    from atlast_ecp.record import compute_chain_hash
    
    client = wrap(OpenAI(api_key=OPENROUTER_KEY, base_url=BASE_URL), session_id="stress_coding")
    
    tasks = [
        "Write a Python function to merge two sorted lists. Keep it under 20 lines.",
        "Now add type hints and a docstring.",
        "Write 3 pytest test cases for this function.",
        "Find any bugs in the code above and fix them.",
        "Refactor to handle edge cases: empty lists, single-element lists.",
    ]
    
    conversation = []
    for i, task in enumerate(tasks):
        conversation.append({"role": "user", "content": task})
        resp = client.chat.completions.create(
            model=MODELS["mid"], messages=conversation, max_tokens=500
        )
        answer = resp.choices[0].message.content
        conversation.append({"role": "assistant", "content": answer})
        flush_print(f"  [coding] Task {i+1}/{len(tasks)} ✓")
    
    # Verify chain integrity
    records = load_records(limit=20, ecp_dir=ECP_DIR)
    chain_ok = True
    for r in records:
        if "chain" in r:
            expected = compute_chain_hash(r)
            if expected != r["chain"]["hash"]:
                chain_ok = False
                flush_print(f"  ❌ CHAIN BROKEN at {r['id']}")
    
    return {
        "agent": "coding",
        "records": len(records),
        "chain_ok": chain_ok,
        "tasks": len(tasks),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 2: Research Agent (LangChain adapter)
# ═══════════════════════════════════════════════════════════════════════════════
def run_research_agent():
    """Test: LangChain callback, session_id, multi-stage pipeline."""
    ECP_DIR = "/tmp/ecp-stress-02"
    os.environ["ATLAST_ECP_DIR"] = ECP_DIR
    
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from atlast_ecp.adapters.langchain import ATLASTCallbackHandler
    from atlast_ecp.storage import load_records
    
    handler = ATLASTCallbackHandler(agent="research-agent", verbose=False, session_id="stress_research")
    llm = ChatOpenAI(
        model=MODELS["fast"], api_key=OPENROUTER_KEY, base_url=BASE_URL,
        callbacks=[handler], max_tokens=400,
    )
    parser = StrOutputParser()
    
    topics = [
        "Impact of EU AI Act on autonomous AI agents",
        "Blockchain-based attestation for agent accountability",
    ]
    
    for i, topic in enumerate(topics):
        # 3-stage pipeline per topic
        outline = (ChatPromptTemplate.from_messages([
            ("system", "Create a brief 3-point outline."),
            ("user", "Topic: {topic}")
        ]) | llm | parser).invoke({"topic": topic})
        flush_print(f"  [research] Topic {i+1} outline ✓")
        
        analysis = (ChatPromptTemplate.from_messages([
            ("system", "Analyze briefly."),
            ("user", "Outline:\n{outline}\n\nBrief analysis per point.")
        ]) | llm | parser).invoke({"outline": outline})
        flush_print(f"  [research] Topic {i+1} analysis ✓")
        
        (ChatPromptTemplate.from_messages([
            ("system", "Summarize in 50 words."),
            ("user", "Analysis:\n{analysis}")
        ]) | llm | parser).invoke({"analysis": analysis})
        flush_print(f"  [research] Topic {i+1} summary ✓")
    
    records = load_records(limit=50, ecp_dir=ECP_DIR)
    return {
        "agent": "research",
        "records": len(records),
        "callback_count": handler.record_count,
        "topics": len(topics),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 3: Customer Support (track decorator, flags)
# ═══════════════════════════════════════════════════════════════════════════════
def run_support_agent():
    """Test: record_minimal, flag detection, trust signals."""
    ECP_DIR = "/tmp/ecp-stress-03"
    os.environ["ATLAST_ECP_DIR"] = ECP_DIR
    
    from openai import OpenAI
    from atlast_ecp.core import record_minimal, reset
    from atlast_ecp.signals import compute_trust_signals, detect_flags
    from atlast_ecp.storage import load_records
    
    reset()
    client = OpenAI(api_key=OPENROUTER_KEY, base_url=BASE_URL)
    
    queries = [
        ("How do I reset my password?", "support"),
        ("I want a refund for order #12345", "billing"),
        ("Your product broke after 2 days!", "complaint"),
        ("Can you help me with something technical?", "tech"),
        ("I'm not sure if this is the right product for me", "sales"),
    ]
    
    for i, (query, category) in enumerate(queries):
        t0 = time.time()
        resp = client.chat.completions.create(
            model=MODELS["fast"],
            messages=[
                {"role": "system", "content": f"You are a {category} support agent. Be brief (2 sentences)."},
                {"role": "user", "content": query}
            ],
            max_tokens=150,
        )
        output = resp.choices[0].message.content
        latency = int((time.time() - t0) * 1000)
        flags = detect_flags(output)
        
        record_minimal(
            input_content=query,
            output_content=output,
            agent="support-agent",
            action="llm_call",
            model=MODELS["fast"],
            latency_ms=latency,
            session_id=f"stress_support_{category}",
        )
        flush_print(f"  [support] Query {i+1}/{len(queries)} flags={flags} ✓")
    
    records = load_records(limit=20, ecp_dir=ECP_DIR)
    signals = compute_trust_signals(records)
    
    return {
        "agent": "support",
        "records": len(records),
        "signals": signals,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 4: Delegation Chain (parent → child, session tracking)
# ═══════════════════════════════════════════════════════════════════════════════
def run_delegation_agent():
    """Test: delegation fields, parent_agent, session_id chaining."""
    ECP_DIR = "/tmp/ecp-stress-04"
    os.environ["ATLAST_ECP_DIR"] = ECP_DIR
    
    from openai import OpenAI
    from atlast_ecp.core import record, reset
    from atlast_ecp.identity import get_or_create_identity
    from atlast_ecp.storage import load_records
    from atlast_ecp.record import compute_chain_hash
    
    reset()
    identity = get_or_create_identity()
    client = OpenAI(api_key=OPENROUTER_KEY, base_url=BASE_URL)
    
    session_id = "stress_delegation_parent"
    
    # Parent agent: planning
    resp = client.chat.completions.create(
        model=MODELS["fast"],
        messages=[{"role": "user", "content": "Plan a 3-step approach to analyze a dataset. Just list steps."}],
        max_tokens=200,
    )
    plan = resp.choices[0].message.content
    
    record(
        input_content="Plan dataset analysis",
        output_content=plan,
        step_type="llm_call",
        model=MODELS["fast"],
        session_id=session_id,
        delegation_depth=0,
    )
    flush_print(f"  [delegation] Parent planned ✓")
    
    # Sub-agents: execute each step
    for i in range(3):
        step_prompt = f"Execute step {i+1} of this plan: {plan[:200]}. Give a brief result."
        resp = client.chat.completions.create(
            model=MODELS["fast"],
            messages=[{"role": "user", "content": step_prompt}],
            max_tokens=200,
        )
        result = resp.choices[0].message.content
        
        record(
            input_content=step_prompt,
            output_content=result,
            step_type="a2a_call",
            model=MODELS["fast"],
            session_id=f"stress_delegation_child_{i}",
            delegation_id=session_id,
            delegation_depth=1,
            parent_agent=identity["did"],
        )
        flush_print(f"  [delegation] Sub-agent {i+1}/3 ✓")
    
    # Parent: synthesize
    resp = client.chat.completions.create(
        model=MODELS["fast"],
        messages=[{"role": "user", "content": "Summarize the analysis results in 2 sentences."}],
        max_tokens=100,
    )
    record(
        input_content="Synthesize results",
        output_content=resp.choices[0].message.content,
        step_type="llm_call",
        model=MODELS["fast"],
        session_id=session_id,
        delegation_depth=0,
    )
    flush_print(f"  [delegation] Parent synthesized ✓")
    
    records = load_records(limit=20, ecp_dir=ECP_DIR)
    
    # Verify all chain hashes
    chain_ok = True
    for r in records:
        if "chain" in r:
            expected = compute_chain_hash(r)
            if expected != r["chain"]["hash"]:
                chain_ok = False
    
    # Verify delegation fields present
    delegation_records = [r for r in records if r.get("step", {}).get("delegation_depth", -1) == 1]
    
    return {
        "agent": "delegation",
        "records": len(records),
        "chain_ok": chain_ok,
        "delegation_records": len(delegation_records),
        "parent_did": identity["did"],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 5: Batch + Merkle Verification
# ═══════════════════════════════════════════════════════════════════════════════
def run_batch_agent():
    """Test: batch collection, Merkle tree, proof verification."""
    ECP_DIR = "/tmp/ecp-stress-05"
    os.environ["ATLAST_ECP_DIR"] = ECP_DIR
    
    from openai import OpenAI
    from atlast_ecp import wrap
    from atlast_ecp.storage import load_records
    from atlast_ecp.batch import collect_batch, build_merkle_tree
    from atlast_ecp.verify import build_merkle_proof, verify_merkle_proof
    
    client = wrap(OpenAI(api_key=OPENROUTER_KEY, base_url=BASE_URL), session_id="stress_batch")
    
    # Generate 8 records
    for i in range(8):
        client.chat.completions.create(
            model=MODELS["fast"],
            messages=[{"role": "user", "content": f"Count from 1 to {i+3}."}],
            max_tokens=50,
        )
        flush_print(f"  [batch] Record {i+1}/8 ✓")
    
    records = load_records(limit=20, ecp_dir=ECP_DIR)
    hashes = [r["chain"]["hash"] for r in records if "chain" in r]
    
    if len(hashes) >= 2:
        root, _tree = build_merkle_tree(hashes)
        
        # Verify each record's Merkle proof
        all_proofs_ok = True
        for h in hashes:
            proof = build_merkle_proof(hashes, h)
            if not verify_merkle_proof(h, proof, root):
                all_proofs_ok = False
                flush_print(f"  ❌ Merkle proof failed for {h[:20]}")
        
        flush_print(f"  [batch] Merkle root: {root[:30]}...")
        flush_print(f"  [batch] All proofs valid: {all_proofs_ok}")
    else:
        root = ""
        all_proofs_ok = False
    
    return {
        "agent": "batch",
        "records": len(records),
        "merkle_root": root[:40] if root else None,
        "all_proofs_ok": all_proofs_ok,
        "hash_count": len(hashes),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Agent 6: Chaos Agent (errors, retries, edge cases)
# ═══════════════════════════════════════════════════════════════════════════════
def run_chaos_agent():
    """Test: error recording, flag injection, chain continuity after errors."""
    ECP_DIR = "/tmp/ecp-stress-06"
    os.environ["ATLAST_ECP_DIR"] = ECP_DIR
    
    from openai import OpenAI
    from atlast_ecp import wrap
    from atlast_ecp.core import record_minimal, reset
    from atlast_ecp.storage import load_records
    from atlast_ecp.signals import compute_trust_signals
    
    reset()
    client = wrap(OpenAI(api_key=OPENROUTER_KEY, base_url=BASE_URL), session_id="stress_chaos")
    
    # Normal calls
    for i in range(3):
        client.chat.completions.create(
            model=MODELS["fast"],
            messages=[{"role": "user", "content": f"Say the number {i+1}."}],
            max_tokens=10,
        )
        flush_print(f"  [chaos] Normal {i+1}/3 ✓")
    
    # Error: invalid model
    try:
        client.chat.completions.create(
            model="nonexistent/model",
            messages=[{"role": "user", "content": "This should fail"}],
            max_tokens=10,
        )
    except Exception as e:
        record_minimal(
            input_content="This should fail",
            output_content=f"ERROR: {e}",
            agent="chaos-agent",
            action="llm_call",
            session_id="stress_chaos",
        )
        flush_print(f"  [chaos] Error recorded ✓")
    
    # Simulated retry
    record_minimal(
        input_content="Retry attempt",
        output_content="ERROR: timeout",
        agent="chaos-agent",
        action="llm_call",
        session_id="stress_chaos",
    )
    client.chat.completions.create(
        model=MODELS["fast"],
        messages=[{"role": "user", "content": "Retry: say hello"}],
        max_tokens=10,
    )
    flush_print(f"  [chaos] Retry sequence ✓")
    
    # More normal calls after errors (chain should continue)
    for i in range(2):
        client.chat.completions.create(
            model=MODELS["fast"],
            messages=[{"role": "user", "content": f"Post-error call {i+1}"}],
            max_tokens=10,
        )
        flush_print(f"  [chaos] Post-error {i+1}/2 ✓")
    
    records = load_records(limit=30, ecp_dir=ECP_DIR)
    signals = compute_trust_signals(records)
    
    return {
        "agent": "chaos",
        "records": len(records),
        "signals": {k: v for k, v in signals.items() if isinstance(v, (int, float))},
        "error_rate": signals.get("error_rate", 0),
        "chain_intact": signals.get("chain_integrity", 0) == 1.0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main Runner
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    import shutil
    
    # Clean previous runs
    for i in range(1, 7):
        p = f"/tmp/ecp-stress-0{i}"
        if os.path.exists(p):
            shutil.rmtree(p)
    
    agents = [
        ("Agent 1: Coding (wrap + chain)", run_coding_agent),
        ("Agent 2: Research (LangChain)", run_research_agent),
        ("Agent 3: Support (record_minimal + signals)", run_support_agent),
        ("Agent 4: Delegation (parent→child)", run_delegation_agent),
        ("Agent 5: Batch (Merkle proof)", run_batch_agent),
        ("Agent 6: Chaos (errors + recovery)", run_chaos_agent),
    ]
    
    results = []
    total_start = time.time()
    
    for name, fn in agents:
        flush_print(f"\n{'='*60}")
        flush_print(f"  {name}")
        flush_print(f"{'='*60}")
        t0 = time.time()
        try:
            result = fn()
            result["duration_s"] = round(time.time() - t0, 1)
            result["status"] = "OK"
            results.append(result)
            flush_print(f"  ✅ {result['records']} records in {result['duration_s']}s")
        except Exception as e:
            traceback.print_exc()
            results.append({"agent": name, "status": "FAILED", "error": str(e), "duration_s": round(time.time() - t0, 1)})
            flush_print(f"  ❌ FAILED: {e}")
    
    total_elapsed = round(time.time() - total_start, 1)
    total_records = sum(r.get("records", 0) for r in results)
    all_ok = all(r.get("status") == "OK" for r in results)
    
    # Cross-agent chain verification
    flush_print(f"\n{'='*60}")
    flush_print(f"  CROSS-AGENT VERIFICATION")
    flush_print(f"{'='*60}")
    
    chain_results = {}
    for r in results:
        if "chain_ok" in r:
            chain_results[r["agent"]] = r["chain_ok"]
    
    merkle_ok = any(r.get("all_proofs_ok") for r in results)
    delegation_ok = any(r.get("delegation_records", 0) > 0 for r in results)
    signals_ok = any("signals" in r for r in results)
    
    flush_print(f"  Chain integrity: {chain_results}")
    flush_print(f"  Merkle proofs:   {'✅' if merkle_ok else '❌'}")
    flush_print(f"  Delegation:      {'✅' if delegation_ok else '❌'}")
    flush_print(f"  Trust signals:   {'✅' if signals_ok else '❌'}")
    
    # Summary
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "total_duration_s": total_elapsed,
        "total_records": total_records,
        "total_api_calls": total_records,  # ~1:1 for this test
        "all_passed": all_ok,
        "chain_integrity": chain_results,
        "merkle_proofs_ok": merkle_ok,
        "delegation_ok": delegation_ok,
        "agents": results,
    }
    
    summary_path = RESULTS_DIR / "stress_test_report.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    flush_print(f"\n{'='*60}")
    flush_print(f"  STRESS TEST {'PASSED ✅' if all_ok else 'FAILED ❌'}")
    flush_print(f"  {total_records} records | {total_elapsed}s | 6 agents")
    flush_print(f"  Report: {summary_path}")
    flush_print(f"{'='*60}")
    
    return summary


if __name__ == "__main__":
    main()
