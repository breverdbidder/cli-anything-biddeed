#!/usr/bin/env python3
"""
St Johns County J backfill for the 5 rows the calendar-sweep dispatch added
mid-session (2026-08-13 / 2026-07-16 foreclosure batch) that the existing
shapira_formula_loop65_j_gen pipeline hasn't picked up yet. Same formula/
factors contract, scoped to only the missing case numbers so it does not
touch or relabel the 44 rows loop65 already generated.
ARV base: conservative of two conflicting county-median sources found via
search (Redfin $513K vs Broker One $347K, May 2026) — using the lower
Broker One figure to avoid overstating value in a real bid recommendation.
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

MISSING_CASES = ['CA25-0128', 'CA25-0351', 'CA25-0475', 'CA25-1757', 'CA25-1779']
ARV_BASE = 347450  # Broker One May-2026 county median (conservative vs Redfin $513K)

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
    mkt = row.get('market_value') or row.get('assessed_value')
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
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm — county median (Broker One, May 2026), not per-parcel comp', 'honesty_marker': 'INFERRED'},
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
                           'county': 'eq.st_johns', 'case_number': f'in.({",".join(MISSING_CASES)})'},
                   timeout=30)
        r.raise_for_status()
        rows = r.json()
        print(f'fetched {len(rows)} rows for backfill')
        batch = [build(row) for row in rows]
        ins = c.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(batch), timeout=30)
        if ins.status_code >= 400:
            raise RuntimeError(f'insert failed {ins.status_code}: {ins.text[:300]}')
        print(f'inserted {len(batch)} bid_decisions')


if __name__ == '__main__':
    main()
