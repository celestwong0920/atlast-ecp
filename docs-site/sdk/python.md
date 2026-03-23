# Python SDK

`pip install atlast-ecp`

## wrap() — Zero-Code Integration

The simplest way to add evidence recording:

```python
from openai import OpenAI
from atlast_ecp import wrap

client = wrap(OpenAI())
# Every call is now recorded — no other changes needed
```

Supports: **OpenAI**, **Anthropic**, **Google Gemini**, **LiteLLM**

```python
from anthropic import Anthropic
from atlast_ecp import wrap

client = wrap(Anthropic())
response = client.messages.create(
    model="claude-3-sonnet-20240229",
    messages=[{"role": "user", "content": "Hello"}]
)
# Automatically recorded with latency, model, tokens, flags
```

### Streaming

Streaming is fully supported. The SDK records after the stream completes:

```python
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write a poem"}],
    stream=True
)
for chunk in stream:
    print(chunk.choices[0].delta.content, end="")
# Record created after stream ends
```

## record() — Explicit Recording

For full control:

```python
from atlast_ecp import record

record(
    in_content="Summarize this document: ...",
    out_content="The document discusses three key points...",
    model="gpt-4",
    latency_ms=1200,
    tokens_in=500,
    tokens_out=200,
    cost_usd=0.01,
    session_id="sess_abc",
)
```

## record_minimal() — Lightweight

Minimum viable record (no signing, no chaining):

```python
from atlast_ecp import record_minimal

record_minimal(
    in_content="input",
    out_content="output",
    model="gpt-4",
)
```

## Framework Adapters

### LangChain

```python
from atlast_ecp.langchain import ATLASTCallbackHandler

handler = ATLASTCallbackHandler(session_id="my-session")
chain.invoke({"input": "..."}, config={"callbacks": [handler]})
```

### CrewAI

```python
from atlast_ecp.crewai import ATLASTCrewCallback

crew = Crew(
    agents=[...],
    tasks=[...],
    callbacks=[ATLASTCrewCallback(session_id="crew-run-1")],
)
```

### AutoGen

```python
from atlast_ecp.autogen import ecp_middleware

agent = ConversableAgent(
    "assistant",
    middleware=[ecp_middleware(session_id="autogen-1")],
)
```

## CLI Reference

```bash
atlast init              # Initialize ~/.ecp directory + identity
atlast log               # View recent records
atlast log --date 2026-03-23  # View specific date
atlast stats             # Record count, avg latency, flags
atlast verify <id>       # Verify record integrity
atlast inspect <id>      # View record + original content
atlast proof             # Generate proof package
atlast push              # Upload batch to server
atlast push --retry      # Retry failed uploads
atlast register          # Register agent with server
atlast proxy             # Start transparent proxy
atlast run <cmd>         # Run command with proxy injected
atlast export            # Export records as JSON
atlast insights          # Performance analysis
```
