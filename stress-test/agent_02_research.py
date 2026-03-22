"""
Agent 2: Research Agent — LangChain adapter.
Simulates a research agent that searches, summarizes, and writes reports.
Tests: LangChain callback, tool_calls, parent_run_id→delegation_id, high token output.
"""
import time
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, MODEL_GPT4O

SESSION_ID = f"sess_research_{int(time.time())}"


def run():
    print("\n🔍 Agent 2: Research Agent (LangChain + gpt-4o)")
    print(f"   Session: {SESSION_ID}")

    try:
        from langchain_openai import ChatOpenAI
        from atlast_ecp.adapters.langchain import ATLASTCallbackHandler
    except ImportError:
        print("   ⚠️ LangChain not installed, using fallback")
        return _run_fallback()

    handler = ATLASTCallbackHandler(agent="research-agent", verbose=False, session_id=SESSION_ID)
    llm = ChatOpenAI(
        model=MODEL_GPT4O,
        openai_api_key=OPENROUTER_API_KEY,
        openai_api_base=OPENROUTER_BASE_URL,
        max_tokens=800,
        callbacks=[handler],
    )

    topics = [
        # Phase 1: Research (10 calls)
        "What are the top 5 AI agent frameworks in 2025? List with brief descriptions.",
        "Compare LangChain vs CrewAI vs AutoGen. Which is best for multi-agent systems?",
        "What is the current state of AI agent trust and accountability?",
        "Explain the EU AI Act requirements for autonomous AI systems.",
        "What are Decentralized Identifiers (DIDs) and how do they work?",
        "How does Ethereum Attestation Service (EAS) work?",
        "What is a Merkle tree and why is it useful for data integrity?",
        "Explain zero-knowledge proofs in the context of AI agent privacy.",
        "What are the main challenges in building an agent-to-agent economy?",
        "How do trust scores work in decentralized reputation systems?",

        # Phase 2: Synthesis (5 calls)
        "Based on the research above, write a 3-paragraph executive summary of the AI agent trust problem.",
        "What are the top 3 technical approaches to solving agent accountability?",
        "Draft a comparison table: centralized logging vs protocol-based evidence chains.",
        "Write a risk analysis: what happens if AI agents operate without accountability?",
        "Propose a 3-phase roadmap for building agent trust infrastructure.",
    ]

    results = []
    for i, topic in enumerate(topics):
        print(f"   [{i+1}/{len(topics)}] {topic[:60]}...")
        try:
            response = llm.invoke(topic)
            results.append(response.content[:100] if hasattr(response, 'content') else str(response)[:100])
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            results.append(f"ERROR: {e}")

    print(f"   ✅ Completed {len(results)} calls, {handler.record_count} ECP records")
    return {"agent": "research", "calls": len(results), "ecp_records": handler.record_count, "session_id": SESSION_ID}


def _run_fallback():
    """Fallback without LangChain — use record_minimal directly."""
    from openai import OpenAI
    from atlast_ecp.core import record_minimal
    from config import MODEL_GPT4O

    client = OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)
    topics = [
        "What are the top 5 AI agent frameworks in 2025?",
        "Compare LangChain vs CrewAI vs AutoGen.",
        "What is the EU AI Act?",
        "How does Ethereum Attestation Service work?",
        "What are Merkle trees?",
    ]

    results = []
    for i, topic in enumerate(topics):
        print(f"   [{i+1}/{len(topics)}] {topic[:60]}...")
        try:
            start = time.time()
            resp = client.chat.completions.create(model=MODEL_GPT4O, messages=[{"role": "user", "content": topic}], max_tokens=500)
            latency = int((time.time() - start) * 1000)
            text = resp.choices[0].message.content
            record_minimal(input_content=topic, output_content=text, agent="research-agent",
                          action="llm_call", model=MODEL_GPT4O, latency_ms=latency, session_id=SESSION_ID)
            results.append(text[:100])
        except Exception as e:
            results.append(f"ERROR: {e}")

    print(f"   ✅ Completed {len(results)} calls (fallback mode)")
    return {"agent": "research", "calls": len(results), "session_id": SESSION_ID}


if __name__ == "__main__":
    run()
