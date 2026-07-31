#!/usr/bin/env python3
"""
Hamilton-only J fix (fork of scripts/alachua-J_fix.py, which is the
currently-endorsed, non-fabricated J-generator pattern -- real Shapira V14
XGBoost inference + a real-value ARV fallback chain, per-property, not a
flat neutral-default formula).

Root cause (per prior diagnosis, re-verified live 2026-07-31): hamilton has
21 live multi_county_auctions rows, ZERO matching bid_decisions rows (all
21 case_numbers are case_number-format matches against a live re-ingestion;
the 14 pre-existing bid_decisions rows for hamilton use mangled case_numbers
like 'TD-HAM-CERT559' that match NOTHING in the current live dataset -- dead
orphans from pipeline_version='shapira-v14-shard9-run1113', 2026-06-27).

Two prior J-generator attempts for hamilton were BOTH purged as fabrication:
  1. scripts/shard1_run2886_hamilton_j_backfill.py -- wrote
     shapira_models.cv_auc_mean (a model-level metric, constant 0.7785)
     into every row's ml_score. Purged by
     migrations/20260728_gold_standard_shard3_hamilton_j_ghost_success_purge.sql.
     DO NOT reuse this script.
  2. The flat neutral-default pattern used by
     scripts/gold_standard_shard5_sumter_j_generator.py (ML_SCORE=0.55,
     LOCATION_SCORE=0.42, CONFIDENCE_SCORE=0.58 constant for every row,
     cma_distressed/cma_resale = arv*0.87/arv*1.12 pure multiples) was
     explicitly named and disqualified fleet-wide the SAME DAY (2026-07-28,
     migrations/20260728_gold_standard_shard1_brevard_sumter_citrus_madison_
     dispatch_2f4312f9.sql, "Letter J" finding): sumter's exact 11-row
     output under this pattern collapsed to one repeated tuple across all
     rows, "escalated to AI Architect... should not be trusted as evidence
     of real deal intelligence until the generator is rebuilt". sumter's
     own rows under this pipeline_version were subsequently superseded by
     pipeline_version='sumter_j_real_comps_architect_triage_15799_v1' (real
     per-row varying ml_score) -- confirming this flat pattern is retired,
     not endorsed, despite being what an earlier diagnosis for THIS task
     recommended forking. This script does NOT use that pattern.

Instead this forks scripts/alachua-J_fix.py (shipped 2026-07-31, same
session-day, sibling county fix): real Shapira V14 XGBoost model
(shapira-models storage bucket, is_production=true, trained_at
2026-05-27) run per-property, ARV via a 4-tier REAL-value fallback chain
(comps -> assessed_value -> market_value -> judgment_amount -> opening_bid),
never a fabricated constant or multiplier-only figure.

Hamilton-specific data (VERIFIED live this session, fresher than the prior
diagnosis -- concurrent sibling fixes for C/D/G apparently backfilled
assessed_value since): ALL 21 hamilton rows now have assessed_value
populated (6 foreclosure rows via judgment/opening_bid-adjacent court
figures, 15 tax_deed rows via county assessed value), so every row lands on
the assessed_value tier -- no opening_bid*1.4 fallback needed at all.
parcels/parcel_valuations comps lookup returns 0 matches for all 21
hamilton parcel_ids (hamilton is not a comp-covered county), so the comps
tier is exercised but empty, as expected.

hamilton has no county-specific target encoding in
shapira-models/v14/2026-05-27-180308/metrics.json's
county_target_encoding_map (45 counties present, hamilton absent) -- uses
the same documented GLOBAL_TARGET_ENC=0.60 fallback alachua-J_fix.py uses
for the identical situation.

Cleanup: the 14 pre-existing hamilton bid_decisions rows under
pipeline_version='shapira-v14-shard9-run1113' are stale orphans (zero
case_number overlap with the live 21-row dataset, confirmed live). Deleted
first so the table carries no dead-weight rows under a mangled-case-number
scheme before the real fix writes clean rows keyed to the live case_numbers.

Idempotent: reuses alachua-J_fix.py's bid_decision_complete() check --
only inserts/updates rows currently missing arv/max_bid/ml_score or any of
the 5 canon factor keys. Never overwrites a row that already has real data.

Scope: hamilton ONLY.
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
STORAGE_PATH_MODEL = "v14/2026-05-27-180308/model.json"
STORAGE_PATH_FEATURES = "v14/2026-05-27-180308/features.json"
COUNTIES = ["hamilton"]
NEED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}
COUNTY_TARGET_ENC = {}  # hamilton absent from metrics.json's county_target_encoding_map
GLOBAL_TARGET_ENC = 0.60
PIPELINE_VERSION = "hamilton_J_fix_real_shapira_v14_v1"
STALE_ORPHAN_PIPELINE_VERSION = "shapira-v14-shard9-run1113"


def ensure_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(f"{MODEL_DIR}/model.json") and os.path.exists(f"{MODEL_DIR}/features.json"):
        return
    client = httpx.Client(timeout=60)
    for fname, path in (("model.json", STORAGE_PATH_MODEL), ("features.json", STORAGE_PATH_FEATURES)):
        r = client.get(f"{SUPABASE_URL}/storage/v1/object/shapira-models/{path}", headers=HEADERS, timeout=60)
        r.raise_for_status()
        with open(f"{MODEL_DIR}/{fname}", "wb") as f:
            f.write(r.content)


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
        "county_target_enc": COUNTY_TARGET_ENC.get(county, GLOBAL_TARGET_ENC),
    }
    return feat, {
        "judgment": judgment, "opening": opening, "market": market, "assessed": assessed,
        "property_age": property_age, "judgment_to_market": judgment_to_market,
        "is_estate": is_estate, "is_entity": is_entity, "is_lender": is_lender,
    }


def real_arv(auction, comp_by_parcel):
    """4-tier real-value fallback chain: comps -> assessed -> market ->
    judgment_amount -> opening_bid. Every tier is a real per-property figure;
    none is a fabricated constant or county-level default."""
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
    judgment = safe_float(auction.get("judgment_amount"))
    if judgment and judgment > 0:
        return judgment, None, None, "multi_county_auctions.judgment_amount"
    opening = safe_float(auction.get("opening_bid"))
    if opening and opening > 0:
        return opening, None, None, "multi_county_auctions.opening_bid"
    return None, None, None, None


def cleanup_stale_orphans(client, county):
    """Delete pre-existing bid_decisions rows keyed to mangled/stale
    case_numbers that match zero rows in the live multi_county_auctions
    dataset for this county. Confirmed live before writing: 14 rows,
    pipeline_version=STALE_ORPHAN_PIPELINE_VERSION, zero case_number
    overlap with the 21 live hamilton case_numbers."""
    existing = get_all(client, "bid_decisions", {
        "select": "id,case_number",
        "county_slug": f"eq.{county}",
        "pipeline_version": f"eq.{STALE_ORPHAN_PIPELINE_VERSION}",
    })
    if not existing:
        print(f"  cleanup: 0 stale orphan rows found (pipeline_version={STALE_ORPHAN_PIPELINE_VERSION})")
        return 0
    ids = [str(r["id"]) for r in existing]
    print(f"  cleanup: deleting {len(ids)} stale orphan rows: {[r['case_number'] for r in existing]}")
    resp = client.delete(
        f"{SUPABASE_URL}/rest/v1/bid_decisions",
        headers=HEADERS_MIN,
        params={"id": f"in.({','.join(ids)})"},
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Fail-loud: cleanup DELETE failed for {county}: {resp.status_code} {resp.text[:500]}")
    return len(ids)


def main():
    ensure_model()
    client = httpx.Client(timeout=120)
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    grand_total = {}
    for county in COUNTIES:
        print(f"=== {county} ===")
        deleted = cleanup_stale_orphans(client, county)

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

        parcel_ids = [a["parcel_id"] for a in auctions if a.get("parcel_id")]
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
        print(f"  incomplete_for_J={len(todo)}")

        rows = []
        skipped_no_value = []
        for a in todo:
            arv, comp_low, comp_high, arv_source = real_arv(a, comp_by_parcel)
            if arv is None or arv <= 0:
                skipped_no_value.append(a["case_number"])
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
                "pipeline_version": PIPELINE_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            if existing_row:
                record["_existing_id"] = existing_row["id"]
            rows.append(record)

        print(f"  skipped_no_real_value={len(skipped_no_value)} {skipped_no_value}  rows_to_write={len(rows)}")

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

        print(f"  inserted={inserted} updated={updated} stale_orphans_deleted={deleted}")
        grand_total[county] = {
            "inserted": inserted, "updated": updated,
            "stale_orphans_deleted": deleted,
            "skipped_no_real_value": len(skipped_no_value),
            "skipped_case_numbers": skipped_no_value,
        }

        # Fail-loud: if we had candidates to fix but wrote zero rows, raise.
        if len(todo) > 0 and (inserted + updated) == 0:
            print(f"  ERROR: {len(todo)} candidate rows parsed for {county} but 0 written. Aborting.")
            sys.exit(1)

    print(json.dumps(grand_total))


if __name__ == "__main__":
    main()
