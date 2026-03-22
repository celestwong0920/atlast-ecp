"""
Agent 5: AutoGen-style Debate — Multi-turn discussion between 2 agents.
Tests: a2a_delegated flag, long conversation chains, parent_agent tracking.
"""
import time
from openai import OpenAI
from atlast_ecp.core import record
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL_GPT4O_MINI

SESSION_ID = f"sess_debate_{int(time.time())}"


def run():
    print("\n🗣️ Agent 5: AutoGen Debate Simulation")
    print(f"   Session: {SESSION_ID}")

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

    # Two agents debating a topic
    agent_a = {
        "name": "advocate",
        "did": "did:ecp:advocate_001",
        "system": "You are an advocate for open-source AI agent protocols. Argue passionately but with evidence. Keep responses under 200 words.",
    }
    agent_b = {
        "name": "skeptic",
        "did": "did:ecp:skeptic_001",
        "system": "You are a skeptic of standardized protocols. Argue that the market should decide, not standards bodies. Keep responses under 200 words.",
    }

    topics = [
        "Should AI agent accountability be enforced through protocol standards or market forces?",
        "Is blockchain-based evidence anchoring necessary, or is centralized logging sufficient?",
        "Should AI agents have persistent identities (DIDs), or remain anonymous?",
        "Will agent-to-agent economies require trust infrastructure, or will reputation emerge naturally?",
        "Is the EU AI Act's approach to AI regulation helpful or harmful for innovation?",
    ]

    total_calls = 0

    for topic_idx, topic in enumerate(topics):
        print(f"\n   Topic {topic_idx+1}: {topic[:60]}...")

        history_a = [{"role": "system", "content": agent_a["system"]}]
        history_b = [{"role": "system", "content": agent_b["system"]}]

        current_argument = topic
        rounds = 4  # 4 rounds per topic × 2 agents = 8 calls per topic

        for round_idx in range(rounds):
            # Agent A responds
            history_a.append({"role": "user", "content": current_argument})
            try:
                start = time.time()
                resp_a = client.chat.completions.create(
                    model=MODEL_GPT4O_MINI, messages=history_a, max_tokens=250,
                )
                lat_a = int((time.time() - start) * 1000)
                text_a = resp_a.choices[0].message.content
                history_a.append({"role": "assistant", "content": text_a})

                record(
                    input_content=current_argument,
                    output_content=text_a,
                    step_type="llm_call" if round_idx == 0 else "a2a_call",
                    model=MODEL_GPT4O_MINI,
                    latency_ms=lat_a,
                    session_id=SESSION_ID,
                    delegation_id=f"debate_{topic_idx}_round_{round_idx}",
                    delegation_depth=0,
                    parent_agent=agent_b["did"] if round_idx > 0 else None,
                )
                total_calls += 1
            except Exception as e:
                text_a = f"[Error: {e}]"
                total_calls += 1

            # Agent B responds to A
            history_b.append({"role": "user", "content": text_a})
            try:
                start = time.time()
                resp_b = client.chat.completions.create(
                    model=MODEL_GPT4O_MINI, messages=history_b, max_tokens=250,
                )
                lat_b = int((time.time() - start) * 1000)
                text_b = resp_b.choices[0].message.content
                history_b.append({"role": "assistant", "content": text_b})

                record(
                    input_content=text_a,
                    output_content=text_b,
                    step_type="a2a_call",
                    model=MODEL_GPT4O_MINI,
                    latency_ms=lat_b,
                    session_id=SESSION_ID,
                    delegation_id=f"debate_{topic_idx}_round_{round_idx}",
                    delegation_depth=1,
                    parent_agent=agent_a["did"],
                )
                total_calls += 1
                current_argument = text_b
            except Exception as e:
                current_argument = f"[Error: {e}]"
                total_calls += 1

            print(f"     Round {round_idx+1}: A({lat_a if 'lat_a' in dir() else '?'}ms) B({lat_b if 'lat_b' in dir() else '?'}ms)")

    print(f"\n   ✅ Completed {total_calls} calls ({len(topics)} topics × {rounds} rounds × 2 agents)")
    return {"agent": "autogen_debate", "calls": total_calls, "session_id": SESSION_ID}


if __name__ == "__main__":
    run()
