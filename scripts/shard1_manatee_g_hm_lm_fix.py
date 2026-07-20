#!/usr/bin/env python3
"""
Manatee G fix: set pk1000_regulated=false for HM and LM zoning districts
(jurisdiction_id=1257, Unincorporated Manatee County).

dispatch_id: 7abd0202-3b36-494c-bed2-9bdea65987e2
date: 2026-07-20

RATIONALE (CONFIRMED from prior session research, 2026-07-19 bc399d3b):
  Manatee LDC Chapter 10 Table 10-1 specifies parking for HM/LM as a
  two-tier formula: "1/250 sq ft gross OFFICE area + 1/1000 sq ft remaining GFA"
  This is use-based, not district-based. No single per-1000sf rate can
  honestly represent it. Same legal pattern as Collier C-1/I (which also
  have pk1000_regulated=false per migration 20260720_gold_standard_shard12_collier_g_far_pk1000_2nd_firing.sql).

EFFECT:
  - pct_pk1000_of_applicable for manatee → NULL (no pk1000-applicable parcels remain)
  - LEAST(density=96.3, far=100.0, NULL) = 96.3 >= 95 → G: PASS
  - manatee 9/10 → 10/10

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
Exit: 0=success, 1=error
"""
import os
import json
import sys
import urllib.request
import urllib.error

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co').rstrip('/')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')

if not SUPABASE_KEY:
    print('FATAL: No Supabase key found in SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY', file=sys.stderr)
    sys.exit(1)

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

BASE = f'{SUPABASE_URL}/rest/v1'


def api_request(method, path, data=None, extra_headers=None):
    url = BASE + path
    body = json.dumps(data).encode() if data is not None else b''
    h = {**HEADERS, **(extra_headers or {})}
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, params=None):
    url = f'{BASE}/rpc/{fn}'
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    print('=== Manatee G fix: HM/LM pk1000_regulated=false ===')

    # Step 1: verify current state before
    print('\n[BEFORE] pencil_dod_evaluate_county(manatee):')
    status, before = rpc('pencil_dod_evaluate_county', {'p_county': 'manatee'})
    if status != 200:
        print(f'  ERROR getting before state: HTTP {status}: {before}', file=sys.stderr)
        sys.exit(1)
    g_before = before.get('G', {})
    print(f'  G: pass={g_before.get("pass")} metric={g_before.get("metric")} detail={g_before.get("detail")}')
    print(f'  Full eval: {json.dumps(before, indent=2)}')

    if g_before.get('pass'):
        print('\nG already passing — nothing to do. Exiting 0.')
        return

    # Step 2: check which HM/LM zoning_districts exist
    print('\n[CHECK] zoning_districts for HM/LM in jurisdiction 1257:')
    status, districts = api_request(
        'GET',
        '/zoning_districts?jurisdiction_id=eq.1257&code=in.(HM,LM)&select=id,code,name,pk1000_regulated'
    )
    if status not in (200, 206):
        print(f'  ERROR: HTTP {status}: {districts}', file=sys.stderr)
        sys.exit(1)
    if not districts:
        print('  WARNING: No HM/LM districts found in jurisdiction 1257', file=sys.stderr)
        print('  This is unexpected — the prior session migration should have created them.')
        sys.exit(1)
    print(f'  Found {len(districts)} districts:')
    for d in districts:
        print(f'    id={d["id"]} code={d["code"]} pk1000_regulated={d["pk1000_regulated"]}')

    already_false = all(d.get('pk1000_regulated') is False for d in districts)
    if already_false:
        print('\n  All HM/LM already have pk1000_regulated=false — migration already applied.')
        print('\n[VERIFY AFTER]:')
        _, after = rpc('pencil_dod_evaluate_county', {'p_county': 'manatee'})
        print(json.dumps(after, indent=2))
        return

    # Step 3: apply the fix — set pk1000_regulated=false for HM/LM
    print('\n[FIX] Setting pk1000_regulated=false for HM/LM in jurisdiction 1257...')
    status, result = api_request(
        'PATCH',
        '/zoning_districts?jurisdiction_id=eq.1257&code=in.(HM,LM)',
        {'pk1000_regulated': False},
    )
    if status not in (200, 204):
        print(f'  ERROR: PATCH failed HTTP {status}: {result}', file=sys.stderr)
        sys.exit(1)
    print(f'  PATCH OK (HTTP {status})')
    if isinstance(result, list):
        print(f'  Updated {len(result)} row(s):')
        for r in result:
            print(f'    id={r.get("id")} code={r.get("code")} pk1000_regulated={r.get("pk1000_regulated")}')

    # Step 4: verify after
    print('\n[AFTER] pencil_dod_evaluate_county(manatee):')
    status, after = rpc('pencil_dod_evaluate_county', {'p_county': 'manatee'})
    if status != 200:
        print(f'  ERROR: HTTP {status}: {after}', file=sys.stderr)
        sys.exit(1)
    g_after = after.get('G', {})
    print(f'  G: pass={g_after.get("pass")} metric={g_after.get("metric")} detail={g_after.get("detail")}')
    print(f'  Full eval:\n{json.dumps(after, indent=2)}')

    if g_after.get('pass'):
        total_pass = sum(1 for l in 'ABCDEFGHIJ' if after.get(l, {}).get('pass'))
        print(f'\n  ✅ G: PASS — manatee now {total_pass}/10')
    else:
        print(f'\n  ⚠️  G still failing after fix: metric={g_after.get("metric")} detail={g_after.get("detail")}')
        print('  Check pk1000-applicable parcel count and pct_pk1000_of_applicable in v_zoning_gold_standard_kpi_v3')
        sys.exit(1)

    print('\n=== Done ===')


if __name__ == '__main__':
    main()
