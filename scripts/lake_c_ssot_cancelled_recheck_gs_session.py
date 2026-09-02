#!/usr/bin/env python3
"""Lake C letter fix, Gold Standard county-scoped session (2026-09-02).

Targeted re-run of the vetted lake courtrecords.lakecountyclerk.org/sci docket-
check lever (see scripts/lake_c_showcaseweb_docket_recheck_5f3a88a5.py for full
method docstring) against the CURRENT 19 lake parity_status='CLERK_SSOT_CANCELLED'
rows, scoped to write ONLY the single unambiguous hit this session confirmed by
hand: case 2025CA000251.

Full dry-run of the prior session's script (lake_c_showcaseweb_docket_recheck_
5f3a88a5.py --dry-run) against the current 19-row remainder found 2 candidates:

  - 2016CA002108: FALSE POSITIVE of that script's null-cutoff handling. Its
    parity_checked_at is NULL, so the script's "new_entries" filter degenerates
    to the case's ENTIRE docket history (172 entries back to 2016), which
    trivially contains old RESCHEDULE/RESET keyword hits from 2021 and 2026-07/08.
    Manually walked the full chronological docket for this case: the true most
    recent entry is 2026-08-18T15:34:50 "FORECLOSURE SALE CANCELLED" -- AFTER
    the 2026-08-04 "ORDER RESETTING/RESCHEDULING" entry that the buggy null-
    cutoff scan picked up. The case is genuinely, currently cancelled. NOT
    patched. Left as CLERK_SSOT_CANCELLED (correct).

  - 2025CA000251: parity_checked_at=2026-08-02 (real cutoff). New docket
    entries since then, in chronological order: 2026-08-21 PROOF OF
    PUBLICATION -> 2026-08-24 FORECLOSURE SALE CANCELLED -> 2026-09-01 MOTION
    TO RESCHEDULE FORECLOSURE SALE (most recent entry, no later cancellation).
    This is the same unambiguous reopen-after-cancellation pattern as the
    documented 2024CA000186 precedent (shard2 dispatch 5f3a88a5). Genuine,
    live, current reschedule motion -- not fabricated. PATCHED.

This script does NOT touch cron jobs 109/111/115 or any gold_standard_loop
scoring job, and does not run gold_standard_loop()/certify(). Single targeted
PATCH via PostgREST REST API, same auth/read/write pattern as the shard2
script it forks from.

Usage: python3 scripts/lake_c_ssot_cancelled_recheck_gs_session.py [--dry-run]
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

DRY_RUN = "--dry-run" in sys.argv
TARGET_CASE = "2025CA000251"


def sb_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(row_id, body):
    url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={**REST_HEADERS, "Prefer": "return=minimal"}, method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_insert(table, row):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}", data=json.dumps(row).encode(),
        headers={**REST_HEADERS, "Prefer": "return=minimal"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    rows = sb_get(
        "multi_county_auctions?county=eq.lake&data_source=neq.propertyonion"
        f"&case_number=eq.{TARGET_CASE}&parity_status=eq.CLERK_SSOT_CANCELLED"
        "&select=id,case_number,auction_date,auction_status,parity_checked_at,parity_source"
    )
    if not rows:
        print(f"[INFO] no matching CLERK_SSOT_CANCELLED row found for {TARGET_CASE} -- nothing to do")
        return

    row = rows[0]
    print(f"[INFO] target row: {row}")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] BASELINE C: {baseline['C']}")

    body = {
        "parity_status": "CLERK_VERIFIED",
        "parity_source": "lake_courtrecords_docket:gs_session_20260902_recheck",
        "parity_checked_at": datetime.now(timezone.utc).isoformat(),
    }
    # 2026-09-01T15:23:43 MOTION TO RESCHEDULE FORECLOSURE SALE is the most
    # recent docket entry (post-dates the 2026-08-24 CANCELLED entry, no
    # later cancellation). Do NOT fabricate a specific new auction_date --
    # the docket text gives a motion, not yet a new noticed sale date/time.
    # Leave auction_date/auction_status as-is per the conservative BLANK >
    # WRONG rule; only the parity classification changes.
    print(f"[INFO] patch body: {body}")

    if DRY_RUN:
        print("### DRY-RUN COMPLETE -- no writes performed")
        return

    wstatus = sb_patch(row["id"], body)
    print(f"[INFO] PATCH multi_county_auctions id={row['id']} -> status {wstatus}")

    log_row = {
        "dispatch_id": "lake-C-gs-session-20260902",
        "task": "lake letter C — CLERK_SSOT_CANCELLED live re-verify",
        "status": "VERIFIED",
        "evidence": (
            f"{TARGET_CASE} CLERK_SSOT_CANCELLED -> CLERK_VERIFIED on unambiguous "
            "2026-09-01 MOTION TO RESCHEDULE docket entry post-dating the 2026-08-24 "
            "CANCELLED entry. 2016CA002108 checked and confirmed still genuinely "
            "cancelled (most recent docket entry 2026-08-18 FORECLOSURE SALE "
            "CANCELLED, post-dates its own earlier reschedule motion) -- left "
            "untouched. Remaining 17 CLERK_SSOT_CANCELLED + 1 PHANTOM_NOT_ON_CLERK "
            "rows show no new reschedule/reopen evidence since last "
            "parity_checked_at; correctly excluded from matched_clean per canon C "
            "rationale (field divergence vs clerk source of truth). Likely a soft "
            "structural ceiling for lake C, not a bug -- most of the remainder are "
            "genuinely cancelled auctions with no re-verification mechanism once "
            "auction_date passes (separate pipeline issue in run_parity.py, not "
            "fixed this session)."
        ),
        "severity": "info",
    }
    log_status = sb_insert("agent_ops_log", log_row)
    print(f"[INFO] agent_ops_log insert -> {log_status}")

    after = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] AFTER C: {after['C']}")
    print(f"BEFORE C: {baseline['C']}")
    print(f"AFTER  C: {after['C']}")


if __name__ == "__main__":
    main()
