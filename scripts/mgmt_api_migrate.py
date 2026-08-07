#!/usr/bin/env python3
"""
Supabase Management API SQL executor — fallback when psql credentials absent.
Uses POST https://api.supabase.com/v1/projects/{ref}/database/query
which goes to api.supabase.com (NOT the 522-affected project REST endpoint).

Env:
  SUPABASE_ACCESS_TOKEN (required) — sbp_ token from Supabase dashboard
  MIGRATION_FILE        (optional) — path to SQL file (default: hardcoded migration)
  GITHUB_ENV            (optional) — path to GHA env file for MIGRATION_APPLIED flag
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF   = "mocerqjnksmhcjzxrewo"

if not TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN not set", file=sys.stderr)
    sys.exit(2)

SQL_FILE = os.environ.get(
    "MIGRATION_FILE",
    "supabase/migrations/20260623_6county_gold_b_f_outcome_pipeline.sql",
)

try:
    with open(SQL_FILE) as f:
        sql = f.read()
except FileNotFoundError:
    print(f"ERROR: {SQL_FILE} not found", file=sys.stderr)
    sys.exit(1)

print(f"Sending {len(sql)} bytes to Management API for project {REF}...", flush=True)

H    = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    # Cloudflare returns 403 (error 1010) on the default Python-urllib UA.
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
}
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
            print(f"Management API SQL ({status}): {json.dumps(result)[:800]}", flush=True)
            # Write MIGRATION_APPLIED flag to GHA env file if present
            gha_env = os.environ.get("GITHUB_ENV", "")
            if gha_env:
                with open(gha_env, "a") as ef:
                    ef.write("MIGRATION_APPLIED=true\n")
            print("Migration applied via Management API ✅")
            sys.exit(0)
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()[:600]
        print(f"Attempt {attempt + 1}/3: HTTP {e.code}: {body_txt}", flush=True)
        if e.code in (429, 503, 502) and attempt < 2:
            delay = 30 * (attempt + 1)
            print(f"Retrying in {delay}s...", flush=True)
            time.sleep(delay)
            continue
        break
    except Exception as exc:
        print(f"Attempt {attempt + 1}/3: {exc}", flush=True)
        if attempt < 2:
            time.sleep(30)
            continue
        break

print("Management API SQL execution failed — migration skipped", flush=True)
gha_env = os.environ.get("GITHUB_ENV", "")
if gha_env:
    with open(gha_env, "a") as ef:
        ef.write("MIGRATION_SKIPPED=true\n")
sys.exit(1)
