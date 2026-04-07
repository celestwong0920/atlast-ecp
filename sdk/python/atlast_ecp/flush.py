"""
ATLAST ECP — Buffer flush utility.

Flushes Claude Code hook buffers into ECP records.
Called by: dashboard server, CLI commands, hook script.

Design: any code path that READS records should flush stale buffers first,
so the user always sees complete data.
"""

import json
import logging
import time
from pathlib import Path

_logger = logging.getLogger(__name__)

def flush_stale_buffers(timeout_s: int = 0) -> int:
    """
    Flush Claude Code hook buffers that belong to CLOSED sessions.

    A session is considered closed if NO Claude Code process is using it.
    We detect this by checking if the session's Claude Code process is still alive.

    If timeout_s > 0, also flush buffers older than timeout_s (legacy behavior).
    Default: timeout_s=0 means only flush truly closed sessions.

    Safe to call frequently — no-op if no stale buffers exist.
    Fail-Open: never raises, never blocks.
    """
    from .storage import ECP_DIR
    import subprocess

    buffer_dir = ECP_DIR / "hook_buffer"
    if not buffer_dir.exists():
        return 0

    flushed = 0
    now = time.time()

    # Get list of active Claude Code session IDs by checking running processes
    active_sessions = set()
    try:
        # Check which Claude Code sessions are still running
        # Claude Code processes have their session ID in the transcript path
        result = subprocess.run(
            ["pgrep", "-a", "claude"], capture_output=True, text=True, timeout=5
        )
        # If Claude Code is running, consider ALL buffers potentially active
        if result.stdout.strip():
            active_sessions.add("__claude_running__")
    except Exception:
        pass

    for session_file in buffer_dir.glob("*.json"):
        try:
            buf = json.loads(session_file.read_text())
            last_update = buf.get("last_update", 0)
            age = now - last_update

            # If Claude Code is running, only flush buffers older than 1 hour
            # (these are definitely from a previous session that's done)
            if "__claude_running__" in active_sessions:
                if age < 3600:  # Less than 1 hour — might be active
                    continue
            elif timeout_s > 0 and age < timeout_s:
                continue

            steps = buf.get("steps", [])
            if not steps:
                session_file.unlink(missing_ok=True)
                continue

            # Build aggregated record
            tool_names = [s.get("tool_name", "?") for s in steps]
            tool_summary = {}
            for name in tool_names:
                tool_summary[name] = tool_summary.get(name, 0) + 1
            summary_str = ", ".join(f"{name} x{count}" for name, count in tool_summary.items())

            # Try to read Claude Code transcript for real user message + agent response + model
            user_input = None
            agent_response = None
            transcript_model = None
            transcript_path = buf.get("transcript_path", "")
            message_index = buf.get("user_message_count", 1) - 1  # 0-based index
            if transcript_path:
                try:
                    from pathlib import Path as _Path
                    tp = _Path(transcript_path)
                    if tp.exists():
                        entries = []
                        for tl in tp.read_text().splitlines():
                            if tl.strip():
                                try: entries.append(json.loads(tl))
                                except: pass

                        # Collect real user messages (text, not tool_results, not system tags)
                        user_msgs = []
                        for i, e in enumerate(entries):
                            if e.get("type") == "user":
                                c = e.get("message", {}).get("content", "")
                                if isinstance(c, str) and len(c.strip()) > 0 and not c.startswith("<"):
                                    user_msgs.append({"idx": i, "text": c})

                        # Match by index: the Nth user message corresponds to the Nth conversation
                        if 0 <= message_index < len(user_msgs):
                            um = user_msgs[message_index]
                            next_idx = user_msgs[message_index + 1]["idx"] if message_index + 1 < len(user_msgs) else len(entries)
                            user_input = um["text"][:1000]
                            # Find last assistant response + model in this block
                            for i in range(next_idx - 1, um["idx"], -1):
                                e = entries[i]
                                if e.get("type") == "assistant":
                                    msg = e.get("message", {})
                                    if not transcript_model:
                                        transcript_model = msg.get("model")
                                    content = msg.get("content", [])
                                    if isinstance(content, list) and not agent_response:
                                        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                                        if texts:
                                            agent_response = "\n".join(texts)[:3000]
                                    if agent_response and transcript_model:
                                        break
                except Exception:
                    pass

            # Fallback: use tool data if transcript not available
            first_input = user_input or ""
            if not first_input:
                for s in steps:
                    inp = s.get("tool_input_str", "")
                    if inp and len(inp) > 10:
                        first_input = inp[:500]
                        break

            last_output = agent_response or ""
            if not last_output:
                for s in reversed(steps):
                    out = s.get("tool_response", "")
                    if out and len(str(out)) > 5:
                        last_output = str(out)[:3000]
                        break

            total_latency = sum(s.get("duration_ms", 0) for s in steps)

            output_json = json.dumps({
                "final_response": last_output or f"Completed {len(steps)} actions: {summary_str}",
                "tool_calls_used": [
                    {"name": s.get("tool_name", "?"), "input": s.get("tool_input", {})}
                    for s in steps
                ],
                "steps": len(steps),
            }, ensure_ascii=False)

            from .core import record_minimal
            record_minimal(
                input_content=first_input or f"Claude Code session ({summary_str})",
                output_content=output_json,
                agent="claude-code",
                action="session",
                model=transcript_model or "claude",
                latency_ms=total_latency,
            )

            session_file.unlink(missing_ok=True)
            flushed += 1
            _logger.debug("Flushed %d steps from %s", len(steps), session_file.name)

        except Exception as e:
            _logger.debug("flush_stale_buffers error on %s: %s", session_file, e)
            continue

    return flushed


def flush_all_buffers() -> int:
    """Force flush ALL buffers regardless of age. Used before displaying data."""
    return flush_stale_buffers(timeout_s=0)
