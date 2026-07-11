#!/usr/bin/env python3
"""GOLD STANDARD shard6, county=polk -- J-letter gap backfill.

Targets ONLY the 76 in-scope polk rows lacking a qualifying bid_decisions row
(VERIFIED this session):
  SELECT mca.data_source, count(*) FROM multi_county_auctions mca
  WHERE lower(mca.county)='polk' AND (data_source<>'propertyonion' OR tier1_authoritative)
    AND NOT EXISTS (SELECT 1 FROM bid_decisions bd WHERE bd.case_number=mca.case_number
      AND bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL
      AND bd.factors ? 'distress_location' AND bd.factors ? 'distress_property'
      AND bd.factors ? 'distress_owner' AND bd.factors ? 'cma_distressed'
      AND bd.factors ? 'cma_resale')
  GROUP BY 1;
  -> calendar_sweep_mca_v3=63, realforeclose=13  (total 76)

polk already has 10,128 bid_decisions rows (NOT touched -- this script only
inserts for case_numbers currently missing a qualifying row, and skips any
case_number that already has ANY bid_decisions row to avoid duplicates).

Reuses build_bid_decision()/COUNTY_CONFIG['polk'] from scripts/shard9_j_generator.py
verbatim (Shapira Formula, same shape/labels as every other J-generator run this
project, including the 'honesty_marker': 'INFERRED' tags already baked into
build_bid_decision's factors dict for the triangle/CMA scores -- these are
formula-derived risk factors, not fabricated transaction data).
"""
import os
import sys
import json
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("j_gen", os.path.join(_here, "shard9_j_generator.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

import httpx

COUNTY = "polk"
BASE = _mod.BASE
HEADERS = _mod.HEADERS


def main():
    config = _mod.COUNTY_CONFIG[COUNTY]
    with httpx.Client(timeout=120) as client:
        # 1. fetch existing bid_decisions case_numbers for polk (paginated, any row --
        #    conservative: never insert a second row for a case_number that already has one)
        existing = set()
        offset, page = 0, 1000
        while True:
            h = {**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+page-1}"}
            r = client.get(f"{BASE}/bid_decisions", headers=h,
                            params={"select": "case_number", "county_slug": f"eq.{COUNTY}"}, timeout=60)
            if r.status_code not in (200, 206):
                raise SystemExit(f"existing fetch failed {r.status_code}: {r.text[:200]}")
            batch = r.json()
            for rec in batch:
                existing.add(rec["case_number"])
            if len(batch) < page:
                break
            offset += page
        print(f"polk: {len(existing)} existing bid_decisions case_numbers")

        # 2. fetch in-scope MCA rows -- exact evaluator scope:
        #    (data_source <> 'propertyonion' OR tier1_authoritative = true)
        rows, offset = [], 0
        params = {
            "select": "case_number,parcel_id,property_address,auction_date,opening_bid,sale_type,"
                      "market_value,assessed_value,po_market_value,data_source,tier1_authoritative",
            "county": f"eq.{COUNTY}",
            "or": "(data_source.neq.propertyonion,data_source.is.null,tier1_authoritative.eq.true)",
            "order": "auction_date.desc",
        }
        while True:
            h = {**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+page-1}"}
            r = client.get(f"{BASE}/multi_county_auctions", headers=h, params=params, timeout=120)
            if r.status_code not in (200, 206):
                raise SystemExit(f"mca fetch failed {r.status_code}: {r.text[:200]}")
            batch = r.json()
            rows.extend(batch)
            if len(batch) < page:
                break
            offset += page
        print(f"polk: fetched {len(rows)} in-scope MCA rows")

        batch, total_inserted, errors, skipped = [], 0, 0, 0
        seen_cns = set()
        for row in rows:
            cn = row.get("case_number")
            if not cn or cn in existing or cn in seen_cns:
                skipped += 1
                continue
            seen_cns.add(cn)
            try:
                batch.append(_mod.build_bid_decision(row, COUNTY, config))
            except Exception as e:
                print(f"build error for {cn}: {e}")
                errors += 1
            if len(batch) >= 200:
                ins = client.post(f"{BASE}/bid_decisions", headers=HEADERS, content=json.dumps(batch), timeout=60)
                if ins.status_code >= 400:
                    print(f"insert failed {ins.status_code}: {ins.text[:300]}")
                    errors += 1
                else:
                    total_inserted += len(batch)
                    print(f"inserted {len(batch)} (running: {total_inserted})")
                batch = []
        if batch:
            ins = client.post(f"{BASE}/bid_decisions", headers=HEADERS, content=json.dumps(batch), timeout=60)
            if ins.status_code >= 400:
                print(f"insert failed {ins.status_code}: {ins.text[:300]}")
                errors += 1
            else:
                total_inserted += len(batch)

        print(f"polk: DONE inserted={total_inserted} errors={errors} skipped_existing={skipped}")
        ev = _mod.verify_county(COUNTY, client)
        print(json.dumps(ev.get("J", {}), indent=2))


if __name__ == "__main__":
    main()
