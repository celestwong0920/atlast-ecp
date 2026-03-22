"""
Agent 3: Customer Service Bot — @track decorator / record_minimal.
High-frequency short conversations. Tests throughput + batch splitting.
"""
import time
from openai import OpenAI
from atlast_ecp.core import record_minimal
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL_HAIKU

SESSION_ID = f"sess_cs_{int(time.time())}"

# Simulate 50 customer conversations (3 turns each = 150 calls)
CONVERSATIONS = [
    [
        "How do I reset my password?",
        "I tried that but it says invalid email. My email is john@example.com",
        "Thanks, it worked! How do I enable 2FA?",
    ],
    [
        "What's your refund policy?",
        "I bought a product 3 days ago. Can I still return it?",
        "OK, how long does the refund take?",
    ],
    [
        "My order hasn't arrived. Order #12345",
        "It was supposed to arrive yesterday.",
        "Can you expedite the shipping?",
    ],
] * 17  # 51 conversations × 3 turns = 153 calls


def run():
    print("\n💬 Agent 3: Customer Service (record_minimal + claude-haiku)")
    print(f"   Session: {SESSION_ID}")
    print(f"   Conversations: {len(CONVERSATIONS)}, ~{len(CONVERSATIONS)*3} calls")

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

    total_calls = 0
    total_errors = 0
    latencies = []

    for conv_idx, conversation in enumerate(CONVERSATIONS):
        conv_session = f"{SESSION_ID}_conv{conv_idx}"
        history = [{"role": "system", "content": "You are a helpful customer service agent. Be concise."}]

        for turn_idx, user_msg in enumerate(conversation):
            history.append({"role": "user", "content": user_msg})

            try:
                start = time.time()
                response = client.chat.completions.create(
                    model=MODEL_HAIKU,
                    messages=history,
                    max_tokens=150,
                )
                latency_ms = int((time.time() - start) * 1000)
                latencies.append(latency_ms)

                text = response.choices[0].message.content
                history.append({"role": "assistant", "content": text})

                tokens_in = getattr(response.usage, 'prompt_tokens', None) if response.usage else None
                tokens_out = getattr(response.usage, 'completion_tokens', None) if response.usage else None

                record_minimal(
                    input_content=user_msg,
                    output_content=text,
                    agent="cs-bot",
                    action="llm_call",
                    model=MODEL_HAIKU,
                    latency_ms=latency_ms,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    session_id=conv_session,
                )

                total_calls += 1

            except Exception as e:
                total_errors += 1
                record_minimal(
                    input_content=user_msg,
                    output_content=f"ERROR: {e}",
                    agent="cs-bot",
                    action="llm_call",
                    model=MODEL_HAIKU,
                    latency_ms=0,
                    session_id=conv_session,
                )

        if (conv_idx + 1) % 10 == 0:
            print(f"   [{conv_idx+1}/{len(CONVERSATIONS)}] conversations done...")

    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    print(f"   ✅ Completed {total_calls} calls, {total_errors} errors, avg latency {avg_latency:.0f}ms")
    return {
        "agent": "customer_service",
        "calls": total_calls,
        "errors": total_errors,
        "avg_latency_ms": round(avg_latency),
        "session_id": SESSION_ID,
    }


if __name__ == "__main__":
    run()
