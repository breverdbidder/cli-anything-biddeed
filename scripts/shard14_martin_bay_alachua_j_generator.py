#!/usr/bin/env python3
"""SHARD-14 (martin/bay/alachua/lake), dispatch 2a2b2667-58f3-4e55-a353-d33a04236bf9.

J-generator for martin/bay/alachua (lake already at J=100%, see
scripts/shard7_lake_j_generator.py -- not touched here). Reuses the exact
formula/insert pattern from scripts/gold_standard_shard5_sumter_j_generator.py
(shipped commit e1349b21, proven live). Not a rebuild: bid_decisions already
carries 33/101/49 complete rows for martin/bay/alachua respectively (arv,
max_bid, ml_score, and all 5 factor keys already present on every existing
row -- confirmed via direct diagnostic pull, zero incomplete rows found).
The gap is coverage, not quality: 4/36/7 case_numbers in the scored
multi_county_auctions population (data_source<>propertyonion OR
tier1_authoritative) have no bid_decisions row at all yet. This script fills
only those.

County ARV defaults (used ONLY when a row has no assessed_value/market_value
/opening_bid of its own) are the live median(assessed_value, market_value)
across each county's current multi_county_auctions rows, queried this
session -- not guessed:
  martin  239480 (n=32)   bay  73911.5 (n=114)   alachua  150000 (n=43)

Usage:
  python3 scripts/shard14_martin_bay_alachua_j_generator.py --county bay
  python3 scripts/shard14_martin_bay_alachua_j_generator.py --all
"""
import argparse
import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58

COUNTY_DEFAULT_ARV = {
    "martin": 239480,
    "bay": 73912,
    "alachua": 150000,
}


def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def calc_bid_decision(row, county):
    assessed = row.get("assessed_value") or 0
    opening = row.get("opening_bid") or 0
    market = row.get("market_value") or 0
    arv = max(assessed, market) if max(assessed, market) > 0 else (
        opening * 1.4 if opening > 0 else 0
    )
    if arv <= 0:
        arv = COUNTY_DEFAULT_ARV[county]
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

    factors = {
        "distress_location": LOCATION_SCORE,
        "distress_property": 0.50,
        "distress_owner": 0.55,
        "cma_distressed": {"value": round(arv * 0.87, 2), "sources": ["assessed_value_proxy"]},
        "cma_resale": {"value": round(arv * 1.12, 2), "sources": ["market_value_proxy"]},
    }

    bid_ratio = max_bid / opening if opening > 0 else None
    if bid_ratio is not None:
        bid_ratio = min(bid_ratio, 9.99)

    return {
        "case_number": row["case_number"],
        "county_slug": county,
        "parcel_id": row.get("parcel_id"),
        "address": row.get("property_address"),
        "auction_date": row.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": round(repairs, 2),
        "final_judgment": round(opening, 2) if opening else None,
        "max_bid": round(max_bid, 2),
        "bid_judgment_ratio": round(bid_ratio, 4) if bid_ratio else None,
        "recommendation": "BID" if (opening > 0 and max_bid > opening) else "PASS",
        "confidence": CONFIDENCE_SCORE,
        "ml_score": ML_SCORE,
        "factors": factors,
        "pipeline_run_id": "SHARD14-2a2b2667-J-v1",
    }


def run_county(county):
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=headers(),
        params={
            "county": f"eq.{county}",
            "case_number": "not.is.null",
            "or": "(data_source.neq.propertyonion,tier1_authoritative.eq.true)",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value",
            "limit": 2000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    auctions = resp.json()
    print(f"{county}: {len(auctions)} scored auctions with case_number")

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=headers(),
        params={"county_slug": f"eq.{county}", "select": "case_number", "limit": 5000},
        timeout=60,
    )
    resp.raise_for_status()
    existing = {r["case_number"] for r in resp.json()}
    print(f"{county}: {len(existing)} existing bid_decisions")

    new_auctions = [a for a in auctions if a["case_number"] not in existing]
    print(f"{county}: {len(new_auctions)} new to insert")

    if not new_auctions:
        print(f"{county}: DONE - 0 rows inserted")
        return

    rows = [calc_bid_decision(a, county) for a in new_auctions]

    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers={**headers(), "Prefer": "return=representation"},
        json=rows,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Fail-loud: parsed={len(rows)} inserted=0 for {county}: "
            f"{resp.status_code} {resp.text[:500]}"
        )
    inserted = len(resp.json())
    if inserted == 0 and len(rows) > 0:
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted=0 for {county}")
    print(f"{county}: DONE - {inserted} rows inserted")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    counties = list(COUNTY_DEFAULT_ARV) if args.all else [args.county]
    for c in counties:
        if c not in COUNTY_DEFAULT_ARV:
            raise SystemExit(f"unknown county {c}")
        run_county(c)


if __name__ == "__main__":
    main()
