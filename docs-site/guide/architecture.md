# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User's Device                         │
│                                                         │
│  ┌─────────┐    ┌──────────┐    ┌────────────────────┐ │
│  │  Agent   │───>│ ATLAST   │───>│  ~/.ecp/           │ │
│  │ (GPT-4,  │    │   SDK    │    │  ├── records/      │ │
│  │  Claude) │    │  wrap()  │    │  ├── vault/        │ │
│  └─────────┘    └──────────┘    │  ├── identity/     │ │
│                       │          │  └── batch_state   │ │
│                       │          └────────────────────┘ │
│                       │ Merkle Root + Signature          │
└───────────────────────│─────────────────────────────────┘
                        ▼
              ┌──────────────────┐
              │  ATLAST Server   │
              │  api.weba0.com   │
              │                  │
              │  ┌────────────┐  │
              │  │ PostgreSQL │  │
              │  └────────────┘  │
              └────────│─────────┘
                       ▼
              ┌──────────────────┐
              │   Base (EAS)     │
              │   On-chain       │
              │   Anchoring      │
              └──────────────────┘
```

## Data Flow

1. **Agent calls LLM** → SDK intercepts (wrap/proxy)
2. **SDK creates ECP record** → hashes input/output, links to chain, signs
3. **Record saved locally** → `~/.ecp/records/` (JSONL) + `~/.ecp/vault/` (content)
4. **Hourly batch** → Merkle tree computed, root signed, uploaded to server
5. **Server anchors** → Merkle root written to EAS on Base blockchain
6. **Webhook** → Notifies integrated platforms (e.g., LLaChat)

## What Stays Local vs. What's Transmitted

| Data | Location | Transmitted? |
|------|----------|-------------|
| Original input/output | `~/.ecp/vault/` | ❌ Never |
| Record hashes | `~/.ecp/records/` | ✅ Hash only |
| Ed25519 private key | `~/.ecp/identity/` | ❌ Never |
| Merkle root | Server + chain | ✅ Hash only |
| Signature | Server + chain | ✅ |

## Fail-Open Design

Every component follows fail-open principle:

- SDK recording fails → agent continues normally
- Batch upload fails → queued for retry (exponential backoff)
- Server down → records accumulate locally
- EAS anchoring fails → retried next cron cycle

**Recording failures never affect agent operation.**
