#!/usr/bin/env python3
"""
SHARD-6 executor: walton (G density), okeechobee (C/D/I), gulf (H freshness)
dispatch_id: fd6f48d0-e8ef-411f-93ad-e77c345ae5ff

Applies the migration at migrations/20260723_shard6_walton_okeechobee_gulf_fd6f48d0.sql
via the Supabase Management API, then verifies pencil_dod_evaluate_county for all 3 counties.

Usage: python3 scripts/shard6_fd6f48d0_walton_okeechobee_gulf_executor.py
Requires: SUPABASE_ACCESS_TOKEN env var (for Management API writes)
          SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY env var (for REST API reads)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ── credentials ──────────────────────────────────────────────────────────────
SB_REF = "mocerqjnksmhcjzxrewo"
SB_URL = os.environ.get("SUPABASE_URL", f"https://{SB_REF}.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

DISPATCH_ID = "fd6f48d0-e8ef-411f-93ad-e77c345ae5ff"
MIGRATION_PATH = Path(__file__).parent.parent / "migrations" / "20260723_shard6_walton_okeechobee_gulf_fd6f48d0.sql"


def mgmt_query(sql: str) -> dict:
    """Run SQL via Supabase Management API."""
    if not MGMT_TOKEN:
        raise RuntimeError("SUPABASE_ACCESS_TOKEN not set — cannot write via Management API")
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{SB_REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def sb_rpc(fn: str, payload: dict) -> dict:
    """Call a Supabase RPC endpoint."""
    if not SB_KEY:
        raise RuntimeError("No Supabase service role key found")
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(payload).encode(),
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def evaluate_county(county: str) -> dict:
    """Run pencil_dod_evaluate_county and print results."""
    try:
        result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
        print(f"\n=== pencil_dod_evaluate_county('{county}') ===")
        total = result.get("auctions_total", "?")
        print(f"  auctions_total: {total}")
        passes = 0
        for letter in "ABCDEFGHIJ":
            item = result.get(letter, {})
            status = "PASS" if item.get("pass") else "FAIL"
            metric = item.get("metric")
            detail = item.get("detail", "")
            print(f"  {letter} {status} metric={metric} {detail}")
            if item.get("pass"):
                passes += 1
        print(f"  SCORE: {passes}/10")
        return result
    except Exception as e:
        print(f"  ERROR calling pencil_dod_evaluate_county('{county}'): {e}")
        return {}


def apply_migration() -> bool:
    """Apply the migration SQL via Management API."""
    sql = MIGRATION_PATH.read_text()
    print(f"\n=== Applying migration: {MIGRATION_PATH.name} ===")
    print(f"  SQL length: {len(sql)} chars")
    try:
        result = mgmt_query(f"SET statement_timeout = 0;\n{sql}")
        print(f"  Management API response: STATUS OK")
        print(f"  Result rows: {len(result) if isinstance(result, list) else 'N/A'}")
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code} error: {body[:500]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return False


def verify_parity_counts() -> None:
    """Quick parity count check via REST."""
    if not SB_KEY:
        print("  SKIP parity count check (no SB_KEY)")
        return
    try:
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/multi_county_auctions"
            f"?county=in.(walton,okeechobee,gulf)"
            f"&select=county,parity_status"
            f"&limit=5000",
            headers={
                "apikey": SB_KEY,
                "Authorization": f"Bearer {SB_KEY}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            rows = json.loads(r.read())
        by_county: dict[str, dict] = {}
        for row in rows:
            c = row["county"].lower()
            if c not in by_county:
                by_county[c] = {"total": 0, "matched_clean": 0}
            by_county[c]["total"] += 1
            if row.get("parity_status") == "matched_clean":
                by_county[c]["matched_clean"] += 1
        print("\n=== Parity count verification ===")
        for c, d in sorted(by_county.items()):
            pct = round(100.0 * d["matched_clean"] / d["total"], 1) if d["total"] else 0
            print(f"  {c}: total={d['total']} matched_clean={d['matched_clean']} pct={pct}%")
    except Exception as e:
        print(f"  ERROR in parity count check: {e}")


def main() -> int:
    print(f"=== SHARD-6 EXECUTOR: walton / okeechobee / gulf ===")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"SB_KEY present: {'YES' if SB_KEY else 'NO'}")
    print(f"MGMT_TOKEN present: {'YES' if MGMT_TOKEN else 'NO'}")

    if not SB_KEY and not MGMT_TOKEN:
        print("\nERROR: No credentials found. Set SUPABASE_ACCESS_TOKEN and SUPABASE_SERVICE_ROLE_KEY",
              file=sys.stderr)
        return 1

    # BEFORE snapshot
    print("\n" + "="*60)
    print("BEFORE STATE")
    print("="*60)
    before = {}
    for county in ("walton", "okeechobee", "gulf"):
        before[county] = evaluate_county(county)

    # Apply migration
    ok = apply_migration()
    if not ok:
        print("\nMigration failed — aborting verification", file=sys.stderr)
        return 1

    # AFTER snapshot
    print("\n" + "="*60)
    print("AFTER STATE")
    print("="*60)
    after = {}
    for county in ("walton", "okeechobee", "gulf"):
        after[county] = evaluate_county(county)

    # Parity counts
    verify_parity_counts()

    # Summary diff
    print("\n" + "="*60)
    print("CHANGES SUMMARY")
    print("="*60)
    for county in ("walton", "okeechobee", "gulf"):
        b = before.get(county, {})
        a = after.get(county, {})
        changes = []
        for letter in "ABCDEFGHIJ":
            bm = b.get(letter, {}).get("metric")
            am = a.get(letter, {}).get("metric")
            bp = b.get(letter, {}).get("pass")
            ap = a.get(letter, {}).get("pass")
            if bm != am or bp != ap:
                if not bp and ap:
                    changes.append(f"  {letter}: {bm} -> {am} ** FLIP TO PASS **")
                elif bp and not ap:
                    changes.append(f"  {letter}: {bm} -> {am} ** REGRESSION (P0) **")
                else:
                    changes.append(f"  {letter}: {bm} -> {am}")
        b_passes = sum(1 for l in "ABCDEFGHIJ" if b.get(l, {}).get("pass"))
        a_passes = sum(1 for l in "ABCDEFGHIJ" if a.get(l, {}).get("pass"))
        print(f"\n{county}: {b_passes}/10 -> {a_passes}/10")
        for c in changes:
            print(c)
        if not changes:
            print(f"  (no changes)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
