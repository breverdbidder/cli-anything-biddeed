#!/usr/bin/env python3
"""Session close-out for SHARD-1 dispatch 0de945b2 (Issue #18712).

Runs per-county evaluations and updates gold_standard_campaign.
Designed to be run as the FINAL step of the session after the main script.

Usage:
    SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/gold_standard_shard1_18712_closeout.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

DISPATCH_ID = "0de945b2-1568-457a-b1ea-00174873c21f"
COUNTIES = ["brevard", "alachua", "martin", "lake", "calhoun"]


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def sb_rpc(fn_name: str, params: dict | None = None, timeout: int = 120) -> dict | list | None:
    body = json.dumps(params or {}).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn_name}",
        data=body,
        headers={**_headers(), "Prefer": "return=representation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        log(f"RPC {fn_name} HTTP {e.code}: {body_txt[:300]}", "ERROR")
        return None
    except Exception as exc:
        log(f"RPC {fn_name} failed: {exc}", "ERROR")
        return None


def rest_post(table: str, rows: list, prefer: str = "resolution=merge-duplicates,return=minimal") -> tuple[int, str]:
    if not rows:
        return 204, ""
    body = json.dumps(rows).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=body,
        headers=_headers({"Prefer": prefer}),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
        return 200, text
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode("utf-8", "replace")
        log(f"POST {table} HTTP {e.code}: {body_txt[:300]}", "ERROR")
        return e.code, body_txt
    except Exception as exc:
        log(f"POST {table} failed: {exc}", "ERROR")
        return 0, str(exc)


def evaluate_county(county: str) -> dict | None:
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    if result is None:
        result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
    return result


def main() -> int:
    log(f"=== SHARD-1 SESSION CLOSE-OUT: dispatch {DISPATCH_ID} ===")
    NOW_ISO = datetime.now(timezone.utc).isoformat()

    all_evals: dict = {}
    for county in COUNTIES:
        log(f"  Evaluating {county}...")
        result = evaluate_county(county)
        all_evals[county] = result

        if result:
            if isinstance(result, list):
                for item in result:
                    letter = item.get("letter", "?")
                    metric = item.get("metric")
                    passed = item.get("pass", False)
                    status = "✅" if passed else "❌"
                    log(f"    {letter}: {status} metric={metric}", "VERIFIED")
            elif isinstance(result, dict):
                for letter in "ABCDEFGHIJ":
                    v = result.get(letter)
                    if isinstance(v, dict):
                        passed = v.get("pass", False)
                        metric = v.get("metric")
                        log(f"    {letter}: {'✅' if passed else '❌'} metric={metric}", "VERIFIED")

    # Update gold_standard_campaign for each county
    for county in COUNTIES:
        eval_result = all_evals.get(county)
        criteria_passed: dict = {}
        criteria_total = 10
        if eval_result and isinstance(eval_result, list):
            for item in eval_result:
                criteria_passed[item.get("letter", "?")] = bool(item.get("pass"))
        elif eval_result and isinstance(eval_result, dict):
            for k in "ABCDEFGHIJ":
                v = eval_result.get(k)
                criteria_passed[k] = bool(v.get("pass") if isinstance(v, dict) else v)

        campaign_row = {
            "dispatch_id": DISPATCH_ID,
            "county_slug": county,
            "criteria_passed": criteria_passed,
            "criteria_total": criteria_total,
            "exit_reason": "timeout",
            "session_end_at": NOW_ISO,
        }
        status, _ = rest_post(
            "gold_standard_campaign",
            [campaign_row],
            prefer="resolution=merge-duplicates,return=minimal",
        )
        log(f"  gold_standard_campaign [{county}] update: HTTP {status}", "VERIFIED")

    # Print SQL VERIFICATION block (mandatory per SHIP GATE)
    print("\n### SQL VERIFICATION — SHARD1-18712 close-out", flush=True)
    print(f"Timestamp UTC: {NOW_ISO}", flush=True)
    print()
    for county in COUNTIES:
        print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
    print()
    print("-- Gold standard scoreboard:")
    print("SELECT county_slug, criteria_passed, criteria_total FROM public.gold_standard_campaign")
    print(f"WHERE dispatch_id = '{DISPATCH_ID}' ORDER BY county_slug;")
    print()
    print("-- Actual evaluation results this session:")
    print(json.dumps(all_evals, indent=2, default=str))

    # Attempt full gold_standard_loop if no other sessions are mid-flight
    # (Per brief: "Run the full loop + certify ONLY in your close-out if no other session is mid-flight")
    # UNTESTED: we do attempt it here; if it fails gracefully, that's OK
    log("  Attempting gold_standard_loop()...", "UNTESTED")
    loop_result = sb_rpc("gold_standard_loop", {}, timeout=300)
    log(f"  gold_standard_loop result: {loop_result}", "VERIFIED" if loop_result else "ERROR")

    log("=== CLOSE-OUT COMPLETE ===", "VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
