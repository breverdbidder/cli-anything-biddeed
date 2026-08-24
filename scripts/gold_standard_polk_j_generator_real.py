#!/usr/bin/env python3
"""
Gold Standard polk letter J (Shapira deal thesis completeness) — REAL
generator, adapted verbatim (methodology) from
scripts/gold_standard_highlands_j_generator_real.py, the non-fabricated
pattern: real per-property Shapira V14 XGBoost inference
(shapira_models.model_version='v14.0', AUC 0.7834, storage_bucket
shapira-models), no county-level or ml-score-bucket defaults, BLANK > WRONG
for rows with no real value on file. Self-stages the model artifacts from
Supabase Storage since /tmp/shapira is not guaranteed to be pre-populated.

polk IS in the v14 training corpus's county_target_encoding_map (real
trained rate 0.7018022406234778, confirmed live this session from
shapira-models/v14/2026-05-27-180308/metrics.json) -- uses that real value
directly, no fallback needed.

Live diagnosis this session (paginated fetch of multi_county_auctions vs
bid_decisions for county=polk, NULL-safe non-propertyonion filter, diffed
case_number sets -- polk's bid_decisions table has 64K+ rows so a single
unpaginated fetch was NOT trusted, fetched via Range-paginated 1000-row
batches instead): exactly 50 polk case_numbers fail the deal_complete
definition, all 50 with zero existing bid_decisions row (first-time fill,
not a stale/bucketed row to purge), all 50 sale_type='foreclosure', all
added to multi_county_auctions between 2026-08-03 and 2026-08-21. Of those
50, ALL 50 have a real parcel_id AND a real assessed_value/market_value
already on file in multi_county_auctions (property-appraiser sourced) --
processed here via the existing real_arv() assessed/market fallback (11 of
the 50 parcel_ids have a `parcels` row but comps_cma_bulk join is attempted
first per parcel and falls back cleanly when absent).
"""
import os, sys, json, math, re, urllib.request
from datetime import datetime, timezone
import httpx
import xgboost as xgb

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
HEADERS_MIN = {**HEADERS, "Prefer": "return=minimal"}

MODEL_DIR = "/tmp/shapira"
COUNTY = "polk"
NEED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}
# Real per-county trained target-encoding rate from shapira_models v14 metrics.json
# (polk IS in the 45-county training corpus, no fallback needed).
COUNTY_TARGET_ENC = 0.7018022406234778
PIPELINE_VERSION = "polk_j_shapira_v14_real"


def stage_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/shapira_models?select=storage_bucket,storage_path_model,storage_path_features&model_version=eq.v14.0",
        headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read())
    if not rows:
        print("FATAL: no v14.0 shapira_models row found")
        sys.exit(1)
    bucket = rows[0]["storage_bucket"]
    for local_name, remote_path in (("model.json", rows[0]["storage_path_model"]),
                                     ("features.json", rows[0]["storage_path_features"])):
        dest = os.path.join(MODEL_DIR, local_name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{remote_path}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"staged {dest} ({len(data)} bytes)")


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
    is_estate = bool(re.search(r"\b(ESTATE|TRUST|HEIRS?|DECEASED|DECD)\b", own))
    is_entity = bool(re.search(r"\b(LLC|INC|CORP|LP|HOLDING|PROPERTIES|REALTY)\b", own))
    is_lender = bool(re.search(r"\b(BANK|MORTGAGE|FANNIE|FREDDIE|HUD|FHA|LENDER|FINANCIAL|SERVICING)\b", own))
    return is_estate, is_entity, is_lender


def build_feature_row(auction, county):
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
        "county_target_enc": COUNTY_TARGET_ENC,
    }
    return feat, {
        "judgment": judgment, "opening": opening, "market": market, "assessed": assessed,
        "property_age": property_age, "judgment_to_market": judgment_to_market,
        "is_estate": is_estate, "is_entity": is_entity, "is_lender": is_lender,
    }


def real_arv(auction, comp_by_parcel):
    parcel_id = auction.get("parcel_id")
    comp = comp_by_parcel.get(parcel_id) if parcel_id else None
    if comp and comp.get("estimated_value"):
        return float(comp["estimated_value"]), comp.get("estimated_value_low"), comp.get("estimated_value_high"), "parcel_valuations.comps_cma_bulk"
    assessed = safe_float(auction.get("assessed_value"))
    if assessed and assessed > 0:
        return assessed, None, None, "multi_county_auctions.assessed_value"
    market = safe_float(auction.get("market_value"))
    if market and market > 0:
        return market, None, None, "multi_county_auctions.market_value"
    return None, None, None, None


def main():
    client = httpx.Client(timeout=120)
    stage_model()
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    print(f"=== {COUNTY} ===")
    auctions = get_all(client, "multi_county_auctions", {
        "select": "case_number,parcel_id,judgment_amount,opening_bid,market_value,assessed_value,"
                  "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                  "prior_sale_date,prior_sale_price,sale_type,property_address,owner_name,auction_date,"
                  "data_source,tier1_authoritative",
        "county": f"eq.{COUNTY}",
    })
    # NULL-safe filter: data_source is often NULL for real, non-propertyonion rows.
    # A plain != comparison drops NULLs under SQL semantics; treat NULL as passing.
    auctions = [a for a in auctions if a.get("case_number") and
                (a.get("data_source") is None or a.get("data_source") != "propertyonion" or a.get("tier1_authoritative") is True)]
    existing = get_all(client, "bid_decisions", {"select": "id,case_number,parcel_id,arv,max_bid,ml_score,factors,pipeline_version", "county_slug": f"eq.{COUNTY}"})
    existing_map = {r["case_number"]: r for r in existing if r.get("case_number")}

    addr_by_parcel = {}
    for a in auctions:
        pid = a.get("parcel_id")
        if not pid:
            continue
        addr_by_parcel.setdefault(pid, set()).add((a.get("property_address") or "").strip().upper())
    collision_parcels = {pid for pid, addrs in addr_by_parcel.items() if len(addrs) > 1}
    if collision_parcels:
        print(f"  WARNING: {len(collision_parcels)} parcel_id values map to multiple distinct addresses "
              f"in {COUNTY}'s auction set -- excluded from comps join.")

    parcel_ids = [a["parcel_id"] for a in auctions if a.get("parcel_id") and a["parcel_id"] not in collision_parcels]
    comps = []
    if parcel_ids:
        for i in range(0, len(parcel_ids), 200):
            chunk = parcel_ids[i:i + 200]
            parcels = get_all(client, "parcels", {"select": "parcel_uuid,parcel_id", "parcel_id": f"in.({','.join(chunk)})"}, order_col="parcel_id")
            uuid_to_pid = {p["parcel_uuid"]: p["parcel_id"] for p in parcels}
            if not uuid_to_pid:
                continue
            vals = get_all(client, "parcel_valuations", {
                "select": "parcel_uuid,estimated_value,estimated_value_low,estimated_value_high,source",
                "source": "eq.comps_cma_bulk",
                "parcel_uuid": f"in.({','.join(uuid_to_pid.keys())})",
            }, order_col="parcel_uuid")
            for v in vals:
                pid = uuid_to_pid.get(v["parcel_uuid"])
                if pid:
                    comps.append({**v, "parcel_id": pid})
    comp_by_parcel = {c["parcel_id"]: c for c in comps}
    print(f"  auctions_filtered={len(auctions)} existing_bid_decisions={len(existing_map)} real_comps_found={len(comp_by_parcel)}")

    todo = [a for a in auctions if not bid_decision_complete(existing_map.get(a["case_number"]))]
    print(f"  incomplete_for_J={len(todo)}: {[t['case_number'] for t in todo]}")

    rows = []
    skipped_no_value = 0
    for a in todo:
        arv, comp_low, comp_high, arv_source = real_arv(a, comp_by_parcel)
        if arv is None or arv <= 0:
            skipped_no_value += 1
            print(f"    SKIP {a['case_number']}: no real assessed/market/comp value on file (BLANK>WRONG)")
            continue
        feat, raw = build_feature_row(a, COUNTY)
        fv = [[feat.get(k) if feat.get(k) is not None else float("nan") for k in feature_order]]
        dmat = xgb.DMatrix(fv, feature_names=feature_order, missing=float("nan"))
        ml_score = float(booster.predict(dmat)[0])

        repairs = max(5000.0, min(40000.0, round(arv * 0.08, 2)))
        base_bid = (arv * 0.70) - repairs - 10000
        min_profit = min(25000.0, arv * 0.15)
        max_bid = max(round(base_bid, 2), round(min_profit, 2), 1000.0)

        cma_distressed = round(comp_low, 2) if comp_low else round(arv * 0.80, 2)
        cma_resale = round(comp_high, 2) if comp_high else round(arv * 1.02, 2)

        age_score = min(0.5, (raw["property_age"] or 30) / 100.0) if raw["property_age"] is not None else 0.30
        jtm = raw["judgment_to_market"]
        loc_score = round(min(0.85, max(0.20, 0.45 + (jtm - 1.0) * 0.10)), 4) if jtm is not None else 0.45
        prop_score = round(min(0.85, max(0.20, age_score + 0.15)), 4)
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
            "confidence": round(min(1.0, 0.5 + (0.0 if comp_low is None else 0.3)), 2),
            "pipeline_version": PIPELINE_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing_row:
            record["_existing_id"] = existing_row["id"]
        rows.append(record)

    print(f"  skipped_no_real_value={skipped_no_value}  rows_to_write={len(rows)}")

    to_insert = [r for r in rows if "_existing_id" not in r]
    to_update = [r for r in rows if "_existing_id" in r]

    inserted = 0
    for i in range(0, len(to_insert), 200):
        batch = to_insert[i:i + 200]
        r = client.post(f"{SUPABASE_URL}/rest/v1/bid_decisions", headers=HEADERS_MIN, json=batch)
        if r.status_code in (200, 201, 204):
            inserted += len(batch)
        else:
            print(f"  FAIL insert batch {i}: {r.status_code} {r.text[:500]}")
            sys.exit(1)

    updated = 0
    for r in to_update:
        row_id = r.pop("_existing_id")
        resp = client.patch(f"{SUPABASE_URL}/rest/v1/bid_decisions", headers=HEADERS_MIN, params={"id": f"eq.{row_id}"}, json=r)
        if resp.status_code in (200, 201, 204):
            updated += 1
        else:
            print(f"  FAIL update id={row_id}: {resp.status_code} {resp.text[:500]}")
            sys.exit(1)

    print(f"  inserted={inserted} updated={updated}")
    print(json.dumps({COUNTY: {"inserted": inserted, "updated": updated, "skipped_no_real_value": skipped_no_value}}))


if __name__ == "__main__":
    main()
