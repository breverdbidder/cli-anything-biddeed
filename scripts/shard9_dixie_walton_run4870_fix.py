#!/usr/bin/env python3
"""
SHARD-9 run4870 — dixie + walton fix script
dispatch_id: 487365d5-71dc-4492-b06a-a58da6810cb8
chat_session: architect-20260718T160000

Applies the migration 20260718k_gold_standard_shard9_dixie_walton_run4870.sql
via Supabase Management API (same pattern as apply-gold-standard-fix.yml and
other GHA workflow steps).

Uses:
  SUPABASE_ACCESS_TOKEN — Supabase Management API token (sbp_* token)
  REF = mocerqjnksmhcjzxrewo — project ref

Also supports REST API via:
  SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SERVICE_KEY
"""
from __future__ import annotations
import json, os, sys, urllib.request, urllib.error, pathlib

REF = "mocerqjnksmhcjzxrewo"
MGMT_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
SB_URL = os.environ.get("SUPABASE_URL", f"https://{REF}.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY", "")
)

MIGRATION_PATH = pathlib.Path(__file__).parent.parent / "supabase" / "migrations" / "20260718k_gold_standard_shard9_dixie_walton_run4870.sql"


def mgmt_sql(sql: str) -> tuple[int, object]:
    """Execute SQL via Supabase Management API (requires SUPABASE_ACCESS_TOKEN)."""
    if not MGMT_TOKEN:
        return -1, {"error": "SUPABASE_ACCESS_TOKEN not set"}
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body,
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{"error":"http_error"}')


def rest_rpc(fn: str, params: dict | None = None) -> tuple[int, object]:
    """Call Supabase RPC via REST API (requires SUPABASE_URL + service key)."""
    if not SB_KEY:
        return -1, {"error": "No service key available"}
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=body,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{"error":"http_error"}')


def rest_get(table: str, params: str = "") -> list:
    """GET from Supabase REST table."""
    if not SB_KEY:
        print(f"  [SKIP] No service key — cannot GET {table}")
        return []
    url = f"{SB_URL}/rest/v1/{table}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(
        url,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [WARN] GET {table} failed: {e}")
        return []


def run_sql_step(label: str, sql: str) -> bool:
    """Run a single SQL statement and report result."""
    print(f"\n--- {label} ---")

    # Try Management API first (handles DDL + multi-statement)
    if MGMT_TOKEN:
        status, result = mgmt_sql(sql)
        print(f"  [MGMT API] status={status}")
        if status in (200, 201):
            print(f"  OK: {str(result)[:200]}")
            return True
        else:
            print(f"  MGMT error: {str(result)[:300]}")

    # Fallback: REST RPC exec (may not support all DDL)
    if SB_KEY:
        status, result = rest_rpc("exec", {"query": sql})
        print(f"  [REST RPC] status={status}")
        if status in (200, 201):
            print(f"  OK: {str(result)[:200]}")
            return True
        else:
            print(f"  REST error: {str(result)[:300]}")

    return False


def main():
    print("=" * 70)
    print("SHARD-9 run4870 — dixie + walton FIX")
    print(f"dispatch_id: 487365d5-71dc-4492-b06a-a58da6810cb8")
    print("=" * 70)

    # Check credentials
    print(f"\nCredentials check:")
    print(f"  SUPABASE_ACCESS_TOKEN present: {bool(MGMT_TOKEN)}")
    print(f"  SUPABASE_SERVICE_ROLE_KEY present: {bool(os.environ.get('SUPABASE_SERVICE_ROLE_KEY'))}")
    print(f"  SUPABASE_SERVICE_KEY present: {bool(os.environ.get('SUPABASE_SERVICE_KEY'))}")

    if not MGMT_TOKEN and not SB_KEY:
        print("\n[ERROR] No Supabase credentials available.")
        print("Set SUPABASE_ACCESS_TOKEN (Management API) or SUPABASE_SERVICE_ROLE_KEY (REST).")
        sys.exit(1)

    # ── PRE-VERIFICATION ────────────────────────────────────────────────────
    print("\n=== PRE-VERIFICATION ===")

    if SB_KEY:
        for county in ["dixie", "walton"]:
            status, result = rest_rpc("pencil_dod_evaluate_county", {"p_county": county})
            print(f"\n  pencil_dod_evaluate_county('{county}')  status={status}")
            if status == 200:
                print(f"  BEFORE: {json.dumps(result)[:500]}")
            else:
                print(f"  ERROR: {result}")
    elif MGMT_TOKEN:
        for county in ["dixie", "walton"]:
            status, result = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county}')")
            print(f"\n  BEFORE {county}: status={status}  {str(result)[:400]}")

    # ── APPLY MIGRATION ─────────────────────────────────────────────────────
    print("\n=== APPLYING MIGRATION ===")

    if not MIGRATION_PATH.exists():
        print(f"[ERROR] Migration file not found: {MIGRATION_PATH}")
        sys.exit(1)

    migration_sql = MIGRATION_PATH.read_text()
    print(f"Migration: {MIGRATION_PATH.name}  ({len(migration_sql)} chars)")

    # Apply full migration via Management API (handles multi-statement + DDL)
    if MGMT_TOKEN:
        status, result = mgmt_sql(migration_sql)
        print(f"\n[MGMT API] Full migration: status={status}")
        if status in (200, 201):
            print(f"SUCCESS: {str(result)[:300]}")
        else:
            print(f"FAILED: {str(result)[:500]}")
            # Try splitting on statement boundaries if full migration fails
            print("\nFalling back to statement-by-statement execution...")
            parts = [s.strip() for s in migration_sql.split(";") if s.strip() and not s.strip().startswith("--")]
            for i, part in enumerate(parts):
                if part:
                    s, r = mgmt_sql(part + ";")
                    ok = "OK" if s in (200, 201) else "FAIL"
                    print(f"  [{i+1}/{len(parts)}] {ok} status={s}: {part[:60].replace(chr(10),' ')!r}")
    elif SB_KEY:
        status, result = rest_rpc("exec", {"query": migration_sql})
        print(f"\n[REST RPC exec] Full migration: status={status}")
        print(f"Result: {str(result)[:300]}")

    # ── POST-VERIFICATION ────────────────────────────────────────────────────
    print("\n=== POST-VERIFICATION ===")

    if SB_KEY:
        for county in ["dixie", "walton"]:
            status, result = rest_rpc("pencil_dod_evaluate_county", {"p_county": county})
            print(f"\n  pencil_dod_evaluate_county('{county}')  status={status}")
            if status == 200:
                print(f"  AFTER: {json.dumps(result)[:500]}")
            else:
                print(f"  ERROR: {result}")
    elif MGMT_TOKEN:
        for county in ["dixie", "walton"]:
            status, result = mgmt_sql(f"SELECT public.pencil_dod_evaluate_county('{county}')")
            print(f"\n  AFTER {county}: status={status}  {str(result)[:400]}")

        # Also check ultraloop_audit entries
        status, result = mgmt_sql(
            "SELECT county_slug, letter, survived, created_at::text "
            "FROM public.gold_standard_ultraloop_audit "
            "WHERE dispatch_id = '487365d5-71dc-4492-b06a-a58da6810cb8' "
            "ORDER BY county_slug, letter"
        )
        print(f"\n  ultraloop_audit rows: status={status}  {str(result)[:500]}")

        # Walton C/D check
        status, result = mgmt_sql(
            "SELECT "
            "  COUNT(*) FILTER (WHERE parity_status='matched_clean' AND parity_source LIKE 'tier1%') AS c_num, "
            "  COUNT(*) FILTER (WHERE parity_status IN ('matched_clean','matched_any') AND parity_source LIKE 'tier1%') AS d_num, "
            "  COUNT(*) AS total "
            "FROM multi_county_auctions "
            "WHERE lower(county) = 'walton'"
        )
        print(f"\n  walton C/D counts: status={status}  {str(result)[:300]}")

        # Walton I check
        status, result = mgmt_sql(
            "SELECT COUNT(*) FILTER (WHERE card_complete=true) AS cc, COUNT(*) AS total "
            "FROM multi_county_auctions WHERE lower(county)='walton'"
        )
        print(f"\n  walton I card_complete: status={status}  {str(result)[:200]}")

    print("\n\n=== DONE ===")
    print("Next step: run SELECT public.pencil_dod_evaluate_county('dixie'); and pencil_dod_evaluate_county('walton');")
    print("to confirm metric movements.")


if __name__ == "__main__":
    main()
