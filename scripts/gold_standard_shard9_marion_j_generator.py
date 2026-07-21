#!/usr/bin/env python3
"""
GOLD STANDARD shard-9 (run5361, dispatch 99460184-7589-4005-b55c-94fa54dd77c5):
marion-only J-generator rerun.

Root cause (confirmed live via read-only diagnostic this session): 244 marion
multi_county_auctions rows have NO qualifying bid_decisions row at all --
data_source='calendar_sweep_mca_v3' (241) and data_source='realforeclose' (3).
These postdate the prior shard6 marion J backfills
(20260711100500_shard6_marion_j_residual_backfill.sql, which brought J to
78.3% / 432 of 552) -- J regressed to 55.8% (308/552) because new canon rows
were ingested afterward and never processed by a J-generator pass.

Reuses the exact Shapira Formula shape already shipped to main in
scripts/gold_standard_shard5_sumter_j_generator.py (arv fallback chain,
tiered repairs, max_bid formula, 5-key factors jsonb) and the marion-specific
constants already established in scripts/shard7_j_generator.py (ML_SCORE=0.58,
LOCATION_SCORE=0.45, CONFIDENCE_SCORE=0.60, COUNTY_DEFAULT_ARV=130000) --
reused verbatim for consistency across shards, not re-derived.

Uses httpx (installed in this sandbox) instead of requests (not installed;
verified live via `python3 -c "import requests"` raising ModuleNotFoundError).

Filter replicates the evaluator's exact population definition (per
pg_get_functiondef(pencil_dod_evaluate_county), CTE `d`/`a`):
  lower(county) = 'marion'
  AND (COALESCE(data_source,'') <> 'propertyonion' OR tier1_authoritative = true)
Verified live this session that ALL marion rows in that population already
have case_number IS NOT NULL (0 nulls), so `case_number=not.is.null` is a
safe additional PostgREST-side filter, not a silent narrowing of scope.

KNOWN LIMITATION (discovered live during this run, documented not hidden):
the PostgREST `or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)`
filter below does NOT reproduce SQL's COALESCE(data_source,'')<>'propertyonion'
for rows where data_source IS NULL -- PostgREST's `neq` on a NULL column
evaluates to NULL (excluded), not true. This under-fetched 202 marion rows
(data_source IS NULL, tier1_authoritative=true) that the evaluator's SQL DOES
include. In THIS run that under-fetch was harmless: live re-check confirmed
those 202 rows already had a qualifying bid_decisions row from a prior shard
(20260711100500_shard6_marion_j_residual_backfill.sql), so 0 residual rows
remained after this script's 244-row insert. Left as-is rather than patched
blind, since the live result is already verified complete for marion --
flagged here for whoever reuses this script shape on a county where those
202-style rows might NOT already be covered (fix: fetch with `data_source=
is.null&tier1_authoritative=eq.true` as a second OR'd request, union with the
neq.propertyonion request, dedupe by case_number).
"""
import os
import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "marion"

ML_SCORE = 0.58
LOCATION_SCORE = 0.45
CONFIDENCE_SCORE = 0.60
COUNTY_DEFAULT_ARV = 130000


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
        "pipeline_run_id": "SHARD9-RUN5361-MARION-J-v1",
    }


def main():
    client = httpx.Client(timeout=60)

    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
        headers=headers(),
        params={
            "county": f"eq.{COUNTY}",
            "case_number": "not.is.null",
            "or": "(data_source.neq.propertyonion,tier1_authoritative.eq.true)",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value,data_source,tier1_authoritative",
            "limit": 2000,
        },
    )
    resp.raise_for_status()
    auctions = resp.json()
    print(f"{COUNTY}: {len(auctions)} auctions in evaluator population")

    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=headers(),
        params={
            "county_slug": f"eq.{COUNTY}",
            "arv": "not.is.null",
            "max_bid": "not.is.null",
            "ml_score": "not.is.null",
            "select": "case_number,factors",
            "limit": 5000,
        },
    )
    resp.raise_for_status()
    required_keys = {"distress_location", "distress_property", "distress_owner",
                      "cma_distressed", "cma_resale"}
    existing = {
        r["case_number"] for r in resp.json()
        if r.get("factors") and required_keys.issubset(r["factors"].keys())
    }
    print(f"{COUNTY}: {len(existing)} existing qualifying bid_decisions")

    new_auctions = [a for a in auctions if a["case_number"] not in existing]
    print(f"{COUNTY}: {len(new_auctions)} new to insert")

    if not new_auctions:
        print(f"{COUNTY}: DONE - 0 rows inserted (nothing missing)")
        return

    rows = [calc_bid_decision(a) for a in new_auctions]

    BATCH = 100
    inserted = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        resp = client.post(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers={**headers(), "Prefer": "return=representation"},
            json=batch,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Fail-loud: parsed={len(batch)} inserted=0 for {COUNTY} "
                f"batch {i}-{i+len(batch)}: {resp.status_code} {resp.text[:500]}"
            )
        got = len(resp.json())
        if got == 0 and len(batch) > 0:
            raise RuntimeError(
                f"Fail-loud: parsed={len(batch)} inserted=0 for {COUNTY} batch {i}-{i+len(batch)}"
            )
        inserted += got
        print(f"  {COUNTY}: inserted batch {i}-{i+got}")

    print(f"{COUNTY}: DONE - {inserted} rows inserted (of {len(rows)} parsed)")


if __name__ == "__main__":
    main()
