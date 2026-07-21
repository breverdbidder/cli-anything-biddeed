#!/usr/bin/env python3
"""
SHARD-8 (dispatch c04799e6) — Apply migration + verify collier + holmes.
Run in GHA environment with SUPABASE_ACCESS_TOKEN and SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY.

Steps:
  1. Apply supabase/migrations/20260721_gold_standard_shard8_collier_holmes_session_c04799e6.sql
     via Supabase Management API.
  2. Run pencil_dod_evaluate_county() for collier and holmes.
  3. Print before/after JSON for session report.
"""
import json
import os
import sys
import urllib.error
import urllib.request

REF   = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SURL  = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SKEY  = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

MIGRATION_FILE = "supabase/migrations/20260721_gold_standard_shard8_collier_holmes_session_c04799e6.sql"


def mgmt_query(sql):
    body = json.dumps({"query": sql}).encode()
    req  = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"[]")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"[]")


def rest_rpc(fn, params=None):
    body = json.dumps(params or {}).encode()
    req  = urllib.request.Request(
        f"{SURL}/rest/v1/rpc/{fn}",
        data=body,
        headers={
            "apikey": SKEY,
            "Authorization": f"Bearer {SKEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


print("=" * 60, flush=True)
print("SHARD-8 dispatch c04799e6 — Apply + Verify", flush=True)
print("=" * 60, flush=True)

if not TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN not set", file=sys.stderr)
    sys.exit(2)

if not SKEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(2)

# ── STEP 0: BEFORE state ────────────────────────────────────────────────────
print("\n=== BEFORE: pencil_dod_evaluate_county('collier') ===", flush=True)
code, before_collier = rest_rpc("pencil_dod_evaluate_county", {"p_county": "collier"})
print(f"HTTP {code}: {json.dumps(before_collier, indent=2)}", flush=True)

print("\n=== BEFORE: pencil_dod_evaluate_county('holmes') ===", flush=True)
code, before_holmes = rest_rpc("pencil_dod_evaluate_county", {"p_county": "holmes"})
print(f"HTTP {code}: {json.dumps(before_holmes, indent=2)}", flush=True)

# ── STEP 1: Apply migration ──────────────────────────────────────────────────
print(f"\n=== Applying {MIGRATION_FILE} ===", flush=True)
try:
    with open(MIGRATION_FILE) as f:
        sql = f.read()
    print(f"Migration size: {len(sql)} bytes", flush=True)
except FileNotFoundError:
    print(f"ERROR: {MIGRATION_FILE} not found", file=sys.stderr)
    sys.exit(1)

code, result = mgmt_query(sql)
print(f"Management API HTTP {code}: {json.dumps(result)[:800]}", flush=True)
if code not in (200, 201):
    print("ERROR: migration failed — aborting", file=sys.stderr)
    sys.exit(1)
print("Migration applied ✅", flush=True)

# ── STEP 2: AFTER state ──────────────────────────────────────────────────────
print("\n=== AFTER: pencil_dod_evaluate_county('collier') ===", flush=True)
code, after_collier = rest_rpc("pencil_dod_evaluate_county", {"p_county": "collier"})
print(f"HTTP {code}: {json.dumps(after_collier, indent=2)}", flush=True)

print("\n=== AFTER: pencil_dod_evaluate_county('holmes') ===", flush=True)
code, after_holmes = rest_rpc("pencil_dod_evaluate_county", {"p_county": "holmes"})
print(f"HTTP {code}: {json.dumps(after_holmes, indent=2)}", flush=True)

# ── STEP 3: Ultraloop audit count ────────────────────────────────────────────
print("\n=== Ultraloop audit rows for this dispatch ===", flush=True)
code, rows = mgmt_query(
    "SELECT county_slug, letter, survived, created_at "
    "FROM gold_standard_ultraloop_audit "
    "WHERE dispatch_id = 'c04799e6-1443-4234-ae22-ef14044499e6' "
    "ORDER BY county_slug, letter, created_at;"
)
print(f"HTTP {code}: {len(rows or [])} row(s)", flush=True)
for r in (rows or []):
    print(f"  {r.get('county_slug')}/{r.get('letter')}: survived={r.get('survived')} "
          f"at={r.get('created_at','')[:19]}", flush=True)

# ── STEP 4: H freshness check ────────────────────────────────────────────────
print("\n=== H freshness (last_seen_at) ===", flush=True)
code, freshness = mgmt_query(
    "SELECT county, COUNT(*) AS rows, "
    "MAX(last_seen_at) AS newest_seen, "
    "MIN(last_seen_at) AS oldest_seen "
    "FROM multi_county_auctions "
    "WHERE county IN ('collier','holmes') "
    "GROUP BY county ORDER BY county;"
)
print(f"HTTP {code}: {json.dumps(freshness, indent=2)}", flush=True)

print("\n=== DONE ===", flush=True)
