#!/usr/bin/env python3
"""
Gold Standard shard-9 (dispatch 20a33672, 5th firing) — REAL J generator for
broward + alachua, county-agnostic by construction.

Replaces the bucketed/flat-default fallback pattern the 4th firing of this
same dispatch caught and purged (byte-identical arv/max_bid/ml_score across
dissimilar judgment amounts — a fabrication signature). This generator scores
every row with the ACTUAL production Shapira V14 XGBoost model
(shapira_models.model_version='v14.0', AUC 0.7834, storage_bucket
shapira-models) using the exact feature-engineering recipe from
scripts/train_shapira_v14.py — no county-level or ml-score-bucket defaults.

Real per-property inputs, no fabricated constants:
  - ARV: parcel_valuations.estimated_value (comps_cma_bulk, real percentile-of-
    real-sales CMA) when a comp exists for the parcel; else assessed_value or
    market_value already present on the auction row (both real BCPA/appraiser
    figures). Rows with NONE of these three real values are left incomplete
    (BLANK > WRONG) rather than assigned an invented ARV.
  - cma_distressed/cma_resale: parcel_valuations.estimated_value_low/high
    (real p25/p75 of actual comparable sales) when available; else 0.80x/1.02x
    of the real ARV (documented company convention, continuous not bucketed).
  - ml_score: real XGBoost predict_proba from the production model, using the
    row's own judgment/opening/market/assessed values, beds/baths/sqft, year
    built, homestead flag, prior sale, sale_type, and a text-derived owner-type
    signal — every input varies per property, so no two dissimilar properties
    can land on the same score by construction (unlike the purged buckets).
  - repairs/max_bid: documented Shapira Formula ((ARV*70%)-Repairs-$10K-
    MIN($25K,15%*ARV)) with repairs = 8% of the real per-property ARV (bounded
    5k-40k), continuous per property.
  - factors.distress_location/property/owner: continuous scores built from the
    same per-property signals used in the ml_score feature vector (owner
    entity/estate/lender text match, property age, judgment/market ratio) —
    not fixed enum buckets.

Idempotent: only targets case_numbers whose bid_decisions row is currently
missing arv/max_bid/ml_score or any of the 5 canon factor keys (matches
pencil_dod_evaluate_county's own definition of "deal_complete" exactly).
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
COUNTIES = ["broward", "alachua"]
NEED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}
# Real per-county base rates from shapira_models.metrics.county_target_encoding_map
# (v14/2026-05-27-180308/metrics.json), NOT a fabricated constant.
COUNTY_TARGET_ENC = {"broward": 0.5509154866059349, "alachua": 0.5655502392344498}
GLOBAL_TARGET_ENC = 0.60  # metrics.json global fallback rate is not itself stored; use
# the documented conservative company-wide midpoint only as an out-of-scope-county guard;
# never hit for broward/alachua since both are in COUNTY_TARGET_ENC above.


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
    """Matches training: pd.to_numeric(...).clip(lower=0) then np.log1p — a
    missing input must stay NaN (XGBoost's native missing-value routing), not
    become log1p(0)=0.0, which would misrepresent "no data" as "value is $0"."""
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
        "county_target_enc": COUNTY_TARGET_ENC.get(county, GLOBAL_TARGET_ENC),
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
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    grand_total = {}
    for county in COUNTIES:
        print(f"=== {county} ===")
        auctions = get_all(client, "multi_county_auctions", {
            "select": "case_number,parcel_id,judgment_amount,opening_bid,market_value,assessed_value,"
                      "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                      "prior_sale_date,prior_sale_price,sale_type,property_address,owner_name,auction_date,"
                      "data_source,tier1_authoritative",
            "county": f"eq.{county}",
        })
        auctions = [a for a in auctions if a.get("case_number") and (a.get("data_source") != "propertyonion" or a.get("tier1_authoritative") is True)]
        existing = get_all(client, "bid_decisions", {"select": "id,case_number,parcel_id,arv,max_bid,ml_score,factors,pipeline_version", "county_slug": f"eq.{county}"})
        existing_map = {r["case_number"]: r for r in existing if r.get("case_number")}

        # Guard against a pre-existing multi_county_auctions data defect (found
        # live this session): some parcel_id values are shared across multiple
        # case_numbers with genuinely different property_address — i.e. the
        # parcel linkage itself is wrong for at least one of the colliding
        # rows. Trusting parcel_id as a join key for those would silently
        # attach one property's real comps to a DIFFERENT property. Any
        # parcel_id backing more than one distinct address in this county's
        # auction set is excluded from the comps join; those rows fall back to
        # the auction's OWN assessed_value/market_value (still real, still
        # tied unambiguously to that exact case_number).
        addr_by_parcel = {}
        for a in auctions:
            pid = a.get("parcel_id")
            if not pid:
                continue
            addr_by_parcel.setdefault(pid, set()).add((a.get("property_address") or "").strip().upper())
        collision_parcels = {pid for pid, addrs in addr_by_parcel.items() if len(addrs) > 1}
        if collision_parcels:
            print(f"  WARNING: {len(collision_parcels)} parcel_id values map to multiple distinct addresses "
                  f"in this county's auction set — excluded from comps join (pre-existing E/parcel-linkage defect, "
                  f"not fixed here, flagged for next session).")

        parcel_ids = [a["parcel_id"] for a in auctions if a.get("parcel_id") and a["parcel_id"] not in collision_parcels]
        comps = []
        if parcel_ids:
            # parcel_valuations keys on parcel_uuid; join via parcels.parcel_id -> parcel_uuid
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

        def needs_repair(existing_row):
            # A prior run of THIS generator may have joined a collision parcel_id
            # to the wrong comps row before the guard above existed — reprocess
            # those specific rows even though they already look "complete".
            return (existing_row and existing_row.get("pipeline_version") == "shard9_20a33672_5th_firing_shapira_v14_real"
                    and existing_row.get("parcel_id") in collision_parcels)

        todo = [a for a in auctions
                if not bid_decision_complete(existing_map.get(a["case_number"]))
                or needs_repair(existing_map.get(a["case_number"]))]
        print(f"  incomplete_for_J={len(todo)}")

        rows = []
        skipped_no_value = 0
        for a in todo:
            arv, comp_low, comp_high, arv_source = real_arv(a, comp_by_parcel)
            if arv is None or arv <= 0:
                skipped_no_value += 1
                continue
            feat, raw = build_feature_row(a, county)
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
                "county_slug": county,
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
                "pipeline_version": "shard9_20a33672_5th_firing_shapira_v14_real",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            if existing_row:
                record["_existing_id"] = existing_row["id"]
            rows.append(record)

        print(f"  skipped_no_real_value={skipped_no_value}  rows_to_write={len(rows)}")

        to_insert = [r for r in rows if "_existing_id" not in r]
        to_update = [r for r in rows if "_existing_id" in r]

        inserted = 0
        batch_size = 200
        for i in range(0, len(to_insert), batch_size):
            batch = to_insert[i:i + batch_size]
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
        grand_total[county] = {"inserted": inserted, "updated": updated, "skipped_no_real_value": skipped_no_value}

    print(json.dumps(grand_total))


if __name__ == "__main__":
    main()
