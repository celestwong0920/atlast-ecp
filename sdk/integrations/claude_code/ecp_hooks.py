"""
ECP — Claude Code Plugin (Hook-based passive recording)

This plugin hooks into Claude Code's PreToolUse and PostToolUse events
to passively record all tool calls as ECP evidence.

Installation:
    npx atlast-ecp install
    → auto-writes ~/.claude/plugins/atlast_ecp.py

How it works:
    PreToolUse  → record in_hash (tool name + input)
    PostToolUse → record out_hash (output) + latency + flags
    Records are chained and stored in local .ecp/ directory.
"""

import json
import sys
import time
import threading
from pathlib import Path

# ECP SDK path — injected by installer
_ECP_SDK_PATH = Path.home() / ".atlast" / "sdk"
if _ECP_SDK_PATH.exists() and str(_ECP_SDK_PATH) not in sys.path:
    sys.path.insert(0, str(_ECP_SDK_PATH))

# In-flight tracking (PreToolUse → PostToolUse correlation)
_in_flight: dict[str, dict] = {}
_lock = threading.Lock()


def _get_ecp():
    """Lazy import ECP SDK (fails silently if not installed)."""
    try:
        from atlast_ecp.identity import get_or_create_identity
        from atlast_ecp.record import create_record, record_to_dict, hash_content
        from atlast_ecp.storage import save_record
        from atlast_ecp.signals import detect_flags
        return {
            "get_identity": get_or_create_identity,
            "create_record": create_record,
            "record_to_dict": record_to_dict,
            "hash_content": hash_content,
            "save_record": save_record,
            "detect_flags": detect_flags,
        }
    except ImportError:
        return None


# Shared state
_identity = None
_last_record = None


def _ensure_identity():
    global _identity
    if _identity is None:
        ecp = _get_ecp()
        if ecp:
            _identity = ecp["get_identity"]()
    return _identity


# ─── Claude Code Hook Entry Points ───────────────────────────────────────────

def pre_tool_use(tool_name: str, tool_input: dict) -> dict:
    """
    Called by Claude Code BEFORE a tool is executed.
    Records the input hash and stores start time for latency tracking.
    Returns the tool_input unchanged (pass-through).
    """
    call_id = f"{tool_name}_{time.time_ns()}"

    try:
        ecp = _get_ecp()
        if not ecp:
            return tool_input

        in_content = {"tool": tool_name, "input": tool_input}
        in_hash = ecp["hash_content"](in_content)

        with _lock:
            _in_flight[call_id] = {
                "tool_name": tool_name,
                "in_content": in_content,
                "in_hash": in_hash,
                "t_start": time.time(),
            }
    except Exception:
        pass  # Fail-Open

    # Tag the call_id into tool_input metadata (for correlation in PostToolUse)
    # This is a Claude Code convention — __ecp_call_id is stripped before execution
    return {**tool_input, "__ecp_call_id": call_id}


def post_tool_use(tool_name: str, tool_input: dict, tool_result: str) -> str:
    """
    Called by Claude Code AFTER a tool is executed.
    Records the output hash, latency, and behavioral flags.
    Returns the tool_result unchanged (pass-through).
    """
    try:
        ecp = _get_ecp()
        if not ecp:
            return tool_result

        call_id = tool_input.pop("__ecp_call_id", None)

        with _lock:
            in_flight = _in_flight.pop(call_id, None) if call_id else None

        if not in_flight:
            # Fallback: record without correlation
            in_flight = {
                "tool_name": tool_name,
                "in_content": {"tool": tool_name, "input": tool_input},
                "t_start": time.time(),
            }

        latency_ms = int((time.time() - in_flight["t_start"]) * 1000)
        flags = ecp["detect_flags"](str(tool_result))

        def _do_record():
            global _last_record
            try:
                identity = _ensure_identity()
                if not identity:
                    return

                record = ecp["create_record"](
                    agent_did=identity["did"],
                    step_type="tool_call",
                    in_content=in_flight["in_content"],
                    out_content=tool_result,
                    identity=identity,
                    prev_record=_last_record,
                    model=None,          # Tool calls have no model
                    tokens_in=None,
                    tokens_out=None,
                    latency_ms=latency_ms,
                    flags=flags,
                )
                ecp["save_record"](ecp["record_to_dict"](record))
                _last_record = record
            except Exception:
                pass  # Fail-Open

        threading.Thread(target=_do_record, daemon=True).start()

    except Exception:
        pass  # Fail-Open

    return tool_result
