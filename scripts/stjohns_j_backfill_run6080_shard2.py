#!/usr/bin/env python3
"""
St Johns County J (deal-thesis) backfill, continuation of
scripts/stjohns_j_backfill_run_letterJ_20260718.py for the last 2 gap cases.

Gold Standard shard-2 (nassau, st_johns), loop run 6080,
dispatch_id ffe1aa89-758e-42a2-8ac2-73ceeee9d290.

Both cases were previously blocked (E: no parcel_id/property_address). This
session's research workflow VERIFIED real parcel_id + property_address for
both via St. Johns County's official ArcGIS Parcel/Zoning REST services
(gis.sjcfl.us), independently re-checked by an adversarial refuter agent
before any write -- so they are no longer "we know nothing about this
property" ghost-success candidates. The remaining 4 st_johns J gaps
(CA22-1233, CA25-1470, CC25-0048, CC25-2919) stay BLOCKED: the same research
pass hit CAPTCHA/403-gated clerk search systems and found zero indexed data
for any of them.

Same formula/factors contract as the 2026-07-18 run (arv_source=
shapira_formula_stjohns_j_backfill_broker1_county_median, pipeline_version=
stjohns_j_backfill_v1) -- extends the existing convention rather than
introducing a new one. Both rows carry assessed_value=200000, the confirmed
placeholder default (not a sourced valuation, per the 07-18 script's finding
of an identical flat value across many rows) -- so it is excluded from the
arv calc exactly as before, falling back to opening_bid*1.4 (both real
recorded judgment amounts, not placeholders).
"""
import os
import json
import httpx

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json', 'Prefer': 'return=representation',
}

ELIGIBLE_CASES = ['CA26-0218', 'CA25-1404']
ARV_BASE = 347450  # Broker One May-2026 county median (same base as prior runs)
STUB_ASSESSED_VALUE = 200000  # confirmed placeholder default, not real -- must not feed arv

TIERED_REPAIRS = [(100000, 30000), (200000, 25000), (400000, 20000), (float('inf'), 15000)]


def tiered_repair(arv):
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return repair
    return 15000


def shapira_max_bid(arv, repairs):
    return (arv * 0.70) - repairs - 10000 - min(25000, 0.15 * arv)


def build(row):
    arv_base = ARV_BASE
    raw_mkt = row.get('market_value')
    raw_assessed = row.get('assessed_value')
    assessed = None if (raw_assessed and float(raw_assessed) == STUB_ASSESSED_VALUE) else raw_assessed
    mkt = raw_mkt or assessed
    opening = float(row.get('opening_bid') or 0)
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
    ratio = min(9.9999, max(-9.9999, max_bid / opening_f))
    factors = {
        'distress_location': {'score': 7.5, 'note': 'st_johns county FL — coastal, St Augustine area', 'honesty_marker': 'INFERRED'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type","foreclosure")} distress', 'honesty_marker': 'INFERRED'},
        'distress_owner': {'score': 7.0, 'note': 'judicial action filed', 'honesty_marker': 'INFERRED'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm', 'honesty_marker': 'INFERRED'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm — opening_bid*1.4 (real recorded judgment/opening amount), not per-parcel comp', 'honesty_marker': 'INFERRED'},
        'model': 'shapira_v14',
    }
    return {
        'case_number': row['case_number'], 'county_slug': 'st_johns',
        'parcel_id': row.get('parcel_id') or None, 'address': row.get('property_address'),
        'auction_date': row.get('auction_date'), 'arv': round(arv, 2), 'repairs': round(repairs, 2),
        'max_bid': round(max(max_bid, 0), 2), 'bid_judgment_ratio': round(ratio, 4), 'ml_score': ml_score,
        'factors': factors, 'recommendation': 'BID' if max_bid > 1000 else 'SKIP', 'confidence': 0.5,
        'arv_source': 'shapira_formula_stjohns_j_backfill_broker1_county_median',
        'pipeline_version': 'stjohns_j_backfill_v1',
    }


def main():
    with httpx.Client() as c:
        r = c.get(f'{BASE}/multi_county_auctions',
                   headers=HEADERS,
                   params={'select': 'case_number,parcel_id,property_address,auction_date,opening_bid,sale_type,market_value,assessed_value',
                           'county': 'eq.st_johns', 'case_number': f'in.({",".join(ELIGIBLE_CASES)})'},
                   timeout=30)
        r.raise_for_status()
        rows = r.json()
        print(f'fetched {len(rows)} rows for backfill')
        if len(rows) != len(ELIGIBLE_CASES):
            raise RuntimeError(f'fail-loud: expected {len(ELIGIBLE_CASES)} rows, got {len(rows)}')
        batch = [build(row) for row in rows]
        ins = c.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch), timeout=30)
        if ins.status_code >= 400:
            raise RuntimeError(f'insert failed {ins.status_code}: {ins.text[:300]}')
        inserted = ins.json()
        if len(inserted) != len(batch):
            raise RuntimeError(f'fail-loud: built={len(batch)} inserted={len(inserted)}')
        print(f'inserted {len(inserted)} bid_decisions')


if __name__ == '__main__':
    main()
