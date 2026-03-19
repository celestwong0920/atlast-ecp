"""Tests for P3-2 (API Enhancement) + P3-4 (Discovery)."""

import os
import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.database import get_db, close_db
from server.merkle import build_merkle_root


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    os.environ["ECP_DB_PATH"] = str(tmp_path / "test.db")
    get_db()
    yield
    close_db()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def agent_with_batches(client):
    """Register agent and upload 3 batches."""
    resp = client.post("/v1/agents/register", json={
        "did": "did:ecp:pagtest",
        "public_key": "dGVzdA==",
        "handle": "pag-agent",
    })
    api_key = resp.json()["api_key"]

    for i in range(3):
        hashes = [
            {"record_id": f"rec_{i}_1", "chain_hash": f"sha256:h{i}a"},
            {"record_id": f"rec_{i}_2", "chain_hash": f"sha256:h{i}b"},
        ]
        root = build_merkle_root([h["chain_hash"] for h in hashes])
        client.post("/v1/batches", json={
            "agent_did": "did:ecp:pagtest",
            "batch_ts": 1710000000 + i * 1000,
            "record_hashes": hashes,
            "merkle_root": root,
            "record_count": 2,
        }, headers={"X-Agent-Key": api_key})

    return {"api_key": api_key, "handle": "pag-agent"}


# ── P3-2: Pagination ──

class TestPagination:
    def test_first_page(self, client, agent_with_batches):
        resp = client.get("/v1/agents/pag-agent/batches", params={"page": 1, "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["limit"] == 2
        assert len(data["items"]) == 2

    def test_second_page(self, client, agent_with_batches):
        resp = client.get("/v1/agents/pag-agent/batches", params={"page": 2, "limit": 2})
        data = resp.json()
        assert len(data["items"]) == 1  # 3rd batch

    def test_empty_page(self, client, agent_with_batches):
        resp = client.get("/v1/agents/pag-agent/batches", params={"page": 10, "limit": 2})
        data = resp.json()
        assert len(data["items"]) == 0
        assert data["total"] == 3

    def test_not_found(self, client):
        resp = client.get("/v1/agents/nonexistent/batches")
        assert resp.status_code == 404


# ── P3-2: Batch Detail ──

class TestBatchDetail:
    def test_detail_with_records(self, client, agent_with_batches):
        # Get first batch id
        batches = client.get("/v1/agents/pag-agent/batches").json()
        batch_id = batches["items"][0]["id"]

        resp = client.get(f"/v1/batches/{batch_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["batch_id"] == batch_id
        assert len(data["records"]) == 2

    def test_not_found(self, client):
        resp = client.get("/v1/batches/nonexistent-id")
        assert resp.status_code == 404


# ── P3-2: Handoffs ──

class TestHandoffs:
    def test_no_handoffs(self, client, agent_with_batches):
        resp = client.get("/v1/agents/pag-agent/handoffs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_not_found(self, client):
        resp = client.get("/v1/agents/nonexistent/handoffs")
        assert resp.status_code == 404


# ── P3-4: Discovery ──

class TestDiscovery:
    def test_well_known(self, client):
        resp = client.get("/.well-known/ecp.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ecp_version"] == "1.0"
        assert "batch" in data["capabilities"]
        assert "insights" in data["capabilities"]
        assert "discovery" in data["capabilities"]
        assert "handoffs" in data["capabilities"]
        assert len(data["endpoints"]) >= 10

    def test_capabilities_complete(self, client):
        data = client.get("/.well-known/ecp.json").json()
        expected = {"batch", "profile", "leaderboard", "insights", "handoffs", "discovery"}
        assert set(data["capabilities"]) == expected

    def test_auth_methods(self, client):
        data = client.get("/.well-known/ecp.json").json()
        assert "X-Agent-Key" in data["auth_methods"]
