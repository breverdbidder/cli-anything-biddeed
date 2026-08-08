#!/usr/bin/env python3
"""
Apply columbia I+J migration and verify results.
dispatch_id: 9f7b5985-3765-4e7b-955c-10e2f2aca59e
"""
import os
import sys
import json
import requests
from pathlib import Path

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
REF = "mocerqjnksmhcjzxrewo"

def get_credentials():
    token = os.environ.get('SUPABASE_ACCESS_TOKEN')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY')
    return token, service_key

def run_sql_via_mgmt(sql, token):
    resp = requests.post(
        MGMT_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=120
    )
    return resp

def run_sql_via_rest(sql, service_key):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json"
        },
        json={"query": sql},
        timeout=120
    )
    return resp

def main():
    token, service_key = get_credentials()
    
    if not token and not service_key:
        print("BLOCKED: No DB credentials available (SUPABASE_ACCESS_TOKEN or SUPABASE_SERVICE_ROLE_KEY).")
        print("Migration file created at migrations/20260808_gold_standard_shard3_9f7b5985_columbia_ij.sql")
        print("Apply via GHA dispatch of apply-gold-standard-fix.yml or equivalent.")
        sys.exit(0)
    
    migration_path = Path(__file__).parent / "migrations" / "20260808_gold_standard_shard3_9f7b5985_columbia_ij.sql"
    if not migration_path.exists():
        print(f"ERROR: Migration file not found: {migration_path}")
        sys.exit(1)
    
    migration_sql = migration_path.read_text()
    print(f"Migration file: {migration_path.name} ({len(migration_sql)} chars)")
    
    print("\n=== BEFORE: pencil_dod_evaluate_county('columbia') ===")
    before_sql = "SET statement_timeout=0; SELECT public.pencil_dod_evaluate_county('columbia');"
    
    if token:
        r = run_sql_via_mgmt(before_sql, token)
    else:
        r = run_sql_via_rest(before_sql, service_key)
    
    if r.status_code in (200, 201):
        try:
            data = r.json()
            print(json.dumps(data, indent=2, default=str))
        except Exception:
            print(r.text[:2000])
    else:
        print(f"Before query failed: HTTP {r.status_code}")
        print(r.text[:500])
    
    print("\n=== APPLYING MIGRATION ===")
    if token:
        r = run_sql_via_mgmt(migration_sql, token)
    else:
        r = run_sql_via_rest(migration_sql, service_key)
    
    if r.status_code in (200, 201):
        print(f"Migration applied: HTTP {r.status_code}")
        try:
            data = r.json()
            if isinstance(data, list):
                print(f"Rows returned: {len(data)}")
            else:
                print(json.dumps(data, indent=2, default=str)[:500])
        except Exception:
            print(r.text[:500])
    else:
        print(f"Migration FAILED: HTTP {r.status_code}")
        print(r.text[:1000])
        sys.exit(1)
    
    print("\n=== AFTER: pencil_dod_evaluate_county('columbia') ===")
    after_sql = "SET statement_timeout=0; SELECT public.pencil_dod_evaluate_county('columbia');"
    
    if token:
        r = run_sql_via_mgmt(after_sql, token)
    else:
        r = run_sql_via_rest(after_sql, service_key)
    
    if r.status_code in (200, 201):
        try:
            data = r.json()
            print(json.dumps(data, indent=2, default=str))
            if data and isinstance(data, list):
                row = data[0]
                if 'pencil_dod_evaluate_county' in row:
                    result = row['pencil_dod_evaluate_county']
                    passes = sum(1 for k, v in result.items()
                                 if k not in ('county', 'auctions_total') and isinstance(v, dict) and v.get('pass'))
                    print(f"\n=== SCORE: {passes}/10 ===")
                    for letter in ['A','B','C','D','E','F','G','H','I','J']:
                        if letter in result:
                            v = result[letter]
                            status = 'PASS' if v.get('pass') else 'FAIL'
                            metric = v.get('metric', '')
                            detail = v.get('detail', '')
                            print(f"  {letter}: {status} metric={metric} [{detail}]")
        except Exception as e:
            print(f"Parse error: {e}")
            print(r.text[:2000])
    else:
        print(f"After query failed: HTTP {r.status_code}")
        print(r.text[:500])
    
    print("\n=== SPOT CHECKS ===")
    checks = [
        ("columbia bid_decisions count", "SELECT COUNT(*) AS n FROM public.bid_decisions WHERE county_slug='columbia' AND arv IS NOT NULL AND ml_score IS NOT NULL AND factors ? 'distress_location' AND factors ? 'cma_distressed';"),
        ("columbia parcel_zones count", "SELECT COUNT(*) AS n FROM public.parcel_zones pz WHERE EXISTS (SELECT 1 FROM public.multi_county_auctions a WHERE a.parcel_id=pz.parcel_id AND lower(a.county)='columbia');"),
        ("columbia assessed_value fill", "SELECT COUNT(*) FILTER (WHERE assessed_value IS NOT NULL) AS has_av, COUNT(*) AS total FROM public.multi_county_auctions WHERE lower(county)='columbia';"),
        ("columbia lat/lon fill", "SELECT COUNT(*) FILTER (WHERE latitude IS NOT NULL) AS has_lat, COUNT(*) AS total FROM public.multi_county_auctions WHERE lower(county)='columbia';"),
    ]
    
    for label, sql in checks:
        if token:
            r = run_sql_via_mgmt(f"SET statement_timeout=0; {sql}", token)
        else:
            r = run_sql_via_rest(sql, service_key)
        if r.status_code in (200, 201):
            try:
                data = r.json()
                print(f"  {label}: {json.dumps(data)}")
            except Exception:
                print(f"  {label}: {r.text[:200]}")
        else:
            print(f"  {label}: HTTP {r.status_code}")

if __name__ == '__main__':
    main()
