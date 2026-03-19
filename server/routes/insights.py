"""
ECP Reference Server — Insights Endpoints (P3-1)

GET /v1/insights/performance?agent_did=&period=
GET /v1/insights/trends?agent_did=&bucket=day|hour
GET /v1/insights/tools?agent_did=&top_n=10
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..database import get_db
from ..models import PerformanceResponse, TrendsResponse, ToolsResponse

router = APIRouter(prefix="/v1/insights", tags=["insights"])


def _get_records_for_agent(agent_did: str | None = None, limit: int = 10000) -> list[dict]:
    """Fetch record_hashes rows, optionally filtered by agent DID."""
    conn = get_db()
    if not conn:
        return []

    if agent_did:
        rows = conn.execute(
            """SELECT rh.record_id, rh.chain_hash, rh.step_type, rh.ts,
                      rh.flags, rh.latency_ms, rh.model, b.agent_id, a.did
               FROM record_hashes rh
               JOIN batches b ON rh.batch_id = b.id
               JOIN agents a ON b.agent_id = a.id
               WHERE a.did = ?
               ORDER BY rh.ts DESC LIMIT ?""",
            (agent_did, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT rh.record_id, rh.chain_hash, rh.step_type, rh.ts,
                      rh.flags, rh.latency_ms, rh.model, b.agent_id, a.did
               FROM record_hashes rh
               JOIN batches b ON rh.batch_id = b.id
               JOIN agents a ON b.agent_id = a.id
               ORDER BY rh.ts DESC LIMIT ?""",
            (limit,),
        ).fetchall()

    # Convert to ECP v1.0 record format for insights functions
    import json
    records = []
    for row in rows:
        flags = []
        if row[4]:
            try:
                flags = json.loads(row[4])
            except Exception:
                pass
        records.append({
            "ecp": "1.0",
            "id": row[0],
            "ts": row[3] or 0,
            "agent": row[8],
            "action": row[2] or "unknown",
            "in_hash": row[1],
            "out_hash": row[1],
            "meta": {
                "model": row[6],
                "latency_ms": row[5],
                "flags": flags,
            },
        })
    return records


@router.get("/performance", response_model=PerformanceResponse)
def insights_performance(
    agent_did: str | None = Query(None, description="Filter by agent DID"),
    limit: int = Query(10000, ge=1, le=100000),
):
    """Performance analysis: latency, throughput, success rate, by-model."""
    from atlast_ecp.insights import analyze_performance
    records = _get_records_for_agent(agent_did, limit)
    return analyze_performance(records)


@router.get("/trends", response_model=TrendsResponse)
def insights_trends(
    agent_did: str | None = Query(None, description="Filter by agent DID"),
    bucket: str = Query("day", description="Bucket size: day or hour"),
    limit: int = Query(10000, ge=1, le=100000),
):
    """Time-series trend analysis."""
    from atlast_ecp.insights import analyze_trends
    records = _get_records_for_agent(agent_did, limit)
    return analyze_trends(records, bucket=bucket)


@router.get("/tools", response_model=ToolsResponse)
def insights_tools(
    agent_did: str | None = Query(None, description="Filter by agent DID"),
    top_n: int = Query(10, ge=1, le=100),
    limit: int = Query(10000, ge=1, le=100000),
):
    """Tool usage analysis."""
    from atlast_ecp.insights import analyze_tools
    records = _get_records_for_agent(agent_did, limit)
    return analyze_tools(records, top_n=top_n)
