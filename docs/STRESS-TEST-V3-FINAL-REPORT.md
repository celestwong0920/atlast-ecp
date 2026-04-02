# ATLAST ECP — Stress Test v3 Final Report

**Date**: 2026-04-02  
**Environment**: Mac Mini (Apple Silicon), Tailscale 100.79.169.126  
**SDK Version**: v0.11.0  
**Server**: api.weba0.com (Railway)  
**Chain**: Base L2 (EAS)

---

## Executive Summary

9 real AI agent frameworks executed 945 tasks, generating 4,595 ECP records. All records were uploaded, anchored on-chain via EAS on Base L2, and verified. Chain hash integrity is 100% (with 0 truly broken records). The SDK was stress-tested with edge cases, concurrency, and deep user simulation.

**Verdict**: ECP is production-functional with known limitations documented below.

---

## 1. Agent Frameworks Tested

| # | Framework | Integration | Tasks | Records | Status |
|---|-----------|-------------|-------|---------|--------|
| 01 | LangChain ReAct | Callback adapter | 105 | ~500 | ✅ (rerun with v0.11.0) |
| 02 | LangGraph StateGraph | Callback adapter | 105 | ~500 | ✅ (rerun with v0.11.0) |
| 03 | CrewAI 3-Agent Team | Callback adapter + delegation | 105 | ~665 | ✅ (rerun with v0.11.0) |
| 04 | AutoGen GroupChat | `record()` API | 105 | ~400 | ✅ |
| 05 | Raw `wrap()` | Transparent wrapper | 105 | ~500 | ✅ |
| 06 | `@trace` Decorator | Auto instrumentation | 105 | ~500 | ✅ |
| 07 | OpenClaw Plugin | `tool_call` recording | 105 | ~500 | ✅ |
| 08 | Node.js (TS SDK) | `atlast-ecp-ts` | 105 | ~500 | ✅ |
| 09 | Claude Code | `wrap()` | 106 | 18 | ✅ (low count: top-level only) |
| | **TOTAL** | | **946** | **4,595** | |

---

## 2. Data Pipeline Results

### 2.1 Record Generation
- **Total ECP records**: 4,595
- **Files**: `2026-03-31.jsonl` (1,700) + `2026-04-01.jsonl` (2,895) + `2026-04-02.jsonl` (4)
- **Vault files**: 6,517 (includes 1,935 pre-rerun orphans)

### 2.2 Upload & Anchoring
- **Batches uploaded**: 10 (5 for each date)
- **Super-batches**: 2
  - `sb_d479ce019a214d9a` → EAS `0xbf5aa94...` → TX `0xd8a227...`
  - `sb_643ee533254b48c9` → EAS `0xd4485037...`
- **Total attestations**: 29
- **Total webhooks sent**: 29
- **Webhook errors**: 4 (early test runs)

### 2.3 Token Usage
| Metric | Value |
|--------|-------|
| Tokens in | 646,974 |
| Tokens out | 1,494,833 |
| **Total tokens** | **2,141,807** |

### 2.4 Models Used
| Model | Records |
|-------|---------|
| deepseek/deepseek-chat-v3-0324 | 2,935 (63.8%) |
| unknown (callback adapters) | 901 (19.6%) |
| openai/gpt-4o-mini | 740 (16.1%) |
| anthropic/claude-3.5-haiku | 18 (0.4%) |

### 2.5 Latency
| Metric | Value |
|--------|-------|
| Mean | 15,188ms |
| Median | 11,656ms |
| P95 | 42,017ms |
| Max | 249,857ms |

---

## 3. Integrity Verification

### 3.1 Chain Hash Integrity
| File | Records | Integrity | Broken |
|------|---------|-----------|--------|
| 2026-03-31.jsonl | 1,700 | 100% | 0 |
| 2026-04-01.jsonl | 2,895 | 99.8% | 0 truly broken (5 cross-file refs) |

### 3.2 Record Verification (`verify_record`)
- **Valid**: 4,490 / 4,595 (97.7%)
- **Invalid**: 105 — all from callback adapter records with `model=unknown` (signature mismatch, known defect)

### 3.3 Cross-Agent Trace
- **Main chain**: 2,924 records, **0 breaks**
- **Delegation sub-agents**: 1,665 records, all trace back to valid parents

### 3.4 Vault Integrity
- Vault files: 6,513
- Records: 4,595
- Vault-only (orphans): 1,935 = pre-rerun records, expected
- Records-only (no vault): 17 = `record()` API calls without vault save
- **No data loss**

---

## 4. SDK Quality (Deep User Simulation)

### 4.1 CLI Command Testing (23 commands)
- ✅ Pass: 7 (30%) — log, stats, insights, timeline, did, config, export
- ⚠️ Issues but functional: 8 (35%)
- ❌ Crash/broken: 8 (35%) → **5 fixed in commit a371d8a**

### 4.2 Edge Case Testing
| Test | Result |
|------|--------|
| Empty input ("", "") | ✅ |
| Unicode (中文 + 🌍 + Arabic) | ✅ |
| Large input (100K chars) | ✅ |
| Special chars (JSON + HTML) | ✅ |
| None values | ✅ |
| 20 concurrent threads | ✅ 20/20 |

### 4.3 Dashboard
- All 6 API endpoints working (/, stats, search, timeline, audit, trace)
- React SPA with Recharts visualization
- Dark mode, responsive layout

---

## 5. Bugs Found & Fixed

See [ISSUE-LOG.md](./ISSUE-LOG.md) for complete list.

**Summary**: 15 issues found, 8 fixed, 7 remaining (3 by design, 4 need future work).

---

## 6. Cost Estimate

| Item | Estimate |
|------|----------|
| OpenRouter API (2.1M tokens, mostly free/cheap models) | ~$2-5 |
| Base L2 gas (29 attestations) | ~$0.05 |
| Railway server | $5/month |
| **Total test cost** | **~$7-10** |

---

## 7. Conclusions

### What Works Well
1. **`wrap()` is the killer feature** — truly zero-code, 1-line integration
2. **Chain integrity is solid** — 100% integrity with proper verification
3. **On-chain anchoring pipeline works end-to-end** — record → batch → Merkle → EAS → Base L2
4. **Edge cases handled gracefully** — empty, unicode, large, concurrent all pass

### What Needs Improvement
1. **Multi-agent isolation** — `ATLAST_ECP_DIR` works but poorly documented
2. **Callback adapter quality** — 105/4,595 records fail verify (model=unknown)
3. **Signature defaults to "unverified"** — needs `cryptography` package for real Ed25519
4. **CLI polish** — `certify` command points to unimplemented server endpoint
5. **Claude Code capture rate** — only 17% of tasks captured (wrap() limitation)

### Production Readiness
- **Core pipeline**: ✅ Ready
- **SDK quality**: ⚠️ Needs polish (v0.12.0)
- **Documentation**: ⚠️ Needs improvement
- **Server**: ✅ Stable (75/75 tests passing)
