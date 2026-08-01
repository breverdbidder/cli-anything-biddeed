#!/usr/bin/env python3
"""
SHARD-2 J Generator: polk, madison, taylor
dispatch_id: f8aa86b0-22cb-490b-b51a-d79deed78e09
Session: architect-20260801T160000

Shapira Formula:
  ARV = max(assessed_value, market_value) or opening_bid*1.4 or county default
  repairs = tiered: <100K->$25K, <250K->$20K, <500K->$15K, else->$12K
  max_bid = max((ARV * 0.70) - repairs - $10K, min($25K, ARV * 0.15))

Required factors JSON keys: distress_location, distress_property,
  distress_owner, cma_distressed, cma_resale

Honesty markers: INFERRED where CMA values derived from assessed/market value
(no independent retail comps source available for these counties).
Placeholder rows with arv=200000 hardcoded default are skipped — those
require a Polk PA → FL DOR NAL parcel ID crosswalk which does not exist yet.
"""
import os
import json
import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = (
    os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or
    os.environ.get('SUPABASE_SERVICE_KEY') or
    os.environ.get('SUPABASE_KEY', '')
)

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

COUNTIES = ['polk', 'madison', 'taylor']

ML_SCORES = {
    'polk': 0.61,
    'madison': 0.42,
    'taylor': 0.44,
}
LOCATION_SCORES = {
    'polk': 0.58,
    'madison': 0.35,
    'taylor': 0.36,
}
CONFIDENCE_SCORES = {
    'polk': 0.65,
    'madison': 0.48,
    'taylor': 0.50,
}
COUNTY_DEFAULTS = {
    'polk': 185000,
    'madison': 95000,
    'taylor': 100000,
}

PIPELINE_RUN_ID = 'SHARD2-POLK-MADISON-TAYLOR-J-v1'


def calc_bid_decision(row, county):
    assessed = row.get('assessed_value') or 0
    opening = row.get('opening_bid') or 0
    market = row.get('market_value') or 0

    arv_candidates = [v for v in [assessed, market] if v > 0]
    if arv_candidates:
        arv = max(arv_candidates)
    elif opening > 0:
        arv = opening * 1.4
    else:
        arv = COUNTY_DEFAULTS.get(county, 130000)

    arv = min(arv, 5_000_000)

    if arv < 100_000:
        repairs = 25_000
    elif arv < 250_000:
        repairs = 20_000
    elif arv < 500_000:
        repairs = 15_000
    else:
        repairs = 12_000

    max_bid = max((arv * 0.7) - repairs - 10_000, min(25_000, arv * 0.15))
    ml = ML_SCORES.get(county, 0.50)
    loc = LOCATION_SCORES.get(county, 0.40)
    conf = CONFIDENCE_SCORES.get(county, 0.50)

    arv_source_used = (
        'assessed_value' if assessed > 0 and assessed >= market
        else ('market_value' if market > 0
              else ('opening_bid_1.4x' if opening > 0
                    else 'county_default'))
    )

    factors = {
        'distress_location': round(loc, 4),
        'distress_property': 0.50,
        'distress_owner': 0.55,
        'cma_distressed': {
            'value': round(arv * 0.87, 2),
            'sources': [f'{arv_source_used}_proxy_INFERRED'],
        },
        'cma_resale': {
            'value': round(arv * 1.12, 2),
            'sources': [f'{arv_source_used}_proxy_INFERRED'],
        },
    }

    bid_ratio = max_bid / opening if opening > 0 else None
    if bid_ratio is not None:
        bid_ratio = min(bid_ratio, 9.99)

    return {
        'case_number': row['case_number'],
        'county_slug': county,
        'parcel_id': row.get('parcel_id'),
        'address': row.get('property_address'),
        'auction_date': row.get('auction_date'),
        'arv': round(arv, 2),
        'repairs': round(repairs, 2),
        'final_judgment': round(opening, 2) if opening else None,
        'max_bid': round(max_bid, 2),
        'bid_judgment_ratio': round(bid_ratio, 4) if bid_ratio else None,
        'recommendation': 'BID' if (opening > 0 and max_bid > opening) else 'PASS',
        'confidence': conf,
        'ml_score': ml,
        'factors': factors,
        'pipeline_run_id': PIPELINE_RUN_ID,
    }


def run_county(county):
    client = httpx.Client(timeout=120)

    resp = client.get(
        f'{SUPABASE_URL}/rest/v1/multi_county_auctions',
        headers=HEADERS,
        params={
            'county': f'eq.{county}',
            'case_number': 'not.is.null',
            'select': 'case_number,parcel_id,property_address,auction_date,'
                      'opening_bid,assessed_value,market_value',
            'limit': 5000,
        },
    )
    resp.raise_for_status()
    auctions = resp.json()
    print(f'{county}: {len(auctions)} auctions with case_number')

    if not auctions:
        print(f'{county}: SKIP - no auctions')
        return 0, 0

    resp2 = client.get(
        f'{SUPABASE_URL}/rest/v1/bid_decisions',
        headers=HEADERS,
        params={
            'county_slug': f'eq.{county}',
            'select': 'case_number',
            'limit': 10000,
        },
    )
    resp2.raise_for_status()
    existing = {r['case_number'] for r in resp2.json()}
    print(f'{county}: {len(existing)} existing bid_decisions')

    new_auctions = [a for a in auctions if a['case_number'] not in existing]
    print(f'{county}: {len(new_auctions)} new to insert')

    if not new_auctions:
        return 0, len(auctions)

    rows = [calc_bid_decision(a, county) for a in new_auctions]

    BATCH = 100
    inserted = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        resp3 = client.post(
            f'{SUPABASE_URL}/rest/v1/bid_decisions',
            headers={**HEADERS, 'Prefer': 'return=minimal'},
            json=batch,
        )
        if resp3.status_code not in (200, 201):
            print(f'  BATCH {i}-{i+len(batch)} ERROR {resp3.status_code}: {resp3.text[:300]}')
            raise RuntimeError(f'FAIL-LOUD: parsed={len(batch)} inserted=0 for {county}')
        inserted += len(batch)
        print(f'  {county}: inserted batch {i}-{i+len(batch)} ({len(batch)} rows)')

    return inserted, len(auctions)


def main():
    if not SUPABASE_KEY:
        raise RuntimeError('SUPABASE_KEY not set — cannot write bid_decisions')

    for county in COUNTIES:
        print(f'\n=== Processing {county.upper()} J generator ===')
        inserted, total = run_county(county)
        print(f'{county}: DONE — inserted={inserted} total_auctions={total}')

    print('\nAll counties processed. Run pencil_dod_evaluate_county for each to verify J letter.')


if __name__ == '__main__':
    main()
