#!/usr/bin/env python3
"""
Gold Standard polk letter J -- HONESTY CORRECTION (shard5, issue 19775, 2026-09-03).

The gap-only J rerun this session (scripts/gold_standard_polk_j_gap_rerun_shapira_v14_20260903.py)
wrote 235 bid_decisions rows using real_arv(), which prefers multi_county_auctions.assessed_value
whenever it is truthy. An adversarial refuter caught that 191 of those 235 rows have
assessed_value EXACTLY 100000.0 -- a known Polk ingestion placeholder/default present on 7978 of
8676 polk multi_county_auctions rows (92%) -- while a genuinely distinct market_value sat unused
in the same source row. Zero-variance factors (0.45/0.45/0.35) and identical arv=100000/
max_bid=52000 on 191 rows confirmed the fabrication-by-placeholder pattern (Honesty Protocol
ghost-success mode "e": fabricated/placeholder values).

Fix: for the 191 affected bid_decisions rows (pipeline_version=
'polk_j_shapira_v14_real_shard5_19775_gap_rerun', arv=100000.0 exactly), re-derive ARV using
market_value instead (multi_county_auctions.market_value, real per-row appraiser figure -- NOT
the 100000 placeholder) wherever market_value is present, real (>0), and not itself 100000.
Recompute repairs/max_bid/factors/ml_score from that corrected ARV. Rows with no usable
market_value are DELETED (not left with a fabricated arv) per BLANK > WRONG -- a missing
bid_decisions row is an honest J-letter gap, a placeholder-backed row is not.
"""
import os, sys, json, math, urllib.request, urllib.parse
from datetime import datetime, timezone
import xgboost as xgb

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
HEADERS_MIN = {**HEADERS, "Prefer": "return=minimal"}
MODEL_DIR = "/tmp/shapira"
COUNTY = "polk"
PIPELINE_VERSION_BAD = "polk_j_shapira_v14_real_shard5_19775_gap_rerun"
PIPELINE_VERSION_FIXED = "polk_j_shapira_v14_real_shard5_19775_placeholder_arv_fix"
PLACEHOLDER_ASSESSED = 100000.0


def rest_get(path, params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}?{qs}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, params, body):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}?{qs}", data=json.dumps(body).encode(),
                                  headers=HEADERS_MIN, method="PATCH")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def rest_delete(path, params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}?{qs}", headers=HEADERS_MIN, method="DELETE")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def safe_float(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def stage_model():
    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(f"{MODEL_DIR}/model.json") and os.path.getsize(f"{MODEL_DIR}/model.json") > 0:
        return
    rows = rest_get("shapira_models", {"select": "storage_bucket,storage_path_model,storage_path_features", "model_version": "eq.v14.0"})
    bucket = rows[0]["storage_bucket"]
    for local_name, remote_path in (("model.json", rows[0]["storage_path_model"]), ("features.json", rows[0]["storage_path_features"])):
        req = urllib.request.Request(f"{SUPABASE_URL}/storage/v1/object/{bucket}/{remote_path}", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(f"{MODEL_DIR}/{local_name}", "wb") as f:
            f.write(data)


def main():
    stage_model()
    booster = xgb.Booster()
    booster.load_model(f"{MODEL_DIR}/model.json")
    feature_order = json.load(open(f"{MODEL_DIR}/features.json"))["features"]

    bad = rest_get("bid_decisions", {
        "select": "id,case_number,parcel_id",
        "county_slug": f"eq.{COUNTY}",
        "pipeline_version": f"eq.{PIPELINE_VERSION_BAD}",
        "arv": f"eq.{PLACEHOLDER_ASSESSED}",
    })
    print(f"flagged placeholder-ARV rows: {len(bad)}")
    if len(bad) != 191:
        print(f"WARNING: expected 191 flagged rows per refuter evidence, found {len(bad)} -- proceeding with actual set")

    case_numbers = [r["case_number"] for r in bad]
    auctions = []
    for i in range(0, len(case_numbers), 50):
        chunk = case_numbers[i:i + 50]
        quoted = ",".join(f'"{c}"' for c in chunk)
        auctions += rest_get("multi_county_auctions", {
            "select": "case_number,parcel_id,market_value,assessed_value,judgment_amount,opening_bid,"
                      "beds,baths,sqft,bedrooms,bathrooms,living_area_sqft,year_built,homestead_exemption,"
                      "prior_sale_date,prior_sale_price,owner_name",
            "county": f"eq.{COUNTY}",
            "case_number": f"in.({quoted})",
        })
    auction_by_case = {a["case_number"]: a for a in auctions}

    fixed, deleted, skip_no_row = 0, 0, 0
    for r in bad:
        a = auction_by_case.get(r["case_number"])
        if not a:
            skip_no_row += 1
            continue
        market = safe_float(a.get("market_value"))
        if not market or market <= 0 or market == PLACEHOLDER_ASSESSED:
            rest_delete("bid_decisions", {"id": f"eq.{r['id']}"})
            deleted += 1
            continue

        arv = market
        judgment = safe_float(a.get("judgment_amount")) or 0.0
        opening = safe_float(a.get("opening_bid")) or 0.0
        year_built = a.get("year_built")
        property_age = (2026 - year_built) if year_built else None
        judgment_to_market = (judgment / arv) if arv else None
        owner = (a.get("owner_name") or "").upper()
        is_estate = 1 if ("ESTATE" in owner or "DECEASED" in owner) else 0
        is_entity = 1 if any(t in owner for t in (" LLC", " INC", " TRUST", " CORP", " LP")) else 0
        is_lender = 1 if any(t in owner for t in ("BANK", "MORTGAGE", "LENDING", "FINANCIAL")) else 0

        feat = {
            "judgment_amount_log1p": math.log1p(judgment) if judgment else 0.0,
            "opening_bid_log1p": math.log1p(opening) if opening else 0.0,
            "market_value_log1p": math.log1p(market),
            "assessed_value_log1p": math.log1p(market),
            "property_age": property_age,
            "judgment_to_market": judgment_to_market,
            "is_estate": is_estate, "is_entity": is_entity, "is_lender": is_lender,
            "county_target_enc": 0.7018022406234778,
        }
        fv = [[feat.get(k) if feat.get(k) is not None else float("nan") for k in feature_order]]
        dmat = xgb.DMatrix(fv, feature_names=feature_order, missing=float("nan"))
        ml_score = float(booster.predict(dmat)[0])

        repairs = max(5000.0, min(40000.0, round(arv * 0.08, 2)))
        base_bid = (arv * 0.70) - repairs - 10000
        min_profit = min(25000.0, arv * 0.15)
        max_bid = max(round(base_bid, 2), round(min_profit, 2), 1000.0)
        cma_distressed = round(arv * 0.80, 2)
        cma_resale = round(arv * 1.02, 2)

        age_score = min(0.5, (property_age or 30) / 100.0) if property_age is not None else 0.30
        loc_score = round(min(0.85, max(0.20, 0.45 + ((judgment_to_market or 1.0) - 1.0) * 0.10)), 4)
        prop_score = round(min(0.85, max(0.20, age_score + 0.15)), 4)
        owner_score = round(min(0.90, 0.35 + 0.20 * is_estate + 0.20 * is_entity + 0.25 * is_lender), 4)

        factors = {
            "distress_location": loc_score, "distress_property": prop_score, "distress_owner": owner_score,
            "cma_distressed": cma_distressed, "cma_resale": cma_resale,
        }
        profit = arv - max_bid - repairs
        body = {
            "arv": round(arv, 2),
            "arv_source": "shapira_v14_real_multi_county_auctions.market_value",
            "repairs": repairs, "repair_estimate": repairs,
            "max_bid": round(max_bid, 2),
            "ml_score": round(ml_score, 4),
            "factors": factors,
            "recommendation": "BID" if profit > 0 else "PASS",
            "confidence": 0.5,
            "pipeline_version": PIPELINE_VERSION_FIXED,
        }
        rest_patch("bid_decisions", {"id": f"eq.{r['id']}"}, body)
        fixed += 1

    print(f"fixed_with_real_market_value={fixed} deleted_no_real_value={deleted} skip_no_source_row={skip_no_row}")


if __name__ == "__main__":
    main()
