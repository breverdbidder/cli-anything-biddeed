#!/usr/bin/env python3
"""
SHARD-2 EVAL: polk, madison, taylor — live pencil_dod_evaluate_county
Dispatch: f8aa86b0-22cb-490b-b51a-d79deed78e09
Session: architect-20260801T160000
"""
import os
import json
import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = (
    os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or
    os.environ.get('SUPABASE_SERVICE_KEY') or
    os.environ.get('SUPABASE_KEY', '')
)

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}


def rpc(fn, params=None):
    r = httpx.post(
        f'{SUPABASE_URL}/rest/v1/rpc/{fn}',
        headers=HEADERS,
        json=params or {},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


def main():
    counties = ['polk', 'madison', 'taylor']
    results = {}
    for county in counties:
        print(f'\n=== {county.upper()} ===')
        try:
            result = rpc('pencil_dod_evaluate_county', {'p_county': county})
            results[county] = result
            print(json.dumps(result, indent=2))
        except Exception as e:
            print(f'ERROR: {e}')
            results[county] = {'error': str(e)}

    print('\n=== SUMMARY ===')
    for county, data in results.items():
        if 'error' in data:
            print(f'{county}: ERROR — {data["error"]}')
            continue
        passes = sum(1 for k, v in data.items() if k.isupper() and len(k) == 1 and isinstance(v, dict) and v.get('pass'))
        total = sum(1 for k, v in data.items() if k.isupper() and len(k) == 1 and isinstance(v, dict))
        print(f'{county}: {passes}/{total}')
        for letter in 'ABCDEFGHIJ':
            if letter in data:
                ld = data[letter]
                status = 'PASS' if ld.get('pass') else 'FAIL'
                metric = ld.get('metric')
                detail = ld.get('detail', '')
                print(f'  {letter}: {status} metric={metric} {detail}')


if __name__ == '__main__':
    main()
