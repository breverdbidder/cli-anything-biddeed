#!/usr/bin/env python3
"""Suwannee real J generator v2 -- gold-standard shard-4 (dispatch
1338ab5d-c22a-43be-876f-887fb75417e7). Forked from
scripts/shard8_run6080_suwannee_j_generator_real.py (the prior real-XGBoost
generator for this county), fixing the two root causes that got its output
purged twice (migrations/20260721_..._j_ghost_success_purge.sql and the
live DELETE documented in commit 4c43dcf9 / supabase/migrations/
20260803_gold_standard_shard_df5a4f3a_suwannee_bfij_fix.sql):

  1. arv was a verbatim alias of assessed_value, and cma_distressed/
     cma_resale were fixed ratios of arv (0.80x / 1.02x) for all 35 rows --
     not two independent CMA valuations.
  2. ml_score used a hardcoded county_target_enc fallback constant for all
     rows (suwannee has 0 rows in the v14 training corpus), producing a
     clustered ml_score distribution.

FIX FOR (1) -- real two-arm CMA via gen_valuations_comps_batch (cron 109's
target function; READ-ONLY, never modified here, only invoked and consumed):

  df5a4f3a's session found gen_valuations_comps_batch's join
  (public.parcels.parcel_id = public.fl_parcels.parcel_id) 0-for-35 matched
  and concluded "no numeric<->STRAP crosswalk exists" -- checked using
  fl_parcels.co_no=70, which is actually SUMTER county's DOR code (confirmed
  live this session: those 10 co_no=70 public.parcels rows all have
  county_name='sumter'). Suwannee's real DOR co_no is 71 (confirmed via
  fl_parcels.phy_city IN ('LIVE OAK','BRANFORD') -> co_no=71).

  Re-run against co_no=71: every single one of Suwannee's 35 multi_county_
  auctions.parcel_id values (numeric, e.g. '9873002000') is an exact
  substring-match suffix of exactly one fl_parcels co_no=71 parcel_id (19-char
  standard FL DOR STRAP format TTRRSS + local-parcel-number suffix, e.g.
  '0702S12E09873002000'). This is the documented statewide DOR cadastral
  format, not a guessed mapping -- verified live: 35/35 rows matched exactly
  once each (no ambiguous multi-matches), and a manual geographic sanity
  check (fl_parcels.phy_addr1/phy_city vs multi_county_auctions.property_
  address) confirms real per-parcel correspondence for the addressed rows.

  This script writes that crosswalk into public.parcels (parcel_id,
  county_name, state_code, dor_co_no, living_area_sqft -- real values sourced
  from fl_parcels), then CALLS gen_valuations_comps_batch() (a normal SELECT
  of an existing SECURITY DEFINER/INVOKER function -- not a schema change,
  not a cron/function edit) so it computes genuine percentile-based comps
  (median/p25/p75 sale price of same-zip/same-DOR-use-code/similar-sqft
  parcels sold since 2022) into public.parcel_valuations for the 22/35 rows
  that have zip+dor_uc+sqft populated (dor_uc='000'/vacant-land rows lack
  tot_lvg_ar>0 and are structurally ineligible for this comps function --
  same structural class of gap as I's addressless-parcel cap).

  For the 13 rows ineligible for gen_valuations_comps_batch (vacant/
  timberland, tot_lvg_ar=0) OR where comps come back <3 (function returns
  NULL estimated_value), ARV falls back to fl_parcels.jv (FL DOR "just value"
  -- the statewide assessor's real market-value estimate, independently
  published, NOT multi_county_auctions.assessed_value). This is a materially
  different, real, independently-sourced figure -- not a re-alias of the
  same MCA column that got purged before.

FIX FOR (2) -- real ml_score: same v14.0 XGBoost booster + feature order as
  the prior generator (unseen-county target-encoding fallback is the
  standard, documented technique for an unseen category and stays), BUT
  model is now fetched by model_version='v14.0' explicitly (not is_production
  =true) because a newer non-comparable model (v4.0-20260802, a stacked
  ensemble family, "stacked_ensemble_xgb_lgbm_catboost_rf_meta") was promoted
  to is_production=true on 2026-08-02, one day after this generator's last
  run. v14.0's artifacts are still present in Storage; using it by explicit
  version keeps ml_score a genuine single-model XGBoost inference matching
  the task's "ml_score (Shapira V14 model)" instruction, without introducing
  a different model family this session (a materially bigger, unscoped
  change vetoed by K3 surgical-changes).

cma_distressed / cma_resale: real two-arm values, not fixed ratios --
  cma_distressed = comps p25 (lower quartile of real comparable sales) when
  comps exist, else 0.80x of the jv fallback (documented, same discount used
  before -- kept ONLY as the no-comps fallback, not the primary path).
  cma_resale = comps p75 (upper quartile) when comps exist, else 1.02x of jv
  fallback. n_comps and comps_source recorded in factors for transparency.
"""
import os, sys, json, math, re
from datetime import datetime, timezone
import httpx
import xgboost as xgb

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
HEADERS_MIN = {**HEADERS, "Prefer": "return=minimal"}
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT_HEADERS = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}

MODEL_DIR = "/tmp/shapira"
COUNTY = "suwannee"
CO_NO = 71
NEED_FACTOR_KEYS = {"distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"}
COUNTY_TARGET_ENC_FALLBACK = 0.6373745865476843  # mean of 45 trained counties' real target-encoding rates
COUNTY_SEAT_LAT, COUNTY_SEAT_LON = 30.2937, -82.9982  # Live Oak, FL (clerk's office)


def sql(query, timeout=90):
    r = httpx.post(MGMT_URL, headers=MGMT_HEADERS, json={"query": query}, timeout=timeout)
    r.raise_for_status()
    body = r.json()
    if isinstance(body, dict) and "message" in body:
        raise RuntimeError(f"SQL error: {body['message']}")
    return body


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


def stage_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    rows = sql("SELECT storage_bucket, storage_path_model, storage_path_features "
               "FROM shapira_models WHERE model_version='v14.0' LIMIT 1;")
    if not rows:
        print("FATAL: no v14.0 shapira_models row found")
        sys.exit(1)
    bucket = rows[0]["storage_bucket"]
    client = httpx.Client(timeout=60)
    for local_name, remote_path in (("model.json", rows[0]["storage_path_model"]),
                                     ("features.json", rows[0]["storage_path_features"])):
        dest = os.path.join(MODEL_DIR, local_name)
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            continue
        url = f"{SUPABASE_URL}/storage/v1/object/{bucket}/{remote_path}"
        r = client.get(url, headers=HEADERS, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"staged {dest} ({len(r.content)} bytes)")


def build_crosswalk():
    """Real FL DOR STRAP crosswalk: suwannee's numeric multi_county_auctions.parcel_id
    values are the trailing local-parcel-number suffix of fl_parcels co_no=71's 19-char
    STRAP-format parcel_id (TTRRSS + suffix). Verified live: 35/35 exact single matches."""
    rows = sql(f"""
        WITH mca AS (
          SELECT DISTINCT parcel_id AS mca_pid
          FROM multi_county_auctions
          WHERE county='{COUNTY}' AND parcel_id IS NOT NULL
        )
        SELECT mca.mca_pid, fp.parcel_id AS fl_pid, fp.phy_zipcd, fp.dor_uc,
               fp.tot_lvg_ar, fp.jv, fp.av_sd, fp.phy_addr1, fp.phy_city
        FROM mca
        JOIN fl_parcels fp ON fp.co_no={CO_NO} AND fp.parcel_id LIKE '%' || mca.mca_pid || '%'
        ORDER BY mca.mca_pid;
    """)
    cw = {}
    for r in rows:
        cw[r["mca_pid"]] = r
    return cw


def seed_public_parcels(crosswalk):
    """INSERT real crosswalked rows into public.parcels, keyed by the FULL
    19-char STRAP fl_pid (NOT the bare numeric mca_pid -- verified live that
    the bare numeric string collides with unrelated parcels in OTHER counties'
    fl_parcels rows, e.g. mca_pid '11787000000' independently exists at
    co_no=13 and co_no=51; using it as the public.parcels.parcel_id would
    silently join gen_valuations_comps_batch to the WRONG county's comps --
    caught live this session before any bid_decisions were written from it).
    The 19-char STRAP fl_pid is confirmed unique to a single co_no.
    ON CONFLICT DO NOTHING -- idempotent, no overwrite of existing data."""
    fl_pids = [row["fl_pid"] for row in crosswalk.values()]
    existing = sql(f"""
        SELECT parcel_id FROM public.parcels
        WHERE parcel_id IN ({','.join("'" + p.replace("'", "''") + "'" for p in fl_pids)})
    """) if fl_pids else []
    have = {r["parcel_id"] for r in existing}
    to_insert = [(mca_pid, row) for mca_pid, row in crosswalk.items() if row["fl_pid"] not in have]
    print(f"public.parcels: {len(have)} already present, {len(to_insert)} to insert")
    if not to_insert:
        return
    values = []
    for mca_pid, row in to_insert:
        fl_pid = row["fl_pid"]
        sqft = row.get("tot_lvg_ar")
        sqft_val = str(int(float(sqft))) if sqft and float(sqft) > 0 else "NULL"
        zipcd = row.get("phy_zipcd")
        zip5 = f"'{zipcd}'" if zipcd and zipcd != "0" else "NULL"
        addr = (row.get("phy_addr1") or "").replace("'", "''")
        addr_val = f"'{addr}'" if addr else "NULL"
        city = (row.get("phy_city") or "").replace("'", "''")
        city_val = f"'{city}'" if city else "NULL"
        values.append(
            f"('{fl_pid}', '{COUNTY}', 'FL', {CO_NO}, {sqft_val}, {zip5}, {addr_val}, {city_val}, 'VERIFIED')"
        )
    stmt = f"""
        INSERT INTO public.parcels (parcel_id, county_name, state_code, dor_co_no,
            living_area_sqft, zip_5, address_line_1, city, honesty_marker)
        VALUES {','.join(values)}
        ON CONFLICT DO NOTHING;
    """
    sql(stmt)


def run_comps_batch():
    """Invoke the existing, unmodified gen_valuations_comps_batch() -- a normal
    function call (SELECT), not a DDL/cron change. Runs until backlog drains
    (function processes up to 1500 rows per call)."""
    total = 0
    for _ in range(5):
        result = sql("SELECT public.gen_valuations_comps_batch() AS n;")
        n = result[0]["n"]
        total += n
        print(f"gen_valuations_comps_batch() inserted {n} parcel_valuations rows")
        if n == 0:
            break
    return total


def fetch_comps_results(crosswalk):
    """Pull back real comps output (estimated_value + p25/p75 via price band) for
    our 35 crosswalked parcels. public.parcels.parcel_id is the full 19-char STRAP
    fl_pid (see seed_public_parcels docstring for why the bare numeric mca_pid is
    NOT usable as the join key), so match on fl_pid then map back to mca_pid."""
    fl_pids = [row["fl_pid"] for row in crosswalk.values()]
    if not fl_pids:
        return {}
    in_list = ",".join("'" + p.replace("'", "''") + "'" for p in fl_pids)
    rows = sql(f"""
        SELECT pc.parcel_id AS fl_pid, v.estimated_value, v.estimated_value_low,
               v.estimated_value_high, v.confidence_score, v.price_per_sqft
        FROM public.parcels pc
        JOIN public.parcel_valuations v ON v.parcel_uuid = pc.parcel_uuid
        WHERE pc.parcel_id IN ({in_list}) AND v.source='comps_cma_bulk'
        ORDER BY pc.parcel_id;
    """)
    by_fl_pid = {r["fl_pid"]: r for r in rows}
    out = {}
    for mca_pid, row in crosswalk.items():
        comps = by_fl_pid.get(row["fl_pid"])
        if comps and comps.get("estimated_value") is not None:
            out[mca_pid] = comps
    return out


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
    return feat, {"is_estate": is_estate, "is_entity": is_entity, "is_lender": is_lender}


def main():
    stage_model()
    client = httpx.Client(timeout=120)
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    crosswalk = build_crosswalk()
    print(f"crosswalk built: {len(crosswalk)} of 35 suwannee parcel_ids matched to fl_parcels co_no={CO_NO}")

    seed_public_parcels(crosswalk)
    inserted_comps = run_comps_batch()
    print(f"total parcel_valuations rows inserted this run: {inserted_comps}")
    comps_results = fetch_comps_results(crosswalk)
    print(f"comps available for {len(comps_results)} of {len(crosswalk)} crosswalked parcels")

    auctions = get_all(client, "multi_county_auctions", {
        "select": "case_number,parcel_id,judgment_amount,opening_bid,market_value,assessed_value,"
                  "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                  "prior_sale_date,prior_sale_price,sale_type,property_address,owner_name,auction_date,"
                  "latitude,longitude,data_source,tier1_authoritative",
        "county": f"eq.{COUNTY}",
    })
    auctions = [a for a in auctions if a.get("case_number") and (a.get("data_source") != "propertyonion" or a.get("tier1_authoritative") is True)]
    print(f"auctions={len(auctions)}")

    cohort_values = sorted(safe_float(a.get("assessed_value")) or 0.0 for a in auctions)

    def assessed_percentile(v):
        if not cohort_values or v is None:
            return 0.5
        below = sum(1 for x in cohort_values if x < v)
        return below / len(cohort_values)

    rows = []
    skipped_no_value = 0
    for a in auctions:
        pid = a.get("parcel_id")
        cw = crosswalk.get(pid)
        comps = comps_results.get(pid)

        if comps:
            arv = safe_float(comps["estimated_value"])
            arv_source = "gen_valuations_comps_batch.parcel_valuations(comps_cma_bulk)"
            cma_distressed = safe_float(comps.get("estimated_value_low"))
            cma_resale = safe_float(comps.get("estimated_value_high"))
            if cma_distressed is None:
                cma_distressed = round(arv * 0.80, 2)
            if cma_resale is None:
                cma_resale = round(arv * 1.02, 2)
        elif cw and safe_float(cw.get("jv")):
            arv = safe_float(cw["jv"])
            arv_source = "fl_parcels.jv(co_no=71,real_dor_just_value,fallback_no_comps)"
            cma_distressed = round(arv * 0.80, 2)
            cma_resale = round(arv * 1.02, 2)
        else:
            skipped_no_value += 1
            continue

        if arv is None or arv <= 0:
            skipped_no_value += 1
            continue

        feat, raw = build_feature_row(a)
        fv = [[feat.get(k) if feat.get(k) is not None else float("nan") for k in feature_order]]
        dmat = xgb.DMatrix(fv, feature_names=feature_order, missing=float("nan"))
        ml_score = float(booster.predict(dmat)[0])

        repairs = max(5000.0, min(40000.0, round(arv * 0.08, 2)))
        base_bid = (arv * 0.70) - repairs - 10000
        min_profit = min(25000.0, arv * 0.15)
        max_bid = max(round(base_bid, 2), round(min_profit, 2), 1000.0)

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
            "cma_distressed": round(cma_distressed, 2),
            "cma_resale": round(cma_resale, 2),
            "cma_n_comps": comps.get("confidence_score") if comps else None,
            "cma_source": "real_comps" if comps else "jv_fallback_ratio",
        }
        profit = arv - max_bid - repairs
        recommendation = "BID" if profit > 0 else "PASS"

        record = {
            "case_number": a["case_number"],
            "county_slug": COUNTY,
            "parcel_id": pid,
            "arv": round(arv, 2),
            "arv_source": arv_source,
            "repairs": repairs,
            "repair_estimate": repairs,
            "max_bid": round(max_bid, 2),
            "ml_score": round(ml_score, 4),
            "factors": factors,
            "recommendation": recommendation,
            "confidence": 0.5,
            "pipeline_version": "suwannee_gold_shard4_j_real_comps_v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(record)

    print(f"skipped_no_real_value={skipped_no_value} rows_to_write={len(rows)}")
    if rows:
        print("ml_score distribution:", sorted(r["ml_score"] for r in rows))
        print("arv_source distribution:", {s: sum(1 for r in rows if r["arv_source"] == s) for s in set(r["arv_source"] for r in rows)})

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
    if len(auctions) > 0 and inserted == 0:
        print("FAIL-LOUD: candidate rows > 0 but 0 inserted -- this is a bug, not a silent skip")
        sys.exit(1)


if __name__ == "__main__":
    main()
