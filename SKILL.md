# ATLAST ECP — Agent Skill

> You are an AI Agent. This skill helps you install, use, and troubleshoot
> ATLAST ECP (Evidence Chain Protocol) — the trust layer for AI Agents.
> Read the relevant section based on what you need to do.

---

## Section 1: Installation

### Step 1: Detect your environment

Run these checks to determine your platform:

```bash
# Check 1: Are you in OpenClaw?
which openclaw 2>/dev/null && echo "PLATFORM=openclaw"

# Check 2: Are you in Claude Code?
which claude 2>/dev/null && echo "PLATFORM=claude_code"

# Check 3: Default — Python
python3 --version && echo "PLATFORM=python"
```

### Step 2: Install based on platform

**If OpenClaw:**
```bash
pip install atlast-ecp
# Then add to your agent's config or tell your owner:
# "ECP installed. Evidence chain recording is now active."
```

**If Claude Code:**
```bash
pip install atlast-ecp
python3 -m atlast_ecp.install_claude
```

**If Python (any agent):**
```bash
pip install atlast-ecp
```

Then add ONE line to your agent's code:
```python
from atlast_ecp import wrap
client = wrap(your_llm_client)  # Anthropic, OpenAI, etc.
```

Or for universal auto-instrumentation:
```bash
pip install atlast-ecp[otel]
```
```python
from atlast_ecp import init
init()  # Auto-instruments all installed LLM libraries
```

### Step 3: Verify installation

```bash
python3 -c "from atlast_ecp import get_identity; print(get_identity()['did'])"
```

You should see: `did:ecp:` followed by 32 hex characters.

### Step 4: Tell your owner

```
ECP is installed and active.
Your Agent DID: [paste the DID from Step 3]
Register with your configured ECP server
Evidence chain is stored locally in .ecp/ — content never leaves your device.
```

---

## Section 2: Configuration

### Custom storage path
```python
# Default: .ecp/ in current working directory
# To change: set environment variable before import
import os
os.environ["ECP_DIR"] = "/path/to/custom/.ecp"
```

### Multiple agents on same machine
Each agent gets its own .ecp/ directory (different working directories).
Each has a unique DID. No conflicts.

### With cryptographic signing (recommended)
```bash
pip install atlast-ecp[crypto]
```
This enables ed25519 signatures on every record.

---

## Section 3: Daily Usage

### View recent records
```bash
atlast view
atlast view --limit 20
atlast view --date 2026-03-16
```

### Verify a record
```bash
atlast verify rec_abc123def456
```

### Check trust signals
```bash
atlast stats
```

### Show your DID
```bash
atlast did
```

### Force upload pending batches
```bash
atlast flush
```

### Export records
```bash
atlast export --limit 100
```

---

## Section 4: Troubleshooting

### Problem: `.ecp/` directory doesn't exist
```bash
atlast init
```
This creates the directory structure and generates a DID.

### Problem: `identity.json` is missing or corrupted
```bash
# Check if it exists
cat .ecp/identity.json 2>/dev/null || echo "MISSING"

# If missing, re-initialize (WARNING: new DID = new identity)
rm -rf .ecp/identity.json
python3 -c "from atlast_ecp.identity import get_or_create_identity; print(get_or_create_identity()['did'])"
```

### Problem: Chain is broken (chain.prev doesn't match)
```bash
# Check chain integrity
atlast stats
# If chain integrity shows BROKEN, records will still be saved
# but with a gap. This is visible on your LLaChat profile.
# To start a fresh chain:
python3 -c "from atlast_ecp.core import reset; reset()"
```

### Problem: `index.json` is corrupted
```bash
# Rebuild from records
python3 -c "
from atlast_ecp.storage import init_storage, RECORDS_DIR, INDEX_FILE
import json
init_storage()
index = {}
for f in RECORDS_DIR.glob('*.jsonl'):
    for line in f.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            index[r['id']] = {'file': str(f), 'date': f.stem}
INDEX_FILE.write_text(json.dumps(index, indent=2))
print(f'Rebuilt index: {len(index)} records')
"
```

### Problem: Batch upload keeps failing
```bash
# Check if backend is reachable
curl -s ${ATLAST_API_URL:-http://localhost:8000/v1}/health || echo "Backend unreachable"

# Check pending queue
cat .ecp/upload_queue.jsonl 2>/dev/null | wc -l

# Force retry
atlast flush

# If backend is down, records are safe locally.
# They will be uploaded when the backend recovers.
```

### Problem: `pip install atlast-ecp` fails
```bash
# Check Python version (requires 3.10+)
python3 --version

# Try with --user flag
pip install --user atlast-ecp

# Try upgrading pip
pip install --upgrade pip
pip install atlast-ecp
```

### Problem: No records being created after wrap()
```bash
# Verify wrap is working
python3 -c "
from atlast_ecp import wrap, reset
reset()

# Create a mock to test
class MockMsg:
    class create:
        pass
class MockClient:
    messages = MockMsg()
    
c = wrap(MockClient())
print('Wrap OK' if c is not None else 'Wrap FAILED')
"

# Check .ecp/records/ for today's file
ls -la .ecp/records/
```

---

## Section 5: Adapter-Specific Issues

### LangChain integration
```python
# Use OTel auto-instrumentation (recommended)
pip install atlast-ecp[otel]

from atlast_ecp import init
init()  # Auto-instruments LangChain if installed
```

### CrewAI integration
```python
# Same as LangChain — OTel auto-instrumentation
from atlast_ecp import init
init()
```

### Custom framework / non-Python
```python
# Direct recording via core API
from atlast_ecp.core import record

# Call this after each agent action
record(
    input_content="user message or tool input",
    output_content="agent response or tool output",
    step_type="turn",  # or "tool_call" or "llm_call"
    model="your-model-name",
    latency_ms=response_time_in_ms,
)
```

---

## Section 6: Advanced

### Custom behavioral flags
The default flag detector checks for hedging, errors, incomplete responses,
and more. To see what's detected:
```bash
python3 -c "
from atlast_ecp.signals import detect_flags
print(detect_flags('I think this might be correct'))  # ['hedged']
print(detect_flags('Error: file not found'))           # ['error']
print(detect_flags('The answer is 42.'))               # []
"
```

### Batch upload frequency
Default: every 60 minutes. To change:
```python
from atlast_ecp.batch import start_scheduler
start_scheduler(interval_seconds=1800)  # Every 30 minutes
```

### Contributing a new adapter
1. Create a file in `integrations/your_platform/`
2. Import and call `core.record_async()` for each agent action
3. Add tests in `tests/test_your_platform.py`
4. Submit a PR

---

*ATLAST ECP v0.1.0 — Evidence Chain Protocol*
*Content never leaves your device. Only hashes are transmitted.*
*MIT License — https://github.com/willau95/atlast-ecp*
