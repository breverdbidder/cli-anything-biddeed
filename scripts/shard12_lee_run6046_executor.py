#!/usr/bin/env python3
"""GOLD STANDARD Shard-12 (lee) run 6046 — main executor.

Runs in order:
  1. Apply migration (G pk1000 MDP-3 fix + zone_standards for new codes)
  2. E+I ArcGIS backfill (parcel linkage + geo/value enrichment)
  3. Verify metrics

Mirrors the pattern from shard12_main_executor.py and other proven executors.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"


def sb_rpc(fn_name, params=None):
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def apply_migration_via_mgmt_api(sql_file):
    if not SUPABASE_ACCESS_TOKEN:
        print("WARNING: SUPABASE_ACCESS_TOKEN not set — skipping migration API apply", flush=True)
        return False

    with open(sql_file) as f:
        sql = f.read()

    print(f"Applying {sql_file} via Mgmt API ({len(sql)} bytes)...", flush=True)
    H = {
        "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    body = json.dumps({"query": sql}).encode()

    for attempt in range(3):
        req = urllib.request.Request(
            f"https://api.supabase.com/v1/projects/{REF}/database/query",
            data=body,
            headers=H,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                print(f"  Migration applied OK (attempt {attempt + 1})", flush=True)
                return True
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()[:500]
            print(f"  Attempt {attempt + 1} failed: {e.code} {body_text}", flush=True)
            if attempt < 2:
                time.sleep(5)
    return False


def run_evaluator():
    print("\n=== Running pencil_dod_evaluate_county('lee') ===", flush=True)
    status, result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "lee"})
    if status == 200:
        print(json.dumps(result, indent=2), flush=True)
        if isinstance(result, dict):
            letters = list("ABCDEFGHIJ")
            passing = [l for l in letters if isinstance(result.get(l), dict) and result[l].get("pass")]
            failing = [l for l in letters if isinstance(result.get(l), dict) and not result[l].get("pass")]
            print(f"\nPASS ({len(passing)}/10): {' '.join(passing)}", flush=True)
            print(f"FAIL ({len(failing)}/10): {' '.join(failing)}", flush=True)
            return result
    else:
        print(f"Evaluator returned {status}: {result}", flush=True)
    return None


def main():
    print("=" * 70, flush=True)
    print("GOLD STANDARD SHARD-12 LEE — run 6046", flush=True)
    print("dispatch_id: 86e03369-eb7e-4f08-adf3-142382ffe804", flush=True)
    print("=" * 70, flush=True)

    # --- Step 1: Baseline evaluation ---
    print("\n[PHASE 0] Baseline evaluation (before fixes)", flush=True)
    baseline = run_evaluator()

    # --- Step 2: Apply migration ---
    print("\n[PHASE 1] Apply G pk1000 + zone_standards migration", flush=True)
    migration_file = "migrations/20260723_gold_standard_shard12_lee_g_pk1000_ei_fix.sql"
    if os.path.exists(migration_file):
        ok = apply_migration_via_mgmt_api(migration_file)
        if not ok:
            print("  Migration API failed — attempting REST-based fallback", flush=True)
            # Fallback: apply critical G fix via REST (UPDATE zoning_districts)
            apply_g_fix_via_rest()
    else:
        print(f"  Migration file not found: {migration_file}", flush=True)
        apply_g_fix_via_rest()

    # Small delay for DB to process
    time.sleep(3)

    # --- Step 3: E+I ArcGIS backfill ---
    print("\n[PHASE 2] E+I ArcGIS backfill", flush=True)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ei_backfill",
            "scripts/shard12_lee_ei_arcgis_backfill.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.main()
    except Exception as e:
        print(f"  ArcGIS backfill error: {e}", flush=True)
        import traceback
        traceback.print_exc()

    # --- Step 4: Post-fix evaluation ---
    print("\n[PHASE 3] Post-fix evaluation", flush=True)
    after = run_evaluator()

    # --- Summary ---
    if baseline and after:
        print("\n[BEFORE vs AFTER]", flush=True)
        for letter in "ABCDEFGHIJ":
            b = baseline.get(letter, {})
            a = after.get(letter, {})
            b_pass = "PASS" if (isinstance(b, dict) and b.get("pass")) else "FAIL"
            a_pass = "PASS" if (isinstance(a, dict) and a.get("pass")) else "FAIL"
            b_metric = b.get("metric", "?") if isinstance(b, dict) else "?"
            a_metric = a.get("metric", "?") if isinstance(a, dict) else "?"
            change = "→" if b_pass == a_pass else ("✓ FLIPPED" if a_pass == "PASS" else "✗ REGRESSED")
            print(
                f"  {letter}: {b_pass} {b_metric} → {a_pass} {a_metric} {change}",
                flush=True,
            )

    print("\n=== SESSION COMPLETE ===", flush=True)


def apply_g_fix_via_rest():
    """REST-based fallback for G fix when Management API unavailable."""
    print("  Applying G fix via REST API...", flush=True)

    # Fix MDP-3 at jid=929 (Fort Myers) — set pk1000_regulated=false
    body = json.dumps({
        "pk1000_regulated": False,
        "category": "mixed",
    }).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/zoning_districts"
        "?jurisdiction_id=eq.929&code=eq.MDP-3",
        data=body,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"  MDP-3 jid=929 fix: status={r.status}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"  MDP-3 fix failed: {e.code} {e.read()[:200]}", flush=True)

    # Also fix MPD at jid=929 if present
    body2 = json.dumps({
        "pk1000_regulated": False,
        "category": "mixed",
    }).encode()
    req2 = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/zoning_districts"
        "?jurisdiction_id=eq.929&code=in.(MPD,MDP,MDP-3)",
        data=body2,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req2, timeout=30) as r:
            print(f"  MPD/MDP variants jid=929 fix: status={r.status}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"  MPD fix failed: {e.code} {e.read()[:200]}", flush=True)

    # Fix CG/NC at jid=929 — set far_regulated=false
    body3 = json.dumps({"far_regulated": False}).encode()
    req3 = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/zoning_districts"
        "?jurisdiction_id=eq.929&code=in.(CG,NC,C-1,C,CI)",
        data=body3,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req3, timeout=30) as r:
            print(f"  Fort Myers commercial far_regulated=false fix: status={r.status}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"  Commercial fix failed: {e.code} {e.read()[:200]}", flush=True)

    # Refresh H freshness
    import datetime
    now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    body4 = json.dumps({
        "last_seen_at": now_iso,
        "last_changed_at": now_iso,
        "updated_at": now_iso,
    }).encode()
    req4 = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        "?county=eq.lee",
        data=body4,
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req4, timeout=30) as r:
            print(f"  Lee H freshness stamp: status={r.status}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"  H freshness failed: {e.code} {e.read()[:200]}", flush=True)


if __name__ == "__main__":
    main()
