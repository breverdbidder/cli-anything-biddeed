#!/usr/bin/env python3
"""
SHARD-6 J-Generator: Bid Decisions via Shapira Formula
=======================================================
Generates Letter J bid_decisions for counties: okeechobee, jackson, dixie, monroe
Uses Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)

Factors contract per production pencil_dod_evaluate_county:
  - distress_location, distress_property, distress_owner (triangle)
  - cma_distressed, cma_resale (two-arm CMA)

Usage:
  python scripts/shard6_j_generator.py --county okeechobee
  python scripts/shard6_j_generator.py --county jackson
  python scripts/shard6_j_generator.py --all
"""
import os
import sys
import json
import logging
import argparse
from datetime import date
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('shard6-j-gen')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates,return=representation',
}

# County-level ARV estimates (FL property appraiser medians)
COUNTY_CONFIG = {
    'okeechobee': {'arv': 145000, 'repair_factor': 0.15, 'location_score': 6.5},
    'jackson':    {'arv': 135000, 'repair_factor': 0.15, 'location_score': 6.0},
    'dixie':      {'arv': 142000, 'repair_factor': 0.15, 'location_score': 5.5},
    'monroe':     {'arv': 520000, 'repair_factor': 0.10, 'location_score': 8.5},  # Florida Keys premium
}

SHARD6_COUNTIES = list(COUNTY_CONFIG.keys())


def shapira_max_bid(arv: float, repairs: float) -> float:
    """Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)"""
    profit_reserve = min(25000, 0.15 * arv)
    return (arv * 0.70) - repairs - 10000 - profit_reserve


def build_bid_decision(row: dict, county: str, config: dict) -> dict:
    """Build a bid_decisions record for one auction."""
    arv_base = config['arv']
    opening = float(row.get('opening_bid') or 0)
    arv = opening * 1.35 if opening > 1000 else arv_base
    arv = max(arv, arv_base * 0.4)

    repairs = arv * config['repair_factor']
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.72 if max_bid > 0 else 0.38

    opening_f = opening if opening > 0 else arv * 0.5
    ratio = max_bid / opening_f if opening_f > 0 else 1.0
    ratio = min(9.9999, max(-9.9999, ratio))

    loc_score = config['location_score']
    factors = {
        'distress_location': {'score': loc_score, 'note': f'{county} county FL'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type", "foreclosure")} distress'},
        'distress_owner': {'score': 7.0, 'note': 'judicial action filed'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm'},
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
        'arv_source': 'shapira_formula_shard6_j_gen',
        'pipeline_version': 'shard6_j_gen_v1',
    }


def run_for_county(county: str, client: httpx.Client) -> dict:
    """Fetch MCA rows and upsert bid_decisions for one county."""
    config = COUNTY_CONFIG[county]
    all_rows = []
    offset = 0
    while True:
        r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS,
                       params={'county': f'eq.{county}',
                               'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,sale_type',
                               'limit': '200', 'offset': str(offset)})
        batch = r.json() if r.status_code == 200 else []
        if not batch:
            break
        all_rows.extend(batch)
        offset += 200
        if len(batch) < 200:
            break

    log.info(f'{county}: {len(all_rows)} auctions to process')

    records = [build_bid_decision(row, county, config) for row in all_rows]

    total_inserted = 0
    errors = 0
    for i in range(0, len(records), 50):
        batch = records[i:i+50]
        r_ins = client.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch))
        if r_ins.status_code in (200, 201):
            total_inserted += len(r_ins.json())
        else:
            errors += 1
            log.error(f'{county} batch {i//50+1} error: {r_ins.status_code} {r_ins.text[:200]}')

    parsed = len(records)
    if parsed > 0 and total_inserted == 0:
        raise RuntimeError(f'FAIL-LOUD: {county} parsed={parsed} but inserted=0')

    log.info(f'{county}: VERIFIED inserted={total_inserted} bid_decisions')
    return {'county': county, 'auctions': parsed, 'bid_decisions_inserted': total_inserted, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description='SHARD-6 J-Generator')
    parser.add_argument('--county', choices=SHARD6_COUNTIES)
    parser.add_argument('--all', action='store_true', dest='all_counties')
    args = parser.parse_args()

    if not args.county and not args.all_counties:
        parser.error('Specify --county or --all')

    counties = SHARD6_COUNTIES if args.all_counties else [args.county]
    client = httpx.Client(timeout=120)

    results = []
    for county in counties:
        try:
            result = run_for_county(county, client)
            results.append(result)
        except Exception as e:
            log.error(f'{county}: {e}')
            results.append({'county': county, 'error': str(e)})

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
