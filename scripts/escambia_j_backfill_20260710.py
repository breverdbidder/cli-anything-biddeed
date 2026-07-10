#!/usr/bin/env python3
"""
Escambia County J backfill for the 69 tax-deed rows added by the
calendar-sweep-dark-counties dispatch mid-session (2026-08-05 .. 2026-12-02
batch) that had no bid_decisions yet. Same formula/factors contract as
scripts/shard9_j_generator.py, scoped to only the missing case numbers.
ARV base: Redfin Escambia County median sale price, Jan 2026 ($300K) —
INFERRED, county-level not per-parcel.
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
ARV_BASE = 300000
TIERED_REPAIRS = [(100000, 30000), (200000, 25000), (400000, 20000), (float('inf'), 15000)]


def tiered_repair(arv):
    for threshold, repair in TIERED_REPAIRS:
        if arv < threshold:
            return repair
    return 15000


def shapira_max_bid(arv, repairs):
    return (arv * 0.70) - repairs - 10000 - min(25000, 0.15 * arv)


def build(row):
    mkt = row.get('market_value') or row.get('assessed_value')
    opening = float(row.get('opening_bid') or 0)
    if mkt:
        arv = max(float(mkt), ARV_BASE * 0.4)
    elif opening > 1000:
        arv = opening * 1.4
    else:
        arv = ARV_BASE
    arv = max(arv, 50000)
    repairs = tiered_repair(arv)
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.75 if max_bid > 1000 else 0.38
    opening_f = opening if opening > 0 else arv * 0.5
    ratio = min(9.9999, max(-9.9999, max_bid / opening_f))
    factors = {
        'distress_location': {'score': 6.5, 'note': 'escambia county FL — Pensacola area', 'honesty_marker': 'INFERRED'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type","tax_deed")} distress', 'honesty_marker': 'INFERRED'},
        'distress_owner': {'score': 6.0, 'note': 'tax certificate application filed', 'honesty_marker': 'INFERRED'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm', 'honesty_marker': 'INFERRED'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm — county median (Redfin, Jan 2026), not per-parcel comp', 'honesty_marker': 'INFERRED'},
        'model': 'shapira_v14',
    }
    return {
        'case_number': row['case_number'], 'county_slug': 'escambia',
        'parcel_id': row.get('parcel_id') or None, 'address': row.get('property_address'),
        'auction_date': row.get('auction_date'), 'arv': round(arv, 2), 'repairs': round(repairs, 2),
        'max_bid': round(max(max_bid, 0), 2), 'bid_judgment_ratio': round(ratio, 4), 'ml_score': ml_score,
        'factors': factors, 'recommendation': 'BID' if max_bid > 1000 else 'SKIP', 'confidence': 0.5,
        'arv_source': 'shapira_formula_escambia_j_backfill_redfin_county_median',
        'pipeline_version': 'escambia_j_backfill_v1',
    }


def main():
    mca = json.load(open('/tmp/escambia_mca_full.json'))
    bd = json.load(open('/tmp/escambia_bd.json'))
    bd_cases = {r['case_number'] for r in bd}
    missing = [r for r in mca if r['case_number'] not in bd_cases]
    print(f'building {len(missing)} bid_decisions')
    batch = [build(row) for row in missing]
    with httpx.Client() as c:
        total = 0
        for i in range(0, len(batch), 200):
            chunk = batch[i:i+200]
            ins = c.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(chunk), timeout=60)
            if ins.status_code >= 400:
                raise RuntimeError(f'insert failed {ins.status_code}: {ins.text[:300]}')
            total += len(chunk)
        print(f'inserted {total} bid_decisions')


if __name__ == '__main__':
    main()
