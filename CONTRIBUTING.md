# Contributing to ATLAST ECP

Thank you for your interest in contributing to the Evidence Chain Protocol!

## Community

- **Discord**: [discord.gg/gztk5Ud3C2](https://discord.gg/gztk5Ud3C2) — ask questions, report bugs, discuss features
- **Email**: atlastecp@gmail.com — business inquiries
- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas

## Development Setup

### Monorepo Structure

```
atlast-ecp/
├── sdk/python/       # Python SDK (PyPI: atlast-ecp) — primary
├── sdk/go/           # Go SDK — minimal ECP records
├── server/           # ECP Reference Server (FastAPI)
├── whitepaper/       # Whitepaper + Litepaper (EN + ZH)
├── docs/             # ADRs, migration guides, specs
└── ECP-SPEC.md       # Protocol specification
```

### Python SDK

```bash
git clone https://github.com/willau95/atlast-ecp.git
cd atlast-ecp/sdk/python
pip install -e ".[dev,crypto]"
pytest tests/ -v
```

Requires Python 3.9+.

### Go SDK

```bash
cd sdk/go
go test ./... -v
```

### Reference Server

```bash
cd server
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Making Changes

1. **Fork** the repo and create a branch from `main`
2. **Write tests** for any new functionality
3. **Run the full test suite** before submitting:
   ```bash
   cd sdk/python && pytest tests/ -v   # Python SDK (830+ tests)
   cd sdk/go && go test ./... -v       # Go SDK
   cd server && python -m pytest tests/ -v # Server
   ```
4. **Update documentation** if you changed public APIs
5. Submit a **Pull Request** with a clear description

## Code Conventions

- **Python**: Type hints. `from __future__ import annotations` in new files.
- **Go**: Standard library only. No external dependencies.
- **Tests**: Descriptive names (`test_upload_batch_wrong_key`, not `test_3`).
- **Fail-Open**: Recording failures must NEVER crash the host agent.
- **Privacy**: Never log or transmit raw content. Hashes only.

## ECP Spec Compliance

All contributions must maintain compatibility with [ECP-SPEC.md](ECP-SPEC.md):

- Record format: ECP v1.0 flat format (7 core fields)
- `hash_content()` output must be identical across Python and Go SDKs
- Record IDs: `rec_` + 16 hex characters
- Chain hash: SHA-256 of canonical JSON (sorted keys, no spaces)

## Cross-SDK Hash Consistency

If you modify `hash_content()` or Merkle tree logic, verify the output matches all SDKs:

```python
hash_content("hello") == "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
```

## 🔒 Important: Install Interface is Locked

`pip3 install atlast-ecp` and `atlast init` are permanent public interfaces. They must never change. See ARCHITECTURE-DECISIONS.md for details.

## Reporting Security Issues

Please email security issues to atlastecp@gmail.com. Do not open public issues for security vulnerabilities.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
