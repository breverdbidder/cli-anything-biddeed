#!/usr/bin/env python3
"""Lake J (deal_complete) fix, shard-2 continuation (dispatch
5f3a88a5-19bc-4d64-a3b6-fba1e561f75b, loop run 11435).

Scope: the 5 rows this same session's E-fix (scripts/shard14_lake_e_ownername_match.py,
live run) newly linked to a real parcel_id/address/assessed_value via the Lake PA
ArcGIS FieldMap OwnerName-match method (2023CA003042, 2024CA001596, 2025CA002056,
2025CA002465, 2017CA000729). None of the 5 had a bid_decisions row before this
script ran (verified via a live SELECT). Same generator/model artifact/
non-fabrication contract as the prior lake_j_generator_ifollowup_* scripts, single
new case-number scope for this session's E-fix output.

Forked from scripts/lake_j_generator_ifollowup_1row_002152.py.
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
COUNTY = "lake"
NEED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}
REPAIR_TAG = "lake_j_generator_shard2_5f3a88a5_efollowup_5row_shapira_v14_real"

COUNTY_TARGET_ENC = 0.6406727828746177

TARGET_CASE_NUMBERS = [
    "2023CA003042",
    "2024CA001596",
    "2025CA002056",
    "2025CA002465",
    "2017CA000729",
]


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


def build_feature_row(auction, own_name_override=None):
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

    is_estate, is_entity, is_lender = owner_flags(own_name_override or auction.get("owner_name"))

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
        "county_target_enc": COUNTY_TARGET_ENC,
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
    dry_run = "--dry-run" in sys.argv
    client = httpx.Client(timeout=120)
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    case_list = ",".join(TARGET_CASE_NUMBERS)
    auctions = get_all(client, "multi_county_auctions", {
        "select": "case_number,parcel_id,judgment_amount,opening_bid,market_value,assessed_value,"
                  "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                  "prior_sale_date,prior_sale_price,sale_type,property_address,owner_name,auction_date,"
                  "latitude,longitude,data_source,tier1_authoritative",
        "county": f"eq.{COUNTY}",
        "case_number": f"in.({case_list})",
    })
    print(f"fetched {len(auctions)} of {len(TARGET_CASE_NUMBERS)} target lake auctions")
    if len(auctions) != len(TARGET_CASE_NUMBERS):
        print("ERROR: fetched count does not match target scope — aborting to avoid silent gap", file=sys.stderr)
        sys.exit(1)

    parcel_ids = sorted({a["parcel_id"] for a in auctions if a.get("parcel_id")})
    own_name_by_parcel = {}
    for i in range(0, len(parcel_ids), 100):
        batch = parcel_ids[i:i + 100]
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_parcels", headers=HEADERS,
                        params={"parcel_id": "in.(" + ",".join(batch) + ")", "select": "parcel_id,own_name"}, timeout=60)
        r.raise_for_status()
        for row in r.json():
            if row.get("own_name"):
                own_name_by_parcel[row["parcel_id"]] = row["own_name"]
    print(f"own_name resolved for {len(own_name_by_parcel)} of {len(parcel_ids)} linked parcel_ids")

    lats = sorted(safe_float(a.get("latitude")) for a in auctions if a.get("latitude") is not None)
    lons = sorted(safe_float(a.get("longitude")) for a in auctions if a.get("longitude") is not None)
    ref_lat = lats[len(lats) // 2] if lats else 28.7
    ref_lon = lons[len(lons) // 2] if lons else -81.7
    print(f"reference point (median of gap-row geocodes): {ref_lat}, {ref_lon}")

    cohort_values = sorted(safe_float(a.get("assessed_value")) or 0.0 for a in auctions)

    def assessed_percentile(v):
        if not cohort_values or v is None:
            return 0.5
        below = sum(1 for x in cohort_values if x < v)
        return below / len(cohort_values)

    existing = get_all(client, "bid_decisions", {
        "select": "id,case_number,parcel_id,arv,max_bid,ml_score,factors,pipeline_version",
        "case_number": f"in.({case_list})",
    })
    existing_map = {r["case_number"]: r for r in existing if r.get("case_number")}
    print(f"auctions={len(auctions)} existing_bid_decisions_in_scope={len(existing_map)}")

    rows = []
    skipped_no_value = 0
    for a in auctions:
        arv, arv_source = real_arv(a)
        if arv is None or arv <= 0:
            skipped_no_value += 1
            continue
        own_name = own_name_by_parcel.get(a.get("parcel_id"))
        feat, raw = build_feature_row(a, own_name_override=own_name)
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
        dist_mi = haversine_miles(lat, lon, ref_lat, ref_lon) if (lat is not None and lon is not None) else None
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
            "repairs": repairs,
            "repair_estimate": repairs,
            "max_bid": round(max_bid, 2),
            "ml_score": round(ml_score, 4),
            "factors": factors,
            "recommendation": recommendation,
            "confidence": 0.5,
            "pipeline_version": REPAIR_TAG,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing_row:
            record["_existing_id"] = existing_row["id"]
        rows.append(record)

    print(f"skipped_no_real_value={skipped_no_value} rows_to_write={len(rows)}")
    print("ml_score distribution:", sorted(r["ml_score"] for r in rows))
    print("distinct ml_score count:", len(set(r["ml_score"] for r in rows)))

    if skipped_no_value > 0:
        print(f"ERROR: {skipped_no_value} target rows had no real assessed/market value — "
              f"scope was supposed to guarantee all rows have real assessed_value. Aborting.", file=sys.stderr)
        sys.exit(1)

    if dry_run:
        print("DRY RUN — no writes performed")
        return

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

    if inserted + updated != len(rows):
        print(f"ERROR: wrote {inserted + updated} but expected {len(rows)} — fail-loud, do not silently swallow", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
