"""
ATLAST ECP — Evidence Chain Protocol SDK

Usage:
    from atlast_ecp import wrap
    from anthropic import Anthropic

    client = wrap(Anthropic())
    # That's it. Passive recording starts immediately.
"""

from .wrap import wrap
from .core import record, record_async, get_identity, reset
from .auto import init
from .identity import get_or_create_identity
from .record import create_record, record_to_dict
from .storage import save_record, load_records, load_record_by_id
from .signals import detect_flags, compute_trust_signals
from .batch import trigger_batch_upload, run_batch, start_scheduler
from .verify import (
    verify_signature,
    verify_merkle_proof,
    build_merkle_proof,
    verify_record,
    verify_record_with_key,
)
from .config import get_api_url, get_api_key, load_config, save_config

__version__ = "0.5.1"
__all__ = [
    # Core
    "wrap",
    "init",
    "record",
    "record_async",
    "get_identity",
    "reset",
    # Identity
    "get_or_create_identity",
    # Records
    "create_record",
    "record_to_dict",
    # Storage
    "save_record",
    "load_records",
    "load_record_by_id",
    # Signals
    "detect_flags",
    "compute_trust_signals",
    # Batch
    "trigger_batch_upload",
    "run_batch",
    "start_scheduler",
    # Verification (public API for llachat backend + third parties)
    "verify_signature",
    "verify_merkle_proof",
    "build_merkle_proof",
    "verify_record",
    "verify_record_with_key",
    # Config
    "get_api_url",
    "get_api_key",
    "load_config",
    "save_config",
]
