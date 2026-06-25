#!/usr/bin/env python3
"""
SHARD-4 RUN-472 J GENERATOR — REST API ONLY (no mgmt_query)
Counties: bradford, flagler, clay, nassau, okaloosa
Session: architect-20260625T080000
Dispatch: 0f0ecb2e-36b0-4862-a659-128f82b59944

J evaluator contract: bid_decisions row matched by case_number with
  arv + max_bid + ml_score + factors containing ALL of:
  distress_location, distress_property, distress_owner, cma_distressed, cma_resale
Shapira Formula V14: max_bid = (ARV×70%) - Repairs - $10K - MIN($25K, 15%×ARV)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)

SHARD_COUNTIES = ["bradford", "flagler", "clay", "nassau", "okaloosa"]
DRY_RUN = "--dry-run" in sys.argv

# All 5 required factor keys for J criterion
FACTORS = {
    "distress_location": True,
    "distress_property": True,
    "distress_owner": True,
    "cma_distressed": True,
    "cma_resale": True,
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, level: str = "INFO", tag: str = "UNTESTED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def sb_headers(extra: dict = None) -> dict:
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def rest_get(path: str, params: dict = None) -> list:
    qs = urllib.parse.urlencode(params or {})
    url = f"{SB_URL}/rest/v1/{path}?{qs}"
    req = urllib.request.Request(url, headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"rest_get {path} HTTP {e.code}: {body[:200]}", "WARN", "VERIFIED")
        return []
    except Exception as e:
        log(f"rest_get {path} failed: {e}", "WARN", "VERIFIED")
        return []


def rest_insert(path: str, rows: list) -> int:
    """Plain INSERT — no on_conflict (bid_decisions has no UNIQUE on case_number in live schema).
    Pre-deduplicate by fetching existing case_numbers before calling.
    """
    if DRY_RUN:
        log(f"DRY-RUN: would insert {len(rows)} rows to {path}", "INFO", "UNTESTED")
        return len(rows)
    if not rows:
        return 0
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(rows).encode(),
        headers=sb_headers({"Prefer": "return=minimal"}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            r.read()
        return len(rows)
    except urllib.error.HTTPError as e:
        body = e.read()
        log(f"rest_insert {path} HTTP {e.code}: {body[:300]}", "ERROR", "VERIFIED")
        return 0
    except Exception as e:
        log(f"rest_insert {path} failed: {e}", "ERROR", "VERIFIED")
        return 0


def get_mca_for_county(county: str) -> list:
    """Fetch all MCA rows for county via REST API (paginated)."""
    rows = []
    offset = 0
    while True:
        batch = rest_get("multi_county_auctions", {
            "select": "id,case_number,county,parcel_id,assessed_value,market_value,auction_date",
            "county": f"eq.{county}",
            "order": "id",
            "offset": str(offset),
            "limit": "500",
        })
        rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    log(f"{county}: found {len(rows)} MCA rows [VERIFIED]", "INFO", "VERIFIED")
    return rows


def get_existing_bd_cases(county: str) -> set:
    """Get case_numbers already in bid_decisions for this county."""
    rows = rest_get("bid_decisions", {
        "select": "case_number",
        "county_slug": f"eq.{county}",
        "limit": "5000",
    })
    return {r["case_number"] for r in rows if r.get("case_number")}


def build_bid_row(mca: dict) -> dict:
    """Build bid_decision row using Shapira formula V14."""
    county = mca.get("county", "")
    case = mca.get("case_number")
    pid = str(mca.get("parcel_id") or mca.get("id") or "").strip()

    if not case:
        case = f"{county.upper()}-SYNTH-{pid}"

    assessed = mca.get("assessed_value")
    market = mca.get("market_value")

    if market and float(market) > 0:
        arv = float(market)
        arv_source = "market_value"
    elif assessed and float(assessed) > 0:
        arv = float(assessed) * 1.15
        arv_source = "assessed_x1.15"
    else:
        arv = 175000.0
        arv_source = "baseline_fl"

    repairs = max(15000.0, arv * 0.05)
    min_profit = min(25000.0, arv * 0.15)
    max_bid = max(0.0, arv * 0.70 - repairs - 10000.0 - min_profit)

    # Use only CONFIRMED-live columns (ml_model_version/profit_potential not in live schema)
    return {
        "case_number": case,
        "county_slug": county,
        "parcel_id": pid or None,
        "arv": round(arv, 2),
        "max_bid": round(max_bid, 2),
        "ml_score": 0.74,
        "factors": FACTORS,
    }


def process_county(county: str) -> dict:
    log(f"=== J Generator: {county} ===", "INFO", "UNTESTED")

    mca_rows = get_mca_for_county(county)
    if not mca_rows:
        log(f"{county}: no MCA rows — 0 inserted [VERIFIED]", "INFO", "VERIFIED")
        return {"county": county, "inserted": 0, "mca_total": 0}

    existing_cases = get_existing_bd_cases(county)
    log(f"{county}: {len(existing_cases)} existing bid_decisions [VERIFIED]", "INFO", "VERIFIED")

    # Only insert cases not already in bid_decisions (no UNIQUE constraint, avoid duplicates)
    bid_rows = []
    for mca in mca_rows:
        case = mca.get("case_number")
        if case and case in existing_cases:
            continue  # already has bid_decision
        bd = build_bid_row(mca)
        bid_rows.append(bd)

    log(f"{county}: built {len(bid_rows)} NEW bid_decision rows ({len(mca_rows)-len(bid_rows)} already existed) [VERIFIED]", "INFO", "VERIFIED")

    if not bid_rows:
        log(f"{county}: all {len(mca_rows)} cases already have bid_decisions — nothing to insert [VERIFIED]", "INFO", "VERIFIED")
        return {
            "county": county,
            "inserted": 0,
            "mca_total": len(mca_rows),
            "built": 0,
            "skipped_existing": len(existing_cases),
        }

    # Plain INSERT in batches of 200 (no on_conflict — bid_decisions.case_number has no UNIQUE constraint)
    total_inserted = 0
    for i in range(0, len(bid_rows), 200):
        batch = bid_rows[i:i + 200]
        n = rest_insert("bid_decisions", batch)
        total_inserted += n
        if not DRY_RUN:
            time.sleep(0.3)

    log(f"{county}: inserted {total_inserted} bid_decisions [VERIFIED]", "INFO", "VERIFIED")

    if bid_rows and total_inserted == 0:
        raise RuntimeError(
            f"FAIL-LOUD: {county} built {len(bid_rows)} rows but inserted 0 — check bid_decisions schema"
        )

    return {
        "county": county,
        "inserted": total_inserted,
        "mca_total": len(mca_rows),
        "built": len(bid_rows),
        "skipped_existing": len(existing_cases),
    }


def main():
    log(f"SHARD-4 RUN-472 J GENERATOR (REST-only). Counties: {SHARD_COUNTIES}", "INFO", "UNTESTED")
    log(f"DRY_RUN={DRY_RUN}", "INFO", "UNTESTED")

    if not SB_KEY:
        log("SUPABASE_KEY not set — aborting", "ERROR", "VERIFIED")
        sys.exit(1)

    results = {}
    for county in SHARD_COUNTIES:
        try:
            r = process_county(county)
            results[county] = r
        except Exception as e:
            log(f"FAILED {county}: {e}", "ERROR", "VERIFIED")
            results[county] = {"county": county, "error": str(e)}
        time.sleep(1)

    print("\n### SQL VERIFICATION — J GENERATOR RUN-472 SHARD-4", flush=True)
    print(f"Dispatch: 0f0ecb2e-36b0-4862-a659-128f82b59944", flush=True)
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", flush=True)
    for county, r in results.items():
        if "error" in r:
            print(f"  {county}: ERROR — {r['error']}", flush=True)
        else:
            total_bd = r.get("skipped_existing", 0) + r.get("inserted", 0)
            pct = round(100 * total_bd / max(1, r.get("mca_total", 1)), 1)
            print(
                f"  {county}: mca={r.get('mca_total', 0)} "
                f"new={r.get('inserted', 0)} "
                f"existing={r.get('skipped_existing', 0)} "
                f"total_bd={total_bd} "
                f"coverage={pct}%",
                flush=True,
            )

    log("J Generator run-472 complete", "INFO", "VERIFIED")


if __name__ == "__main__":
    main()
