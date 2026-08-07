#!/usr/bin/env python3
"""Apply SHARD-5 5d40a513 migration via Supabase Management API.
Run: python3 run_migration_5d40a513.py
Requires: SUPABASE_ACCESS_TOKEN env var
"""
import os, json, urllib.request, urllib.error, sys

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not TOKEN and not SB_KEY:
    print("ERROR: need SUPABASE_ACCESS_TOKEN or SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

COUNTIES = ["pinellas", "osceola", "suwannee", "baker"]

def rest_rpc(endpoint, payload, headers):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as ex:
        return -1, str(ex)

def mgmt_sql(query):
    if not TOKEN:
        return None, "no SUPABASE_ACCESS_TOKEN"
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers=h, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]
    except Exception as ex:
        return -1, str(ex)

def rest_evaluate(county):
    if not SB_KEY:
        return None
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    status, result = rest_rpc(f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county", {"p_county": county}, h)
    if status in (200, 201):
        return result
    return {"error": f"HTTP {status}", "body": result}

print("=== SHARD-5 5d40a513 Migration Executor ===")
print(f"Supabase project: {REF}")
print()

# Read and execute migration SQL
migration_file = "migrations/20260807_gold_standard_shard5_5d40a513_pinellas_osceola_suwannee_baker.sql"
try:
    sql = open(migration_file).read()
    print(f"Migration file: {migration_file} ({len(sql)} bytes)")
except FileNotFoundError:
    print(f"ERROR: {migration_file} not found")
    sys.exit(1)

if TOKEN:
    print("\n--- Applying migration via Management API ---")
    status, result = mgmt_sql(sql)
    print(f"  Status: {status}")
    if status in (200, 201):
        print(f"  Result: {json.dumps(result, default=str)[:1000]}")
        print("  Migration applied OK")
    else:
        print(f"  Error: {result}")
        print("  Will continue to verify current state...")
else:
    print("  (SUPABASE_ACCESS_TOKEN not available — skipping Management API migration)")
    print("  Migration file committed to repo — apply manually via psql or Supabase dashboard")

# Verify current metrics
print("\n--- Current pencil_dod_evaluate_county results ---")
if SB_KEY:
    for county in COUNTIES:
        result = rest_evaluate(county)
        if result and isinstance(result, dict):
            passes = sum(1 for ltr in "ABCDEFGHIJ" if isinstance(result.get(ltr), dict) and result[ltr].get("pass"))
            letters = {ltr: result.get(ltr) for ltr in "ABCDEFGHIJ"}
            print(f"  {county} [{passes}/10]: {json.dumps(letters, default=str)}")
        elif result and isinstance(result, list):
            passes = sum(1 for r in result if isinstance(r, dict) and r.get("pass"))
            print(f"  {county} [{passes}/10]: {json.dumps(result, default=str)}")
        else:
            print(f"  {county}: eval failed - {result}")
else:
    print("  (SUPABASE_SERVICE_ROLE_KEY not available — skipping live evaluation)")

print("\nDone.")
