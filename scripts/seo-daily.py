#!/usr/bin/env python3
"""
seo-daily — GSC + GA4 daily snapshot for weba0.com, with bot-signal detection.

Usage:
    python3 scripts/seo-daily.py                 # headline metrics (fast)
    python3 scripts/seo-daily.py --days 14       # longer GSC lookback
    python3 scripts/seo-daily.py --inspect       # also run URL Inspection API per sitemap URL
    python3 scripts/seo-daily.py --json          # machine-readable output

Exit codes:
    0  clean — no anomalies
    2  anomaly — bot signal detected OR indexing issues (if --inspect)

Credentials:
    ATLAST_WEBA0_KEY env var, or ~/Desktop/atlast-weba0-96fc884738f5.json (default).
"""
import argparse
import json
import os
import sys
import warnings
import urllib.request
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore")

DEFAULT_KEY = Path.home() / "Desktop" / "atlast-weba0-96fc884738f5.json"
GSC_SITE = "https://weba0.com/"
GA4_PROPERTY = "properties/530424771"
SITEMAP_URL = "https://weba0.com/sitemap.xml"


def _color(s, code, enabled):
    return f"\033[{code}m{s}\033[0m" if enabled else s


class Out:
    def __init__(self, color=True):
        self.color = color and sys.stdout.isatty()

    def h(self, s): print(f"\n{_color(s, '1', self.color)}")
    def ok(self, s): print(f"  {_color('✅', '32', self.color)} {s}")
    def w(self, s):  print(f"  {_color('⚠', '33', self.color)}  {s}")
    def bad(self, s): print(f"  {_color('🚨', '31', self.color)} {s}")
    def dim(self, s): print(f"     {_color(s, '2', self.color)}")


def load_credentials(key_path):
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )


def fetch_sitemap_urls(url=SITEMAP_URL):
    with urllib.request.urlopen(url, timeout=10) as r:
        body = r.read().decode()
    return re.findall(r"<loc>([^<]+)</loc>", body)


def gsc_daily_metrics(gsc, days):
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    resp = gsc.searchanalytics().query(
        siteUrl=GSC_SITE,
        body={"startDate": start.isoformat(), "endDate": end.isoformat(),
              "dimensions": ["date"], "rowLimit": days + 1},
    ).execute()
    return [{
        "date": r["keys"][0],
        "clicks": int(r["clicks"]),
        "impressions": int(r["impressions"]),
        "ctr": r["ctr"],
        "position": r["position"],
    } for r in resp.get("rows", [])]


def gsc_top_queries(gsc, date_str, limit=15):
    resp = gsc.searchanalytics().query(
        siteUrl=GSC_SITE,
        body={"startDate": date_str, "endDate": date_str,
              "dimensions": ["query"], "rowLimit": limit},
    ).execute()
    return [{"query": r["keys"][0], "clicks": int(r["clicks"]),
             "impressions": int(r["impressions"]),
             "ctr": r["ctr"], "position": r["position"]}
            for r in resp.get("rows", [])]


def gsc_top_pages(gsc, date_str, limit=10):
    resp = gsc.searchanalytics().query(
        siteUrl=GSC_SITE,
        body={"startDate": date_str, "endDate": date_str,
              "dimensions": ["page"], "rowLimit": limit},
    ).execute()
    return [{"page": r["keys"][0], "clicks": int(r["clicks"]),
             "impressions": int(r["impressions"])}
            for r in resp.get("rows", [])]


def ga4_headline(ga4, start="yesterday", end="today"):
    from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
    req = RunReportRequest(
        property=GA4_PROPERTY,
        date_ranges=[DateRange(start_date=start, end_date=end)],
        metrics=[Metric(name=m) for m in [
            "activeUsers", "sessions", "screenPageViews",
            "bounceRate", "averageSessionDuration", "engagementRate", "newUsers",
        ]],
    )
    resp = ga4.run_report(req)
    if not resp.rows:
        return None
    v = [x.value for x in resp.rows[0].metric_values]
    return {
        "active_users": int(v[0]),
        "sessions": int(v[1]),
        "pageviews": int(v[2]),
        "bounce_rate": float(v[3]),
        "avg_session_duration_s": float(v[4]),
        "engagement_rate": float(v[5]),
        "new_users": int(v[6]),
    }


def ga4_by_dim(ga4, dims, metrics, start="yesterday", end="today", limit=10):
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    req = RunReportRequest(
        property=GA4_PROPERTY,
        date_ranges=[DateRange(start_date=start, end_date=end)],
        dimensions=[Dimension(name=d) for d in dims],
        metrics=[Metric(name=m) for m in metrics],
        limit=limit,
    )
    resp = ga4.run_report(req)
    out = []
    for r in resp.rows:
        row = {f"dim_{i}": v.value for i, v in enumerate(r.dimension_values)}
        row.update({metrics[i]: v.value for i, v in enumerate(r.metric_values)})
        out.append(row)
    return out


def detect_bot_signals(headline, sources, geo):
    signals = []
    if headline is None:
        return signals
    if headline["active_users"] >= 30 and headline["avg_session_duration_s"] < 15:
        signals.append(
            f"avg session duration {headline['avg_session_duration_s']:.1f}s too short for {headline['active_users']} users"
        )
    if headline["active_users"] >= 30:
        ratio = headline["new_users"] / max(headline["active_users"], 1)
        if ratio >= 0.95:
            signals.append(f"{ratio*100:.0f}% new-user ratio (real sites have returning visitors)")
    if sources:
        total = sum(int(s.get("sessions", 0)) for s in sources)
        top = sources[0]
        if total >= 30 and top.get("dim_0", "").lower() in {"(direct)", "direct"}:
            share = int(top.get("sessions", 0)) / max(total, 1)
            if share >= 0.9:
                signals.append(f"{share*100:.0f}% of sessions are (direct)/(none) — missing organic/referral signature")
    if geo:
        total_u = sum(int(g.get("activeUsers", 0)) for g in geo)
        top = geo[0]
        if total_u >= 30:
            top_u = int(top.get("activeUsers", 0))
            share = top_u / max(total_u, 1)
            if share >= 0.95:
                c = top.get("dim_0", "?")
                d = top.get("dim_1", "?")
                signals.append(f"{share*100:.0f}% of users from {c}/{d} (no geographic diversity)")
    return signals


def inspect_url(gsc, url, site_url=GSC_SITE):
    try:
        resp = gsc.urlInspection().index().inspect(body={
            "inspectionUrl": url,
            "siteUrl": site_url,
        }).execute()
        ir = resp.get("inspectionResult", {})
        idx = ir.get("indexStatusResult", {})
        return {
            "url": url,
            "verdict": idx.get("verdict", "?"),
            "coverage": idx.get("coverageState", "?"),
            "indexing": idx.get("indexingState", "?"),
            "last_crawl": idx.get("lastCrawlTime"),
            "page_fetch": idx.get("pageFetchState"),
            "robots_state": idx.get("robotsTxtState"),
            "error": None,
        }
    except Exception as e:
        return {"url": url, "verdict": "ERROR", "error": str(e)[:180]}


def main():
    ap = argparse.ArgumentParser(description="Daily SEO snapshot for weba0.com")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--inspect", action="store_true", help="Also run URL Inspection API (slow)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--key", default=os.environ.get("ATLAST_WEBA0_KEY", str(DEFAULT_KEY)))
    args = ap.parse_args()

    if not Path(args.key).exists():
        print(f"Service account file not found: {args.key}", file=sys.stderr)
        sys.exit(1)

    from googleapiclient.discovery import build
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    creds = load_credentials(args.key)
    gsc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    ga4 = BetaAnalyticsDataClient.from_service_account_file(args.key)

    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).date().isoformat()

    daily = gsc_daily_metrics(gsc, args.days)
    queries = gsc_top_queries(gsc, yesterday)
    pages = gsc_top_pages(gsc, yesterday)
    headline = ga4_headline(ga4)
    sources = ga4_by_dim(ga4, ["sessionSource", "sessionMedium"],
                         ["sessions", "activeUsers", "engagementRate"])
    geo = ga4_by_dim(ga4, ["country", "deviceCategory"],
                     ["activeUsers", "sessions"])
    top_pages_ga4 = ga4_by_dim(ga4, ["pagePath"],
                               ["screenPageViews", "activeUsers", "averageSessionDuration"])
    bot_signals = detect_bot_signals(headline, sources, geo)

    inspections = None
    indexing_issues = 0
    if args.inspect:
        urls = fetch_sitemap_urls()
        inspections = [inspect_url(gsc, u) for u in urls]
        indexing_issues = sum(1 for i in inspections if i.get("verdict") != "PASS")

    if args.json:
        print(json.dumps({
            "now_utc": now.isoformat(),
            "gsc_daily": daily,
            "gsc_top_queries_yesterday": queries,
            "gsc_top_pages_yesterday": pages,
            "ga4_headline_24h": headline,
            "ga4_sources": sources,
            "ga4_geo_devices": geo,
            "ga4_top_pages": top_pages_ga4,
            "bot_signals": bot_signals,
            "url_inspections": inspections,
        }, indent=2))
        sys.exit(2 if (bot_signals or indexing_issues) else 0)

    o = Out(color=not args.no_color)
    print(f"SEO daily — weba0.com — {now.strftime('%Y-%m-%d %H:%M UTC')}")

    o.h(f"1. GSC daily (last {args.days}d — yesterday may lag 1–2 days)")
    if daily:
        for d in daily:
            print(f"  {d['date']}  clicks={d['clicks']:3d}  imp={d['impressions']:4d}  "
                  f"CTR={d['ctr']*100:5.2f}%  pos={d['position']:5.2f}")
        imps = [d["impressions"] for d in daily[-3:]]
        if len(imps) == 3 and imps[0] > 0 and imps[-1] < imps[0] * 0.3:
            o.w(f"Impressions trend: {imps[0]} → {imps[1]} → {imps[2]} (declining sharply)")
    else:
        o.w("GSC returned no rows")

    o.h(f"2. GSC top queries (yesterday {yesterday})")
    if queries:
        for q in queries[:10]:
            print(f"  {q['query'][:40]:<42} clicks={q['clicks']:2d}  imp={q['impressions']:3d}  pos={q['position']:.1f}")
    else:
        o.dim("(no queries yesterday — normal if zero impressions)")

    o.h(f"3. GSC top pages (yesterday {yesterday})")
    if pages:
        for p in pages:
            short = p["page"].replace("https://weba0.com", "")
            print(f"  {short[:50]:<52} clicks={p['clicks']:2d}  imp={p['impressions']:3d}")
    else:
        o.dim("(no page data yesterday)")

    o.h(f"4. GA4 past 24 hours")
    if headline:
        print(f"  active users:         {headline['active_users']}")
        print(f"  new users:            {headline['new_users']} "
              f"({headline['new_users']/max(headline['active_users'],1)*100:.0f}% of active)")
        print(f"  sessions:             {headline['sessions']}")
        print(f"  pageviews:            {headline['pageviews']}")
        print(f"  bounce rate:          {headline['bounce_rate']*100:.1f}%")
        print(f"  avg session duration: {headline['avg_session_duration_s']:.1f}s")
        print(f"  engagement rate:      {headline['engagement_rate']*100:.1f}%")

    o.h("5. GA4 traffic sources")
    for s in sources[:5]:
        src = f"{s.get('dim_0', '?')}/{s.get('dim_1', '?')}"
        print(f"  {src[:35]:<37} sessions={s.get('sessions')}  users={s.get('activeUsers')}  "
              f"engage={float(s.get('engagementRate', 0))*100:.0f}%")

    o.h("6. GA4 geo/device")
    for g in geo[:5]:
        print(f"  {g.get('dim_0', '?'):<25} {g.get('dim_1', '?'):<10} users={g.get('activeUsers')}  sessions={g.get('sessions')}")

    if top_pages_ga4:
        o.h("7. GA4 top pages (past 24h)")
        for p in top_pages_ga4[:8]:
            path = p.get("dim_0", "?")[:52]
            print(f"  {path:<54} pv={p.get('screenPageViews')}  users={p.get('activeUsers')}  dur={float(p.get('averageSessionDuration', 0)):.1f}s")

    o.h("8. Anomaly detection")
    if bot_signals:
        for s in bot_signals:
            o.bad(s)
        print()
        print(f"  {_color('→ likely bot traffic. Consider GA4 data filters, Cloudflare bot rules,', '31', o.color)}")
        print(f"  {_color('→ or pause paid ads. Real-user signal is buried in this noise.', '31', o.color)}")
    else:
        o.ok("no bot-signal patterns triggered")

    if inspections is not None:
        o.h("9. URL Inspection (coverage)")
        for i in inspections:
            url = i["url"].replace("https://weba0.com", "")
            if i.get("error"):
                o.bad(f"{url:<52}  ERROR {i['error']}")
                continue
            verdict = i.get("verdict", "?")
            coverage = i.get("coverage", "?")
            badge = "✅" if verdict == "PASS" else ("⚠" if "PARTIAL" in verdict else "❌")
            print(f"  {badge} {url:<52} {verdict:<8}  {coverage}")
            if i.get("last_crawl"):
                o.dim(f"  last crawl: {i['last_crawl'][:10]}")
        passing = sum(1 for i in inspections if i.get("verdict") == "PASS")
        total = len(inspections)
        if passing < total:
            o.w(f"{passing}/{total} URLs indexed cleanly — the other {total - passing} need investigation")

    issues = len(bot_signals) + indexing_issues
    if issues:
        print()
        o.w(f"Exiting with non-zero ({issues} anomaly signal(s))")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
