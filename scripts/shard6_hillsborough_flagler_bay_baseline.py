#!/usr/bin/env python3
"""
SHARD-6 Baseline Metrics — hillsborough, flagler, bay
Get live pencil_dod_evaluate_county for all three counties.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SB = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SB}/rest/v1"
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def evaluate_county(county: str) -> dict:
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(
        f"{BASE}/rpc/pencil_dod_evaluate_county",
        data=body,
        headers={**HEADERS, "Prefer": ""},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:300]}")
        return {}


def print_eval(county: str, result: dict):
    print(f"\n{'='*60}")
    print(f"COUNTY: {county.upper()}")
    print(f"{'='*60}")
    if not result:
        print("  ERROR: No result returned")
        return
    passes = 0
    for letter in "ABCDEFGHIJ":
        d = result.get(letter, {})
        p = d.get("pass", False)
        metric = d.get("metric", "?")
        detail = d.get("detail", "")
        mark = "PASS" if p else "FAIL"
        passes += 1 if p else 0
        print(f"  {letter} {mark} metric={metric} {detail}")
    total = result.get("auctions_total", "?")
    print(f"  SCORE: {passes}/10  (auctions_total={total})")
    return passes


if __name__ == "__main__":
    print(f"SHARD-6 Baseline — {ts()}")
    counties = ["hillsborough", "flagler", "bay"]
    results = {}
    for county in counties:
        print(f"\nQuerying {county}...")
        r = evaluate_county(county)
        results[county] = r
        print_eval(county, r)

    print(f"\n\nRAW JSON (for paste into session summary):")
    for county in counties:
        print(f"\n{county}:")
        print(json.dumps(results[county]))
