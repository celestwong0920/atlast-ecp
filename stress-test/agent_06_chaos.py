"""
Agent 6: Chaos Agent — Deliberately triggers edge cases and errors.
Tests: error flag, retried flag, incomplete flag, high_latency flag,
       fail-open behavior, batch throttling, malformed inputs.
"""
import time
import os
from openai import OpenAI
from atlast_ecp.core import record, record_minimal
from atlast_ecp.batch import run_batch, MIN_BATCH_INTERVAL_S
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL_GPT4O_MINI, MODEL_HAIKU

SESSION_ID = f"sess_chaos_{int(time.time())}"


def run():
    print("\n💥 Agent 6: Chaos Agent (error injection)")
    print(f"   Session: {SESSION_ID}")

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    results = []

    # Test 1: Normal call (baseline)
    print("   [1/8] Normal call (baseline)...")
    try:
        start = time.time()
        resp = client.chat.completions.create(
            model=MODEL_GPT4O_MINI,
            messages=[{"role": "user", "content": "Say hello in exactly 3 words."}],
            max_tokens=20,
        )
        lat = int((time.time() - start) * 1000)
        record(input_content="Say hello", output_content=resp.choices[0].message.content,
               step_type="llm_call", model=MODEL_GPT4O_MINI, latency_ms=lat, session_id=SESSION_ID)
        results.append("normal: OK")
    except Exception as e:
        results.append(f"normal: ERROR {e}")

    # Test 2: Retry detection (same input twice)
    print("   [2/8] Retry detection...")
    same_input = "What is 2+2? Answer with just the number."
    for attempt in range(3):
        try:
            start = time.time()
            resp = client.chat.completions.create(
                model=MODEL_GPT4O_MINI,
                messages=[{"role": "user", "content": same_input}],
                max_tokens=10,
            )
            lat = int((time.time() - start) * 1000)
            record(input_content=same_input, output_content=resp.choices[0].message.content,
                   step_type="llm_call", model=MODEL_GPT4O_MINI, latency_ms=lat, session_id=SESSION_ID)
        except Exception:
            pass
    results.append("retry: 3 attempts recorded")

    # Test 3: Error output (trigger error flag)
    print("   [3/8] Error flag trigger...")
    record(input_content="Test input", output_content="Error: Connection refused. Traceback: ...",
           step_type="llm_call", model="test", latency_ms=100, session_id=SESSION_ID)
    results.append("error_flag: recorded")

    # Test 4: High latency simulation
    print("   [4/8] High latency simulation...")
    record(input_content="Slow query", output_content="Eventually responded",
           step_type="llm_call", model="test", latency_ms=45000, session_id=SESSION_ID)
    results.append("high_latency: recorded (45s)")

    # Test 5: Empty/incomplete output
    print("   [5/8] Incomplete output...")
    record(input_content="Generate a long essay", output_content="",
           step_type="llm_call", model="test", latency_ms=5000, session_id=SESSION_ID)
    results.append("incomplete: recorded")

    # Test 6: Hedged output
    print("   [6/8] Hedged output...")
    record(input_content="Is this safe?",
           output_content="I'm not entirely sure, but I think it might be okay. However, I could be wrong.",
           step_type="llm_call", model="test", latency_ms=200, session_id=SESSION_ID)
    results.append("hedged: recorded")

    # Test 7: A2A delegation
    print("   [7/8] A2A delegation chain...")
    for depth in range(4):  # 4-level deep delegation
        record(
            input_content=f"Delegated task at depth {depth}",
            output_content=f"Completed by sub-agent at depth {depth}",
            step_type="a2a_call",
            model="test",
            latency_ms=100 * (depth + 1),
            session_id=SESSION_ID,
            delegation_id=f"chaos_chain_{depth}",
            delegation_depth=depth,
            parent_agent=f"did:ecp:chaos_parent_{depth}" if depth > 0 else None,
        )
    results.append("a2a_chain: 4 levels recorded")

    # Test 8: Batch throttle test
    print("   [8/8] Batch throttle test...")
    batch_result = run_batch()
    results.append(f"batch: {batch_result.get('status', 'unknown')}")

    # Try immediate second batch (should be throttled)
    batch_result2 = run_batch()
    results.append(f"batch_throttle: {batch_result2.get('status', 'unknown')}")

    print(f"   ✅ Chaos tests complete:")
    for r in results:
        print(f"      - {r}")

    return {"agent": "chaos", "tests": len(results), "results": results, "session_id": SESSION_ID}


if __name__ == "__main__":
    run()
