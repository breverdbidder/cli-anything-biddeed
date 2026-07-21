#!/usr/bin/env python3
"""Apply shard-2 run5668 migration: hardee/dixie/madison/gulf freshness refresh."""
import os, sys, json
import urllib.request, urllib.error

REF   = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

if not TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN not set", file=sys.stderr)
    sys.exit(2)

SQL_FILE = os.path.join(
    os.path.dirname(__file__), "..",
    "supabase", "migrations",
    "20260721_gold_standard_shard2_hardee_dixie_madison_gulf_freshness_refresh.sql"
)

with open(SQL_FILE) as f:
    sql = f.read()

print(f"Sending {len(sql)} bytes to Management API for project {REF}...", flush=True)

H    = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
body = json.dumps({"query": sql}).encode()

for attempt in range(3):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body, headers=H, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw    = r.read()
            status = r.status
            result = json.loads(raw or b"[]")
            print(f"Management API SQL ({status}): {json.dumps(result, indent=2, default=str)[:4000]}")
            sys.exit(0)
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()
        print(f"Attempt {attempt+1}: HTTP {e.code}: {body_txt[:500]}", file=sys.stderr)
        if attempt == 2:
            sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Attempt {attempt+1}: URLError: {e}", file=sys.stderr)
        if attempt == 2:
            sys.exit(1)
