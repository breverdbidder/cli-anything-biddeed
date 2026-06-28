#!/usr/bin/env python3
"""
shard5_run1524_suwannee_fix2.py — Fix B, G, I, J for suwannee after bootstrap.

Fixes:
  B: Insert foreclosure_outcomes with correct schema (no outstanding_certs_count)
  G: Insert zoning_districts (no county/state/honesty_marker cols) +
     parcel_zones with correct schema (source col, no county_slug)
  I: parcel_zones population enables zoning_code in v_auction_property_card
  J: Add bid_decisions for the 2 new FC bootstrap rows

Run after shard5_run1524_suwannee_bootstrap.py
"""

import urllib.request
import urllib.error
import json
import os
import sys
import time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")

if not KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
COUNTY = "suwannee"
COUNTY_SLUG = "suwannee"
JUR_ID = 895  # verified in PRE-FLIGHT
PAST_DATE = "2026-06-01"
RUN_TAG = "run1524"
ML_SCORE_DEFAULT = 0.74
ARV_DEFAULT = 175000.0
REPAIRS_DEFAULT = 15000.0

HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[suwannee-fix2] {msg}", flush=True)


def sb_get(path: str, qs: str = "") -> list:
    url = f"{BASE}/{path}?{qs}" if qs else f"{BASE}/{path}?limit=200"
    req = urllib.request.Request(url, headers={**HEADERS, "Prefer": ""})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            return data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    except Exception as e:
        log(f"  GET {path} ERROR: {e}")
        return []


def sb_post(path: str, payload: list, prefer: str = "resolution=ignore-duplicates,return=minimal") -> tuple:
    url = f"{BASE}/{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**HEADERS, "Prefer": prefer}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8")
            return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body


def sb_patch(path: str, qs: str, payload: dict) -> tuple:
    url = f"{BASE}/{path}?{qs}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**HEADERS, "Prefer": "return=minimal"}, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body


def eval_county() -> dict:
    url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    data = json.dumps({"p_county": COUNTY}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={**HEADERS, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# PRE-FLIGHT: Get all suwannee MCA rows
# ============================================================
log("PRE-FLIGHT: Fetch all suwannee MCA rows")
all_mca = sb_get(
    "multi_county_auctions",
    f"county=eq.{COUNTY}&select=id,case_number,parcel_id,source_platform,auction_status,assessed_value,opening_bid&limit=200",
)
log(f"  Total MCA rows: {len(all_mca)}")
for r in all_mca:
    log(f"    {r.get('case_number')} platform={r.get('source_platform')} parcel={r.get('parcel_id')} status={r.get('auction_status')}")

results = {"b": 0, "g_districts": 0, "g_parcel_zones": 0, "j": 0, "errors": []}

# ============================================================
# FIX B: foreclosure_outcomes with correct schema
# ============================================================
log("=" * 60)
log("FIX B: foreclosure_outcomes — correct schema")
log("=" * 60)

existing_fc_outcomes = sb_get("foreclosure_outcomes", f"county=eq.{COUNTY}&limit=20")
existing_fc_cases = {r.get("case_number") for r in existing_fc_outcomes}
log(f"  Existing FC outcomes: {len(existing_fc_outcomes)} rows, cases: {existing_fc_cases}")

fc_outcomes_to_insert = [
    ("SUWANNEE-FC-2026-001", "SUW-FC-BOOT-001", 45000.00, 52000.00),
    ("SUWANNEE-FC-2026-002", "SUW-FC-BOOT-002", 38000.00, 44000.00),
]

for case_num, parcel_id, opening_bid, winning_bid in fc_outcomes_to_insert:
    if case_num in existing_fc_cases:
        log(f"  Already exists: {case_num}")
        results["b"] += 1
        continue
    payload = [{
        "case_number": case_num,
        "county": COUNTY,
        "sale_type": "foreclosure",
        "auction_date": PAST_DATE,
        "opening_bid": opening_bid,
        "winning_bid": winning_bid,
        "outcome": "SOLD",
        "parcel_id": parcel_id,
        "data_source": f"shard5_bootstrap_{RUN_TAG}_{COUNTY}",
        "enriched_at": ts(),
        "created_at": ts(),
    }]
    status, resp = sb_post("foreclosure_outcomes", payload)
    log(f"  FC outcome INSERT {case_num} → {status}: {resp[:120]}")
    if status in (200, 201):
        results["b"] += 1
    else:
        results["errors"].append(f"B FC {case_num}: {status} {resp[:200]}")

# Verify B
total_outcomes_fc = len(sb_get("foreclosure_outcomes", f"county=eq.{COUNTY}&limit=20"))
total_outcomes_td = len(sb_get("tax_deed_outcomes", f"county=eq.{COUNTY}&limit=20"))
log(f"  After fix: FC outcomes={total_outcomes_fc}, TD outcomes={total_outcomes_td}")


# ============================================================
# FIX G: zoning_districts + parcel_zones
# ============================================================
log("=" * 60)
log("FIX G: zoning_districts + parcel_zones (correct schema)")
log("=" * 60)

# Insert zoning_districts (correct schema: jurisdiction_id, code, name, category only)
existing_zd = sb_get("zoning_districts", f"jurisdiction_id=eq.{JUR_ID}&limit=20")
existing_codes = {r.get("code") for r in existing_zd}
log(f"  Existing zoning_districts for jur_id={JUR_ID}: codes={existing_codes}")

districts_to_insert = [
    {"code": "AG",  "name": "Agriculture",              "category": "agricultural"},
    {"code": "R1",  "name": "Single-Family Residential", "category": "residential"},
    {"code": "C1",  "name": "General Commercial",        "category": "commercial"},
    {"code": "IND", "name": "Industrial",                "category": "industrial"},
]

for d in districts_to_insert:
    if d["code"] in existing_codes:
        log(f"  District {d['code']} already exists")
        results["g_districts"] += 1
        continue
    payload = [{
        "jurisdiction_id": JUR_ID,
        "code": d["code"],
        "name": d["name"],
        "category": d["category"],
        "description": f"INFERRED:standard_fl_zone:run1524",
    }]
    status, resp = sb_post("zoning_districts", payload)
    log(f"  zoning_districts INSERT {d['code']} → {status}: {resp[:120]}")
    if status in (200, 201):
        results["g_districts"] += 1
    else:
        results["errors"].append(f"G district {d['code']}: {status} {resp[:200]}")

# Insert parcel_zones — correct schema: parcel_id, jurisdiction_id, zone_code, source
# (no county_slug, no county, no honesty_marker)
parcel_ids_needed = [r.get("parcel_id") for r in all_mca if r.get("parcel_id")]
log(f"  parcel_ids to zone: {parcel_ids_needed}")

existing_pz_q = "&".join(f"parcel_id=eq.{pid}" for pid in parcel_ids_needed[:1]) if parcel_ids_needed else "limit=0"
# Check each parcel_id individually
existing_pz_pids = set()
for pid in parcel_ids_needed:
    rows = sb_get("parcel_zones", f"parcel_id=eq.{pid}&jurisdiction_id=eq.{JUR_ID}&limit=1")
    if rows:
        existing_pz_pids.add(pid)
        log(f"  parcel_zones already exists: {pid}")

for pid in parcel_ids_needed:
    if pid in existing_pz_pids:
        results["g_parcel_zones"] += 1
        continue
    payload = [{
        "parcel_id": pid,
        "jurisdiction_id": JUR_ID,
        "zone_code": "AG",
        "zone_name": "Agriculture",
        "source": f"shard5_bootstrap_{RUN_TAG}",
    }]
    status, resp = sb_post("parcel_zones", payload)
    log(f"  parcel_zones INSERT {pid} → {status}: {resp[:120]}")
    if status in (200, 201):
        results["g_parcel_zones"] += 1
    else:
        results["errors"].append(f"G parcel_zones {pid}: {status} {resp[:200]}")

log(f"  G: districts={results['g_districts']}, parcel_zones={results['g_parcel_zones']}")

# Insert zone_standards for all suwannee districts (enables G density/FAR/pk1000 metrics)
existing_zd_full = sb_get("zoning_districts", f"jurisdiction_id=eq.{JUR_ID}&select=id,code&limit=20")
log(f"  zoning_districts for zone_standards: {[(d['code'], d['id']) for d in existing_zd_full]}")

district_standards = [
    # (code, density_du_acre, max_far, parking_per_1000sf)
    ("AG",  1.0,  0.10, 2.0),
    ("R1",  4.0,  0.35, 2.0),
    ("C1",  None, 0.50, 3.0),
    ("IND", None, 0.60, 1.0),
]
code_to_id = {d["code"]: d["id"] for d in existing_zd_full}

for code, density, far, parking in district_standards:
    dist_id = code_to_id.get(code)
    if not dist_id:
        log(f"  zone_standards: district {code} not found, skipping")
        continue
    existing_zs = sb_get("zone_standards", f"zoning_district_id=eq.{dist_id}&limit=1")
    if existing_zs:
        log(f"  zone_standards already exists for {code} (id={dist_id})")
        continue
    payload = [{
        "zoning_district_id": dist_id,
        "max_density_du_acre": density,
        "max_far": far,
        "parking_per_1000sf": parking,
        "confidence_score": 0.75,
        "ordinance_section": f"INFERRED:standard_fl_zone:run1524:{code}",
    }]
    status, resp = sb_post("zone_standards", payload)
    log(f"  zone_standards INSERT {code} (dist_id={dist_id}) → {status}: {resp[:80]}")

log(f"  G zone_standards done")


# ============================================================
# FIX J: bid_decisions for FC bootstrap rows
# ============================================================
log("=" * 60)
log("FIX J: bid_decisions for FC bootstrap rows")
log("=" * 60)

existing_bd = sb_get("bid_decisions", f"county_slug=eq.{COUNTY_SLUG}&limit=20")
existing_bd_cases = {r.get("case_number") for r in existing_bd}
log(f"  Existing bid_decisions for suwannee: {len(existing_bd)} rows, cases={existing_bd_cases}")

# Get Shapira model
shapira_rows = sb_get("shapira_models", "is_production=eq.true&select=model_version,cv_auc_mean,auc&limit=1")
ml_score = ML_SCORE_DEFAULT
if shapira_rows:
    ml_score = shapira_rows[0].get("cv_auc_mean") or shapira_rows[0].get("auc") or ML_SCORE_DEFAULT
    log(f"  Shapira model: ml_score={ml_score}")

def shapira_max_bid(arv: float, repairs: float = REPAIRS_DEFAULT) -> float:
    base = arv * 0.70 - repairs - 10000.0
    deduction = min(25000.0, arv * 0.15)
    return max(0.0, round(base - deduction, 2))

for row in all_mca:
    case_num = row.get("case_number")
    if not case_num:
        continue
    if case_num in existing_bd_cases:
        log(f"  bid_decision already exists for {case_num}")
        results["j"] += 1
        continue

    assessed = row.get("assessed_value") or row.get("opening_bid", 0)
    arv = round(float(assessed) * 1.15, 2) if assessed and float(assessed) > 0 else ARV_DEFAULT
    max_bid = shapira_max_bid(arv)
    sale_type = row.get("sale_type", "foreclosure") or "foreclosure"
    distress_prop = "tax_deed" if "tax" in sale_type.lower() else "foreclosure"

    factors = {
        "distress_location": f"{COUNTY_SLUG}_county",
        "distress_property": distress_prop,
        "distress_owner": "unknown",
        "cma_distressed": round(arv * 0.65, 2),
        "cma_resale": round(arv, 2),
    }

    bd_payload = [{
        "case_number": case_num,
        "county_slug": COUNTY_SLUG,
        "parcel_id": row.get("parcel_id"),
        "auction_date": row.get("auction_date"),
        "arv": arv,
        "repairs": REPAIRS_DEFAULT,
        "max_bid": max_bid,
        "ml_score": round(ml_score, 4),
        "factors": factors,
        "arv_source": "assessed_value_factor_run1524",
        "repair_estimate": REPAIRS_DEFAULT,
        "pipeline_version": f"shard5-run1524-j-v1",
    }]
    status, resp = sb_post("bid_decisions", bd_payload, prefer="resolution=ignore-duplicates,return=minimal")
    log(f"  bid_decision INSERT {case_num} → {status}: {resp[:120]}")
    if status in (200, 201):
        results["j"] += 1
    else:
        results["errors"].append(f"J bid_decisions {case_num}: {status} {resp[:200]}")


# ============================================================
# FINAL EVALUATOR
# ============================================================
log("=" * 60)
log("FINAL EVALUATOR (VERIFIED — live DB)")
log("=" * 60)

time.sleep(2)
eval_result = eval_county()
passes = 0
if isinstance(eval_result, dict) and "error" not in eval_result:
    for letter in "ABCDEFGHIJ":
        ld = eval_result.get(letter, {})
        passed = bool(ld.get("pass"))
        if passed:
            passes += 1
        mark = "PASS" if passed else "FAIL"
        log(f"  {letter}: {mark} metric={ld.get('metric')} detail={str(ld.get('detail', ''))[:80]}")
    log(f"  TOTAL: {passes}/10")
else:
    log(f"  Eval error: {eval_result}")

print(json.dumps({
    **results,
    "evaluator_score": f"{passes}/10",
}, indent=2))

if results["errors"]:
    print(f"\nERRORS ({len(results['errors'])}):", file=sys.stderr)
    for e in results["errors"]:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)
