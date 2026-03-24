# ATLAST ECP — Go SDK

> Evidence Chain Protocol SDK for Go. Create, store, and verify ECP records. Zero external dependencies.

## Install

```bash
go get github.com/willau95/atlast-ecp/sdk/go
```

## Quick Start

```go
package main

import (
    "fmt"
    ecp "github.com/willau95/atlast-ecp/sdk/go"
)

func main() {
    // Create a minimal ECP record (Level 1 — 7 fields)
    record := ecp.NewMinimalRecord("my-agent", "llm_call", "user query", "agent response")

    // Save to local JSONL file (~/.atlast/records.jsonl)
    ecp.SaveRecord(ecp.DefaultPath(), record)

    fmt.Println(record.ID)       // rec_<16 hex chars>
    fmt.Println(record.InHash)   // sha256:<hex>
    fmt.Println(record.OutHash)  // sha256:<hex>
}
```

## Identity

```go
// Load or generate a persistent Ed25519 identity (~/.atlast/identity.json)
id, err := ecp.GetOrCreateIdentity()
fmt.Println(id.DID)    // did:ecp:<32 hex chars>
fmt.Println(id.PubKey) // <64 hex chars> (32 bytes Ed25519 public key)

// Sign data
sig := ecp.SignData(id, "some data")  // ed25519:<hex>
```

## Config

Priority order: env vars > `~/.atlast/config.json` > defaults.

```go
url := ecp.GetAPIURL() // ATLAST_API_URL env > config endpoint > https://api.weba0.com/v1
key := ecp.GetAPIKey() // ATLAST_API_KEY env > config agent_api_key

cfg := ecp.LoadConfig()
fmt.Println(cfg.Endpoint, cfg.AgentAPIKey)
```

Environment variables:

| Variable | Description |
|----------|-------------|
| `ATLAST_API_URL` | Override API base URL |
| `ATLAST_API_KEY` | Override API key |

## Batch Upload

```go
records, _ := ecp.LoadRecords(ecp.DefaultPath())

// Build Merkle batch from records
batch := ecp.BuildBatch(records)
fmt.Println(batch.ID)          // batch_<16 hex chars>
fmt.Println(batch.MerkleRoot)  // sha256:<hex>
fmt.Println(batch.RecordCount) // number of records

// Upload to ATLAST API
err := ecp.UploadBatch(ecp.GetAPIURL(), ecp.GetAPIKey(), batch)
```

## CLI

```bash
go install github.com/willau95/atlast-ecp/sdk/go/cmd/atlast-go@latest

# Create and save a record
atlast-go record --agent my-agent --input "hello" --output "world"

# List recent records
atlast-go log
atlast-go log --n 50

# Upload a batch to the API
atlast-go push
atlast-go push --api-url https://api.weba0.com/v1 --api-key my-key

# Verify chain integrity
atlast-go verify
atlast-go verify --json
```

## API Reference

| Function | Description |
|----------|-------------|
| `NewMinimalRecord(agent, action, input, output)` | Create Level 1 record (7 fields) |
| `NewRecord(agent, action, input, output, meta)` | Create Level 2 record with metadata |
| `HashContent(input)` | SHA-256 hash (`sha256:{hex}`) |
| `SaveRecord(path, record)` | Append record to JSONL file (creates dirs) |
| `LoadRecords(path)` | Load all records from JSONL file |
| `BuildMerkleRoot(hashes)` | Compute Merkle root from hash list |
| `VerifyMerkleRoot(hashes, root)` | Verify Merkle root matches hashes |
| `ComputeChainHash(record)` | Compute chain hash for a record |
| `VerifyChain(records)` | Verify record chain integrity |
| `GetOrCreateIdentity()` | Load or generate Ed25519 identity |
| `GenerateIdentity()` | Generate a new Ed25519 identity |
| `LoadIdentity(path)` | Load identity from file |
| `SaveIdentity(path, identity)` | Save identity to file (0600) |
| `SignData(identity, data)` | Sign data, returns `ed25519:{hex}` |
| `BuildBatch(records)` | Build Merkle batch from records |
| `UploadBatch(apiURL, apiKey, batch)` | POST batch to ATLAST API |
| `GetAPIURL()` | Get API URL (env > config > default) |
| `GetAPIKey()` | Get API key (env > config) |
| `LoadConfig()` | Load `~/.atlast/config.json` |

## Cross-SDK Compatibility

Go SDK produces records that are **fully interoperable** with Python and TypeScript SDKs:

- Same hash output: `HashContent("hello")` matches across all SDKs
- Same record ID format: `rec_` + 16 hex characters
- Same JSONL storage format: records created in Go can be read by Python and vice versa
- Same Merkle root algorithm: sort → pair → SHA-256
- Same DID format: `did:ecp:{sha256(pub_key_hex)[:32]}`
- Same identity file: `~/.atlast/identity.json` with `{did, pub_key, priv_key}`

## Zero Dependencies

This SDK uses only the Go standard library (`crypto/ed25519`, `crypto/sha256`, `encoding/json`, `net/http`, `os`). No external dependencies.

## License

MIT
