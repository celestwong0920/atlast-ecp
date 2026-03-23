# ECP Specification

The full Evidence Chain Protocol specification is maintained in the main repository:

📄 **[ECP-SPEC.md on GitHub](https://github.com/willau95/atlast-ecp/blob/main/ECP-SPEC.md)**

## Version

Current: **ECP-SPEC v2.1**

## Summary

ECP defines a 5-level progressive evidence model:

| Level | Name | What's Recorded | Integrity |
|-------|------|-----------------|-----------|
| 1 | Minimal | input/output hashes only | Hash |
| 2 | Standard | + model, latency, tokens, cost | Hash |
| 3 | Signed | + Ed25519 signature | Hash + Sig |
| 4 | Chained | + linked to previous record | Hash + Sig + Chain |
| 5 | Anchored | + Merkle root on-chain (EAS) | Hash + Sig + Chain + Blockchain |

## Data Format

### Record (Nested Format — Python SDK)
```json
{
  "ecp": "0.1",
  "id": "rec_xxx",
  "agent": "did:ecp:xxx",
  "ts": 1711180800000,
  "step": {
    "type": "llm_call",
    "in_hash": "sha256:...",
    "out_hash": "sha256:...",
    "latency_ms": 1200,
    "model": "gpt-4",
    "flags": []
  },
  "chain": { "prev": "sha256:...", "hash": "sha256:..." },
  "sig": "ed25519:..."
}
```

### Record (Flat Format — TypeScript SDK)
```json
{
  "id": "rec_xxx",
  "agent": "did:ecp:xxx",
  "ts": 1711180800000,
  "action": "llm_call",
  "in_hash": "sha256:...",
  "out_hash": "sha256:...",
  "latency_ms": 1200,
  "model": "gpt-4",
  "flags": [],
  "chain": { "prev": "sha256:...", "hash": "sha256:..." },
  "sig": "..."
}
```

Both formats are valid. Chain hash is computed over the canonical JSON of the record (with `chain.hash=""` and `sig=""`).

## Cross-SDK Hash Interoperability

Given identical JSON structure, Python and TypeScript produce identical chain hashes:
- Python: `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",",":"))`
- TypeScript: `stableStringify(obj)` — recursive key sort, no spaces

**Verified**: 14/14 interop tests passing (SHA-256, chain hash, Merkle root).
