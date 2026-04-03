"""
ATLAST ECP — Automatic Scanner Service

Detects OpenClaw agent directories and installs a persistent system service
(launchd on macOS, systemd on Linux, cron fallback) that continuously scans
agent session logs and creates ECP records.

Users never need to know this exists. `atlast init` calls setup_scanner_service()
and everything just works.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PLIST_LABEL = "ai.atlast.ecp.scanner"
SYSTEMD_UNIT = "atlast-ecp-scanner"


def detect_openclaw_agents() -> list[dict]:
    """Find all OpenClaw agent directories on this machine."""
    home = Path.home()
    agents = []
    for d in sorted(home.glob(".openclaw-*")):
        if not d.is_dir():
            continue
        sessions_dir = d / "agents" / "main" / "sessions"
        if not sessions_dir.exists():
            continue
        # Extract agent name
        name = d.name.replace(".openclaw-", "")
        # Check if there are actual session files
        session_files = list(sessions_dir.glob("*.jsonl"))
        if not session_files:
            continue
        agents.append({
            "name": name,
            "dir": str(d),
            "sessions": len(session_files),
        })
    return agents


def _find_atlast_binary() -> str:
    """Find the atlast CLI binary path."""
    # Try which
    result = shutil.which("atlast")
    if result:
        return result
    # Try common locations
    for p in [
        Path(sys.prefix) / "bin" / "atlast",
        Path.home() / ".local" / "bin" / "atlast",
        Path("/usr/local/bin/atlast"),
        Path("/opt/homebrew/bin/atlast"),
    ]:
        if p.exists():
            return str(p)
    # Fallback: use python -m
    return f"{sys.executable} -m atlast_ecp.openclaw_scanner"


def _find_python() -> str:
    """Find the Python that has atlast_ecp installed."""
    return sys.executable


def _build_scanner_command(agents: list[dict]) -> list[str]:
    """Build the scanner command that watches all agents."""
    python = _find_python()
    # We'll create a wrapper script that scans all agents
    return [python, "-m", "atlast_ecp.scanner_daemon"]


def _get_wrapper_script_path() -> Path:
    """Path for the scanner daemon wrapper."""
    ecp_dir = Path(os.environ.get("ATLAST_ECP_DIR", str(Path.home() / ".ecp")))
    return ecp_dir / "scanner_daemon.py"


def create_scanner_daemon(agents: list[dict]) -> Path:
    """Create a daemon script that scans all detected agents."""
    script_path = _get_wrapper_script_path()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    
    agent_configs = json.dumps(agents, indent=2)
    python = _find_python()
    
    script = f'''#!/usr/bin/env python3
"""ATLAST ECP Scanner Daemon — auto-generated, do not edit."""
import json
import os
import sys
import time
import signal

# Agents to scan (auto-detected at init time)
AGENTS = {agent_configs}
SCAN_INTERVAL = 30  # seconds

def scan_all():
    """Scan all registered agents."""
    # Re-detect agents each cycle (new agents may appear)
    from pathlib import Path
    home = Path.home()
    
    # Start with configured agents
    agent_dirs = {{a["name"]: a["dir"] for a in AGENTS}}
    
    # Also detect any new openclaw agents
    for d in home.glob(".openclaw-*"):
        if not d.is_dir():
            continue
        sessions = d / "agents" / "main" / "sessions"
        if not sessions.exists():
            continue
        name = d.name.replace(".openclaw-", "")
        if name not in agent_dirs:
            agent_dirs[name] = str(d)
    
    from atlast_ecp.openclaw_scanner import scan_openclaw_agent
    
    for name, agent_dir in agent_dirs.items():
        try:
            result = scan_openclaw_agent(agent_dir, agent_name=name)
            if result.get("new_records", 0) > 0:
                ts = time.strftime("%H:%M:%S")
                print(f"[{{ts}}] {{name}}: {{result['new_records']}} new records", flush=True)
        except Exception as e:
            ts = time.strftime("%H:%M:%S")
            print(f"[{{ts}}] {{name}}: error: {{e}}", flush=True)


def main():
    print(f"ATLAST Scanner Daemon started (PID {{os.getpid()}})")
    print(f"Watching {{len(AGENTS)}} agent(s), interval={{SCAN_INTERVAL}}s")
    
    # Handle graceful shutdown
    running = True
    def stop(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    
    while running:
        try:
            scan_all()
        except Exception as e:
            print(f"Scan error: {{e}}", flush=True)
        
        # Sleep in small increments for responsive shutdown
        for _ in range(SCAN_INTERVAL):
            if not running:
                break
            time.sleep(1)
    
    print("ATLAST Scanner Daemon stopped")


if __name__ == "__main__":
    main()
'''
    script_path.write_text(script)
    script_path.chmod(0o755)
    return script_path


def setup_macos_launchd(agents: list[dict]) -> bool:
    """Install launchd plist for macOS."""
    script_path = create_scanner_daemon(agents)
    python = _find_python()
    
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / f"{PLIST_LABEL}.plist"
    
    log_dir = Path.home() / ".ecp" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/scanner.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/scanner.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>'''
    
    # Unload existing if present
    try:
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True, timeout=5
        )
    except Exception:
        pass
    
    plist_path.write_text(plist_content)
    
    # Load the service
    try:
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def setup_linux_systemd(agents: list[dict]) -> bool:
    """Install systemd user service for Linux."""
    script_path = create_scanner_daemon(agents)
    python = _find_python()
    
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit_path = unit_dir / f"{SYSTEMD_UNIT}.service"
    
    unit_content = f'''[Unit]
Description=ATLAST ECP Scanner Daemon
After=network.target

[Service]
Type=simple
ExecStart={python} {script_path}
Restart=always
RestartSec=10
Environment=HOME={Path.home()}

[Install]
WantedBy=default.target
'''
    
    unit_path.write_text(unit_content)
    
    try:
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=5)
        subprocess.run(["systemctl", "--user", "enable", SYSTEMD_UNIT], capture_output=True, timeout=5)
        result = subprocess.run(
            ["systemctl", "--user", "start", SYSTEMD_UNIT],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def setup_cron_fallback(agents: list[dict]) -> bool:
    """Fallback: install cron job for scanning."""
    script_path = create_scanner_daemon(agents)
    python = _find_python()
    
    cron_line = f"* * * * * {python} {script_path} --once 2>>{Path.home()}/.ecp/logs/scanner.err >>{Path.home()}/.ecp/logs/scanner.log"
    
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        
        if PLIST_LABEL in existing or "scanner_daemon" in existing:
            return True  # Already installed
        
        new_cron = existing.rstrip() + "\n" + cron_line + "\n"
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(input=new_cron)
        return proc.returncode == 0
    except Exception:
        return False


def setup_scanner_service() -> dict:
    """
    Main entry point. Detects agents, installs appropriate system service.
    Returns status dict.
    """
    agents = detect_openclaw_agents()
    
    if not agents:
        return {
            "status": "no_agents",
            "message": "No OpenClaw agents found. Scanner will auto-start when agents are detected.",
        }
    
    system = platform.system()
    
    if system == "Darwin":
        success = setup_macos_launchd(agents)
        method = "launchd"
    elif system == "Linux":
        success = setup_linux_systemd(agents)
        if not success:
            success = setup_cron_fallback(agents)
            method = "cron"
        else:
            method = "systemd"
    else:
        success = setup_cron_fallback(agents)
        method = "cron"
    
    return {
        "status": "ok" if success else "failed",
        "method": method,
        "agents": [a["name"] for a in agents],
        "agent_count": len(agents),
    }


def get_scanner_status() -> dict:
    """Check if scanner service is running."""
    system = platform.system()
    
    if system == "Darwin":
        try:
            result = subprocess.run(
                ["launchctl", "list", PLIST_LABEL],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Parse PID from output
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if "PID" in line:
                        pid = line.split("=")[-1].strip().rstrip(";")
                        return {"running": True, "pid": pid, "method": "launchd"}
                return {"running": True, "method": "launchd"}
            return {"running": False, "method": "launchd"}
        except Exception:
            return {"running": False, "method": "unknown"}
    
    elif system == "Linux":
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", SYSTEMD_UNIT],
                capture_output=True, text=True, timeout=5
            )
            return {
                "running": result.stdout.strip() == "active",
                "method": "systemd",
            }
        except Exception:
            return {"running": False, "method": "unknown"}
    
    return {"running": False, "method": "unknown"}
