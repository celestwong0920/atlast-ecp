# ECP × EU AI Act Mapping

> The EU AI Act takes effect in 2027. ECP covers key requirements today.

## Key Articles

### Article 9 — Risk Management System

**Requirement**: "Establish, implement, document and maintain a risk management system... continuously throughout the lifetime of the AI system."

**ECP Mapping**:
| Requirement | ECP Feature | Level | Status |
|------------|------------|-------|--------|
| Continuous monitoring | `meta.flags[]` auto-detection | L2 | ✅ Full |
| Risk identification | `error`, `high_latency`, `hedged` flags | L2 | ✅ Full |
| Residual risk documentation | `atlast insights` reports | L2 | ✅ Full |
| Monitoring measures | `atlast insights --json` for integration | L2 | ✅ Full |

### Article 12 — Record-Keeping (Logging)

**Requirement**: "High-risk AI systems shall technically allow for the automatic recording of events (logs)."

**ECP Mapping**:
| Requirement | ECP Feature | Level | Status |
|------------|------------|-------|--------|
| Automatic event recording | `record()` / `record_minimal()` | L1 | ✅ Full |
| Traceability | `chain.prev` + `chain.hash` | L3 | ✅ Full |
| Duration of log storage | JSONL files, retention policy configurable | L1 | ✅ Full |
| Period of operation covered | `ts` timestamps on every record | L1 | ✅ Full |

### Article 14 — Human Oversight

**Requirement**: "Enable those to whom human oversight is assigned to... correctly interpret the system's output."

**ECP Mapping**:
| Requirement | ECP Feature | Level | Status |
|------------|------------|-------|--------|
| Interpret output | `action`, `meta.model`, `meta.latency_ms` | L2 | ✅ Full |
| Identify anomalies | `meta.flags`, `human_review` flag | L2 | ✅ Full |
| Override / stop | Not in scope (runtime control) | — | ❌ Gap |
| Agent identity | `agent` (DID) + `sig` (Ed25519) | L4 | ✅ Full |

### Article 52 — Transparency

**Requirement**: "AI systems intended to interact with natural persons are designed and developed in such a way that the natural person is informed they are interacting with an AI system."

**ECP Mapping**:
| Requirement | ECP Feature | Level | Status |
|------------|------------|-------|--------|
| Disclosure of AI interaction | Agent DID identifies AI actor | L4 | ✅ Full |
| Content provenance | `in_hash` / `out_hash` for verification | L1 | ✅ Full |
| Tamper detection | Hash chain + Merkle root | L3 | ✅ Full |

## Compliance Score

| Article | Coverage | Notes |
|---------|----------|-------|
| Art. 9 | 🟢 90% | Missing: runtime risk mitigation actions |
| Art. 12 | 🟢 95% | Full logging capability |
| Art. 14 | 🟡 70% | Missing: runtime override/stop mechanisms |
| Art. 52 | 🟢 85% | Missing: UI-level disclosure (not ECP's scope) |

## Gaps → Roadmap

- **Runtime control** (Art. 14 override): → ASP (Agent Safety Protocol), Phase 3
- **UI disclosure** (Art. 52): Application-level, not protocol-level
