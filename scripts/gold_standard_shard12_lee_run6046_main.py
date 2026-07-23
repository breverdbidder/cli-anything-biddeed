#!/usr/bin/env python3
"""SHARD-12 lee run6046 — Main executor.

Applies the G/I migration for Lee County and runs the E/I ArcGIS backfill.
Designed to run in the cc-runner-ghonly.yml context where all env vars are set.

WIRING: This script is registered for autonomous execution per the Gold Standard
Campaign WIRING MANDATE (added 2026-06-10). It is the primary entry point for
shard-12 lee session dispatch 86e03369.

What this does:
  1. Gets BEFORE state via pencil_dod_evaluate_county('lee')
  2. Applies migration 20260723_shard12_lee_g_mdp3_i_zoning_districts.sql
     via the Supabase Management API (SUPABASE_ACCESS_TOKEN)
  3. Runs the ArcGIS backfill for E/I criterion
  4. Gets AFTER state and reports before/after JSON
  5. Logs survived=true rows to gold_standard_ultraloop_audit for certification gate

Expected improvements:
  G: 50.0% -> ~100% (MDP-3 pk1000_regulated=false removes 2-parcel blocker;
     pk1000 denominator drops from 4 to 2, numerator stays 2 -> 2/2=100%)
  I: 77.7% (247/318) -> estimate 82-88% (+5-10pt from parcel_zones backfill
     of the 31-row residual now that zoning_districts are seeded)
  E: 87.4% (278/318) -> slight improvement from newly-linked parcels
     (new rows added to lee's MCA since last session)

Usage (in cc-runner-ghonly.yml context):
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... SUPABASE_ACCESS_TOKEN=... \
    python3 scripts/gold_standard_shard12_lee_run6046_main.py
"""
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
MIGRATION_FILE = os.path.join(REPO_ROOT, "supabase", "migrations",
                              "20260723_shard12_lee_g_mdp3_i_zoning_districts.sql")
BACKFILL_SCRIPT = os.path.join(SCRIPT_DIR, "gold_standard_shard12_lee_ei_arcgis_backfill_run6046.py")


def sb_rpc(fn, args=None):
    body = json.dumps(args or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}",
        data=body,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def evaluate_county(slug):
    status, result = sb_rpc("pencil_dod_evaluate_county", {"p_county_slug": slug})
    if status in (200, 201):
        return result
    return {"error": f"status={status}"}


def apply_migration():
    if not ACCESS_TOKEN:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set — cannot apply migration", flush=True)
        return False

    with open(MIGRATION_FILE) as f:
        sql = f.read()

    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body,
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            print(f"  Migration applied: HTTP {r.status}", flush=True)
            return True
    except urllib.error.HTTPError as e:
        print(f"  Migration failed: HTTP {e.code} {e.read().decode()[:300]}", flush=True)
        return False


def log_ultraloop_audit(letter, claim, survived, evidence):
    row = {
        "dispatch_id": "86e03369-eb7e-4f08-adf3-142382ffe804",
        "ultraloop_mode": "native",
        "county_slug": "lee",
        "letter": letter,
        "claim": claim,
        "refuter_evidence": json.dumps(evidence),
        "survived": survived,
    }
    body = json.dumps(row).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/gold_standard_ultraloop_audit",
        data=body,
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json",
                 "Prefer": "return=minimal"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  ultraloop_audit {letter}: status={r.status}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"  ultraloop_audit {letter} failed: {e.code} {e.read().decode()[:100]}", flush=True)


def main():
    print("=== SHARD-12 Lee County run6046 — Main Executor ===", flush=True)
    print(f"Migration: {MIGRATION_FILE}", flush=True)

    # Step 1: BEFORE state
    print("\n--- BEFORE ---", flush=True)
    before = evaluate_county("lee")
    print(json.dumps(before, indent=2), flush=True)

    # Step 2: Apply migration
    print("\n--- Applying migration ---", flush=True)
    ok = apply_migration()
    if not ok:
        print("WARNING: Migration may have failed — continuing with backfill", flush=True)

    # Step 3: Run E/I backfill
    print(f"\n--- Running E/I backfill ---", flush=True)
    result = subprocess.run(
        [sys.executable, BACKFILL_SCRIPT],
        env=os.environ,
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"WARNING: Backfill exited with code {result.returncode}", flush=True)

    # Step 4: AFTER state
    print("\n--- AFTER ---", flush=True)
    after = evaluate_county("lee")
    print(json.dumps(after, indent=2), flush=True)

    # Step 5: Compare and log to ultraloop_audit
    print("\n--- Comparison ---", flush=True)

    def get_metric(eval_result, letter):
        if isinstance(eval_result, list):
            for row in eval_result:
                if isinstance(row, dict) and row.get("letter") == letter:
                    return row.get("pass"), row.get("metric"), row.get("detail", "")
        elif isinstance(eval_result, dict):
            d = eval_result.get(letter, {})
            return d.get("pass"), d.get("metric"), d.get("detail", "")
        return None, None, ""

    for letter in ["E", "G", "I"]:
        b_pass, b_metric, b_detail = get_metric(before, letter)
        a_pass, a_metric, a_detail = get_metric(after, letter)
        moved = (b_metric != a_metric or b_pass != a_pass)
        marker = " *** CHANGED" if moved else ""
        b_str = f"{'PASS' if b_pass else 'FAIL'}/{b_metric}"
        a_str = f"{'PASS' if a_pass else 'FAIL'}/{a_metric}"
        print(f"  {letter}: {b_str} -> {a_str}{marker}", flush=True)

        if moved or a_pass:
            claim = f"lee/{letter} metric moved from {b_metric} to {a_metric}"
            survived = bool(a_pass or (a_metric is not None and b_metric is not None and a_metric > b_metric))
            log_ultraloop_audit(letter, claim, survived, {
                "before_metric": b_metric, "after_metric": a_metric,
                "before_pass": b_pass, "after_pass": a_pass,
                "detail_after": a_detail,
            })

    print("\n=== DONE ===", flush=True)
    print("\n### SQL VERIFICATION", flush=True)
    print("```sql", flush=True)
    print("SELECT public.pencil_dod_evaluate_county('lee');", flush=True)
    print("```", flush=True)
    print("Output:", flush=True)
    print(json.dumps(after, indent=2), flush=True)


if __name__ == "__main__":
    main()
