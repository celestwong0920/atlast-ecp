# Recovery & Backup

ATLAST ECP provides built-in identity recovery and encrypted vault backup to protect against data loss.

## Recovery Phrase

When you run `atlast init`, a **12-word recovery phrase** is generated and displayed once:

```
🔑 RECOVERY PHRASE — write this down and store safely:
┌─────────────────────────────────────────────────────┐
│  1. marble        2. ocean         3. pencil        │
│  4. quiet         5. river         6. storm         │
│  7. tiger         8. umbrella      9. violet        │
│ 10. whale        11. xenon        12. yard          │
└─────────────────────────────────────────────────────┘
```

**Write it down.** It will NOT be shown again. This phrase can fully restore your agent identity (DID + signing keys).

## Vault Backup

During `atlast init`, you can choose an encrypted backup location for your evidence content:

- **iCloud Drive** (macOS, auto-detected)
- **Dropbox** (auto-detected)
- **OneDrive** (auto-detected)
- **Custom path** (USB drive, NAS, any directory)

All content is encrypted with **AES-256-GCM** using a key derived from your private key. The backup service (iCloud, Dropbox, etc.) cannot read your data.

### Manual Backup

```bash
# Backup entire vault to a path
atlast backup --path /Volumes/MyUSB/ecp-backup

# Set permanent backup path
atlast config set vault_backup_path /path/to/backup
```

## Disaster Recovery

If your computer is lost, stolen, or the hard drive fails:

```bash
# On new computer
pip install atlast-ecp

# Restore identity from recovery phrase
atlast recover
> Enter your 12-word recovery phrase:
> marble ocean pencil quiet river storm tiger umbrella violet whale xenon yard

✅ Identity recovered: did:ecp:a3f8c2...
✅ Downloaded 5000 records from server
✅ Vault restored: 5000 entries
```

### What Gets Recovered

| Data | Source | Status |
|------|--------|--------|
| Identity (DID + keys) | Recovery phrase | ✅ Full |
| Record hashes + chain | Server (api.weba0.com) | ✅ Full |
| On-chain anchoring | Base blockchain | ✅ Permanent |
| Original content | Encrypted backup | ✅ If backup was configured |

## Security Notes

- Recovery phrase = full access to your identity. Treat like a password.
- Never share your recovery phrase.
- Vault backups are encrypted — only your private key can decrypt them.
- The ATLAST server never has access to your original content or private key.
