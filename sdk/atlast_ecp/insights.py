"""
ATLAST ECP Insights — local analysis of ECP records.

Usage:
    atlast insights              # Full report
    atlast insights --top 5      # Top 5 issues
    atlast insights --json       # Machine-readable output

Analyzes locally stored ECP records to surface:
- Latency bottlenecks
- Cost hotspots (by model)
- Error/retry patterns
- Flag distribution
- Agent activity summary

Privacy: runs entirely locally. No data leaves your device.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Optional


def analyze_records(records: list[dict], top_n: int = 10) -> dict:
    """
    Analyze a list of ECP records and return insights.

    Returns a dict with sections: summary, latency, models, flags, errors, recommendations.
    """
    if not records:
        return {
            "summary": {"total_records": 0, "unique_agents": 0, "agents": [],
                        "action_breakdown": {}, "time_span_hours": 0,
                        "avg_latency_ms": 0, "total_tokens_in": 0,
                        "total_tokens_out": 0, "total_tokens": 0},
            "latency_by_model": {}, "model_usage": [], "flags": {},
            "error_count": 0, "high_latency_count": 0,
            "recommendations": ["No records found. Start recording with: atlast run python my_agent.py"],
        }

    # ── Summary ───────────────────────────────────────────────────────────
    total = len(records)
    agents = set()
    actions = Counter()
    models = Counter()
    total_latency = 0
    latency_count = 0
    total_tokens_in = 0
    total_tokens_out = 0
    flag_counter = Counter()
    error_records = []
    high_latency_records = []
    timestamps = []

    for rec in records:
        # Agent
        agent = rec.get("agent") or rec.get("agent_did", "unknown")
        agents.add(agent)

        # Action
        action = rec.get("action") or rec.get("step", {}).get("type", "unknown")
        actions[action] += 1

        # Timestamp
        ts = rec.get("ts")
        if ts:
            timestamps.append(ts)

        # Meta (v1.0) or step (v0.1)
        meta = rec.get("meta", {})

        # Model
        model = meta.get("model")
        if model:
            models[model] += 1

        # Latency
        latency = meta.get("latency_ms", 0)
        if latency:
            total_latency += latency
            latency_count += 1

        # Tokens
        if meta.get("tokens_in"):
            total_tokens_in += meta["tokens_in"]
        if meta.get("tokens_out"):
            total_tokens_out += meta["tokens_out"]

        # Flags
        flags = meta.get("flags", [])
        for f in flags:
            flag_counter[f] += 1

        if "error" in flags:
            error_records.append(rec)
        if "high_latency" in flags:
            high_latency_records.append(rec)

    avg_latency = total_latency / latency_count if latency_count else 0

    # Time span
    time_span_hours = 0
    if len(timestamps) >= 2:
        time_span_ms = max(timestamps) - min(timestamps)
        time_span_hours = time_span_ms / (1000 * 60 * 60)

    summary = {
        "total_records": total,
        "unique_agents": len(agents),
        "agents": sorted(agents),
        "action_breakdown": dict(actions.most_common()),
        "time_span_hours": round(time_span_hours, 1),
        "avg_latency_ms": round(avg_latency),
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
        "total_tokens": total_tokens_in + total_tokens_out,
    }

    # ── Latency Analysis ──────────────────────────────────────────────────
    latency_by_model = defaultdict(list)
    for rec in records:
        meta = rec.get("meta", {})
        model = meta.get("model", "unknown")
        lat = meta.get("latency_ms")
        if lat:
            latency_by_model[model].append(lat)

    latency_insights = {}
    for model, lats in sorted(latency_by_model.items(), key=lambda x: -max(x[1])):
        latency_insights[model] = {
            "count": len(lats),
            "avg_ms": round(sum(lats) / len(lats)),
            "max_ms": max(lats),
            "min_ms": min(lats),
            "p90_ms": round(sorted(lats)[int(len(lats) * 0.9)] if len(lats) >= 2 else lats[0]),
        }

    # ── Model Usage ───────────────────────────────────────────────────────
    model_usage = []
    for model, count in models.most_common(top_n):
        pct = round(count / total * 100, 1)
        model_usage.append({"model": model, "calls": count, "percentage": pct})

    # ── Flag Analysis ─────────────────────────────────────────────────────
    flag_analysis = {}
    for flag, count in flag_counter.most_common():
        pct = round(count / total * 100, 1)
        flag_analysis[flag] = {"count": count, "percentage": pct}

    # ── Recommendations ───────────────────────────────────────────────────
    recommendations = []

    error_rate = len(error_records) / total * 100 if total else 0
    if error_rate > 5:
        recommendations.append(f"⚠️  High error rate: {error_rate:.1f}% of records have errors. Check your prompts or API reliability.")
    
    high_lat_rate = len(high_latency_records) / total * 100 if total else 0
    if high_lat_rate > 10:
        recommendations.append(f"🐌 {high_lat_rate:.1f}% of calls have high latency. Consider using a faster model or reducing prompt size.")

    if flag_counter.get("hedged", 0) / total > 0.2 if total else False:
        recommendations.append("🤔 >20% of responses are hedged. Consider more specific prompts to reduce uncertainty.")

    if flag_counter.get("retried", 0) / total > 0.1 if total else False:
        recommendations.append("🔄 >10% retry rate. Check for rate limiting or transient API errors.")

    if avg_latency > 10000:
        recommendations.append(f"⏱️  Average latency is {avg_latency/1000:.1f}s. Consider streaming or async patterns.")

    # Model-specific
    for model, stats in latency_insights.items():
        if stats["max_ms"] > 30000:
            recommendations.append(f"🔥 {model}: max latency {stats['max_ms']/1000:.1f}s. Consider timeout + retry logic.")

    if not recommendations:
        recommendations.append("✅ No major issues detected. Your agent is running well!")

    return {
        "summary": summary,
        "latency_by_model": latency_insights,
        "model_usage": model_usage,
        "flags": flag_analysis,
        "error_count": len(error_records),
        "high_latency_count": len(high_latency_records),
        "recommendations": recommendations,
    }


def format_report(insights: dict) -> str:
    """Format insights as a human-readable report."""
    lines = []
    lines.append("\n🔗 ATLAST ECP Insights Report")
    lines.append("=" * 50)

    s = insights["summary"]
    lines.append(f"\n📊 Summary")
    lines.append(f"   Records: {s['total_records']}")
    lines.append(f"   Agents:  {s['unique_agents']} ({', '.join(s.get('agents', [])[:5])})")
    lines.append(f"   Period:  {s['time_span_hours']}h")
    if s["avg_latency_ms"]:
        lines.append(f"   Avg latency: {s['avg_latency_ms']}ms")
    if s["total_tokens"]:
        lines.append(f"   Tokens: {s['total_tokens']:,} ({s['total_tokens_in']:,} in / {s['total_tokens_out']:,} out)")

    # Action breakdown
    actions = s.get("action_breakdown", {})
    if actions:
        lines.append(f"\n📋 Actions")
        for action, count in actions.items():
            lines.append(f"   {action}: {count}")

    # Model usage
    models = insights.get("model_usage", [])
    if models:
        lines.append(f"\n🤖 Model Usage")
        for m in models:
            lines.append(f"   {m['model']}: {m['calls']} calls ({m['percentage']}%)")

    # Latency by model
    latency = insights.get("latency_by_model", {})
    if latency:
        lines.append(f"\n⏱️  Latency by Model")
        for model, stats in latency.items():
            lines.append(f"   {model}: avg {stats['avg_ms']}ms, p90 {stats['p90_ms']}ms, max {stats['max_ms']}ms")

    # Flags
    flags = insights.get("flags", {})
    if flags:
        lines.append(f"\n🚩 Flags Detected")
        for flag, info in flags.items():
            lines.append(f"   {flag}: {info['count']} ({info['percentage']}%)")

    # Recommendations
    recs = insights.get("recommendations", [])
    if recs:
        lines.append(f"\n💡 Recommendations")
        for r in recs:
            lines.append(f"   {r}")

    lines.append("")
    return "\n".join(lines)


def cmd_insights(args: list[str]):
    """CLI entry point for 'atlast insights'."""
    from .storage import load_records

    limit = 1000
    top_n = 10
    as_json = "--json" in args

    for i, a in enumerate(args):
        if a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])
        if a == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])

    records = load_records(limit=limit)
    insights = analyze_records(records, top_n=top_n)

    if as_json:
        print(json.dumps(insights, indent=2, ensure_ascii=False))
    else:
        print(format_report(insights))
