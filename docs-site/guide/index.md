# Introduction

**ATLAST Protocol** (Agent Trust Layer, Accountability Standards & Transactions) is the trust infrastructure for the AI agent economy.

## What Problem Does It Solve?

AI agents are increasingly autonomous — writing code, making decisions, managing workflows. But:

- **How do you know what an agent actually did?** Not what it claims, but what it provably did.
- **How do you verify an agent's work** without re-running everything?
- **How do you compare agents** objectively, based on evidence rather than marketing?

ATLAST Protocol answers all three questions with the **Evidence Chain Protocol (ECP)** — a cryptographic audit trail for every agent action.

## How It Works

```
Agent does work → ECP records input/output hashes → Links into chain → Signs with Ed25519
                                                                              ↓
                                                          Batch → Merkle Root → EAS on-chain
```

Think of it as a **dashcam for AI agents**: it doesn't judge what the agent does, but it proves exactly what happened.

## Three-Layer Integration

| Layer | Effort | How |
|-------|--------|-----|
| **Layer 0** | Zero code | `atlast run python my_agent.py` — transparent proxy |
| **Layer 1** | 5 lines | `from atlast_ecp import wrap` — SDK wrapper |
| **Layer 2** | 10-20 lines | LangChain / CrewAI / AutoGen adapters |

## Key Properties

- **Privacy**: Content never leaves your device. Only SHA-256 hashes are transmitted.
- **Tamper-proof**: Chain hashes + Ed25519 signatures. Modifying any record breaks the chain.
- **Verifiable**: Anyone can verify a record's authenticity without the original content.
- **Fail-Open**: Recording failures never affect agent operation.
- **Open Standard**: MIT license, designed for ecosystem adoption.
