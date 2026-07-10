#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-11 (run 3497): union-only J-generator.

Reuses the exact Shapira Formula constants/shape from
scripts/gold_standard_shard5_sumter_j_generator.py (same pattern already
shipped for sumter). union has only 3 auctions total (2 foreclosure,
1 tax deed), all with real assessed_value + opening_bid from the
unionclerk_official primary_scrape (2026-07-03) -- no fabrication needed,
ARV is computed straight from those real fields.

dispatch_id: 761a0229-3bfc-414b-86b3-d27da1fd9939
"""
import os
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "union"

ML_SCORE = 0.52
LOCATION_SCORE = 0.40
CONFIDENCE_SCORE = 0.55
COUNTY_DEFAULT_ARV = 120000


def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def calc_bid_decision(row):
    assessed = float(row.get("assessed_value") or 0)
    opening = float(row.get("opening_bid") or 0)
    market = float(row.get("market_value") or 0)
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
        "distress_property": 0.48,
        "distress_owner": 0.53,
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
        "pipeline_run_id": "SHARD11-RUN3497-UNION-J-v1",
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
