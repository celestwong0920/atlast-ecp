"""Storage date-parameter path traversal guard (Phase 4.3 M4).

storage._iter_record_files interpolates the `date` argument directly into
a filename (`{date}.jsonl`). Without validation, an attacker-controlled
`date` value like "../../etc/passwd" could resolve outside RECORDS_DIR.
Strict regex `YYYY-MM-DD` prevents this.
"""
import pytest

from atlast_ecp.storage import _iter_record_files


@pytest.mark.parametrize("bad_date", [
    "../../etc/passwd",
    "../../../root/.ssh/id_rsa",
    "2026/04/19",              # wrong separator
    "../2026-04-19",
    "..%2F..",
    "2026-04-19/../other",
    "2026-4-19",               # unpadded month
    "26-04-19",                # 2-digit year
    "2026-04-19.jsonl",        # with extension
    "\x00",                    # NUL byte
])
def test_rejects_path_traversal(bad_date):
    with pytest.raises(ValueError, match="Invalid date"):
        _iter_record_files(bad_date)


@pytest.mark.parametrize("good_date", [
    "2026-04-19",
    "2020-01-01",
    "9999-12-31",
])
def test_accepts_valid_dates(good_date):
    # Returns an empty list if no file matches — the important thing is no raise
    result = _iter_record_files(good_date)
    assert isinstance(result, list)


def test_no_date_returns_all_files():
    """No date argument → list all files (no regex check needed)."""
    result = _iter_record_files(None)
    assert isinstance(result, list)


def test_empty_string_date_falls_through():
    """Empty string is falsy → skips date check entirely, lists all files.
    Not a path traversal risk because the empty string never gets interpolated
    into a filename in this branch."""
    result = _iter_record_files("")
    assert isinstance(result, list)
