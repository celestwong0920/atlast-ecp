"""
Agent 1: Coding Agent — wrap() Layer 0 integration.
Simulates a developer agent that reads, analyzes, and refactors code.
Tests: wrap(), streaming, long chains, session_id, sub-agent delegation.
"""
import time
import json
from openai import OpenAI
from atlast_ecp import wrap
from atlast_ecp.core import record
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL_SONNET

SESSION_ID = f"sess_coding_{int(time.time())}"

def run():
    print("\n🔧 Agent 1: Coding Agent (wrap + claude-sonnet)")
    print(f"   Session: {SESSION_ID}")

    client = wrap(
        OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL),
        session_id=SESSION_ID,
    )

    tasks = [
        # Phase 1: Read & understand (5 calls)
        "Read this Python function and explain what it does:\n```python\ndef merge_sort(arr):\n    if len(arr) <= 1: return arr\n    mid = len(arr) // 2\n    left = merge_sort(arr[:mid])\n    right = merge_sort(arr[mid:])\n    return merge(left, right)\n```",
        "What is the time complexity of this merge_sort? Explain step by step.",
        "Are there any edge cases that could cause issues?",
        "How would you optimize this for nearly-sorted arrays?",
        "Write unit tests for this function covering all edge cases.",

        # Phase 2: Refactor (5 calls)
        "Refactor merge_sort to be iterative instead of recursive. Show the full code.",
        "Add type hints and docstrings to the refactored version.",
        "Now add logging to track the number of comparisons made.",
        "Write a benchmark comparing recursive vs iterative versions.",
        "Generate a comprehensive code review summary of all changes made.",

        # Phase 3: Sub-agent delegation (simulate)
        "You are now delegating a security review to a sub-agent. What security concerns exist in sort implementations?",
        "The sub-agent found a potential integer overflow in the mid calculation. How would you fix it?",
    ]

    results = []
    for i, task in enumerate(tasks):
        print(f"   [{i+1}/{len(tasks)}] {task[:60]}...")
        try:
            # Alternate between streaming and non-streaming
            streaming = (i % 3 == 0)
            response = client.chat.completions.create(
                model=MODEL_SONNET,
                messages=[{"role": "user", "content": task}],
                max_tokens=500,
                stream=streaming,
            )

            if streaming:
                text = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        text += chunk.choices[0].delta.content
                results.append(text[:100])
            else:
                text = response.choices[0].message.content
                results.append(text[:100])

            # For last 2 tasks (sub-agent), also record delegation manually
            if i >= len(tasks) - 2:
                record(
                    input_content=task,
                    output_content=text,
                    step_type="a2a_call",
                    model=MODEL_SONNET,
                    session_id=SESSION_ID,
                    delegation_id=f"del_security_review_{i}",
                    delegation_depth=1,
                )

        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            results.append(f"ERROR: {e}")

    print(f"   ✅ Completed {len(results)} calls")
    return {"agent": "coding", "calls": len(results), "session_id": SESSION_ID}


if __name__ == "__main__":
    run()
