# ECP × US NIST AI Risk Management Framework Mapping

## About NIST AI RMF

The NIST AI RMF (2023) is a voluntary framework for managing AI risks. While not legally binding, it is widely adopted by US enterprises and often referenced in procurement requirements.

## Core Functions → ECP

### GOVERN (Governance)

| Requirement | ECP Feature | Status |
|------------|------------|--------|
| GOVERN 1.1: Accountability structures | Agent DID + Ed25519 signatures | ✅ Full |
| GOVERN 1.4: Transparency processes | `action`, `meta.*` structured records | ✅ Full |
| GOVERN 1.7: Processes for third-party AI | A2A multi-agent verification | ✅ Full |

### MAP (Context)

| Requirement | ECP Feature | Status |
|------------|------------|--------|
| MAP 1.5: Lifecycle documentation | JSONL audit trail from init to decommission | ✅ Full |
| MAP 3.5: Third-party risk assessment | A2A handoff verification + blame trace | ✅ Full |

### MEASURE (Assessment)

| Requirement | ECP Feature | Status |
|------------|------------|--------|
| MEASURE 2.6: Anomalous behavior monitoring | `meta.flags[]` automated detection | ✅ Full |
| MEASURE 2.8: Bias/fairness testing | ❌ Not in scope | Gap |
| MEASURE 4.1: Measurement approaches | `atlast insights` + trust signals | ✅ Full |

### MANAGE (Response)

| Requirement | ECP Feature | Status |
|------------|------------|--------|
| MANAGE 1.3: Risk response documentation | ECP chain as evidence for response actions | ✅ Full |
| MANAGE 4.1: Incident response | Blame trace for root cause analysis | ✅ Full |

## Key Value for US Market

NIST AI RMF is becoming the de facto standard for AI procurement in US government and enterprise. ECP's structured, verifiable records provide ready-made evidence for RMF compliance assessments.
