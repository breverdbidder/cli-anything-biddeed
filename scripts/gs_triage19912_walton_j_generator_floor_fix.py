#!/usr/bin/env python3
"""
Architect triage (issue #19912, diagnosing blocked #19837), dispatch
aa276a6e-2402-47a6-8810-796f74c2392c -- walton letter J generator floor fix.

ROOT CAUSE (confirmed by reading scripts/shard9_j_generator.py
build_bid_decision(), NOT edited here -- this is a targeted county-scoped
recompute, matching the precedent pattern in
scripts/gs_8da482b6_walton_j_ghostfix.py):

  Two flat-constant floors in build_bid_decision() independently manufacture
  templated duplicate bid_decisions rows whenever a real per-parcel value
  falls below the floor:
    1. `arv = max(mkt, config['arv'] * 0.4)` -- walton config['arv']=520000,
       so any real market_value/assessed_value below $208,000 gets clobbered
       to the identical $208,000 floor. Collapsed 32 of 151 walton rows into
       one indistinguishable (arv=208000, max_bid=90600, ml_score=0.75) tuple.
    2. `arv = max(arv, 50000)` -- any real value below $50,000 (walton has
       genuine small platted vacant lots in the DeFuniak Springs
       20-4N-20-29000 subdivision with assessed_value in the hundreds-to-low-
       thousands) gets clobbered to a second identical $50,000 floor.
       Collapsed another 17 of 151 rows into one tuple.

  Both floors are removed in THIS script's recompute() only (shard9_j_generator.py
  itself is intentionally left untouched, per PARALLEL-FLEET RULES / surgical-
  change discipline -- other counties' configs may rely on the same function
  and a shared-code edit was out of this triage session's scope).

RESIDUAL, NOT FIXED (genuine data ceiling, documented not fabricated):
  12 of 151 walton bid_decisions rows still resolve to an identical
  (arv=200000, max_bid=85000, ml_score=0.75) tuple. Traced to
  multi_county_auctions.assessed_value=200000 for those exact 12 case_numbers
  -- a confirmed UPSTREAM placeholder, not a bid_decisions computation bug:
  3 of the 12 even carry a garbage parcel_id ("Property Appraiser",
  "TIMESHARE" -- literal UI label strings, proof of an upstream scrape/parse
  failure). multi_county_auctions is an M2 protected table (read-only unless
  an issue names it); this script does not touch it and does not fabricate a
  replacement value. See gold_standard_ultraloop_audit walton/J (this
  dispatch) for the full residual list and the REFUTED verdict.

RESULT: distinct-tuple count across walton's 151 bid_decisions rows rose from
113 to 122; rows in clusters of >=3 identical values fell from ~29-35 to 25
(all 25 are the still-unresolved 12-row placeholder cluster plus two genuine
small-lot subdivision clusters of legitimately-shared real assessed_value).
Prior session (2026-08-27) baseline was 95 of 145 rows (65.5%) fabricated;
this session: 12 of 151 (7.9%) residual, all attributable to one documented
upstream data gap.

Usage:
  python scripts/gs_triage19912_walton_j_generator_floor_fix.py            # apply
  python scripts/gs_triage19912_walton_j_generator_floor_fix.py --dry-run  # report only
"""
import argparse
import json
import os
from collections import defaultdict

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

COUNTY = 'walton'
ARV_BASE = 520000
LOCATION_SCORE = 8.0
DUP_CLUSTER_MIN = 4  # only touch rows in clusters this large or bigger

TIERED_REPAIRS = [
    (100000, 30000),
    (200000, 25000),
    (400000, 20000),
    (float('inf'), 15000),
]

# Known upstream placeholder: multi_county_auctions.assessed_value=200000
# identically for these 12 case_numbers (3 with garbage parcel_id). Left
# untouched -- see module docstring.
KNOWN_PLACEHOLDER_CASES = {
    '2025-0090TD', '2026-0001TD', '2026-0024TD', '24CA000292', '24CA000541',
    '25CA000128', '25CA000377', '25CA000531', '25CA000561', '25CA000562',
    '25CA000566', '25CA000591',
}


def tiered_repair(arv):
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return repair
    return 15000


def shapira_max_bid(arv, repairs):
    profit_reserve = min(25000, 0.15 * arv)
    return (arv * 0.70) - repairs - 10000 - profit_reserve


def recompute(mca_row):
    """Same shape as build_bid_decision() in scripts/shard9_j_generator.py,
    minus the two clobbering floors -- see module docstring."""
    mkt = (mca_row.get('market_value') or mca_row.get('po_market_value')
           or mca_row.get('assessed_value') or None)
    opening = mca_row.get('opening_bid')
    opening = float(opening) if opening else 0.0
    if mkt:
        arv = float(mkt)
    elif opening > 1000:
        arv = opening * 1.4
    else:
        return None
    repairs = tiered_repair(arv)
    max_bid = max(shapira_max_bid(arv, repairs), 0)
    ml_score = 0.75 if max_bid > 1000 else 0.38
    opening_f = opening if opening > 0 else arv * 0.5
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
        'arv_source': 'shapira_formula_shard9_j_gen_triage19912_refresh',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with httpx.Client(timeout=30) as client:
        bd_resp = client.get(f'{BASE}/bid_decisions', headers=HEADERS, params={
            'select': 'id,case_number,arv,max_bid,ml_score',
            'county_slug': f'eq.{COUNTY}',
        })
        bd_resp.raise_for_status()
        bid_decisions = bd_resp.json()

        groups = defaultdict(list)
        for row in bid_decisions:
            groups[(row['arv'], row['max_bid'], row['ml_score'])].append(row)
        degenerate_cases = {
            row['case_number']
            for rows in groups.values() if len(rows) >= DUP_CLUSTER_MIN
            for row in rows
        }
        target_cases = degenerate_cases - KNOWN_PLACEHOLDER_CASES
        if not target_cases:
            print('no degenerate clusters found beyond the known residual -- nothing to do')
            return

        cases_filter = ','.join(target_cases)
        mca_resp = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS, params={
            'select': 'case_number,parcel_id,market_value,po_market_value,assessed_value,opening_bid,sale_type',
            'county': f'eq.{COUNTY}',
            'case_number': f'in.({cases_filter})',
        })
        mca_resp.raise_for_status()
        mca_by_case = {r['case_number']: r for r in mca_resp.json()}

        updated, residual = [], []
        for row in bid_decisions:
            case = row['case_number']
            if case not in target_cases:
                continue
            mca_row = mca_by_case.get(case)
            if not mca_row:
                residual.append({'case_number': case, 'reason': 'no_mca_row'})
                continue
            result = recompute(mca_row)
            if result is None:
                residual.append({'case_number': case, 'reason': 'no_real_signal'})
                continue
            if not args.dry_run:
                resp = client.patch(f'{BASE}/bid_decisions', headers=HEADERS,
                                     params={'id': f'eq.{row["id"]}'}, json=result)
                resp.raise_for_status()
            updated.append({'id': row['id'], 'case_number': case,
                             'old_arv': row['arv'], 'new_arv': result['arv']})

        print(f'{"[dry-run] " if args.dry_run else ""}updated={len(updated)} residual={len(residual)}')
        for r in residual:
            print('  residual:', r)


if __name__ == '__main__':
    main()
