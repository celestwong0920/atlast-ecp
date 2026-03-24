"""
Tests for storage optimizations: gzip compression, TTL cleanup, vault_mode.
"""

import gzip
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


# ─── Fixture: isolated ECP dir ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Isolate all storage paths for each test."""
    ecp_dir = tmp_path / ".ecp"
    monkeypatch.setenv("ATLAST_ECP_DIR", str(ecp_dir))

    # Clear any storage-related env vars before each test
    for var in ("ECP_STORAGE_COMPRESS", "ECP_STORAGE_TTL_DAYS", "ECP_VAULT_MODE"):
        monkeypatch.delenv(var, raising=False)

    import atlast_ecp.storage as _storage
    _storage.ECP_DIR = ecp_dir
    _storage.RECORDS_DIR = ecp_dir / "records"
    _storage.LOCAL_DIR = ecp_dir / "local"
    _storage.VAULT_DIR = ecp_dir / "vault"
    _storage.INDEX_FILE = ecp_dir / "index.json"
    _storage.QUEUE_FILE = ecp_dir / "upload_queue.jsonl"

    yield ecp_dir


def _make_record(uid: str = "rec_test001") -> dict:
    return {"id": uid, "agent": "test-agent", "ts": "2026-01-01T00:00:00Z"}


# ─── Config helpers ────────────────────────────────────────────────────────────

class TestConfigHelpers:
    def test_get_storage_compress_default(self):
        from atlast_ecp.config import get_storage_compress
        assert get_storage_compress() is False

    def test_get_storage_compress_true(self, monkeypatch):
        from atlast_ecp.config import get_storage_compress
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        assert get_storage_compress() is True

    def test_get_storage_compress_1(self, monkeypatch):
        from atlast_ecp.config import get_storage_compress
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "1")
        assert get_storage_compress() is True

    def test_get_storage_compress_yes(self, monkeypatch):
        from atlast_ecp.config import get_storage_compress
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "yes")
        assert get_storage_compress() is True

    def test_get_storage_compress_false(self, monkeypatch):
        from atlast_ecp.config import get_storage_compress
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "false")
        assert get_storage_compress() is False

    def test_get_storage_ttl_days_default(self):
        from atlast_ecp.config import get_storage_ttl_days
        assert get_storage_ttl_days() == 0

    def test_get_storage_ttl_days_env(self, monkeypatch):
        from atlast_ecp.config import get_storage_ttl_days
        monkeypatch.setenv("ECP_STORAGE_TTL_DAYS", "30")
        assert get_storage_ttl_days() == 30

    def test_get_storage_ttl_days_invalid(self, monkeypatch):
        from atlast_ecp.config import get_storage_ttl_days
        monkeypatch.setenv("ECP_STORAGE_TTL_DAYS", "bad")
        assert get_storage_ttl_days() == 0

    def test_get_vault_mode_default(self):
        from atlast_ecp.config import get_vault_mode
        assert get_vault_mode() == "full"

    def test_get_vault_mode_hash_only(self, monkeypatch):
        from atlast_ecp.config import get_vault_mode
        monkeypatch.setenv("ECP_VAULT_MODE", "hash_only")
        assert get_vault_mode() == "hash_only"

    def test_get_vault_mode_compact(self, monkeypatch):
        from atlast_ecp.config import get_vault_mode
        monkeypatch.setenv("ECP_VAULT_MODE", "compact")
        assert get_vault_mode() == "compact"

    def test_get_vault_mode_invalid_falls_back(self, monkeypatch):
        from atlast_ecp.config import get_vault_mode
        monkeypatch.setenv("ECP_VAULT_MODE", "nonsense")
        assert get_vault_mode() == "full"


# ─── Gzip compression ─────────────────────────────────────────────────────────

class TestGzipCompression:
    def test_save_creates_gz_file(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, RECORDS_DIR
        save_record(_make_record("rec_gz001"))
        gz_files = list(RECORDS_DIR.glob("*.jsonl.gz"))
        assert len(gz_files) == 1, "Expected one .jsonl.gz file"

    def test_save_no_plain_file_when_compressed(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, RECORDS_DIR
        save_record(_make_record("rec_gz002"))
        plain_files = list(RECORDS_DIR.glob("*.jsonl"))
        assert len(plain_files) == 0, "No plain .jsonl should exist when compression is on"

    def test_gz_file_is_valid_gzip(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, RECORDS_DIR
        save_record(_make_record("rec_gz003"))
        gz_file = next(RECORDS_DIR.glob("*.jsonl.gz"))
        # Must be readable as gzip
        with gzip.open(gz_file, "rt", encoding="utf-8") as fh:
            lines = fh.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["id"] == "rec_gz003"

    def test_load_records_from_gz(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, load_records
        save_record(_make_record("rec_gz004"))
        records = load_records(limit=10)
        assert any(r["id"] == "rec_gz004" for r in records)

    def test_load_record_by_id_from_gz(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, load_record_by_id
        save_record(_make_record("rec_gz005"))
        r = load_record_by_id("rec_gz005")
        assert r is not None
        assert r["id"] == "rec_gz005"

    def test_multiple_records_appended_to_same_gz(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, load_records, RECORDS_DIR
        for i in range(5):
            save_record(_make_record(f"rec_gz_multi{i:02d}"))
        gz_files = list(RECORDS_DIR.glob("*.jsonl.gz"))
        assert len(gz_files) == 1, "All records should be in one daily file"
        records = load_records(limit=10)
        assert len(records) == 5

    def test_index_stores_gz_path(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, _load_index
        save_record(_make_record("rec_gz_idx"))
        index = _load_index()
        assert "rec_gz_idx" in index
        assert index["rec_gz_idx"]["file"].endswith(".jsonl.gz")


# ─── Backward compatibility ───────────────────────────────────────────────────

class TestBackwardCompat:
    def test_load_plain_when_compress_off(self, isolated_storage):
        """Default (no compress) writes .jsonl and reads it back."""
        from atlast_ecp.storage import save_record, load_records, RECORDS_DIR
        save_record(_make_record("rec_plain001"))
        plain_files = list(RECORDS_DIR.glob("*.jsonl"))
        assert len(plain_files) == 1
        records = load_records(limit=10)
        assert any(r["id"] == "rec_plain001" for r in records)

    def test_load_records_mixed_plain_and_gz(self, monkeypatch, isolated_storage):
        """Can read both plain and gz files in the same records dir."""
        from atlast_ecp.storage import save_record, load_records, RECORDS_DIR

        # Write a plain record
        save_record(_make_record("rec_plain_mix"))

        # Manually write a gzip record for a different "date"
        gz_file = RECORDS_DIR / "2020-01-01.jsonl.gz"
        with gzip.open(gz_file, "wt", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "rec_gz_mix", "agent": "old"}) + "\n")

        records = load_records(limit=20)
        ids = [r["id"] for r in records]
        assert "rec_plain_mix" in ids
        assert "rec_gz_mix" in ids

    def test_load_record_by_id_plain_file(self, isolated_storage):
        """load_record_by_id works on plain .jsonl files."""
        from atlast_ecp.storage import save_record, load_record_by_id
        save_record(_make_record("rec_byid_plain"))
        r = load_record_by_id("rec_byid_plain")
        assert r is not None and r["id"] == "rec_byid_plain"

    def test_load_record_by_id_gz_via_index(self, isolated_storage):
        """load_record_by_id follows index to a .jsonl.gz file."""
        import atlast_ecp.storage as st
        from atlast_ecp.storage import load_record_by_id, RECORDS_DIR, INDEX_FILE

        # Manually create a gz file and inject index entry
        gz_file = RECORDS_DIR / "2020-06-15.jsonl.gz"
        RECORDS_DIR.mkdir(parents=True, exist_ok=True)
        rec = {"id": "rec_byid_gz_old", "agent": "legacy"}
        with gzip.open(gz_file, "wt", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        INDEX_FILE.write_text(json.dumps({
            "rec_byid_gz_old": {"file": str(gz_file), "date": "2020-06-15"}
        }))

        result = load_record_by_id("rec_byid_gz_old")
        assert result is not None
        assert result["id"] == "rec_byid_gz_old"


# ─── TTL cleanup ──────────────────────────────────────────────────────────────

class TestTTLCleanup:
    def _write_old_file(self, records_dir: Path, date_str: str, records: list[dict]) -> Path:
        """Write a plain .jsonl file with the given date in its name."""
        records_dir.mkdir(parents=True, exist_ok=True)
        f = records_dir / f"{date_str}.jsonl"
        with open(f, "w", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return f

    def _write_old_gz_file(self, records_dir: Path, date_str: str, records: list[dict]) -> Path:
        records_dir.mkdir(parents=True, exist_ok=True)
        f = records_dir / f"{date_str}.jsonl.gz"
        with gzip.open(f, "wt", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return f

    def test_cleanup_disabled_when_days_zero(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR
        self._write_old_file(RECORDS_DIR, "2000-01-01", [_make_record("old_rec")])
        result = cleanup_old_records(days=0)
        assert result["removed_files"] == 0
        assert (RECORDS_DIR / "2000-01-01.jsonl").exists()

    def test_cleanup_removes_old_plain_file(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR, INDEX_FILE
        old_rec = _make_record("rec_old_plain")
        old_file = self._write_old_file(RECORDS_DIR, "2000-01-01", [old_rec])
        INDEX_FILE.write_text(json.dumps({
            "rec_old_plain": {"file": str(old_file), "date": "2000-01-01"}
        }))
        result = cleanup_old_records(days=90)
        assert not old_file.exists()
        assert result["removed_files"] == 1
        assert result["removed_index"] == 1

    def test_cleanup_removes_old_gz_file(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR, INDEX_FILE
        old_rec = _make_record("rec_old_gz")
        old_file = self._write_old_gz_file(RECORDS_DIR, "2000-01-01", [old_rec])
        INDEX_FILE.write_text(json.dumps({
            "rec_old_gz": {"file": str(old_file), "date": "2000-01-01"}
        }))
        result = cleanup_old_records(days=90)
        assert not old_file.exists()
        assert result["removed_files"] == 1

    def test_cleanup_removes_vault_files(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR, VAULT_DIR, INDEX_FILE
        old_rec = _make_record("rec_vault_old")
        old_file = self._write_old_file(RECORDS_DIR, "2000-01-01", [old_rec])
        # Create a vault file
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        vault_file = VAULT_DIR / "rec_vault_old.json"
        vault_file.write_text('{"record_id": "rec_vault_old"}')
        INDEX_FILE.write_text(json.dumps({
            "rec_vault_old": {"file": str(old_file), "date": "2000-01-01"}
        }))
        result = cleanup_old_records(days=90)
        assert not vault_file.exists()
        assert result["removed_vault"] == 1

    def test_cleanup_preserves_recent_files(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR, INDEX_FILE
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        recent_rec = _make_record("rec_recent")
        recent_file = self._write_old_file(RECORDS_DIR, today, [recent_rec])
        INDEX_FILE.write_text(json.dumps({
            "rec_recent": {"file": str(recent_file), "date": today}
        }))
        result = cleanup_old_records(days=90)
        assert recent_file.exists()
        assert result["removed_files"] == 0
        assert result["removed_index"] == 0

    def test_cleanup_mixed_old_and_recent(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR, INDEX_FILE
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        old_file = self._write_old_file(RECORDS_DIR, "2000-01-01", [_make_record("rec_old")])
        recent_file = self._write_old_file(RECORDS_DIR, today, [_make_record("rec_new")])
        INDEX_FILE.write_text(json.dumps({
            "rec_old": {"file": str(old_file), "date": "2000-01-01"},
            "rec_new": {"file": str(recent_file), "date": today},
        }))
        result = cleanup_old_records(days=90)
        assert not old_file.exists()
        assert recent_file.exists()
        assert result["removed_files"] == 1
        assert result["removed_index"] == 1

    def test_cleanup_updates_index(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR, INDEX_FILE, _load_index
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        old_file = self._write_old_file(RECORDS_DIR, "2000-01-01", [_make_record("rec_old_idx")])
        recent_file = self._write_old_file(RECORDS_DIR, today, [_make_record("rec_new_idx")])
        INDEX_FILE.write_text(json.dumps({
            "rec_old_idx": {"file": str(old_file), "date": "2000-01-01"},
            "rec_new_idx": {"file": str(recent_file), "date": today},
        }))
        cleanup_old_records(days=90)
        index = _load_index()
        assert "rec_old_idx" not in index
        assert "rec_new_idx" in index

    def test_cleanup_empty_dir_no_error(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records
        result = cleanup_old_records(days=30)
        assert result["removed_files"] == 0
        assert result["removed_vault"] == 0
        assert result["removed_index"] == 0

    def test_cleanup_negative_days_disabled(self, isolated_storage):
        from atlast_ecp.storage import cleanup_old_records, RECORDS_DIR
        self._write_old_file(RECORDS_DIR, "2000-01-01", [_make_record("rec_neg")])
        result = cleanup_old_records(days=-1)
        assert result["removed_files"] == 0
        assert (RECORDS_DIR / "2000-01-01.jsonl").exists()


# ─── Vault mode ───────────────────────────────────────────────────────────────

class TestVaultMode:
    def test_full_mode_saves_with_indent(self, isolated_storage):
        from atlast_ecp.storage import save_vault, VAULT_DIR
        save_vault("rec_vm_full", "input text", "output text")
        vault_file = VAULT_DIR / "rec_vm_full.json"
        assert vault_file.exists()
        raw = vault_file.read_text()
        # Pretty-printed → has newlines / indentation
        assert "\n" in raw
        data = json.loads(raw)
        assert data["record_id"] == "rec_vm_full"
        assert data["input"] == "input text"

    def test_compact_mode_saves_no_indent(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_VAULT_MODE", "compact")
        from atlast_ecp.storage import save_vault, VAULT_DIR
        save_vault("rec_vm_compact", "inp", "out")
        vault_file = VAULT_DIR / "rec_vm_compact.json"
        assert vault_file.exists()
        raw = vault_file.read_text()
        # Compact → single line, no pretty-print indentation
        assert "\n" not in raw.strip()
        data = json.loads(raw)
        assert data["record_id"] == "rec_vm_compact"

    def test_hash_only_mode_skips_vault(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_VAULT_MODE", "hash_only")
        from atlast_ecp.storage import save_vault, VAULT_DIR
        save_vault("rec_vm_hashonly", "inp", "out")
        vault_file = VAULT_DIR / "rec_vm_hashonly.json"
        assert not vault_file.exists(), "hash_only mode must not write vault file"

    def test_vault_v2_full_mode(self, isolated_storage):
        from atlast_ecp.storage import save_vault_v2, VAULT_DIR
        save_vault_v2("rec_v2_full", "inp", "out", extra={"vault_version": 2})
        vault_file = VAULT_DIR / "rec_v2_full.json"
        assert vault_file.exists()
        raw = vault_file.read_text()
        assert "\n" in raw  # indented

    def test_vault_v2_compact_mode(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_VAULT_MODE", "compact")
        from atlast_ecp.storage import save_vault_v2, VAULT_DIR
        save_vault_v2("rec_v2_compact", "inp", "out", extra={"vault_version": 2})
        vault_file = VAULT_DIR / "rec_v2_compact.json"
        assert vault_file.exists()
        raw = vault_file.read_text()
        assert "\n" not in raw.strip()

    def test_vault_v2_hash_only_mode(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_VAULT_MODE", "hash_only")
        from atlast_ecp.storage import save_vault_v2, VAULT_DIR
        save_vault_v2("rec_v2_hashonly", "inp", "out")
        vault_file = VAULT_DIR / "rec_v2_hashonly.json"
        assert not vault_file.exists()

    def test_load_vault_after_full_save(self, isolated_storage):
        from atlast_ecp.storage import save_vault, load_vault
        save_vault("rec_lv_full", "my input", "my output")
        data = load_vault("rec_lv_full")
        assert data is not None
        assert data["input"] == "my input"
        assert data["output"] == "my output"

    def test_load_vault_after_compact_save(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_VAULT_MODE", "compact")
        from atlast_ecp.storage import save_vault, load_vault
        save_vault("rec_lv_compact", "inp2", "out2")
        data = load_vault("rec_lv_compact")
        assert data is not None
        assert data["input"] == "inp2"

    def test_load_vault_hash_only_returns_none(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_VAULT_MODE", "hash_only")
        from atlast_ecp.storage import save_vault, load_vault
        save_vault("rec_lv_ho", "inp", "out")
        data = load_vault("rec_lv_ho")
        assert data is None


# ─── count_records with gzip ──────────────────────────────────────────────────

class TestCountRecords:
    def test_count_plain(self, isolated_storage):
        from atlast_ecp.storage import save_record, count_records
        save_record(_make_record("rec_cnt1"))
        save_record(_make_record("rec_cnt2"))
        assert count_records() == 2

    def test_count_gz(self, monkeypatch, isolated_storage):
        monkeypatch.setenv("ECP_STORAGE_COMPRESS", "true")
        from atlast_ecp.storage import save_record, count_records
        save_record(_make_record("rec_gz_cnt1"))
        save_record(_make_record("rec_gz_cnt2"))
        assert count_records() == 2

    def test_count_mixed(self, monkeypatch, isolated_storage):
        """count_records handles both plain and gz files."""
        from atlast_ecp.storage import save_record, count_records, RECORDS_DIR
        save_record(_make_record("rec_mix_plain"))
        # Write a gz file manually for a different date
        gz = RECORDS_DIR / "2020-01-01.jsonl.gz"
        with gzip.open(gz, "wt", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "rec_mix_gz"}) + "\n")
        assert count_records() == 2
