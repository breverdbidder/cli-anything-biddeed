#!/usr/bin/env python3
"""
GOLD STANDARD shard-8 (okeechobee), dispatch_id ed344dc4-9b86-4f5a-97af-26ea782adcbe, loop run 7519.

Root cause (VERIFIED live via direct SQL against multi_county_auctions): okeechobee had 76 rows but only
66 distinct case_number values. Exactly 10 case_numbers (all TD-docket / tax_deed by Florida clerk
convention) were duplicated as two rows each:
  - an older row, already tier1-verified (real property_address/latitude/longitude/assessed_value,
    parity_status='matched_clean', parity_source LIKE 'tier1%'), but mislabeled sale_type='foreclosure'
  - a newer row (created 2026-07-30 16:35 UTC, data_source NULL) correctly labeled sale_type='tax_deed'
    but a blank duplicate scaffold with no parity_status and missing address/lat/lon.
All 10 pairs share an identical opening_bid between the two rows -- strong evidence they represent the
same underlying sale double-seeded with conflicting sale_type labels, not two real auctions.

Fix: for each pair, delete the blank tax_deed-labeled duplicate, then relabel the data-rich row's
sale_type from 'foreclosure' to 'tax_deed'. No address/lat/lon/value was invented -- every surviving
value already existed on the row that was kept. bid_decisions is keyed by (county_slug, case_number),
not by multi_county_auctions.id, so deleting the blank duplicate id does not orphan J.

Effect (live, VERIFIED via pencil_dod_evaluate_county('okeechobee')):
  auctions_total 76 -> 66, C 86.8 -> 100 (PASS), D 86.8 -> 100 (PASS), I 85.5 -> 98.5 (PASS).
  A/B/E/F/G/H/J unaffected (all remained PASS).

Residual (NOT fixed, reported honestly): case_number 2026TD050 (id adc8301b-d58f-4bd0-a300-f35d0239d82a,
parcel_id 1-25-37-35-0070-00060-1760) still lacks property_address/latitude/longitude. FL GIO Statewide
Cadastral was queried for this parcel_id (dash-stripped format, confirmed correct via a successful lookup
on a sibling okeechobee parcel) and returned zero features. Left incomplete rather than fabricated --
I is 98.5% (65 of 66), already above the 95% threshold.

This script is idempotent: rerunning it after the ids are already fixed matches zero rows and is a no-op.

Usage: python3 scripts/gold_standard_shard8_okeechobee_run7519_ed344dc4_cd_i_dedup_fix.py
"""
import os
import sys

import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

# (fc_id relabeled foreclosure->tax_deed, td_id blank duplicate deleted), keyed by case_number
PAIRS = {
    '2026TD038': ('0b4485d7-14c2-4b0d-ac68-570f38e21a5c', 'ad55c33c-4789-4c6b-a726-b43be20502fe'),
    '2026TD039': ('56b0b086-85b8-45f1-833b-edd1007520d2', '4d76412f-a072-4d1d-9c81-3c84a1a00437'),
    '2026TD040': ('92ab9212-c703-43dd-b5cd-5f0ea48d93cf', '0838f639-f18d-4293-be80-0824299fa8bf'),
    '2026TD045': ('4e663b11-0c3e-4364-8c50-849296837144', '3ce7f1c0-fee0-4f93-bf09-4ad61070088f'),
    '2026TD046': ('cacf2126-99fd-4c2d-a3bf-60227c96e366', 'f8499ad9-effa-4ea6-9e8e-619a7be52ab0'),
    '2026TD047': ('e2dbc581-1686-4afc-a768-8e26fc37e6db', '2be4766e-a83b-49c6-8e85-4225a7bdfcbd'),
    '2026TD048': ('21a32dc2-ef35-4106-9e06-7154a69fb1f7', '462bbf76-a2d7-4027-9751-6f885b2ea8c9'),
    '2026TD051': ('52092e61-ab25-4bfd-b011-da04bf354640', '568feb16-6bb7-4b3f-9dbc-c69900d3a5e6'),
    '2026TD067': ('428cdc3c-2ef5-4a98-aa8b-ed15913d5ad7', '3ae69a15-867e-47f8-acba-a1a377a4a97f'),
    '2026TD071': ('a9834e75-7771-4986-a2a8-a89a1ff776a4', '1af2a45c-df83-461c-9d9d-15433c51280f'),
}


def main() -> None:
    if not SUPABASE_KEY:
        print('SUPABASE_SERVICE_ROLE_KEY not set', file=sys.stderr)
        sys.exit(1)

    deleted, relabeled = 0, 0
    for case_number, (fc_id, td_id) in PAIRS.items():
        r = httpx.delete(f'{BASE}/multi_county_auctions', headers=HEADERS,
                          params={'id': f'eq.{td_id}', 'county': 'eq.okeechobee',
                                   'sale_type': 'eq.tax_deed', 'parity_status': 'is.null',
                                   'data_source': 'is.null'}, timeout=30)
        r.raise_for_status()
        n_deleted = len(r.json())
        deleted += n_deleted

        r = httpx.patch(f'{BASE}/multi_county_auctions', headers=HEADERS,
                         params={'id': f'eq.{fc_id}', 'county': 'eq.okeechobee', 'sale_type': 'eq.foreclosure'},
                         json={'sale_type': 'tax_deed'}, timeout=30)
        r.raise_for_status()
        n_relabeled = len(r.json())
        relabeled += n_relabeled

        print(f'{case_number}: deleted={n_deleted} relabeled={n_relabeled}')

    print(f'\nTotal: deleted={deleted} relabeled={relabeled} (expect 10/10 on first run, 0/0 if already applied)')


if __name__ == '__main__':
    main()
