#!/usr/bin/env python3
"""
shard5_run7553_apply_migration.py
Apply the 20260731_gold_standard_shard5_seminole_citrus_run7553.sql migration
via the Supabase Management API (same method as mgmt_sql.py).

Usage:
  SUPABASE_ACCESS_TOKEN=<sbp_...> python3 scripts/shard5_run7553_apply_migration.py

Also runs the Python-side harvest + enrichment from shard5_seminole_citrus_run7553_fix.py
after the migration is applied.
"""
import os
import sys
import json
import urllib.request
from pathlib import Path

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def mgmt_sql(query: str) -> any:
    if not TOKEN:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set", flush=True)
        sys.exit(1)
    url = f"https://api.supabase.com/v1/projects/{REF}/database/query"
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())


def main():
    migration_path = Path(__file__).parent.parent / "migrations" / "20260731_gold_standard_shard5_seminole_citrus_run7553.sql"
    if not migration_path.exists():
        print(f"ERROR: migration not found at {migration_path}", flush=True)
        sys.exit(1)

    sql = migration_path.read_text()
    print(f"Applying migration: {migration_path.name}", flush=True)
    print(f"SQL length: {len(sql)} chars", flush=True)

    try:
        result = mgmt_sql(sql)
        print(f"STATUS 200 (success)", flush=True)
        print(json.dumps(result, indent=2, default=str)[:8000], flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"STATUS {e.code}", flush=True)
        print(body[:8000], flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        sys.exit(1)

    print("\nMigration applied. Running Python-side harvest+enrichment...", flush=True)

    # Now run the harvest + enrichment script
    fix_script = Path(__file__).parent / "shard5_seminole_citrus_run7553_fix.py"
    if fix_script.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("shard5_fix", str(fix_script))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    else:
        print(f"WARNING: fix script not found at {fix_script}", flush=True)


if __name__ == "__main__":
    main()
