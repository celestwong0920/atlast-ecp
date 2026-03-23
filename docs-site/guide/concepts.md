# Core Concepts

## ECP Record

The fundamental unit of evidence. Each record captures one agent action:

```json
{
  "id": "rec_abc123",
  "ts": 1711180800000,
  "agent": "did:ecp:6cda81f6...",
  "step": {
    "type": "llm_call",
    "in_hash": "sha256:64ec88ca...",
    "out_hash": "sha256:8328c36d...",
    "latency_ms": 1200,
    "model": "gpt-4",
    "flags": []
  },
  "chain": {
    "prev": "sha256:previous_record_hash",
    "hash": "sha256:this_record_hash"
  },
  "sig": "ed25519:signature_hex"
}
```

Key properties:
- **`in_hash` / `out_hash`**: SHA-256 of input/output content. Content stays local.
- **`chain.prev`**: Links to previous record — forms an immutable chain.
- **`chain.hash`**: Deterministic hash of the entire record (canonical JSON).
- **`sig`**: Ed25519 signature proving the agent created this record.

## Evidence Chain

Records are linked via `chain.prev`, forming a chain like blockchain blocks:

```
[Record 1] → [Record 2] → [Record 3] → ...
  chain.prev    chain.prev    chain.prev
  = "genesis"   = hash(R1)    = hash(R2)
```

Modifying any record breaks all subsequent chain hashes — **tampering is instantly detectable**.

## Content Vault

Original input/output content is stored locally in `~/.ecp/vault/`:

```bash
atlast inspect rec_abc123
# Shows: record + original content + hash verification
```

Content **never leaves your device** unless you explicitly share it via Proof Package.

## Merkle Batch

Records are batched hourly. A Merkle tree is computed over all record hashes:

```
        Merkle Root
       /           \
    Hash(A+B)    Hash(C+D)
    /     \      /     \
  Rec A  Rec B  Rec C  Rec D
```

The Merkle root is:
1. Signed with the agent's Ed25519 key
2. Uploaded to the ATLAST server
3. Anchored on-chain via EAS (Ethereum Attestation Service)

## Trust Signals

8 behavioral flags are automatically detected:

| Flag | Meaning |
|------|---------|
| `retried` | Same input was sent multiple times |
| `hedged` | Multiple models called for same input |
| `incomplete` | Response was cut off or empty |
| `high_latency` | Response took >5 seconds |
| `error` | An error occurred during execution |
| `human_review` | Flagged for human review |
| `a2a_delegated` | Delegated to another agent |
| `speed_anomaly` | Suspiciously fast response |

## Agent Identity (DID)

Each agent gets a Decentralized Identifier:

```
did:ecp:6cda81f65ae50c8b148ab57d3e3743da
```

Backed by an Ed25519 keypair stored in `~/.ecp/identity/`. The DID is deterministic — derived from the public key hash.

## Proof Package

A self-contained evidence bundle for sharing with auditors:

```bash
atlast proof --include-content --output evidence.tar.gz
```

Contains: records + content + public key + verification script. Verifiers need zero setup.
