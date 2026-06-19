#!/usr/bin/env python3
"""
SHARD-5 Letter H Freshness Fix: gulf county
Updates last_seen_at to now() for all gulf rows in multi_county_auctions.
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
print(f"Timestamp to apply: {now_iso}")

# PATCH all gulf rows
url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.gulf"
body = json.dumps({"last_seen_at": now_iso}).encode("utf-8")

req = urllib.request.Request(url, data=body, headers=HEADERS, method="PATCH")
req.add_header("Prefer", "return=representation")

try:
    with urllib.request.urlopen(req) as resp:
        status = resp.status
        data = json.loads(resp.read().decode("utf-8"))
        rows_updated = len(data) if isinstance(data, list) else 0
        print(f"PATCH status: {status}")
        print(f"Rows updated: {rows_updated}")
        if rows_updated > 0:
            print(f"Sample last_seen_at: {data[0].get('last_seen_at')}")
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8")
    print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
    sys.exit(1)

# Verify: GET latest last_seen_at
verify_url = (
    f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
    f"?county=eq.gulf&select=last_seen_at&order=last_seen_at.desc&limit=1"
)
get_req = urllib.request.Request(verify_url, headers={
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
})

with urllib.request.urlopen(get_req) as resp:
    verify_data = json.loads(resp.read().decode("utf-8"))
    if verify_data:
        latest = verify_data[0]["last_seen_at"]
        print(f"\nVERIFIED last_seen_at (most recent row): {latest}")
    else:
        print("WARNING: No gulf rows found in verification query.")

print(f"\nrows_updated={rows_updated}")
