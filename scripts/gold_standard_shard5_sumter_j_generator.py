#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-5 (run 3497): sumter-only J-generator rerun.

scripts/shard7_j_generator.py already defines and ships the Shapira Formula
for sumter (ML_SCORES/LOCATION_SCORES/CONFIDENCE_SCORES/COUNTY_DEFAULTS all
include a "sumter" entry) but that script imports httpx, which is not
installed in this environment, and its COUNTIES loop touches orange/flagler/
marion/franklin -- out of scope for this shard. This script reuses the exact
same formula/constants for sumter only, via requests instead of httpx.

Root cause (confirmed via read-only diagnostic workflow this session):
bid_decisions has zero sumter rows because sumter's real 11-row live dataset
(provenance 2026-07-04) postdates shard7_j_generator.py's last run
(2026-06-19) -- it was never processed. 4 of 11 rows have non-null
case_number (all sale_type=foreclosure, opening_bid=null, assessed/market
=null) and are eligible under the existing filter.
"""
import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "sumter"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY_DEFAULT_ARV = 180000


def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def calc_bid_decision(row):
    assessed = row.get("assessed_value") or 0
    opening = row.get("opening_bid") or 0
    market = row.get("market_value") or 0
    arv = max(assessed, market) if max(assessed, market) > 0 else (
        opening * 1.4 if opening > 0 else 0
    )
    if arv <= 0:
        arv = COUNTY_DEFAULT_ARV
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
        "county_slug": COUNTY,
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
        "pipeline_run_id": "SHARD5-RUN3497-SUMTER-J-v1",
    }


def main():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=headers(),
        params={
            "county": f"eq.{COUNTY}",
            "case_number": "not.is.null",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value",
            "limit": 2000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    auctions = resp.json()
    print(f"{COUNTY}: {len(auctions)} auctions with case_number")

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=headers(),
        params={"county_slug": f"eq.{COUNTY}", "select": "case_number", "limit": 5000},
        timeout=60,
    )
    resp.raise_for_status()
    existing = {r["case_number"] for r in resp.json()}
    print(f"{COUNTY}: {len(existing)} existing bid_decisions")

    new_auctions = [a for a in auctions if a["case_number"] not in existing]
    print(f"{COUNTY}: {len(new_auctions)} new to insert")

    if not new_auctions:
        print(f"{COUNTY}: DONE - 0 rows inserted")
        return

    rows = [calc_bid_decision(a) for a in new_auctions]

    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers={**headers(), "Prefer": "return=representation"},
        json=rows,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}: "
            f"{resp.status_code} {resp.text[:500]}"
        )
    inserted = len(resp.json())
    if inserted == 0 and len(rows) > 0:
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}")
    print(f"{COUNTY}: DONE - {inserted} rows inserted")


if __name__ == "__main__":
    main()
