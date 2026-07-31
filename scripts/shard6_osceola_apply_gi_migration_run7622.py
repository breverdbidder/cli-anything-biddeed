#!/usr/bin/env python3
"""
Apply the osceola G+I fix migration (shard-6, loop run 7622, dispatch 091fb9f9).

USAGE:
  SUPABASE_ACCESS_TOKEN=<sbp_token> python3 scripts/shard6_osceola_apply_gi_migration_run7622.py
  
  Or with dry-run:
  SUPABASE_ACCESS_TOKEN=<sbp_token> python3 scripts/shard6_osceola_apply_gi_migration_run7622.py --dry-run

This uses the Supabase Management API (same pattern as mgmt_sql.py) and is
designed to run in GitHub Actions via SUPABASE_ACCESS_TOKEN secret.

After running, it calls pencil_dod_evaluate_county('osceola') to verify the fix.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
DRY_RUN = "--dry-run" in sys.argv
DISPATCH_ID = "091fb9f9-f5a4-49b3-ad21-2472b3cc9f4a"
MIGRATION_FILE = "migrations/20260731_gold_standard_shard6_osceola_gi_fix_run7622.sql"

if not TOKEN:
    print("ERROR: SUPABASE_ACCESS_TOKEN must be set")
    sys.exit(1)


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg, tag="INFO"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def mgmt_query(sql: str, timeout: int = 120):
    """Run a SQL query via Supabase Management API."""
    if DRY_RUN:
        log(f"DRY-RUN SQL (first 200 chars): {sql[:200]}")
        return {"mock": True}

    url = f"https://api.supabase.com/v1/projects/{REF}/database/query"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            body = resp.read().decode()
            result = json.loads(body) if body else {}
            log(f"HTTP {status}: {str(result)[:300]}", "VERIFIED")
            return result
    except urllib.request.HTTPError as e:
        body = e.read().decode()
        log(f"HTTP ERROR {e.code}: {body[:500]}", "ERROR")
        raise


def run_migration():
    """Apply the G/I fix migration."""
    log("=== Applying osceola G+I fix migration ===")

    migration_path = os.path.join(os.path.dirname(__file__), "..", MIGRATION_FILE)
    migration_path = os.path.normpath(migration_path)

    with open(migration_path, "r") as f:
        sql = f.read()

    log(f"Migration file: {migration_path} ({len(sql)} chars)")
    result = mgmt_query(sql, timeout=60)
    log("Migration applied", "VERIFIED" if not DRY_RUN else "UNTESTED")
    return result


def verify_evaluation():
    """Run pencil_dod_evaluate_county and log result."""
    log("=== Verification: pencil_dod_evaluate_county('osceola') ===")

    eval_sql = "SELECT public.pencil_dod_evaluate_county('osceola') AS result;"
    result = mgmt_query(eval_sql, timeout=120)

    log(f"Evaluation: {json.dumps(result)}", "VERIFIED" if not DRY_RUN else "UNTESTED")
    return result


def verify_far_districts():
    """Check which osceola districts still have far_regulated=true after migration."""
    log("=== Verification: FAR-regulated districts still true ===")

    sql = """
SELECT zd.code, zd.name, j.name AS jurisdiction, zd.far_regulated, zs.max_far
FROM public.zoning_districts zd
JOIN public.jurisdictions j ON j.id = zd.jurisdiction_id
LEFT JOIN public.zone_standards zs ON zs.zoning_district_id = zd.id
WHERE lower(j.county) = 'osceola' AND j.state = 'FL'
  AND zd.far_regulated = true
ORDER BY j.name, zd.code;
"""
    result = mgmt_query(sql)
    log(f"FAR-true districts: {json.dumps(result)}", "VERIFIED" if not DRY_RUN else "UNTESTED")
    return result


def verify_incomplete_i():
    """Check how many osceola I cards are still incomplete."""
    log("=== Verification: Incomplete I cards ===")

    sql = """
SELECT 
    COUNT(*) AS total_mca,
    COUNT(*) FILTER (
        WHERE mca.latitude IS NOT NULL 
          AND mca.longitude IS NOT NULL
          AND (mca.assessed_value IS NOT NULL OR mca.market_value IS NOT NULL)
          AND EXISTS (
              SELECT 1 FROM public.parcel_zones pz 
              WHERE pz.parcel_id = mca.parcel_id AND pz.zone_code IS NOT NULL
          )
    ) AS card_complete,
    COUNT(*) FILTER (
        WHERE mca.latitude IS NULL OR mca.longitude IS NULL
          OR (mca.assessed_value IS NULL AND mca.market_value IS NULL)
    ) AS missing_geo_or_value,
    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1 FROM public.parcel_zones pz 
            WHERE pz.parcel_id = mca.parcel_id AND pz.zone_code IS NOT NULL
        )
    ) AS missing_zone
FROM public.multi_county_auctions mca
WHERE lower(mca.county) = 'osceola'
  AND mca.parcel_id IS NOT NULL;
"""
    result = mgmt_query(sql)
    log(f"I card completeness: {json.dumps(result)}", "VERIFIED" if not DRY_RUN else "UNTESTED")
    return result


def main():
    log(f"=== SHARD-6 osceola G+I apply+verify (dispatch {DISPATCH_ID}, run 7622) ===")

    if DRY_RUN:
        log("DRY-RUN MODE — no writes to DB")

    run_migration()
    time.sleep(2)

    far_result = verify_far_districts()
    i_result = verify_incomplete_i()
    eval_result = verify_evaluation()

    log("=== SUMMARY ===")
    log(f"Migration: {'DRY-RUN (not applied)' if DRY_RUN else 'APPLIED'}")
    log(f"FAR districts still regulated: {json.dumps(far_result)[:300]}")
    log(f"I card status: {json.dumps(i_result)[:300]}")
    log(f"Final evaluation: {json.dumps(eval_result)[:500]}")


if __name__ == "__main__":
    main()
