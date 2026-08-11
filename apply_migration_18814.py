#!/usr/bin/env python3
"""Apply the bay/nassau shard-2 migration via Supabase Management API.
Uses only stdlib (no httpx dependency).

Usage:
    SUPABASE_ACCESS_TOKEN=<token> python3 apply_migration_18814.py
"""
import json
import os
import sys
import urllib.request
import urllib.error

TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"

if not TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN not set", file=sys.stderr)
    sys.exit(2)

SQL_FILE = "migrations/20260811_gold_standard_shard2_18814_bay_nassau_ei_cd_fix.sql"
try:
    with open(SQL_FILE) as f:
        sql = f.read()
except FileNotFoundError:
    print(f"ERROR: {SQL_FILE} not found", file=sys.stderr)
    sys.exit(1)

print(f"Applying {len(sql)} bytes to Supabase project {REF}...", flush=True)

h = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}
body = json.dumps({"query": sql}).encode()

req = urllib.request.Request(
    f"https://api.supabase.com/v1/projects/{REF}/database/query",
    data=body, headers=h, method="POST")

try:
    with urllib.request.urlopen(req, timeout=120) as r:
        print(f"STATUS {r.status}")
        resp_body = json.loads(r.read())
        print(json.dumps(resp_body, indent=2, default=str)[:8000])
except urllib.error.HTTPError as e:
    print(f"STATUS {e.code}")
    print(e.read().decode()[:2000])
    sys.exit(1)

print("\nNow verifying via pencil_dod_evaluate_county...", flush=True)
for county in ("bay", "nassau"):
    verify_sql = f"SELECT public.pencil_dod_evaluate_county('{county}') AS result"
    vbody = json.dumps({"query": verify_sql}).encode()
    vreq = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=vbody, headers=h, method="POST")
    try:
        with urllib.request.urlopen(vreq, timeout=60) as vr:
            vresp = json.loads(vr.read())
            print(f"\n### SQL VERIFICATION — {county}")
            print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
            print(json.dumps(vresp, indent=2, default=str)[:4000])
    except Exception as exc:
        print(f"Verification error for {county}: {exc}")
