#!/usr/bin/env python3
"""Wakulla real J growth backfill — forked from
scripts/shard7_wakulla_j_generator_real.py (itself forked from the audit-survived
scripts/shard8_run6080_suwannee_j_generator_real.py Shapira V14 pattern; suwannee's
case 4713 real inference is gold_standard_ultraloop_audit id 9478, survived=true).

Root cause this fixes: wakulla's auctions_total grew from 30 (the prior full-pass
scope) to 44 live this session. All 38 auctions that DO carry real assessed_value/
market_value already have complete, real-inference bid_decisions rows written by
shard7_wakulla_j_generator_real.py (pipeline_version=
wakulla_j_generator_5cd42fe0_shapira_v14_real) -- confirmed live this session by
querying bid_decisions for county_slug=wakulla and finding zero incomplete rows
among the 38 that exist. The remaining 6 auctions (2026-TXD-097, -117, -118, -120,
-122, 25-CA-105) have NO bid_decisions row at all, and all 6 have assessed_value AND
market_value both null in multi_county_auctions -- confirmed live this session.
This is the exact documented pre-existing exclusion pattern from the prior wakulla J
session (case 2026-TXD-097 is one of these 6, named explicitly in that prior run's
notes). This script re-confirms that fact for the current 44-row auction set and
performs zero writes for those 6 by construction (real_arv() returns None for all
of them, matching the shard7 script's skip behavior). No new writes are expected;
this script exists to prove -- not assume -- that the growth from 30->44 did not
introduce any new fixable J gap, per the "do not shortcut it" instruction.

arv formula kept IDENTICAL to the already-shipped wakulla arv fix (GREATEST(assessed_
value, market_value)) -- unchanged from shard7_wakulla_j_generator_real.py, per this
session's explicit instruction not to deviate from that accepted baseline.

county_target_enc: wakulla still has 0 rows in the v14 training corpus (confirmed
live this session by re-downloading metrics.json from the shapira-models storage
bucket bucket path v14/2026-05-27-180308/metrics.json and checking membership).
Uses the same mean-of-45-counties fallback (0.6374) as the prior wakulla/suwannee
generators.
"""
import os, sys, json, math, re
from datetime import datetime, timezone
import httpx
import xgboost as xgb

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
HEADERS_MIN = {**HEADERS, "Prefer": "return=minimal"}

MODEL_DIR = "/tmp/shapira"
COUNTY = "wakulla"
NEED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}
COUNTY_TARGET_ENC_FALLBACK = 0.6373745865476843  # mean of 45 trained counties' real target-encoding rates

# Crawfordville, FL -- Wakulla county seat / clerk's office. Identical to shard7.
COUNTY_SEAT_LAT, COUNTY_SEAT_LON = 30.2136, -84.3755


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
        "county_target_enc": COUNTY_TARGET_ENC_FALLBACK,
    }
    return feat, {
        "judgment": judgment, "opening": opening, "market": market, "assessed": assessed,
        "property_age": property_age, "judgment_to_market": judgment_to_market,
        "is_estate": is_estate, "is_entity": is_entity, "is_lender": is_lender,
    }


def real_arv(auction):
    # GREATEST(assessed_value, market_value) -- identical formula to the already-shipped
    # wakulla arv fix and to shard7_wakulla_j_generator_real.py. Confirmed live this
    # session as the accepted, non-fabricated baseline for wakulla specifically; do not
    # deviate from it.
    assessed = safe_float(auction.get("assessed_value")) or 0.0
    market = safe_float(auction.get("market_value")) or 0.0
    arv = max(assessed, market)
    if arv <= 0:
        return None, None
    source = "multi_county_auctions.assessed_value" if assessed >= market else "multi_county_auctions.market_value"
    return arv, source


def main():
    client = httpx.Client(timeout=120)
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    auctions = get_all(client, "multi_county_auctions", {
        "select": "case_number,parcel_id,judgment_amount,opening_bid,market_value,assessed_value,"
                  "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                  "prior_sale_date,prior_sale_price,sale_type,property_address,owner_name,auction_date,"
                  "latitude,longitude,data_source,tier1_authoritative,auction_status",
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
    existing_map = {r["case_number"]: r for r in existing if r.get("case_number")}
    print(f"auctions={len(auctions)} existing_bid_decisions={len(existing_map)}")

    # Growth-scoped repair: only auctions with NO bid_decisions row, or an existing row
    # that is incomplete (missing arv/max_bid/ml_score/factor keys), are in scope. The 38
    # rows already written by shard7_wakulla_j_generator_real.py are confirmed complete
    # live this session and are left untouched (no perturbation of already-fixed rows).
    todo = [a for a in auctions if not bid_decision_complete(existing_map.get(a["case_number"]))]
    print(f"incomplete_for_J={len(todo)}")
    for a in todo:
        print("  candidate:", a["case_number"], "status=", a.get("auction_status"),
              "assessed=", a.get("assessed_value"), "market=", a.get("market_value"))

    rows = []
    skipped_no_value = 0
    for a in todo:
        arv, arv_source = real_arv(a)
        if arv is None:
            skipped_no_value += 1
            print(f"  SKIP (no real assessed_value/market_value) {a['case_number']}")
            continue
        feat, raw = build_feature_row(a)
        fv = [[feat.get(k) if feat.get(k) is not None else float("nan") for k in feature_order]]
        dmat = xgb.DMatrix(fv, feature_names=feature_order, missing=float("nan"))
        ml_score = float(booster.predict(dmat)[0])

        if arv < 100_000:
            repairs = 25_000.0
        elif arv < 250_000:
            repairs = 20_000.0
        elif arv < 500_000:
            repairs = 15_000.0
        else:
            repairs = 12_000.0
        max_bid = max((arv * 0.7) - repairs - 10_000, min(25_000.0, arv * 0.15))

        cma_distressed = round(arv * 0.87, 2)
        cma_resale = round(arv * 1.12, 2)

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

        existing_row = existing_map.get(a["case_number"])
        record = {
            "case_number": a["case_number"],
            "county_slug": COUNTY,
            "parcel_id": a.get("parcel_id"),
            "arv": round(arv, 2),
            "arv_source": f"shapira_v14_real_{arv_source}",
            "repairs": round(repairs, 2),
            "repair_estimate": round(repairs, 2),
            "max_bid": round(max_bid, 2),
            "ml_score": round(ml_score, 4),
            "factors": factors,
            "recommendation": recommendation,
            "confidence": 0.5,
            "pipeline_version": "wakulla_j_growth_backfill_shapira_v14_real",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing_row:
            record["_existing_id"] = existing_row["id"]
        rows.append(record)

    print(f"skipped_no_real_value={skipped_no_value} rows_to_write={len(rows)}")
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
    print(f"FINAL: candidates={len(todo)} written={inserted + updated} genuinely_excluded_no_value={skipped_no_value}")


if __name__ == "__main__":
    main()
