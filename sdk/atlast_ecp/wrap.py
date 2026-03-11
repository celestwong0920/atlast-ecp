"""
ECP Library Mode — wrap(client)
One line. Passive recording. Fail-Open.

Usage:
    from atlast_ecp import wrap
    from anthropic import Anthropic

    client = wrap(Anthropic())
    # Everything else stays the same.
"""

import time
import threading
from functools import wraps
from typing import Optional

from .identity import get_or_create_identity
from .record import create_record, record_to_dict
from .storage import save_record
from .signals import detect_flags


class _ECPContext:
    """Thread-local context for tracking retries and sessions."""
    def __init__(self):
        self.identity = get_or_create_identity()
        self.last_record = None
        self.call_hashes = {}    # in_hash → count (retry detection)
        self.lock = threading.Lock()


_ctx = _ECPContext()


def _record_async(
    step_type: str,
    in_content,
    out_content,
    model: Optional[str],
    tokens_in: Optional[int],
    tokens_out: Optional[int],
    latency_ms: int,
    is_retry: bool,
):
    """Fire-and-forget recording in background thread. Never raises."""
    def _do_record():
        try:
            from .record import hash_content
            out_text = _extract_text(out_content)
            flags = detect_flags(out_text, is_retry=is_retry)

            record = create_record(
                agent_did=_ctx.identity["did"],
                step_type=step_type,
                in_content=in_content,
                out_content=out_content,
                identity=_ctx.identity,
                prev_record=_ctx.last_record,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                flags=flags,
            )
            save_record(record_to_dict(record))
            with _ctx.lock:
                _ctx.last_record = record
        except Exception:
            # Fail silently — recording failure NEVER affects the LLM call
            pass

    t = threading.Thread(target=_do_record, daemon=True)
    t.start()


def _extract_text(content) -> str:
    """Extract plain text from various response formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif "text" in item:
                    parts.append(item["text"])
        return " ".join(parts)
    if hasattr(content, "text"):
        return content.text
    return str(content)


def _wrap_anthropic(client):
    """Wrap an Anthropic client."""
    original_create = client.messages.create

    @wraps(original_create)
    def recorded_create(*args, **kwargs):
        in_content = kwargs.get("messages", args[0] if args else [])
        model = kwargs.get("model", "unknown")

        # Retry detection: same input hash seen before?
        from .record import hash_content
        in_hash = hash_content(in_content)
        with _ctx.lock:
            prev_count = _ctx.call_hashes.get(in_hash, 0)
            _ctx.call_hashes[in_hash] = prev_count + 1
        is_retry = prev_count > 0

        t_start = time.time()
        response = original_create(*args, **kwargs)
        latency_ms = int((time.time() - t_start) * 1000)

        # Extract response content
        out_content = ""
        tokens_in = tokens_out = None
        try:
            if hasattr(response, "content"):
                out_content = [
                    block.text for block in response.content
                    if hasattr(block, "text")
                ]
            if hasattr(response, "usage"):
                tokens_in = getattr(response.usage, "input_tokens", None)
                tokens_out = getattr(response.usage, "output_tokens", None)
        except Exception:
            pass

        _record_async(
            step_type="llm_call",
            in_content=in_content,
            out_content=out_content,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            is_retry=is_retry,
        )
        return response

    client.messages.create = recorded_create
    return client


def _wrap_openai(client):
    """Wrap an OpenAI client."""
    original_create = client.chat.completions.create

    @wraps(original_create)
    def recorded_create(*args, **kwargs):
        in_content = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")

        from .record import hash_content
        in_hash = hash_content(in_content)
        with _ctx.lock:
            prev_count = _ctx.call_hashes.get(in_hash, 0)
            _ctx.call_hashes[in_hash] = prev_count + 1
        is_retry = prev_count > 0

        t_start = time.time()
        response = original_create(*args, **kwargs)
        latency_ms = int((time.time() - t_start) * 1000)

        out_content = ""
        tokens_in = tokens_out = None
        try:
            if hasattr(response, "choices") and response.choices:
                out_content = response.choices[0].message.content or ""
            if hasattr(response, "usage"):
                tokens_in = getattr(response.usage, "prompt_tokens", None)
                tokens_out = getattr(response.usage, "completion_tokens", None)
        except Exception:
            pass

        _record_async(
            step_type="llm_call",
            in_content=in_content,
            out_content=out_content,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            is_retry=is_retry,
        )
        return response

    client.chat.completions.create = recorded_create
    return client


def wrap(client):
    """
    Wrap any supported LLM client with ECP passive recording.

    Supports: Anthropic, OpenAI (auto-detected).
    Fail-Open: if wrapping fails, returns original client unchanged.

    Usage:
        client = wrap(Anthropic())
        client = wrap(openai.OpenAI())
    """
    try:
        class_name = type(client).__name__
        module_name = type(client).__module__

        if "anthropic" in module_name.lower() or class_name == "Anthropic":
            return _wrap_anthropic(client)

        if "openai" in module_name.lower() or class_name in ("OpenAI", "AzureOpenAI"):
            return _wrap_openai(client)

        # Unknown client — return as-is (fail-open)
        return client

    except Exception:
        # Wrapping failed — return original client, Agent unaffected
        return client
