"""Dashboard singleton + PID file tests (P0.1).

Ensures the dashboard never runs as two processes on the same port, and that
an older-version dashboard gets killed and replaced when a newer version is
launched (self-healing upgrade).
"""
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def pid_file_home(tmp_path, monkeypatch):
    """Redirect $HOME so the PID file lives under tmp_path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # dashboard_server caches _PID_FILE at module load; reload to pick up HOME
    import importlib
    import atlast_ecp.dashboard_server as ds
    importlib.reload(ds)
    return tmp_path


def test_no_pid_file_proceeds(pid_file_home):
    import atlast_ecp.dashboard_server as ds
    assert ds._read_pid_file() is None
    assert ds._check_singleton(3827, "127.0.0.1") == "proceed"


def test_write_then_read_pid_file(pid_file_home):
    import atlast_ecp.dashboard_server as ds
    ds._write_pid_file(3827, "127.0.0.1")
    data = ds._read_pid_file()
    assert data is not None
    assert data["pid"] == os.getpid()
    assert data["port"] == 3827
    assert data["host"] == "127.0.0.1"
    assert "version" in data


def test_stale_pid_file_treated_as_no_pid(pid_file_home, tmp_path):
    """PID file pointing at a dead process should be treated as absent."""
    import atlast_ecp.dashboard_server as ds
    (tmp_path / ".ecp").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ecp" / "dashboard.pid").write_text(json.dumps({
        "pid": 999999,  # almost certainly not a running process
        "version": "0.32.12",
        "host": "127.0.0.1",
        "port": 3827,
    }))
    # _check_singleton should see the stale PID and proceed
    assert ds._check_singleton(3827, "127.0.0.1") == "proceed"


def test_same_version_same_port_exits(pid_file_home, capsys):
    """Same SDK version running on same port → new invocation exits, not duplicates."""
    import atlast_ecp.dashboard_server as ds
    from atlast_ecp import __version__

    (pid_file_home / ".ecp").mkdir(parents=True, exist_ok=True)
    (pid_file_home / ".ecp" / "dashboard.pid").write_text(json.dumps({
        "pid": os.getpid(),  # use our own PID (guaranteed alive)
        "version": __version__,
        "host": "127.0.0.1",
        "port": 3827,
    }))
    assert ds._check_singleton(3827, "127.0.0.1") == "exit_same"
    captured = capsys.readouterr()
    assert "already running" in captured.out.lower()


def test_different_port_does_not_conflict(pid_file_home):
    """If existing dashboard is on a different port, ours can proceed."""
    import atlast_ecp.dashboard_server as ds
    from atlast_ecp import __version__

    (pid_file_home / ".ecp").mkdir(parents=True, exist_ok=True)
    (pid_file_home / ".ecp" / "dashboard.pid").write_text(json.dumps({
        "pid": os.getpid(),
        "version": __version__,
        "host": "127.0.0.1",
        "port": 9999,  # different port
    }))
    # We want port 3827; existing is on 9999 → proceed
    assert ds._check_singleton(3827, "127.0.0.1") == "proceed"


def test_older_version_gets_killed(pid_file_home, capsys):
    """Older-version dashboard running on our target port → we kill it and proceed."""
    import atlast_ecp.dashboard_server as ds

    (pid_file_home / ".ecp").mkdir(parents=True, exist_ok=True)
    (pid_file_home / ".ecp" / "dashboard.pid").write_text(json.dumps({
        "pid": os.getpid(),  # alive
        "version": "0.17.0",  # older
        "host": "127.0.0.1",
        "port": 3827,
    }))

    killed = []

    def fake_kill(pid, sig):
        killed.append((pid, sig))
        # Mark process as dead after first SIGTERM
        if sig == __import__("signal").SIGTERM:
            # subsequent _process_alive(pid) should return False
            pass

    # Patch os.kill so we don't actually kill ourselves. We also need
    # _process_alive to eventually return False so the kill loop exits.
    call_count = {"alive": 0}

    def fake_alive(pid):
        call_count["alive"] += 1
        # First call (initial existence check) → alive
        # Subsequent calls (during SIGTERM wait loop) → dead after first
        return call_count["alive"] == 1

    with patch.object(ds, "_process_alive", side_effect=fake_alive), \
         patch.object(ds.os, "kill", side_effect=fake_kill):
        result = ds._check_singleton(3827, "127.0.0.1")

    assert result == "replaced_old"
    # Must have attempted SIGTERM on the old PID
    assert len(killed) >= 1
    assert killed[0][0] == os.getpid()
    captured = capsys.readouterr()
    assert "0.17.0" in captured.out
    assert "replace" in captured.out.lower() or "stopped" in captured.out.lower()


# ── P0.4: --host safety tests ────────────────────────────────────────────

def _run_cmd_dashboard(args, capsys):
    """Invoke cmd_dashboard with args; capture stdout. Mock start_dashboard
    so we don't actually bind sockets — we only care about pre-launch logic."""
    import atlast_ecp.cli as cli
    with patch("atlast_ecp.dashboard_server.start_dashboard") as mock_start, \
         patch("atlast_ecp.cli._dashboard_check_launchagent"):
        cli.cmd_dashboard(args)
    return capsys.readouterr().out, mock_start


def test_host_localhost_accepted(capsys):
    out, mock_start = _run_cmd_dashboard(["--host", "127.0.0.1", "--no-open"], capsys)
    mock_start.assert_called_once()
    assert "expose" not in out.lower()


def test_host_lan_rejected_without_unsafe_flag(capsys):
    out, mock_start = _run_cmd_dashboard(["--host", "0.0.0.0", "--no-open"], capsys)
    # Must NOT launch without --unsafe-expose-to-lan
    mock_start.assert_not_called()
    assert "expose" in out.lower()
    assert "unsafe-expose-to-lan" in out
    assert "ssh -L" in out  # suggestion for safer alternative


def test_host_lan_accepted_with_unsafe_flag(capsys):
    out, mock_start = _run_cmd_dashboard(
        ["--host", "0.0.0.0", "--unsafe-expose-to-lan", "--no-open"], capsys,
    )
    mock_start.assert_called_once()
    # Must print red warning banner
    assert "WARNING" in out
    assert "0.0.0.0" in out


def test_host_public_ip_rejected_without_unsafe_flag(capsys):
    """An explicit public or LAN IP (not loopback) must be blocked."""
    out, mock_start = _run_cmd_dashboard(["--host", "192.168.1.10", "--no-open"], capsys)
    mock_start.assert_not_called()
    assert "unsafe-expose-to-lan" in out


def test_localhost_alias_accepted(capsys):
    out, mock_start = _run_cmd_dashboard(["--host", "localhost", "--no-open"], capsys)
    mock_start.assert_called_once()
    assert "WARNING" not in out


def test_default_no_host_flag_is_safe(capsys):
    """Running `atlast dashboard` with no --host defaults to 127.0.0.1, no warning."""
    out, mock_start = _run_cmd_dashboard(["--no-open"], capsys)
    mock_start.assert_called_once()
    assert "WARNING" not in out
    assert "unsafe-expose-to-lan" not in out
