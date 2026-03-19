"""
ECP Reference Server — Merkle Tree Verification

Algorithm matches SDK batch.py build_merkle_tree() exactly:
1. Keep original hash order (NO sorting — order-preserving)
2. Pad odd-length layers by duplicating last element
3. Pair adjacent hashes, SHA-256(concat) each pair
4. Repeat until one root remains

IMPORTANT: Do NOT sort hashes. SDK builds Merkle tree in insertion order.
Sorting would produce a different root, breaking verification.
"""

from __future__ import annotations

import hashlib


def build_merkle_root(hashes: list[str]) -> str:
    """Build Merkle root from a list of hash strings. Matches Python SDK algorithm."""
    if not hashes:
        return ""
    if len(hashes) == 1:
        return hashes[0]

    # Keep original order — must match SDK batch.py exactly
    layer = list(hashes)

    while len(layer) > 1:
        # Pad odd-length layer by duplicating last element (matches SDK)
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        next_layer = []
        for i in range(0, len(layer), 2):
            combined = layer[i] + layer[i + 1]
            h = hashlib.sha256(combined.encode()).hexdigest()
            next_layer.append(f"sha256:{h}")
        layer = next_layer

    return layer[0]


def verify_merkle_root(record_hashes: list[str], claimed_root: str) -> bool:
    """Verify that record hashes produce the claimed Merkle root."""
    if not record_hashes:
        return claimed_root == ""
    computed = build_merkle_root(record_hashes)
    return computed == claimed_root
