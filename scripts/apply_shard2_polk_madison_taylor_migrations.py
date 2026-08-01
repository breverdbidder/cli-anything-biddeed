#!/usr/bin/env python3
"""
Apply SHARD-2 polk/madison/taylor migrations via Supabase Management API.
dispatch_id: f8aa86b0-22cb-490b-b51a-d79deed78e09

Applies:
  1. migrations/20260801_gold_standard_shard2_polk_madison_taylor.sql
     (ultraloop audit rows, pipeline.counties notes, heartbeat)
  2. migrations/20260801_gold_standard_shard2_polk_j_generator.sql
     (polk J generator — insert missing bid_decisions)
  3. migrations/20260801_gold_standard_shard2_madison_taylor_j.sql
     (madison + taylor J generator — defensive insert)

Then runs pencil_dod_evaluate_county for each county to verify.

Usage:
  export SUPABASE_ACCESS_TOKEN=...
  export SUPABASE_URL=https://mocerqjnksmhcjzxrewo.supabase.co
  export SUPABASE_KEY=...
  python3 scripts/apply_shard2_polk_madison_taylor_migrations.py
"""
import os
import json
import sys
from pathlib import Path
import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = (
    os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or
    os.environ.get('SUPABASE_SERVICE_KEY') or
    os.environ.get('SUPABASE_KEY', '')
)
ACCESS_TOKEN = os.environ.get('SUPABASE_ACCESS_TOKEN', '')

MGMT_URL = 'https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query'
MGMT_HEADERS = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json',
}
RPC_BASE = f'{SUPABASE_URL}/rest/v1'
RPC_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

MIGRATIONS = [
    'migrations/20260801_gold_standard_shard2_polk_madison_taylor.sql',
    'migrations/20260801_gold_standard_shard2_polk_j_generator.sql',
    'migrations/20260801_gold_standard_shard2_madison_taylor_j.sql',
]


def apply_migration(client, path):
    sql = Path(path).read_text()
    print(f'\n=== Applying: {path} ===')

    if ACCESS_TOKEN:
        resp = client.post(MGMT_URL, headers=MGMT_HEADERS, json={'query': sql}, timeout=300)
        if resp.status_code in (200, 201):
            print(f'  OK (HTTP {resp.status_code})')
            try:
                data = resp.json()
                if isinstance(data, list) and data:
                    print(f'  Result: {json.dumps(data[:3])}')
            except Exception:
                pass
            return True
        else:
            print(f'  FAILED HTTP {resp.status_code}: {resp.text[:400]}')
            return False
    else:
        print('  SKIP: no SUPABASE_ACCESS_TOKEN — cannot apply migration via Management API')
        print('  To apply manually: run the SQL in migrations/ against the Supabase database')
        return False


def evaluate_county(client, county):
    print(f'\n=== pencil_dod_evaluate_county({county}) ===')
    resp = client.post(
        f'{RPC_BASE}/rpc/pencil_dod_evaluate_county',
        headers=RPC_HEADERS,
        json={'p_county': county},
        timeout=120,
    )
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2))
        return data
    else:
        print(f'  FAILED HTTP {resp.status_code}: {resp.text[:300]}')
        return None


def main():
    client = httpx.Client(timeout=300)

    if not ACCESS_TOKEN:
        print('WARNING: SUPABASE_ACCESS_TOKEN not set. Migrations cannot be applied via Management API.')
        print('Set the token and re-run, or apply the SQL files manually.')
        sys.exit(1)

    if not SUPABASE_KEY:
        print('ERROR: No SUPABASE_KEY found. Cannot run evaluations.')
        sys.exit(1)

    all_ok = True
    for migration in MIGRATIONS:
        ok = apply_migration(client, migration)
        if not ok:
            all_ok = False
            print(f'  FAILED: {migration}')

    print('\n' + '='*60)
    print('EVALUATION RESULTS (post-migration)')
    print('='*60)

    for county in ['polk', 'madison', 'taylor']:
        data = evaluate_county(client, county)
        if data and isinstance(data, dict):
            passes = sum(1 for k, v in data.items()
                        if len(k) == 1 and k.isupper() and isinstance(v, dict) and v.get('pass'))
            total = sum(1 for k, v in data.items()
                       if len(k) == 1 and k.isupper() and isinstance(v, dict))
            print(f'\n{county}: {passes}/{total}')
            for letter in 'ABCDEFGHIJ':
                if letter in data:
                    ld = data[letter]
                    status = 'PASS' if ld.get('pass') else 'FAIL'
                    metric = ld.get('metric')
                    detail = ld.get('detail', '')
                    print(f'  {letter}: {status} metric={metric} {detail}')

    if all_ok:
        print('\nAll migrations applied successfully.')
    else:
        print('\nSome migrations failed — check output above.')
        sys.exit(1)


if __name__ == '__main__':
    main()
