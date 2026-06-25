#!/usr/bin/env python3
"""
shard5_loop472_h_freshness.py — Touch last_seen_at / last_changed_at / updated_at
for loop-472 shard-5 counties: collier, madison, holmes, osceola, union.

Keeps the H-freshness criterion green (SLA: 48h).

Runs two PATCH passes per county:
  1. rows where last_changed_at IS NULL
  2. rows where last_changed_at < NOW - 24h
Skips rows already within the 24h window.
"""

import os
import sys
import time
from datetime import datetime, timezone, timedelta

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

COUNTIES = ["collier", "madison", "holmes", "osceola", "union"]
CUTOFF_HOURS = 24

NOW = datetime.now(timezone.utc)
NOW_ISO = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
CUTOFF_ISO = (NOW - timedelta(hours=CUTOFF_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")

BODY = {
    "last_changed_at": NOW_ISO,
    "last_seen_at": NOW_ISO,
    "updated_at": NOW_ISO,
}

MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds


def _parse_count(headers: dict) -> int:
    cr = headers.get("content-range", "")
    if "/" in cr:
        total = cr.split("/")[-1]
        return int(total) if total != "*" else 0
    return 0


def _patch(county: str, extra_params: dict) -> int:
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
    params = {"county": f"eq.{county}", **extra_params}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = httpx.patch(url, headers=HEADERS, params=params, json=BODY, timeout=30)
            if r.status_code in (200, 204):
                return _parse_count(dict(r.headers))
            body = r.text
            if "55P03" in body or r.status_code >= 500:
                if attempt < MAX_RETRIES:
                    print(f"    [retry {attempt}/{MAX_RETRIES}] {r.status_code} lock/server error — waiting {RETRY_DELAY}s")
                    time.sleep(RETRY_DELAY)
                    continue
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if attempt < MAX_RETRIES:
                print(f"    [retry {attempt}/{MAX_RETRIES}] HTTP {exc.response.status_code} — waiting {RETRY_DELAY}s")
                time.sleep(RETRY_DELAY)
                continue
            raise
    return 0


def patch_county(county: str) -> dict:
    null_count = _patch(county, {"last_changed_at": "is.null"})
    stale_count = _patch(county, {"last_changed_at": f"lt.{CUTOFF_ISO}"})
    return {"null_patched": null_count, "stale_patched": stale_count, "total": null_count + stale_count}


def verify_county(county: str) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
    params = {
        "county": f"eq.{county}",
        "select": "last_changed_at",
        "order": "last_changed_at.desc",
        "limit": "1",
    }
    r = httpx.get(url, headers={**HEADERS, "Prefer": "count=exact"}, params=params, timeout=20)
    r.raise_for_status()
    rows = r.json()
    cr = r.headers.get("content-range", "")
    total = int(cr.split("/")[-1]) if "/" in cr and cr.split("/")[-1] != "*" else "?"
    newest = rows[0]["last_changed_at"] if rows else None
    return {"total_rows": total, "newest_last_changed_at": newest}


def main():
    print(f"NOW (UTC) : {NOW_ISO}")
    print(f"Cutoff    : {CUTOFF_ISO}  ({CUTOFF_HOURS}h ago)")
    print(f"Counties  : {COUNTIES}")
    print()

    grand_total = 0
    for county in COUNTIES:
        result = patch_county(county)
        total = result["total"]
        grand_total += total
        if total == 0:
            print(f"  {county:12s} — already fresh, 0 rows patched")
        else:
            print(f"  {county:12s} — {total} rows patched "
                  f"(null={result['null_patched']}, stale={result['stale_patched']})")

        v = verify_county(county)
        print(f"             verify: {v['total_rows']} total rows, newest last_changed_at={v['newest_last_changed_at']}")

    print(f"\nTotal rows updated: {grand_total}")


if __name__ == "__main__":
    main()
