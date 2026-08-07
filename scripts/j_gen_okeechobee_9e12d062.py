#!/usr/bin/env python3
"""
Gold Standard shard-5 okeechobee (dispatch 9e12d062): Letter J bid_decisions
generation for the 14 fresh calendar_sweep_mca_v3 tax-deed rows (2026TD082-095)
that just gained parity_status='matched_clean' (C/D fix) and property_address/
lat/lon/assessed_value (I fix, partial -- these rows still lack zoning-district
linkage per the residual gap logged separately).

Reuses the EXACT Shapira formula/factors contract + okeechobee ARV baseline
($145,000, FL PA median) already proven in scripts/shard6_j_generator.py
(1580 existing okeechobee bid_decisions rows use this same arv_source).
Scoped ONLY to these 14 case_numbers -- does NOT touch the other ~66 already-
passing okeechobee bid_decisions rows (shard6_j_generator.py's --county mode
re-processes the whole county and would worsen the already-disclosed
bid_decisions row duplication issue for okeechobee).
"""
import os
import json
import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('okeechobee-j-gen-9e12d062')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

CONFIG = {'arv': 145000, 'repair_factor': 0.15, 'location_score': 6.5}
COUNTY = 'okeechobee'

TARGET_CASE_NUMBERS = [
    '2026TD082', '2026TD083', '2026TD084', '2026TD085', '2026TD086',
    '2026TD087', '2026TD088', '2026TD089', '2026TD090', '2026TD091',
    '2026TD092', '2026TD093', '2026TD094', '2026TD095',
]


def shapira_max_bid(arv: float, repairs: float) -> float:
    profit_reserve = min(25000, 0.15 * arv)
    return (arv * 0.70) - repairs - 10000 - profit_reserve


def build_bid_decision(row: dict) -> dict:
    arv_base = CONFIG['arv']
    opening = float(row.get('opening_bid') or 0)
    arv = opening * 1.35 if opening > 1000 else arv_base
    arv = max(arv, arv_base * 0.4)

    repairs = arv * CONFIG['repair_factor']
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.72 if max_bid > 0 else 0.38

    opening_f = opening if opening > 0 else arv * 0.5
    ratio = max_bid / opening_f if opening_f > 0 else 1.0
    ratio = min(9.9999, max(-9.9999, ratio))

    loc_score = CONFIG['location_score']
    factors = {
        'distress_location': {'score': loc_score, 'note': f'{COUNTY} county FL'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type", "tax_deed")} distress'},
        'distress_owner': {'score': 7.0, 'note': 'tax certificate foreclosure filed'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm'},
    }

    return {
        'case_number': row['case_number'],
        'county_slug': COUNTY,
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
        'pipeline_version': 'shard5_9e12d062_j_gen_v1',
    }


def main():
    client = httpx.Client(timeout=60)

    r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS, params={
        'county': f'eq.{COUNTY}',
        'case_number': f'in.({",".join(TARGET_CASE_NUMBERS)})',
        'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,sale_type',
    })
    r.raise_for_status()
    rows = r.json()
    log.info(f'{COUNTY}: fetched {len(rows)} target MCA rows')

    ex = client.get(f'{BASE}/bid_decisions', headers=HEADERS, params={
        'county_slug': f'eq.{COUNTY}',
        'case_number': f'in.({",".join(TARGET_CASE_NUMBERS)})',
        'select': 'case_number',
    })
    existing = {rec['case_number'] for rec in ex.json()} if ex.status_code == 200 else set()
    log.info(f'{COUNTY}: {len(existing)} of the 14 already have bid_decisions')

    records = [build_bid_decision(row) for row in rows if row['case_number'] not in existing]

    if not records:
        log.info(f'{COUNTY}: nothing to insert (all 14 already present)')
        print(json.dumps({'county': COUNTY, 'inserted': 0, 'already_present': len(existing)}))
        return

    r_ins = client.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(records))
    if r_ins.status_code not in (200, 201):
        raise RuntimeError(f'FAIL-LOUD: insert failed {r_ins.status_code}: {r_ins.text[:300]}')

    inserted = len(r_ins.json())
    if len(records) > 0 and inserted == 0:
        raise RuntimeError(f'FAIL-LOUD: built {len(records)} records but inserted=0')

    log.info(f'{COUNTY}: VERIFIED inserted={inserted} bid_decisions')
    print(json.dumps({'county': COUNTY, 'inserted': inserted, 'already_present': len(existing)}))


if __name__ == '__main__':
    main()
