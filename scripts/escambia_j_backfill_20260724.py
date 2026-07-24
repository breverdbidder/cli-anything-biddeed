#!/usr/bin/env python3
"""
Escambia County J backfill (2026-07-24, ultracode fan-out session).

Extends scripts/escambia_j_backfill_20260710.py: same Shapira formula and
factors contract, but queries the CURRENT gap live from Postgres via the
Management API instead of relying on stale pre-staged /tmp JSON snapshots
(those files no longer exist / no longer reflect the live gap).

Gap definition matches pencil_dod_evaluate_county letter J exactly:
  base row set = multi_county_auctions WHERE lower(county)='escambia'
    AND (data_source <> 'propertyonion' OR tier1_authoritative=true)
  gap = base rows with NO bid_decisions row at all (has_bd=False) OR an
    incomplete bid_decisions row (missing arv/max_bid/ml_score/any factor key).

As of 2026-07-24 the live gap is 33 rows, ALL of which are missing a
bid_decisions row entirely (has_bd=False) and ALL of which have a real
assessed_value from the county tax roll — so all 33 are FIXABLE-NOW with
the existing Shapira-formula generator pattern, no fabrication needed.

ARV base: same Redfin Escambia County median sale price fallback used by
the 2026-07-10 backfill ($300K) — INFERRED, county-level not per-parcel,
only used when a row has neither market_value nor assessed_value (none of
the 33 gap rows hit this fallback; all have assessed_value).
"""
import os
import json
import httpx

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
ACCESS_TOKEN = os.environ['SUPABASE_ACCESS_TOKEN']
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json', 'Prefer': 'return=representation',
}
MGMT_URL = 'https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query'
MGMT_HEADERS = {'Authorization': f'Bearer {ACCESS_TOKEN}', 'Content-Type': 'application/json'}

ARV_BASE = 300000
TIERED_REPAIRS = [(100000, 30000), (200000, 25000), (400000, 20000), (float('inf'), 15000)]

GAP_SQL = """
WITH base AS (
  SELECT case_number, parcel_id, property_address, market_value, assessed_value,
         opening_bid, auction_date, data_source, sale_type
  FROM multi_county_auctions
  WHERE lower(county)='escambia'
    AND (data_source <> 'propertyonion' OR tier1_authoritative=true)
),
bd AS (
  SELECT case_number, arv, max_bid, ml_score, factors
  FROM bid_decisions
  WHERE case_number IN (SELECT case_number FROM base)
),
joined AS (
  SELECT b.*, d.arv, d.max_bid, d.ml_score, d.factors,
         (d.case_number IS NOT NULL) AS has_bd,
         (d.arv IS NOT NULL AND d.max_bid IS NOT NULL AND d.ml_score IS NOT NULL
          AND d.factors ? 'distress_location' AND d.factors ? 'distress_property'
          AND d.factors ? 'distress_owner' AND d.factors ? 'cma_distressed'
          AND d.factors ? 'cma_resale') AS complete
  FROM base b
  LEFT JOIN bd d ON d.case_number = b.case_number
)
SELECT case_number, parcel_id, property_address, market_value, assessed_value,
       opening_bid, auction_date, data_source, sale_type, has_bd, complete
FROM joined
WHERE NOT complete
ORDER BY auction_date;
"""


def fetch_gap():
    with httpx.Client(timeout=60) as c:
        r = c.post(MGMT_URL, headers=MGMT_HEADERS, content=json.dumps({'query': GAP_SQL}))
        if r.status_code >= 400:
            raise RuntimeError(f'gap query failed {r.status_code}: {r.text[:300]}')
        return r.json()


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
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm — county tax-roll assessed_value, not per-parcel comp', 'honesty_marker': 'INFERRED'},
        'model': 'shapira_v14',
    }
    return {
        'case_number': row['case_number'], 'county_slug': 'escambia',
        'parcel_id': row.get('parcel_id') or None, 'address': row.get('property_address'),
        'auction_date': row.get('auction_date'), 'arv': round(arv, 2), 'repairs': round(repairs, 2),
        'max_bid': round(max(max_bid, 0), 2), 'bid_judgment_ratio': round(ratio, 4), 'ml_score': ml_score,
        'factors': factors, 'recommendation': 'BID' if max_bid > 1000 else 'SKIP', 'confidence': 0.5,
        'arv_source': 'shapira_formula_escambia_j_backfill_20260724_assessed_value',
        'pipeline_version': 'escambia_j_backfill_v2_20260724',
    }


def main():
    gap = fetch_gap()
    print(f'live gap rows (letter J, escambia): {len(gap)}')
    if not gap:
        print('no gap rows found — nothing to do')
        return
    missing_no_bd = [r for r in gap if not r['has_bd']]
    print(f'  of which has_bd=False (no bid_decisions row at all): {len(missing_no_bd)}')
    if len(missing_no_bd) != len(gap):
        raise RuntimeError(
            f'FAIL-LOUD: {len(gap) - len(missing_no_bd)} gap rows already HAVE a bid_decisions '
            'row but are still incomplete (missing arv/max_bid/ml_score/factor keys) — this '
            'script only builds new rows via INSERT and would violate the unique constraint '
            'on case_number. These rows need an UPDATE-based fix, not covered here. Aborting.'
        )
    batch = [build(row) for row in gap]
    with httpx.Client(timeout=60) as c:
        total = 0
        for i in range(0, len(batch), 200):
            chunk = batch[i:i + 200]
            ins = c.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(chunk))
            if ins.status_code >= 400:
                raise RuntimeError(f'insert failed {ins.status_code}: {ins.text[:500]}')
            total += len(chunk)
        if total == 0 and len(batch) > 0:
            raise RuntimeError(
                f'FAIL-LOUD: parsed {len(batch)} candidate rows but wrote 0 — silent failure guard tripped.'
            )
        print(f'inserted {total} bid_decisions rows')


if __name__ == '__main__':
    main()
