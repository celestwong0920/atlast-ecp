"""
ECP Record — data structure, chaining, and hashing.
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ECPStep:
    type: str           # "llm_call" | "tool_call" | "turn"
    in_hash: str        # sha256 of input (content never transmitted)
    out_hash: str       # sha256 of output
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    latency_ms: Optional[int] = None
    flags: Optional[list] = None   # e.g. ["hedge_detected", "retry"]


@dataclass
class ECPChain:
    prev: Optional[str]  # id of previous record (None if first)
    hash: str            # sha256 of this record's content


@dataclass
class ECPRecord:
    id: str
    agent: str           # did:ecp:{agent_id}
    ts: int              # unix ms
    step: ECPStep
    chain: ECPChain
    sig: str             # ed25519 signature of (id+agent+ts+in_hash+out_hash+prev)


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def hash_content(content) -> str:
    """Hash any content (str, list, dict) — content stays local."""
    if isinstance(content, str):
        raw = content
    else:
        raw = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return sha256(raw)


def create_record(
    agent_did: str,
    step_type: str,
    in_content,
    out_content,
    identity: dict,
    prev_record: Optional["ECPRecord"] = None,
    model: str = None,
    tokens_in: int = None,
    tokens_out: int = None,
    latency_ms: int = None,
    flags: list = None,
) -> ECPRecord:
    record_id = f"ecp_{uuid.uuid4().hex[:16]}"
    ts = int(time.time() * 1000)

    in_hash = hash_content(in_content)
    out_hash = hash_content(out_content)
    prev_id = prev_record.id if prev_record else None

    step = ECPStep(
        type=step_type,
        in_hash=in_hash,
        out_hash=out_hash,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        flags=flags or [],
    )

    # Signing payload — deterministic string
    sign_payload = f"{record_id}|{agent_did}|{ts}|{in_hash}|{out_hash}|{prev_id or 'genesis'}"

    from .identity import sign
    sig = sign(identity, sign_payload)

    # Record hash (used as chain link for next record)
    record_content = f"{record_id}{agent_did}{ts}{in_hash}{out_hash}{prev_id or ''}{sig}"
    record_hash = sha256(record_content)

    chain = ECPChain(prev=prev_id, hash=record_hash)

    return ECPRecord(
        id=record_id,
        agent=agent_did,
        ts=ts,
        step=step,
        chain=chain,
        sig=sig,
    )


def record_to_dict(record: ECPRecord) -> dict:
    return {
        "id": record.id,
        "agent": record.agent,
        "ts": record.ts,
        "step": asdict(record.step),
        "chain": asdict(record.chain),
        "sig": record.sig,
    }
