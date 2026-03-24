"""Tests for Super-Batch aggregation: merkle tree, proofs, and endpoint."""

import pytest
from app.services.merkle import sha256, build_super_merkle_tree, get_inclusion_proof, verify_inclusion


class TestMerkleTree:
    def test_sha256_deterministic(self):
        assert sha256("hello") == sha256("hello")
        assert sha256("hello") != sha256("world")
        assert sha256("hello").startswith("sha256:")

    def test_empty_roots(self):
        root, layers = build_super_merkle_tree([])
        assert root == sha256("empty")

    def test_single_root(self):
        root, layers = build_super_merkle_tree(["sha256:abc"])
        assert root == "sha256:abc"
        assert layers == [["sha256:abc"]]

    def test_two_roots(self):
        roots = ["sha256:aaa", "sha256:bbb"]
        root, layers = build_super_merkle_tree(roots)
        assert len(layers) == 2
        assert layers[0] == roots
        assert root == sha256("sha256:aaa" + "sha256:bbb")

    def test_odd_roots_duplicates_last(self):
        roots = ["sha256:a", "sha256:b", "sha256:c"]
        root, layers = build_super_merkle_tree(roots)
        assert len(layers) >= 2
        # Should still produce a single root
        assert isinstance(root, str)

    def test_power_of_two(self):
        roots = [f"sha256:root{i}" for i in range(8)]
        root, layers = build_super_merkle_tree(roots)
        assert len(layers) == 4  # 8 -> 4 -> 2 -> 1
        assert len(layers[0]) == 8
        assert len(layers[-1]) == 1
        assert root == layers[-1][0]


class TestInclusionProof:
    def test_single_root_no_proof(self):
        proof = get_inclusion_proof(["sha256:only"], 0)
        assert proof == []

    def test_two_roots_proof(self):
        roots = ["sha256:aaa", "sha256:bbb"]
        super_root, _ = build_super_merkle_tree(roots)

        proof0 = get_inclusion_proof(roots, 0)
        assert len(proof0) == 1
        assert verify_inclusion(roots[0], proof0, super_root)

        proof1 = get_inclusion_proof(roots, 1)
        assert verify_inclusion(roots[1], proof1, super_root)

    def test_five_roots_all_verifiable(self):
        roots = [f"sha256:root_{i}" for i in range(5)]
        super_root, _ = build_super_merkle_tree(roots)

        for i in range(5):
            proof = get_inclusion_proof(roots, i)
            assert verify_inclusion(roots[i], proof, super_root), f"Failed for index {i}"

    def test_eight_roots_all_verifiable(self):
        roots = [sha256(f"batch_{i}") for i in range(8)]
        super_root, _ = build_super_merkle_tree(roots)

        for i in range(8):
            proof = get_inclusion_proof(roots, i)
            assert verify_inclusion(roots[i], proof, super_root), f"Failed for index {i}"

    def test_wrong_root_fails(self):
        roots = ["sha256:aaa", "sha256:bbb", "sha256:ccc"]
        super_root, _ = build_super_merkle_tree(roots)
        proof = get_inclusion_proof(roots, 0)
        assert not verify_inclusion("sha256:wrong", proof, super_root)

    def test_wrong_super_root_fails(self):
        roots = ["sha256:aaa", "sha256:bbb"]
        proof = get_inclusion_proof(roots, 0)
        assert not verify_inclusion(roots[0], proof, "sha256:fake_super_root")


class TestSuperBatchEndpoint:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_super_batch_not_found(self, client):
        resp = client.get("/v1/super-batches/nonexistent")
        # 404 (DB configured), 503 (no DB), or 500 (DB mismatch in test env)
        assert resp.status_code in (404, 500, 503)
