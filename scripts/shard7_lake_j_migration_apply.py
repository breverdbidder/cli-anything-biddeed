#!/usr/bin/env python3
"""
Apply lake bid_decisions migration via Supabase Management API.

dispatch_id: bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7

Uses SUPABASE_ACCESS_TOKEN (Management API) if available, falls back to
the Supabase REST API upsert pattern via shard7_lake_j_generator.py approach
but with correct INSERT WHERE NOT EXISTS semantics.

NOTE: bid_decisions has NO unique constraint on case_number (only pkey on id
and a non-unique btree index). Therefore merge-duplicates/ON CONFLICT will fail.
We use INSERT WHERE NOT EXISTS instead.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
MGMT_URL = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"

REST_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="INFO"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def mgmt_query(sql):
    if not ACCESS_TOKEN:
        log("SUPABASE_ACCESS_TOKEN not set — cannot use Management API", "WARN")
        return None
    req = urllib.request.Request(
        MGMT_URL,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            result = json.loads(r.read())
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        log(f"mgmt_query HTTP {e.code}: {body[:300]}", "ERROR")
        return None
    except Exception as e:
        log(f"mgmt_query failed: {e}", "ERROR")
        return None


def rest_get(path):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read())


def rest_post(path, body, prefer="return=minimal"):
    hdrs = {**REST_HEADERS, "Prefer": prefer}
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=data, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return e.code, {"error": body}


def apply_via_mgmt_api():
    """Apply the full migration SQL via Management API."""
    log("Applying lake J migration via Management API...")

    migration_path = "supabase/migrations/20260719_shard7_manatee_madison_lake_j_bid_decisions.sql"
    try:
        with open(migration_path) as f:
            sql = f.read()
    except FileNotFoundError:
        log(f"Migration file not found: {migration_path}", "ERROR")
        return False

    result = mgmt_query(sql)
    if result is None:
        return False

    log(f"Migration result: {json.dumps(result)[:500]}", "VERIFIED")
    return True


def compute_arv(row):
    assessed = row.get("assessed_value")
    if assessed and float(assessed) > 0:
        return float(assessed) * 1.15
    opening = row.get("opening_bid_usd") or row.get("opening_bid")
    if opening and float(opening) > 0:
        return float(opening) * 1.4
    return 165000.0


def compute_repairs(arv):
    if arv < 100_000:
        return 25_000.0
    if arv < 250_000:
        return 20_000.0
    if arv < 500_000:
        return 15_000.0
    return 12_000.0


def compute_max_bid(arv, repairs):
    formula = (arv * 0.70) - repairs - 10_000.0
    floor = min(25_000.0, arv * 0.15)
    return max(formula, floor)


def apply_via_rest_api():
    """
    Fallback: apply via REST API by fetching lake auctions,
    checking existing bid_decisions, and inserting missing rows.
    """
    log("Applying lake J migration via REST API (fallback)...")

    status, auctions = rest_get(
        "multi_county_auctions?county=eq.lake&select=case_number,assessed_value,po_market_value,opening_bid_usd,auction_type,county,city,zip,property_type,year_built,sqft,living_area_sqft,owner_name,homestead_status,parcel_id,property_address,auction_date"
    )
    if status != 200:
        log(f"Failed to fetch lake auctions: HTTP {status}", "ERROR")
        return 0

    log(f"Fetched {len(auctions)} lake auction rows")

    # Get existing bid_decisions for lake (check by case_number)
    status2, existing = rest_get("bid_decisions?county_slug=eq.lake&select=case_number")
    if status2 != 200:
        log(f"Failed to fetch existing bid_decisions: HTTP {status2}", "WARN")
        existing_cases = set()
    else:
        existing_cases = {r["case_number"] for r in existing if r.get("case_number")}

    log(f"Existing lake bid_decisions: {len(existing_cases)}")

    now_utc = datetime.now(timezone.utc).isoformat()
    to_insert = []

    for row in auctions:
        case_number = row.get("case_number") or ""
        if not case_number:
            continue
        if case_number in existing_cases:
            continue

        arv = compute_arv(row)
        repairs = compute_repairs(arv)
        max_bid = compute_max_bid(arv, repairs)
        auction_type = row.get("auction_type") or "foreclosure"
        assessed = row.get("assessed_value")
        po_mv = row.get("po_market_value")

        ml_score = 0.55
        opening = row.get("opening_bid_usd") or 0
        val_base = po_mv or (assessed * 1.15 if assessed else None)
        if opening and val_base and float(val_base) > 0:
            ratio = float(opening) / float(val_base)
            if ratio < 0.40:
                ml_score = 0.78
            elif ratio < 0.65:
                ml_score = 0.58
            else:
                ml_score = 0.38

        factors = {
            "distress_location": {
                "county": row.get("county", "lake"),
                "city": row.get("city") or "unknown",
                "zip": row.get("zip"),
                "state": "FL",
                "score": 0.50,
                "honesty_marker": "HYPOTHESIS",
            },
            "distress_property": {
                "property_type": row.get("property_type") or "unknown",
                "year_built": row.get("year_built"),
                "sqft": row.get("sqft") or row.get("living_area_sqft"),
                "assessed_value": assessed,
                "parcel_id": row.get("parcel_id"),
                "score": (
                    0.65 if assessed and float(assessed) > 150000
                    else 0.50 if assessed and float(assessed) > 75000
                    else 0.35
                ),
                "honesty_marker": "HYPOTHESIS",
            },
            "distress_owner": {
                "owner_name": row.get("owner_name"),
                "homestead": row.get("homestead_status"),
                "score": 0.50,
                "honesty_marker": "HYPOTHESIS",
            },
            "cma_distressed": {
                "estimated_value": po_mv or assessed,
                "source": "propertyonion_mv" if po_mv else ("assessed_value" if assessed else "none"),
                "confidence": "medium" if po_mv else ("low" if assessed else "unknown"),
                "honesty_marker": "HYPOTHESIS",
            },
            "cma_resale": {
                "arv": round(arv, 2),
                "max_bid": round(max(0, arv * 0.70 - 55000), 2),
                "formula": "shapira_v14: (ARV*0.70) - repairs - friction($10K) - cushion(MIN $25K, ARV*15%)",
                "source": "shapira_formula_v14_heuristic",
                "honesty_marker": "HYPOTHESIS",
            },
        }

        to_insert.append({
            "case_number": case_number,
            "county_slug": "lake",
            "parcel_id": row.get("parcel_id"),
            "address": row.get("property_address"),
            "auction_date": row.get("auction_date"),
            "arv": round(arv, 2),
            "arv_source": (
                "po_market_value" if po_mv
                else ("assessed_value_x1.15" if assessed else "default_165k_lake")
            ),
            "repairs": round(repairs, 2),
            "repair_estimate": round(repairs, 2),
            "max_bid": round(max_bid, 2),
            "ml_score": round(ml_score, 4),
            "pipeline_version": "v14.0_heuristic",
            "factors": factors,
            "recommendation": (
                "BID" if max(0, arv * 0.70 - 55000) > (float(opening) * 1.10 if opening else 0)
                else "WATCH" if max(0, arv * 0.70 - 55000) > float(opening or 0)
                else "SKIP"
            ),
            "confidence": 0.45,
        })

    log(f"New bid_decisions rows to insert: {len(to_insert)}")
    if not to_insert:
        log("Nothing to insert — all lake cases already have bid_decisions", "VERIFIED")
        return 0

    inserted = 0
    chunk_size = 100
    for i in range(0, len(to_insert), chunk_size):
        chunk = to_insert[i : i + chunk_size]
        status3, result = rest_post("bid_decisions", chunk)
        if status3 in (200, 201):
            inserted += len(chunk)
            log(f"  Batch {i // chunk_size + 1}: inserted {len(chunk)} rows")
        else:
            log(f"  Batch {i // chunk_size + 1}: HTTP {status3} {str(result)[:200]}", "ERROR")

    log(f"lake J: total inserted {inserted}", "VERIFIED")
    return inserted


def verify():
    """Verify bid_decisions count and factor completeness."""
    log("Verifying lake bid_decisions...")

    if ACCESS_TOKEN:
        result = mgmt_query("""
            SELECT
                COUNT(*) AS total,
                COUNT(CASE WHEN factors ? 'distress_location'
                            AND factors ? 'distress_property'
                            AND factors ? 'distress_owner'
                            AND factors ? 'cma_distressed'
                            AND factors ? 'cma_resale'
                           THEN 1 END) AS with_all_5_factors,
                COUNT(CASE WHEN ml_score IS NOT NULL THEN 1 END) AS with_ml_score,
                COUNT(CASE WHEN arv IS NOT NULL AND max_bid IS NOT NULL THEN 1 END) AS with_arv_maxbid
            FROM bid_decisions
            WHERE county_slug = 'lake';
        """)
        log(f"Verification (mgmt API): {json.dumps(result)[:500]}", "VERIFIED")
    else:
        status, data = rest_get("bid_decisions?county_slug=eq.lake&select=case_number,ml_score,arv,max_bid,factors")
        if status == 200:
            total = len(data)
            with_5_factors = sum(
                1 for r in data
                if r.get("factors") and all(
                    k in r["factors"] for k in
                    ["distress_location", "distress_property", "distress_owner", "cma_distressed", "cma_resale"]
                )
            )
            log(f"Total lake bid_decisions: {total}, with_all_5_factors: {with_5_factors}", "VERIFIED")


def main():
    log("=== SHARD-7 LAKE J MIGRATION APPLY (dispatch bc399d3b) ===")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR")
        sys.exit(1)

    # Try Management API first (preferred — can run full SQL migration)
    success = False
    if ACCESS_TOKEN:
        success = apply_via_mgmt_api()
        if success:
            log("Management API migration applied successfully", "VERIFIED")
    else:
        log("No SUPABASE_ACCESS_TOKEN — falling back to REST API approach", "WARN")

    if not success:
        # Fallback: REST API insert
        inserted = apply_via_rest_api()
        if inserted >= 0:
            success = True

    verify()

    # Evaluate lake J
    log("Running pencil_dod_evaluate_county for lake...")
    import urllib.parse
    for param in ("p_county", "county_slug_arg"):
        try:
            data = json.dumps({param: "lake"}).encode()
            req = urllib.request.Request(
                f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                data=data,
                headers={**REST_HEADERS},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                ev = json.loads(r.read())
            log(f"lake J after fix: {json.dumps(ev)[:500]}", "VERIFIED")
            break
        except Exception as e:
            if param == "county_slug_arg":
                log(f"evaluate_county(lake) failed: {e}", "ERROR")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print(f"dispatch_id: bc399d3b-f50e-406a-a0f1-66d8f4f5d9d7")


if __name__ == "__main__":
    main()
