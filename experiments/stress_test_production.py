#!/usr/bin/env python3
"""
ATLAST ECP Production Stress Test Suite (ST1-ST4)

ST1: Production environment test (api.weba0.com)
ST2: Concurrent agents (10 parallel)
ST3: Long-running stability (configurable duration)
ST4: Server load test (HTTP bombardment)

Usage:
  python3 stress_test_production.py --test st1        # Production API
  python3 stress_test_production.py --test st2        # Concurrent
  python3 stress_test_production.py --test st4        # Server load
  python3 stress_test_production.py --test all        # All tests
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
import threading
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

# Add SDK to path
sys.path.insert(0, str(Path(__file__).parent.parent / "sdk" / "python"))

from atlast_ecp.identity import get_or_create_identity, sign as sign_data
from atlast_ecp.batch import build_merkle_tree, sha256
from atlast_ecp.record import create_record, record_to_dict
from atlast_ecp.storage import save_record, init_storage

PROD_BASE = "https://api.weba0.com"  # Base URL (no /v1)
PROD_API = f"{PROD_BASE}/v1"         # API prefix
RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_s: float
    details: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)


# ─── ST1: Production Environment Test ─────────────────────────────────────

def test_st1_production_api() -> TestResult:
    """Test core API endpoints on api.weba0.com."""
    start = time.time()
    errors = []
    checks = {}

    # 1. Health check
    try:
        req = urllib.request.Request(f"{PROD_BASE}/health", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            checks["health"] = data.get("status") == "ok"
    except Exception as e:
        checks["health"] = False
        errors.append(f"Health: {e}")

    # 2. Discovery
    try:
        req = urllib.request.Request(f"{PROD_BASE}/.well-known/ecp.json", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            checks["discovery"] = "endpoints" in data
    except Exception as e:
        checks["discovery"] = False
        errors.append(f"Discovery: {e}")

    # 3. Stats
    try:
        req = urllib.request.Request(f"{PROD_API}/stats", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            checks["stats"] = True
    except Exception as e:
        checks["stats"] = False
        errors.append(f"Stats: {e}")

    # 4. Batch upload (test)
    try:
        identity = get_or_create_identity()
        merkle_root = sha256("test_st1")
        sig = sign_data(identity, merkle_root)
        body = json.dumps({
            "merkle_root": merkle_root,
            "agent_did": identity["did"],
            "record_count": 1,
            "avg_latency_ms": 100,
            "batch_ts": int(time.time() * 1000),
            "sig": sig,
            "ecp_version": "0.1",
        }).encode()
        req = urllib.request.Request(
            f"{PROD_API}/batches",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            checks["batch_upload"] = data.get("batch_id", "").startswith("batch_")
    except Exception as e:
        checks["batch_upload"] = False
        errors.append(f"Batch upload: {e}")

    # 5. Verify endpoint
    try:
        req = urllib.request.Request(
            f"{PROD_API}/verify/batch_nonexistent",
            method="GET",
        )
        urllib.request.urlopen(req, timeout=10)
        checks["verify_endpoint"] = True
    except urllib.error.HTTPError as e:
        # 404 is expected for nonexistent batch — endpoint works
        checks["verify_endpoint"] = e.code == 404
    except Exception as e:
        checks["verify_endpoint"] = False
        errors.append(f"Verify: {e}")

    passed = all(checks.values())
    return TestResult(
        name="ST1: Production API",
        passed=passed,
        duration_s=time.time() - start,
        details={"checks": checks},
        errors=errors,
    )


# ─── ST2: Concurrent Agents ──────────────────────────────────────────────

def _agent_worker(agent_id: int, record_count: int = 5) -> dict:
    """Single agent: create records + build merkle tree."""
    import tempfile
    ecp_dir = tempfile.mkdtemp(prefix=f"ecp-st2-agent{agent_id}-")
    os.environ["ATLAST_ECP_DIR"] = ecp_dir
    # Re-init storage for this thread
    init_storage()

    records = []
    start = time.time()
    identity = get_or_create_identity()

    for i in range(record_count):
        rec = create_record(
            in_content=f"Agent {agent_id} input {i}",
            out_content=f"Agent {agent_id} output {i}",
            model=f"test-model-{agent_id}",
            latency_ms=50 + agent_id * 10,
            agent=identity["did"],
        )
        rec_dict = record_to_dict(rec)
        save_record(rec_dict)
        records.append(rec_dict)

    # Build merkle tree
    hashes = [r["chain"]["hash"] for r in records if r.get("chain", {}).get("hash")]
    merkle_root, _ = build_merkle_tree(hashes)

    return {
        "agent_id": agent_id,
        "records": len(records),
        "merkle_root": merkle_root,
        "duration_s": time.time() - start,
        "did": identity["did"],
    }


def test_st2_concurrent(num_agents: int = 10, records_per_agent: int = 5) -> TestResult:
    """Run N agents concurrently, each creating records."""
    start = time.time()
    errors = []
    results = []

    # Save original ECP_DIR
    orig_ecp_dir = os.environ.get("ATLAST_ECP_DIR", "")

    with ThreadPoolExecutor(max_workers=num_agents) as pool:
        futures = {
            pool.submit(_agent_worker, i, records_per_agent): i
            for i in range(num_agents)
        }
        for f in as_completed(futures):
            agent_id = futures[f]
            try:
                result = f.result()
                results.append(result)
            except Exception as e:
                errors.append(f"Agent {agent_id}: {e}")

    # Restore
    if orig_ecp_dir:
        os.environ["ATLAST_ECP_DIR"] = orig_ecp_dir

    total_records = sum(r["records"] for r in results)
    all_have_merkle = all(r["merkle_root"].startswith("sha256:") for r in results)

    passed = len(results) == num_agents and all_have_merkle and not errors
    return TestResult(
        name=f"ST2: {num_agents} Concurrent Agents",
        passed=passed,
        duration_s=time.time() - start,
        details={
            "agents_completed": len(results),
            "total_records": total_records,
            "all_merkle_valid": all_have_merkle,
            "per_agent": [
                {"id": r["agent_id"], "records": r["records"], "time": f"{r['duration_s']:.2f}s"}
                for r in sorted(results, key=lambda x: x["agent_id"])
            ],
        },
        errors=errors,
    )


# ─── ST4: Server Load Test ──────────────────────────────────────────────

def _http_request(url: str) -> tuple[int, float]:
    """Single HTTP request, returns (status_code, latency_ms)."""
    start = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return resp.status, (time.time() - start) * 1000
    except urllib.error.HTTPError as e:
        return e.code, (time.time() - start) * 1000
    except Exception:
        return 0, (time.time() - start) * 1000


def test_st4_server_load(target_rps: int = 20, duration_s: int = 10) -> TestResult:
    """HTTP load test against production server."""
    start = time.time()
    url = f"{PROD_BASE}/health"
    results = []
    errors_list = []

    total_requests = target_rps * duration_s

    with ThreadPoolExecutor(max_workers=min(target_rps, 50)) as pool:
        futures = []
        request_start = time.time()
        for i in range(total_requests):
            # Pace requests
            expected_time = request_start + (i / target_rps)
            wait = expected_time - time.time()
            if wait > 0:
                time.sleep(wait)
            futures.append(pool.submit(_http_request, url))

        for f in as_completed(futures):
            try:
                status, latency = f.result()
                results.append({"status": status, "latency_ms": latency})
            except Exception as e:
                errors_list.append(str(e))

    # Analyze
    status_counts = {}
    latencies = []
    for r in results:
        s = r["status"]
        status_counts[s] = status_counts.get(s, 0) + 1
        latencies.append(r["latency_ms"])

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0

    success_rate = status_counts.get(200, 0) / len(results) * 100 if results else 0
    # Accept if >80% success (some 429s expected from rate limiting)
    passed = success_rate > 80

    return TestResult(
        name=f"ST4: Server Load ({target_rps} RPS × {duration_s}s)",
        passed=passed,
        duration_s=time.time() - start,
        details={
            "total_requests": len(results),
            "status_counts": status_counts,
            "success_rate": f"{success_rate:.1f}%",
            "latency_p50_ms": f"{p50:.1f}",
            "latency_p95_ms": f"{p95:.1f}",
            "latency_p99_ms": f"{p99:.1f}",
            "actual_rps": f"{len(results) / (time.time() - start):.1f}",
        },
        errors=errors_list[:5],  # Truncate
    )


# ─── Runner ──────────────────────────────────────────────────────────────

def run_tests(test_filter: str = "all"):
    print("=" * 60)
    print("🔬 ATLAST ECP Production Stress Test Suite")
    print("=" * 60)

    tests = {
        "st1": ("ST1: Production API", test_st1_production_api),
        "st2": ("ST2: 10 Concurrent Agents", lambda: test_st2_concurrent(10, 5)),
        "st4": ("ST4: Server Load (20 RPS × 10s)", lambda: test_st4_server_load(20, 10)),
    }

    results = []
    for key, (name, fn) in tests.items():
        if test_filter != "all" and test_filter != key:
            continue

        print(f"\n{'─' * 50}")
        print(f"▶ Running {name}...")
        try:
            result = fn()
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"  {status} ({result.duration_s:.1f}s)")
            if result.details:
                for k, v in result.details.items():
                    if isinstance(v, list):
                        print(f"    {k}:")
                        for item in v[:5]:
                            print(f"      {item}")
                    else:
                        print(f"    {k}: {v}")
            if result.errors:
                print(f"  Errors: {result.errors[:3]}")
            results.append(result)
        except Exception as e:
            print(f"  ❌ CRASHED: {e}")
            results.append(TestResult(name=name, passed=False, duration_s=0, errors=[str(e)]))

    # Summary
    print(f"\n{'=' * 60}")
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"📊 Results: {passed}/{total} passed")
    for r in results:
        s = "✅" if r.passed else "❌"
        print(f"  {s} {r.name} ({r.duration_s:.1f}s)")

    # Save report
    RESULTS_DIR.mkdir(exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "summary": f"{passed}/{total} passed",
        "tests": [
            {
                "name": r.name,
                "passed": r.passed,
                "duration_s": round(r.duration_s, 2),
                "details": r.details,
                "errors": r.errors,
            }
            for r in results
        ],
    }
    report_file = RESULTS_DIR / "production_stress_report.json"
    report_file.write_text(json.dumps(report, indent=2))
    print(f"\n📄 Report saved: {report_file}")

    return all(r.passed for r in results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ATLAST ECP Production Stress Tests")
    parser.add_argument("--test", default="all", choices=["all", "st1", "st2", "st4"])
    args = parser.parse_args()

    ok = run_tests(args.test)
    sys.exit(0 if ok else 1)
