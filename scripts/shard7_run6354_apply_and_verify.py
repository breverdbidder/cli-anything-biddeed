#!/usr/bin/env python3
"""
Gold Standard Shard-7: okeechobee + miami_dade
dispatch_id: 9c1a37b0-3ff4-42f7-9cd8-813925988316
chat_session: architect-20260725T080000

Applies the migration SQL via Supabase Management API and verifies results
via pencil_dod_evaluate_county for both counties.

Usage: python3 scripts/shard7_run6354_apply_and_verify.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
                or os.environ.get("SUPABASE_KEY", ""))

DRY_RUN = "--dry-run" in sys.argv

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

MIGRATION_FILE = (
    Path(__file__).parent.parent
    / "supabase/migrations/20260725_gold_standard_shard7_okeechobee_miami_dade_9c1a37b0.sql"
)


def rpc(func_name: str, params: dict) -> dict:
    url = f"{SUPABASE_URL}/rest/v1/rpc/{func_name}"
    data = json.dumps(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:500]
        return {"error": e.code, "msg": body}
    except Exception as ex:
        return {"error": str(ex)}


def run_sql(sql: str) -> dict:
    """Execute SQL via the exec_raw RPC or Management API."""
    # Try exec_raw first (Supabase custom RPC)
    result = rpc("exec_raw", {"query": sql})
    if "error" not in result:
        return result
    # Try exec
    result2 = rpc("exec", {"sql": sql})
    if "error" not in result2:
        return result2
    return {"error": "both exec_raw and exec failed", "raw": result, "exec": result2}


def evaluate_county(county: str) -> dict:
    return rpc("pencil_dod_evaluate_county", {"p_county": county})


def check_key_fields(county: str) -> dict:
    """Check basic field coverage for a county via REST."""
    params = urllib.parse.urlencode({
        "county": f"eq.{county}",
        "select": "count",
    })
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?{params}"
    req = urllib.request.Request(url, method="GET")
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("Prefer", "count=exact")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            count_hdr = resp.getheader("Content-Range", "")
            return {"count_header": count_hdr}
    except Exception as ex:
        return {"error": str(ex)}


def main():
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("SHARD-7 run6354: okeechobee + miami_dade")
    print(f"DRY_RUN: {DRY_RUN}")
    print("=" * 70)

    # ── BEFORE state ──────────────────────────────────────────────────────────
    print("\n--- BEFORE: pencil_dod_evaluate_county ---")
    before_ok = evaluate_county("okeechobee")
    before_md = evaluate_county("miami_dade")
    print("OKEECHOBEE BEFORE:")
    print(json.dumps(before_ok, indent=2))
    print("MIAMI_DADE BEFORE:")
    print(json.dumps(before_md, indent=2))

    if DRY_RUN:
        print("\nDRY_RUN: skipping migration application")
        return

    # ── Apply migration ───────────────────────────────────────────────────────
    if not MIGRATION_FILE.exists():
        print(f"ERROR: Migration file not found: {MIGRATION_FILE}", file=sys.stderr)
        sys.exit(1)

    migration_sql = MIGRATION_FILE.read_text()
    print(f"\n--- Applying migration ({len(migration_sql)} chars) ---")

    # Split by statement-level comments/sections to apply in chunks
    # The Supabase REST exec endpoint handles multi-statement SQL
    result = rpc("exec_raw", {"query": migration_sql})
    if "error" in result:
        # Try splitting into chunks on section breaks and applying each
        print(f"exec_raw failed: {result}")
        print("Trying section-by-section application...")
        sections = migration_sql.split("-- ====")
        for i, section in enumerate(sections):
            if not section.strip() or section.strip().startswith("--"):
                continue
            chunk = "-- ====" + section if i > 0 else section
            # Extract actual SQL (skip comment-only chunks)
            sql_lines = [
                ln for ln in chunk.split("\n")
                if not ln.strip().startswith("--") and ln.strip()
            ]
            if not sql_lines:
                continue
            chunk_sql = "\n".join(
                [ln for ln in chunk.split("\n") if not ln.strip().startswith("-- ====")]
            )
            r = rpc("exec_raw", {"query": chunk_sql})
            if "error" in r:
                print(f"  Section {i} FAILED: {r}")
            else:
                print(f"  Section {i} OK")
            time.sleep(0.5)
    else:
        print(f"Migration applied: {result}")

    # ── AFTER state ───────────────────────────────────────────────────────────
    print("\n--- Sleeping 2s for DB to settle ---")
    time.sleep(2)

    print("\n--- AFTER: pencil_dod_evaluate_county ---")
    after_ok = evaluate_county("okeechobee")
    after_md = evaluate_county("miami_dade")
    print("OKEECHOBEE AFTER:")
    print(json.dumps(after_ok, indent=2))
    print("MIAMI_DADE AFTER:")
    print(json.dumps(after_md, indent=2))

    # ── Delta report ──────────────────────────────────────────────────────────
    print("\n--- DELTA REPORT ---")
    for letter in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]:
        ok_before = before_ok.get(letter, {})
        ok_after = after_ok.get(letter, {})
        md_before = before_md.get(letter, {})
        md_after = after_md.get(letter, {})

        ok_pass_before = ok_before.get("pass", False)
        ok_pass_after = ok_after.get("pass", False)
        md_pass_before = md_before.get("pass", False)
        md_pass_after = md_after.get("pass", False)

        ok_metric_before = ok_before.get("metric", "?")
        ok_metric_after = ok_after.get("metric", "?")
        md_metric_before = md_before.get("metric", "?")
        md_metric_after = md_after.get("metric", "?")

        ok_changed = ok_pass_before != ok_pass_after or ok_metric_before != ok_metric_after
        md_changed = md_pass_before != md_pass_after or md_metric_before != md_metric_after

        if ok_changed:
            ok_flag = "✅ FLIPPED" if not ok_pass_before and ok_pass_after else ("⬆" if ok_metric_after > ok_metric_before else "⬇")
            print(f"  okeechobee {letter}: {ok_metric_before} -> {ok_metric_after} {'PASS' if ok_pass_after else 'FAIL'} {ok_flag}")
        if md_changed:
            md_flag = "✅ FLIPPED" if not md_pass_before and md_pass_after else ("⬆" if md_metric_after > md_metric_before else "⬇")
            print(f"  miami_dade {letter}: {md_metric_before} -> {md_metric_after} {'PASS' if md_pass_after else 'FAIL'} {md_flag}")

    # Counts
    ok_before_pass = sum(1 for l in "ABCDEFGHIJ" if before_ok.get(l, {}).get("pass", False))
    ok_after_pass = sum(1 for l in "ABCDEFGHIJ" if after_ok.get(l, {}).get("pass", False))
    md_before_pass = sum(1 for l in "ABCDEFGHIJ" if before_md.get(l, {}).get("pass", False))
    md_after_pass = sum(1 for l in "ABCDEFGHIJ" if after_md.get(l, {}).get("pass", False))

    print(f"\nokeechobee: {ok_before_pass}/10 -> {ok_after_pass}/10")
    print(f"miami_dade: {md_before_pass}/10 -> {md_after_pass}/10")

    # ── SQL VERIFICATION BLOCK (for session report) ───────────────────────────
    print("\n### SQL VERIFICATION")
    print("```")
    print("OKEECHOBEE BEFORE:")
    print(json.dumps(before_ok))
    print("\nOKEECHOBEE AFTER:")
    print(json.dumps(after_ok))
    print("\nMIAMI_DADE BEFORE:")
    print(json.dumps(before_md))
    print("\nMIAMI_DADE AFTER:")
    print(json.dumps(after_md))
    print("```")
    print(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())}")


if __name__ == "__main__":
    main()
