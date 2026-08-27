#!/usr/bin/env python3
"""
Gold Standard dispatch 8da482b6-8cff-45ea-9950-4e8fed552f37 — walton letter J ghost-fill remediation.

Scoped, one-off fix (NOT a shared generator edit) for the 95 degenerate/templated
public.bid_decisions rows in county_slug='walton' diagnosed in commit ddd3cd69 /
migration 20260827f_architect_triage_19510_shard1_walton_freshness_refresh_j_ghost_fill_flag.sql.

ROOT CAUSE (confirmed by reading scripts/shard9_j_generator.py, NOT edited here):
  build_bid_decision() computes `arv = max(mkt, config['arv'] * 0.4)` where
  config['arv']=520000 for walton (single flat county-wide 30A-beach-corridor
  estimate). 0.4*520000=208000 floor clobbers real per-parcel market_value for
  the 84-row template; for the 11-row template mkt was null when the generator
  last ran but real assessed_value/market_value has since been backfilled.

This script:
  1. Fetches the 95 walton bid_decisions rows matching the two degenerate tuples.
  2. For each, looks up matching multi_county_auctions rows (county=eq.walton,
     case_number=eq.<case>), preferring an exact parcel_id match, else the row
     with the most complete value fields.
  3. Recomputes arv/repairs/max_bid/ml_score/factors WITHOUT the arv_base*0.4
     floor, using the same tiered-repair/Shapira-formula shape as
     build_bid_decision() in scripts/shard9_j_generator.py (read, not imported,
     to avoid touching the shared generator).
  4. PATCHes each bid_decisions row by id.
  5. Rows where no real value signal exists are left unchanged and reported as
     a residual ceiling (never guessed).

Usage:
  python scripts/gs_8da482b6_walton_j_ghostfix.py            # apply
  python scripts/gs_8da482b6_walton_j_ghostfix.py --dry-run  # report only, no PATCH
"""
import os
import sys
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

COUNTY = 'walton'
LOCATION_SCORE = 8.0  # unchanged from COUNTY_CONFIG['walton']['location_score'] in shard9_j_generator.py

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


def pick_best_mca_row(mca_rows: list, target_parcel_id: str | None) -> dict | None:
    """Prefer exact parcel_id match; else the row with most complete value fields."""
    if not mca_rows:
        return None
    if target_parcel_id:
        exact = [r for r in mca_rows if r.get('parcel_id') == target_parcel_id]
        if exact:
            mca_rows = exact

    def completeness(r):
        return sum(1 for f in ('market_value', 'po_market_value', 'assessed_value', 'opening_bid') if r.get(f))

    return max(mca_rows, key=completeness)


def recompute(mca_row: dict) -> dict | None:
    """Returns dict with arv/repairs/max_bid/ml_score/factors, or None if no real signal."""
    mkt = (mca_row.get('market_value') or mca_row.get('po_market_value')
           or mca_row.get('assessed_value') or None)
    opening = mca_row.get('opening_bid')
    if mkt:
        arv = float(mkt)
    elif opening and float(opening) > 1000:
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
        'arv_source': 'shapira_formula_walton_j_ghostfix_8da482b6_real_value',
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    client = httpx.Client(timeout=60)

    # 1. Fetch the 95 degenerate rows
    params = {
        'select': 'id,case_number,parcel_id,arv,max_bid,ml_score',
        'county_slug': f'eq.{COUNTY}',
        'or': '(and(arv.eq.208000,max_bid.eq.90600),and(arv.eq.50000,max_bid.eq.0))',
    }
    r = client.get(f'{BASE}/bid_decisions', headers=HEADERS, params=params)
    r.raise_for_status()
    ghost_rows = r.json()
    print(f'Found {len(ghost_rows)} degenerate bid_decisions rows for {COUNTY}')

    # 2. Fetch all MCA rows for walton once (154 rows, cheap)
    mca_params = {
        'select': 'case_number,parcel_id,market_value,assessed_value,po_market_value,opening_bid,sale_type',
        'county': f'eq.{COUNTY}',
        'limit': '5000',
    }
    rm = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS, params=mca_params)
    rm.raise_for_status()
    mca_all = rm.json()
    mca_by_case = {}
    for row in mca_all:
        mca_by_case.setdefault(row['case_number'], []).append(row)
    print(f'Fetched {len(mca_all)} MCA rows for {COUNTY} ({len(mca_by_case)} distinct case_numbers)')

    results = []
    unresolved = []
    for br in ghost_rows:
        case = br['case_number']
        pid = br.get('parcel_id')
        mca_candidates = mca_by_case.get(case, [])
        best = pick_best_mca_row(mca_candidates, pid)

        if not best:
            unresolved.append({'id': br['id'], 'case_number': case, 'reason': 'no_mca_match'})
            continue

        new_vals = recompute(best)
        if new_vals is None:
            unresolved.append({'id': br['id'], 'case_number': case, 'reason': 'no_real_value_signal'})
            continue

        picked_note = 'parcel_id_match' if pid and best.get('parcel_id') == pid else 'most_complete_row'
        results.append({
            'id': br['id'],
            'case_number': case,
            'parcel_id': pid,
            'arv_before': br['arv'],
            'max_bid_before': br['max_bid'],
            'ml_score_before': br['ml_score'],
            'arv_after': new_vals['arv'],
            'max_bid_after': new_vals['max_bid'],
            'ml_score_after': new_vals['ml_score'],
            'mca_row_picked': picked_note,
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
        'dispatch_id': '8da482b6-8cff-45ea-9950-4e8fed552f37',
        'county': COUNTY,
        'rows_examined': len(ghost_rows),
        'rows_resolvable': len(results),
        'rows_fixed': fixed if not args.dry_run else 0,
        'rows_left_unresolved': len(unresolved),
        'unresolved_detail': unresolved,
        'sample_changes': results[:5],
    }
    with open('/tmp/gs_8da482b6_walton_j_ghostfix_result.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps({k: v for k, v in out.items() if k != 'sample_changes'}, indent=2, default=str))


if __name__ == '__main__':
    main()
