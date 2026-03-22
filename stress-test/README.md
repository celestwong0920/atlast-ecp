# ATLAST ECP Stress Test Suite

**Purpose**: Validate the full ECP pipeline with realistic agent scenarios.

## Test Agents

| # | Agent | Framework | Model | Scenario | Calls |
|---|-------|-----------|-------|----------|-------|
| 1 | Coding Agent | `wrap()` | claude-sonnet | Read→Analyze→Refactor→Test | ~40 |
| 2 | Research Agent | LangChain | gpt-4o | Search→Summarize→Report | ~30 |
| 3 | Customer Service | `@track` decorator | claude-haiku | High-frequency short QA | ~150 |
| 4 | CrewAI Team | CrewAI | mixed | 3-agent collaboration | ~60 |
| 5 | AutoGen Debate | AutoGen | gpt-4o-mini | Multi-turn debate | ~80 |
| 6 | Chaos Agent | raw Python | mixed | Error injection, retries, timeouts | ~30 |

## What We're Testing

- [ ] Full chain: SDK → batch → ECP Server anchor → EAS → webhook → Alex DB → score
- [ ] All 7 flags: retried, hedged, incomplete, high_latency, error, human_review, a2a_delegated
- [ ] Sub-agent delegation: session_id, delegation_id, delegation_depth
- [ ] Batch size limits and throttling (anti-abuse)
- [ ] Merkle tree correctness at scale (100+ records)
- [ ] Streaming response recording
- [ ] Multiple concurrent sessions
- [ ] Long-running chain integrity (50+ records chained)

## Prerequisites

```bash
export OPENROUTER_API_KEY="sk-or-..."
pip install atlast-ecp openai anthropic
```

## Run All

```bash
cd stress-test
python run_all.py
```
