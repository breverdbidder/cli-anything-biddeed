#!/usr/bin/env python3
"""highlands C/D REGRESSION fix, 2026-08-27 session (dispatch 3b3e322c).

ROOT CAUSE (diagnosed this session, VERIFIED via gh run log):
  The nightly scheduled workflow .github/workflows/gold-standard-shard8-
  gadsden-highlands.yml (cron '30 8 * * *') runs
  scripts/shard8_run6046_highlands_cdij_fix.py every day at ~08:30-08:45
  UTC. That script re-derives parity_status from scratch each run via its
  own AJAX-calendar harvest + a self-authored "litmus_fallback" heuristic,
  and does NOT preserve a prior session's CLERK_SSOT_CANCELLED
  reclassification. It unconditionally overwrites rows back toward
  PHANTOM_NOT_ON_CLERK (or a non-tier1-prefixed matched_clean that the
  evaluator's C/D FILTER clauses do not count).

  Confirmed via `gh run view <run_id> --log`:
    - commit 61f30897 (2026-08-26T08:27:33Z) fixed highlands D to
      389/401=97.0% (26 rows -> CLERK_SSOT_CANCELLED, 1 row -> matched_clean)
      and C to 363/401=90.5%.
    - GHA run 32949422278 (cron, 2026-08-26T08:45:42Z, 18 MINUTES LATER)
      already clobbered it: highlands AFTER in that run's log shows
      matched_clean=matched_any=340/401=84.8% -- CLERK_SSOT_CANCELLED count
      dropped back toward 0 same day.
    - GHA run 33069670824 (cron, 2026-08-27T11:57:44Z, this morning)
      clobbered it further to 339/401=84.5%.
    - Live at session start (this script's BASELINE step below): 344/401.

  This is a REAL, REPRODUCIBLE scheduler bug: the nightly job silently
  reverts hand-verified clerk-status reclassifications every ~24h. Flagged
  in the session report as a follow-up. NOT fixed in this session (out of
  scope per dispatch instructions -- "do not attempt a scheduler/pipeline
  architecture fix mid-session unless it's trivial and low-risk"; disabling
  or rewriting scripts/shard8_run6046_highlands_cdij_fix.py's overwrite
  behavior is neither trivial nor obviously low-risk without also auditing
  its I/J logic, which this session did not do).

THIS SESSION'S FIX: re-derive the CURRENT PHANTOM_NOT_ON_CLERK gap-row set
live from the DB (NOT reusing the 2026-08-26 hardcoded case list -- the
row composition has already shifted: 2 of the original 34 cases are now
classified matched_clean via litmus_fallback instead of PHANTOM, and one
new case, 24000615, has entered the PHANTOM set since 08-26). Re-query
highlands.realtdm.com (clerk's own public tax-deed case list, no status
filter) for each tax_deed PHANTOM case's REAL current status, using the
identical, previously-proven technique from
scripts/gold_standard_highlands_cd_20260826_realtdm_phantom_recheck.py.

Foreclosure-type PHANTOM rows (25000402GCAXMX, 25000681GCAXMX) are OUT OF
SCOPE for this script -- they are a different sale_type / different clerk
source (highlands_clerk_foreclosure), not part of the tax_deed realtdm.com
bucket this technique targets. Left untouched, not force-matched.

Usage:
  python3 scripts/highlands_shard4_3b3e322c_cd_regression_realtdm_recheck.py [--dry-run]

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

DRY_RUN = "--dry-run" in sys.argv

TD_URL = "https://highlands.realtdm.com/public/cases/list"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
PARITY_SOURCE = "tier1_highlands_realtdm_phantom_recheck_20260827_regression_fix"


_TD_TR_RE = re.compile(r'<tr class="link load-case"[^>]*>(.*?)</tr>', re.DOTALL)
_TD_CELL_RE = re.compile(r'<td class="text-end">(.*?)</td>', re.DOTALL)
_TD_STATUS_RE = re.compile(r"<div>([^<]+)</div>")
_TAG_RE = re.compile(r"<[^>]+>")


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get_all(table: str, params: str, limit: int = 500) -> List[Dict]:
    out: List[Dict] = []
    offset = 0
    while True:
        url = f"{BASE}/{table}?{params}&limit={limit}&offset={offset}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            batch = json.loads(r.read())
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return out


def sb_patch(table: str, filters: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**HEADERS, "Prefer": "return=minimal"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def evaluate(county: str) -> Dict:
    url = f"{BASE}/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def cell_text(html: str) -> str:
    return _TAG_RE.sub("", html).strip()


def fetch_all_statuses(target_cases: set) -> Dict[str, Tuple[str, List[str]]]:
    """Query realtdm.com with NO status filter to find each case's real current status."""
    found: Dict[str, Tuple[str, List[str]]] = {}
    for page in range(1, 20):
        resp = httpx.post(
            TD_URL,
            headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
                     "Content-Type": "application/x-www-form-urlencoded"},
            data={"filterFiltered": "1", "filterCaseStatus": "",
                  "filterCasesPerPage": "100", "filterPageNumber": str(page)},
            timeout=30, follow_redirects=True,
        )
        rows = _TD_TR_RE.findall(resp.text)
        if not rows:
            break
        for row_html in rows:
            status_m = _TD_STATUS_RE.search(row_html)
            status = status_m.group(1).strip() if status_m else ""
            cells = [cell_text(c) for c in _TD_CELL_RE.findall(row_html)]
            if len(cells) < 5:
                continue
            cn = cells[0].strip()
            if cn in target_cases:
                found[cn] = (status, cells)
        if len(found) == len(target_cases):
            break
        time.sleep(0.2)
    return found


def main() -> None:
    log("=== BASELINE ===")
    before = evaluate("highlands")
    log(f"highlands BEFORE: {json.dumps(before)}")

    log("\n=== RE-DERIVE CURRENT PHANTOM GAP ROWS (live, paginated, not hardcoded) ===")
    all_rows = sb_get_all(
        "multi_county_auctions",
        "county=eq.highlands&select=case_number,parcel_id,sale_type,parity_status,parity_source,auction_status",
    )
    log(f"total highlands rows: {len(all_rows)}")

    phantom_tax_deed = [
        r for r in all_rows
        if r["parity_status"] == "PHANTOM_NOT_ON_CLERK" and r["sale_type"] == "tax_deed"
    ]
    phantom_other = [
        r for r in all_rows
        if r["parity_status"] == "PHANTOM_NOT_ON_CLERK" and r["sale_type"] != "tax_deed"
    ]
    log(f"PHANTOM_NOT_ON_CLERK tax_deed (in scope, realtdm.com technique): {len(phantom_tax_deed)}")
    log(f"PHANTOM_NOT_ON_CLERK non-tax_deed (OUT OF SCOPE, different source): {len(phantom_other)}")
    for r in phantom_other:
        log(f"  SKIPPED (not tax_deed): {r['case_number']} sale_type={r['sale_type']} source={r['parity_source']}")

    targets = {r["case_number"] for r in phantom_tax_deed}
    db_rows = {r["case_number"]: r for r in phantom_tax_deed}

    log(f"\n=== LIVE RE-VERIFICATION (highlands.realtdm.com, no status filter) — {len(targets)} cases ===")
    live_status = fetch_all_statuses(targets)
    for cn in sorted(targets):
        log(f"  {cn}: {live_status.get(cn, 'NOT FOUND')}")

    active_fixed = 0
    cancelled_fixed = 0
    blocked = []

    log("\n=== APPLYING FIXES ===")
    for cn in sorted(targets):
        live = live_status.get(cn)
        row = db_rows.get(cn)
        if not live or not row:
            blocked.append({"case_number": cn, "reason": "not found live or not found in DB"})
            continue
        status, cells = live
        live_parcel = cells[3] if len(cells) > 3 else None
        status_u = status.upper()

        if "ACTIVE" in status_u:
            if live_parcel != row.get("parcel_id"):
                blocked.append({"case_number": cn, "reason": f"parcel_id mismatch live={live_parcel} db={row.get('parcel_id')}"})
                continue
            if DRY_RUN:
                log(f"  [DRY RUN] would set matched_clean: {cn} (status={status})")
                active_fixed += 1
                continue
            s, body = sb_patch(
                "multi_county_auctions",
                f"county=eq.highlands&case_number=eq.{urllib.parse.quote(cn)}",
                {
                    "parity_status": "matched_clean",
                    "parity_source": PARITY_SOURCE,
                    "parity_checked_at": ts(),
                },
            )
            if s < 300:
                active_fixed += 1
                log(f"  FIXED matched_clean: {cn} (realtdm status={status})")
            else:
                blocked.append({"case_number": cn, "reason": f"PATCH failed HTTP {s}: {body[:200]}"})

        elif "CANCELED" in status_u or "CANCELLED" in status_u:
            if live_parcel != row.get("parcel_id"):
                blocked.append({"case_number": cn, "reason": f"parcel_id mismatch live={live_parcel} db={row.get('parcel_id')}"})
                continue
            if DRY_RUN:
                log(f"  [DRY RUN] would set CLERK_SSOT_CANCELLED: {cn} (status={status})")
                cancelled_fixed += 1
                continue
            s, body = sb_patch(
                "multi_county_auctions",
                f"county=eq.highlands&case_number=eq.{urllib.parse.quote(cn)}",
                {
                    "parity_status": "CLERK_SSOT_CANCELLED",
                    "parity_source": PARITY_SOURCE,
                    "auction_status": "CANCELLED",
                    "parity_checked_at": ts(),
                },
            )
            if s < 300:
                cancelled_fixed += 1
                log(f"  FIXED CLERK_SSOT_CANCELLED: {cn} (realtdm status={status})")
            else:
                blocked.append({"case_number": cn, "reason": f"PATCH failed HTTP {s}: {body[:200]}"})
        else:
            blocked.append({"case_number": cn, "reason": f"unrecognized live status: {status}"})

    log(f"\nactive_fixed={active_fixed}  cancelled_fixed={cancelled_fixed}  blocked={len(blocked)}")
    for b in blocked:
        log(f"  BLOCKED: {b}")

    if active_fixed + cancelled_fixed == 0 and len(targets) > 0:
        raise RuntimeError(
            f"FAIL-LOUD: parsed {len(targets)} target rows but wrote 0 changes -- "
            "not swallowing silently"
        )

    time.sleep(2)
    log("\n=== POST-FIX EVALUATION ===")
    after = evaluate("highlands") if not DRY_RUN else before
    log(f"highlands AFTER: {json.dumps(after)}")

    print("\n### SQL VERIFICATION")
    print(f"Timestamp: {ts()}")
    print(f"highlands BEFORE: {json.dumps(before)}")
    print(f"highlands AFTER:  {json.dumps(after)}")
    print(f"active_fixed={active_fixed} cancelled_fixed={cancelled_fixed} blocked={blocked}")


if __name__ == "__main__":
    main()
