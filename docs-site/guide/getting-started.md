# Quick Start

Get evidence recording working in under 3 minutes.

## Install

::: code-group
```bash [Python]
pip install atlast-ecp
```
```bash [TypeScript]
npm install atlast-ecp-ts
```
:::

## Initialize

```bash
atlast init
```

This creates:
- `~/.ecp/` — local evidence storage (never transmitted)
- Ed25519 keypair for signing
- Agent DID (`did:ecp:{hash}`)

## Option A: Zero-Code (Proxy)

Wrap any existing agent — no code changes:

```bash
atlast run python my_agent.py
```

This starts a transparent proxy that intercepts all LLM API calls (OpenAI, Anthropic, etc.) and records evidence automatically.

## Option B: SDK Wrapper (5 lines)

```python
from openai import OpenAI
from atlast_ecp import wrap

client = wrap(OpenAI())  # That's it

# Use normally — every call is automatically recorded
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Option C: Explicit Recording

```python
from atlast_ecp import record

record(
    in_content="Summarize this document",
    out_content="The document discusses...",
    model="gpt-4",
    latency_ms=1200,
)
```

## View Your Evidence

```bash
# See recent records
atlast log

# Verify a specific record
atlast verify rec_abc123

# View stats
atlast stats

# Inspect with original content
atlast inspect rec_abc123
```

## Upload to Server

```bash
# Register your agent
atlast register

# Push evidence batch
atlast push
```

This uploads Merkle roots to `api.weba0.com` for on-chain anchoring.

## Next Steps

- [Core Concepts](/guide/concepts) — understand ECP data model
- [Python SDK](/sdk/python) — detailed SDK reference
- [TypeScript SDK](/sdk/typescript) — Node.js integration
- [API Reference](/api/) — server endpoints
