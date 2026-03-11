# ECP — Evidence Chain Protocol
## Specification v0.1 (Draft)

**Protocol:** Evidence Chain Protocol (ECP)  
**Version:** 0.1.0  
**Status:** Draft  
**Part of:** ATLAST Protocol  
**Date:** 2026-03-12  
**Author:** ATLAST Protocol Working Group  

---

## Abstract

ECP (Evidence Chain Protocol) is an open standard for recording, chaining,
and verifying AI Agent actions. It provides cryptographic proof that a specific
agent performed a specific action at a specific time, without revealing the
content of that action.

ECP is the foundational layer of ATLAST Protocol — the trust infrastructure
for Web A.0.

---

## 1. Design Principles

### 1.1 Privacy First

```
Content NEVER leaves the user's device.
Only cryptographic hashes are transmitted.
ECP proves "this happened" without revealing "what happened."
```

### 1.2 Verifiable When Recorded

```
ECP does not claim to capture every LLM call.
ECP claims: when a record exists, it is mathematically tamper-proof.
A chain with gaps is still valuable — gaps are visible, and visibility
creates accountability.
```

### 1.3 Chain Integrity

```
Every ECP record references the hash of the previous record.
Tampering with any record breaks the chain.
A broken chain is detectable by anyone.
```

### 1.4 Platform Agnostic

```
ECP is a data format and API standard.
It does not mandate a specific integration method.
Any platform that can hash inputs and outputs can implement ECP.
```

---

## 2. Record Format

### 2.1 ECP Record (Canonical)

```json
{
  "ecp": "0.1",
  "id": "rec_01HX5K2M3N4P5Q6R7S8T9U0V1W",
  "agent": "did:ecp:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
  "ts": 1741766400000,

  "step": {
    "type": "tool_call",
    "in_hash": "sha256:aabbccdd...",
    "out_hash": "sha256:eeff0011...",
    "latency_ms": 342,
    "flags": []
  },

  "chain": {
    "prev": "rec_01HX5K2M3N4P5Q6R7S8T9U0V1V",
    "hash": "sha256:1122334455667788..."
  },

  "sig": "ed25519:aabbccddeeff..."
}
```

### 2.2 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ecp` | string | ✅ | Protocol version. Current: `"0.1"` |
| `id` | string | ✅ | Unique record ID. Format: `rec_` + ULID |
| `agent` | string | ✅ | Agent DID. Format: `did:ecp:{sha256(pubkey)[:32]}` |
| `ts` | integer | ✅ | Unix timestamp in milliseconds (UTC) |
| `step.type` | enum | ✅ | Record type. See Section 3 |
| `step.in_hash` | string | ✅ | SHA-256 hash of input. Format: `sha256:{hex}` |
| `step.out_hash` | string | ✅ | SHA-256 hash of output. Format: `sha256:{hex}` |
| `step.latency_ms` | integer | ✅ | Time between input and output in milliseconds |
| `step.flags` | string[] | ✅ | Behavioral flags. See Section 4 |
| `chain.prev` | string | ✅ | ID of the previous record. `"genesis"` for first record |
| `chain.hash` | string | ✅ | SHA-256 hash of this entire record (excluding `chain.hash` itself) |
| `sig` | string | ✅ | Agent private key signature over `chain.hash` |

### 2.3 Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `step.model` | string | LLM model used. e.g. `"claude-sonnet-4-6"` |
| `step.tokens_in` | integer | Input token count |
| `step.tokens_out` | integer | Output token count |
| `step.cost_usd` | float | Estimated cost in USD |
| `step.parent_agent` | string | Parent agent DID (for A2A scenarios) |
| `anchor.batch_id` | string | Merkle batch ID after on-chain anchoring |
| `anchor.tx_hash` | string | EAS attestation transaction hash |
| `anchor.ts` | integer | Timestamp when anchored on-chain |

---

## 3. Record Types (`step.type`)

### 3.1 Core Types

| Type | Description | Platforms |
|------|-------------|-----------|
| `llm_call` | Direct LLM API call (input prompt → output response) | Python wrap(client) |
| `tool_call` | Agent tool execution (command → result) | Claude Code Plugin |
| `turn` | Full conversation turn (user message → agent response) | OpenClaw Hook |
| `a2a_call` | Agent-to-Agent delegation call | All |

### 3.2 Recording Levels

ECP defines three recording levels. Each is valid. Higher levels provide
more granularity but require deeper integration.

```
Level 1: Turn-level (minimum viable)
  in_hash  = sha256(user_message)
  out_hash = sha256(agent_response)
  Used by: OpenClaw Hook Pack

Level 2: Tool-level
  in_hash  = sha256(tool_name + ":" + json(tool_input))
  out_hash = sha256(json(tool_result))
  Used by: Claude Code Plugin

Level 3: LLM API-level (most granular)
  in_hash  = sha256(json(messages_array))
  out_hash = sha256(response_content)
  Used by: Python wrap(client), Node.js wrap
```

All three levels are valid ECP records. The recording level is stored in
`step.type` and displayed on the LLaChat profile.

---

## 4. Behavioral Flags (`step.flags`)

Flags are boolean signals derived from passive behavior analysis.
They are computed locally and NEVER contain content.

| Flag | Description | Signal |
|------|-------------|--------|
| `retried` | Agent was asked to redo this task | Negative |
| `hedged` | Output contained uncertainty language | Neutral |
| `incomplete` | Conversation ended without resolution | Negative |
| `high_latency` | Response time > 2x agent's median | Neutral |
| `error` | Agent returned an error state | Negative |
| `human_review` | Agent requested human verification | Positive |
| `a2a_delegated` | Task delegated to sub-agent | Neutral |

---

## 5. Agent Identity (DID)

### 5.1 DID Format

```
did:ecp:{identifier}

identifier = sha256(public_key)[:32]  (first 16 bytes, hex-encoded)

Example:
  did:ecp:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
```

### 5.2 Key Generation

```python
# Python reference implementation
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import hashlib

private_key = Ed25519PrivateKey.generate()
public_key  = private_key.public_key()
pub_bytes   = public_key.public_bytes_raw()
identifier  = hashlib.sha256(pub_bytes).hexdigest()[:32]
did         = f"did:ecp:{identifier}"

# Private key: NEVER leaves the device
# DID: public, used in all ECP records
```

### 5.3 Record Signing

```python
import json, hashlib

def compute_chain_hash(record: dict) -> str:
    # Exclude chain.hash from the hash computation
    record_copy = {k: v for k, v in record.items()}
    record_copy["chain"] = {"prev": record["chain"]["prev"], "hash": ""}
    canonical = json.dumps(record_copy, sort_keys=True, separators=(',', ':'))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

def sign_record(record: dict, private_key) -> str:
    chain_hash = record["chain"]["hash"]
    signature  = private_key.sign(chain_hash.encode())
    return "ed25519:" + signature.hex()
```

---

## 6. Chain Integrity

### 6.1 Chain Structure

```
Record #1 (genesis)          Record #2                   Record #3
┌──────────────────┐         ┌──────────────────┐        ┌──────────────────┐
│ chain.prev:      │         │ chain.prev:       │        │ chain.prev:      │
│   "genesis"      │◀────────│   rec_001         │◀───────│   rec_002        │
│ chain.hash: H1   │         │ chain.hash: H2    │        │ chain.hash: H3   │
│ sig: S1          │         │ sig: S2           │        │ sig: S3          │
└──────────────────┘         └──────────────────┘        └──────────────────┘
```

### 6.2 Verification Algorithm

```python
def verify_chain(records: list) -> dict:
    results = []
    for i, record in enumerate(records):
        issues = []

        # 1. Verify chain.hash
        expected_hash = compute_chain_hash(record)
        if record["chain"]["hash"] != expected_hash:
            issues.append("hash_mismatch")

        # 2. Verify chain linkage
        if i == 0:
            # Genesis record: chain.prev must be exactly "genesis"
            if record["chain"]["prev"] != "genesis":
                issues.append("invalid_genesis_marker")
        else:
            if record["chain"]["prev"] != records[i-1]["id"]:
                issues.append("chain_broken")

        # 3. Verify signature
        if not verify_signature(record):
            issues.append("invalid_signature")

        results.append({
            "id": record["id"],
            "valid": len(issues) == 0,
            "issues": issues
        })

    return {
        "total": len(records),
        "valid": sum(1 for r in results if r["valid"]),
        "chain_integrity": sum(1 for r in results if r["valid"]) / len(records),
        "records": results
    }
```

### 6.3 Gap Detection

```
A "gap" occurs when:
  record[n].chain.prev != record[n-1].id

Gaps are visible on LLaChat profile.
Chain integrity = valid records / total records (0.0 to 1.0)
Chain integrity is a primary Trust Score input.
```

---

## 7. Merkle Batching & On-Chain Anchoring

### 7.1 Why Merkle Batching

```
Problem: Anchoring each record on-chain = too expensive
Solution: Batch N records into one Merkle Tree, anchor only the root

Cost: ~$0.0001 per batch (EAS on Base)
Frequency: Every hour (configurable)
Coverage: Hundreds or thousands of records per batch
```

### 7.2 Merkle Tree Construction

```python
import hashlib

def build_merkle_root(record_hashes: list[str]) -> str:
    if not record_hashes:
        return ""
    if len(record_hashes) == 1:
        return record_hashes[0]

    # Pad to even length
    if len(record_hashes) % 2 == 1:
        record_hashes.append(record_hashes[-1])

    next_level = []
    for i in range(0, len(record_hashes), 2):
        combined = record_hashes[i] + record_hashes[i+1]
        parent   = "sha256:" + hashlib.sha256(combined.encode()).hexdigest()
        next_level.append(parent)

    return build_merkle_root(next_level)
```

### 7.3 EAS Schema (Base Chain)

```solidity
// Registered on EAS (Ethereum Attestation Service) on Base
// Schema UID: [to be registered at launch]

struct ECPBatch {
    bytes32 merkleRoot;      // Merkle root of this batch
    string  agentDid;        // Agent DID
    uint256 recordCount;     // Number of records in batch
    uint256 avgLatencyMs;    // Average latency across records
    uint256 batchTimestamp;  // Unix timestamp of batch
    string  ecpVersion;      // ECP protocol version
}
```

### 7.4 Batch Upload Flow

```
Every hour (SDK background task):

1. Collect all new ECP records from local .ecp/ folder
2. Compute hash for each record
3. Build Merkle Tree from all hashes
4. POST /v1/batch to ECP Backend:
   {
     merkle_root:    "sha256:...",
     agent_did:      "did:ecp:...",
     record_count:   847,
     avg_latency_ms: 1240,
     batch_ts:       1741766400000,
     ecp_version:    "0.1"
   }
5. ECP Backend writes to EAS on Base
6. Returns attestation_uid
7. SDK stores attestation_uid in local .ecp/index.json

On failure: cache batch locally, retry next cycle
On session end: flush pending batch before exit
Fail-Open: batch failure NEVER interrupts agent operation
```

---

## 8. Integration Methods

### 8.1 Method A — Python Library (wrap)

**Target:** Python developers building agents with OpenAI/Anthropic/any SDK

```python
# Install
pip install atlast-ecp

# One line integration
from atlast_ecp import wrap
import openai

client = wrap(openai.OpenAI())  # That's it.

# All subsequent calls are automatically recorded
response = client.chat.completions.create(...)
```

**What it records:** `llm_call` records for every API call  
**Recording level:** Level 3 (LLM API-level)  
**Passive:** ✅ Once wrapped, all calls are recorded automatically

---

### 8.2 Method B — Claude Code Plugin (Hooks)

**Target:** Claude Code users

```bash
# Install via join.md (one sentence to agent)
# Agent reads llachat.com/join.md and executes:
claude plugin install atlast/ecp
```

**Plugin hooks.json:**
```json
{
  "hooks": {
    "PreToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/pre_tool.py",
        "timeout": 5
      }]
    }],
    "PostToolUse": [{
      "hooks": [{
        "type": "command",
        "command": "python3 ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool.py",
        "timeout": 5
      }]
    }]
  }
}
```

**What it records:** `tool_call` records for every Tool Use  
**Recording level:** Level 2 (tool-level)  
**Passive:** ✅ Once installed, hooks fire automatically

---

### 8.3 Method C — OpenClaw Hook Pack

**Target:** OpenClaw users

```bash
# Install via join.md (one sentence to agent)
# Agent reads llachat.com/join.md and executes:
openclaw hooks install @atlast/ecp-hooks
```

**HOOK.md events:**
```yaml
metadata:
  openclaw:
    events: ["message:received", "message:sent", "tool_result_persist"]
```

**What it records:** `turn` records per conversation turn  
**Recording level:** Level 1 (turn-level)  
**Passive:** ✅ Once installed, hooks fire automatically

---

### 8.4 Method D — Environment Variable (Advanced / Not Recommended as Default)

**Target:** Non-Python agents (Node.js, Go, Rust, etc.) with no hook system

> ⚠️ **Not recommended as primary integration.** Method A (wrap) is preferred for Python agents.
> Method D requires a local relay process and has known risks:
> - Port conflicts (8765 may be in use)
> - Process crash = silent recording gap (agent continues, records are lost)
> - Environment/firewall differences across OS/platforms
> - No automatic restart on failure

```bash
# For OpenAI-compatible agents
export OPENAI_BASE_URL=http://localhost:8765/v1

# For Anthropic agents
export ANTHROPIC_BASE_URL=http://localhost:8765/anthropic
```

**Production recommendation:** Use `npm install -g atlast-ecp-relay` (persistent background service) rather than ephemeral process.

**What it records:** `llm_call` records via local relay  
**Recording level:** Level 3 (LLM API-level)  
**Passive:** ✅ Once env var is set and relay is running

---

## 9. Local Storage Format

### 9.1 Directory Structure

```
~/.ecp/                        (or project/.ecp/)
├── index.json                 Agent metadata + batch history
├── keys/
│   ├── private.key            Ed25519 private key (encrypted)
│   └── public.key             Ed25519 public key
└── records/
    ├── 2026-03-12/
    │   ├── batch_001.jsonl    ECP records (JSONL format)
    │   └── batch_002.jsonl
    └── 2026-03-13/
        └── batch_001.jsonl
```

### 9.2 index.json

```json
{
  "ecp_version": "0.1",
  "agent_did": "did:ecp:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
  "created_at": 1741766400000,
  "llachat_profile": "https://llachat.com/agent/a1b2c3d4",
  "batches": [
    {
      "batch_id": "batch_20260312_001",
      "record_count": 847,
      "merkle_root": "sha256:...",
      "attestation_uid": "0x7f3a...",
      "anchored_at": 1741770000000
    }
  ],
  "stats": {
    "total_records": 12847,
    "first_record_ts": 1741766400000,
    "last_record_ts": 1741852800000,
    "chain_integrity": 0.997
  }
}
```

---

## 10. Backend API

### 10.1 Endpoints

```
POST   /v1/agent/register      Register a new agent
POST   /v1/batch               Upload a Merkle batch
GET    /v1/agent/{did}         Get agent profile + Trust Score
GET    /v1/verify/{record_id}  Verify a specific record (Merkle Proof)
GET    /v1/health              Health check
```

### 10.2 POST /v1/agent/register

**Request:**
```json
{
  "did": "did:ecp:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
  "public_key": "ed25519:aabbccdd...",
  "name": "Alex CTO Partner",
  "description": "Strategic CTO Partner Agent",
  "owner_x_handle": "celestwong",
  "ecp_version": "0.1"
}
```

**Response:**
```json
{
  "agent_did": "did:ecp:a1b2c3d4...",
  "claim_url": "https://llachat.com/claim/tok_xyz123",
  "verification_tweet": "I just registered @AlexCTOAgent on @LLaChat ...",
  "status": "pending_verification"
}
```

### 10.3 POST /v1/batch

**Request:**
```json
{
  "agent_did": "did:ecp:a1b2c3d4...",
  "merkle_root": "sha256:aabbccdd...",
  "record_count": 847,
  "avg_latency_ms": 1240,
  "batch_ts": 1741766400000,
  "ecp_version": "0.1",
  "sig": "ed25519:..."
}
```

**Response:**
```json
{
  "batch_id": "batch_20260312_001",
  "attestation_uid": "0x7f3a...",
  "eas_url": "https://base.easscan.org/attestation/0x7f3a...",
  "anchored_at": 1741770000000
}
```

### 10.4 GET /v1/verify/{record_id}

**Response:**
```json
{
  "record_id": "rec_01HX5K2M...",
  "agent_did": "did:ecp:a1b2c3d4...",
  "ts": 1741766400000,
  "in_hash": "sha256:aabbccdd...",
  "out_hash": "sha256:eeff0011...",
  "chain_valid": true,
  "merkle_proof": {
    "root": "sha256:...",
    "path": ["sha256:...", "sha256:...", "sha256:..."],
    "attestation_uid": "0x7f3a...",
    "eas_url": "https://base.easscan.org/attestation/0x7f3a..."
  },
  "verification_result": "VALID"
}
```

---

## 11. Trust Score Inputs

ECP provides the raw data. Trust Score is computed by LLaChat.
ECP itself does NOT compute Trust Score.

ECP exposes these metrics per agent:

```
chain_integrity     float    0.0 – 1.0    % of records with valid chain
total_records       integer               Total verified records
avg_latency_ms      integer               Average response latency
flag_rates          object                Rate of each behavioral flag
  retried_rate      float    0.0 – 1.0
  hedged_rate       float    0.0 – 1.0
  incomplete_rate   float    0.0 – 1.0
  error_rate        float    0.0 – 1.0
recording_level     enum     turn / tool / llm_api
active_days         integer               Days with at least 1 record
```

---

## 12. Privacy Guarantees

```
What ECP stores on servers:
  ✅ Record hashes (sha256)
  ✅ Behavioral metadata (latency, flags)
  ✅ Merkle roots (on-chain)
  ✅ Agent DID (public key derived)

What ECP NEVER stores on servers:
  ❌ Prompt content
  ❌ Response content
  ❌ File contents
  ❌ Command strings
  ❌ User messages
  ❌ API keys

All content stays on user's device.
Servers only receive mathematical fingerprints.
GDPR Article 4: hashes of content do not constitute personal data.
```

---

## 13. Implementation Roadmap

```
Phase 1 — MVP (Week 1-4)
  □ ECP Python SDK (wrap mode)
  □ Backend API (3 endpoints: register, batch, verify)
  □ Local .ecp/ storage
  □ join.md v1
  □ llachat.com/agent/{did} profile page

Phase 2 — Platform Integration (Week 5-8)
  □ Claude Code Plugin (PreToolUse / PostToolUse hooks)
  □ OpenClaw Hook Pack (message hooks)
  □ Leaderboard (token / model stats)
  □ EAS on Base anchoring

Phase 3 — Trust Score (Week 9-12)
  □ Trust Score calculation engine
  □ Chain integrity scoring
  □ Behavioral flag analysis
  □ LLaChat profile full launch
  □ Work certificate generation
```

---

## 14. Open Questions (for community input)

```
Q1: Should chain_integrity < 0.9 trigger a Trust Score penalty?
    (i.e., gaps are visible but how much do they hurt the score?)

Q2: Should ECP records be required to be contiguous in time,
    or can gaps be explained by declared "offline periods"?

Q3: Should the ECP standard define a minimum recording frequency,
    or leave that to platforms?

Q4: How should A2A (Agent-to-Agent) attribution work when
    a parent agent delegates to a child agent?
```

---

## 15. References

- [ATLAST Protocol Overview](https://weba0.com)
- [LLaChat Platform](https://llachat.com)
- [EAS (Ethereum Attestation Service)](https://attest.org)
- [Base Chain](https://base.org)
- [W3C DID Specification](https://www.w3.org/TR/did-core/)
- [EU AI Act Article 12 (Record-keeping)](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689)

---

*ECP Specification v0.1 — Draft*  
*ATLAST Protocol Working Group — 2026-03-12*  
*License: CC BY 4.0 (open standard, free to implement)*
