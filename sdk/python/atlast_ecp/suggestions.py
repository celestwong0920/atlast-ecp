"""
ATLAST ECP — Auto-fix Suggestions

Rule-based suggestion engine. Analyzes records/incidents/flags
and generates actionable fix recommendations.

NOT LLM-based — pure pattern matching for consistency.
"""

from typing import Optional


# ── Suggestion Rules ──

def generate_suggestions(
    records: list,
    anomalies: Optional[list] = None,
    incidents: Optional[list] = None,
) -> list:
    """Generate fix suggestions from record patterns.

    Returns: [{severity, category, title, description, fix, confidence}]
    """
    suggestions = []
    if not records:
        return suggestions

    # Extract stats
    total = len(records)
    errors = [r for r in records if r.get("error")]
    error_rate = len(errors) / total if total else 0
    latencies = [r.get("latency_ms", 0) or 0 for r in records if r.get("latency_ms")]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    models = {}
    for r in records:
        m = r.get("model") or r.get("meta", {}).get("model", "")
        if m:
            models[m] = models.get(m, 0) + 1

    flags_all = []
    for r in records:
        f = r.get("flags", "")
        if isinstance(f, str):
            try:
                import json
                f = json.loads(f)
            except Exception:
                f = [x.strip() for x in f.split(",") if x.strip()]
        if isinstance(f, list):
            flags_all.extend(f)

    flag_counts = {}
    for f in flags_all:
        flag_counts[f] = flag_counts.get(f, 0) + 1

    # ── Rule 1: High error rate ──
    if error_rate > 0.10:
        sev = "critical" if error_rate > 0.30 else "warning"
        suggestions.append({
            "severity": sev,
            "category": "reliability",
            "title": "High error rate: %.0f%%" % (error_rate * 100),
            "description": "%d out of %d records have errors. This significantly impacts Trust Score." % (len(errors), total),
            "fix": "Check error patterns in the Records page. Common causes: invalid API keys, rate limiting, model unavailable. Consider adding retry logic with exponential backoff.",
            "confidence": 0.9,
        })

    # ── Rule 2: Rate limiting ──
    rate_limit_count = flag_counts.get("rate_limit", 0) + flag_counts.get("429", 0)
    if rate_limit_count > 3:
        suggestions.append({
            "severity": "warning",
            "category": "performance",
            "title": "Rate limiting detected (%d occurrences)" % rate_limit_count,
            "description": "Your agent is hitting API rate limits. This causes retries and slower responses.",
            "fix": "Add delay between API calls (time.sleep(1)), implement exponential backoff, or upgrade your API plan. Consider batching requests where possible.",
            "confidence": 0.95,
        })

    # ── Rule 3: High latency ──
    if avg_latency > 15000:
        suggestions.append({
            "severity": "warning",
            "category": "performance",
            "title": "High average latency: %.1fs" % (avg_latency / 1000),
            "description": "Average response time is %.1f seconds. Users experience significant wait times." % (avg_latency / 1000),
            "fix": "Consider: (1) Use a faster model (e.g., gpt-4o-mini instead of gpt-4o), (2) Lower max_tokens if full responses aren't needed, (3) Use streaming for better perceived performance.",
            "confidence": 0.85,
        })

    # ── Rule 4: Expensive model for simple tasks ──
    expensive_models = {"gpt-4o", "gpt-4", "claude-opus", "claude-3-opus"}
    cheap_models = {"gpt-4o-mini", "gpt-3.5-turbo", "claude-haiku", "claude-3-5-haiku"}
    for model, count in models.items():
        model_lower = model.lower()
        if any(e in model_lower for e in expensive_models) and count > 10:
            if avg_latency < 3000:  # Fast responses = simple tasks
                suggestions.append({
                    "severity": "info",
                    "category": "cost",
                    "title": "Premium model used for potentially simple tasks",
                    "description": "%s used %d times with avg latency %.1fs. Fast responses suggest tasks may not need a premium model." % (model, count, avg_latency / 1000),
                    "fix": "Consider switching to a faster/cheaper model (e.g., gpt-4o-mini, claude-haiku) for simple tasks. Reserve premium models for complex reasoning.",
                    "confidence": 0.6,
                })

    # ── Rule 5: No chain integrity ──
    unchained = sum(1 for r in records if not r.get("chain_hash") and not r.get("chain", {}).get("hash"))
    if unchained > total * 0.5 and total > 5:
        suggestions.append({
            "severity": "info",
            "category": "evidence",
            "title": "%.0f%% of records missing chain links" % (unchained / total * 100),
            "description": "%d out of %d records don't have chain hashes. This weakens evidence integrity and Trust Score." % (unchained, total),
            "fix": "Ensure atlast init has been run and identity is set up. Chain linking happens automatically when Ed25519 identity is available.",
            "confidence": 0.8,
        })

    # ── Rule 6: Empty outputs ──
    empty_out = sum(1 for r in records if not (r.get("output_preview") or "").strip())
    if empty_out > total * 0.3 and total > 5:
        suggestions.append({
            "severity": "warning",
            "category": "quality",
            "title": "%.0f%% of records have empty outputs" % (empty_out / total * 100),
            "description": "%d records have no output content. This could indicate agent failures or tool-only calls." % empty_out,
            "fix": "Check if your agent is returning empty responses. For tool-call-only conversations, this may be normal — verify by looking at the tool call details.",
            "confidence": 0.7,
        })

    # ── Rule 7: Infra errors ──
    infra_count = sum(1 for r in records if r.get("is_infra"))
    if infra_count > 5:
        suggestions.append({
            "severity": "warning",
            "category": "infrastructure",
            "title": "%d infrastructure errors" % infra_count,
            "description": "Network timeouts, API 500/502/503 errors detected. These are not your agent's fault.",
            "fix": "Check your API provider's status page. Consider implementing retry with backoff. If using a proxy, verify the proxy is running correctly (atlast doctor).",
            "confidence": 0.9,
        })

    # ── Rule 8: Active incidents ──
    if incidents:
        active = [i for i in incidents if i.get("status") == "created"]
        if active:
            suggestions.append({
                "severity": "critical",
                "category": "incident",
                "title": "%d active incident(s)" % len(active),
                "description": "There are ongoing incidents: %s" % ", ".join(i.get("reason", "?")[:40] for i in active),
                "fix": "Check the Incidents section for details. Recent changes to prompts, models, or infrastructure may have caused the regression.",
                "confidence": 1.0,
            })

    # Deduplicate by title
    seen = set()
    unique = []
    for s in suggestions:
        if s["title"] not in seen:
            seen.add(s["title"])
            unique.append(s)

    # Sort by severity
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    unique.sort(key=lambda s: severity_order.get(s["severity"], 3))

    return unique
