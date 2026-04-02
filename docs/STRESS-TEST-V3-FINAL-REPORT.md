# ATLAST ECP — Stress Test v3 Final Report

**Date**: 2026-04-02  
**Duration**: 2026-03-31 ~ 2026-04-02 (3 days)  
**Environment**: Mac Mini (M-series, 100.79.169.126), Python 3.14/3.13, Node.js  
**SDK Version**: v0.11.1 (released to PyPI during test)  
**Server**: api.weba0.com (Railway, EAS on Base L2)

---

## Executive Summary

Tested 9 AI agent frameworks executing 945 tasks, generating 4,595 ECP records. Full lifecycle validated: agent execution → ECP recording → batch upload → on-chain anchoring → Merkle verification → vault tracing.

**Result: PASS with known limitations**

| Metric | Value |
|--------|-------|
| Frameworks tested | 9 |
| Total tasks | 945 |
| ECP records generated | 4,595 |
| Records uploaded | 4,595 (100%) |
| On-chain attestations | 29 |
| Super-batches | 2 |
| Verify pass rate | 97.7% (4,490/4,595) |
| Chain integrity | 99.8% |
| Total tokens | 2,141,807 |

---

## 1. Agent Framework Results

| # | Framework | Integration | Tasks | Records | Verify | Notes |
|---|-----------|------------|-------|---------|--------|-------|
| 01 | LangChain ReAct | Callback adapter | 105 | ~550 | 95%* | *model=unknown on some |
| 02 | LangGraph StateGraph | Callback adapter | 105 | ~550 | 95%* | Same callback issue |
| 03 | CrewAI 3-agent team | Callback + delegation | 105 | ~800 | 95%* | Delegation sub-records |
| 04 | AutoGen GroupChat | record() API | 105 | ~500 | 100% | Slowest (GroupChat overhead) |
| 05 | Raw wrap() | wrap(openai.OpenAI()) | 105 | ~500 | 100% | Best UX, zero-code |
| 06 | @trace decorator | auto instrumentation | 105 | ~500 | 100% | Clean integration |
| 07 | OpenClaw plugin | tool_call record | 105 | ~500 | 100% | Works well |
| 08 | Node.js (TS SDK) | @atlast/sdk | 105 | ~500 | 100% | npm package OK |
| 09 | Claude Code | wrap() | 106 | 18 | 100% | Low capture (top-level only) |

**Total**: 946 tasks → 4,595 records → 4,490 verified (97.7%)

### Key Findings per Framework
- **wrap()** is the best user experience — true zero-code, 100% verify rate
- **Callback adapters** (LangChain/CrewAI) have `model=unknown` issue causing 105 verify failures (signature mismatch)
- **Claude Code wrap()** only captures 17% of tasks (18/106) — wrap() intercepts top-level API calls only, not internal agent-to-agent calls
- **AutoGen** is slowest due to GroupChat multi-turn overhead

---

## 2. Pipeline Metrics

### 2.1 Recording
| Metric | Value |
|--------|-------|
| Records (2026-03-31) | 1,700 |
| Records (2026-04-01) | 2,895 |
| Records (2026-04-02) | 4 (test) |
| Vault files | 6,517 |
| Vault-only (orphans) | 1,935 (pre-rerun, expected) |
| Records-only (no vault) | 17 (record() API, expected) |

### 2.2 Upload & Anchoring
| Metric | Value |
|--------|-------|
| Batches uploaded | 10 |
| Super-batches | 2 |
| On-chain attestations | 29 |
| Webhooks sent | 29 |
| EAS chain | Base L2 (mainnet) |
| Super-batch 1 | sb_d479ce019a214d9a → EAS `0xbf5aa94...` |
| Super-batch 2 | sb_643ee533254b48c9 → EAS `0xd4485037...` |

### 2.3 Verification
| Check | Result |
|-------|--------|
| Merkle proof (records 0/100/500/999) | ✅ All verified |
| EAS attestation API | ✅ Confirmed |
| Chain hash integrity (03-31) | ✅ 1,700/1,700 (100%) |
| Chain hash integrity (04-01) | ✅ 2,890/2,895 (99.8%, 5 cross-file refs) |
| SDK verify_record | ✅ 4,490/4,595 (97.7%) |
| Cross-agent trace | ✅ 2,924 main + 1,665 delegation, 0 breaks |

### 2.4 Performance
| Metric | Value |
|--------|-------|
| Total tokens (in) | 646,974 |
| Total tokens (out) | 1,494,833 |
| Total tokens | 2,141,807 |
| Mean latency | 15,188ms |
| Median latency | 11,656ms |
| P95 latency | 42,017ms |
| Max latency | 249,857ms (~4 min) |

### 2.5 Models Used
| Model | Records | % |
|-------|---------|---|
| deepseek/deepseek-chat-v3-0324 | 2,935 | 63.9% |
| unknown (callback adapter) | 901 | 19.6% |
| openai/gpt-4o-mini | 740 | 16.1% |
| anthropic/claude-3.5-haiku | 18 | 0.4% |

---

## 3. SDK Release

| Version | Status | Changes |
|---------|--------|---------|
| v0.10.0 | Published (PyPI) | Initial release |
| v0.11.0 | Superseded | batch.py fix, chain hash in adapters |
| v0.11.1 | **Current (PyPI)** | + lint fixes, bip39 packaging, discover crash, dashboard assets, push output, improved error messages |

### v0.11.1 Bug Fixes
1. `backup-key` crash → bip39_english.txt packaged
2. `discover` crash → dict/list handling
3. `dashboard` missing → assets packaged
4. `push` empty output → shows attestation ID
5. `proxy`/`run` → improved error messages
6. Ruff lint 225+ errors → 0

---

## 4. Deep User Simulation Test

Simulated a fresh user installing and using ECP from scratch:

| Scenario | Result |
|----------|--------|
| `atlast init` + `register` | ✅ |
| `wrap()` with OpenAI-compatible | ✅ |
| `record()` with metadata | ✅ |
| `@trace` / auto instrumentation | ✅ |
| CLI (7 commands) | ✅ 7/7 |
| Dashboard (6 API endpoints) | ✅ 6/6 |
| Push + Server upload | ✅ |
| Proof generation | ✅ |
| Edge cases (empty/unicode/100K/special/None) | ✅ 5/5 |
| Concurrent records (20 threads) | ✅ 20/20 |

---

## 5. Known Limitations

1. **Callback adapter `model=unknown`**: LangChain/CrewAI callback handlers don't always capture the model name, causing 105/4,595 verify failures (2.3%)
2. **Claude Code low capture rate**: wrap() only captures top-level OpenAI calls (18/106 = 17%)
3. **`sig: unverified` default**: Without `cryptography` package, records have no cryptographic signature
4. **`certify` command**: Server endpoint `/certificates/create` not implemented
5. **`proxy`/`run`**: Requires `pip install atlast-ecp[proxy]` (aiohttp dependency)
6. **Multi-agent isolation**: Requires `ATLAST_ECP_DIR` env var (works but poorly documented)

---

## 6. Conclusion

The ATLAST ECP pipeline is **functional end-to-end**: agents create records → records are chain-hashed → batched and uploaded → Merkle-proven → anchored on-chain via EAS → verifiable.

The core value proposition (verifiable agent work records) is proven. Priority improvements for production:
1. Fix callback adapter model capture
2. Default cryptographic signatures
3. Better multi-agent isolation documentation
4. Implement `certify` endpoint
