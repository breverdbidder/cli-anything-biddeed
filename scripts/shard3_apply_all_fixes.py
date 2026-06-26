#!/usr/bin/env python3
"""
SHARD-3 GOLD STANDARD FIX EXECUTOR
Counties: broward, columbia, bay, miami_dade
dispatch_id: 4ad1d5d6-faa5-4219-8809-f6401586b34e

Applies all 4 county migrations via Supabase management API and reports results.
Run: SUPABASE_ACCESS_TOKEN=... SUPABASE_KEY=... python3 scripts/shard3_apply_all_fixes.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx", "--quiet"])
    import httpx

ACCESS_TOKEN = (
    os.environ.get("SUPABASE_ACCESS_TOKEN")
    or os.environ.get("SUPABASE_ACCESS_TOKEN")
    or ""
)
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
PROJECT_REF = "mocerqjnksmhcjzxrewo"

MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
MGMT_HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}")


def run_sql(sql: str, label: str = "") -> list[dict]:
    """Run SQL via Supabase management API."""
    client = httpx.Client(timeout=120)
    try:
        resp = client.post(MGMT_URL, headers=MGMT_HEADERS, json={"query": sql})
        if resp.status_code in (200, 201):
            return resp.json() if resp.text.strip() != "" else []
        else:
            log(f"SQL {label} FAILED {resp.status_code}: {resp.text[:300]}", "ERROR")
            return []
    except Exception as e:
        log(f"SQL {label} ERROR: {e}", "ERROR")
        return []


def apply_migration(path: Path) -> bool:
    """Read and execute a migration file."""
    sql = path.read_text()
    log(f"Applying {path.name} ({len(sql)} chars)...")

    # Split on statement boundaries for the management API
    # The management API prefers single statements but handles multi-statement SQL
    result = run_sql(sql, label=path.stem)
    log(f"  -> {len(result)} result rows")
    if result:
        for row in result[:5]:
            log(f"     {row}", "RESULT")
    return True


def evaluate_county(county: str) -> dict:
    """Run pencil_dod_evaluate_county for a county.
    Returns the inner evaluation dict with uppercase A-J keys.
    The management API wraps the result as: [{"pencil_dod_evaluate_county": {...}}]
    """
    sql = f"SELECT * FROM public.pencil_dod_evaluate_county('{county}');"
    result = run_sql(sql, label=f"eval_{county}")
    if not result:
        return {}
    row = result[0]
    # Unwrap nested result: {"pencil_dod_evaluate_county": {"A": {...}, ...}}
    if "pencil_dod_evaluate_county" in row:
        return row["pencil_dod_evaluate_county"]
    return row


def count_letters_passing(eval_result: dict) -> int:
    """Count passing letters from pencil_dod evaluation.
    Evaluator returns uppercase keys A through J.
    """
    if not eval_result:
        return 0
    passing = 0
    for letter in "ABCDEFGHIJ":
        val = eval_result.get(letter)
        if isinstance(val, dict):
            if val.get("pass") is True:
                passing += 1
        elif val is True:
            passing += 1
    return passing


def main() -> None:
    log("=== SHARD-3 GOLD STANDARD FIX EXECUTOR ===", "START")
    log(f"Project: {PROJECT_REF}")
    log(f"Token: {'SET' if ACCESS_TOKEN else 'MISSING!'}")
    log(f"Key:   {'SET' if SB_KEY else 'MISSING!'}")

    if not ACCESS_TOKEN:
        log("SUPABASE_ACCESS_TOKEN required for management API — aborting", "ERROR")
        sys.exit(1)

    # Migration files for this shard — all waves
    migration_dir = Path("supabase/migrations")
    migrations = [
        # Wave 1 (applied in run 28208565949)
        migration_dir / "20260626_shard3_broward_a_fix.sql",
        migration_dir / "20260626_shard3_columbia_bcd_fix.sql",
        migration_dir / "20260626_shard3_bay_bcdfgi_fix.sql",
        migration_dir / "20260626_shard3_miami_dade_fix.sql",
        migration_dir / "20260626_shard3_miami_dade_j_generator.sql",
        # Wave 2 (applied in run 28208866477 — broward+columbia now 10/10)
        migration_dir / "20260626_shard3_wave2_cd_columbia_bay.sql",
        migration_dir / "20260626_shard3_wave2_broward_verify_certify.sql",
        # Wave 3 (bay B/F + miami_dade J generator)
        migration_dir / "20260626_shard3_wave3_bay_bf_miami_j.sql",
        migration_dir / "20260626_shard3_wave3_columbia_bf.sql",
        # Wave 4 (miami_dade H refresh + bay C/D schema-safe fix)
        migration_dir / "20260626_shard3_wave4_h_refresh_and_bay_cd.sql",
        # Wave 5 (miami_dade H last_changed_at fix + J generator fixed + bay B gap)
        migration_dir / "20260626_shard3_wave5_miami_h_j_bay_b.sql",
    ]

    # ── Pre-run evaluation ────────────────────────────────────────────────────
    counties = ["broward", "columbia", "bay", "miami_dade"]
    log("--- PRE-FIX EVALUATION ---", "EVAL")
    before_scores: dict[str, int] = {}
    for county in counties:
        result = evaluate_county(county)
        score = count_letters_passing(result)
        before_scores[county] = score
        log(f"  {county}: {score}/10 letters passing", "BEFORE")

    # ── Apply migrations ──────────────────────────────────────────────────────
    log("--- APPLYING MIGRATIONS ---", "MIGRATE")
    for migration in migrations:
        if not migration.exists():
            log(f"Migration not found: {migration}", "WARN")
            continue
        success = apply_migration(migration)
        if not success:
            log(f"Migration FAILED: {migration.name}", "ERROR")
        time.sleep(1)  # Brief pause between migrations

    # ── Post-run evaluation ───────────────────────────────────────────────────
    log("--- POST-FIX EVALUATION ---", "EVAL")
    after_scores: dict[str, int] = {}
    eval_results: dict[str, dict] = {}
    for county in counties:
        result = evaluate_county(county)
        score = count_letters_passing(result)
        after_scores[county] = score
        eval_results[county] = result
        delta = score - before_scores.get(county, 0)
        status = "+" if delta > 0 else ("=" if delta == 0 else "")
        log(f"  {county}: {score}/10 ({status}{delta} letters) {'✓ GOLD!' if score==10 else ''}", "AFTER")

    # ── Print full evaluation JSON for issue comment ──────────────────────────
    log("--- FULL EVALUATION OUTPUT (paste into issue) ---", "VERIFY")
    for county in counties:
        print(f"\n### SQL VERIFICATION — {county.upper()}")
        print(f"Before: {before_scores.get(county, '?')}/10 → After: {after_scores.get(county, '?')}/10")
        print("```json")
        print(json.dumps(eval_results.get(county, {}), indent=2, default=str))
        print("```")

    # ── Populate ultraloop audit rows ─────────────────────────────────────────
    dispatch_id = "4ad1d5d6-faa5-4219-8809-f6401586b34e"
    for county in counties:
        score = after_scores.get(county, 0)
        before = before_scores.get(county, 0)
        if score > before:
            # Record improvement in audit table
            letters_improved = []
            ev = eval_results.get(county, {})
            for letter in "abcdefghij":
                key = f"letter_{letter}"
                if key in ev:
                    val = ev[key]
                    passing = (val.get("pass") if isinstance(val, dict) else val) or False
                    if passing:
                        letters_improved.append(letter.upper())

            for letter in letters_improved:
                sql = f"""
                INSERT INTO gold_standard_ultraloop_audit
                  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
                VALUES (
                  '{dispatch_id}',
                  'fallback',
                  '{county}',
                  '{letter}',
                  'Letter {letter} moved from {before}/10 to {score}/10 after shard3 migration 20260626',
                  '{{"query": "pencil_dod_evaluate_county", "score_after": {score}, "score_before": {before}}}'::jsonb,
                  true
                )
                ON CONFLICT DO NOTHING;
                """
                run_sql(sql, label=f"audit_{county}_{letter}")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_before = sum(before_scores.values())
    total_after = sum(after_scores.values())
    log(f"=== SESSION RESULT: {total_before} → {total_after} letter-points across {len(counties)} counties ===", "DONE")
    log("", "DONE")

    # Return non-zero if any county regressed
    regressions = [c for c in counties if after_scores.get(c, 0) < before_scores.get(c, 0)]
    if regressions:
        log(f"REGRESSION DETECTED in: {regressions}", "ERROR")
        sys.exit(2)


if __name__ == "__main__":
    main()
