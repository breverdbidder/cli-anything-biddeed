#!/usr/bin/env python3
"""GOLD STANDARD dispatch 0c4df455-e5d2-4d65-9237-0d35132b0e53, loop run 6253.

Bay County C/D/I/J backfill — shard-9.

Applies the migration SQL at migrations/20260724_gold_standard_shard9_bay_cdij_run6253.sql
via the Supabase Management API, then runs pencil_dod_evaluate_county('bay') to confirm
metric movement.

Usage:
  python3 scripts/bay_cdij_run6253.py
  python3 scripts/bay_cdij_run6253.py --dry-run    # print SQL only, no write
"""
import json
import os
import sys
import urllib.request
import urllib.error

SUPABASE_REF = "mocerqjnksmhcjzxrewo"
TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MIGRATION_FILE = "migrations/20260724_gold_standard_shard9_bay_cdij_run6253.sql"


def mgmt_query(sql: str) -> dict:
    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{SUPABASE_REF}/database/query",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return {"status": resp.status, "body": json.loads(resp.read())}
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            body = json.loads(body)
        except Exception:
            body = body.decode()
        return {"status": e.code, "body": body}


def run_migration(dry_run: bool = False):
    with open(MIGRATION_FILE) as f:
        sql = f.read()

    if dry_run:
        print("DRY RUN — SQL that would be applied:")
        print(sql[:2000], "...")
        return

    print(f"Applying migration: {MIGRATION_FILE}")
    result = mgmt_query(sql)
    print(f"HTTP {result['status']}")
    body = result["body"]
    if isinstance(body, list):
        for item in body:
            print(json.dumps(item, indent=2, default=str)[:500])
    else:
        print(json.dumps(body, indent=2, default=str)[:2000])

    if result["status"] not in (200, 201):
        raise RuntimeError(f"Migration failed HTTP {result['status']}")

    print("\n=== MIGRATION APPLIED SUCCESSFULLY ===\n")

    # Run evaluation
    print("Running pencil_dod_evaluate_county('bay')...")
    eval_result = mgmt_query("SELECT public.pencil_dod_evaluate_county('bay');")
    print(f"Evaluation HTTP {eval_result['status']}")
    print(json.dumps(eval_result["body"], indent=2, default=str)[:3000])

    # Additional diagnostic queries
    diag_sql = """
    SELECT
        'bay_final_cdij' AS checkpoint,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE parity_status = 'matched_clean') AS matched_clean,
        ROUND(100.0 * COUNT(*) FILTER (WHERE parity_status = 'matched_clean') / NULLIF(COUNT(*), 0), 1) AS pct_c,
        ROUND(100.0 * COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_divergent')) / NULLIF(COUNT(*), 0), 1) AS pct_d
    FROM public.multi_county_auctions WHERE lower(county) = 'bay';
    """
    diag_result = mgmt_query(diag_sql)
    print("\nDiagnostic:")
    print(json.dumps(diag_result["body"], indent=2, default=str)[:1000])

    bd_sql = """
    SELECT
        'bay_bid_decisions' AS label,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE ml_score IS NOT NULL) AS with_ml_score,
        COUNT(*) FILTER (
            WHERE factors ? 'distress_location' AND factors ? 'distress_property'
              AND factors ? 'distress_owner' AND factors ? 'cma_distressed' AND factors ? 'cma_resale'
        ) AS with_5_factors
    FROM public.bid_decisions WHERE county_slug = 'bay';
    """
    bd_result = mgmt_query(bd_sql)
    print("\nBid decisions:")
    print(json.dumps(bd_result["body"], indent=2, default=str)[:1000])


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_migration(dry_run)
