#!/usr/bin/env python3
"""
HERNANDO J-Generator (19 FL GIO rows): bid_decisions backfill for the 19
tax_deed case_numbers enriched by yesterday's E-fix
(scripts/hernando_e_taxdeed_ajax_arcgis_fix.py, dispatch 2026-08-15, commit
2f7938f9). Those 19 rows now carry real market_value from FL GIO Statewide
Cadastral (CER_JUST_VALUE), which is a strictly better ARV source than the
opening_bid*1.5 heuristic used by scripts/hernando_j_generator_26.py for the
other 26 hernando rows (none of which had real market_value at insert time).

Forked from scripts/hernando_j_generator_26.py's structure (same county-
scoped generator pattern, same FAIL-LOUD guard, same defensive
already-exists re-check). NOT a reuse of that script verbatim -- it hardcodes
a different TARGET list and uses a different ARV source/formula, matching the
precedent set in supabase/migrations/20260812083000_gold_standard_shard3_
holmes_eij_new_row_enrichment.sql for real-FL-GIO-sourced ARV
(arv_source='fl_gio_cadastral_jv', cma_distressed = arv * 0.85).

Uses Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)

Factors contract per production pencil_dod_evaluate_county (triangle +
two-arm CMA): distress_location, distress_property, distress_owner,
cma_distressed, cma_resale.

bid_decisions has NO unique constraint on case_number (only PK on id).
This script targets the 19 case_numbers confirmed (via live GET) to have
ZERO existing bid_decisions rows -- straight POST, no PATCH branch needed.

Usage:
  python scripts/hernando_j_generator_19_fl_gio.py
"""
import os
import sys
import json
import logging
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger('hernando-j-gen-19-flgio')

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

TARGET_CASE_NUMBERS = [
    '2026-077TD', '2026-115TD', '2026-066TD', '2026-100TD', '2026-141TD',
    '2026-140TD', '2026-068TD', '2026-069TD', '2026-070TD', '2026-071TD',
    '2026-073TD', '2026-078TD', '2026-079TD', '2026-091TD', '2026-067TD',
    '2026-072TD', '2026-074TD', '2026-114TD', '2026-095TD',
]

COUNTY = 'hernando'
REPAIRS_FLAT = 15000.0
DISPATCH_ID = '3eefe79f'


def shapira_max_bid(arv: float, repairs: float) -> float:
    """Shapira Formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)"""
    profit_reserve = min(25000, 0.15 * arv)
    return (arv * 0.70) - repairs - 10000 - profit_reserve


def build_bid_decision(row: dict) -> dict:
    """Build a bid_decisions record for one hernando TD auction, using real
    FL GIO market_value as ARV (strictly better than the opening_bid*1.5
    heuristic since this is verified assessor cadastral data, not a proxy)."""
    arv = float(row['market_value'])
    opening = float(row.get('opening_bid') or 0)
    repairs = REPAIRS_FLAT

    shapira = shapira_max_bid(arv, repairs)
    max_bid = shapira if shapira > 0 else arv * 0.2
    max_bid = max(max_bid, 0)

    ml_score = 0.55

    opening_f = opening if opening > 0 else arv * 0.5
    ratio = max_bid / opening_f if opening_f > 0 else None
    ratio = min(9.9999, max(-9.9999, ratio)) if ratio is not None else None

    factors = {
        'distress_location': 0.55,
        'distress_property': 0.50,
        'distress_owner': 0.55,
        'cma_distressed': round(arv * 0.85, 2),
        'cma_resale': round(arv, 2),
    }

    return {
        'case_number': row['case_number'],
        'county_slug': COUNTY,
        'parcel_id': row.get('parcel_id') or None,
        'address': row.get('property_address'),
        'auction_date': row.get('auction_date'),
        'arv': round(arv, 2),
        'repairs': round(repairs, 2),
        'repair_estimate': round(repairs, 2),
        'max_bid': round(max_bid, 2),
        'bid_judgment_ratio': round(ratio, 4) if ratio is not None else None,
        'ml_score': ml_score,
        'factors': factors,
        'recommendation': 'REVIEW',
        'confidence': 0.55,
        'arv_source': 'fl_gio_cadastral_jv',
        'pipeline_version': f'hernando_j_gen_19_flgio_{DISPATCH_ID}',
    }


def fetch_target_auctions(client: httpx.Client) -> list:
    r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS,
                    params={'county': f'eq.{COUNTY}',
                            'case_number': f'in.({",".join(TARGET_CASE_NUMBERS)})',
                            'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,market_value,sale_type'})
    if r.status_code != 200:
        raise RuntimeError(f'FAIL-LOUD: fetch auctions failed {r.status_code} {r.text[:300]}')
    return r.json()


def fetch_existing_case_ids(client: httpx.Client) -> set:
    """Defensive re-check at execution time -- confirm none of the 19
    targets already have a bid_decisions row (state may have shifted)."""
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

    missing_market_value = [row['case_number'] for row in all_rows if not row.get('market_value')]
    if missing_market_value:
        raise RuntimeError(f'FAIL-LOUD: {COUNTY} {len(missing_market_value)} target rows missing market_value, refusing to fabricate ARV: {missing_market_value}')

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
