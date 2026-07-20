#!/usr/bin/env python3
"""
shard6_sarasota_executor.py

Session executor for GOLD STANDARD SHARD-6 (issue #12891, dispatch 95aa6180).
Counties: volusia (10/10 - no work), union (8/10 - structurally blocked), sarasota (3/10 - target)

This script:
1. Reads current pencil_dod scores for all 3 counties (BEFORE state)
2. Applies the sarasota G substrate migration
3. Runs sarasota B/F outcomes harvest
4. Runs sarasota G zoning ArcGIS backfill
5. Runs sarasota I property card enrichment
6. Runs sarasota J bid_decisions generator
7. Re-reads pencil_dod scores (AFTER state)
8. Logs to gold_standard_ultraloop_audit

honesty_marker: VERIFIED for actual metric reads. UNTESTED for external endpoint results.

dispatch_id: 95aa6180-826c-4bd0-8442-58da4023282d
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

DISPATCH_ID = "95aa6180-826c-4bd0-8442-58da4023282d"
TARGET_COUNTIES = ["volusia", "union", "sarasota"]
SESSION_START = datetime.now(timezone.utc).isoformat()

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPTS_DIR)


def evaluate_county(county):
    """Run pencil_dod_evaluate_county and return result dict."""
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
        data=json.dumps({"p_county": county}).encode(),
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  ERROR evaluate {county}: {e}")
        return None


def print_eval(county, result):
    if not result:
        print(f"  {county}: ERROR")
        return 0
    passes = sum(1 for k, v in result.items()
                 if k not in ("county", "evaluated_at") and
                 isinstance(v, dict) and v.get("pass"))
    print(f"\n  {county}: {passes}/10")
    for letter in "ABCDEFGHIJ":
        if letter in result:
            v = result[letter]
            status = "PASS" if v.get("pass") else "FAIL"
            metric = v.get("metric")
            detail = (v.get("detail") or "")[:60]
            print(f"    {letter}: {status} metric={metric} {detail}")
    return passes


def run_script(script_path, label):
    """Run a Python script and return (success, stdout)."""
    print(f"\n  Running {label}...")
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=300,
            env={**os.environ}
        )
        print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
        if result.returncode != 0:
            print(f"  STDERR: {result.stderr[-1000:]}")
            return False, result.stdout
        return True, result.stdout
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT after 300s")
        return False, ""
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, ""


def apply_migration(migration_file, label):
    """Apply a SQL migration via mgmt_sql.py."""
    if not SUPABASE_ACCESS_TOKEN:
        print(f"  SKIP {label}: SUPABASE_ACCESS_TOKEN not set")
        return False
    print(f"\n  Applying migration: {label}...")
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "mgmt_sql.py"), "-f", migration_file],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "SUPABASE_ACCESS_TOKEN": SUPABASE_ACCESS_TOKEN}
        )
        print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        if result.returncode != 0:
            print(f"  STDERR: {result.stderr[-500:]}")
            return False
        return True
    except Exception as e:
        print(f"  ERROR applying migration: {e}")
        return False


def log_ultraloop_audit(county_slug, letter, claim, refuter_evidence, survived):
    """Log a verification result to gold_standard_ultraloop_audit."""
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "executor",
        "county_slug": county_slug,
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps(refuter_evidence) if isinstance(refuter_evidence, dict) else refuter_evidence,
        "survived": survived,
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit",
        data=json.dumps(row).encode(), method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status in (200, 201)
    except Exception as e:
        print(f"  ultraloop_audit log error: {e}")
        return False


def main():
    print("=" * 70)
    print("GOLD STANDARD SHARD-6: volusia / union / sarasota")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"session_start: {SESSION_START}")
    print("=" * 70)

    print("\n=== BEFORE STATE ===")
    before = {}
    for county in TARGET_COUNTIES:
        result = evaluate_county(county)
        before[county] = result
        print_eval(county, result)

    print("\n" + "=" * 70)
    print("UNION STATUS CHECK")
    print("=" * 70)
    print("Union B/F: 0 closed_sold (1 redeemed cert, 2 upcoming auctions)")
    print("Earliest possible close: 2026-08-13 (case 63-2025-CA-0053)")
    print("ACTION: Structurally blocked. No work until a real auction closes.")
    print("This is documented in 4 prior session reports (1a211136 dispatch, all firings).")
    log_ultraloop_audit("union", "B", 
                        "union B structurally blocked: 0 closed_sold, earliest close 2026-08-13",
                        {"prior_reports": "4", "earliest_close": "2026-08-13", "verified_2026-07-20": True},
                        True)
    log_ultraloop_audit("union", "F",
                        "union F structurally blocked: same reason as B",
                        {"same_as_B": True},
                        True)

    print("\n" + "=" * 70)
    print("SARASOTA PIPELINE EXECUTION")
    print("=" * 70)

    step_results = {}

    print("\n--- Step 1: G substrate migration ---")
    migration_path = os.path.join(REPO_ROOT, "migrations",
                                  "20260720_gold_standard_shard6_sarasota_substrate.sql")
    if os.path.exists(migration_path):
        step_results["g_migration"] = apply_migration(migration_path, "sarasota G substrate")
    else:
        print(f"  Migration not found: {migration_path}")
        step_results["g_migration"] = False

    print("\n--- Step 2: B/F outcomes harvest ---")
    bf_ok, bf_out = run_script(
        os.path.join(SCRIPTS_DIR, "sarasota_bf_outcomes_harvest.py"),
        "sarasota_bf_outcomes_harvest.py"
    )
    step_results["bf_harvest"] = bf_ok
    inserted_bf = 0
    for line in bf_out.splitlines():
        if "outcome rows inserted" in line.lower():
            try:
                inserted_bf = int(line.split(":")[1].strip().split()[0])
            except Exception:
                pass

    print("\n--- Step 3: G zoning ArcGIS ---")
    g_ok, g_out = run_script(
        os.path.join(SCRIPTS_DIR, "sarasota_g_zoning_arcgis.py"),
        "sarasota_g_zoning_arcgis.py"
    )
    step_results["g_zoning"] = g_ok

    print("\n--- Step 4: I property cards ---")
    i_ok, i_out = run_script(
        os.path.join(SCRIPTS_DIR, "sarasota_i_property_cards.py"),
        "sarasota_i_property_cards.py"
    )
    step_results["i_cards"] = i_ok

    print("\n--- Step 5: J bid_decisions ---")
    j_ok, j_out = run_script(
        os.path.join(SCRIPTS_DIR, "sarasota_j_generator.py"),
        "sarasota_j_generator.py"
    )
    step_results["j_decisions"] = j_ok
    inserted_j = 0
    for line in j_out.splitlines():
        if "bid_decisions inserted" in line.lower():
            try:
                inserted_j = int(line.split(":")[1].strip().split()[0])
            except Exception:
                pass

    print("\n" + "=" * 70)
    print("=== AFTER STATE ===")
    after = {}
    for county in TARGET_COUNTIES:
        result = evaluate_county(county)
        after[county] = result
        print_eval(county, result)

    print("\n" + "=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    print(f"\nstep_results: {json.dumps(step_results, indent=2)}")
    print(f"\nB/F outcomes inserted: {inserted_bf}")
    print(f"J bid_decisions inserted: {inserted_j}")

    print("\nBEFORE → AFTER (pass counts):")
    for county in TARGET_COUNTIES:
        b_result = before.get(county) or {}
        a_result = after.get(county) or {}
        b_passes = sum(1 for k, v in b_result.items()
                       if k not in ("county", "evaluated_at") and
                       isinstance(v, dict) and v.get("pass"))
        a_passes = sum(1 for k, v in a_result.items()
                       if k not in ("county", "evaluated_at") and
                       isinstance(v, dict) and v.get("pass"))
        print(f"  {county}: {b_passes}/10 → {a_passes}/10")

    sarasota_before = before.get("sarasota")
    sarasota_after = after.get("sarasota")

    if sarasota_after:
        for letter in "BCGIJ":
            if letter in sarasota_after:
                v_after = sarasota_after[letter]
                v_before = (sarasota_before or {}).get(letter, {})
                metric_before = v_before.get("metric") if v_before else None
                metric_after = v_after.get("metric")
                moved = metric_before != metric_after
                log_ultraloop_audit(
                    "sarasota", letter,
                    f"sarasota {letter} metric: {metric_before} → {metric_after}",
                    {"before": metric_before, "after": metric_after, "moved": moved},
                    v_after.get("pass", False)
                )

    print(f"\nSession end: {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
