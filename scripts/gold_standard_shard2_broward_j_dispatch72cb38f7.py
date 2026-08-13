#!/usr/bin/env python3
"""Broward County J backfill, GOLD STANDARD shard-2, dispatch 72cb38f7.

Same Shapira-formula bid_decisions generator contract already used and
proven across many prior counties (see scripts/highlands_j_bid_decisions_backfill.py,
scripts/escambia_j_backfill_20260724.py, scripts/okaloosa_bid_decisions_backfill.py,
scripts/shard11_j_generator.py) — this does NOT touch cron 109 /
gen_valuations_comps_batch / cron 111 / 115 / gold_standard_loop-* jobs, it
replicates their per-case output shape for the specific broward case_numbers
that are still missing a bid_decisions row.

Gap definition matches pencil_dod_evaluate_county letter J exactly:
  base row set = multi_county_auctions WHERE lower(county)='broward'
    AND (data_source <> 'propertyonion' OR tier1_authoritative=true)
  gap = base rows with NO bid_decisions row (has_bd=False) OR an incomplete
    one (missing arv/max_bid/ml_score/any of the 5 factors keys)

Confirmed live this session via the exact query below: 44 gap rows, ALL 44
with has_bd=False (zero partial/incomplete rows) — this script therefore
only INSERTs, matching the highlands/escambia script's fail-loud guard: if
any gap row already HAS a bid_decisions row when re-queried fresh at run
time (i.e. someone else's fix landed since this session's measurement), it
is routed to an UPDATE instead of erroring hard, and logged which path was
taken per case_number.

ARV: uses this row's real market_value/assessed_value from
multi_county_auctions when present (19 of the 44 gap rows have one — real
BCPA figures already ingested on the row). For the remaining 25 rows (no
market_value, no assessed_value, no opening_bid — confirmed live: zero of
the 25 have a usable opening_bid either), falls back to a real Broward
County-wide median, queried live this session:
  SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY market_value)
  FROM multi_county_auctions WHERE lower(county)='broward'
  -> median_market = $260,540 (n=9,793 rows with a real market_value)
This is a real, live-queried county-wide statistic, not an invented
constant — documented same as the highlands script's county-median
fallback pattern, just grounded in an actual DB aggregate instead of an
eyeballed figure.

The two distress-triangle scores and both CMA arms are formula-derived
(Shapira v14), not per-parcel comps — every such field is tagged
honesty_marker: INFERRED, matching the established contract used by every
other county's J-backfill script.

Usage:
  python3 scripts/gold_standard_shard2_broward_j_dispatch72cb38f7.py            # dry-run
  python3 scripts/gold_standard_shard2_broward_j_dispatch72cb38f7.py --apply    # write

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN
"""
import json
import os
import sys

import httpx

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
ACCESS_TOKEN = os.environ['SUPABASE_ACCESS_TOKEN']
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json', 'Prefer': 'return=representation',
}
MGMT_URL = 'https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query'
MGMT_HEADERS = {'Authorization': f'Bearer {ACCESS_TOKEN}', 'Content-Type': 'application/json'}

# Broward County-wide median market_value, queried LIVE this session
# (percentile_cont(0.5) over 9,793 real multi_county_auctions.market_value
# rows for lower(county)='broward'). Used ONLY when a gap row has none of:
# market_value, assessed_value, opening_bid>$1000. Real aggregate, not an
# invented constant.
ARV_BASE = 260540
TIERED_REPAIRS = [(100000, 30000), (200000, 25000), (400000, 20000), (float('inf'), 15000)]

GAP_SQL = """
WITH base AS (
  SELECT case_number, parcel_id, property_address, market_value, assessed_value,
         opening_bid, auction_date, data_source, sale_type
  FROM multi_county_auctions
  WHERE lower(county)='broward'
    AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
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
        arv_source = 'shapira_formula_broward_j_backfill_bcpa_assessed_value'
    elif opening > 1000:
        arv = opening * 1.4
        arv_source = 'shapira_formula_broward_j_backfill_opening_bid_multiple'
    else:
        arv = ARV_BASE
        arv_source = 'shapira_formula_broward_j_backfill_county_median_fallback'
    arv = max(arv, 50000)
    repairs = tiered_repair(arv)
    max_bid = shapira_max_bid(arv, repairs)
    ml_score = 0.75 if max_bid > 1000 else 0.38
    opening_f = opening if opening > 0 else arv * 0.5
    ratio = min(9.9999, max(-9.9999, max_bid / opening_f))
    factors = {
        'distress_location': {'score': 6.0, 'note': 'broward county FL — Fort Lauderdale/Hollywood/Pompano metro area', 'honesty_marker': 'INFERRED'},
        'distress_property': {'score': 5.0, 'note': f'{row.get("sale_type", "foreclosure")} distress', 'honesty_marker': 'INFERRED'},
        'distress_owner': {'score': 6.0, 'note': 'foreclosure/tax certificate filed', 'honesty_marker': 'INFERRED'},
        'cma_distressed': {'value': round(arv * 0.85, 2), 'note': 'distressed comp arm', 'honesty_marker': 'INFERRED'},
        'cma_resale': {'value': round(arv, 2), 'note': 'retail resale arm — BCPA assessed/market value where available, else live-queried county median fallback', 'honesty_marker': 'INFERRED'},
        'model': 'shapira_v14',
    }
    return {
        'case_number': row['case_number'], 'county_slug': 'broward',
        'parcel_id': row.get('parcel_id') or None, 'address': row.get('property_address'),
        'auction_date': row.get('auction_date'), 'arv': round(arv, 2), 'repairs': round(repairs, 2),
        'max_bid': round(max(max_bid, 0), 2), 'bid_judgment_ratio': round(ratio, 4), 'ml_score': ml_score,
        'factors': factors, 'recommendation': 'BID' if max_bid > 1000 else 'SKIP', 'confidence': 0.5,
        'arv_source': arv_source,
        'pipeline_version': 'broward_j_backfill_v1_shard2_72cb38f7',
    }


def main():
    apply = '--apply' in sys.argv
    gap = fetch_gap()
    print(f'live gap rows (letter J, broward): {len(gap)}')
    if not gap:
        print('no gap rows found — nothing to do')
        return

    missing_no_bd = [r for r in gap if not r['has_bd']]
    partial_has_bd = [r for r in gap if r['has_bd']]
    print(f'  has_bd=False (no bid_decisions row at all): {len(missing_no_bd)} -> INSERT path')
    print(f'  has_bd=True (partial/incomplete row already exists): {len(partial_has_bd)} -> UPDATE path')

    insert_batch = [build(row) for row in missing_no_bd]
    update_batch = [build(row) for row in partial_has_bd]
    have_real_value = sum(1 for r in gap if r.get('market_value') or r.get('assessed_value'))
    print(f'  {have_real_value} / {len(gap)} rows have a real BCPA assessed_value/market_value (ARV grounded in real data)')

    if not apply:
        print('DRY RUN (no --apply flag). No DB writes performed.')
        print(json.dumps(insert_batch[:2], indent=2, default=str))
        return

    total_inserted, total_updated = 0, 0
    with httpx.Client(timeout=60) as c:
        for i in range(0, len(insert_batch), 200):
            chunk = insert_batch[i:i + 200]
            if not chunk:
                continue
            ins = c.post(f'{BASE}/bid_decisions', headers=HEADERS, content=json.dumps(chunk))
            if ins.status_code >= 400:
                raise RuntimeError(f'insert failed {ins.status_code}: {ins.text[:500]}')
            total_inserted += len(chunk)

        for row in update_batch:
            case_number = row['case_number']
            upd = c.patch(
                f'{BASE}/bid_decisions',
                headers=HEADERS,
                params={'case_number': f'eq.{case_number}'},
                content=json.dumps(row),
            )
            if upd.status_code >= 400:
                raise RuntimeError(f'update failed for {case_number} {upd.status_code}: {upd.text[:500]}')
            total_updated += 1
            print(f'  UPDATE path: {case_number}')

        if (total_inserted + total_updated) == 0 and len(gap) > 0:
            raise RuntimeError(
                f'FAIL-LOUD: parsed {len(gap)} candidate rows but wrote 0 — silent failure guard tripped.'
            )
        print(f'inserted {total_inserted} bid_decisions rows, updated {total_updated} bid_decisions rows')


if __name__ == '__main__':
    main()
