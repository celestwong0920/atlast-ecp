# ATLAST ECP Cloud Backup Design (P1)

## Problem

ECP uses Commit-Reveal architecture: only hashes are transmitted to the server.
Original content stays on the user's device in `~/.ecp/vault/` (Content Vault).

**If the device is lost/destroyed, the original content is gone forever.**
The hashes on-chain still prove *something existed*, but the actual evidence is lost.

## Solution: Encrypted Cloud Backup (L1)

### Architecture

```
User Device                          Cloud Storage (S3/R2)
┌─────────────┐                     ┌──────────────────┐
│ ~/.ecp/      │                     │                  │
│   vault/     │  ─── encrypt ───>  │  {did}/vault/    │
│   records/   │  ─── encrypt ───>  │  {did}/records/  │
│   identity/  │  ─── encrypt ───>  │  {did}/identity/ │
│              │                     │                  │
└─────────────┘                     └──────────────────┘
         │                                    │
         │ AES-256-GCM                        │
         │ Key = HKDF(Ed25519 private key)    │
         └────────────────────────────────────┘
```

### Encryption Scheme

1. **Key Derivation**: `backup_key = HKDF(SHA-256, ikm=ed25519_private_key, salt="atlast-backup-v1", info="aes-256-gcm")`
2. **Encryption**: AES-256-GCM per file (unique nonce per file)
3. **File format**: `[12-byte nonce][16-byte auth tag][ciphertext]`
4. **Filename**: `sha256(original_filename).enc` (no metadata leakage)

### Key Properties

- **Zero-knowledge**: Cloud provider cannot read any content
- **Single secret**: Agent's Ed25519 private key is the only secret needed
- **Deterministic key**: Same private key always derives same backup key
- **No additional passwords**: Users don't need to remember anything extra

### Supported Providers

| Provider | Cost | Notes |
|----------|------|-------|
| Cloudflare R2 | Free 10GB/mo | Recommended (S3-compatible, no egress fees) |
| AWS S3 | ~$0.023/GB | Standard, well-known |
| Local Directory | Free | For testing, NAS backup |

### CLI Commands

```bash
# Configure backup
atlast backup config --provider r2 --bucket my-ecp-backup
atlast backup config --provider s3 --bucket my-ecp-backup --region us-east-1
atlast backup config --provider local --path /mnt/nas/ecp-backup

# Manual backup
atlast backup push          # Encrypt + upload all new files
atlast backup push --full   # Full backup (all files)

# Restore
atlast backup restore       # Download + decrypt to ~/.ecp/
atlast backup restore --to /tmp/ecp-restore  # Restore to custom dir

# Status
atlast backup status        # Show last backup time, file count, size
```

### Automatic Backup

After each batch upload succeeds, automatically backup new vault files:

```python
# In batch.py, after successful upload:
if backup_configured():
    threading.Thread(target=backup_incremental, daemon=True).start()
```

### Implementation Plan

1. `sdk/python/atlast_ecp/backup.py` — encrypt/decrypt + provider abstraction
2. `sdk/python/atlast_ecp/providers/` — S3, R2, local filesystem
3. CLI commands in `cli.py`
4. Auto-backup hook in `batch.py`
5. Tests

### Security Considerations

- Private key never leaves device (only derived backup key is used for encryption)
- Each file has unique nonce (no nonce reuse)
- Auth tag prevents tampering of encrypted files
- Cloud provider sees only encrypted blobs with hashed filenames
- Backup key rotation: if agent rekeys, old backups need old key to decrypt
  - Solution: store key version in backup metadata

### What If Identity Is Also Lost?

If `~/.ecp/identity/` is destroyed along with the device:
- The Ed25519 private key is gone → cannot derive backup key → cannot decrypt backups
- **Mitigation**: `atlast backup` also backs up the encrypted identity (self-referential)
- **Alternative**: User can export a **recovery phrase** (BIP-39 mnemonic of the private key)
  - `atlast identity export-recovery` → 24-word phrase
  - `atlast identity import-recovery` → restores from phrase
  - User stores phrase offline (paper, password manager)

### Cost Estimate

- Average agent: ~100 records/day × ~2KB each = ~200KB/day = ~6MB/month
- R2 free tier: 10GB → supports ~1,600 agent-months free
- **$0/month for individual users**
