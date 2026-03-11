"""
ECP Identity — Agent DID generation and signing.
did:ecp:{sha256(pubkey)[:16]}
"""

import json
import hashlib
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


def get_or_create_identity() -> dict:
    """Load existing identity or generate a new one."""
    ECP_DIR.mkdir(exist_ok=True)

    if IDENTITY_FILE.exists():
        return json.loads(IDENTITY_FILE.read_text())

    return _create_identity()


def _create_identity() -> dict:
    if HAS_CRYPTO:
        private_key = Ed25519PrivateKey.generate()
        pub_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        priv_bytes = private_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        pub_hex = pub_bytes.hex()
        priv_hex = priv_bytes.hex()
    else:
        # Fallback: random hex (no signing, unverified mode)
        import secrets
        priv_hex = secrets.token_hex(32)
        pub_hex = hashlib.sha256(bytes.fromhex(priv_hex)).hexdigest()

    agent_id = hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:16]
    did = f"did:ecp:{agent_id}"

    identity = {
        "did": did,
        "pub_key": pub_hex,
        "priv_key": priv_hex,  # stored locally only, never transmitted
        "created_at": _now_ms(),
        "verified": HAS_CRYPTO,
    }

    IDENTITY_FILE.write_text(json.dumps(identity, indent=2))
    return identity


def sign(identity: dict, data: str) -> str:
    """Sign data with agent's private key. Returns hex signature."""
    if not HAS_CRYPTO or not identity.get("verified"):
        return "unverified"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        priv_bytes = bytes.fromhex(identity["priv_key"])
        private_key = Ed25519PrivateKey.from_private_bytes(priv_bytes)
        sig = private_key.sign(data.encode())
        return sig.hex()
    except Exception:
        return "unverified"


def _now_ms() -> int:
    import time
    return int(time.time() * 1000)
