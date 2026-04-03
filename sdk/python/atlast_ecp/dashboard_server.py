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
        data = filepath.read_bytes()
        # Inject enhancement script into index.html
        if filename == "index.html":
            data = self._inject_enhancements(data)
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _inject_enhancements(self, html_bytes: bytes) -> bytes:
        """Inject vault viewer, guidance banner, and UX enhancements."""
        enhancement_script = _get_enhancement_script()
        html = html_bytes.decode("utf-8")
        html = html.replace("</body>", f"{enhancement_script}\n</body>")
        return html.encode("utf-8")

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


def _get_enhancement_script() -> str:
    """Return the JS/CSS enhancement script injected into index.html."""
    return '''<style>
/* === ATLAST Dashboard Enhancements === */
#atlast-guide-banner {
  position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
  background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
  color: white; padding: 10px 20px; font-family: system-ui, sans-serif;
  display: flex; align-items: center; justify-content: space-between;
  font-size: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
#atlast-guide-banner a { color: #93c5fd; text-decoration: underline; cursor: pointer; }
#atlast-guide-banner .close-btn {
  background: rgba(255,255,255,0.2); border: none; color: white;
  padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 13px;
}
#atlast-guide-banner .close-btn:hover { background: rgba(255,255,255,0.3); }
body { padding-top: 44px !important; }
body.guide-dismissed { padding-top: 0 !important; }

/* Vault overlay */
#atlast-vault-overlay {
  display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6); z-index: 10000;
  justify-content: center; align-items: center;
}
#atlast-vault-overlay.visible { display: flex; }
#atlast-vault-panel {
  background: white; border-radius: 12px; padding: 24px; max-width: 800px;
  width: 90%; max-height: 80vh; overflow-y: auto; position: relative;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3); font-family: system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) {
  #atlast-vault-panel { background: #1e1e2e; color: #e0e0e0; }
}
#atlast-vault-panel .vault-close {
  position: absolute; top: 12px; right: 16px; background: none;
  border: none; font-size: 24px; cursor: pointer; color: #888;
}
#atlast-vault-panel h3 { margin: 0 0 16px; font-size: 18px; color: #1e40af; }
#atlast-vault-panel .vault-section {
  margin: 12px 0; padding: 12px; border-radius: 8px;
  background: #f8fafc; border: 1px solid #e2e8f0;
}
@media (prefers-color-scheme: dark) {
  #atlast-vault-panel .vault-section { background: #2a2a3e; border-color: #3a3a5e; }
}
#atlast-vault-panel .vault-section h4 {
  margin: 0 0 8px; font-size: 13px; text-transform: uppercase;
  letter-spacing: 0.5px; color: #64748b;
}
#atlast-vault-panel .vault-content {
  white-space: pre-wrap; word-break: break-word; font-size: 14px;
  line-height: 1.6; max-height: 200px; overflow-y: auto;
}
#atlast-vault-panel .vault-path {
  font-family: monospace; font-size: 12px; color: #64748b;
  background: #f1f5f9; padding: 6px 10px; border-radius: 4px;
  margin-top: 12px; word-break: break-all;
}
@media (prefers-color-scheme: dark) {
  #atlast-vault-panel .vault-path { background: #2a2a3e; color: #94a3b8; }
}

/* Floating help button */
#atlast-help-btn {
  position: fixed; bottom: 20px; right: 20px; z-index: 9998;
  width: 48px; height: 48px; border-radius: 50%;
  background: linear-gradient(135deg, #1e40af, #7c3aed);
  color: white; border: none; font-size: 22px; cursor: pointer;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  display: flex; align-items: center; justify-content: center;
}
#atlast-help-btn:hover { transform: scale(1.1); }
#atlast-help-panel {
  display: none; position: fixed; bottom: 80px; right: 20px; z-index: 9998;
  background: white; border-radius: 12px; padding: 20px; width: 320px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.2); font-family: system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) {
  #atlast-help-panel { background: #1e1e2e; color: #e0e0e0; }
}
#atlast-help-panel.visible { display: block; }
#atlast-help-panel h4 { margin: 0 0 12px; font-size: 16px; }
#atlast-help-panel .help-item {
  padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; line-height: 1.5;
}
#atlast-help-panel .help-item:last-child { border-bottom: none; }
#atlast-help-panel .help-item b { color: #1e40af; }

/* Vault click hint on record rows */
[data-record-id] { cursor: pointer; }
[data-record-id]:hover { background: rgba(30, 64, 175, 0.05) !important; }
</style>

<div id="atlast-guide-banner">
  <span>
    📊 <b>ATLAST ECP Dashboard</b> — Your AI agent's evidence chain viewer.
    All data stays on your machine.
    <a id="guide-learn-more">Learn how to use →</a>
  </span>
  <button class="close-btn" id="guide-dismiss">✕ Dismiss</button>
</div>

<div id="atlast-vault-overlay">
  <div id="atlast-vault-panel">
    <button class="vault-close" id="vault-close">×</button>
    <h3 id="vault-title">Loading...</h3>
    <div id="vault-body"></div>
  </div>
</div>

<button id="atlast-help-btn" title="Help & Guide">?</button>
<div id="atlast-help-panel">
  <h4>📖 Quick Guide</h4>
  <div class="help-item"><b>📊 Stats</b> — Total records, reliability score, active days</div>
  <div class="help-item"><b>🔍 Search</b> — Find records by model, type, or flags. <em>Click any row to see full AI input/output.</em></div>
  <div class="help-item"><b>📅 Timeline</b> — Daily activity trends and error rates</div>
  <div class="help-item"><b>🔗 Trace</b> — Follow the chain: each record links to the previous one</div>
  <div class="help-item"><b>📋 Audit</b> — 30-day health report of your agent</div>
  <div class="help-item"><b>🔐 Privacy</b> — All data stays on your machine. The vault (raw conversations) never leaves your device.</div>
  <div class="help-item" style="margin-top:8px; font-size:12px; color:#64748b;">
    Data dir: <code id="help-ecp-dir">~/.ecp/</code>
  </div>
</div>

<script>
(function() {
  "use strict";

  // === Guide Banner ===
  const banner = document.getElementById("atlast-guide-banner");
  const dismissed = localStorage.getItem("atlast-guide-dismissed");
  if (dismissed) {
    banner.style.display = "none";
    document.body.classList.add("guide-dismissed");
  }
  document.getElementById("guide-dismiss").onclick = function() {
    banner.style.display = "none";
    document.body.classList.add("guide-dismissed");
    localStorage.setItem("atlast-guide-dismissed", "1");
  };
  document.getElementById("guide-learn-more").onclick = function() {
    document.getElementById("atlast-help-panel").classList.toggle("visible");
  };

  // === Help Button ===
  document.getElementById("atlast-help-btn").onclick = function() {
    document.getElementById("atlast-help-panel").classList.toggle("visible");
  };

  // Fetch ECP dir for help panel
  fetch("/api/stats").then(r => r.json()).then(data => {
    if (data.ecp_dir) {
      document.getElementById("help-ecp-dir").textContent = data.ecp_dir;
    }
  }).catch(() => {});

  // === Vault Overlay ===
  const overlay = document.getElementById("atlast-vault-overlay");
  const vaultTitle = document.getElementById("vault-title");
  const vaultBody = document.getElementById("vault-body");

  document.getElementById("vault-close").onclick = closeVault;
  overlay.onclick = function(e) { if (e.target === overlay) closeVault(); };
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") closeVault();
  });

  function closeVault() {
    overlay.classList.remove("visible");
  }

  function openVault(recordId) {
    vaultTitle.textContent = "Loading vault...";
    vaultBody.innerHTML = "";
    overlay.classList.add("visible");

    fetch("/api/vault/" + recordId)
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          vaultTitle.textContent = "⚠️ Vault Not Available";
          vaultBody.innerHTML =
            '<div class="vault-section"><div class="vault-content">' +
            escapeHtml(data.error) +
            (data.hint ? "<br><br><em>" + escapeHtml(data.hint) + "</em>" : "") +
            "</div></div>" +
            (data.vault_path ? '<div class="vault-path">Expected path: ' + escapeHtml(data.vault_path) + "</div>" : "");
          return;
        }

        vaultTitle.textContent = "🔍 Record: " + recordId;

        var html = "";
        // Input section
        html += '<div class="vault-section"><h4>📥 Input (what was sent to AI)</h4>';
        html += '<div class="vault-content">' + formatVaultContent(data.input) + "</div></div>";

        // Output section
        html += '<div class="vault-section"><h4>📤 Output (AI response)</h4>';
        html += '<div class="vault-content">' + formatVaultContent(data.output) + "</div></div>";

        // Metadata (other fields)
        var metaKeys = Object.keys(data).filter(function(k) {
          return k !== "input" && k !== "output" && k !== "_vault_path" && k !== "_ecp_dir" && k !== "record_id";
        });
        if (metaKeys.length > 0) {
          html += '<div class="vault-section"><h4>📋 Metadata</h4>';
          html += '<div class="vault-content">';
          metaKeys.forEach(function(k) {
            html += "<b>" + escapeHtml(k) + ":</b> " + escapeHtml(JSON.stringify(data[k])) + "<br>";
          });
          html += "</div></div>";
        }

        // File path
        if (data._vault_path) {
          html += '<div class="vault-path">📁 Local file: ' + escapeHtml(data._vault_path) + "</div>";
        }
        if (data._ecp_dir) {
          html += '<div class="vault-path">📂 ECP directory: ' + escapeHtml(data._ecp_dir) + "</div>";
        }

        vaultBody.innerHTML = html;
      })
      .catch(function(err) {
        vaultTitle.textContent = "❌ Error";
        vaultBody.innerHTML = '<div class="vault-section"><div class="vault-content">Failed to load vault: ' + escapeHtml(String(err)) + "</div></div>";
      });
  }

  function escapeHtml(str) {
    if (str == null) return "(empty)";
    str = String(str);
    return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function formatVaultContent(val) {
    if (val == null) return "<em>(no content recorded)</em>";
    if (typeof val === "object") {
      try { return escapeHtml(JSON.stringify(val, null, 2)); } catch(e) {}
    }
    return escapeHtml(String(val));
  }

  // === Click Interception: watch for record IDs in the DOM ===
  // Use MutationObserver to attach click handlers to record rows
  function attachVaultClicks() {
    // Look for elements containing record IDs (rec_xxx pattern)
    document.querySelectorAll("tr, [class*='row'], [class*='card'], [class*='item']").forEach(function(el) {
      if (el._atlastBound) return;
      var text = el.textContent || "";
      var match = text.match(/\\b(rec_[a-f0-9]{16,})\\b/);
      if (match) {
        el._atlastBound = true;
        el.setAttribute("data-record-id", match[1]);
        el.title = "Click to view full AI input/output";
        el.addEventListener("click", function(e) {
          // Don't intercept clicks on links or buttons
          if (e.target.tagName === "A" || e.target.tagName === "BUTTON") return;
          e.preventDefault();
          e.stopPropagation();
          openVault(match[1]);
        });
      }
    });
  }

  // Run on load and observe DOM changes
  var observer = new MutationObserver(function() {
    setTimeout(attachVaultClicks, 100);
  });
  observer.observe(document.body, { childList: true, subtree: true });
  setTimeout(attachVaultClicks, 500);
  setTimeout(attachVaultClicks, 2000);

  // Also make window.openVault available for manual use
  window.atlastOpenVault = openVault;

  console.log("[ATLAST] Dashboard enhancements loaded. Click any record to view vault content.");
})();
</script>'''


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
