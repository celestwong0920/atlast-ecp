"""
ECP Signals — passive behavioral signal detection.
All signals are detected locally, never LLM-as-Judge.
Agent cannot control or self-report these.
"""

import re
from typing import Optional

# Hedge language patterns (locale-aware)
HEDGE_PATTERNS = [
    # English
    r"\bi think\b", r"\bi believe\b", r"\bi'm not sure\b",
    r"\bprobably\b", r"\bperhaps\b", r"\bmaybe\b", r"\bmight\b",
    r"\bcould be\b", r"\bit's possible\b", r"\bpossibly\b",
    r"\buncertain\b", r"\bnot certain\b", r"\bnot sure\b",
    r"\bi'm unsure\b", r"\bapproximately\b", r"\baround\b",
    r"\bit seems\b", r"\bseems like\b", r"\bappears to\b",
    r"\bto the best of my knowledge\b", r"\bif i recall\b",
    r"\bi may be wrong\b", r"\btake this with\b",
    # Chinese
    r"我觉得", r"我认为", r"可能", r"也许", r"大概",
    r"不确定", r"应该是", r"或许", r"似乎", r"好像",
    r"不太清楚", r"不是很确定", r"我不确定",
]

# Compiled patterns (performance)
_COMPILED_HEDGE = [re.compile(p, re.IGNORECASE) for p in HEDGE_PATTERNS]

# Incomplete/abandonment patterns
INCOMPLETE_PATTERNS = [
    r"\bi cannot\b", r"\bi can't\b", r"\bunable to\b",
    r"\bnot able to\b", r"\boutside my (capabilities|scope|knowledge)\b",
    r"\bi don't have access\b", r"\bi apologize.{0,30}(can't|cannot|unable)\b",
    r"无法", r"做不到", r"超出了我的", r"我没有权限",
]
_COMPILED_INCOMPLETE = [re.compile(p, re.IGNORECASE) for p in INCOMPLETE_PATTERNS]

# Error signal patterns
ERROR_PATTERNS = [
    r"\berror\b", r"\bexception\b", r"\bfailed\b", r"\bfailure\b",
    r"\btraceback\b", r"\bstack trace\b",
]
_COMPILED_ERROR = [re.compile(p, re.IGNORECASE) for p in ERROR_PATTERNS]


def detect_flags(output_text: str, is_retry: bool = False) -> list[str]:
    """
    Passively detect behavioral flags from output text.
    Returns list of flag strings.
    """
    flags = []

    if not output_text:
        return ["incomplete"]

    text = output_text.strip()

    # Retry signal (set externally when the same task is invoked again)
    if is_retry:
        flags.append("retried")

    # Hedge detection
    if _detect_hedge(text):
        flags.append("hedged")

    # Incomplete detection
    if _detect_incomplete(text):
        flags.append("incomplete")

    # Error detection
    if _detect_error(text):
        flags.append("error")

    return flags


def _detect_hedge(text: str) -> bool:
    """Returns True if output contains hedge language."""
    for pattern in _COMPILED_HEDGE:
        if pattern.search(text):
            return True
    return False


def _detect_incomplete(text: str) -> bool:
    """Returns True if output signals inability to complete the task."""
    for pattern in _COMPILED_INCOMPLETE:
        if pattern.search(text):
            return True
    return False


def _detect_error(text: str) -> bool:
    """Returns True if output contains error signals."""
    for pattern in _COMPILED_ERROR:
        if pattern.search(text):
            return True
    return False


def compute_trust_signals(records: list[dict]) -> dict:
    """
    Compute aggregate Trust Score signals from a list of ECP records.
    Used for batch reporting, not for individual record scoring.
    """
    if not records:
        return {
            "total": 0,
            "retried_rate": 0.0,
            "hedged_rate": 0.0,
            "incomplete_rate": 0.0,
            "error_rate": 0.0,
            "chain_integrity": 1.0,
            "avg_latency_ms": 0,
        }

    total = len(records)
    retried = sum(1 for r in records if "retried" in (r.get("step", {}).get("flags") or []))
    hedged = sum(1 for r in records if "hedged" in (r.get("step", {}).get("flags") or []))
    incomplete = sum(1 for r in records if "incomplete" in (r.get("step", {}).get("flags") or []))
    errors = sum(1 for r in records if "error" in (r.get("step", {}).get("flags") or []))
    latencies = [r["step"]["latency_ms"] for r in records if r.get("step", {}).get("latency_ms")]

    # Chain integrity: check prev links are consistent
    chain_ok = _check_chain_integrity(records)

    return {
        "total": total,
        "retried_rate": round(retried / total, 4),
        "hedged_rate": round(hedged / total, 4),
        "incomplete_rate": round(incomplete / total, 4),
        "error_rate": round(errors / total, 4),
        "chain_integrity": 1.0 if chain_ok else 0.0,
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
    }


def _check_chain_integrity(records: list[dict]) -> bool:
    """Verify that the chain of records is unbroken."""
    if len(records) <= 1:
        return True
    for i in range(1, len(records)):
        expected_prev = records[i - 1]["id"]
        actual_prev = records[i].get("chain", {}).get("prev")
        if actual_prev != expected_prev:
            return False
    return True
