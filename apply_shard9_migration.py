#!/usr/bin/env python3
"""Apply shard-9 broward+alachua migration via Supabase Management API."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"

if not TOKEN:
    print("SUPABASE_ACCESS_TOKEN not set — cannot apply migration via Management API")
    print("The migration file is at: migrations/20260720_gold_standard_shard9_broward_alachua.sql")
    sys.exit(0)

sql_file = Path(__file__).parent / "migrations" / "20260720_gold_standard_shard9_broward_alachua.sql"
sql = sql_file.read_text()

print(f"Applying migration ({len(sql)} bytes) to project {REF}...")

H = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
body = json.dumps({"query": sql}).encode()

for attempt in range(3):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body, headers=H, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read() or b"[]")
            print(f"Management API ({r.status}): {json.dumps(result)[:500]}")
            print("Migration applied ✅")
            sys.exit(0)
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()[:400]
        print(f"Attempt {attempt+1}/3: HTTP {e.code}: {body_txt}")
        if e.code in (429, 503) and attempt < 2:
            time.sleep(30)
            continue
        break
    except Exception as e:
        print(f"Attempt {attempt+1}/3: {e}")
        if attempt < 2:
            time.sleep(30)
            continue
        break

print("Migration API call failed")
sys.exit(1)
