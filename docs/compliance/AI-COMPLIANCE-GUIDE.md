# ECP Global AI Compliance Guide

> ECP is not a tool for one regulation. It is the infrastructure for all of them.

## Executive Summary

As AI agents become autonomous economic actors, governments worldwide are demanding the same thing: **prove what your AI did, how it decided, and that it can be audited.**

ECP (Evidence Chain Protocol) provides five compliance capabilities that map to every major AI regulation:

| Capability | What ECP Does | Who Requires It |
|-----------|---------------|-----------------|
| **Audit Trail** | Immutable hash-chain of every agent action | EU AI Act, China GenAI, NIST AI RMF, ISO 42001 |
| **Privacy Protection** | Only SHA-256 hashes transmitted, content stays local | GDPR, China PIPL, APAC frameworks |
| **Behavioral Transparency** | Structured records: input/output/action/timestamp | EU AI Act Art. 52, NIST Transparency |
| **Anomaly Detection** | Automated flags: error, high_latency, hedged, retry | EU AI Act Art. 9, NIST Risk Management |
| **Identity Verification** | DID-based agent identity with Ed25519 signatures | EU AI Act Art. 14, ISO 42001 |

**Key insight**: These are not five features — they are one protocol. ECP satisfies them all because "verifiable agent behavior" is a universal requirement, not a regional one.

---

## 1. Five Compliance Capabilities of ECP

### 1.1 Audit Trail (ECP Levels 1-3)

**What**: Every agent action produces an ECP record with `id`, `ts`, `agent`, `action`, `in_hash`, `out_hash`. Records are chained via `chain.prev` + `chain.hash` (Level 3), making tampering detectable.

**ECP Fields**: `id`, `ts`, `agent`, `action`, `chain.prev`, `chain.hash`

**Regulations requiring this**:
- EU AI Act Article 12: "Logging capabilities"
- China GenAI Article 17: "Retain records of training data, algorithms, and generated content"
- NIST AI RMF MAP 1.5: "Maintain documentation of AI lifecycle"
- ISO/IEC 42001: "Establish and maintain records of AI system operations"

### 1.2 Privacy Protection (By Design)

**What**: ECP records contain only SHA-256 hashes of input/output. Raw content never leaves the device. Upload is opt-in via `atlast push`.

**ECP Fields**: `in_hash` (sha256), `out_hash` (sha256) — never raw content

**Regulations requiring this**:
- GDPR Article 25: "Data protection by design and by default"
- China PIPL Article 7: "Principle of minimum necessary personal information"
- Singapore PDPA: Data minimization principle
- All frameworks: Privacy-by-design is universally required

### 1.3 Behavioral Transparency (ECP Levels 1-2)

**What**: Every record captures what action was taken (`action`), when (`ts`), by whom (`agent`), with what model (`meta.model`), how long it took (`meta.latency_ms`), and how many tokens (`meta.tokens_in/out`).

**ECP Fields**: `action`, `meta.model`, `meta.latency_ms`, `meta.tokens_in`, `meta.tokens_out`

**Regulations requiring this**:
- EU AI Act Article 52: "Transparency obligations for certain AI systems"
- China GenAI Article 4: "Improve transparency of generative AI services"
- NIST AI RMF GOVERN 1.4: "Transparency processes"
- ISO/IEC 42001 A.6.2.6: "Transparent communication"

### 1.4 Anomaly Detection (ECP Level 2)

**What**: ECP automatically detects behavioral flags: `error`, `high_latency`, `hedged`, `retried`, `incomplete`, `human_review`. These flags enable risk monitoring without content inspection.

**ECP Fields**: `meta.flags[]`

**Regulations requiring this**:
- EU AI Act Article 9: "Risk management system... continuously monitor"
- NIST AI RMF MEASURE 2.6: "Monitor for anomalous behavior"
- ISO/IEC 42001 A.8.4: "System monitoring"
- China GenAI Article 14: "Monitoring and evaluation mechanisms"

### 1.5 Identity Verification (ECP Levels 4-5)

**What**: Agents have DID-based identities with Ed25519 keypairs. Records can be signed (`sig` field). Signatures enable: (a) proving who recorded what, (b) detecting impersonation, (c) non-repudiation.

**ECP Fields**: `agent` (DID), `sig` (Ed25519), `integrity.agent_signature`

**Regulations requiring this**:
- EU AI Act Article 14: "Human oversight... ability to correctly interpret the system's output"
- ISO/IEC 42001 A.6.1.3: "Roles and responsibilities for AI"
- NIST AI RMF GOVERN 1.1: "Accountability structures"

---

## 2. Regulation-Specific Mappings

Detailed mappings are available per regulation:

| Regulation | Region | Status | Mapping |
|-----------|--------|--------|---------|
| [EU AI Act](mappings/EU-AI-ACT.md) | EU | Effective 2027 | Detailed (Articles 9, 12, 14, 52) |
| [China AI Regulations](mappings/CHINA-AI-REGULATIONS.md) | China | Effective 2023-2024 | Summary (GenAI Measures, PIPL) |
| [US NIST AI RMF](mappings/US-NIST-AI-RMF.md) | US | Framework (voluntary) | Summary (MAP, MEASURE, GOVERN) |
| [APAC Frameworks](mappings/APAC-FRAMEWORKS.md) | Asia-Pacific | Various | Summary (Singapore, Japan, Korea, Australia) |

---

## 3. Practical Scenarios

### Scenario 1: Audit Log Export (EU + China)

Both EU AI Act and China GenAI require retaining operational logs. ECP records are stored as JSONL files — standard format, easy to export.

```bash
# Export all agent records for audit
atlast export --format jsonl --output audit_2026.jsonl

# Verify chain integrity before submission
atlast verify --chain audit_2026.jsonl

# For multi-agent workflows
atlast verify --a2a agent_a.jsonl agent_b.jsonl agent_c.jsonl
```

### Scenario 2: Anomaly Detection (Global)

Every regulation requires monitoring. ECP flags detect anomalies automatically:

```bash
# Run local insights
atlast insights

# Output:
#   ⚠️ Error rate: 12% (above 5% threshold)
#   ⚠️ Agent "writer" has 8 high_latency flags in 24h
#   ⚠️ 3 hedged responses detected (agent uncertain)
```

### Scenario 3: Agent Identity Traceability (Multi-Regulation)

When regulators ask "which AI made this decision?":

```bash
# Initialize agent with verifiable identity
atlast init
# → Created DID: did:ecp:z6MkrT...
# → Keypair stored at ~/.atlast/identity.json

# All subsequent records are signed
atlast run python my_agent.py
# → Records include: "agent": "did:ecp:z6MkrT...", "sig": "ed25519:..."
```

---

## 4. Gap Analysis

ECP is not a complete compliance solution. Here is what it covers and what it does not:

| Requirement | ECP Status | Gap | Roadmap |
|------------|-----------|-----|---------|
| Action logging | ✅ Full | — | — |
| Content privacy | ✅ Full | — | — |
| Behavioral flags | ✅ Full | — | — |
| Chain integrity | ✅ Full | — | — |
| Agent identity (DID) | ✅ Full | — | — |
| Multi-agent verification | ✅ Full | — | — |
| Blockchain anchoring | ✅ Optional | Requires EAS setup | Available now (Level 5) |
| Access control / RBAC | ❌ Not covered | Server-level concern | AIP (Phase 3) |
| Safety guardrails | ❌ Not covered | Content-level concern | ASP (Phase 3) |
| Certification / attestation | 🟡 Partial | Basic certs available | ACP (Phase 3) |
| Data retention policies | ❌ Not covered | Org-level policy | Out of scope |
| Explainability / XAI | ❌ Not covered | Requires model internals | Out of scope |

### Upcoming Sub-Protocols

| Protocol | Purpose | Timeline |
|----------|---------|----------|
| **AIP** (Agent Identity Protocol) | RBAC, delegation, org hierarchy | Phase 3 |
| **ASP** (Agent Safety Protocol) | Safety guardrails, content filtering | Phase 3 |
| **ACP** (Agent Certification Protocol) | Third-party attestation, compliance certs | Phase 3 |

---

## 5. Why ECP, Not [X]?

| Tool | What It Does | What ECP Does Differently |
|------|-------------|--------------------------|
| LangSmith | Developer debugging / tracing | ECP = compliance audit, not debugging. Hash-only, no raw content. |
| Arize AI | ML model monitoring | ECP = protocol standard, not SaaS. Open-source, self-hostable. |
| OpenTelemetry | General observability | ECP = agent-specific evidence chain. OTel has no chain integrity or multi-agent verification. |
| Internal logging | Custom audit logs | ECP = standardized, cross-platform, verifiable. Your logs are not mine. ECP is universal. |

---

*ECP Global AI Compliance Guide v1.0 — ATLAST Protocol — 2026*
