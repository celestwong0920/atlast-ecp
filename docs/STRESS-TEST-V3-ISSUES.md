# ATLAST ECP — Stress Test v3 Issue Log

All bugs discovered during Stress Test v3 (2026-03-31 ~ 2026-04-02).

---

## 🔴 Critical (Fixed)

| # | Issue | Root Cause | Fix | Commit |
|---|-------|-----------|-----|--------|
| BUG-001 | `batch.py` sorting causes records to upload out of order | `collect_batch` didn't sort by timestamp | Sort + use `max_record_ts` for `last_batch_ts` | SDK v0.11.0 |
| BUG-002 | LangChain/CrewAI adapters missing chain hash | Used `record_minimal()` instead of `record()` | Changed to `record()` | SDK v0.11.0 |
| BUG-003 | `atlast backup-key` crashes: `FileNotFoundError: bip39_english.txt` | File not included in PyPI package | Added to `pyproject.toml` `[tool.setuptools.package-data]` | a371d8a |
| BUG-004 | `atlast discover` crashes: `AttributeError: 'str' has no 'get'` | Server returns endpoints as `{name: path}` dict, code expected list of objects | Handle both dict and list | a371d8a |
| BUG-005 | Dashboard assets missing from install | `dashboard_assets/` not in package-data | Added to `pyproject.toml` | a371d8a |
| BUG-006 | `atlast push` shows empty batch ID | `batch_result` dict didn't propagate `attestation_uid` | Show `attestation_uid` from server response | a371d8a |
| BUG-007 | CI lint failure (225+ errors) blocking PyPI publish | Whitespace on blank lines (W293), semicolons (E702) | `ruff --fix` + manual semicolon splits + ruff config | b444737 |
| BUG-008 | `query.py` test failure: `VAULT_DIR` import missing | Import removed during lint cleanup | Restored import | post-b444737 |

## 🟡 Medium (Known, Not Fixed)

| # | Issue | Impact | Workaround |
|---|-------|--------|-----------|
| BUG-009 | Callback adapters produce `model=unknown` | 105/4,595 records fail `verify_record` (sig mismatch) | Use `wrap()` or `record()` instead |
| BUG-010 | `atlast certify` returns HTTP 404 | Work Certificate feature unusable | Server endpoint not implemented yet |
| BUG-011 | `atlast proxy`/`run` require extra deps | Layer 0 "zero-code" requires `pip install atlast-ecp[proxy]` | Use `wrap()` (truly zero extra deps) |
| BUG-012 | `sig: unverified` is default | Records lack cryptographic proof without `cryptography` package | `pip install cryptography` |
| BUG-013 | Agent 09 (Claude Code) low capture rate | wrap() only captures 18/106 tasks (17%) | By design — wrap() intercepts top-level calls only |
| BUG-014 | `atlast stats` shows "BROKEN" on multi-agent shared dir | Chain prev pointers cross between agents | Use `ATLAST_ECP_DIR` per agent |
| BUG-015 | `atlast register` generates new API key each call | No idempotency check | Remember your key from first call |
| BUG-016 | `atlast config` shows `api_key = test123` | Dev leftover | Reset with `atlast config set api_key <real_key>` |

## 🟢 Minor / By Design

| # | Issue | Notes |
|---|-------|-------|
| INFO-001 | 5 chain hash "breaks" in 04-01 records | Cross-file references to 03-31 — not actual breaks |
| INFO-002 | 1,935 vault orphan files | Pre-rerun records, expected after SDK fix + rerun |
| INFO-003 | 17 records without vault files | `record()` API doesn't create vault copies — by design |
| INFO-004 | Concurrent chain prev breaks | Multiple threads writing simultaneously — by design for performance |

---

## Fix Timeline

| Version | Fixes | Status |
|---------|-------|--------|
| v0.11.0 | BUG-001, BUG-002 | ✅ Released |
| v0.11.1 | BUG-003 ~ BUG-008 | ✅ Released (PyPI) |
| v0.12.0 (planned) | BUG-009 ~ BUG-012 | 🔲 Next sprint |
