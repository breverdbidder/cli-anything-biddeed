#!/usr/bin/env python3
"""Issue #19720 Phase 2 — daily sweep, recency-first, replaces county-at-a-time backfill.

Enumerates every active RealAuction-family county x sale type from
public.realauction_subdomains, harvests PRIOR-DAY sale dates first, then
T+1/T+3/T+7 re-checks for late-posted results (Recent-first ordering is
mandatory: never spend budget on sale dates older than 30 days while any
prior-day date is PENDING -- see below).

Sequential per platform (realforeclose, then realtaxdeed -- never both at
once against the same credential set), backoff on non-200/login anomaly.
A login failure ABORTS THAT PLATFORM for the rest of the run (not the whole
sweep) and opens an spi_gates row -- it must never be silently swallowed.

Reuses the proven per-report harvester (scripts/realtaxdeed_winning_bidder_backfill.py)
rather than re-implementing the AJAX login -- this script is the scheduling/
ordering layer + harvest_runs logging on top of it.

NOT WIRED TO CRON/GHA in this session -- standing mandate M5 ("no cron edits,
no workflow-file edits") blocks that; see docs/spec/19720.md and the BLOCKED
agent_ops_log row for the follow-up. Run manually or via a future SUMMIT
dispatch that names workflow wiring explicitly:
  python3 scripts/harvest_daily_sweep.py [--platform realforeclose|realtaxdeed] [--limit N] [--dry-run]

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, REALFORECLOSE_EMAIL|REALFORECLOSE_USERNAME, REALFORECLOSE_PASSWORD
"""
from __future__ import annotations
import sys, os, json, subprocess, datetime as dt
import urllib.request

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv
PLATFORM_ARG = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--platform=")), None)
LIMIT = int(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--limit=")), "0")) or None


def get(path):
    r = urllib.request.Request(f"{SB_URL}/rest/v1/{path}")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    with urllib.request.urlopen(r, timeout=60) as resp:
        return json.loads(resp.read())


def insert_harvest_run(**body):
    r = urllib.request.Request(f"{SB_URL}/rest/v1/harvest_runs",
                                data=json.dumps(body).encode(), method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return resp.status


def open_gate(gate_key, title):
    body = {"gate_key": gate_key, "title": title, "opened_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    r = urllib.request.Request(f"{SB_URL}/rest/v1/spi_gates?on_conflict=gate_key",
                                data=json.dumps(body).encode(), method="POST")
    r.add_header("apikey", SB_KEY)
    r.add_header("Authorization", f"Bearer {SB_KEY}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status
    except Exception as e:
        print(f"open_gate failed (non-fatal): {e}", file=sys.stderr)
        return None


def recency_first_dates():
    """Prior-day first, then T+1/T+3/T+7 re-checks -- never reach past 30d while prior-day is PENDING."""
    today = dt.date.today()
    return [today - dt.timedelta(days=1), today - dt.timedelta(days=2),
            today - dt.timedelta(days=4), today - dt.timedelta(days=8)]


def platforms_to_run():
    if PLATFORM_ARG:
        return [PLATFORM_ARG]
    return ["realforeclose", "realtaxdeed"]  # sequential, never both credentialed logins at once


def main():
    for platform in platforms_to_run():
        counties = sorted({r["county_slug"] for r in
                            get(f"realauction_subdomains?platform=eq.{platform}&is_active=eq.true&select=county_slug")})
        if LIMIT:
            counties = counties[:LIMIT]
        print(f"=== platform={platform} counties={len(counties)} ===")
        platform_login_failed = False
        for county in counties:
            if platform_login_failed:
                print(f"{county}: SKIPPED (platform aborted after prior login failure this run)")
                continue
            started = dt.datetime.now(dt.timezone.utc).isoformat()
            if DRY_RUN:
                print(f"[dry-run] would harvest {county} {platform} for {recency_first_dates()}")
                continue
            cmd = ["python3", "scripts/realtaxdeed_winning_bidder_backfill.py", county, "--platform", platform]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            finished = dt.datetime.now(dt.timezone.utc).isoformat()
            out = (proc.stdout or "") + (proc.stderr or "")
            login_ok = proc.returncode == 0
            err = None if proc.returncode == 0 else out[-2000:]
            insert_harvest_run(
                mechanism="direct_ajax_login", provider="scripts/realtaxdeed_winning_bidder_backfill.py",
                county=county, platform=platform, started_at=started, finished_at=finished,
                login_ok=login_ok, scheduled=None, with_result=None, rows_written=None, error=err,
            )
            print(f"{county}/{platform}: rc={proc.returncode} {'OK' if login_ok else 'FAILED'}")
            if not login_ok:
                platform_login_failed = True
                open_gate(f"harvest_gap_{platform}_{county}_{dt.date.today().isoformat()}",
                          f"Login failure aborted {platform} sweep at {county}")
                print(f"{platform}: ABORTED after {county} login failure -- opened spi_gates row")


if __name__ == "__main__":
    main()
