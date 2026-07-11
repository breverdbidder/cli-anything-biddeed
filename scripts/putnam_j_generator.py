#!/usr/bin/env python3
"""
PUTNAM J-Generator: Bid Decisions via Shapira Formula
======================================================
Forked from scripts/shard6_j_generator.py (do not modify the shared shard6
file -- other counties may still need it). This fork is scoped to putnam only.

Uses Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)

Factors contract per production pencil_dod_evaluate_county:
  - distress_location, distress_property, distress_owner (triangle)
  - cma_distressed, cma_resale (two-arm CMA)

ARV base for putnam ($155,000): INFERRED -- no live comp/market-stat data
was found in zip_market_stats for putnam's zip codes this session. Putnam
is rural north-central Florida (Palatka area), comparable to other rural
north FL counties already estimated in this campaign (okeechobee $145k,
jackson $135k, dixie $142k). $155,000 is a documented estimate, NOT a
live-sourced median -- matches the existing convention for this letter
across the campaign.

bid_decisions has NO unique constraint on case_number (only PK on id --
verified via pg_constraint this session). Blind POST with
Prefer:resolution=merge-duplicates would merge on the PK (always new),
creating duplicate case_number rows. This script GETs existing rows by
case_number first and PATCHes them; only case_numbers with zero existing
rows are POSTed. This avoids adding to the 9 pre-existing duplicate
case_numbers already in the table (not created by this script).

Usage:
  python scripts/putnam_j_generator.py
"""
import os
import sys
import json
import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('putnam-j-gen')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

# County-level ARV estimate (INFERRED -- see module docstring)
COUNTY_CONFIG = {
    'putnam': {'arv': 155000, 'repair_factor': 0.15, 'location_score': 5.0},
}


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
        'arv_source': 'shapira_formula_putnam_j_gen_INFERRED',
        'pipeline_version': 'putnam_j_gen_v1',
    }


def fetch_all_auctions(county: str, client: httpx.Client) -> list:
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
    return all_rows


def fetch_existing_case_ids(county: str, client: httpx.Client) -> dict:
    """Map case_number -> first bid_decisions.id (for PATCH targeting).
    Only the first row per case_number is patched; pre-existing duplicate
    rows (9 case_numbers with 2 rows each, confirmed via pg query) are left
    as-is -- not created by this script, out of scope to dedupe them."""
    mapping = {}
    offset = 0
    while True:
        r = client.get(f'{BASE}/bid_decisions', headers=HEADERS,
                       params={'county_slug': f'eq.{county}',
                               'select': 'id,case_number',
                               'order': 'id.asc',
                               'limit': '500', 'offset': str(offset)})
        batch = r.json() if r.status_code == 200 else []
        if not batch:
            break
        for rec in batch:
            cn = rec['case_number']
            if cn not in mapping:
                mapping[cn] = rec['id']
        offset += 500
        if len(batch) < 500:
            break
    return mapping


def run_for_county(county: str, client: httpx.Client) -> dict:
    config = COUNTY_CONFIG[county]
    all_rows = fetch_all_auctions(county, client)
    log.info(f'{county}: {len(all_rows)} auctions to process')

    existing = fetch_existing_case_ids(county, client)
    log.info(f'{county}: {len(existing)} distinct case_numbers already have a bid_decisions row')

    records = [build_bid_decision(row, county, config) for row in all_rows]

    to_insert = [rec for rec in records if rec['case_number'] not in existing]
    to_update = [rec for rec in records if rec['case_number'] in existing]

    total_inserted = 0
    total_updated = 0
    errors = 0

    insert_headers = dict(HEADERS)
    insert_headers['Prefer'] = 'return=representation'
    for i in range(0, len(to_insert), 50):
        batch = to_insert[i:i+50]
        r_ins = client.post(f'{BASE}/bid_decisions', headers=insert_headers, content=json.dumps(batch))
        if r_ins.status_code in (200, 201):
            total_inserted += len(r_ins.json())
        else:
            errors += 1
            log.error(f'{county} insert batch {i//50+1} error: {r_ins.status_code} {r_ins.text[:300]}')

    update_headers = dict(HEADERS)
    update_headers['Prefer'] = 'return=representation'
    for rec in to_update:
        rec_id = existing[rec['case_number']]
        body = {k: v for k, v in rec.items() if k != 'case_number'}
        r_upd = client.patch(f'{BASE}/bid_decisions', headers=update_headers,
                             params={'id': f'eq.{rec_id}'}, content=json.dumps(body))
        if r_upd.status_code in (200, 201):
            result = r_upd.json()
            if result:
                total_updated += 1
            else:
                errors += 1
                log.error(f'{county} update id={rec_id} returned empty result')
        else:
            errors += 1
            log.error(f'{county} update id={rec_id} error: {r_upd.status_code} {r_upd.text[:300]}')

    parsed = len(records)
    if parsed > 0 and total_inserted == 0 and total_updated == 0:
        raise RuntimeError(f'FAIL-LOUD: {county} parsed={parsed} but inserted=0 and updated=0')

    log.info(f'{county}: VERIFIED inserted={total_inserted} updated={total_updated} bid_decisions (errors={errors})')
    return {
        'county': county,
        'auctions': parsed,
        'bid_decisions_inserted': total_inserted,
        'bid_decisions_updated': total_updated,
        'errors': errors,
    }


def main():
    client = httpx.Client(timeout=120)
    result = run_for_county('putnam', client)
    print(json.dumps([result], indent=2))


if __name__ == '__main__':
    main()
