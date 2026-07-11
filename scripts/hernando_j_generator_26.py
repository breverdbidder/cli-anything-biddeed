#!/usr/bin/env python3
"""
HERNANDO J-Generator: bid_decisions backfill for the 26 case numbers that
never had a bid_decisions row at all.

Forked from scripts/putnam_j_generator.py (do not modify that shared file).
Scoped ONLY to the 26 hernando case_numbers that were missing a bid_decisions
row entirely -- the other 23 hernando cases already have complete rows and
are left untouched by this script.

Convention: reverse-engineered from the 23 pre-existing hernando
bid_decisions rows this session (verified via live query, not assumed):
  - Tax-deed (TD) cases:  arv = opening_bid * 1.5, repairs = $15,000 flat,
    max_bid = shapira(arv, repairs) if positive else arv * 0.2,
    ml_score = 0.5, confidence = 0.35, recommendation = 'REVIEW'.
  - Confirmed exact match against 10/10 clean pre-existing TD rows before
    this script was written (see session notes -- not re-derived here).
arv_source = 'INFERRED' (matches existing hernando convention -- no live
zip_market_stats coverage found for hernando zip codes 34601-34613/33523/34661
this session, confirmed via live query returning zero rows).

Uses Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)

Factors contract per production pencil_dod_evaluate_county:
  - distress_location, distress_property, distress_owner (triangle)
  - cma_distressed, cma_resale (two-arm CMA)

bid_decisions has NO unique constraint on case_number (only PK on id).
This script only targets the 26 case_numbers confirmed (via live GET) to
have ZERO existing bid_decisions rows -- straight POST, no PATCH branch
needed since there is nothing to update.

Usage:
  python scripts/hernando_j_generator_26.py
"""
import os
import sys
import json
import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('hernando-j-gen-26')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

TARGET_CASE_NUMBERS = [
    '2026-041TD', '2026-059TD', '2026-060TD', '2026-049TD', '2026-042TD',
    '2026-051TD', '2026-048TD', '2026-045TD', '2026-046TD', '2026-058TD',
    '2026-043TD', '2026-034TD', '2026-036TD', '2026-039TD', '2026-037TD',
    '2026-053TD', '2026-040TD', '2026-056TD', '2026-033TD', '2026-061TD',
    '2026-050TD', '2026-064TD', '2026-055TD', '2026-027TD', '2026-035TD',
    '2026-044TD',
]

COUNTY = 'hernando'
REPAIRS_FLAT = 15000.0
ARV_MULTIPLIER = 1.5
LOCATION_SCORE = 5.0


def shapira_max_bid(arv: float, repairs: float) -> float:
    """Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)"""
    profit_reserve = min(25000, 0.15 * arv)
    return (arv * 0.70) - repairs - 10000 - profit_reserve


def build_bid_decision(row: dict) -> dict:
    """Build a bid_decisions record for one hernando TD auction, matching
    the exact convention verified against the 23 pre-existing hernando rows."""
    opening = float(row.get('opening_bid') or 0)
    arv = opening * ARV_MULTIPLIER if opening > 0 else 0.0
    repairs = REPAIRS_FLAT

    shapira = shapira_max_bid(arv, repairs)
    max_bid = shapira if shapira > 0 else arv * 0.2
    max_bid = max(max_bid, 0)

    ml_score = 0.5

    opening_f = opening if opening > 0 else arv * 0.5
    ratio = max_bid / opening_f if opening_f > 0 else None
    ratio = min(9.9999, max(-9.9999, ratio)) if ratio is not None else None

    factors = {
        'distress_location': {'score': LOCATION_SCORE, 'note': f'{COUNTY} county FL'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type", "tax_deed")} distress'},
        'distress_owner': {'score': 7.0, 'note': 'tax deed application filed'},
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
        'max_bid': round(max_bid, 2),
        'bid_judgment_ratio': round(ratio, 4) if ratio is not None else None,
        'ml_score': ml_score,
        'factors': factors,
        'recommendation': 'REVIEW',
        'confidence': 0.35,
        'arv_source': 'INFERRED',
        'pipeline_version': 'hernando_j_gen_26_v1',
    }


def fetch_target_auctions(client: httpx.Client) -> list:
    r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS,
                    params={'county': f'eq.{COUNTY}',
                            'case_number': f'in.({",".join(TARGET_CASE_NUMBERS)})',
                            'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,sale_type'})
    if r.status_code != 200:
        raise RuntimeError(f'FAIL-LOUD: fetch auctions failed {r.status_code} {r.text[:300]}')
    return r.json()


def fetch_existing_case_ids(client: httpx.Client) -> set:
    """Confirm none of the 26 targets already have a bid_decisions row
    (defensive re-check at execution time -- state may have shifted)."""
    r = client.get(f'{BASE}/bid_decisions', headers=HEADERS,
                    params={'case_number': f'in.({",".join(TARGET_CASE_NUMBERS)})',
                            'select': 'id,case_number'})
    if r.status_code != 200:
        raise RuntimeError(f'FAIL-LOUD: fetch existing bid_decisions failed {r.status_code} {r.text[:300]}')
    return {rec['case_number'] for rec in r.json()}


def run() -> dict:
    client = httpx.Client(timeout=120)
    all_rows = fetch_target_auctions(client)
    log.info(f'{COUNTY}: {len(all_rows)} of {len(TARGET_CASE_NUMBERS)} target auctions found')

    existing = fetch_existing_case_ids(client)
    if existing:
        log.warning(f'{COUNTY}: {len(existing)} target case_numbers already have a bid_decisions row -- skipping those: {sorted(existing)}')

    to_process = [row for row in all_rows if row['case_number'] not in existing]
    records = [build_bid_decision(row) for row in to_process]

    total_inserted = 0
    errors = 0
    insert_headers = dict(HEADERS)
    insert_headers['Prefer'] = 'return=representation'
    for i in range(0, len(records), 50):
        batch = records[i:i + 50]
        r_ins = client.post(f'{BASE}/bid_decisions', headers=insert_headers, content=json.dumps(batch))
        if r_ins.status_code in (200, 201):
            total_inserted += len(r_ins.json())
        else:
            errors += 1
            log.error(f'{COUNTY} insert batch {i // 50 + 1} error: {r_ins.status_code} {r_ins.text[:300]}')

    parsed = len(records)
    if parsed > 0 and total_inserted == 0:
        raise RuntimeError(f'FAIL-LOUD: {COUNTY} parsed={parsed} but inserted=0')

    missing_from_mca = sorted(set(TARGET_CASE_NUMBERS) - {row['case_number'] for row in all_rows})
    if missing_from_mca:
        log.warning(f'{COUNTY}: {len(missing_from_mca)} target case_numbers not found in multi_county_auctions: {missing_from_mca}')

    log.info(f'{COUNTY}: VERIFIED inserted={total_inserted} (errors={errors})')
    return {
        'county': COUNTY,
        'targets': len(TARGET_CASE_NUMBERS),
        'found_in_mca': len(all_rows),
        'already_had_bid_decision': len(existing),
        'bid_decisions_inserted': total_inserted,
        'errors': errors,
        'missing_from_mca': missing_from_mca,
    }


def main():
    result = run()
    print(json.dumps([result], indent=2))


if __name__ == '__main__':
    main()
