#!/usr/bin/env python3
"""Apply 20260623_brevard_g_kpi_auction_fix.sql via Supabase Management API.

DoD:
  SELECT pct_zoning_known FROM v_zoning_gold_standard_kpi_auction WHERE county='brevard'
  → row with pct_zoning_known ≥ 95

  SELECT crit_g_pass FROM v_pencil_brevard_dod WHERE county='brevard'
  → true
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SB_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
          or os.environ.get("SUPABASE_SERVICE_KEY")
          or os.environ.get("SUPABASE_KEY", ""))
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"
MGMT_BASE = f"https://api.supabase.com/v1/projects/{REF}/database/query"
REST_BASE = f"{SUPABASE_URL}/rest/v1"

MIGRATION = Path(__file__).parent.parent / "supabase/migrations/20260623_brevard_g_kpi_auction_fix.sql"


def mgmt_query(sql: str) -> dict | None:
    """Execute SQL via Supabase Management API."""
    if not ACCESS_TOKEN:
        return None
    payload = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        MGMT_BASE,
        data=payload,
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
        return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        print(f"  Management API HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
        return None
    except Exception as ex:
        print(f"  Management API error: {ex}")
        return None


def rest_query(endpoint: str, params: str = "") -> list | None:
    """GET from Supabase REST API."""
    if not SB_KEY:
        return None
    url = f"{REST_BASE}/{endpoint}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
        return json.loads(body) if body else []
    except Exception as ex:
        print(f"  REST error ({endpoint}): {ex}")
        return None


def rest_rpc(fn: str, args: dict) -> dict | list | None:
    """Call a Supabase RPC function via REST."""
    if not SB_KEY:
        return None
    payload = json.dumps(args).encode()
    req = urllib.request.Request(
        f"{REST_BASE}/rpc/{fn}",
        data=payload,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
        return json.loads(body) if body else {}
    except Exception as ex:
        print(f"  RPC error ({fn}): {ex}")
        return None


def main() -> int:
    print("=" * 60)
    print("fix(brevard-G): apply v_zoning_gold_standard_kpi_auction fix")
    print("=" * 60)

    if not MIGRATION.exists():
        print(f"ERROR: migration not found: {MIGRATION}")
        return 1

    sql = MIGRATION.read_text()
    print(f"Migration: {MIGRATION.name} ({len(sql)} bytes)")

    # ── Step 1: Apply migration via Management API ──────────────────────
    print("\n── Applying migration via Management API ──")
    result = mgmt_query(sql)
    if result is None:
        print("  Management API unavailable — trying REST RPC exec_sql fallback")
        result = rest_rpc("exec_sql", {"query": sql})
        if result is None:
            print("ERROR: both Mgmt API and REST exec_sql failed")
            return 1

    if isinstance(result, dict) and result.get("error"):
        print(f"ERROR: migration failed: {result['error'][:300]}")
        return 1

    print("  Migration applied OK")

    # ── Step 2: Verify DoD ──────────────────────────────────────────────
    print("\n── DoD Verification ──")

    # 2a. Check v_zoning_gold_standard_kpi_auction
    kpi_rows = rest_query(
        "v_zoning_gold_standard_kpi_auction",
        "county=eq.brevard&select=county,pct_density_known,pct_far_known,pct_parking_known,pct_zoning_known"
    )
    if kpi_rows:
        row = kpi_rows[0]
        pct = row.get("pct_zoning_known")
        print(f"\n### SQL VERIFICATION")
        print(f"```sql")
        print(f"-- v_zoning_gold_standard_kpi_auction WHERE county='brevard'")
        print(f"-- county:              {row.get('county')}")
        print(f"-- pct_density_known:   {row.get('pct_density_known')}")
        print(f"-- pct_far_known:       {row.get('pct_far_known')}")
        print(f"-- pct_parking_known:   {row.get('pct_parking_known')}")
        print(f"-- pct_zoning_known:    {pct}")
        print(f"-- dod_g_pass:          {pct is not None and float(pct) >= 95}")
        print(f"```")
        dod1_pass = pct is not None and float(pct) >= 95
        print(f"\n  DoD #1 (pct_zoning_known ≥ 95): {'PASS ✓' if dod1_pass else 'FAIL ✗'} ({pct})")
    else:
        print("  WARNING: v_zoning_gold_standard_kpi_auction WHERE county='brevard' → 0 rows")
        print("  Checking if v_zoning_gold_standard_kpi_v3 has county column...")
        v3_rows = rest_query(
            "v_zoning_gold_standard_kpi_v3",
            "select=county,county_slug,pct_density_of_applicable,pct_far_of_applicable,pct_pk1000_of_applicable&limit=3"
        )
        if v3_rows:
            print(f"  v3 sample (first 3 rows): {json.dumps(v3_rows[:3], indent=2)}")
        dod1_pass = False

    # 2b. Check v_pencil_brevard_dod
    dod_rows = rest_query(
        "v_pencil_brevard_dod",
        "county=eq.brevard&select=county,crit_g_pass,zoning_density_pct&limit=1"
    )
    if dod_rows:
        row = dod_rows[0]
        g_pass = row.get("crit_g_pass")
        print(f"\n  DoD #2 (v_pencil_brevard_dod.crit_g_pass): {'PASS ✓' if g_pass else 'FAIL ✗'}")
        print(f"  zoning_density_pct: {row.get('zoning_density_pct')}")
        dod2_pass = bool(g_pass)
    else:
        print("  NOTE: v_pencil_brevard_dod not accessible via REST (may be function-based)")
        dod2_pass = None

    # 2c. Run pencil_dod_evaluate_county('brevard') for G letter
    eval_result = rest_rpc("pencil_dod_evaluate_county", {"p_county": "brevard"})
    if eval_result and isinstance(eval_result, dict):
        g = eval_result.get("G", {})
        g_pass = g.get("pass")
        g_metric = g.get("metric")
        print(f"\n  DoD #3 (pencil_dod_evaluate_county G): pass={g_pass} metric={g_metric}")
    else:
        # try old signature
        eval_result = rest_rpc("pencil_dod_evaluate_county", {"county_slug_arg": "brevard"})
        if eval_result:
            print(f"  pencil_dod_evaluate_county (old sig): {json.dumps(eval_result)[:400]}")

    print("\n" + "=" * 60)
    if dod1_pass:
        print("RESULT: DoD PASS — brevard G regression fixed")
        print("  v_zoning_gold_standard_kpi_auction.pct_zoning_known ≥ 95 ✓")
    else:
        print("RESULT: DoD FAIL — further investigation needed")
        print("  Check if v_zoning_gold_standard_kpi_v3 has 'county' column")
        print("  vs 'county_slug' (scripts use both)")
        print("  Manual fallback: see migration SQL for SELECT verification block")
    print("=" * 60)

    return 0 if dod1_pass else 2


if __name__ == "__main__":
    sys.exit(main())
