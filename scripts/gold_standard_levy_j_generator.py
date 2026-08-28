#!/usr/bin/env python3
"""
GOLD STANDARD Levy-only J-generator (criterion J: Shapira deal thesis).

Same shape as scripts/gold_standard_alachua_j_generator.py (the canonical,
already-shipped-to-main Shapira Formula pattern used across ~20 counties).
Uses urllib.request instead of `requests` -- matches the stdlib-only
convention already used across the shard scripts.

CONTEXT: levy J was failing at 31/39 (79.5%) because 8 case_numbers in
multi_county_auctions had NO public.bid_decisions row at all: all 8 are tax
deed cases (2026-4164TD, 2026-4166TD, 2026-4167TD, 2026-4168TD, 2026-4169TD,
2026-4170TD, 2026-4171TD, 2026-4173TD). This script targets exactly those 8
case_numbers.

INPUT DATA (re-queried fresh this session): a prior agent (levy-I-enrich)
backfilled real property_address/latitude/longitude/assessed_value/
market_value/opening_bid for all 8 rows via TaxSmart + FL GIO cadastral in
this same session. Re-fetched independently here and confirmed live in DB --
all 8 rows have non-null, non-zero assessed_value, market_value, and
opening_bid. No row needed the COUNTY_DEFAULT_ARV fallback (max(assessed,
market) > 0 for all 8).

ML_SCORE / LOCATION_SCORE / CONFIDENCE_SCORE: reused verbatim (0.55/0.42/
0.58) -- standing neutral-default convention across ~20 shard scripts
(collier, sumter, union, lee, glades, alachua, shard13, shard14, shard20,
shard28, etc). Levy has no county-specific calibration data either, so no
new number is invented.

FIELDS WRITTEN: one bid_decisions row per new levy case_number (case_number,
county_slug, parcel_id, address, auction_date, arv, repairs, final_judgment,
max_bid, bid_judgment_ratio, recommendation, confidence, ml_score, factors,
pipeline_run_id). Idempotent -- only inserts rows whose case_number is not
already present in bid_decisions. Fail-loud: raises on any non-2xx POST
response or on inserted=0 when rows were parsed.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "levy"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY_DEFAULT_ARV = 175000  # Levy County (small rural north-central FL)
# fallback median-ish value; NOT expected to be used since all 8 target rows
# have real assessed/market values post I-enrich, kept only for parity with
# the template's fallback chain / fail-safety.

TARGET_CASE_NUMBERS = [
    "2026-4164TD",
    "2026-4166TD",
    "2026-4167TD",
    "2026-4168TD",
    "2026-4169TD",
    "2026-4170TD",
    "2026-4171TD",
    "2026-4173TD",
]


def headers(extra=None):
    h = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def http_get(path, params):
    url = f"{SB}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers(), method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def http_post(path, rows):
    url = f"{SB}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(rows).encode(),
        headers=headers({"Prefer": "return=representation"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


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
        "pipeline_run_id": "GOLDSTD-LEVY-J-8ROW-v1",
    }


def main():
    auctions = http_get(
        "/rest/v1/multi_county_auctions",
        {
            "county": f"eq.{COUNTY}",
            "case_number": f"in.({','.join(chr(34) + c + chr(34) for c in TARGET_CASE_NUMBERS)})",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value",
            "limit": 2000,
        },
    )
    print(f"{COUNTY}: {len(auctions)} target auctions fetched fresh")
    found = {a["case_number"] for a in auctions}
    missing = set(TARGET_CASE_NUMBERS) - found
    if missing:
        print(f"{COUNTY}: WARNING - {len(missing)} target case_numbers not found in multi_county_auctions: {sorted(missing)}")

    existing_rows = http_get(
        "/rest/v1/bid_decisions",
        {"county_slug": f"eq.{COUNTY}", "select": "case_number", "limit": 5000},
    )
    existing = {r["case_number"] for r in existing_rows}
    already_present = existing & found
    if already_present:
        print(f"{COUNTY}: {len(already_present)} target case_numbers already in bid_decisions (skipping): {sorted(already_present)}")

    new_auctions = [a for a in auctions if a["case_number"] not in existing]
    print(f"{COUNTY}: {len(new_auctions)} new to insert")

    if not new_auctions:
        print(f"{COUNTY}: DONE - 0 rows inserted (all already present)")
        return

    rows = [calc_bid_decision(a) for a in new_auctions]

    status, body = http_post("/rest/v1/bid_decisions", rows)
    if status not in (200, 201):
        raise RuntimeError(
            f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}: "
            f"HTTP {status}: {body if isinstance(body, str) else json.dumps(body)[:500]}"
        )
    inserted = len(body)
    if inserted == 0 and len(rows) > 0:
        raise RuntimeError(f"Fail-loud: parsed={len(rows)} inserted=0 for {COUNTY}")
    print(f"{COUNTY}: DONE - {inserted} rows inserted: {sorted(r['case_number'] for r in body)}")
    for r in sorted(body, key=lambda x: x["case_number"]):
        print(f"  {r['case_number']}: arv={r['arv']} max_bid={r['max_bid']} recommendation={r['recommendation']}")


if __name__ == "__main__":
    main()
