"""Tests for ECP Reference Server — Insights endpoints (P3-1)."""

import pytest
from fastapi.testclient import TestClient

from server.main import app
from server.database import get_db, close_db
from server.merkle import build_merkle_root


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    import os
    os.environ["ECP_DB_PATH"] = str(tmp_path / "test.db")
    get_db()
    yield
    close_db()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def registered_agent(client):
    resp = client.post("/v1/agents/register", json={
        "did": "did:ecp:insights_test_agent",
        "public_key": "dGVzdGtleQ==",
        "handle": "insights-agent",
    })
    data = resp.json()
    return data


@pytest.fixture
def agent_with_data(client, registered_agent):
    """Agent with uploaded batch containing records with various metadata."""
    api_key = registered_agent["api_key"]
    hashes = [
        {"record_id": "rec_01", "chain_hash": "sha256:aaa1", "step_type": "llm_call",
         "ts": 1710000000000, "latency_ms": 500, "model": "gpt-4"},
        {"record_id": "rec_02", "chain_hash": "sha256:bbb2", "step_type": "tool_call",
         "ts": 1710000060000, "latency_ms": 1200},
        {"record_id": "rec_03", "chain_hash": "sha256:ccc3", "step_type": "llm_call",
         "ts": 1710000120000, "latency_ms": 300, "model": "gpt-4"},
    ]
    chain_hashes = [h["chain_hash"] for h in hashes]
    merkle_root = build_merkle_root(chain_hashes)

    resp = client.post("/v1/batches", json={
        "agent_did": "did:ecp:insights_test_agent",
        "batch_ts": 1710000000,
        "record_hashes": hashes,
        "merkle_root": merkle_root,
        "record_count": 3,
    }, headers={"X-Agent-Key": api_key})
    assert resp.status_code == 201, f"Batch upload failed: {resp.text}"

    return registered_agent


def test_performance_empty(client):
    resp = client.get("/v1/insights/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_records"] == 0


def test_performance_with_data(client, agent_with_data):
    resp = client.get("/v1/insights/performance", params={"agent_did": "did:ecp:insights_test_agent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_records"] == 3
    assert data["avg_latency_ms"] > 0


def test_trends_empty(client):
    resp = client.get("/v1/insights/trends")
    assert resp.status_code == 200
    data = resp.json()
    assert data["buckets"] == []


def test_trends_with_data(client, agent_with_data):
    resp = client.get("/v1/insights/trends", params={"agent_did": "did:ecp:insights_test_agent"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["buckets"]) >= 1


def test_trends_hour_bucket(client, agent_with_data):
    resp = client.get("/v1/insights/trends", params={"bucket": "hour"})
    assert resp.status_code == 200
    assert resp.json()["bucket_size"] == "hour"


def test_tools_empty(client):
    resp = client.get("/v1/insights/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tool_calls"] == 0
