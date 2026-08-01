#!/usr/bin/env python3
"""SHARD-4 9f070f2b: sarasota J (deal_complete) generator.

Investigated before writing (SEARCH-FIRST MANDATE):
  - scripts/j_generator_duval_brevard.py is a duval/brevard-only argparse CLI
    with placeholder ml_score logic (constant base_score +/- adjustments, NOT
    real model inference) -- extending its choices=[...] list to add
    'sarasota' would silently regress the ml_score field back to a fabricated
    constant, which the county's own bid_decisions rows do NOT currently use.
  - No sarasota-specific J generator exists yet in scripts/.
  - The proven, non-fabricated pattern already used for suwannee (and its
    parent, gold_standard_shard9_broward_alachua_j_generator_real.py) loads
    the real production Shapira V14 XGBoost booster and computes a genuine
    per-property ml_score. Forked that pattern here rather than extending the
    placeholder CLI, per SEARCH-FIRST MANDATE ("build only the delta").
  - Checked for a valuations_comps / comps table live: PostgREST schema cache
    has no such table (PGRST205) -- same finding as the suwannee session.
    No separate CMA-comps source exists; cma_distressed/cma_resale are
    derived from real per-row ARV (assessed_value/market_value), matching
    every other real J generator in this repo.
  - sarasota IS one of the 45 counties in the v14.0 model's real
    county_target_encoding_map (metrics.json), encoded rate 0.6097074468085106
    -- used directly, not the unseen-category fallback mean.

Live query before writing (see task evidence in returned report) found 21 of
367 sarasota multi_county_auctions case_numbers lack a qualifying
bid_decisions row. Of those:
  - 16 have a real assessed_value (ARV source) and real lat/lon -> genuine
    J rows generated below.
  - 5 have NULL assessed_value AND NULL market_value AND no lat/lon (the
    calendar_sweep_mca_v3 stub rows, same pattern flagged in the prior-stage
    letter-I finding for this county) -- correctly skipped, no fabrication.
"""
import os
import sys
import json
import math
import re
from datetime import datetime, timezone

import httpx
import xgboost as xgb

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
HEADERS_MIN = {**HEADERS, "Prefer": "return=minimal"}

MODEL_DIR = "/tmp/shapira"
COUNTY = "sarasota"
NEED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}
# Real per-county encoded rate pulled live from metrics.json
# county_target_encoding_map['sarasota'] -- sarasota IS in the 45-county
# training corpus, so the unseen-category fallback mean is NOT used here.
COUNTY_TARGET_ENC_SARASOTA = 0.6097074468085106


def stage_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    r = httpx.get(
        f"{SUPABASE_URL}/rest/v1/shapira_models",
        headers=HEADERS,
        params={"select": "storage_bucket,storage_path_model,storage_path_features", "model_version": "eq.v14.0", "is_production": "eq.true"},
        timeout=30,
    )
    r.raise_for_status()
    rows = r.json()
    if not rows:
        print("FATAL: no production v14.0 shapira_models row found")
        sys.exit(1)
    bucket = rows[0]["storage_bucket"]
    for local_name, remote_path in (("model.json", rows[0]["storage_path_model"]), ("features.json", rows[0]["storage_path_features"])):
        dest = os.path.join(MODEL_DIR, local_name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{remote_path}"
        resp = httpx.get(url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            f.write(resp.content)
        print(f"staged {dest} ({len(resp.content)} bytes)")


def get_all(client, table, params, order_col="case_number"):
    rows, offset, page = [], 0, 1000
    while True:
        p = dict(params)
        p.update({"limit": page, "offset": offset, "order": f"{order_col}.asc"})
        r = client.get(f"{SUPABASE_URL}/rest/v1/{table}", headers=HEADERS, params=p, timeout=60)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    return rows


def bid_decision_complete(row):
    if not row:
        return False
    if row.get("arv") is None or row.get("max_bid") is None or row.get("ml_score") is None:
        return False
    f = row.get("factors") or {}
    return NEED_FACTOR_KEYS.issubset(f.keys())


def safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def log1p(v):
    v = safe_float(v)
    if v is None:
        return float("nan")
    return math.log1p(max(v, 0.0))


def owner_flags(owner_name):
    own = (owner_name or "").upper()
    is_estate = bool(re.search(r"\b(ESTATE|TRUST|HEIRS?|DECEASED|DECD)\b|\bEST\.", own))
    is_entity = bool(re.search(r"\b(LLC|INC|CORP|LP|HOLDING|PROPERTIES|REALTY)\b", own))
    is_lender = bool(re.search(r"\b(BANK|MORTGAGE|FANNIE|FREDDIE|HUD|FHA|LENDER|FINANCIAL|SERVICING)\b", own))
    return is_estate, is_entity, is_lender


# Sarasota County Courthouse (clerk's office) -- real per-row-varying
# rurality/location-distress proxy via haversine distance, same technique as
# the suwannee generator this was forked from.
COUNTY_SEAT_LAT, COUNTY_SEAT_LON = 27.3364, -82.5307


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def build_feature_row(auction):
    judgment = safe_float(auction.get("judgment_amount"))
    opening = safe_float(auction.get("opening_bid"))
    market = safe_float(auction.get("market_value"))
    assessed = safe_float(auction.get("assessed_value"))
    prior_price = safe_float(auction.get("prior_sale_price"))
    beds = safe_float(auction.get("bedrooms")) if auction.get("bedrooms") is not None else safe_float(auction.get("beds"))
    baths = safe_float(auction.get("bathrooms")) if auction.get("bathrooms") is not None else safe_float(auction.get("baths"))
    sqft = safe_float(auction.get("living_area_sqft")) if auction.get("living_area_sqft") is not None else safe_float(auction.get("sqft"))
    year_built = safe_float(auction.get("year_built"))
    property_age = None
    if year_built is not None and 0 <= (2026 - year_built) <= 200:
        property_age = 2026 - year_built

    opening_to_market = (opening / market) if (opening is not None and market not in (None, 0)) else None
    if opening_to_market is not None:
        opening_to_market = min(opening_to_market, 10)
    judgment_to_market = (judgment / market) if (judgment is not None and market not in (None, 0)) else None
    if judgment_to_market is not None:
        judgment_to_market = min(judgment_to_market, 10)

    years_since_prior_sale = None
    prior_sale_date = auction.get("prior_sale_date")
    auction_date = auction.get("auction_date")
    if prior_sale_date and auction_date:
        try:
            d1 = datetime.fromisoformat(prior_sale_date)
            d2 = datetime.fromisoformat(auction_date)
            years_since_prior_sale = (d2 - d1).days / 365.25
        except ValueError:
            pass
    has_prior_sale = 1 if prior_price is not None else 0

    sale_type = auction.get("sale_type") or ""
    is_foreclosure = 1 if sale_type == "foreclosure" else 0
    is_tax_deed = 1 if sale_type == "tax_deed" else 0
    has_homestead = 1 if auction.get("homestead_exemption") else 0

    addr = (auction.get("property_address") or "").strip()
    is_diamond = 1 if (addr == "" or addr.isdigit()) else 0

    is_estate, is_entity, is_lender = owner_flags(auction.get("owner_name"))

    feat = {
        "judgment_amount_log1p": log1p(judgment),
        "opening_bid_log1p": log1p(opening),
        "market_value_log1p": log1p(market),
        "assessed_value_log1p": log1p(assessed),
        "prior_sale_price_log1p": log1p(prior_price),
        "beds_f": beds,
        "baths_f": baths,
        "sqft_f": sqft,
        "property_age": property_age,
        "opening_to_market": opening_to_market,
        "judgment_to_market": judgment_to_market,
        "years_since_prior_sale": years_since_prior_sale,
        "has_prior_sale": has_prior_sale,
        "is_foreclosure": is_foreclosure,
        "is_tax_deed": is_tax_deed,
        "has_homestead": has_homestead,
        "owner_is_estate": int(is_estate),
        "owner_is_entity": int(is_entity),
        "owner_is_lender": int(is_lender),
        "is_diamond": is_diamond,
        "county_target_enc": COUNTY_TARGET_ENC_SARASOTA,
    }
    return feat, {
        "judgment": judgment, "opening": opening, "market": market, "assessed": assessed,
        "property_age": property_age, "judgment_to_market": judgment_to_market,
        "is_estate": is_estate, "is_entity": is_entity, "is_lender": is_lender,
    }


def real_arv(auction):
    assessed = safe_float(auction.get("assessed_value"))
    if assessed and assessed > 0:
        return assessed, "multi_county_auctions.assessed_value"
    market = safe_float(auction.get("market_value"))
    if market and market > 0:
        return market, "multi_county_auctions.market_value"
    return None, None


def main():
    stage_model()
    client = httpx.Client(timeout=120)
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    auctions = get_all(client, "multi_county_auctions", {
        "select": "case_number,parcel_id,judgment_amount,opening_bid,market_value,assessed_value,"
                  "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                  "prior_sale_date,prior_sale_price,sale_type,property_address,owner_name,auction_date,"
                  "latitude,longitude,data_source,tier1_authoritative",
        "county": f"eq.{COUNTY}",
    })
    auctions = [a for a in auctions if a.get("case_number") and (a.get("data_source") != "propertyonion" or a.get("tier1_authoritative") is True)]

    cohort_values = sorted(safe_float(a.get("assessed_value")) or 0.0 for a in auctions)

    def assessed_percentile(v):
        if not cohort_values or v is None:
            return 0.5
        below = sum(1 for x in cohort_values if x < v)
        return below / len(cohort_values)

    existing = get_all(client, "bid_decisions", {"select": "id,case_number,parcel_id,arv,max_bid,ml_score,factors,pipeline_version", "county_slug": f"eq.{COUNTY}"})
    existing_map = {}
    for r in existing:
        existing_map.setdefault(r["case_number"], []).append(r)
    print(f"auctions={len(auctions)} existing_bid_decisions={len(existing)} distinct_case_numbers={len(existing_map)}")

    def complete_any(case_number):
        return any(bid_decision_complete(r) for r in existing_map.get(case_number, []))

    todo = [a for a in auctions if not complete_any(a["case_number"])]
    print(f"incomplete_for_J={len(todo)}")

    rows = []
    skipped_no_value = 0
    skipped_case_numbers = []
    for a in todo:
        arv, arv_source = real_arv(a)
        if arv is None or arv <= 0:
            skipped_no_value += 1
            skipped_case_numbers.append(a["case_number"])
            continue
        feat, raw = build_feature_row(a)
        fv = [[feat.get(k) if feat.get(k) is not None else float("nan") for k in feature_order]]
        dmat = xgb.DMatrix(fv, feature_names=feature_order, missing=float("nan"))
        ml_score = float(booster.predict(dmat)[0])

        repairs = max(5000.0, min(40000.0, round(arv * 0.08, 2)))
        base_bid = (arv * 0.70) - repairs - 10000
        min_profit = min(25000.0, arv * 0.15)
        max_bid = max(round(base_bid, 2), round(min_profit, 2), 1000.0)

        cma_distressed = round(arv * 0.80, 2)
        cma_resale = round(arv * 1.02, 2)

        lat, lon = safe_float(a.get("latitude")), safe_float(a.get("longitude"))
        dist_mi = haversine_miles(lat, lon, COUNTY_SEAT_LAT, COUNTY_SEAT_LON) if (lat is not None and lon is not None) else None
        loc_score = round(min(0.85, max(0.20, 0.20 + min(dist_mi, 25.0) / 25.0 * 0.65)), 4) if dist_mi is not None else 0.45

        pctl = assessed_percentile(safe_float(a.get("assessed_value")))
        sale_type_base = 0.55 if (a.get("sale_type") or "") == "tax_deed" else 0.45
        prop_score = round(min(0.85, max(0.20, sale_type_base + (0.5 - pctl) * 0.30)), 4)

        owner_score = round(min(0.90, 0.35 + 0.20 * raw["is_estate"] + 0.20 * raw["is_entity"] + 0.25 * raw["is_lender"]), 4)

        factors = {
            "distress_location": loc_score,
            "distress_property": prop_score,
            "distress_owner": owner_score,
            "cma_distressed": cma_distressed,
            "cma_resale": cma_resale,
        }
        profit = arv - max_bid - repairs
        recommendation = "BID" if profit > 0 else "PASS"

        existing_rows_for_case = existing_map.get(a["case_number"], [])
        record = {
            "case_number": a["case_number"],
            "county_slug": COUNTY,
            "parcel_id": a.get("parcel_id"),
            "arv": round(arv, 2),
            "arv_source": f"shapira_v14_real_{arv_source}",
            "repairs": repairs,
            "repair_estimate": repairs,
            "max_bid": round(max_bid, 2),
            "ml_score": round(ml_score, 4),
            "factors": factors,
            "recommendation": recommendation,
            "confidence": 0.5,
            "pipeline_version": "sarasota_shard4_9f070f2b_j_generator_real_v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing_rows_for_case:
            # Row exists but is incomplete (e.g. missing ml_score/factors) --
            # update the most recent one in place instead of inserting a dup.
            existing_row = sorted(existing_rows_for_case, key=lambda r: r.get("id", 0))[-1]
            record["_existing_id"] = existing_row["id"]
        rows.append(record)

    print(f"skipped_no_real_value={skipped_no_value} rows_to_write={len(rows)}")
    if skipped_case_numbers:
        print("skipped_case_numbers:", skipped_case_numbers)
    if rows:
        print("ml_score distribution:", sorted(r["ml_score"] for r in rows))

    to_insert = [r for r in rows if "_existing_id" not in r]
    to_update = [r for r in rows if "_existing_id" in r]

    inserted = 0
    for i in range(0, len(to_insert), 200):
        batch = to_insert[i:i + 200]
        r = client.post(f"{SUPABASE_URL}/rest/v1/bid_decisions", headers=HEADERS_MIN, json=batch)
        if r.status_code in (200, 201, 204):
            inserted += len(batch)
        else:
            print(f"FAIL insert batch {i}: {r.status_code} {r.text[:500]}")
            sys.exit(1)

    updated = 0
    for r in to_update:
        row_id = r.pop("_existing_id")
        resp = client.patch(f"{SUPABASE_URL}/rest/v1/bid_decisions", headers=HEADERS_MIN, params={"id": f"eq.{row_id}"}, json=r)
        if resp.status_code in (200, 201, 204):
            updated += 1
        else:
            print(f"FAIL update id={row_id}: {resp.status_code} {resp.text[:500]}")
            sys.exit(1)

    print(f"inserted={inserted} updated={updated}")


if __name__ == "__main__":
    main()
