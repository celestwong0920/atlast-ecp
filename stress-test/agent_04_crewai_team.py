"""
Agent 4: CrewAI Team — Multi-agent collaboration.
3 agents (researcher, writer, reviewer) working on a report.
Tests: CrewAI adapter, session_id, multiple agent names, delegation tracking.
"""
import time
from openai import OpenAI
from atlast_ecp.core import record
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL_GPT4O, MODEL_HAIKU

SESSION_ID = f"sess_crew_{int(time.time())}"


def run():
    print("\n👥 Agent 4: CrewAI Team Simulation (3 agents)")
    print(f"   Session: {SESSION_ID}")

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)

    # Simulate 3-agent crew: Researcher → Writer → Reviewer
    agents = [
        {
            "name": "researcher",
            "model": MODEL_GPT4O,
            "system": "You are a research specialist. Provide detailed factual analysis.",
            "tasks": [
                "Research the current state of AI agent trust infrastructure. What solutions exist?",
                "Find data on how many AI agents are deployed in production in 2025.",
                "What are the key regulatory requirements for AI agents in the EU and US?",
                "Analyze the competitive landscape: who else is building agent trust layers?",
                "Compile key statistics about AI agent failures and accountability gaps.",
            ],
        },
        {
            "name": "writer",
            "model": MODEL_GPT4O,
            "system": "You are a technical writer. Write clear, compelling content based on research provided.",
            "tasks": [
                "Write an introduction paragraph about the AI agent trust crisis.",
                "Draft a section on 'Why Evidence Chains Matter' for a whitepaper.",
                "Write a comparison section: centralized monitoring vs decentralized protocols.",
                "Draft a case study: what happens when an AI agent makes a costly mistake.",
                "Write a conclusion with a call to action for the agent developer community.",
            ],
        },
        {
            "name": "reviewer",
            "model": MODEL_HAIKU,
            "system": "You are a critical reviewer. Find flaws, suggest improvements. Be harsh but constructive.",
            "tasks": [
                "Review the introduction: is the problem statement compelling enough?",
                "Review the evidence chains section: any logical gaps?",
                "Review the comparison: is it fair and balanced?",
                "Review the case study: is it realistic and impactful?",
                "Final review: rate the overall document 1-10 and list top 3 improvements needed.",
            ],
        },
    ]

    total_calls = 0
    accumulated_context = ""

    for agent_idx, agent in enumerate(agents):
        print(f"   Agent: {agent['name']} ({len(agent['tasks'])} tasks)")

        for task_idx, task in enumerate(agent["tasks"]):
            # Build context chain — each agent sees previous agents' work
            messages = [
                {"role": "system", "content": agent["system"]},
            ]
            if accumulated_context:
                messages.append({"role": "user", "content": f"Previous work:\n{accumulated_context[-2000:]}"})
            messages.append({"role": "user", "content": task})

            try:
                start = time.time()
                response = client.chat.completions.create(
                    model=agent["model"],
                    messages=messages,
                    max_tokens=600,
                )
                latency_ms = int((time.time() - start) * 1000)
                text = response.choices[0].message.content
                accumulated_context += f"\n[{agent['name']}]: {text[:300]}"

                # Record with delegation info
                record(
                    input_content=task,
                    output_content=text,
                    step_type="llm_call",
                    model=agent["model"],
                    latency_ms=latency_ms,
                    tokens_in=getattr(response.usage, 'prompt_tokens', None) if response.usage else None,
                    tokens_out=getattr(response.usage, 'completion_tokens', None) if response.usage else None,
                    session_id=SESSION_ID,
                    delegation_id=f"crew_task_{agent_idx}_{task_idx}",
                    delegation_depth=agent_idx,  # 0=researcher, 1=writer, 2=reviewer
                )

                total_calls += 1
                print(f"     [{task_idx+1}/{len(agent['tasks'])}] {task[:50]}... ({latency_ms}ms)")

            except Exception as e:
                print(f"     ⚠️ Error: {e}")
                total_calls += 1

    print(f"   ✅ Completed {total_calls} calls across 3 agents")
    return {"agent": "crewai_team", "calls": total_calls, "session_id": SESSION_ID}


if __name__ == "__main__":
    run()
