#!/usr/bin/env python3
"""GOLD STANDARD shard-4, dispatch 7d59c973-434c-4b8c-a699-e820f9093c39, county=st_johns.

Fixes J (deal_complete / Shapira thesis) coverage for CA23-1974 and CA25-1600.

ROOT CAUSE: 20 case numbers had no bid_decisions row. 18 are the TD26 tax-deed
rows this session's E-fix (scripts/gold_standard_shard4_st_johns_e_taxsmart_strap_backfill.py)
gave real parcel_id/property_address to -- but NOT real assessed_value (that
script deliberately left assessed_value at its existing 200000 placeholder,
matching sibling-row precedent). Generating a J/bid_decisions row from a
placeholder assessed_value would mean fabricating an ARV, which this
project's own prior stjohns_j_backfill scripts explicitly refused to do for
the analogous case CA26-0218 (correctly reported BLOCKED). Same rule applies
here -- the 18 TD26 rows are deliberately NOT touched by this script and
remain a residual J gap until a future session sources real assessed_value
for them (e.g. from fl_parcels.jv, which IS real and IS already fetched in
the E-fix script's evidence, but was not written to multi_county_auctions
this session -- so using it here without that upstream write would be
inconsistent state, not fabrication, but is out of this script's scope).

CA23-1974 and CA25-1600 are different: both are RealForeclose-tier1-verified
(tier1_verified_at populated, tier1_source_run_id set, source_platform=
'realforeclose') with real assessed_value/judgment_amount/parcel_id/address
already in multi_county_auctions from the live scrape -- exactly the same
data completeness bar every other st_johns bid_decisions row was generated
from. This script is a straight re-run of the proven, already-live
scripts/gold_standard_shard5_stjohns_j_generator.py Shapira V1 formula
(same ARV/repairs/max_bid math, same factors structure), scoped only to
these 2 case numbers via the existing "insert if no bid_decisions row exists"
guard -- not a new formula.
"""
import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY = "st_johns"
DEFAULT_ARV = 262176.56  # live median from prior shard-5 J-generator run, reused for consistency
TARGET_CASES = {"CA23-1974", "CA25-1600"}


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
        arv = DEFAULT_ARV
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

    judgment = row.get("judgment_amount") or opening

    return {
        "case_number": row["case_number"],
        "county_slug": COUNTY,
        "parcel_id": row.get("parcel_id"),
        "address": row.get("property_address"),
        "auction_date": row.get("auction_date"),
        "arv": round(arv, 2),
        "repairs": round(repairs, 2),
        "final_judgment": round(judgment, 2) if judgment else None,
        "max_bid": round(max_bid, 2),
        "bid_judgment_ratio": round(bid_ratio, 4) if bid_ratio else None,
        "recommendation": "BID" if (opening > 0 and max_bid > opening) else "PASS",
        "confidence": CONFIDENCE_SCORE,
        "ml_score": ML_SCORE,
        "factors": factors,
        "pipeline_run_id": "SHARD4-7d59c973-STJOHNS-J-v1",
    }


def main():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=headers(),
        params={
            "county": f"eq.{COUNTY}",
            "case_number": f"in.({','.join(TARGET_CASES)})",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value,judgment_amount",
        },
        timeout=60,
    )
    resp.raise_for_status()
    auctions = resp.json()
    print(f"{COUNTY}: {len(auctions)} target rows fetched: {[a['case_number'] for a in auctions]}")

    if len(auctions) != len(TARGET_CASES):
        raise RuntimeError(
            f"FAIL-LOUD: expected {len(TARGET_CASES)} rows, fetched {len(auctions)}"
        )

    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=headers(),
        params={"county_slug": f"eq.{COUNTY}", "case_number": f"in.({','.join(TARGET_CASES)})",
                "select": "case_number"},
        timeout=60,
    )
    resp.raise_for_status()
    existing = {r["case_number"] for r in resp.json()}
    new_auctions = [a for a in auctions if a["case_number"] not in existing]

    if not new_auctions:
        print(f"{COUNTY}: DONE - 0 rows inserted (already present)")
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
            f"FAIL-LOUD: parsed={len(rows)} inserted=0 for {COUNTY}: "
            f"{resp.status_code} {resp.text[:500]}"
        )
    inserted = resp.json()
    if len(inserted) == 0 and len(rows) > 0:
        raise RuntimeError(f"FAIL-LOUD: parsed={len(rows)} inserted=0 for {COUNTY}")

    for r in inserted:
        print(f"OK  {r['case_number']}: arv={r['arv']} max_bid={r['max_bid']} ml_score={r['ml_score']}")
    print(f"\n{COUNTY}: DONE - {len(inserted)} rows inserted")


if __name__ == "__main__":
    main()
