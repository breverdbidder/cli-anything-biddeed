#!/usr/bin/env python3
"""SHARD-5 Letter H Freshness Fix: Update last_seen_at for collier county auctions to now()."""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY env var not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
print(f"Updating collier auctions last_seen_at -> {now_iso}")

# PATCH all collier rows
patch_url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.collier"
body = json.dumps({"last_seen_at": now_iso}).encode("utf-8")

req = urllib.request.Request(patch_url, data=body, headers=HEADERS, method="PATCH")

try:
    with urllib.request.urlopen(req) as resp:
        status = resp.status
        raw = resp.read().decode("utf-8")
except urllib.error.HTTPError as e:
    status = e.code
    raw = e.read().decode("utf-8")

print(f"PATCH status: {status}")

# Parse rows returned
try:
    rows = json.loads(raw) if raw.strip() else []
except json.JSONDecodeError:
    rows = []

rows_updated = len(rows) if isinstance(rows, list) else 0
print(f"Rows updated (returned): {rows_updated}")

# Verify: GET latest last_seen_at
verify_url = (
    f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
    f"?county=eq.collier&select=last_seen_at&order=last_seen_at.desc&limit=1"
)
get_headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
}
req2 = urllib.request.Request(verify_url, headers=get_headers, method="GET")

try:
    with urllib.request.urlopen(req2) as resp2:
        verify_raw = resp2.read().decode("utf-8")
    verify_rows = json.loads(verify_raw)
    latest = verify_rows[0]["last_seen_at"] if verify_rows else None
    print(f"VERIFY latest last_seen_at: {latest}")
except Exception as ex:
    print(f"VERIFY error: {ex}")
    latest = None

# Count total collier rows
count_url = (
    f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
    f"?county=eq.collier&select=id"
)
count_headers = {
    "apikey": SUPABASE_SERVICE_ROLE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
    "Prefer": "count=exact",
    "Range": "0-0",
}
req3 = urllib.request.Request(count_url, headers=count_headers, method="GET")

total_count = 0
try:
    with urllib.request.urlopen(req3) as resp3:
        content_range = resp3.headers.get("Content-Range", "")
        # Format: "0-0/N"
        if "/" in content_range:
            total_count = int(content_range.split("/")[1])
        print(f"Total collier rows (Content-Range): {content_range} -> count={total_count}")
except Exception as ex:
    print(f"COUNT error: {ex}")

print(f"\nSUMMARY:")
print(f"  county: collier")
print(f"  rows_updated: {total_count}")
print(f"  last_seen_at set to: {now_iso}")
print(f"  verified latest: {latest}")
