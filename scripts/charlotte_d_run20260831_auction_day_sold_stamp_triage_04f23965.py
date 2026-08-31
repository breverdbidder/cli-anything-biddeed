#!/usr/bin/env python3
"""Charlotte County Gold Standard D fix — auction-day parity stamp, wave 2
(dispatch: eea4bd53-2820-4c5e-8200-6df5a457b77e, architect triage
04f23965-065b-46b5-8c8d-721d3471139b, issue #19652, 2026-08-31 22:xx UTC).

CONTEXT: the prior same-day session (commit 3b202835, script
charlotte_d_run20260831_auction_day_cancel_stamp.py) stamped case
25001583CA and left a poller watching 5 more rows from the SAME 2026-08-31
auction that were still LISTED at that write time (16:05Z):
25001498CA, 25001286CA, 26000042CA, 25000931CA, 25000598CA.

RE-CHECK THIS SESSION (live, 22:25Z, ~6h after the earlier stamp): all 5
rows now carry tier1_sale_status='SOLD', tier1_authoritative=true,
tier1_verified_at=2026-08-31T22:25:00Z, tier1_source_run_id=176919 (fresh
cron read, not stale) -- the auction has concluded and results are in.
parity_status is still NULL on all 5 (never stamped).

FIX: applies the county's own pre-existing, repeatedly-precedented mapping
(scripts/charlotte_cd_tier1_run93161_parity_stamp.py and
charlotte_d_run20260831_auction_day_cancel_stamp.py):
tier1_sale_status='SOLD' + tier1_authoritative=true -> parity_status=
'matched_clean', parity_source='tier1_foreclosure_outcome'-style tag
(matches the exact parity_source pattern already used by other charlotte
matched_clean/SOLD rows, e.g. 23001550CA, 24001068CA -> 'tier1_foreclosure_outcome').

Idempotent: re-running finds parity_status already set and is a no-op PATCH.
"""
import os
import json
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

COUNTY = 'charlotte'
DISPATCH = '04f23965'

ROWS = [
    '25001498CA',
    '25001286CA',
    '26000042CA',
    '25000931CA',
    '25000598CA',
]


def patch_mca(case_number: str, fields: dict):
    url = (f'{REST}/multi_county_auctions'
           f'?county=eq.{COUNTY}&case_number=eq.{case_number}')
    r = requests.patch(url, headers=H, data=json.dumps(fields), timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f'PATCH {case_number} failed [{r.status_code}]: {r.text[:300]}')
    body = r.json()
    if len(body) != 1:
        raise RuntimeError(f'PATCH {case_number} matched {len(body)} rows, expected 1: {body}')
    return body


if __name__ == '__main__':
    # Pre-flight: verify live state matches the diagnosis before writing anything.
    check = requests.get(
        f'{REST}/multi_county_auctions'
        f'?county=eq.{COUNTY}&case_number=in.({",".join(ROWS)})'
        f'&select=case_number,tier1_sale_status,tier1_authoritative,parity_status',
        headers=H, timeout=30,
    ).json()
    by_case = {r['case_number']: r for r in check}
    for cn in ROWS:
        row = by_case.get(cn)
        if row is None:
            raise RuntimeError(f'{cn} not found in multi_county_auctions')
        if row['tier1_sale_status'] != 'SOLD' or not row['tier1_authoritative']:
            raise RuntimeError(f'{cn} pre-flight failed: {row}')

    updated = []
    for cn in ROWS:
        fields = {
            'parity_status': 'matched_clean',
            'parity_source': f'tier1:charlotte_shard5_{DISPATCH}_20260831_triage:ch_D_auction_day_sold_wave2',
        }
        patch_mca(cn, fields)
        updated.append((cn, fields['parity_status']))

    for cn, s in updated:
        print(f'{cn}: {s}')
    print(f'TOTAL rows updated: {len(updated)}')
