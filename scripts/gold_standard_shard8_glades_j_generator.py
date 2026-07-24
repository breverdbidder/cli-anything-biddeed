#!/usr/bin/env python3
"""
GOLD STANDARD shard-8 (run3713 continuation): glades-only J-generator.

Same shape as scripts/gold_standard_shard1_collier_j_generator.py (the
canonical, already-shipped-to-main Shapira Formula pattern used across
~20 counties), applied to glades. Uses urllib.request instead of
`requests` because `requests` is not installed in this sandbox --
matches the stdlib-only convention already used in
scripts/gold_standard_shard1_collier_i_enrichment.py and
scripts/shard9_run3645_sumter_i_parcel_enrichment.py.

CONTEXT (verified live 2026-07-11 via pencil_dod_evaluate_county('glades')):
  baseline J: deal_complete=0 of 70 auctions_total -> metric 0.0%, pass=false.
  bid_decisions has ZERO glades rows before this run, so this is a full
  first pass with no dedup collisions expected.

INPUT DATA (verified live before writing):
  70 glades multi_county_auctions rows, all with case_number + parcel_id
  populated (data_source='municode_munidocs:GLADES-TD-V1'). 50/70 rows have
  opening_bid populated (min $636.13, max $14,629.15, median ~$1,820 --
  these are back-taxes-owed tax-deed opening bids, not property-value
  proxies, consistent with Glades being FL's smallest-population county).
  20/70 rows have NO opening_bid at all. ZERO rows currently have
  assessed_value or market_value (that I-criterion enrichment is a
  separate, parallel task not depended on here). This script does NOT
  enrich I fields -- it only reads whatever is already on the row and
  applies the ARV/repairs/max_bid/factors formula on top, exactly per the
  established J contract: arv = max(assessed_value, market_value) if either
  is set, else opening_bid*1.4, else COUNTY_DEFAULT_ARV.

COUNTY_DEFAULT_ARV (glades-specific, NOT reused from Collier's $250k
  luxury-market default): Glades is FL's smallest county by population
  (~13K residents, per US Census), overwhelmingly rural agricultural land
  around Lake Okeechobee (Moore Haven + unincorporated). Zillow/Redfin
  county-level ZHVI-class figures for Glades cluster in the low-$100Ks for
  single-family homes, well below Collier's Naples-driven luxury market.
  Chose $90,000 as a conservative rural-county fallback -- applies only to
  the 20/70 rows with neither assessed/market value NOR opening_bid; the
  other 50/70 rows use the opening_bid*1.4 fallback per the established
  formula, which is grounded in actual auction data already in the DB
  (not fabricated).

ML_SCORE / LOCATION_SCORE / CONFIDENCE_SCORE: reused verbatim from the
  established county-agnostic neutral defaults (0.55/0.42/0.58) --
  confirmed via grep to appear identically in
  gold_standard_shard5_sumter_j_generator.py,
  shard14_martin_bay_alachua_j_generator.py,
  gold_standard_shard11_union_j_generator.py, and
  gold_standard_shard1_collier_j_generator.py. Glades has no
  county-specific calibration data either, so the same neutral default
  applies here rather than inventing a new number with no basis.

FIELDS WRITTEN: one bid_decisions row per new glades case_number
  (case_number, county_slug, parcel_id, address, auction_date, arv,
  repairs, final_judgment, max_bid, bid_judgment_ratio, recommendation,
  confidence, ml_score, factors, pipeline_run_id). Idempotent -- only
  inserts rows whose case_number is not already present in bid_decisions.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

print(
    "QUARANTINED (2026-07-24, Gold Standard shard-8 glades J ghost-success "
    "regression): this script's output was confirmed to be a ghost-success "
    "fabrication. It bulk-inserted 70 bid_decisions rows for glades at "
    "2026-07-24T00:07:47Z with a CONSTANT ml_score across all 70 rows "
    "(module-level ML_SCORE = 0.55, never varied per property) and "
    "pipeline_version NULL for all 70 rows -- exactly reproducing the "
    "pattern already purged once by migrations/20260721_gold_standard_"
    "shard9_hillsborough_glades_suwannee_j_ghost_success_purge.sql. The "
    "70 ghost rows were deleted again and superseded by a real per-property "
    "insert: migrations/20260724_glades_j_real_bid_decisions_run6080.sql "
    "(ml_score computed per-row from opening_bid/ARV ratio, range "
    "0.30-0.72, pipeline_version='glades_j_gen_run6080_v1'). Refusing to "
    "run. If glades J ever needs regenerating, use the SQL migration's "
    "per-property formula, or its Python sibling "
    "scripts/glades_j_generator_run6080.py -- do not revive this constant-"
    "score module-level-default approach.",
    file=sys.stderr,
)
sys.exit(1)


SB = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "glades"

ML_SCORE = 0.55
LOCATION_SCORE = 0.42
CONFIDENCE_SCORE = 0.58
COUNTY_DEFAULT_ARV = 90000  # Glades rural-county fallback (see module
# docstring for reasoning). Only used when a row has neither
# assessed/market value NOR opening_bid (20/70 rows).


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
        "pipeline_run_id": "SHARD8-GLADES-J-run3713-v1",
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
