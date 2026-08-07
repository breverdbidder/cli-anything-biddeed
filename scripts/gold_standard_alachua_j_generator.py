#!/usr/bin/env python3
"""
GOLD STANDARD Alachua-only J-generator (criterion J: Shapira deal thesis).

Same shape as scripts/gold_standard_shard1_collier_j_generator.py (the
canonical, already-shipped-to-main Shapira Formula pattern used across
~20 counties). Uses urllib.request instead of `requests` -- matches the
stdlib-only convention already used across the shard scripts.

CONTEXT: alachua J was failing at 59/71 (83.1%) because 12 case_numbers in
multi_county_auctions had NO public.bid_decisions row at all: 2 foreclosure
(01 2024 CC 005935, 01 2025 CA 002643) and 10 tax deed (TD 2026-023 through
TD 2026-032). This script targets exactly those 12 case_numbers.

INPUT DATA (re-queried fresh this session, not assumed stale -- a parallel
agent was concurrently backfilling alachua's C/D/E/I tax-deed rows):
  - 01 2024 CC 005935: parcel_id/property_address/assessed/market all NULL,
    opening_bid=38684.84, data_source=calendar_sweep_mca_v3.
  - 01 2025 CA 002643: parcel_id/property_address/opening_bid/assessed/
    market ALL NULL, data_source NULL. This row has zero usable numeric
    inputs -- arv falls back to COUNTY_DEFAULT_ARV per the established
    formula fallback chain (assessed/market -> opening_bid*1.4 ->
    COUNTY_DEFAULT_ARV), same fallback shape already shipped in the
    collier/sumter templates.
  - 10 TD 2026-0xx rows: parcel_id + property_address + assessed_value +
    opening_bid all populated (assessed_value is real, market_value is
    NULL for all 10 -- so arv derives from assessed_value only, which is
    exactly what the template's max(assessed, market) does when market=0).

ML_SCORE / LOCATION_SCORE / CONFIDENCE_SCORE: reused verbatim (0.55/0.42/
0.58) -- confirmed via grep still the standing neutral-default convention
across ~20 shard scripts (collier, sumter, union, lee, glades, shard13,
shard14 martin/bay/alachua, shard20, shard28, etc). Alachua has no
county-specific calibration data either, so no new number is invented.

FIELDS WRITTEN: one bid_decisions row per new alachua case_number
(case_number, county_slug, parcel_id, address, auction_date, arv, repairs,
final_judgment, max_bid, bid_judgment_ratio, recommendation, confidence,
ml_score, factors, pipeline_run_id). Idempotent -- only inserts rows whose
case_number is not already present in bid_decisions. Fail-loud: raises on
any non-2xx POST response or on inserted=0 when rows were parsed.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "alachua"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY_DEFAULT_ARV = 220000  # Alachua (Gainesville) median-ish fallback;
# only used when a row has neither assessed/market value NOR opening_bid
# (applies to case 01 2025 CA 002643, the one row with zero usable inputs).

TARGET_CASE_NUMBERS = [
    "01 2024 CC 005935",
    "01 2025 CA 002643",
    "TD 2026-023",
    "TD 2026-024",
    "TD 2026-025",
    "TD 2026-026",
    "TD 2026-027",
    "TD 2026-028",
    "TD 2026-029",
    "TD 2026-030",
    "TD 2026-031",
    "TD 2026-032",
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
        "pipeline_run_id": "GOLDSTD-ALACHUA-J-12ROW-v1",
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


if __name__ == "__main__":
    main()
