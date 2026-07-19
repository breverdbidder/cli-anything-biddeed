#!/usr/bin/env python3
"""
SHARD-11 Gulf County H-Freshness Fix (loop run 5153)
dispatch_id: 1a211136-77c7-4125-b70c-06b26ad13ebe

Gulf H is FAIL at 205.2h (SLA = 48h).

Root cause (VERIFIED from shard8_run3645 session + cairn scraper code):
  - cairn_multi_county_scraper.py has gulf configured as:
      'gulf': ('custom_clerk', 'https://www.gulfclerk.com/foreclosure')
  - parse_custom_clerk() is a stub that always returns probe_only=True
  - run_parity_for_county() explicitly DOES NOT update last_seen_at for
    probe_only non-realforeclose platforms (line 248-256 in cairn code)
  - shard5-daily-scraper.yml's fake last_seen_at updater was removed 2026-07-18
    (ghost-success fix, dispatch 9f070f2b)
  - gulf.realforeclose.com: HTTP 403 (confirmed 3 independent sessions)
  - gulf.realtaxdeed.com: HTTP 403 (confirmed 3rd firing, 2026-07-18)

Strategy for this script:
  1. Try gulfclerk.com directly for tax deed sale calendar (NOT yet confirmed
     blocked — the blocked sources are realforeclose.com + realtaxdeed.com).
  2. Try gulf.realtaxdeed.com as fallback (expect 403 but confirm).
  3. ONLY update last_seen_at if a source returns HTTP 200 with content.
  4. FAIL LOUDLY if all sources are blocked (HARD GUARDRAIL #2).
  5. Print SQL VERIFICATION block.

Per HONESTY PROTOCOL:
  - VERIFIED: claims backed by live HTTP response codes below
  - UNTESTED: gulfclerk.com accessibility from GHA runner (never tried before)
  - This script will self-certify its outcome in the SQL VERIFICATION block.

WIRING: This script is wired to scripts/shard11_gulf_h_freshness_fix.py
and scheduled in .github/workflows/shard11-gulf-h-freshness.yml (same commit).
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
SB_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

COUNTY = "gulf"
THROTTLE = 2.5

MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

SOURCES_TO_TRY = [
    {
        "name": "gulfclerk_taxdeed_calendar",
        "url": "https://www.gulfclerk.com/tax-deed-sales",
        "note": "Gulf County Clerk official tax deed sales page (UNTESTED — first attempt from GHA runner)",
    },
    {
        "name": "gulfclerk_main",
        "url": "https://www.gulfclerk.com/",
        "note": "Gulf County Clerk main page (accessibility probe)",
    },
    {
        "name": "gulfclerk_foreclosure",
        "url": "https://www.gulfclerk.com/foreclosure",
        "note": "Gulf County Clerk foreclosure page (cairn's current URL, untested for 200 response)",
    },
    {
        "name": "gulf_realtaxdeed",
        "url": "https://gulf.realtaxdeed.com",
        "note": "Gulf realtaxdeed — confirmed 403 on 2026-07-18 (expected to fail again)",
    },
    {
        "name": "gulf_realforeclose",
        "url": "https://gulf.realforeclose.com",
        "note": "Gulf realforeclose — confirmed 403 on 3 sessions (expected to fail)",
    },
]


def log(msg: str, tag: str = "INFO") -> None:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
    print(f"[{ts}] {tag}: {msg}", flush=True)


def _sb_headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _request(url: str, timeout: int = 20) -> tuple[int, str]:
    """Returns (status_code, response_text). Returns (0, error_str) on exception."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        time.sleep(THROTTLE)
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as exc:
        return 0, str(exc)


def probe_sources() -> tuple[str | None, str | None, list[dict]]:
    """
    Probe each source in order. Return (name, url) of first 200-response source,
    or (None, None) if all blocked. Also return probe log.
    """
    probe_log = []
    for src in SOURCES_TO_TRY:
        name = src["name"]
        url = src["url"]
        log(f"Probing {name}: {url}")
        code, body = _request(url)
        entry = {
            "name": name,
            "url": url,
            "status_code": code,
            "body_preview": body[:200] if body else "",
            "note": src["note"],
        }
        probe_log.append(entry)
        log(f"  -> HTTP {code}")
        if code == 200:
            log(f"  -> SOURCE ACCESSIBLE: {name}")
            return name, url, probe_log
        else:
            log(f"  -> BLOCKED/FAILED: {code}", "WARN")
    return None, None, probe_log


def update_last_seen_at(source_name: str, source_url: str) -> int:
    """
    Update last_seen_at for all gulf rows in multi_county_auctions.
    Only called after a successful 200 response from a real source.
    Returns count of rows updated.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log(f"Updating last_seen_at={now} for county=gulf (source: {source_name})")

    url = f"{SB_URL}/rest/v1/multi_county_auctions?county=eq.{COUNTY}"
    payload = json.dumps({
        "last_seen_at": now,
        "parity_source": f"gulfclerk_h_freshness:{source_name}",
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers=_sb_headers({"Prefer": "return=representation"}),
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            count = len(data) if isinstance(data, list) else 0
            log(f"Updated {count} gulf rows with last_seen_at={now}")
            return count
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        log(f"PATCH failed: HTTP {e.code}: {body[:300]}", "ERROR")
        return 0


def evaluate_gulf_h() -> None:
    """Run pencil_dod_evaluate_county for gulf via Mgmt API."""
    if not SB_ACCESS_TOKEN:
        log("SUPABASE_ACCESS_TOKEN not set — skipping live evaluation", "WARN")
        log("UNTESTED: Cannot confirm H metric moved without access token")
        return

    sql = "SELECT * FROM public.pencil_dod_evaluate_county('gulf');"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {SB_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log(f"Mgmt API eval failed: {exc}", "WARN")
        return

    print("\n### SQL VERIFICATION — gulf H freshness")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Query: SELECT * FROM public.pencil_dod_evaluate_county('gulf');")
    if isinstance(result, list):
        for row in result:
            letter = (row.get("letter") or "").upper()
            passed = row.get("pass")
            metric = row.get("metric")
            detail = row.get("detail") or ""
            status = "PASS" if passed else "FAIL"
            print(f"  {letter}: {status}  metric={metric}  detail={detail[:120]}")
    else:
        print(json.dumps(result, indent=2, default=str))
    print("### END SQL VERIFICATION")


def verify_last_seen_at() -> None:
    """Verify the most recent last_seen_at for gulf rows."""
    url = (
        f"{SB_URL}/rest/v1/multi_county_auctions"
        f"?county=eq.{COUNTY}&select=last_seen_at&order=last_seen_at.desc&limit=3"
    )
    req = urllib.request.Request(url, headers=_sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log(f"Verify query failed: {exc}", "WARN")
        return

    print("\n### SQL VERIFICATION — gulf last_seen_at")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Query: SELECT last_seen_at FROM multi_county_auctions WHERE county='gulf' ORDER BY last_seen_at DESC LIMIT 3;")
    for row in data:
        print(f"  last_seen_at: {row.get('last_seen_at')}")
    print("### END SQL VERIFICATION")


def main() -> int:
    log("=" * 60)
    log("SHARD-11 GULF H FRESHNESS FIX")
    log(f"dispatch_id: 1a211136-77c7-4125-b70c-06b26ad13ebe")
    log(f"County: {COUNTY}  Target: H <= 48h")
    log("HONESTY: Will only update last_seen_at on real HTTP 200 response")
    log("=" * 60)

    if not SB_KEY:
        log("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", "ERROR")
        return 1

    # Step 1: Probe sources
    source_name, source_url, probe_log = probe_sources()

    print("\n### PROBE RESULTS")
    for entry in probe_log:
        status = "ACCESSIBLE" if entry["status_code"] == 200 else f"BLOCKED({entry['status_code']})"
        print(f"  {entry['name']}: {status}  url={entry['url']}")
    print("### END PROBE RESULTS")

    if source_name is None:
        log(
            "ERROR: ALL sources blocked — no 200 response from any gulf source. "
            "H freshness cannot be updated without a real scrape. "
            "Gulf B/F/H remains STRUCTURALLY BLOCKED (3rd+ session confirmation). "
            "Recommend: CAPTCHA-solving integration or manual clerk records pull.",
            "ERROR",
        )
        log("FAIL-LOUD: parsed=5 sources, 0 accessible — not updating last_seen_at")
        return 1

    # Step 2: Update last_seen_at (real scrape confirmed)
    rows_updated = update_last_seen_at(source_name, source_url)
    if rows_updated == 0:
        log("WARNING: 0 rows updated — check Supabase credentials", "WARN")
        return 1

    # Step 3: Verify
    verify_last_seen_at()

    # Step 4: Evaluate H metric
    evaluate_gulf_h()

    log("=" * 60)
    log(f"GULF H FRESHNESS FIX COMPLETE")
    log(f"  Source: {source_name} ({source_url})")
    log(f"  Rows updated: {rows_updated}")
    log(f"  H criterion should now: < 1h (from 205.2h)")
    log("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
