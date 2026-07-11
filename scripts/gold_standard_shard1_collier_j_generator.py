#!/usr/bin/env python3
"""
GOLD STANDARD shard-1 (run3713 continuation): collier-only J-generator.

Same shape as scripts/gold_standard_shard5_sumter_j_generator.py (the
canonical, already-shipped-to-main Shapira Formula pattern used across
~20 counties), applied to collier. Uses urllib.request instead of
`requests` because `requests` is not installed in this sandbox (verified
live this session: `python3 -c "import requests"` raises
ModuleNotFoundError) -- matches the stdlib-only convention already used in
scripts/shard9_run3645_sumter_i_parcel_enrichment.py.

CONTEXT (verified live 2026-07-11 via pencil_dod_evaluate_county('collier')):
  baseline J: deal_complete=0 of 212 auctions_total -> metric 0.0%, pass=false.
  bid_decisions had exactly 1 collier row before this run, case_number
  "PO_1139101" -- a propertyonion-sourced row, NOT one of the 212
  data_source='collier_clerk_laserfiche' rows this script targets, so it
  does not collide with anything inserted here.

INPUT DATA (verified live before writing):
  212 collier multi_county_auctions rows, all with case_number + parcel_id
  populated (data_source='collier_clerk_laserfiche'). A separate agent
  already ran I-enrichment this session via the FL DOR statewide cadastral
  FeatureServer: 204/212 rows now have assessed_value + market_value
  non-null, 95/212 have property_address non-null (vacant-land parcels
  legitimately have no PHY_ADDR1 in DOR and were left null, not
  fabricated), and all 212 have opening_bid non-null. This script does NOT
  re-enrich I fields -- it only reads whatever is already on the row and
  applies the ARV/repairs/max_bid/factors formula on top, exactly per the
  established J contract (arv falls back to opening_bid*1.4, then to
  COUNTY_DEFAULT_ARV, for the small remainder of rows still missing
  assessed/market values).

ML_SCORE / LOCATION_SCORE / CONFIDENCE_SCORE: reused verbatim from sumter's
  constants (0.55/0.42/0.58). REASONING (documented, not invented): these
  are used as a county-agnostic neutral default across every shard that has
  no county-specific historical bid-outcome data to calibrate against
  (confirmed via grep: the same 0.55/0.42/0.58 triple appears in
  gold_standard_shard5_sumter_j_generator.py, shard14_martin_bay_alachua_
  j_generator.py, gold_standard_shard11_union_j_generator.py, and the
  original shard7_j_generator.py/shard7_s65_j_generator.py). Collier has no
  county-specific calibration data either (B/F verified-sale-outcome rows
  exist but were not built to feed ml_score calibration in any prior
  shard), so the same established neutral default applies here rather than
  inventing a new number with no basis.

FIELDS WRITTEN: one bid_decisions row per new collier case_number (case_number,
  county_slug, parcel_id, address, auction_date, arv, repairs,
  final_judgment, max_bid, bid_judgment_ratio, recommendation, confidence,
  ml_score, factors, pipeline_run_id). Idempotent -- only inserts rows whose
  case_number is not already present in bid_decisions.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "collier"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY_DEFAULT_ARV = 250000  # Collier median-ish fallback; only used when a
# row has neither assessed/market value NOR opening_bid (should be zero rows
# given all 212 have opening_bid, but kept for parity with the established
# formula shape / fail-safe against unexpected nulls).


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
        "pipeline_run_id": "SHARD1-COLLIER-J-run3713-v1",
    }


def main():
    auctions = http_get(
        "/rest/v1/multi_county_auctions",
        {
            "county": f"eq.{COUNTY}",
            "case_number": "not.is.null",
            "select": "case_number,parcel_id,property_address,auction_date,"
                      "opening_bid,assessed_value,market_value",
            "limit": 2000,
        },
    )
    print(f"{COUNTY}: {len(auctions)} auctions with case_number")

    existing_rows = http_get(
        "/rest/v1/bid_decisions",
        {"county_slug": f"eq.{COUNTY}", "select": "case_number", "limit": 5000},
    )
    existing = {r["case_number"] for r in existing_rows}
    print(f"{COUNTY}: {len(existing)} existing bid_decisions ({sorted(existing)})")

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
    print(f"{COUNTY}: DONE - {inserted} rows inserted")


if __name__ == "__main__":
    main()
