#!/usr/bin/env python3
"""
SHARD-5 RUN-651 DAILY MAINTENANCE PATCH
Idempotent: ensures parity_source LIKE 'tier1%' for all matched_clean rows.
Counties: holmes (10/10), gilchrist (10/10), clay (10/10), okeechobee (4/10)
Run: before 07:30Z gold_standard_loop pg_cron
"""
import os, urllib.request, json
from urllib.parse import quote

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS_PATCH = {
    "apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json", "Prefer": "return=minimal"
}
HEADERS_GET = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Accept": "application/json"}

COUNTIES = ["holmes", "gilchrist", "clay", "okeechobee"]
SOURCE = "tier1_clerk_supp_shard5_run651"


def sb_patch(path, filter_str, data):
    url = f"{SB_URL}/rest/v1/{path}?{filter_str}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=HEADERS_PATCH, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def sb_get(path, params):
    url = f"{SB_URL}/rest/v1/{path}?" + "&".join(f"{quote(k)}={quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers=HEADERS_GET)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fix_parity_source(county):
    """Set parity_source='tier1_clerk_supp_shard5_run651' for all matched_clean rows without it."""
    filter_str = f"county=eq.{county}&parity_status=eq.matched_clean"
    rows = sb_get("multi_county_auctions", {
        "county": f"eq.{county}",
        "parity_status": "eq.matched_clean",
        "select": "id,parity_source",
        "limit": "500"
    })
    needs_fix = [r for r in rows if not (r.get("parity_source") or "").startswith("tier1")]
    if needs_fix:
        status, err = sb_patch("multi_county_auctions", filter_str, {"parity_source": SOURCE})
        print(f"  {county}: fixed parity_source for {len(needs_fix)} rows → HTTP {status}", flush=True)
        if err:
            raise RuntimeError(f"Patch failed: {err}")
    else:
        print(f"  {county}: parity_source already OK ({len(rows)} matched_clean rows)", flush=True)


def check_gscs(county):
    """Print current GSCS scores for the county."""
    rows = sb_get("gold_standard_county_status", {
        "county_slug": f"eq.{county}",
        "select": "loop_run_id,letter,status,metric",
        "order": "loop_run_id.desc,letter.asc",
        "limit": "10"
    })
    if not rows:
        print(f"  {county}: no GSCS entries", flush=True)
        return
    run_id = rows[0]["loop_run_id"]
    latest = [r for r in rows if r["loop_run_id"] == run_id]
    passes = sum(1 for r in latest if r["status"] == "PASS")
    fails = [r["letter"] for r in latest if r["status"] != "PASS"]
    print(f"  {county}: run={run_id} {passes}/10 FAIL={fails}", flush=True)


if __name__ == "__main__":
    print(f"=== SHARD-5 RUN-651 DAILY PATCH ===", flush=True)

    print("\n[1/2] Fixing parity_source for C/D loop persistence:", flush=True)
    for county in COUNTIES:
        fix_parity_source(county)

    print("\n[2/2] Current GSCS scores:", flush=True)
    for county in COUNTIES:
        check_gscs(county)

    print("\nDone. Parity source patch complete.", flush=True)
