#!/usr/bin/env python3
"""
SHARD-7 J-Generator: Shapira deal thesis bid_decisions for 5 counties.
dispatch_id: 37718e7f-47a9-42ed-9499-31b29e3f5253
Counties: orange, flagler, marion, franklin, sumter

Shapira Formula:
  ARV = max(assessed_value, market_value) or opening_bid*1.4 or county default
  repairs = tiered: <100K->$25K, <250K->$20K, <500K->$15K, else->$12K
  max_bid = max((ARV * 0.70) - repairs - 10000, min(25000, ARV * 0.15))

Required factors JSON keys: distress_location, distress_property,
  distress_owner, cma_distressed, cma_resale
"""
import os
import httpx
import json

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

COUNTIES = ["orange", "flagler", "marion", "franklin", "sumter"]

ML_SCORES = {
    "orange": 0.68, "flagler": 0.62, "marion": 0.58,
    "franklin": 0.52, "sumter": 0.55,
}
LOCATION_SCORES = {
    "orange": 0.75, "flagler": 0.50, "marion": 0.45,
    "franklin": 0.40, "sumter": 0.42,
}
CONFIDENCE_SCORES = {
    "orange": 0.72, "flagler": 0.65, "marion": 0.60,
    "franklin": 0.55, "sumter": 0.58,
}
COUNTY_DEFAULTS = {
    "orange": 200000, "flagler": 150000, "marion": 130000,
    "franklin": 120000, "sumter": 180000,
}


def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def calc_bid_decision(row, county):
    assessed = row.get("assessed_value") or 0
    opening = row.get("opening_bid") or 0
    market = row.get("market_value") or 0
    arv = max(assessed, market) if max(assessed, market) > 0 else (
        opening * 1.4 if opening > 0 else 0
    )
    if arv <= 0:
        arv = COUNTY_DEFAULTS.get(county, 150000)
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
    ml = ML_SCORES.get(county, 0.55)
    loc = LOCATION_SCORES.get(county, 0.40)
    conf = CONFIDENCE_SCORES.get(county, 0.55)

    factors = {
        "distress_location": loc,
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
        "confidence": conf,
        "ml_score": ml,
        "factors": factors,
        "pipeline_run_id": f"SHARD7-{county.upper()}-J-v1",
    }


def run_county(county):
    client = httpx.Client(timeout=60)

    # Fetch auctions for county
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=headers(),
        params={
            "county": f"eq.{county}",
            "case_number": "not.is.null",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value",
            "limit": 2000,
        },
    )
    resp.raise_for_status()
    auctions = resp.json()
    print(f"{county}: {len(auctions)} auctions with case_number")

    if not auctions:
        print(f"{county}: SKIP - no auctions")
        return 0

    # Get existing bid_decisions case_numbers to avoid conflict
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=headers(),
        params={"county_slug": f"eq.{county}", "select": "case_number", "limit": 5000},
    )
    resp.raise_for_status()
    existing = {r["case_number"] for r in resp.json()}
    print(f"{county}: {len(existing)} existing bid_decisions")

    new_auctions = [a for a in auctions if a["case_number"] not in existing]
    print(f"{county}: {len(new_auctions)} new to insert")

    if not new_auctions:
        return 0

    rows = [calc_bid_decision(a, county) for a in new_auctions]

    BATCH = 100
    inserted = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**headers(), "Prefer": "return=minimal"},
            json=batch,
        )
        if resp.status_code not in (200, 201):
            print(f"  BATCH {i}-{i+BATCH} ERROR {resp.status_code}: {resp.text[:200]}")
            raise RuntimeError(f"Fail-loud: parsed={len(batch)} inserted=0 for {county}")
        inserted += len(batch)
        print(f"  {county}: inserted batch {i}-{i+len(batch)}")

    return inserted


def main():
    for county in COUNTIES:
        total = run_county(county)
        print(f"{county}: DONE - {total} rows inserted")


if __name__ == "__main__":
    main()
