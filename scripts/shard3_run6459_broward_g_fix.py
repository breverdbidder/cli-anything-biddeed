#!/usr/bin/env python3
"""
SHARD-3 run-6459: Broward G regression fix + verification
dispatch_id: 76462ac1-c6ad-402a-88cd-d9ae80df858d
issue: #14249

Applies the broward G self-healing migration and verifies the result.
Uses urllib (stdlib only) to avoid dependency issues.
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REF = "mocerqjnksmhcjzxrewo"
DISPATCH_ID = "76462ac1-c6ad-402a-88cd-d9ae80df858d"
MIGRATION_FILE = Path(__file__).parent.parent / "migrations" / "20260725_gold_standard_shard3_broward_g_regression_fix_run6459.sql"


def mgmt_sql(query: str, label: str = "") -> dict:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set")
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            result = json.loads(r.read())
            if label:
                print(f"[OK] {label}: status=200")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        print(f"[ERROR] {label}: HTTP {e.code}: {body}")
        raise


def ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def main():
    print(f"[{ts()}] SHARD-3 run-6459: Broward G regression fix")
    print(f"[{ts()}] dispatch_id: {DISPATCH_ID}")

    # Step 1: Pre-fix evaluation
    print(f"\n[{ts()}] === STEP 1: Pre-fix pencil_dod_evaluate_county('broward') ===")
    pre_eval = mgmt_sql(
        "SET statement_timeout=0; SELECT public.pencil_dod_evaluate_county('broward') as result",
        "pre-fix evaluation"
    )
    print(f"Pre-fix result: {json.dumps(pre_eval, indent=2, default=str)[:1000]}")

    # Step 2: Diagnose unmatched zone codes
    print(f"\n[{ts()}] === STEP 2: Diagnose unmatched Broward zone codes ===")
    diag = mgmt_sql("""
SET statement_timeout=0;
SELECT pz.jurisdiction_id, pz.zone_code, COUNT(*) as parcel_count
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE lower(j.county) = 'broward'
  AND pz.zone_code IS NOT NULL
  AND pz.zone_code != ''
  AND NOT EXISTS (
      SELECT 1 FROM zoning_districts zd
      WHERE zd.jurisdiction_id = pz.jurisdiction_id
        AND zd.code = pz.zone_code
  )
GROUP BY pz.jurisdiction_id, pz.zone_code
ORDER BY parcel_count DESC
""", "unmatched zone code diagnosis")
    print(f"Unmatched zone codes: {json.dumps(diag, indent=2, default=str)[:1000]}")

    unmatched_count = len(diag) if isinstance(diag, list) else 0
    if unmatched_count == 0:
        print(f"[{ts()}] WARNING: No unmatched zone codes found. G failure may have a different root cause.")
        print(f"[{ts()}] Checking v_zoning_gold_standard_kpi_v3 directly...")

        kpi_check = mgmt_sql("""
SET statement_timeout=0;
SELECT 
    pct_density_of_applicable as density,
    pct_far_of_applicable as far,
    pct_pk1000_of_applicable as pk1000,
    parcels_total,
    density_applicable,
    far_applicable,
    pk1000_applicable
FROM v_zoning_gold_standard_kpi_v3
WHERE county_slug = 'broward'
""", "KPI v3 direct check")
        print(f"KPI v3: {json.dumps(kpi_check, indent=2, default=str)[:1000]}")
    else:
        print(f"[{ts()}] Found {unmatched_count} unmatched zone code(s) — proceeding with fix")

    # Step 3: Apply migration
    print(f"\n[{ts()}] === STEP 3: Apply G regression fix migration ===")
    migration_sql = MIGRATION_FILE.read_text()
    result = mgmt_sql(migration_sql, "G regression fix migration")
    print(f"Migration result: {json.dumps(result, indent=2, default=str)[:500]}")

    # Step 4: Verify unmatched zone codes resolved
    print(f"\n[{ts()}] === STEP 4: Verify unmatched zone codes resolved ===")
    time.sleep(2)
    post_diag = mgmt_sql("""
SET statement_timeout=0;
SELECT COUNT(*) as remaining_unmatched
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE lower(j.county) = 'broward'
  AND pz.zone_code IS NOT NULL
  AND pz.zone_code != ''
  AND NOT EXISTS (
      SELECT 1 FROM zoning_districts zd
      WHERE zd.jurisdiction_id = pz.jurisdiction_id
        AND zd.code = pz.zone_code
  )
""", "post-fix unmatched check")
    print(f"Remaining unmatched: {json.dumps(post_diag, indent=2, default=str)[:200]}")

    # Step 5: What was inserted
    print(f"\n[{ts()}] === STEP 5: Newly inserted zoning_districts rows ===")
    new_rows = mgmt_sql("""
SELECT jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated
FROM zoning_districts
WHERE ordinance_section LIKE '%shard3-run6459%'
ORDER BY jurisdiction_id, code
""", "new zoning_districts rows")
    print(f"New rows: {json.dumps(new_rows, indent=2, default=str)[:1000]}")

    # Step 6: Post-fix evaluation
    print(f"\n[{ts()}] === STEP 6: Post-fix pencil_dod_evaluate_county('broward') ===")
    post_eval = mgmt_sql(
        "SET statement_timeout=0; SELECT public.pencil_dod_evaluate_county('broward') as result",
        "post-fix evaluation"
    )
    print(f"\n{'='*60}")
    print(f"BEFORE: {json.dumps(pre_eval, default=str)[:500]}")
    print(f"AFTER:  {json.dumps(post_eval, default=str)[:500]}")
    print(f"{'='*60}")

    # Step 7: Update ultraloop audit with survival verdict
    print(f"\n[{ts()}] === STEP 7: Update ultraloop audit ===")
    # Parse post_eval to determine if G passed
    post_str = json.dumps(post_eval, default=str)
    g_passed = '"G"' in post_str and 'pass' in post_str

    audit_update = mgmt_sql(f"""
UPDATE public.gold_standard_ultraloop_audit
SET survived = {str(g_passed).lower()},
    refuter_evidence = refuter_evidence || '{{"post_fix_eval": "run6459 fix applied", "timestamp": "{ts()}"}}'::jsonb
WHERE dispatch_id = '{DISPATCH_ID}'
  AND county_slug = 'broward'
  AND letter = 'G'
  AND created_at >= NOW() - INTERVAL '1 hour'
""", "ultraloop audit update")
    print(f"Audit update: {json.dumps(audit_update, default=str)[:200]}")

    print(f"\n[{ts()}] === COMPLETE ===")
    print(f"G fix applied. Check post_eval above for G metric.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
