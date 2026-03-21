# ATLAST Protocol: Trust Infrastructure for the Agent Economy

**Version 1.0 — Draft**
**Authors:** ATLAST Protocol Team
**Date:** March 2026

---

## Abstract

The rapid proliferation of autonomous AI agents — systems capable of reasoning, planning, and executing multi-step tasks — creates a fundamental trust deficit. When an AI agent manages financial transactions, writes production code, or makes decisions on behalf of humans, there exists no standardized mechanism to verify *what it did*, *why it did it*, or *whether it did it correctly*.

ATLAST (Agent-Layer Accountability Standards & Transactions) Protocol addresses this gap by introducing **Evidence Chain Protocol (ECP)**, a lightweight, tamper-evident recording standard for AI agent operations. ECP captures the complete decision-execution chain — inputs, reasoning, tool calls, outputs, and confidence assessments — producing cryptographically linked records anchored to public blockchains.

The protocol achieves practical adoption through a **three-layer progressive integration** model:

- **Layer 0 (Zero-Code):** A transparent API proxy that records all LLM interactions with a single command, requiring zero code changes.
- **Layer 1 (SDK):** A Python/TypeScript SDK adding structured evidence capture in 5 lines of code, with a fail-open design that guarantees zero impact on agent operations.
- **Layer 2 (Framework Adapters):** Native integrations for LangChain, CrewAI, AutoGen, and custom frameworks.

Key design principles include:

1. **Fail-Open:** Recording failures never affect agent functionality. The SDK adds < 1ms overhead (measured: 0.78ms / 0.55%).
2. **Gas-Free for Users:** Super-batch Merkle aggregation reduces blockchain costs to < $0.002 per 1,000 agents per month, borne entirely by infrastructure operators.
3. **Incomplete Evidence is Worthless:** ECP chains must be 100% complete under normal operation — partial records provide false assurance.
4. **Open Standard:** The protocol specification, SDK, and server are fully open-source under MIT license.

ATLAST Protocol is positioned as the **trust layer** for the emerging agent economy — analogous to TCP/IP for networking or TLS for web security. As the EU AI Act (effective 2027) mandates transparency and accountability for AI systems, ATLAST provides a compliance-ready infrastructure that transforms opaque agent behavior into verifiable, auditable evidence chains.

---

## 1. Introduction

### 1.1 The Agent Trust Gap

The AI industry is undergoing a fundamental architectural shift. Large Language Models (LLMs) are evolving from passive text generators into autonomous agents — systems that reason about tasks, invoke external tools, make decisions, and execute multi-step workflows with minimal human oversight.

This shift creates an unprecedented trust challenge:

| Dimension | Traditional Software | AI Agents |
|-----------|---------------------|-----------|
| Behavior | Deterministic | Probabilistic |
| Auditability | Source code + logs | Opaque reasoning |
| Accountability | Clear ownership | Diffused responsibility |
| Verification | Unit tests | No standard mechanism |

When an enterprise deploys an AI agent to process insurance claims, manage supply chains, or execute financial trades, fundamental questions arise:

- **Did the agent follow instructions?** There is no standard way to verify compliance with given directives.
- **What was its reasoning?** Agent "thinking" processes are typically discarded after execution.
- **Can we reproduce the decision?** Without capturing inputs, context, and intermediate states, reproducibility is impossible.
- **Who is accountable when things go wrong?** Without evidence chains, post-incident analysis relies on incomplete logs.

### 1.2 Regulatory Imperative

The EU AI Act, entering enforcement in 2027, establishes legal requirements directly relevant to agent operations:

- **Article 14 (Human Oversight):** High-risk AI systems must enable effective human oversight, including the ability to "correctly interpret the high-risk AI system's output."
- **Article 52 (Transparency):** AI systems must be designed to ensure users are aware they are interacting with AI and can understand its behavior.
- **Article 53 (General-Purpose AI):** Providers of general-purpose AI models must maintain documentation of training, evaluation, and capabilities.

No existing standard addresses the operational evidence gap — the record of *what an agent did* during deployment, not just *how it was trained*.

### 1.3 ATLAST Protocol

ATLAST Protocol fills this gap with four sub-protocols:

1. **ECP (Evidence Chain Protocol):** The core recording standard — captures agent inputs, reasoning, execution steps, and outputs in cryptographically linked chains. *MVP focus.*
2. **AIP (Agent Identity Protocol):** Decentralized identity for agents — unique DIDs, capability declarations, and trust credentials. *Phase 3.*
3. **ASP (Agent Safety Protocol):** Real-time safety boundaries — rate limits, scope restrictions, and automated circuit breakers. *Phase 3.*
4. **ACP (Agent Certification Protocol):** Third-party verification — auditors attest to agent behavior patterns and compliance. *Phase 3.*

This whitepaper focuses on **ECP**, the foundational protocol that enables all subsequent layers.

### 1.4 Design Philosophy

Three principles guide every ATLAST design decision:

**1. Zero Friction Adoption**
If integrating evidence recording requires more than 3 minutes, most developers will skip it. Layer 0 (zero-code proxy) ensures the minimum adoption barrier is a single command:
```bash
atlast run python my_agent.py
```

**2. Fail-Open, Always**
Evidence recording must never degrade agent performance or reliability. If the ATLAST SDK crashes, the agent continues operating normally. Measured overhead: 0.78ms per LLM call (0.55% of a typical 142ms call).

**3. Incomplete Evidence is Worthless**
A chain of evidence with gaps provides false assurance. ECP is designed so that under normal operation (SDK initialized, network available), 100% of agent actions are captured. Missing records are treated as system failures, not acceptable losses.

---

## 2. Evidence Chain Protocol (ECP)

### 2.1 Overview

An Evidence Chain is an ordered sequence of **ECP Records**, each representing a discrete step in an agent's operation. Records are cryptographically linked via SHA-256 hashes, forming a tamper-evident chain that can be independently verified.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Record #1  │───▶│  Record #2  │───▶│  Record #3  │
│  LLM Call   │    │  Tool Use   │    │  Decision   │
│  hash: abc  │    │  prev: abc  │    │  prev: def  │
│             │    │  hash: def  │    │  hash: ghi  │
└─────────────┘    └─────────────┘    └─────────────┘
                                            │
                                     ┌──────▼──────┐
                                     │ Merkle Root │
                                     │ Batch Hash  │
                                     └──────┬──────┘
                                            │
                                     ┌──────▼──────┐
                                     │  Blockchain │
                                     │   Anchor    │
                                     └─────────────┘
```

### 2.2 ECP Record Format

Each ECP record is a JSON object with the following structure:

```json
{
  "version": "1.0",
  "chain_id": "ec_1711036800_a1b2c3",
  "record_id": "rec_uuid_v4",
  "agent_id": "did:atlast:agent_identifier",
  "session_id": "sess_unique_id",
  "timestamp": "2026-03-22T00:00:00.000Z",
  "prev_hash": "sha256:previous_record_hash",
  
  "input": {
    "raw": "User instruction or trigger",
    "context_hash": "sha256:hash_of_context_window",
    "tools_available": ["web_search", "code_exec", "file_write"]
  },
  
  "reasoning": {
    "thinking": "Agent's chain-of-thought reasoning",
    "alternatives_considered": [
      {"approach": "Option A", "rejected_reason": "Too slow"},
      {"approach": "Option B", "rejected_reason": "Security risk"}
    ],
    "chosen_approach": "Option C",
    "confidence": 0.87
  },
  
  "execution": [
    {
      "step": 1,
      "action": "web_search",
      "input": {"query": "latest API documentation"},
      "output": {"results": 5, "top_result": "..."},
      "duration_ms": 342,
      "success": true
    }
  ],
  
  "output": {
    "content": "Final response or action result",
    "tokens_in": 1500,
    "tokens_out": 800,
    "model": "claude-sonnet-4-20250514",
    "latency_ms": 2341
  },
  
  "integrity": {
    "record_hash": "sha256:this_record_hash",
    "chain_hash": "sha256:cumulative_chain_hash",
    "signature": "ed25519:agent_signature"
  }
}
```

### 2.3 Hash Chain Construction

Records within a session form a hash chain:

1. **Record Hash:** `SHA-256(canonical_json(record_without_integrity))`
2. **Chain Hash:** `SHA-256(prev_chain_hash + record_hash)`
3. **Merkle Root:** Binary Merkle tree over all record hashes in a batch

The canonical JSON serialization uses sorted keys, no whitespace, and UTF-8 encoding to ensure deterministic hashing across implementations.

### 2.4 Batch Aggregation

Individual records are grouped into **batches** (typically per-session or per-time-window). Each batch produces a Merkle root that serves as the fingerprint for verification:

```
Batch (N records)
├── record_hash_1 ─┐
├── record_hash_2 ─┤── Merkle Tree ──▶ merkle_root
├── record_hash_3 ─┤
└── record_hash_N ─┘
```

The Merkle root is:
- Stored on the ATLAST server
- Optionally anchored to a public blockchain (EAS on Base)
- Used for independent verification without accessing raw records

### 2.5 Blockchain Anchoring

ATLAST uses **Ethereum Attestation Service (EAS)** on Base (L2) for on-chain anchoring:

| Parameter | Value |
|-----------|-------|
| Chain | Base (Mainnet: 8453, Sepolia: 84532) |
| Schema UID | `0xa67da7e...` |
| Cost per attestation | ~$0.001-0.005 |
| Finality | ~2 seconds |

**Super-Batch Aggregation** further reduces costs:
```
Agent 1 batch → merkle_root_1 ─┐
Agent 2 batch → merkle_root_2 ─┤── Super Merkle ──▶ 1 on-chain tx
Agent 3 batch → merkle_root_3 ─┤
...                             │
Agent N batch → merkle_root_N ─┘

Cost: 1 tx per super-batch ≈ $0.002
At 1000 agents/batch: $0.000002 per agent
```

Users never pay gas fees. Infrastructure operators absorb costs through super-batch aggregation.

---

## 3. Three-Layer Progressive Integration

### 3.1 Design Rationale

Adoption is the primary constraint. The protocol is worthless if nobody uses it. ATLAST addresses this with three progressively deeper integration layers:

| Layer | Effort | Capture Depth | Use Case |
|-------|--------|---------------|----------|
| 0 | 1 command | LLM I/O only | Quick eval, compliance minimum |
| 1 | 5 lines | + tools, decisions, metadata | Production monitoring |
| 2 | 10-20 lines | + framework internals | Deep audit, certification |

### 3.2 Layer 0: Transparent API Proxy

```bash
# Option A: CLI wrapper
atlast run python my_agent.py

# Option B: Environment variable
export OPENAI_BASE_URL=https://proxy.atlast.io
python my_agent.py
```

The proxy intercepts all LLM API calls (OpenAI, Anthropic, etc.), records request/response pairs, and forwards them unchanged. Zero code modification required.

**Captured:** prompts, responses, model name, token counts, latency, timestamps.
**Not captured:** tool call internals, reasoning, custom metadata.

### 3.3 Layer 1: SDK Integration

```python
from atlast_ecp import wrap
from openai import OpenAI

client = wrap(OpenAI())

# All calls automatically recorded — including streaming
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Analyze this data"}],
    stream=True
)
for chunk in response:
    print(chunk)  # Chunks arrive at normal speed
# After stream ends: full response recorded in background
```

**Additional SDK features:**
- `@track` decorator for custom function recording
- Automatic batch upload to ATLAST server
- Webhook notifications on batch completion
- HMAC-SHA256 signed payloads

### 3.4 Layer 2: Framework Adapters

```python
# LangChain
from atlast_ecp.adapters.langchain import ATLASTCallbackHandler
chain = LLMChain(llm=llm, callbacks=[ATLASTCallbackHandler()])

# CrewAI
from atlast_ecp.adapters.crewai import ATLASTCrewCallback
crew = Crew(agents=[...], callbacks=[ATLASTCrewCallback()])

# AutoGen
from atlast_ecp.adapters.autogen import ATLASTAutoGenPlugin
autogen.register_plugin(ATLASTAutoGenPlugin())
```

Framework adapters capture framework-specific events: agent delegation, tool routing, memory access, and inter-agent communication.

---

## 4. Verification Architecture

### 4.1 Three-Level Verification

```
Level 1: Merkle Proof (instant, local)
  "Do these records match the claimed batch root?"
  → Recompute Merkle tree from record hashes
  → Compare against stored merkle_root

Level 2: Server Attestation (API call)
  "Does the server confirm this batch exists?"
  → GET /v1/verify/{attestation_uid}
  → Returns batch metadata + on-chain reference

Level 3: On-Chain Verification (trustless)
  "Is the Merkle root permanently recorded on-chain?"
  → Query EAS contract on Base
  → Compare on-chain data with server response
```

### 4.2 Merkle Tree Implementation

ATLAST uses a standard binary Merkle tree with the following specification:

- **Hash function:** SHA-256
- **Leaf format:** `sha256:` prefix + hex digest
- **Odd-layer handling:** Duplicate last element
- **Ordering:** Insertion order (not sorted)
- **Canonical across implementations:** Python SDK, TypeScript SDK, and Server produce identical roots for identical inputs (verified in CI)

### 4.3 Independent Audit

Any third party can verify an evidence chain:

1. Obtain the ECP records (from agent operator or ATLAST server)
2. Recompute record hashes from canonical JSON
3. Rebuild Merkle tree → compare root against on-chain anchor
4. Verify hash chain continuity (each record references previous)
5. Check timestamps for plausibility

No trust in the ATLAST server is required — the chain is self-verifying.

---

## 5. Performance & Overhead

### 5.1 Benchmark Results

Test conditions: 100 iterations, OpenAI API calls, Python 3.12, measured on Apple M-series.

| Metric | Without ATLAST | With ATLAST | Overhead |
|--------|----------------|-------------|----------|
| Avg latency | 141.37ms | 142.15ms | +0.78ms (0.55%) |
| Max latency | 175.24ms | 175.64ms | +0.40ms |
| P99 latency | 168.1ms | 168.9ms | +0.80ms |

### 5.2 Overhead Breakdown

| Component | Time | Notes |
|-----------|------|-------|
| Function interception | ~0.01ms | Python monkey-patch |
| Record construction | ~0.15ms | JSON serialization |
| SHA-256 hashing | ~0.02ms | Single record |
| Background queue push | ~0.10ms | Thread-safe queue |
| Batch upload (async) | 0ms* | Background thread, non-blocking |

*Batch upload occurs asynchronously and does not contribute to per-call latency.

### 5.3 Fail-Open Guarantee

Every recording operation is wrapped in try/except:
```python
try:
    record_async(...)  # Background thread
except Exception:
    pass  # Agent continues normally
```

This design ensures that SDK bugs, network failures, or server outages **never** affect agent operations.

---

## 6. Security Model

### 6.1 Threat Model

| Threat | Mitigation |
|--------|------------|
| Record tampering | SHA-256 hash chain + blockchain anchor |
| Replay attacks | Unique record_id + timestamp + chain continuity |
| Man-in-the-middle | TLS 1.3 for all API communication |
| Denial of service | Rate limiting (per-IP, per-agent) |
| Fake evidence injection | HMAC-SHA256 webhook signing + agent key authentication |
| Evidence omission | Chain completeness verification (gap detection) |

### 6.2 Cryptographic Primitives

- **Hashing:** SHA-256 (FIPS 180-4)
- **Signatures:** HMAC-SHA256 for webhooks, Ed25519 for agent identity (Phase 3)
- **TLS:** 1.3 minimum, Let's Encrypt certificates
- **Token comparison:** Constant-time (`secrets.compare_digest`)

### 6.3 Anti-Abuse (Phase 6+)

- Per-IP agent registration limits
- Per-agent batch frequency caps
- Anomaly detection for suspicious patterns
- Trust score anti-gaming mechanisms
- Open-source self-deployment as natural abuse prevention

---

## 7. Cost Analysis

### 7.1 Three-Tier Cost Model

| Tier | Scope | Cost to User | Cost to Operator |
|------|-------|-------------|-----------------|
| L1: Local | SDK recording | Free | $0 |
| L2: Server | Batch upload + storage | Free | ~$0.001/batch |
| L3: Chain | Blockchain anchoring | Free | ~$0.002/super-batch |

### 7.2 Scaling Projections

| Scale | Monthly Cost (Operator) |
|-------|------------------------|
| 100 agents | ~$15 |
| 1,000 agents | ~$100 |
| 10,000 agents | ~$600 |
| 100,000 agents | ~$3,000-10,000 |

Users pay $0 at every tier. Open-source deployment allows organizations to run their own infrastructure at raw cloud costs.

---

## 8. Compliance Mapping

### 8.1 EU AI Act Alignment

| Requirement | ATLAST Coverage |
|-------------|----------------|
| Art. 14 — Human Oversight | ECP records enable post-hoc review of all agent decisions |
| Art. 52 — Transparency | Evidence chains document agent behavior transparently |
| Art. 53 — GPAI Documentation | ECP captures operational evidence beyond training docs |
| Art. 9 — Risk Management | Continuous evidence collection supports ongoing risk assessment |

### 8.2 ISO 42001 (AI Management Systems)

ECP evidence chains provide artifacts for:
- **Clause 6.1:** Risk assessment evidence
- **Clause 8.2:** Operational control records
- **Clause 9.1:** Monitoring and measurement data
- **Clause 10.2:** Nonconformity and corrective action audit trails

---

## 9. Roadmap

| Phase | Timeline | Deliverables |
|-------|----------|-------------|
| 1-4 | Complete | ECP Spec, Server, Python SDK, TS SDK |
| 5 | Complete | Framework Adapters, CI/CD, 500+ tests |
| 6 | Current | Whitepaper, IETF/W3C prep, anti-abuse |
| 7 | Q3 2026 | Public launch, mainnet anchoring |
| 8 | Q4 2026 | AIP + ASP + ACP sub-protocols |
| 9 | 2027 | EU AI Act compliance toolkit |

---

## 10. Conclusion

ATLAST Protocol provides the missing trust infrastructure for the AI agent economy. By combining lightweight evidence recording (< 1ms overhead), cryptographic integrity (SHA-256 + blockchain), and zero-friction adoption (single command to start), ATLAST makes agent accountability practical rather than theoretical.

The protocol is fully open-source, free for users, and designed as an open standard. We invite the community to contribute to the specification, build integrations, and help establish evidence chains as the foundation of trustworthy AI agent operations.

> *"At last, trust for the Agent economy."*

---

## References

1. European Parliament. *Regulation (EU) 2024/1689 — AI Act.* 2024.
2. Ethereum Attestation Service. *EAS Protocol Specification.* https://attest.sh
3. W3C. *Decentralized Identifiers (DIDs) v1.0.* 2022.
4. W3C. *Verifiable Credentials Data Model v2.0.* 2024.
5. Merkle, R. C. *A Digital Signature Based on a Conventional Encryption Function.* CRYPTO 1987.
6. NIST. *FIPS 180-4: Secure Hash Standard (SHS).* 2015.
7. ISO/IEC 42001:2023. *Artificial Intelligence — Management System.*
8. Anthropic. *Claude Model Card.* 2024.
9. OpenAI. *GPT-4 System Card.* 2024.
10. LangChain. *LangChain Framework Documentation.* 2024.
