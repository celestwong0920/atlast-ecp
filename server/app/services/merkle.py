"""
Merkle tree utilities for Super-Batch aggregation.

Builds a binary Merkle tree from individual batch roots,
generates inclusion proofs, and verifies them.
"""

import hashlib


def sha256(data: str) -> str:
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def build_super_merkle_tree(roots: list[str]) -> tuple[str, list[list[str]]]:
    """Build a Merkle tree from a list of roots. Returns (super_root, layers)."""
    if not roots:
        return sha256("empty"), [[]]
    if len(roots) == 1:
        return roots[0], [roots]
    current = list(roots)
    layers = [current[:]]
    while len(current) > 1:
        next_layer = []
        for i in range(0, len(current), 2):
            if i + 1 < len(current):
                combined = current[i] + current[i + 1]
            else:
                combined = current[i] + current[i]  # duplicate odd
            next_layer.append(sha256(combined))
        current = next_layer
        layers.append(current[:])
    return current[0], layers


def get_inclusion_proof(roots: list[str], index: int) -> list[dict]:
    """Generate a Merkle inclusion proof for the root at `index`."""
    if len(roots) <= 1:
        return []
    proof = []
    current = list(roots)
    idx = index
    while len(current) > 1:
        if idx % 2 == 0:
            sibling_idx = idx + 1
            position = "right"
        else:
            sibling_idx = idx - 1
            position = "left"
        if sibling_idx < len(current):
            proof.append({"hash": current[sibling_idx], "position": position})
        else:
            proof.append({"hash": current[idx], "position": "right"})  # duplicate
        next_layer = []
        for i in range(0, len(current), 2):
            if i + 1 < len(current):
                combined = current[i] + current[i + 1]
            else:
                combined = current[i] + current[i]
            next_layer.append(sha256(combined))
        current = next_layer
        idx = idx // 2
    return proof


def verify_inclusion(root_hash: str, proof: list[dict], super_root: str) -> bool:
    """Verify that root_hash is included in the super_root via the proof."""
    current = root_hash
    for step in proof:
        if step["position"] == "right":
            combined = current + step["hash"]
        else:
            combined = step["hash"] + current
        current = sha256(combined)
    return current == super_root
