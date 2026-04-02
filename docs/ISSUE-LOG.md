# ATLAST ECP — Stress Test v3 Issue Log

**Test Period**: 2026-03-31 → 2026-04-02  
**SDK**: v0.10.0 → v0.11.0  

---

## Fixed Issues ✅

| # | Severity | Issue | Root Cause | Fix | Commit |
|---|----------|-------|-----------|-----|--------|
| 1 | 🔴 Critical | `batch.py` `collect_batch` wrong sort order | Records not sorted by timestamp | Fixed sort key | v0.11.0 |
| 2 | 🔴 Critical | `last_batch_ts` tracking bug | Used batch_ts instead of max_record_ts | Use `max(record_timestamps)` | v0.11.0 |
| 3 | 🔴 Critical | LangChain/CrewAI adapters: no chain hash | Used `record_minimal` instead of `record` | Switched to `record()` | v0.11.0 |
| 4 | 🟡 Medium | `atlast backup-key` crash | `bip39_english.txt` not in PyPI package | Added to `pyproject.toml` package-data | a371d8a |
| 5 | 🟡 Medium | `atlast discover` crash | Endpoints parsed as list, actually dict | Handle both formats | a371d8a |
| 6 | 🟡 Medium | Dashboard assets missing from install | `dashboard_assets/` not in package-data | Added glob to pyproject.toml | a371d8a |
| 7 | 🟢 Low | `atlast push` shows empty batch ID | CLI reads `batch_id` but result has `attestation_uid` | Show attestation_uid | a371d8a |
| 8 | 🟢 Low | Ruff lint 225 errors blocking CI | W293 whitespace + E702 semicolons | `ruff --fix` + manual splits | b444737 |

## Known Issues (Not Fixed) ⚠️

| # | Severity | Issue | Impact | Status |
|---|----------|-------|--------|--------|
| 9 | 🔴 Critical | `atlast certify` returns 404 | Work certificates unusable | Server endpoint `/certificates/create` not implemented |
| 10 | 🔴 Critical | `sig: "unverified"` is default | ECP records ≈ fancy JSON logs without real crypto | Needs `pip install atlast-ecp[crypto]` for Ed25519 |
| 11 | 🟡 Medium | Callback adapter records: `model=unknown` | 105/4,595 records fail `verify_record` | LangChain/CrewAI callbacks don't capture model name reliably |
| 12 | 🟡 Medium | `atlast proxy`/`run` need extra deps | "Zero-code" Layer 0 broken without `aiohttp` | By design (optional dep), error message improved |
| 13 | 🟡 Medium | Claude Code wrap() captures only 17% of tasks | 18/106 tasks recorded | wrap() only captures top-level LLM calls, not internal agent loops |
| 14 | 🟢 Low | `atlast register` creates new API key each call | Multiple orphan keys | Should check if already registered |
| 15 | 🟢 Low | Multi-agent isolation underdocumented | Users don't know about `ATLAST_ECP_DIR` | README needs section on multi-agent setup |

## Design Decisions (Not Bugs)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Chain `prev` pointers are per-agent-session, not file order | Multiple agents share records file; file-order breaks are expected |
| D2 | Concurrent record creation may have chain breaks | Thread safety vs performance tradeoff; records are still individually valid |
| D3 | Vault files > records count (6,517 vs 4,595) | Vault keeps pre-rerun orphans; no data loss |
| D4 | `record()` returns string ID, not dict | Lightweight API; use `load_record_by_id()` for full data |
