#!/usr/bin/env python3
"""
SHARD-9 J-Generator: Bid Decisions via Shapira Formula
=======================================================
Generates Letter J bid_decisions for counties: lee, bay, volusia, calhoun, taylor
Uses Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)

Factors contract per production pencil_dod_evaluate_county:
  - distress_location, distress_property, distress_owner (triangle)
  - cma_distressed, cma_resale (two-arm CMA)

Usage:
  python scripts/shard9_j_generator.py --county lee
  python scripts/shard9_j_generator.py --county volusia
  python scripts/shard9_j_generator.py --all
"""
import os
import sys
import json
import logging
import argparse
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('shard9-j-gen')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = (os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
                or os.environ.get('SUPABASE_SERVICE_KEY')
                or os.environ.get('SUPABASE_KEY', ''))
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

# County-level ARV estimates (FL property appraiser medians)
COUNTY_CONFIG = {
    'lee':     {'arv': 310000, 'repair_factor': 0.09, 'location_score': 7.5},  # Fort Myers area
    'bay':     {'arv': 285000, 'repair_factor': 0.10, 'location_score': 7.0},  # Panama City area
    'volusia': {'arv': 280000, 'repair_factor': 0.10, 'location_score': 7.0},  # Daytona Beach area
    'calhoun': {'arv': 145000, 'repair_factor': 0.15, 'location_score': 5.5},  # Rural panhandle
    'taylor':  {'arv': 155000, 'repair_factor': 0.15, 'location_score': 5.5},  # Rural Big Bend
}

SHARD9_COUNTIES = list(COUNTY_CONFIG.keys())

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


def build_bid_decision(row: dict, county: str, config: dict) -> dict:
    arv_base = config['arv']
    opening = float(row.get('opening_bid') or 0)
    mkt = (row.get('market_value') or row.get('po_market_value')
           or row.get('assessed_value') or None)
    if mkt:
        mkt = float(mkt)
        arv = max(mkt, arv_base * 0.4)
    elif opening > 1000:
        arv = opening * 1.4
    else:
        arv = arv_base
    arv = max(arv, 50000)

    repairs = tiered_repair(arv)
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.75 if max_bid > 1000 else 0.38

    opening_f = opening if opening > 0 else arv * 0.5
    ratio = max_bid / opening_f if opening_f > 0 else 1.0
    ratio = min(9.9999, max(-9.9999, ratio))

    loc_score = config['location_score']
    factors = {
        'distress_location': {'score': loc_score, 'note': f'{county} county FL', 'honesty_marker': 'INFERRED'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type", "foreclosure")} distress', 'honesty_marker': 'INFERRED'},
        'distress_owner': {'score': 7.0, 'note': 'judicial action filed', 'honesty_marker': 'INFERRED'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm', 'honesty_marker': 'INFERRED'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm', 'honesty_marker': 'INFERRED'},
        'model': 'shapira_v14',
    }

    return {
        'case_number': row['case_number'],
        'county_slug': county,
        'parcel_id': row.get('parcel_id') or None,
        'address': row.get('property_address'),
        'auction_date': row.get('auction_date'),
        'arv': round(arv, 2),
        'repairs': round(repairs, 2),
        'max_bid': round(max(max_bid, 0), 2),
        'bid_judgment_ratio': round(ratio, 4),
        'ml_score': ml_score,
        'factors': factors,
        'recommendation': 'BID' if max_bid > 1000 else 'SKIP',
        'confidence': 0.65,
        'arv_source': 'shapira_formula_shard9_j_gen',
        'pipeline_version': 'shard9_j_gen_v1',
    }


def run_for_county(county: str, client: httpx.Client) -> dict:
    config = COUNTY_CONFIG[county]
    params = {
        'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,sale_type,market_value,assessed_value,po_market_value',
        'county': f'eq.{county}',
        'order': 'auction_date.desc',
        'limit': '5000',
    }
    r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS, params=params, timeout=120)
    if r.status_code >= 400:
        log.error(f'{county}: fetch failed {r.status_code}: {r.text[:200]}')
        return {'county': county, 'auctions': 0, 'bid_decisions_inserted': 0, 'errors': 1}

    rows = r.json()
    log.info(f'{county}: fetched {len(rows)} MCA rows')
    if not rows:
        return {'county': county, 'auctions': 0, 'bid_decisions_inserted': 0, 'errors': 0}

    # Check existing bid_decisions to avoid duplicates
    existing_cases = set()
    ex_params = {'select': 'case_number', 'county_slug': f'eq.{county}', 'limit': '5000'}
    rx = client.get(f'{BASE}/bid_decisions', headers=HEADERS, params=ex_params, timeout=60)
    if rx.status_code == 200:
        for rec in rx.json():
            existing_cases.add(rec['case_number'])
    log.info(f'{county}: {len(existing_cases)} existing bid_decisions')

    batch, total_inserted, errors = [], 0, 0
    for row in rows:
        if not row.get('case_number'):
            continue
        if row['case_number'] in existing_cases:
            continue
        try:
            batch.append(build_bid_decision(row, county, config))
        except Exception as e:
            log.warning(f'{county}: build error for {row.get("case_number")}: {e}')
            errors += 1

        if len(batch) >= 200:
            ins = client.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch), timeout=60)
            if ins.status_code >= 400:
                log.error(f'{county}: insert failed {ins.status_code}: {ins.text[:200]}')
                errors += 1
            else:
                total_inserted += len(batch)
                log.info(f'{county}: inserted {len(batch)} bid_decisions (running: {total_inserted})')
            batch = []

    if batch:
        ins = client.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch), timeout=60)
        if ins.status_code >= 400:
            log.error(f'{county}: insert failed {ins.status_code}: {ins.text[:200]}')
            errors += 1
        else:
            total_inserted += len(batch)

    log.info(f'{county}: DONE inserted={total_inserted} bid_decisions')
    return {'county': county, 'auctions': len(rows), 'bid_decisions_inserted': total_inserted, 'errors': errors}


def verify_county(county: str, client: httpx.Client) -> dict:
    r = client.post(f'{BASE}/rpc/pencil_dod_evaluate_county',
                    headers=HEADERS,
                    content=json.dumps({'p_county': county}),
                    timeout=60)
    if r.status_code == 200:
        ev = r.json()
        j = ev.get('J', {})
        log.info(f'{county}: J={j.get("metric")}% pass={j.get("pass")} detail={j.get("detail")}')
        return ev
    return {}


def main():
    parser = argparse.ArgumentParser(description='SHARD-9 J-Generator')
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument('--county', choices=SHARD9_COUNTIES)
    grp.add_argument('--all', action='store_true', dest='all_counties')
    args = parser.parse_args()

    counties = SHARD9_COUNTIES if args.all_counties else [args.county]
    results = []
    with httpx.Client(timeout=120) as client:
        for county in counties:
            log.info(f'Starting J-generator for {county}')
            res = run_for_county(county, client)
            results.append(res)
            ev = verify_county(county, client)
            res['evaluation'] = ev.get('J', {})

    print(json.dumps({'results': results}, indent=2))
    total_inserted = sum(r.get('bid_decisions_inserted', 0) for r in results)
    log.info(f'SHARD-9 J-generator complete: {total_inserted} bid_decisions total across {len(counties)} counties')


if __name__ == '__main__':
    main()
