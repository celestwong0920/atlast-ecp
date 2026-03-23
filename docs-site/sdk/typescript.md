# TypeScript SDK

`npm install atlast-ecp-ts`

## Quick Start

```typescript
import { createRecord, uploadBatch } from 'atlast-ecp-ts';

// Create a record
const record = createRecord({
  agentId: 'my-agent',
  input: 'Summarize this document',
  output: 'The document discusses...',
  model: 'gpt-4',
  latencyMs: 1200,
});

// Upload batch
await uploadBatch({
  agentId: 'my-agent',
  apiUrl: 'https://api.weba0.com/v1',
});
```

## wrap() — Client Wrapper

```typescript
import { wrap } from 'atlast-ecp-ts';
import OpenAI from 'openai';

const client = wrap(new OpenAI(), { agentId: 'my-agent' });
// All calls automatically recorded
```

## track() — Function Decorator

```typescript
import { track } from 'atlast-ecp-ts';

const trackedFn = track(async (input: string) => {
  // Your agent logic
  return result;
}, { agentId: 'my-agent', sessionId: 'sess-1' });

await trackedFn('process this data');
```

## Identity Management

```typescript
import { loadOrCreateIdentity } from 'atlast-ecp-ts';

const identity = loadOrCreateIdentity('my-agent');
console.log(identity.did);  // did:ecp:abc123...
```

## Batch Upload

```typescript
import { uploadBatch } from 'atlast-ecp-ts';

const result = await uploadBatch({
  agentId: 'my-agent',
  apiUrl: 'https://api.weba0.com/v1',
  apiKey: 'ak_live_xxx',  // optional
  maxRetries: 3,           // exponential backoff
});
```

## Cross-SDK Compatibility

TypeScript SDK produces identical hashes to Python SDK:
- Same SHA-256 implementation (`sha256:` prefix)
- Same canonical JSON serialization (`stableStringify` = `json.dumps(sort_keys=True)`)
- Same Merkle tree algorithm
- Records from either SDK are verifiable by the other
