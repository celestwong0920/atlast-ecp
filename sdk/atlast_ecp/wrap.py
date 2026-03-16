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
from functools import wraps

from .core import record_async


def _wrap_anthropic(client):
    """Wrap an Anthropic client."""
    original_create = client.messages.create

    @wraps(original_create)
    def recorded_create(*args, **kwargs):
        in_content = kwargs.get("messages", args[0] if args else [])
        model = kwargs.get("model", "unknown")

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

        # Delegate to core (handles chaining, signing, flags, retry detection)
        record_async(
            input_content=in_content,
            output_content=out_content,
            step_type="llm_call",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
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

        # Delegate to core (handles chaining, signing, flags, retry detection)
        record_async(
            input_content=in_content,
            output_content=out_content,
            step_type="llm_call",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
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
