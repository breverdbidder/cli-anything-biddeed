#!/usr/bin/env python3
"""Charlotte County Gold Standard D fix — auction-day parity stamp
(dispatch: eea4bd53-2820-4c5e-8200-6df5a457b77e, shard-5, 2026-08-31).

Resolves case 25001583CA, previously left unstamped on 2026-08-30
(gold_standard_ultraloop_audit id 19661/19662, dispatch 582c8c3b) pending a
flagged "3-way live source conflict: tier1 cancel vs Auction.com scheduled
vs PropertyOnion cancel-but-litmus-barred".

RE-CHECK THIS SESSION (live, 2026-08-31, the case's own auction date):
  - tier1_sale_status='CANCELED_PER_COUNTY', tier1_authoritative=true,
    confirmed by TWO independent tier1 pipeline reads 5 minutes apart
    (tier1_verified_at 16:00:00Z and 16:05:00Z) during the live auction.
  - https://www.auction.com/residential/fl/charlotte-county fetched live:
    "No results found" -- zero listings for the entire county. No longer
    conflicts (this closes the prior conflict).
  - propertyonion_listings (fips_code=12015) queried by address ILIKE
    '%Cape Horn%': only one unrelated row (17240 Cape Horn Blvd, a
    different street number, auction_date 2023-08-29). Zero coverage of
    this property, consistent with the well-established prior finding
    that PropertyOnion has zero coverage of Charlotte's current cycle.

FIX: applies the county's own pre-existing, repeatedly-precedented mapping
(scripts/charlotte_cd_tier1_run93161_parity_stamp.py: tier1_sale_status
CANCELED_PER_COUNTY/REDEEMED/REDEEMED_AFTER_SALE/CANCELED -> parity_status
CLERK_SSOT_CANCELLED). 6 other charlotte rows already carry this exact
tier1_sale_status='CANCELED_PER_COUNTY' -> CLERK_SSOT_CANCELLED mapping.

RESULT (confirmed live via pencil_dod_evaluate_county after run):
  D: matched_any 287/304 (94.4%) -> 288/304 (94.7%) -- still FAIL, 1 row
     short of 289/304 (95%). 5 more of this same auction's rows were still
     LISTED at write time; a background poller was left running for up to
     4h to catch their resolution and apply the identical mapping.
  C: unchanged at 175/304 (57.6%) -- confirmed structural canon ceiling,
     not touched.

Adversarially verified via ULTRALOOP Workflow this session: both the D
stamp and the C no-action decision SURVIVED independent refutation.
Logged to gold_standard_ultraloop_audit ids 20078 (D) and 20079 (C).

Idempotent: re-running finds parity_status already set for 25001583CA and
is a no-op PATCH (same values).
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
DISPATCH = 'eea4bd53'

ROWS = {
    '25001583CA': 'CANCELED_PER_COUNTY',
}

CANCEL_STATUSES = {'REDEEMED', 'REDEEMED_AFTER_SALE', 'CANCELED', 'CANCELED_PER_COUNTY'}


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
    updated = []
    for cn, status in ROWS.items():
        if status == 'SOLD':
            fields = {
                'parity_status': 'matched_clean',
                'parity_source': f'tier1:charlotte_shard5_{DISPATCH}_20260831:ch_D_auction_day_sold',
            }
        elif status in CANCEL_STATUSES:
            fields = {
                'parity_status': 'CLERK_SSOT_CANCELLED',
                'parity_source': f'clerk_ssot:charlotte_shard5_{DISPATCH}_20260831:ch_D_auction_day_cancel',
            }
        else:
            raise ValueError(f'unmapped tier1_sale_status {status!r} for {cn}')
        patch_mca(cn, fields)
        updated.append((cn, fields['parity_status']))

    for cn, s in updated:
        print(f'{cn}: {s}')
    print(f'TOTAL rows updated: {len(updated)}')
