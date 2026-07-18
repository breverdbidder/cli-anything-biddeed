#!/usr/bin/env python3
"""
DeSoto County J-Generator: Bid Decisions via Shapira Formula.
Reuses the exact formula/factors contract from scripts/columbia_j_generator.py,
scoped to desoto only. ARV base sourced from Redfin DeSoto County median sale
price (3 months ending May 2026, $239K) — INFERRED, not VERIFIED (no per-parcel
comp data available for an 8-row county). Every factor carries an explicit
honesty_marker per existing columbia/shard9 pattern.
"""
import os
import json
import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('desoto-j-gen')

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

# Source: Redfin DeSoto County FL housing market page, median sale price over
# the 3 months ending May 2026 = $239,000 (INFERRED — county-level median, not
# a per-parcel comp; small-sample rural county, treat with caution).
CONFIG = {'arv': 239000, 'repair_factor': 0.12, 'location_score': 5.5}

TIERED_REPAIRS = [
    (100000, 30000), (200000, 25000), (400000, 20000), (float('inf'), 15000),
]


def tiered_repair(arv):
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return repair
    return 15000


def shapira_max_bid(arv, repairs):
    profit_reserve = min(25000, 0.15 * arv)
    return (arv * 0.70) - repairs - 10000 - profit_reserve


def build_bid_decision(row, county, config):
    arv_base = config['arv']
    opening = float(row.get('opening_bid') or 0)
    mkt = row.get('market_value') or row.get('po_market_value') or row.get('assessed_value')
    if mkt:
        arv = max(float(mkt), arv_base * 0.4)
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
        'distress_location': {'score': loc_score, 'note': f'{county} county FL — rural, Arcadia/Peace River corridor', 'honesty_marker': 'INFERRED'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type", "foreclosure")} distress', 'honesty_marker': 'INFERRED'},
        'distress_owner': {'score': 7.0, 'note': 'judicial action filed', 'honesty_marker': 'INFERRED'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm', 'honesty_marker': 'INFERRED'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm — county median (Redfin, 3mo ending May 2026), not per-parcel comp', 'honesty_marker': 'INFERRED'},
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
        'confidence': 0.5,
        'arv_source': 'shapira_formula_desoto_j_gen_redfin_county_median',
        'pipeline_version': 'desoto_j_gen_v1',
    }


def main():
    with httpx.Client() as client:
        params = {
            'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,sale_type,market_value,assessed_value',
            'county': 'ilike.*desoto*',
            'limit': '100',
        }
        r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS, params=params, timeout=60)
        r.raise_for_status()
        rows = r.json()
        log.info(f'desoto: fetched {len(rows)} MCA rows')

        ex = client.get(f'{BASE}/bid_decisions', headers=HEADERS,
                         params={'select': 'case_number', 'county_slug': 'eq.desoto', 'limit': '100'}, timeout=30)
        existing = {rec['case_number'] for rec in ex.json()} if ex.status_code == 200 else set()

        batch = []
        for row in rows:
            if not row.get('case_number') or row['case_number'] in existing:
                continue
            batch.append(build_bid_decision(row, 'desoto', CONFIG))

        if not batch:
            log.info('desoto: nothing to insert')
            return

        ins = client.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch), timeout=60)
        if ins.status_code >= 400:
            raise RuntimeError(f'insert failed {ins.status_code}: {ins.text[:300]}')
        log.info(f'desoto: inserted {len(batch)} bid_decisions')

        if len(batch) > 0 and ins.status_code >= 400:
            raise RuntimeError('Silent failure: batch built but insert failed')


if __name__ == '__main__':
    main()
