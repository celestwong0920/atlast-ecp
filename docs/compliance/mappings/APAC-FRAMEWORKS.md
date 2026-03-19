# ECP × Asia-Pacific AI Governance Frameworks

## Singapore — Model AI Governance Framework (MAIGF)

| Principle | ECP Feature | Status |
|----------|------------|--------|
| Explainability | `action`, `meta.model`, structured records | 🟡 Partial |
| Transparency | Hash chain, agent DID | ✅ Full |
| Fairness | Not in scope (content-level) | ❌ Gap |
| Human oversight | `human_review` flag, audit trail | ✅ Full |
| Accountability | Agent DID + Ed25519 signatures | ✅ Full |
| Data governance | Hash-only design (PDPA compliant) | ✅ Full |

## Japan — AI Strategy / Social Principles of Human-Centric AI

| Principle | ECP Feature | Status |
|----------|------------|--------|
| Transparency | ECP records with timestamps + actions | ✅ Full |
| Controllability | Audit trail for human review | ✅ Full |
| Privacy | SHA-256 hash-only, content stays local | ✅ Full |
| Security | Chain integrity, Ed25519 signatures | ✅ Full |

## South Korea — National AI Ethics Standards

| Principle | ECP Feature | Status |
|----------|------------|--------|
| Transparency & explainability | Structured ECP records | 🟡 Partial |
| Safety | `meta.flags[]` anomaly detection | ✅ Full |
| Data protection | Hash-only privacy design | ✅ Full |

## Australia — AI Ethics Principles

| Principle | ECP Feature | Status |
|----------|------------|--------|
| Transparency | ECP records, agent identity | ✅ Full |
| Contestability | Audit trail enables dispute investigation | ✅ Full |
| Accountability | DID + chain integrity + blame trace | ✅ Full |
| Privacy protection | Hash-only design | ✅ Full |

## APAC Summary

APAC frameworks share common themes: transparency, privacy, and accountability. ECP's design — structured records, hash-only privacy, agent identity — aligns naturally with all of them. The key gap across all frameworks is **explainability** (requires model internals, not protocol-level).
