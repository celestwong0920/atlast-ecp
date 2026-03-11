"""
ECP Identity — Agent DID generation and signing.

DID format: did:ecp:{sha256(pubkey)[:32]}
  - sha256(pubkey) = 64 hex chars
  - [:32] = first 16 bytes (32 hex chars)

Signature format: ed25519:{hex}
"""

import hashlib
import json
import time
from pathlib import Path

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption
    )
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


ECP_DIR = Path(".ecp")
IDENTITY_FILE = ECP_DIR / "identity.json"


def _now_ms() -> int:
    """Current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def get_or_create_identity() -> dict:
    """Load existing identity or generate a new one."""
    ECP_DIR.mkdir(exist_ok=True)
    if IDENTITY_FILE.exists():
        try:
            import json as _json
            return _json.loads(IDENTITY_FILE.read_text())
        except Exception:
            pass
    return _create_identity()


def _create_identity() -> dict:
    ECP_DIR.mkdir(exist_ok=True)  # ensure dir exists before writing
    if HAS_CRYPTO:
        private_key = Ed25519PrivateKey.generate()
        pub_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        priv_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        pub_hex = pub_bytes.hex()
        priv_hex = priv_bytes.hex()
    else:
        # Fallback: random hex (records marked unverified)
        import secrets
        priv_hex = secrets.token_hex(32)
        pub_hex = hashlib.sha256(bytes.fromhex(priv_hex)).hexdigest()

    # DID identifier = first 32 chars of sha256(pubkey hex) = 16 bytes
    agent_id = hashlib.sha256(pub_hex.encode()).hexdigest()[:32]
    did = f"did:ecp:{agent_id}"

    identity = {
        "did": did,
        "pub_key": pub_hex,
        "priv_key": priv_hex,   # local only, NEVER transmitted
        "created_at": _now_ms(),
        "verified": HAS_CRYPTO,
    }

    IDENTITY_FILE.write_text(json.dumps(identity, indent=2))
    return identity


def sign(identity: dict, data: str) -> str:
    """
    Sign data with agent's private key.
    Returns: "ed25519:{hex}" or "unverified"
    """
    if not HAS_CRYPTO or not identity.get("verified"):
        return "unverified"
    try:
        priv_bytes = bytes.fromhex(identity["priv_key"])
        private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
        sig_bytes = private_key.sign(data.encode())
        return f"ed25519:{sig_bytes.hex()}"
    except Exception:
        return "unverified"
