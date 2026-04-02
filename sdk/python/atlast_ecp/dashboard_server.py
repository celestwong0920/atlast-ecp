"""
ATLAST ECP Local Dashboard Server.

Serves a web UI on localhost for visual record exploration.
All data stays local — reads from ~/.ecp/ SQLite index.

Usage: atlast dashboard [--port 3827] [--no-open]
"""

import json
import os
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ASSETS_DIR = Path(__file__).parent / "dashboard_assets"
DEFAULT_PORT = 3827


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the local dashboard."""

    def log_message(self, format, *args):
        """Suppress default request logging."""
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # API routes
        if path.startswith("/api/"):
            self._handle_api(path, params)
            return

        # Static files
        if path == "/" or path == "/index.html":
            self._serve_file("index.html", "text/html")
        elif path.endswith(".js"):
            self._serve_file(path.lstrip("/"), "application/javascript")
        elif path.endswith(".css"):
            self._serve_file(path.lstrip("/"), "text/css")
        else:
            self._serve_file("index.html", "text/html")

    def _serve_file(self, filename: str, content_type: str):
        filepath = (ASSETS_DIR / filename).resolve()
        # Prevent path traversal — file must be under ASSETS_DIR
        if not str(filepath).startswith(str(ASSETS_DIR.resolve())):
            self.send_error(403, "Forbidden")
            return
        if not filepath.exists():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    def _handle_api(self, path: str, params: dict):
        try:
            result = self._dispatch_api(path, params)
            self._json_response(200, result)
        except Exception as e:
            self._json_response(500, {"error": str(e)})

    def _dispatch_api(self, path: str, params: dict) -> dict:
        from .query import search, trace, audit, timeline, rebuild_index

        # ── Vault: raw input/output for a record ──
        if path.startswith("/api/vault/"):
            record_id = path.split("/api/vault/")[1]
            if not record_id:
                return {"error": "record_id required"}
            from .storage import ECP_DIR
            vault_file = ECP_DIR / "vault" / f"{record_id}.json"
            if not vault_file.exists():
                return {
                    "error": f"Vault file not found for {record_id}",
                    "hint": "Raw content is only stored when using wrap() or record(). Callback adapters may not store vault data.",
                    "vault_path": str(vault_file),
                }
            try:
                vault_data = json.loads(vault_file.read_text())
            except Exception as exc:
                return {"error": f"Failed to read vault: {exc}"}
            # Truncate very long content for display
            for key in ("input", "output"):
                val = vault_data.get(key, "")
                if isinstance(val, str) and len(val) > 10000:
                    vault_data[key] = val[:10000] + f"\n\n... (truncated, full content: {len(val)} chars)"
            vault_data["_vault_path"] = str(vault_file)
            vault_data["_ecp_dir"] = str(ECP_DIR)
            return vault_data

        # ── Guide: onboarding info for new users ──
        if path == "/api/guide":
            from .storage import ECP_DIR, RECORDS_DIR, VAULT_DIR
            from .identity import get_or_create_identity
            try:
                identity = get_or_create_identity()
                did = identity.get("did", "unknown")
            except Exception:
                did = "not initialized"
            record_files = sorted(RECORDS_DIR.glob("*.jsonl")) if RECORDS_DIR.exists() else []
            vault_count = len(list(VAULT_DIR.iterdir())) if VAULT_DIR.exists() else 0
            return {
                "welcome": "Welcome to ATLAST ECP Dashboard — your AI agent's evidence chain viewer.",
                "what_is_this": "Every time your AI agent makes an LLM call, ECP records a tamper-proof evidence trail locally on your machine.",
                "your_agent": {
                    "did": did,
                    "explanation": "This is your agent's unique identity (DID). All evidence records are tied to this ID."
                },
                "your_data": {
                    "ecp_dir": str(ECP_DIR),
                    "records_dir": str(RECORDS_DIR),
                    "vault_dir": str(VAULT_DIR),
                    "record_files": [str(f) for f in record_files],
                    "vault_files_count": vault_count,
                    "explanation": "Records contain hashed metadata (no raw content). Vault stores the original input/output locally."
                },
                "how_to_use": {
                    "step_1": "📊 Stats — See total records, reliability score, chain integrity",
                    "step_2": "📅 Timeline — View daily activity trends (records per day, error rates)",
                    "step_3": "🔍 Search — Find specific records by type, model, or flags",
                    "step_4": "🔗 Trace — Click any record to see its full chain (each record links to the previous one)",
                    "step_5": "📋 Audit — Get a 30-day health report of your agent's behavior",
                    "step_6": "👁️ Vault — Click a record to see the original AI input/output (stored locally, never uploaded)"
                },
                "cli_commands": {
                    "atlast stats": "View trust signals summary",
                    "atlast log": "See latest records",
                    "atlast timeline": "Daily activity breakdown",
                    "atlast push": "Upload records to server for on-chain anchoring",
                    "atlast verify": "Verify a record's chain integrity",
                    "atlast export": "Export all records as JSON"
                },
                "privacy": "All data stays on your machine. The vault (raw AI conversations) never leaves your device unless you explicitly push."
            }

        if path == "/api/search":
            query = params.get("q", [""])[0]
            limit = int(params.get("limit", ["20"])[0])
            errors_only = params.get("errors", [""])[0] == "1"
            agent = params.get("agent", [None])[0]
            since = params.get("since", [None])[0]
            until = params.get("until", [None])[0]
            results = search(query, limit=limit, agent=agent, since=since,
                             until=until, errors_only=errors_only, as_json=True)
            return {"results": results, "count": len(results)}

        elif path == "/api/trace":
            record_id = params.get("id", [""])[0]
            direction = params.get("dir", ["back"])[0]
            if not record_id:
                return {"error": "id parameter required"}
            chain = trace(record_id, direction=direction, as_json=True)
            return {"chain": chain, "depth": len(chain)}

        elif path == "/api/audit":
            days = int(params.get("days", ["30"])[0])
            agent = params.get("agent", [None])[0]
            return audit(days=days, agent=agent, as_json=True)

        elif path == "/api/timeline":
            days = int(params.get("days", ["30"])[0])
            agent = params.get("agent", [None])[0]
            results = timeline(days=days, agent=agent, as_json=True)
            return {"timeline": results}

        elif path == "/api/index":
            count = rebuild_index()
            return {"indexed": count}

        elif path == "/api/stats":
            from .storage import count_records, ECP_DIR, RECORDS_DIR, VAULT_DIR
            from .identity import get_or_create_identity
            try:
                identity = get_or_create_identity()
                did = identity.get("did", "unknown")
            except Exception:
                did = "not initialized"
            # Count vault files
            vault_count = 0
            if VAULT_DIR.exists():
                vault_count = len(list(VAULT_DIR.iterdir()))
            # Count record files for session approximation
            record_files = []
            if RECORDS_DIR.exists():
                record_files = sorted(RECORDS_DIR.glob("*.jsonl"))
            return {
                "total_records": count_records(),
                "agent_did": did,
                "ecp_dir": str(ECP_DIR),
                "vault_count": vault_count,
                "record_files": [f.name for f in record_files],
                "active_days": len(record_files),
                "has_vault": vault_count > 0,
            }

        return {"error": f"Unknown API: {path}"}

    def _json_response(self, status: int, data: dict):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def start_dashboard(port: int = DEFAULT_PORT, open_browser: bool = True):
    """Start the local dashboard server."""
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}"

    print("\n  📊 ATLAST ECP Dashboard")
    print(f"  Running at: {url}")
    print("  Data: ~/.ecp/ (local only, nothing leaves your machine)")
    print("  Press Ctrl+C to stop\n")

    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Dashboard stopped.")
        server.server_close()
