"""
Super-Batch routes — public verification endpoint.
"""

import json
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..db.database import get_session, SuperBatch

router = APIRouter()


@router.get("/v1/super-batches/{super_batch_id}")
async def get_super_batch(super_batch_id: str):
    """Get super-batch details for public verification."""
    session = await get_session()
    if session is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    async with session:
        result = await session.execute(
            select(SuperBatch).where(SuperBatch.super_batch_id == super_batch_id)
        )
        record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Super-batch not found")

    return {
        "super_batch_id": record.super_batch_id,
        "super_merkle_root": record.super_merkle_root,
        "attestation_uid": record.attestation_uid,
        "eas_tx_hash": record.eas_tx_hash,
        "batch_count": record.batch_count,
        "batch_ids": json.loads(record.batch_ids),
        "status": record.status,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "anchored_at": record.anchored_at.isoformat() if record.anchored_at else None,
    }
