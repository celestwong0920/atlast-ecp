"""SDK-side Discord webhook throttle (Phase 3.5 H4).

Prevents a loop of `atlast init` (or similar) from flooding the team's
Discord #bug-reports channel. Same `source` is throttled to once per
ATLAST_DISCORD_THROTTLE_S seconds (default 600).
"""
import os
import time
from pathlib import Path

import pytest


@pytest.fixture
def throttle_home(tmp_path, monkeypatch):
    """Redirect HOME so the throttle dir lives under tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Ensure a fresh import state isn't required: we import inside tests
    # so HOME indirection applies when Path.home() is called.
    return tmp_path


def test_throttle_first_call_allows(throttle_home):
    from atlast_ecp.cli import _discord_throttle_ok
    assert _discord_throttle_ok("Init") is True


def test_throttle_second_call_blocks(throttle_home):
    from atlast_ecp.cli import _discord_throttle_ok
    assert _discord_throttle_ok("Init") is True
    assert _discord_throttle_ok("Init") is False


def test_throttle_different_sources_independent(throttle_home):
    from atlast_ecp.cli import _discord_throttle_ok
    assert _discord_throttle_ok("Init") is True
    assert _discord_throttle_ok("Doctor") is True  # different source
    assert _discord_throttle_ok("Init") is False
    assert _discord_throttle_ok("Doctor") is False


def test_throttle_window_elapsed_allows_again(throttle_home, monkeypatch):
    """After the window expires, sending is allowed again."""
    # Short window for test
    monkeypatch.setenv("ATLAST_DISCORD_THROTTLE_S", "1")
    # Re-read module-level constant by reloading
    import importlib
    import atlast_ecp.cli as cli_mod
    importlib.reload(cli_mod)

    assert cli_mod._discord_throttle_ok("WindowTest") is True
    assert cli_mod._discord_throttle_ok("WindowTest") is False
    time.sleep(1.1)
    assert cli_mod._discord_throttle_ok("WindowTest") is True


def test_throttle_handles_bad_source_chars(throttle_home):
    """Source strings with / or spaces get sanitized to a safe filename."""
    from atlast_ecp.cli import _discord_throttle_ok
    assert _discord_throttle_ok("Doctor Report/v2") is True
    assert _discord_throttle_ok("Doctor Report/v2") is False


def test_throttle_fail_open_on_fs_error(monkeypatch):
    """If filesystem ops fail, throttle must fail-open (return True) so we
    never silently break the user's CLI."""
    from atlast_ecp import cli
    # Simulate Path.home() pointing somewhere unwritable-ish by making mkdir raise
    class _FakePath:
        def __init__(self, *_args, **_kwargs): pass
        def mkdir(self, *a, **k): raise OSError("denied")
    # Monkey-patch only the Path used inside the function
    monkeypatch.setattr(cli, "Path" if hasattr(cli, "Path") else "os", cli.os, raising=False)
    # The implementation catches any Exception and returns True; directly exercise:
    # Force an exception by using an invalid path — monkey-patch Path.home
    import pathlib
    original_home = pathlib.Path.home
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: pathlib.Path("/nonexistent_dir_that_definitely_does_not_exist/\x00")))
    try:
        assert cli._discord_throttle_ok("FailOpen") is True
    finally:
        monkeypatch.setattr(pathlib.Path, "home", staticmethod(original_home))
