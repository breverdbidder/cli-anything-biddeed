#!/usr/bin/env python3
"""GOLD STANDARD lee letter J ghost-fill remediation, 2026-08-29 session.

Forked from scripts/gs_8da482b6_walton_j_ghostfix.py (identical remediation
pattern, county-scoped one-off, NOT an edit to the shared
scripts/shard9_j_generator.py).

ROOT CAUSE (confirmed live, same class as the walton precedent):
  build_bid_decision() in shard9_j_generator.py computes
  `arv = max(mkt, config['arv'] * 0.4)` where config['arv']=310000 for lee.
  0.4*310000=124000 floor clobbers real per-parcel assessed_value for every
  lee row whose real assessed_value is under $124,000 -- true for most of the
  107-row 2026-08-27..2026-08-29 new batch (small Lehigh Acres / Cape Coral
  lots and low-value tax-deed parcels). Confirmed live: of the 118 new-batch
  bid_decisions rows the J-generator inserted this session (run scripts/
  shard9_j_generator.py --county lee), exactly 51 collapsed to the identical
  templated tuple (arv=124000.0, max_bid=33200.0, ml_score=0.75) despite EVERY
  ONE of those 51 rows having a real, distinct assessed_value in
  multi_county_auctions (verified: 51 of 51 have assessed_value set, ranging
  from ~$5,600 to ~$100K+).
  A second, smaller degenerate cluster (10 rows, tuple
  (arv=50000.0, max_bid=0.0, ml_score=0.38)) is a related but distinct
  pattern: these 10 rows have NO market/assessed value at all (their STRAP was
  not found on the live ArcGIS FeatureServer in stage 2a -- a genuine source
  gap) but DO have a real, small opening_bid ($1.3K-$13.2K, small tax-deed
  liens). The generator's `arv = max(arv, 50000)` floor overrides the
  opening_bid*1.4 computation for all 10 (each opening_bid*1.4 < 50000),
  producing the same templated tuple for all of them.

This script:
  1. Fetches the 51 + 10 = 61 lee bid_decisions rows matching the two
     degenerate tuples, scoped to the 2026-08-27..2026-08-29 new-batch
     case_numbers (does NOT touch older/unrelated lee bid_decisions rows that
     may coincidentally share a tuple from a prior legitimate run).
  2. For each, looks up the matching multi_county_auctions row by case_number.
  3. Recomputes arv/repairs/max_bid/ml_score/factors WITHOUT the
     arv_base*0.4 floor, using the identical tiered-repair/Shapira-formula
     shape as build_bid_decision() in scripts/shard9_j_generator.py (read,
     not imported, to avoid touching the shared generator) -- real
     assessed_value directly, falling back to opening_bid*1.4 only when a row
     has genuinely no valuation data (matches this session's guardrail
     instructions verbatim).
  4. PATCHes each bid_decisions row by id.
  5. Rows where no real value signal exists at all (no assessed_value AND no
     opening_bid) are left unchanged and reported as a residual ceiling
     (never guessed) -- expected to be zero of the 61 per the diagnosis above.

Usage:
  python scripts/gold_standard_shard5_lee_20260829_j_ghostfix.py            # apply
  python scripts/gold_standard_shard5_lee_20260829_j_ghostfix.py --dry-run  # report only
"""
import os
import json
import argparse
import httpx

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = (os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
                or os.environ.get('SUPABASE_SERVICE_KEY')
                or os.environ.get('SUPABASE_KEY', ''))
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

COUNTY = 'lee'
LOCATION_SCORE = 7.5  # unchanged from COUNTY_CONFIG['lee']['location_score'] in shard9_j_generator.py
NEW_BATCH_CREATED_AT_GTE = '2026-08-27T00:00:00'

TIERED_REPAIRS = [
    (100000, 30000),
    (200000, 25000),
    (400000, 20000),
    (float('inf'), 15000),
]


def tiered_repair(arv: float) -> float:
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return repair
    return 15000


def shapira_max_bid(arv: float, repairs: float) -> float:
    profit_reserve = min(25000, 0.15 * arv)
    return (arv * 0.70) - repairs - 10000 - profit_reserve


def recompute(mca_row: dict) -> dict | None:
    """Returns dict with arv/repairs/max_bid/ml_score/factors, or None if no
    real signal. NO arv_base*0.4 floor and NO 50000 hard floor -- uses real
    per-row value directly, falling back to opening_bid*1.4 only when a row
    has genuinely no valuation data, per this session's guardrail."""
    mkt = (mca_row.get('market_value') or mca_row.get('po_market_value')
           or mca_row.get('assessed_value') or None)
    opening = mca_row.get('opening_bid')
    if mkt:
        arv = float(mkt)
    elif opening and float(opening) > 0:
        arv = float(opening) * 1.4
    else:
        return None

    repairs = tiered_repair(arv)
    max_bid = shapira_max_bid(arv, repairs)
    max_bid = max(max_bid, 0)
    ml_score = 0.75 if max_bid > 1000 else 0.38

    opening_f = float(opening) if opening and float(opening) > 0 else arv * 0.5
    ratio = max_bid / opening_f if opening_f > 0 else 1.0
    ratio = min(9.9999, max(-9.9999, ratio))

    factors = {
        'distress_location': {'score': LOCATION_SCORE, 'note': f'{COUNTY} county FL', 'honesty_marker': 'INFERRED'},
        'distress_property': {'score': 5.0, 'note': f'{mca_row.get("sale_type", "foreclosure")} distress', 'honesty_marker': 'INFERRED'},
        'distress_owner': {'score': 7.0, 'note': 'judicial action filed', 'honesty_marker': 'INFERRED'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm', 'honesty_marker': 'INFERRED'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm', 'honesty_marker': 'INFERRED'},
        'model': 'shapira_v14',
    }

    return {
        'arv': round(arv, 2),
        'repairs': round(repairs, 2),
        'max_bid': round(max_bid, 2),
        'bid_judgment_ratio': round(ratio, 4),
        'ml_score': ml_score,
        'factors': factors,
        'recommendation': 'BID' if max_bid > 1000 else 'SKIP',
        'arv_source': 'shapira_formula_lee_j_ghostfix_20260829_real_value',
    }


def get_all(client, path, params):
    out = []
    offset = 0
    while True:
        p = dict(params)
        p['limit'] = 1000
        p['offset'] = offset
        r = client.get(f'{BASE}/{path}', headers=HEADERS, params=p)
        r.raise_for_status()
        batch = r.json()
        out.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    client = httpx.Client(timeout=60)

    # 1. New-batch case_numbers (the scope this ghost-fill is confined to).
    mca_all = get_all(client, 'multi_county_auctions', {
        'select': 'case_number,parcel_id,market_value,assessed_value,po_market_value,opening_bid,sale_type',
        'county': f'eq.{COUNTY}',
        'created_at': f'gte.{NEW_BATCH_CREATED_AT_GTE}',
    })
    new_batch_cases = {r['case_number'] for r in mca_all}
    mca_by_case = {r['case_number']: r for r in mca_all}
    print(f'New-batch case_numbers (created>={NEW_BATCH_CREATED_AT_GTE}): {len(new_batch_cases)}')

    # 2. Fetch the two degenerate tuples' bid_decisions rows for lee.
    params = {
        'select': 'id,case_number,parcel_id,arv,max_bid,ml_score',
        'county_slug': f'eq.{COUNTY}',
        'or': '(and(arv.eq.124000,max_bid.eq.33200),and(arv.eq.50000,max_bid.eq.0))',
    }
    ghost_rows_all = get_all(client, 'bid_decisions', params)
    ghost_rows = [r for r in ghost_rows_all if r['case_number'] in new_batch_cases]
    print(f'Degenerate-tuple bid_decisions rows total for {COUNTY}: {len(ghost_rows_all)}; '
          f'scoped to new batch: {len(ghost_rows)}')

    results = []
    unresolved = []
    for br in ghost_rows:
        case = br['case_number']
        mca_row = mca_by_case.get(case)
        if not mca_row:
            unresolved.append({'id': br['id'], 'case_number': case, 'reason': 'no_mca_match'})
            continue

        new_vals = recompute(mca_row)
        if new_vals is None:
            unresolved.append({'id': br['id'], 'case_number': case, 'reason': 'no_real_value_signal'})
            continue

        results.append({
            'id': br['id'],
            'case_number': case,
            'parcel_id': br.get('parcel_id'),
            'arv_before': br['arv'],
            'max_bid_before': br['max_bid'],
            'ml_score_before': br['ml_score'],
            'arv_after': new_vals['arv'],
            'max_bid_after': new_vals['max_bid'],
            'ml_score_after': new_vals['ml_score'],
            'patch_body': new_vals,
        })

    print(f'Resolvable: {len(results)}  Unresolved (left unchanged): {len(unresolved)}')

    fixed = 0
    if not args.dry_run:
        for res in results:
            patch_url = f"{BASE}/bid_decisions?id=eq.{res['id']}"
            pr = client.patch(patch_url, headers={**HEADERS, 'Prefer': 'return=minimal'},
                               content=json.dumps(res['patch_body']))
            if pr.status_code in (200, 204):
                fixed += 1
            else:
                print(f"PATCH FAILED id={res['id']} case={res['case_number']}: {pr.status_code} {pr.text[:200]}")
    else:
        print('--dry-run set: no PATCHes issued')

    out = {
        'county': COUNTY,
        'new_batch_case_numbers': len(new_batch_cases),
        'degenerate_rows_examined': len(ghost_rows),
        'rows_resolvable': len(results),
        'rows_fixed': fixed if not args.dry_run else 0,
        'rows_left_unresolved': len(unresolved),
        'unresolved_detail': unresolved,
        'sample_changes': results[:8],
    }
    with open('/tmp/lee_j_ghostfix_result.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps({k: v for k, v in out.items() if k != 'sample_changes'}, indent=2, default=str))


if __name__ == '__main__':
    main()
