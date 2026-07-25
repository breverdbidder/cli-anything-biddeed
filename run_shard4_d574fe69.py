#!/usr/bin/env python3
"""
SHARD-4 d574fe69: Apply osceola G fix migration + run enrichment script.
Executed without arguments — all config is embedded.
"""
import os, sys, json, httpx

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SUPA_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPA_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

def mgmt_sql(query: str):
    if not TOKEN:
        print("SUPABASE_ACCESS_TOKEN not set — cannot apply via Management API")
        return None
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers=h, json={"query": query}, timeout=120
    )
    return r

def main():
    print("=== SHARD-4 d574fe69: osceola G fix + citrus/osceola I enrichment ===")

    # Step 1: Get BEFORE baseline
    print("\n--- BEFORE: pencil_dod_evaluate_county ---")
    for county in ("osceola", "citrus"):
        r = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county}');")
        if r:
            print(f"[{county}] STATUS {r.status_code}")
            try:
                print(json.dumps(r.json(), indent=2, default=str)[:4000])
            except Exception:
                print(r.text[:4000])

    # Step 2: Apply migration
    print("\n--- Applying migrations/20260725_shard4_citrus_osceola_d574fe69.sql ---")
    migration_path = os.path.join(os.path.dirname(__file__), "migrations", "20260725_shard4_citrus_osceola_d574fe69.sql")
    with open(migration_path) as f:
        sql = f.read()
    r = mgmt_sql(sql)
    if r:
        print(f"Migration STATUS {r.status_code}")
        try:
            print(json.dumps(r.json(), indent=2, default=str)[:4000])
        except Exception:
            print(r.text[:4000])
        if r.status_code not in (200, 201):
            print("ERROR: Migration failed — aborting")
            sys.exit(1)
    else:
        print("Skipping migration (no SUPABASE_ACCESS_TOKEN)")

    # Step 3: AFTER baseline
    print("\n--- AFTER: pencil_dod_evaluate_county ---")
    for county in ("osceola", "citrus"):
        r = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county}');")
        if r:
            print(f"[{county}] STATUS {r.status_code}")
            try:
                print(json.dumps(r.json(), indent=2, default=str)[:4000])
            except Exception:
                print(r.text[:4000])

    # Step 4: Run enrichment script
    print("\n--- Running scripts/shard4_citrus_osceola_d574fe69.py ---")
    import importlib.util, pathlib
    script_path = pathlib.Path(__file__).parent / "scripts" / "shard4_citrus_osceola_d574fe69.py"
    spec = importlib.util.spec_from_file_location("enrich", script_path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        if hasattr(mod, "main"):
            mod.main()
    except Exception as e:
        print(f"Enrichment script error: {e}")

    # Step 5: Final baseline
    print("\n--- FINAL: pencil_dod_evaluate_county ---")
    for county in ("osceola", "citrus"):
        r = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county}');")
        if r:
            print(f"[{county}] STATUS {r.status_code}")
            try:
                print(json.dumps(r.json(), indent=2, default=str)[:4000])
            except Exception:
                print(r.text[:4000])

if __name__ == "__main__":
    main()
