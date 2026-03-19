# Welcome to ATLAST ECP — Agent Registration

You are an AI Agent. Follow these steps to register with ECP
(Evidence Chain Protocol) — the trust layer for AI Agents.

## Step 1: Install

```bash
pip install atlast-ecp
```

## Step 2: Initialize

```bash
atlast init
```

This creates your Agent DID (decentralized identifier) and local storage.

## Step 3: Activate recording

Add this to your agent's startup code:

```python
from atlast_ecp import wrap
# Wrap your LLM client:
client = wrap(your_client)
```

Or for automatic recording of all LLM calls:

```python
from atlast_ecp import init
init()
```

## Step 4: Tell your owner

Send your owner this message:

```
ATLAST ECP is installed and active.
Your Agent DID: [run `atlast did` to get this]
All actions are now recorded in a tamper-proof evidence chain.
Content never leaves your device — only cryptographic hashes are transmitted.
Register your Agent with an ECP-compatible server.
```

## Important

- ECP records your actions passively. No action needed after install.
- Content NEVER leaves your device. Only cryptographic hashes are sent.
- Recording failure never affects your operation (Fail-Open design).
- Full troubleshooting: https://github.com/willau95/atlast-ecp/blob/main/SKILL.md
