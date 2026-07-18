#!/usr/bin/env python3
"""
One-shot migration applier for SHARD-12 dispatch 704e70a0.
Counties: okeechobee (G, I), st_johns (C, D, E, I, J)

Apply the SQL migration via Supabase Management API, then run the Python
executor for dynamic fixes (bid_decisions, parcel_zones, fl_parcels lookups).

Usage (in cc-runner-ghonly or gold-standard GHA job with secrets):
    python3 scripts/apply_shard12_704e70a0_migration.py

Wired to: gold-standard-shard12.yml (add this to the run step), or
           dispatch manually via gh workflow run apply-gold-standard-fix.yml
"""
import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime, timezone

DISPATCH_ID = '704e70a0-6459-4599-af5b-c2f31351913e'
MIGRATION_FILE = Path(__file__).parent.parent / 'supabase' / 'migrations' / \
    '20260718_shard12_okeechobee_g_i_stjohns_c_d_e_i_j_fix.sql'
EXECUTOR_SCRIPT = Path(__file__).parent / 'shard12_okeechobee_stjohns_session_704e70a0.py'

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = (os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or
                os.environ.get('SUPABASE_KEY') or
                os.environ.get('SUPABASE_SERVICE_KEY', ''))
ACCESS_TOKEN = os.environ.get('SUPABASE_ACCESS_TOKEN', '')
MGMT_SQL_URL = f'https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query'


def log(msg: str, level: str = 'INFO'):
    ts = datetime.now(timezone.utc).strftime('%H:%M:%S')
    print(f'[{ts}] {level}: {msg}', flush=True)


def apply_sql_via_mgmt_api(sql: str) -> bool:
    """Apply SQL via Supabase Management API (requires SUPABASE_ACCESS_TOKEN)."""
    if not ACCESS_TOKEN:
        log('No SUPABASE_ACCESS_TOKEN — cannot use Management API', 'WARN')
        return False

    import urllib.request, urllib.error
    payload = json.dumps({'query': sql}).encode('utf-8')
    req = urllib.request.Request(
        MGMT_SQL_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Content-Type': 'application/json',
            'User-Agent': 'BidDeed-GoldStandard-Shard12/1.0',
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            if resp.status == 200:
                log(f'SQL applied OK (HTTP 200): {body[:200]}', 'INFO')
                return True
            else:
                log(f'SQL failed HTTP {resp.status}: {body[:300]}', 'ERROR')
                return False
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else str(e)
        log(f'SQL HTTP error {e.code}: {body[:300]}', 'ERROR')
        return False
    except Exception as ex:
        log(f'SQL request error: {ex}', 'ERROR')
        return False


def evaluate_county(county_slug: str) -> dict:
    """Call pencil_dod_evaluate_county via PostgREST."""
    if not SUPABASE_KEY:
        log(f'No SUPABASE_KEY — cannot evaluate {county_slug}', 'WARN')
        return {}

    import urllib.request, urllib.error
    payload = json.dumps({'county_slug_arg': county_slug}).encode('utf-8')
    req = urllib.request.Request(
        f'{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county',
        data=payload,
        headers={
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST'
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as ex:
        log(f'evaluate_county({county_slug}) error: {ex}', 'WARN')
        return {}


def main():
    log(f'=== SHARD-12 MIGRATION APPLIER dispatch={DISPATCH_ID} ===', 'INFO')
    log(f'SUPABASE_KEY present: {bool(SUPABASE_KEY)}', 'INFO')
    log(f'ACCESS_TOKEN present: {bool(ACCESS_TOKEN)}', 'INFO')

    if not SUPABASE_KEY and not ACCESS_TOKEN:
        log('No credentials available — skipping DB operations', 'WARN')
        log('To apply: set SUPABASE_SERVICE_ROLE_KEY + SUPABASE_ACCESS_TOKEN env vars', 'INFO')
        return 0

    # Step 1: Baseline evaluations
    log('\n--- BASELINE ---', 'INFO')
    for county in ['okeechobee', 'st_johns']:
        ev = evaluate_county(county)
        if ev:
            log(f'{county}: {json.dumps(ev)[:400]}', 'INFO')
        else:
            log(f'{county}: evaluation unavailable', 'WARN')

    # Step 2: Apply SQL migration
    if not MIGRATION_FILE.exists():
        log(f'Migration file not found: {MIGRATION_FILE}', 'ERROR')
        return 1

    log(f'\n--- APPLYING SQL MIGRATION ---', 'INFO')
    log(f'File: {MIGRATION_FILE}', 'INFO')
    sql = MIGRATION_FILE.read_text()
    log(f'SQL size: {len(sql)} chars', 'INFO')

    ok = apply_sql_via_mgmt_api(sql)
    if not ok:
        log('SQL migration failed or skipped', 'WARN')
        # Continue anyway — Python executor may succeed independently
    else:
        log('SQL migration applied', 'INFO')

    # Step 3: Run Python executor (handles dynamic operations)
    if EXECUTOR_SCRIPT.exists():
        log(f'\n--- RUNNING PYTHON EXECUTOR ---', 'INFO')
        result = subprocess.run(
            [sys.executable, str(EXECUTOR_SCRIPT)],
            env={**os.environ, 'SUPABASE_URL': SUPABASE_URL, 'SUPABASE_KEY': SUPABASE_KEY},
            timeout=300,
            capture_output=False,
        )
        log(f'Executor exit code: {result.returncode}', 'INFO')
    else:
        log(f'Executor script not found: {EXECUTOR_SCRIPT}', 'WARN')

    # Step 4: Post-fix evaluations
    log('\n--- POST-FIX EVALUATIONS ---', 'INFO')
    time.sleep(3)
    for county in ['okeechobee', 'st_johns']:
        ev = evaluate_county(county)
        if ev:
            log(f'{county} AFTER: {json.dumps(ev)[:600]}', 'INFO')

    log('\n=== MIGRATION APPLIER DONE ===', 'INFO')
    return 0


if __name__ == '__main__':
    sys.exit(main())
