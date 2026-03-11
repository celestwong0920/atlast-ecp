"""
ECP — OpenClaw Plugin (tool_result_persist hook)

Passively records all OpenClaw tool results as ECP evidence.
Uses OpenClaw's tool_result_persist Plugin API.

Installation:
    openclaw plugin add atlast/ecp
    (or via join.md one-sentence flow)

How it works:
    OpenClaw fires `on_tool_result` after every tool execution.
    This plugin intercepts that event, hashes input+output,
    and saves an ECP record locally.
    Content NEVER leaves the device.
"""

import json
import time
import threading
from typing import Optional

# ECP SDK imports (installed via pip install atlast-ecp)
try:
    from atlast_ecp.identity import get_or_create_identity
    from atlast_ecp.record import create_record, record_to_dict, hash_content
    from atlast_ecp.storage import save_record
    from atlast_ecp.signals import detect_flags
    _ECP_AVAILABLE = True
except ImportError:
    _ECP_AVAILABLE = False


# ─── OpenClaw Plugin Metadata ─────────────────────────────────────────────────

PLUGIN_NAME = "atlast-ecp"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = "ATLAST ECP — passive evidence chain recording for OpenClaw agents"
PLUGIN_HOOKS = ["tool_result_persist", "session_end"]

# ─── Plugin State ─────────────────────────────────────────────────────────────

_identity = None
_last_record = None
_session_records = []
_lock = threading.Lock()


def _ensure_identity():
    global _identity
    if _identity is None and _ECP_AVAILABLE:
        _identity = get_or_create_identity()
    return _identity


# ─── OpenClaw Hook: tool_result_persist ───────────────────────────────────────

def on_tool_result(
    tool_name: str,
    tool_input: dict,
    tool_result: str,
    latency_ms: Optional[int] = None,
    session_id: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Called by OpenClaw after every tool execution.
    Records the tool call as an ECP evidence record.
    Returns tool_result unchanged (pass-through).

    This is the primary passive recording hook for OpenClaw agents.
    """
    if not _ECP_AVAILABLE:
        return tool_result

    def _do_record():
        global _last_record
        try:
            identity = _ensure_identity()
            if not identity:
                return

            in_content = {
                "tool": tool_name,
                "input": tool_input,
                "session_id": session_id,
            }
            out_text = str(tool_result)
            flags = detect_flags(out_text, latency_ms=latency_ms)

            record = create_record(
                agent_did=identity["did"],
                step_type="turn",   # OpenClaw = turn-level recording (ECP-SPEC §3.1)
                in_content=in_content,
                out_content=out_text,
                identity=identity,
                prev_record=_last_record,
                model=kwargs.get("model"),
                tokens_in=kwargs.get("tokens_in"),
                tokens_out=kwargs.get("tokens_out"),
                latency_ms=latency_ms or 0,
                flags=flags,
            )
            record_dict = record_to_dict(record)
            save_record(record_dict)

            with _lock:
                _last_record = record
                _session_records.append(record_dict["id"])

        except Exception:
            pass  # Fail-Open: recording failure NEVER affects the agent

    threading.Thread(target=_do_record, daemon=True).start()
    return tool_result


# ─── OpenClaw Hook: session_end ───────────────────────────────────────────────

def on_session_end(session_id: Optional[str] = None, **kwargs):
    """
    Called by OpenClaw when a session ends.
    Flushes any pending records to ensure they're saved before shutdown.
    Also triggers Merkle Root batch upload if configured.
    """
    if not _ECP_AVAILABLE:
        return

    try:
        # Give background threads time to finish
        time.sleep(0.5)

        # Trigger batch upload (non-blocking)
        from atlast_ecp.batch import trigger_batch_upload
        trigger_batch_upload(flush=True)

    except Exception:
        pass  # Fail-Open


# ─── Plugin Registration (OpenClaw Plugin API) ────────────────────────────────

def register(openclaw_api):
    """
    Register ECP hooks with OpenClaw's Plugin API.
    Called automatically by: openclaw plugin add atlast/ecp
    """
    if not _ECP_AVAILABLE:
        print("⚠️  atlast-ecp SDK not found. Run: pip install atlast-ecp")
        return False

    try:
        openclaw_api.on("tool_result_persist", on_tool_result)
        openclaw_api.on("session_end", on_session_end)

        identity = _ensure_identity()
        if identity:
            print(f"✅ ATLAST ECP active | Agent: {identity['did']}")
            print(f"   Evidence chain: .ecp/ (local, private)")
            print(f"   Register at: https://llachat.com")
        return True

    except Exception as e:
        print(f"⚠️  ECP plugin registration failed (non-fatal): {e}")
        return False


def get_agent_did() -> Optional[str]:
    """Return the current agent's DID."""
    identity = _ensure_identity()
    return identity["did"] if identity else None


def get_session_record_ids() -> list[str]:
    """Return all record IDs created in this session."""
    with _lock:
        return list(_session_records)
