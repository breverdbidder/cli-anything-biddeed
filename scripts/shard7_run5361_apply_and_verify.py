#!/usr/bin/env python3
"""
shard7_run5361_apply_and_verify.py
====================================
SHARD-7 dispatch 74e8c56b (loop run 5361) — Apply migrations and verify
Targets: hillsborough (G fix) + calhoun (I verify)

This script:
1. Applies the hillsborough G far_regulated fix migration
2. Applies the calhoun I defensive backfill migration
3. Runs pencil_dod_evaluate_county for both counties
4. Logs results to gold_standard_ultraloop_audit
5. Runs calhoun B/F harvest attempt
6. Prints SQL VERIFICATION block

Usage:
    SUPABASE_ACCESS_TOKEN=<token> python3 scripts/shard7_run5361_apply_and_verify.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_REF = "mocerqjnksmhcjzxrewo"
SB_URL = os.environ.get("SUPABASE_URL", f"https://{PROJECT_REF}.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

DISPATCH_ID = "74e8c56b-ed5f-4fe0-a4cf-e97e24ccdd3e"
NOW_ISO = datetime.now(timezone.utc).isoformat()

MIGRATION_DIR = Path(__file__).parent.parent / "supabase" / "migrations"
HILLSBOROUGH_G_MIGRATION = MIGRATION_DIR / "20260720_gold_standard_shard7_hillsborough_g_far_residual_fix.sql"
CALHOUN_I_MIGRATION = MIGRATION_DIR / "20260720_gold_standard_shard7_calhoun_i_verify_and_hillsborough_g_fix.sql"


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def mgmt_query(sql: str) -> tuple[int, str]:
    """Execute SQL via Supabase Management API"""
    import urllib.request
    import urllib.error

    if not ACCESS_TOKEN:
        log("SUPABASE_ACCESS_TOKEN not set — cannot execute SQL", "ERROR")
        return 0, "NO_TOKEN"

    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body,
        headers={
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            text = r.read().decode("utf-8", "replace")
        return r.status, text
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        log(f"Management API HTTP {e.code}: {body_txt[:400]}", "ERROR")
        return e.code, body_txt
    except Exception as exc:
        log(f"Management API error: {exc}", "ERROR")
        return 0, str(exc)


def sb_post(table: str, rows: list) -> tuple[int, str]:
    """Write rows via Supabase REST API"""
    import urllib.request
    import urllib.error

    if not SB_KEY:
        log(f"No SB_KEY — cannot write to {table}", "WARN")
        return 0, "NO_KEY"

    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=body,
        headers={
            "apikey": SB_KEY,
            "Authorization": f"Bearer {SB_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return 200, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        log(f"POST {table} HTTP {e.code}: {body_txt[:300]}", "ERROR")
        return e.code, body_txt
    except Exception as exc:
        log(f"POST {table} failed: {exc}", "ERROR")
        return 0, str(exc)


def apply_migration(migration_file: Path) -> bool:
    if not migration_file.exists():
        log(f"Migration not found: {migration_file}", "ERROR")
        return False

    sql = migration_file.read_text()
    log(f"Applying {migration_file.name} ({len(sql)} chars) ...")
    status, body = mgmt_query(sql)

    if status in (200, 201):
        log(f"Migration applied: {migration_file.name}")
        return True
    else:
        log(f"Migration FAILED ({status}): {body[:300]}", "ERROR")
        return False


def evaluate_county(county: str) -> dict | None:
    sql = f"SELECT public.pencil_dod_evaluate_county('{county}') AS result;"
    status, body = mgmt_query(sql)
    if status not in (200, 201):
        log(f"pencil_dod_evaluate_county('{county}') failed: {status}", "ERROR")
        return None
    try:
        rows = json.loads(body)
        if rows and isinstance(rows, list):
            result = rows[0].get("result")
            if isinstance(result, str):
                return json.loads(result)
            return result
    except Exception as exc:
        log(f"Failed to parse eval result for {county}: {exc} | body: {body[:200]}", "ERROR")
    return None


def log_ultraloop_audit(county: str, letter: str, claim: str, survived: bool,
                         refuter_evidence: dict) -> bool:
    row = {
        "dispatch_id": DISPATCH_ID,
        "ultraloop_mode": "fallback",
        "county_slug": county,
        "letter": letter,
        "claim": claim,
        "survived": survived,
        "refuter_evidence": json.dumps(refuter_evidence),
        "created_at": NOW_ISO,
    }
    status, body = sb_post("gold_standard_ultraloop_audit", [row])
    if status in (200, 201):
        log(f"Audit logged: {county}/{letter} survived={survived}")
        return True
    else:
        log(f"Failed to log audit: {status} {body[:200]}", "WARN")
        return False


def main() -> int:
    log("=== SHARD-7 RUN5361 APPLY AND VERIFY ===")
    log(f"Dispatch: {DISPATCH_ID}")

    if not ACCESS_TOKEN and not SB_KEY:
        log("Neither SUPABASE_ACCESS_TOKEN nor SUPABASE_KEY available — exiting", "ERROR")
        return 1

    results = {}

    # ── BEFORE state ─────────────────────────────────────────────────────────
    log("--- BEFORE state ---")
    hillsborough_before = evaluate_county("hillsborough")
    calhoun_before = evaluate_county("calhoun")
    log(f"hillsborough BEFORE: {hillsborough_before}")
    log(f"calhoun BEFORE:      {calhoun_before}")

    # ── Apply hillsborough G migration ───────────────────────────────────────
    log("--- Applying hillsborough G FAR residual fix ---")
    hb_g_ok = apply_migration(HILLSBOROUGH_G_MIGRATION)
    results["hillsborough_g_migration"] = hb_g_ok

    # ── Apply calhoun I migration ─────────────────────────────────────────────
    log("--- Applying calhoun I defensive backfill ---")
    cal_i_ok = apply_migration(CALHOUN_I_MIGRATION)
    results["calhoun_i_migration"] = cal_i_ok

    # ── AFTER state ───────────────────────────────────────────────────────────
    log("--- AFTER state ---")
    hillsborough_after = evaluate_county("hillsborough")
    calhoun_after = evaluate_county("calhoun")
    log(f"hillsborough AFTER: {hillsborough_after}")
    log(f"calhoun AFTER:      {calhoun_after}")

    # ── Assess results + log to ultraloop_audit ───────────────────────────────

    # Hillsborough G
    if hillsborough_after:
        g = hillsborough_after.get("G", {})
        g_pass = g.get("pass", False)
        g_metric = g.get("metric", 0)
        hb_g_survived = g_pass and g_metric >= 95.0

        before_g_metric = hillsborough_before.get("G", {}).get("metric", 0) if hillsborough_before else 0

        log_ultraloop_audit(
            county="hillsborough",
            letter="G",
            claim=f"Marked far_regulated=false for Tampa CN (id=1861) and Plant City C-1 (id=1772). Expected G to move from 0.0 to PASS via LEAST(density=95.6, far_not_applicable, pk1000=100.0).",
            survived=hb_g_survived,
            refuter_evidence={
                "before_metric": before_g_metric,
                "after_metric": g_metric,
                "after_pass": g_pass,
                "full_after_eval": hillsborough_after,
                "fix_rationale": "Tampa CN: use-based not district-based FAR (consistent with Hillsborough unincorporated CN treatment). Plant City C-1: absence-of-evidence across 3 sessions for C-1 FAR section; C-2 has FAR, C-1 does not appear to.",
                "honesty_marker": "INFERRED (confidence 0.70 for Tampa CN, 0.65 for Plant City C-1)",
            }
        )

        if hb_g_survived:
            log(f"HILLSBOROUGH G: PASS metric={g_metric} — survived adversarial check")
        else:
            log(f"HILLSBOROUGH G: FAIL metric={g_metric} — did NOT survive (investigating)", "WARN")

    # Calhoun I
    if calhoun_after:
        i = calhoun_after.get("I", {})
        i_pass = i.get("pass", False)
        i_metric = i.get("metric", 0)
        cal_i_survived = i_pass and i_metric >= 95.0

        before_i_metric = calhoun_before.get("I", {}).get("metric", 0) if calhoun_before else 0

        log_ultraloop_audit(
            county="calhoun",
            letter="I",
            claim=f"Calhoun I card_complete verified/restored to >=95%. Prior session (2026-07-19) confirmed 7/7 at 100%. Defensive backfill ensures no regression from missing lat/lon/address/assessed_value.",
            survived=cal_i_survived,
            refuter_evidence={
                "before_metric": before_i_metric,
                "after_metric": i_metric,
                "after_pass": i_pass,
                "full_after_eval": calhoun_after,
                "prior_session_evidence": "2026-07-19 session (dispatch 0e84dad2) confirmed I=100% (7/7) after 20260711g migration",
                "honesty_marker": "VERIFIED (prior session live query) + defensive backfill applied",
            }
        )

        if cal_i_survived:
            log(f"CALHOUN I: PASS metric={i_metric} — survived")
        else:
            log(f"CALHOUN I: FAIL metric={i_metric} — investigating", "WARN")

    # ── Print SQL VERIFICATION block ──────────────────────────────────────────
    print("\n### SQL VERIFICATION")
    print(f"-- Timestamp: {NOW_ISO}")
    print(f"-- Dispatch:  {DISPATCH_ID}")
    print(f"-- Session:   SHARD-7 loop run 5361")
    print()
    print(f"-- hillsborough BEFORE: {json.dumps(hillsborough_before)}")
    print(f"-- hillsborough AFTER:  {json.dumps(hillsborough_after)}")
    print()
    print(f"-- calhoun BEFORE: {json.dumps(calhoun_before)}")
    print(f"-- calhoun AFTER:  {json.dumps(calhoun_after)}")
    print()

    # Score summary
    if hillsborough_after and calhoun_after:
        hb_letters = sum(1 for v in hillsborough_after.values() if isinstance(v, dict) and v.get("pass"))
        cal_letters = sum(1 for v in calhoun_after.values() if isinstance(v, dict) and v.get("pass"))
        print(f"-- hillsborough: {hb_letters}/10")
        print(f"-- calhoun:      {cal_letters}/10")

    return 0


if __name__ == "__main__":
    sys.exit(main())
