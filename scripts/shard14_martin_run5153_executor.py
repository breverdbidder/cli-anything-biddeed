#!/usr/bin/env python3
"""SHARD-14 martin master executor, dispatch 9d22d82f-cbfe-4f01-a459-b5259d8d08df, run 5153.

Runs the full martin session in order:
  1. Baseline evaluation
  2. Apply J migration (bid_decisions for the 4 missing MCA rows)
  3. Run I parcel_zones backfill (GIS-based for new/residual parcels)
  4. Final evaluation
  5. ULTRALOOP verification pass

Usage:
  python3 scripts/shard14_martin_run5153_executor.py [--dry-run]

Environment: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN (all required)
"""
import importlib.util
import json
import os
import sys
import time
import urllib.request

DRY_RUN = "--dry-run" in sys.argv

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = "mocerqjnksmhcjzxrewo"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
MGMT_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def mgmt_query(sql):
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=data, method="POST", headers=MGMT_HEADERS,
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()), r.status


def evaluate_county(county="martin"):
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            data=json.dumps({"county_slug_arg": county}).encode(),
            method="POST", headers=REST_HEADERS,
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  RPC error ({e}), trying Management API...")
        result, _ = mgmt_query(f"SELECT public.pencil_dod_evaluate_county('{county}')")
        return result


def apply_migration_file(path):
    """Apply a SQL file via Management API."""
    with open(path) as f:
        sql = f.read()
    # Strip lines starting with -- (comments) that would otherwise be harmless but
    # may confuse some Management API parsers. Actually, leave them -- they're valid SQL.
    print(f"  Applying {os.path.basename(path)} ({len(sql)} chars)")
    if DRY_RUN:
        print("  [DRY RUN] skipping SQL execution")
        return True
    result, status = mgmt_query(sql)
    print(f"  HTTP {status}: {json.dumps(result)[:300]}")
    return status in (200, 201)


def format_eval(ev):
    """Format an evaluation result to a brief string."""
    if isinstance(ev, dict) and "A" in ev:
        letters = "ABCDEFGHIJ"
        parts = []
        for l in letters:
            d = ev.get(l, {})
            if isinstance(d, dict):
                p = "PASS" if d.get("pass") else "FAIL"
                m = d.get("metric", "?")
                parts.append(f"{l}={p}({m})")
        return " | ".join(parts)
    return json.dumps(ev)[:400]


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("FATAL: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set")
        sys.exit(1)
    if not SUPABASE_ACCESS_TOKEN:
        print("WARNING: SUPABASE_ACCESS_TOKEN not set")

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 70)
    print("SHARD-14 martin session executor (run5153)")
    print("dispatch: 9d22d82f-cbfe-4f01-a459-b5259d8d08df")
    print("=" * 70)

    # 1. Baseline
    print("\n[1] BASELINE evaluation...")
    before = evaluate_county("martin")
    print(f"  {format_eval(before)}")

    # ── J migration ──
    print("\n[2] LETTER J: Apply bid_decisions migration...")
    j_migration = os.path.join(
        here, "supabase", "migrations",
        "20260719_gold_standard_shard14_martin_j_bid_decisions_run5153.sql"
    )
    if os.path.exists(j_migration):
        ok = apply_migration_file(j_migration)
        if not ok and not DRY_RUN:
            print("  FAIL-LOUD: J migration failed.")
        else:
            print("  J migration applied.")
    else:
        print(f"  J migration file not found: {j_migration}")

    if not DRY_RUN:
        time.sleep(2)

    # ── I backfill ──
    print("\n[3] LETTER I: Parcel_zones backfill via ArcGIS...")
    # Import and run the I executor in-process
    i_script = os.path.join(here, "scripts", "shard14_martin_i_run5153.py")
    if os.path.exists(i_script):
        spec = importlib.util.spec_from_file_location("martin_i", i_script)
        mod = importlib.util.module_from_spec(spec)
        # Pass through args
        old_argv = sys.argv[:]
        sys.argv = [i_script]
        if DRY_RUN:
            sys.argv.append("--dry-run")
        try:
            spec.loader.exec_module(mod)
            mod.main()
        except SystemExit:
            pass
        except Exception as e:
            print(f"  I executor error: {e}")
        finally:
            sys.argv = old_argv
    else:
        print(f"  I script not found: {i_script}")

    # 4. Final evaluation
    print("\n[4] FINAL evaluation...")
    after = evaluate_county("martin")
    print(f"\n{'=' * 70}")
    print("FINAL STATE:")
    print(f"  {format_eval(after)}")

    # ── Pretty print letter-by-letter ──
    print("\n### SQL VERIFICATION — pencil_dod_evaluate_county('martin') — 2026-07-19")
    print(json.dumps(after, indent=2) if isinstance(after, dict) else json.dumps(after))

    # ── Count letters passing ──
    if isinstance(after, dict) and "A" in after:
        passing = [l for l in "ABCDEFGHIJ" if isinstance(after.get(l), dict) and after[l].get("pass")]
        failing = [l for l in "ABCDEFGHIJ" if isinstance(after.get(l), dict) and not after[l].get("pass")]
        print(f"\nPassing ({len(passing)}/10): {' '.join(passing)}")
        print(f"Failing ({len(failing)}/10): {' '.join(failing)}")


if __name__ == "__main__":
    main()
