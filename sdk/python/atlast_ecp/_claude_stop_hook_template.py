"""ATLAST ECP — Claude Code Stop hook (v2, turn-accurate).

Fires after every Claude Code response. Records the LATEST turn only:
  - User message (since previous user message or session start)
  - All assistant text + tool calls + tool results in between
  - Full token/cache/context metrics
  - Subagents *started in this turn only* (timestamp-filtered)

All data flows into record_minimal_v2() with vault_extra for rich audit.
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Make atlast_ecp importable (works for dev checkout + pip install)
_DEV_SRC = "/Users/seacapital/Desktop/atlast-ecp/sdk/python"
if os.path.isdir(_DEV_SRC) and _DEV_SRC not in sys.path:
    sys.path.insert(0, _DEV_SRC)

LOG_FILE = Path.home() / ".ecp" / "hook_debug.log"


def _log(msg):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _parse_iso(ts):
    """Parse ISO 8601 timestamp, return None on failure. Accepts '...Z' format."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _find_transcript(data):
    """Locate current session transcript. Prefers hook-data session_id."""
    tp = data.get("transcript_path")
    if tp and Path(tp).exists():
        return Path(tp)

    sid = data.get("session_id")
    if sid:
        claude_dir = Path.home() / ".claude" / "projects"
        if claude_dir.exists():
            for f in claude_dir.rglob(f"{sid}.jsonl"):
                if f.exists() and f.stat().st_size > 50:
                    return f

    # Fallback: most-recent session file
    claude_dir = Path.home() / ".claude" / "projects"
    if not claude_dir.exists():
        return None
    candidates = []
    for f in claude_dir.rglob("*.jsonl"):
        if "/subagents/" in str(f) or f.name == "history.jsonl":
            continue
        try:
            if f.stat().st_size > 50:
                candidates.append(f)
        except Exception:
            pass
    if not candidates:
        return None
    candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return candidates[0]


def _read_jsonl(path):
    """Parse JSONL file into list of dicts, silently skipping malformed lines."""
    out = []
    try:
        for line in path.read_text().splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return out


def _extract_user_text(entry):
    """Get plain user text from a transcript entry. Returns '' for tool-result carriers."""
    c = entry.get("message", {}).get("content", "")
    if isinstance(c, str):
        return c.strip() if not c.startswith("<") else ""
    if isinstance(c, list):
        # Skip entries whose content is purely tool_result (those aren't real user turns)
        has_text = any(
            isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()
            for b in c
        )
        if not has_text:
            return ""
        texts = [
            b.get("text", "")
            for b in c
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        combined = " ".join(texts).strip()
        return combined if not combined.startswith("<") else ""
    return ""


def _tool_input_preview(name, inp):
    """Return a short human-readable preview of a tool invocation's input."""
    if not isinstance(inp, dict):
        return str(inp)[:200]
    key = {
        "Bash": "command", "bash": "command",
        "Read": "file_path", "read": "file_path",
        "Edit": "file_path", "edit": "file_path",
        "Write": "file_path", "write": "file_path",
        "Grep": "pattern", "grep": "pattern",
        "Glob": "pattern", "glob": "pattern",
        "WebFetch": "url",
        "WebSearch": "query",
    }.get(name)
    if key and key in inp:
        return str(inp[key])[:300]
    return json.dumps(inp)[:300]


def _tool_result_text(result):
    """Normalize a tool_result content field to a short string."""
    if isinstance(result, list):
        return " ".join(
            b.get("text", "") for b in result if isinstance(b, dict)
        )
    return str(result or "")


def _extract_turn(entries, last_user_idx):
    """Walk entries from last_user_idx+1 until next user turn; collect everything.

    Returns dict with: narrative, tool_calls, tokens (in/out/cache_read/cache_creation),
    context_length_peak, last_model, first_ts, last_ts.
    """
    narrative_parts = []
    tool_calls = []
    pending_tool = {}  # tool_use_id -> {name, input}

    tokens_in = 0
    tokens_out = 0
    cache_read = 0
    cache_creation = 0
    context_peak = 0
    last_model = None
    first_ts = None
    last_ts = None

    for i in range(last_user_idx + 1, len(entries)):
        e = entries[i]
        etype = e.get("type", "")
        ts = e.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        # Stop at next real user message
        if etype == "user" and _extract_user_text(e):
            break

        if etype == "assistant":
            msg = e.get("message", {})
            if not last_model:
                last_model = msg.get("model")

            usage = msg.get("usage", {}) or {}
            ti = int(usage.get("input_tokens", 0) or 0)
            to = int(usage.get("output_tokens", 0) or 0)
            cr = int(usage.get("cache_read_input_tokens", 0) or 0)
            cc = int(usage.get("cache_creation_input_tokens", 0) or 0)
            tokens_in += ti
            tokens_out += to
            cache_read += cr
            cache_creation += cc
            # Peak context = total tokens in input side at this step
            ctx = ti + cr + cc
            if ctx > context_peak:
                context_peak = ctx

            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text = block.get("text", "")
                        if text.strip():
                            narrative_parts.append(text)
                    elif btype == "tool_use":
                        tid = block.get("id", "")
                        name = block.get("name", "?")
                        inp = block.get("input", {})
                        preview = _tool_input_preview(name, inp)
                        tc = {
                            "name": name,
                            "input": preview,
                            "input_full": json.dumps(inp)[:2000],
                            "result": "",
                            "ts": ts,
                        }
                        pending_tool[tid] = tc
                        tool_calls.append(tc)
                        narrative_parts.append(f"[{name}] {preview[:150]}")
            elif isinstance(content, str) and content.strip():
                narrative_parts.append(content)

        elif etype == "tool_result":
            tid = e.get("tool_use_id", "")
            result = _tool_result_text(e.get("content", ""))
            if tid in pending_tool:
                pending_tool[tid]["result"] = result[:1000]
                pending_tool.pop(tid, None)
            short = result[:250].replace("\n", " ")
            if short:
                narrative_parts.append(f"→ {short}")

        # user entries carrying only tool_results: capture their results too
        elif etype == "user":
            c = e.get("message", {}).get("content", "")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tid = b.get("tool_use_id", "")
                        result = _tool_result_text(b.get("content", ""))
                        if tid in pending_tool:
                            pending_tool[tid]["result"] = result[:1000]
                            pending_tool.pop(tid, None)
                        short = result[:250].replace("\n", " ")
                        if short:
                            narrative_parts.append(f"→ {short}")

    return {
        "narrative": "\n\n".join(narrative_parts) if narrative_parts else "(no response)",
        "tool_calls": tool_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_read": cache_read,
        "cache_creation": cache_creation,
        "context_peak": context_peak,
        "last_model": last_model,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def _extract_subagent(sa_file, turn_start_dt):
    """Parse a subagent JSONL. Return None if it started BEFORE turn_start_dt.

    Otherwise returns dict with prompt, narrative, tool_calls, tokens, model, etc.
    """
    entries = _read_jsonl(sa_file)
    if len(entries) < 2:
        return None

    first_ts = entries[0].get("timestamp")
    first_dt = _parse_iso(first_ts)
    if turn_start_dt and first_dt and first_dt < turn_start_dt:
        return None  # belongs to an older turn — SKIP

    prompt = None
    narrative_parts = []
    tool_calls = []
    pending = {}
    tokens_in = 0
    tokens_out = 0
    cache_read = 0
    cache_creation = 0
    context_peak = 0
    model = None

    for e in entries:
        etype = e.get("type")
        if etype == "user" and prompt is None:
            c = e.get("message", {}).get("content", "")
            if isinstance(c, str) and c.strip():
                prompt = c[:2000]
            elif isinstance(c, list):
                texts = [
                    b.get("text", "")
                    for b in c
                    if isinstance(b, dict) and b.get("type") == "text"
                ]
                if texts:
                    prompt = " ".join(texts)[:2000]

        if etype == "assistant":
            msg = e.get("message", {})
            if not model:
                model = msg.get("model")
            usage = msg.get("usage", {}) or {}
            tokens_in += int(usage.get("input_tokens", 0) or 0)
            tokens_out += int(usage.get("output_tokens", 0) or 0)
            cr = int(usage.get("cache_read_input_tokens", 0) or 0)
            cc = int(usage.get("cache_creation_input_tokens", 0) or 0)
            cache_read += cr
            cache_creation += cc
            ctx = int(usage.get("input_tokens", 0) or 0) + cr + cc
            if ctx > context_peak:
                context_peak = ctx

            content = msg.get("content", [])
            if isinstance(content, list):
                for b in content:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        tid = b.get("id", "")
                        name = b.get("name", "?")
                        inp = b.get("input", {})
                        preview = _tool_input_preview(name, inp)
                        tc = {
                            "name": name,
                            "input": preview,
                            "input_full": json.dumps(inp)[:2000],
                            "result": "",
                        }
                        pending[tid] = tc
                        tool_calls.append(tc)
                        narrative_parts.append(f"[{name}] {preview[:150]}")
                    elif b.get("type") == "text":
                        text = b.get("text", "")
                        if text.strip():
                            narrative_parts.append(text)
        elif etype == "user":
            c = e.get("message", {}).get("content", "")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tid = b.get("tool_use_id", "")
                        result = _tool_result_text(b.get("content", ""))
                        if tid in pending:
                            pending[tid]["result"] = result[:1000]
                            pending.pop(tid, None)

    if not prompt:
        return None

    # Try to enrich with meta.json
    meta_file = sa_file.parent / (sa_file.stem + ".meta.json")
    agent_type = None
    description = None
    if meta_file.exists():
        try:
            m = json.loads(meta_file.read_text())
            agent_type = m.get("agentType")
            description = m.get("description")
        except Exception:
            pass

    return {
        "prompt": prompt,
        "narrative": "\n\n".join(narrative_parts) if narrative_parts else "(no response)",
        "tool_calls": tool_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cache_read": cache_read,
        "cache_creation": cache_creation,
        "context_peak": context_peak,
        "model": model,
        "first_ts": first_ts,
        "agent_id": sa_file.stem.replace("agent-", ""),
        "agent_type": agent_type,
        "description": description,
    }


def _derive_agent_name(transcript_path):
    """Turn ~/.claude/projects/-Users-x-Desktop-my-agent/... into 'my-agent'."""
    try:
        project_dir = transcript_path.parent.name
        parts = [p for p in project_dir.split("-") if p and p != "Users"]
        for i, p in enumerate(parts):
            if p in ("Desktop", "Documents", "Projects", "repos", "code", "src", "home"):
                return "-".join(parts[i + 1 :]) or "claude-code"
        return parts[-1] if parts else "claude-code"
    except Exception:
        return "claude-code"


def main():
    _log("Stop hook v2 fired")

    # Read hook data from stdin
    try:
        data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
    except Exception:
        data = {}

    transcript_path = _find_transcript(data)
    if not transcript_path:
        _log("ERROR: no transcript found")
        return
    _log(f"Transcript: {transcript_path}")

    entries = _read_jsonl(transcript_path)
    if not entries:
        _log("ERROR: empty transcript")
        return
    _log(f"Entries: {len(entries)}")

    # Find last user message (= start of current turn)
    last_user_msg = None
    last_user_idx = -1
    last_user_ts = None
    for i in range(len(entries) - 1, -1, -1):
        e = entries[i]
        if e.get("type") == "user":
            text = _extract_user_text(e)
            if text:
                last_user_msg = text[:2000]
                last_user_idx = i
                last_user_ts = e.get("timestamp")
                break
    if not last_user_msg:
        _log("ERROR: no user message found")
        return

    turn_start_dt = _parse_iso(last_user_ts)
    _log(f"Turn start: {last_user_ts} | user: {last_user_msg[:60]!r}")

    # Extract the turn
    turn = _extract_turn(entries, last_user_idx)
    _log(
        f"Turn: {len(turn['tool_calls'])} tools, "
        f"tokens={turn['tokens_in']}/{turn['tokens_out']} "
        f"cache={turn['cache_read']}r/{turn['cache_creation']}c "
        f"ctx_peak={turn['context_peak']}"
    )

    # Dedup: same user message + same final-entry index = same turn, skip
    ecp_dir = Path(os.environ.get("ATLAST_ECP_DIR", str(Path.home() / ".ecp")))
    dedup_file = ecp_dir / "hook_buffer" / "_last_turn.json"
    dedup_file.parent.mkdir(parents=True, exist_ok=True)
    dedup_key = {
        "user": last_user_msg[:200],
        "entries": len(entries),
        "ts": last_user_ts,
    }
    if dedup_file.exists():
        try:
            prev = json.loads(dedup_file.read_text())
            if prev == dedup_key:
                _log("Dedup: this turn already recorded")
                return
        except Exception:
            pass

    session_id = transcript_path.stem
    agent_name = _derive_agent_name(transcript_path)

    # Find subagents started in THIS turn only
    sub_records = []
    session_dir = transcript_path.parent / transcript_path.stem
    subagent_dir = session_dir / "subagents"
    sub_total_tokens_in = 0
    sub_total_tokens_out = 0
    sub_total_tools = 0

    if subagent_dir.exists() and turn_start_dt:
        for sa_file in sorted(subagent_dir.glob("agent-*.jsonl")):
            sa = _extract_subagent(sa_file, turn_start_dt)
            if sa:
                sub_records.append(sa)
                sub_total_tokens_in += sa["tokens_in"]
                sub_total_tokens_out += sa["tokens_out"]
                sub_total_tools += len(sa["tool_calls"])
    _log(f"Subagents in this turn: {len(sub_records)} (filtered from dir)")

    # Latency
    latency_ms = 0
    try:
        latency_ms = int(data.get("duration_ms", 0))
    except (ValueError, TypeError):
        pass
    if latency_ms <= 0 or latency_ms > 86400000:
        # Fallback: compute from turn timestamps
        start = _parse_iso(turn["first_ts"])
        end = _parse_iso(turn["last_ts"])
        if start and end:
            latency_ms = int((end - start).total_seconds() * 1000)
        if latency_ms < 0:
            latency_ms = 0

    # Build vault_extra for the main record — the "dashcam footage"
    vault_extra = {
        "framework": "claude-code",
        "session_id": session_id,
        "turn_start_ts": last_user_ts,
        "model": turn["last_model"],
        "tokens_in": turn["tokens_in"],
        "tokens_out": turn["tokens_out"],
        "cache_read_input_tokens": turn["cache_read"],
        "cache_creation_input_tokens": turn["cache_creation"],
        "context_length_peak": turn["context_peak"],
        "latency_ms": latency_ms,
        "tool_call_count": len(turn["tool_calls"]),
        "tool_names": [t["name"] for t in turn["tool_calls"]],
        "tool_calls_used": [
            {"name": t["name"], "input": t["input"], "result": t["result"][:500]}
            for t in turn["tool_calls"]
        ],
        "subagent_count": len(sub_records),
        "subagent_total_tokens_in": sub_total_tokens_in,
        "subagent_total_tokens_out": sub_total_tokens_out,
        "subagent_total_tool_calls": sub_total_tools,
        "subagent_ids": [s["agent_id"] for s in sub_records],
    }

    # Record main conversation via record_minimal_v2 (vault_extra persisted)
    try:
        from atlast_ecp.core import record_minimal_v2
        record_minimal_v2(
            input_content=last_user_msg,
            output_content=turn["narrative"],
            agent=agent_name,
            action="conversation",
            model=turn["last_model"] or "claude",
            latency_ms=latency_ms,
            tokens_in=turn["tokens_in"] or None,
            tokens_out=turn["tokens_out"] or None,
            session_id=session_id,
            thread_id=session_id,
            vault_extra=vault_extra,
        )
        _log(
            f"SUCCESS: main recorded "
            f"(session={session_id[:12]} tokens={turn['tokens_in']}/{turn['tokens_out']} "
            f"tools={len(turn['tool_calls'])} subs={len(sub_records)})"
        )
    except Exception as e:
        _log(f"ERROR main: {e}")

    # Record each subagent as its own record (linked via session_id)
    from atlast_ecp.core import record_minimal_v2 as _rec_v2
    for sa in sub_records:
        try:
            sa_vault = {
                "framework": "claude-code",
                "session_id": session_id,
                "parent_agent": agent_name,
                "subagent_id": sa["agent_id"],
                "subagent_type": sa["agent_type"],
                "description": sa["description"],
                "model": sa["model"],
                "tokens_in": sa["tokens_in"],
                "tokens_out": sa["tokens_out"],
                "cache_read_input_tokens": sa["cache_read"],
                "cache_creation_input_tokens": sa["cache_creation"],
                "context_length_peak": sa["context_peak"],
                "tool_call_count": len(sa["tool_calls"]),
                "tool_names": [t["name"] for t in sa["tool_calls"]],
                "tool_calls_used": [
                    {"name": t["name"], "input": t["input"], "result": t["result"][:500]}
                    for t in sa["tool_calls"]
                ],
                "first_ts": sa["first_ts"],
            }
            _rec_v2(
                input_content=sa["prompt"],
                output_content=sa["narrative"],
                agent=f"{agent_name}/subagent",
                action="subagent",
                model=sa["model"] or turn["last_model"] or "claude",
                latency_ms=0,
                tokens_in=sa["tokens_in"] or None,
                tokens_out=sa["tokens_out"] or None,
                session_id=session_id,
                thread_id=session_id,
                vault_extra=sa_vault,
            )
            _log(f"SUCCESS sub {sa['agent_id'][:12]} ({len(sa['tool_calls'])} tools)")
        except Exception as e:
            _log(f"ERROR sub {sa.get('agent_id','?')[:12]}: {e}")

    # Persist dedup
    try:
        dedup_file.write_text(json.dumps(dedup_key))
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log(f"FATAL: {e}")
