#!/usr/bin/env python3
"""GOLD STANDARD shard-5 (lee/st_johns), dispatch ba2461bd-d091-4621-b809-9f1a3fa4244c.

J-generator for st_johns. County-agnostic port of the proven
scripts/gold_standard_shard5_lee_j_generator.py pattern (already used for
lee/martin/bay/alachua/etc.) -- not a new formula. bid_decisions already has
50/54 complete rows for st_johns. The J gap is coverage: 4 case_numbers
(CC24-6166, CA25-1289, CA25-1585, CA25-0749) have no bid_decisions row.

st_johns ARV default (used only when a row has no assessed_value/
market_value/opening_bid) = live median(assessed_value, market_value)
across st_johns's current multi_county_auctions rows, queried this session
2026-08-09: 262176.56 (n=54).
"""
import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY = "st_johns"
DEFAULT_ARV = 262176.56


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
        "pipeline_run_id": "SHARD5-ba2461bd-STJOHNS-J-v1",
    }


def main():
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=headers(),
        params={
            "county": f"eq.{COUNTY}",
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
    print(f"{COUNTY}: {len(auctions)} scored auctions with case_number")

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
    print(f"{COUNTY}: {len(new_auctions)} new to insert: {[a['case_number'] for a in new_auctions]}")

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
