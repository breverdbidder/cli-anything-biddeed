#!/usr/bin/env python3
"""GOLD STANDARD shard-7, dispatch ea6af08a-62cb-4bdb-b69d-224fbfac7d47, county=flagler.

Real J (deal_complete) generator for the 8 flagler auctions with ZERO existing
bid_decisions rows (26-007/012/034/040/046/050/058/063 TDC -- new tax_deed
auctions the J pipeline hadn't reached yet, not a data-quality problem). Forked
from scripts/shard3_run6080_santa_rosa_j_generator_real.py, the latest
adversarially-scrutinized real-XGBoost pattern in this repo.

SCOPE: this script only inserts rows for the 8 case_numbers with no existing
bid_decisions row. It does NOT touch flagler's other 140 existing bid_decisions
rows, even though a live audit this session found those rows carry the exact
ghost-success pattern flagged in commit 6a5a5cb0 (75 rows pipeline_version=
'shard3_inferred_v1' with constant ml_score=0.5000 and constant distress_owner/
location/property factors -- honestly self-tagged _honesty_marker:'INFERRED',
not claimed as real ML; 69 rows with null pipeline_version and only 2 distinct
bucketed ml_score values 0.62/0.74, constant distress_owner=0.55). Repairing
those 140 rows is out of this session's assigned scope (J gap was exactly 1
row) -- flagged as a named residual in the session report, not silently fixed
or silently ignored.

county_target_enc: flagler IS one of the 45 counties in the v14 training
corpus's county_target_encoding_map -- VERIFIED by downloading and parsing
shapira-models/v14/2026-05-27-180308/metrics.json directly (not assumed from
the dispatch brief, which guessed flagler was "almost certainly NOT" in the
corpus -- that guess was wrong; flagler's real trained rate is 0.7409638554216867).

distress_owner: flagler's multi_county_auctions.owner_name is NULL on every
row (VERIFIED, same situation as santa_rosa) -- uses fl_parcels.own_name via
parcel_id join as the real per-row fallback source, same technique as the
santa_rosa script. If a given row's parcel_id has no fl_parcels match, its
owner flags fall out to all-False (0/0/0), which is an honest "no signal
available" state, not a fabricated non-zero constant.

Location-distress reference point: real median lat/lon of flagler's own 148
geocoded auction rows (29.6469, -81.2088), computed live this session via SQL
percentile_cont -- not an externally-asserted county-seat coordinate.

market_value is NULL on all 8 target rows (VERIFIED) -- ARV computed from
assessed_value only, per task instruction to skip (not fabricate) rows with
neither signal. All 8 target rows have a real assessed_value on file.

Usage: python3 scripts/gold_standard_shard7_flagler_j_generator_real.py [--dry-run]
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
COUNTY = "flagler"
PIPELINE_TAG = "flagler_j_generator_shard7_ea6af08a_shapira_v14_real"

# Real per-county trained target-encoding rate, VERIFIED by downloading and
# parsing shapira-models v14 metrics.json county_target_encoding_map live
# this session (flagler IS in the 45-county training corpus).
COUNTY_TARGET_ENC = 0.7409638554216867

# Real median lat/lon of flagler's own 148 geocoded auction rows, computed
# live this session via SQL percentile_cont (not an asserted county-seat coord).
REF_LAT, REF_LON = 29.6469, -81.2088

# Only these 8 case_numbers -- VERIFIED live via SQL: the only flagler
# case_numbers with zero existing bid_decisions rows.
TARGET_CASE_NUMBERS = [
    "26-007 TDC", "26-012 TDC", "26-034 TDC", "26-040 TDC",
    "26-046 TDC", "26-050 TDC", "26-058 TDC", "26-063 TDC",
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

    auctions = get_all(client, "multi_county_auctions", {
        "select": "case_number,parcel_id,judgment_amount,opening_bid,market_value,assessed_value,"
                  "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                  "prior_sale_date,prior_sale_price,sale_type,property_address,owner_name,auction_date,"
                  "latitude,longitude,data_source,tier1_authoritative",
        "county": f"eq.{COUNTY}",
        "case_number": "in.(" + ",".join(f'"{c}"' for c in TARGET_CASE_NUMBERS) + ")",
    })
    print(f"target_auctions_fetched={len(auctions)} of {len(TARGET_CASE_NUMBERS)} expected")

    # Confirm none of these already have a bid_decisions row (idempotency / scope guard).
    existing = get_all(client, "bid_decisions", {
        "select": "id,case_number", "county_slug": f"eq.{COUNTY}",
        "case_number": "in.(" + ",".join(f'"{c}"' for c in TARGET_CASE_NUMBERS) + ")",
    })
    if existing:
        print(f"ABORT: {len(existing)} target case_numbers already have a bid_decisions row "
              f"-- this script is scoped to zero-row cases only: {[e['case_number'] for e in existing]}")
        sys.exit(1)

    parcel_ids = sorted({a["parcel_id"] for a in auctions if a.get("parcel_id")})
    own_name_by_parcel = {}
    if parcel_ids:
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_parcels", headers=HEADERS,
                        params={"parcel_id": "in.(" + ",".join(parcel_ids) + ")", "select": "parcel_id,own_name"}, timeout=60)
        r.raise_for_status()
        for row in r.json():
            if row.get("own_name"):
                own_name_by_parcel[row["parcel_id"]] = row["own_name"]
    print(f"own_name resolved for {len(own_name_by_parcel)} of {len(parcel_ids)} linked parcel_ids")

    # Percentile reference computed from the FULL flagler cohort (not just the
    # 8 targets) so the distress_property signal is genuinely comparative.
    all_flagler = get_all(client, "multi_county_auctions",
                           {"select": "assessed_value", "county": f"eq.{COUNTY}"})
    cohort_values = sorted(safe_float(a.get("assessed_value")) or 0.0 for a in all_flagler)

    def assessed_percentile(v):
        if not cohort_values or v is None:
            return 0.5
        below = sum(1 for x in cohort_values if x < v)
        return below / len(cohort_values)

    rows = []
    skipped_no_value = 0
    for a in auctions:
        arv, arv_source = real_arv(a)
        if arv is None or arv <= 0:
            skipped_no_value += 1
            print(f"  {a['case_number']}: SKIP -- no assessed_value or market_value on file")
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
        dist_mi = haversine_miles(lat, lon, REF_LAT, REF_LON) if (lat is not None and lon is not None) else None
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
            "pipeline_version": PIPELINE_TAG,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(record)
        print(f"  {a['case_number']}: arv={record['arv']} ml_score={record['ml_score']} "
              f"owner_source={'fl_parcels' if own_name else 'no_match'} loc={loc_score} prop={prop_score} owner={owner_score}")

    print(f"\nskipped_no_real_value={skipped_no_value} rows_to_write={len(rows)}")
    print("ml_score distribution:", sorted(r["ml_score"] for r in rows))
    print("distinct ml_score count:", len(set(r["ml_score"] for r in rows)))

    if dry_run:
        print("DRY RUN -- no writes performed")
        return

    if not rows:
        print("Nothing to insert.")
        return

    inserted = 0
    for i in range(0, len(rows), 200):
        batch = rows[i:i + 200]
        r = client.post(f"{SUPABASE_URL}/rest/v1/bid_decisions", headers=HEADERS_MIN, json=batch)
        if r.status_code in (200, 201, 204):
            inserted += len(batch)
        else:
            print(f"FAIL insert batch {i}: {r.status_code} {r.text[:500]}")
            sys.exit(1)
    print(f"inserted={inserted}")


if __name__ == "__main__":
    main()
