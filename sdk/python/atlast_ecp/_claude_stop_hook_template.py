"""ATLAST ECP — Claude Code Stop hook (v3, full-fidelity timeline).

Records EVERY event of a turn with zero truncation:
  - Each LLM call (with its own usage: input/output/cache_read/cache_creation tokens)
  - Every thinking block (Chain-of-Thought / ToT reasoning)
  - Every text block
  - Every tool_use with FULL input (Edit/Write old_string/new_string preserved byte-for-byte)
  - Every tool_result with FULL content + byte size
  - Subagents filtered to the current turn, each with their own full timeline

Stored in vault (~/.ecp/vault/rec_*.json) via record_minimal_v2(vault_extra=...).
Downstream consumers (dashboard, analysis tools) reconstruct the turn from timeline.
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

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
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _find_transcript(data):
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


def _is_real_user_message(entry):
    """True if this user entry is an actual human message (not a tool_result carrier).

    We DO NOT drop <system-reminder> content — those are legitimate context injections
    the agent saw. But an entry whose content is *only* tool_results is not a new turn.
    """
    c = entry.get("message", {}).get("content", "")
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        return any(
            isinstance(b, dict) and b.get("type") == "text" and b.get("text", "").strip()
            for b in c
        )
    return False


def _extract_user_full(entry):
    """Return the FULL user message text (no truncation). Joins text blocks if list."""
    c = entry.get("message", {}).get("content", "")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                t = b.get("text", "")
                if t:
                    parts.append(t)
        return "\n\n".join(parts)
    return str(c or "")


def _normalize_tool_result_content(raw):
    """Convert a tool_result's .content field into a full string. No truncation."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts = []
        for b in raw:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    parts.append(b.get("text", "") or "")
                elif "text" in b:
                    parts.append(b.get("text", "") or "")
                else:
                    parts.append(json.dumps(b))
            else:
                parts.append(str(b))
        return "\n".join(parts)
    return str(raw or "")


def _build_timeline(entries, last_user_idx):
    """Build a full-fidelity timeline of a turn. No truncation.

    Each element is one of:
      - {seq, ts, type: "llm_call", model, usage: {...}, context_at_call, content: [...]}
          content blocks verbatim (thinking, text, tool_use with FULL input)
      - {seq, ts, type: "tool_result", tool_use_id, tool_name, content, bytes}

    Also returns aggregated totals + turn boundary timestamps.
    """
    timeline = []
    # Map tool_use_id -> tool_name so tool_results can carry the name
    tool_use_names = {}
    # Track tool_use occurrences for counting
    tool_names_all = []
    # Dedup: Claude Code splits one API message into multiple JSONL lines
    # (one per content block type — thinking, text, tool_use). All lines
    # share the same message.id and the SAME usage payload. We merge them
    # into a single timeline event keyed by message.id.
    msg_id_to_event = {}

    totals = {
        "llm_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "tool_calls": 0,
        "thinking_blocks": 0,
        "text_blocks": 0,
        "tool_results": 0,
        "context_length_peak": 0,
    }

    last_model = None
    first_ts = None
    last_ts = None
    seq = 0

    for i in range(last_user_idx + 1, len(entries)):
        e = entries[i]
        etype = e.get("type", "")
        ts = e.get("timestamp")
        if ts:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        # Next real user message = next turn boundary
        if etype == "user" and _is_real_user_message(e):
            break

        if etype == "assistant":
            msg = e.get("message", {})
            model = msg.get("model")
            if model and not last_model:
                last_model = model

            msg_id = msg.get("id") or f"__no_id_{i}"
            existing = msg_id_to_event.get(msg_id)

            usage = msg.get("usage", {}) or {}
            ti = int(usage.get("input_tokens", 0) or 0)
            to = int(usage.get("output_tokens", 0) or 0)
            cr = int(usage.get("cache_read_input_tokens", 0) or 0)
            cc = int(usage.get("cache_creation_input_tokens", 0) or 0)

            if existing is None:
                # First line for this message — create the event, count usage once
                totals["llm_calls"] += 1
                totals["input_tokens"] += ti
                totals["output_tokens"] += to
                totals["cache_read_input_tokens"] += cr
                totals["cache_creation_input_tokens"] += cc
                context_at_call = ti + cr + cc
                if context_at_call > totals["context_length_peak"]:
                    totals["context_length_peak"] = context_at_call

                event = {
                    "seq": seq,
                    "ts": ts,
                    "type": "llm_call",
                    "message_id": msg_id,
                    "model": model,
                    "usage": {
                        "input_tokens": ti,
                        "output_tokens": to,
                        "cache_read_input_tokens": cr,
                        "cache_creation_input_tokens": cc,
                    },
                    "context_at_call": context_at_call,
                    "content": [],
                }
                timeline.append(event)
                msg_id_to_event[msg_id] = event
                seq += 1
            else:
                event = existing

            # Append content blocks from THIS line to the message's event
            raw_content = msg.get("content", [])
            if isinstance(raw_content, list):
                for b in raw_content:
                    if not isinstance(b, dict):
                        continue
                    btype = b.get("type")
                    if btype == "thinking":
                        totals["thinking_blocks"] += 1
                        thinking_text = b.get("thinking", "") or b.get("text", "") or ""
                        signature = b.get("signature", "") or ""
                        event["content"].append({
                            "type": "thinking",
                            "text": thinking_text,
                            "signature": signature,
                            "redacted": not bool(thinking_text) and bool(signature),
                            "signature_bytes": len(signature),
                        })
                    elif btype == "text":
                        text = b.get("text", "") or ""
                        if text:
                            totals["text_blocks"] += 1
                            event["content"].append({"type": "text", "text": text})
                    elif btype == "tool_use":
                        tid = b.get("id", "")
                        name = b.get("name", "?")
                        inp = b.get("input", {})
                        tool_use_names[tid] = name
                        tool_names_all.append(name)
                        totals["tool_calls"] += 1
                        event["content"].append({
                            "type": "tool_use",
                            "id": tid,
                            "name": name,
                            "input": inp,  # full, untouched
                        })
                    else:
                        event["content"].append(b)
            elif isinstance(raw_content, str) and raw_content:
                event["content"].append({"type": "text", "text": raw_content})

        elif etype == "tool_result":
            tid = e.get("tool_use_id", "")
            raw = e.get("content", "")
            content = _normalize_tool_result_content(raw)
            totals["tool_results"] += 1
            timeline.append({
                "seq": seq,
                "ts": ts,
                "type": "tool_result",
                "tool_use_id": tid,
                "tool_name": tool_use_names.get(tid),
                "content": content,
                "bytes": len(content.encode("utf-8")),
            })
            seq += 1

        elif etype == "user":
            # Claude Code often wraps tool_results in a user-typed entry
            c = e.get("message", {}).get("content", "")
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tid = b.get("tool_use_id", "")
                        raw = b.get("content", "")
                        content = _normalize_tool_result_content(raw)
                        totals["tool_results"] += 1
                        timeline.append({
                            "seq": seq,
                            "ts": ts,
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "tool_name": tool_use_names.get(tid),
                            "content": content,
                            "bytes": len(content.encode("utf-8")),
                        })
                        seq += 1

    return {
        "timeline": timeline,
        "totals": totals,
        "last_model": last_model,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "tool_names": tool_names_all,
    }


def _timeline_to_narrative(timeline):
    """Build a readable narrative from timeline for the `output` field.

    Includes agent text responses + short tool-call summaries so the list-view
    preview is informative. The authoritative record is in `timeline`, not here.
    """
    parts = []
    tool_name_by_id = {}
    for ev in timeline:
        if ev["type"] == "llm_call":
            for b in ev.get("content", []):
                t = b.get("type")
                if t == "text":
                    text = b.get("text", "")
                    if text:
                        parts.append(text)
                elif t == "tool_use":
                    tool_name_by_id[b.get("id", "")] = b.get("name", "?")
                    name = b.get("name", "?")
                    inp = b.get("input", {})
                    preview = ""
                    if isinstance(inp, dict):
                        for k in ("command", "file_path", "pattern", "url", "query"):
                            if k in inp:
                                preview = str(inp[k])
                                break
                        if not preview:
                            preview = json.dumps(inp, ensure_ascii=False)
                    parts.append(f"[{name}] {preview}")
                # thinking blocks are NOT in narrative (they're in timeline for detail view)
        elif ev["type"] == "tool_result":
            content = ev.get("content", "")
            # For narrative, show a short prefix. Full content is in timeline.
            preview = content[:400].replace("\n", " ")
            if preview:
                parts.append(f"→ {preview}")
    return "\n\n".join(parts) if parts else "(no response)"


def _extract_subagent(sa_file, turn_start_dt):
    """Parse a subagent JSONL into the same vault-v3 structure.

    Returns None if the subagent started BEFORE turn_start_dt.
    """
    entries = _read_jsonl(sa_file)
    if len(entries) < 2:
        return None

    first_ts = entries[0].get("timestamp")
    first_dt = _parse_iso(first_ts)
    if turn_start_dt and first_dt and first_dt < turn_start_dt:
        return None

    # Find first user message (the subagent's "prompt")
    prompt = None
    prompt_idx = -1
    for i, e in enumerate(entries):
        if e.get("type") == "user" and _is_real_user_message(e):
            prompt = _extract_user_full(e)
            prompt_idx = i
            break
    if not prompt:
        return None

    built = _build_timeline(entries, prompt_idx)

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
        "timeline": built["timeline"],
        "totals": built["totals"],
        "tool_names": built["tool_names"],
        "last_model": built["last_model"],
        "first_ts": built["first_ts"],
        "last_ts": built["last_ts"],
        "agent_id": sa_file.stem.replace("agent-", ""),
        "agent_type": agent_type,
        "description": description,
        "narrative": _timeline_to_narrative(built["timeline"]),
    }


def _derive_agent_name(transcript_path):
    try:
        project_dir = transcript_path.parent.name
        parts = [p for p in project_dir.split("-") if p and p != "Users"]
        for i, p in enumerate(parts):
            if p in ("Desktop", "Documents", "Projects", "repos", "code", "src", "home"):
                return "-".join(parts[i + 1:]) or "claude-code"
        return parts[-1] if parts else "claude-code"
    except Exception:
        return "claude-code"


def main():
    _log("Stop hook v3 fired")

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

    # Find last user message (= start of current turn). FULL content, no truncation.
    last_user_msg = None
    last_user_idx = -1
    last_user_ts = None
    for i in range(len(entries) - 1, -1, -1):
        e = entries[i]
        if e.get("type") == "user" and _is_real_user_message(e):
            last_user_msg = _extract_user_full(e)
            last_user_idx = i
            last_user_ts = e.get("timestamp")
            break
    if not last_user_msg:
        _log("ERROR: no user message found")
        return

    turn_start_dt = _parse_iso(last_user_ts)
    preview = (last_user_msg[:60] + "…") if len(last_user_msg) > 60 else last_user_msg
    _log(f"Turn start: {last_user_ts} | user: {preview!r}")

    # Build the main timeline
    built = _build_timeline(entries, last_user_idx)
    totals = built["totals"]
    _log(
        f"Turn: {totals['llm_calls']} LLM calls, "
        f"{totals['tool_calls']} tools, {totals['thinking_blocks']} thinking blocks, "
        f"in={totals['input_tokens']} out={totals['output_tokens']} "
        f"cache_read={totals['cache_read_input_tokens']} cache_creation={totals['cache_creation_input_tokens']} "
        f"ctx_peak={totals['context_length_peak']}"
    )

    ecp_dir = Path(os.environ.get("ATLAST_ECP_DIR", str(Path.home() / ".ecp")))
    dedup_file = ecp_dir / "hook_buffer" / "_last_turn.json"
    dedup_file.parent.mkdir(parents=True, exist_ok=True)
    dedup_key = {
        "user_hash": str(hash(last_user_msg)),
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

    # Subagents spawned in this turn
    sub_records = []
    session_dir = transcript_path.parent / transcript_path.stem
    subagent_dir = session_dir / "subagents"
    if subagent_dir.exists() and turn_start_dt:
        for sa_file in sorted(subagent_dir.glob("agent-*.jsonl")):
            sa = _extract_subagent(sa_file, turn_start_dt)
            if sa:
                sub_records.append(sa)
    _log(f"Subagents in this turn: {len(sub_records)}")

    latency_ms = 0
    try:
        latency_ms = int(data.get("duration_ms", 0))
    except (ValueError, TypeError):
        pass
    if latency_ms <= 0 or latency_ms > 86400000:
        start = _parse_iso(built["first_ts"])
        end = _parse_iso(built["last_ts"])
        if start and end:
            latency_ms = int((end - start).total_seconds() * 1000)
        if latency_ms < 0:
            latency_ms = 0

    # Build narrative for the `output` field (readable summary — timeline is the truth)
    narrative = _timeline_to_narrative(built["timeline"])

    # Sub totals rolled up from subagents
    sub_totals = {
        "count": len(sub_records),
        "llm_calls": sum(s["totals"]["llm_calls"] for s in sub_records),
        "input_tokens": sum(s["totals"]["input_tokens"] for s in sub_records),
        "output_tokens": sum(s["totals"]["output_tokens"] for s in sub_records),
        "cache_read_input_tokens": sum(s["totals"]["cache_read_input_tokens"] for s in sub_records),
        "cache_creation_input_tokens": sum(s["totals"]["cache_creation_input_tokens"] for s in sub_records),
        "tool_calls": sum(s["totals"]["tool_calls"] for s in sub_records),
        "thinking_blocks": sum(s["totals"]["thinking_blocks"] for s in sub_records),
    }

    vault_extra = {
        "vault_version": 3,
        "schema": "atlast.turn.v3",
        "framework": "claude-code",
        "session_id": session_id,
        "turn_start_ts": last_user_ts,
        "turn_end_ts": built["last_ts"],
        "model": built["last_model"],
        "latency_ms": latency_ms,
        "totals": totals,
        "timeline": built["timeline"],  # full fidelity — NO truncation anywhere
        "tool_names": built["tool_names"],
        "subagent_count": len(sub_records),
        "subagent_ids": [s["agent_id"] for s in sub_records],
        "subagent_totals": sub_totals,
    }

    # Record main turn
    main_record_id = None
    try:
        from atlast_ecp.core import record_minimal_v2
        main_record_id = record_minimal_v2(
            input_content=last_user_msg,
            output_content=narrative,
            agent=agent_name,
            action="conversation",
            model=built["last_model"] or "claude",
            latency_ms=latency_ms,
            tokens_in=totals["input_tokens"] or None,
            tokens_out=totals["output_tokens"] or None,
            session_id=session_id,
            thread_id=session_id,
            vault_extra=vault_extra,
        )
        _log(
            f"SUCCESS main ({main_record_id}): "
            f"{totals['llm_calls']} calls, {totals['tool_calls']} tools, "
            f"{totals['thinking_blocks']} thinks, {len(sub_records)} subs"
        )
    except Exception as e:
        _log(f"ERROR main: {e}")

    # Record each subagent with its own full timeline
    try:
        from atlast_ecp.core import record_minimal_v2 as _rec
    except Exception as e:
        _rec = None
        _log(f"ERROR import subagent recorder: {e}")

    for sa in sub_records:
        if _rec is None:
            break
        try:
            sa_vault = {
                "vault_version": 3,
                "schema": "atlast.turn.v3",
                "framework": "claude-code",
                "session_id": session_id,
                "parent_record_id": main_record_id,
                "parent_agent": agent_name,
                "subagent_id": sa["agent_id"],
                "subagent_type": sa["agent_type"],
                "description": sa["description"],
                "model": sa["last_model"],
                "turn_start_ts": sa["first_ts"],
                "turn_end_ts": sa["last_ts"],
                "totals": sa["totals"],
                "timeline": sa["timeline"],  # full fidelity
                "tool_names": sa["tool_names"],
            }
            _rec(
                input_content=sa["prompt"],
                output_content=sa["narrative"],
                agent=f"{agent_name}/subagent",
                action="subagent",
                model=sa["last_model"] or built["last_model"] or "claude",
                latency_ms=0,
                tokens_in=sa["totals"]["input_tokens"] or None,
                tokens_out=sa["totals"]["output_tokens"] or None,
                session_id=session_id,
                thread_id=session_id,
                vault_extra=sa_vault,
            )
            _log(f"SUCCESS sub {sa['agent_id'][:12]}: {sa['totals']['llm_calls']} calls, {sa['totals']['tool_calls']} tools")
        except Exception as e:
            _log(f"ERROR sub {sa.get('agent_id','?')[:12]}: {e}")

    try:
        dedup_file.write_text(json.dumps(dedup_key))
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _log(f"FATAL: {e}")
