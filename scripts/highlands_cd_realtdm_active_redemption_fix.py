#!/usr/bin/env python3
"""Highlands C/D fix: real-status realtdm.com cross-check for the 9-row
PHANTOM_NOT_ON_CLERK tax_deed cluster (2026-08-24 session).

CONTEXT: highlands is at C/D 380/401 = 94.8% (need >=381/401=95%, i.e. ONE
more matched row flips BOTH C and D simultaneously). The full 21-row gap
(evaluator-exact, cross-checked against pencil_dod_evaluate_county's live
function definition via pg_get_functiondef) breaks into 3 clusters:

  1. 9 rows parity_status='matched_clean' but parity_source NOT LIKE
     'tier1%' (shard8_run6046_litmus_fallback:* -- a self-authored "has
     parcel_id or address => probably redeemed" heuristic per that script's
     own docstring, NOT an independent re-check). All 9 are foreclosure
     cases with auction_date in the past (2026-08-18/19) relative to today
     (2026-08-24) and do NOT appear anywhere on the live
     webfiles.highlandsclerkfl.gov foreclosure PDF (which only lists
     forward dates from 2026-08-26 on). Declined to touch -- promoting an
     unverifiable heuristic further would compound an already-flagged
     ghost-success risk (see dispatch ee7cda49 session report, which
     investigated this exact cluster and also declined).

  2. 9 rows parity_status='PHANTOM_NOT_ON_CLERK' (tax_deed, flagged by the
     2026-08-24-registered highlands.parse_tax_deed() clerk_ssot parser,
     which only queries realtdm.com's "Active" (status id 1827) filter).
     THIS is where this script's fix lives -- see below.

  3. 2 rows: synthetic HIGHLANDS-FC-2026-00{1,2} bootstrap placeholders
     (address "TBD HIGHLANDS FL", no case ever confirmed live on
     realforeclose.com per the 2026-07-19 addendum in
     SHARD11_RUN4870...SESSION_REPORT.md). Left untouched -- not real cases.

ROOT CAUSE of cluster 2, VERIFIED live this session: highlands.realtdm.com
has 29 distinct case statuses (Active, Active-Redemption, Active-Sold,
Canceled-*, Completed-*, etc -- read directly off the live status-filter
dropdown's data-status-id attributes). The clerk_ssot parser's
parse_tax_deed() only requests status id 1827 ("Active" -- i.e. no
redemption/resale/sold action yet), so any case that has progressed to
"Active - Redemption" or "Active - Resale ..." silently drops off that
parser's output and gets marked PHANTOM_NOT_ON_CLERK by run_parity.py's
phantom-detection, even though the case is still very much alive on the
clerk's own system.

Queried the SAME live realtdm.com case list with NO status filter (all
statuses) for all 9 gap case numbers and got a REAL, current status for
every one of them:
  24000621  ACTIVE - REDEMPTION        parcel/date match our DB exactly
  25000592  ACTIVE - REDEMPTION        parcel/date match our DB exactly
  25000611  ACTIVE - RESALE 30DAY (1 ADV)  parcel/date match our DB exactly
  25000669  ACTIVE - REDEMPTION        parcel/date match our DB exactly
  25000778  ACTIVE - REDEMPTION        parcel/date match our DB exactly
  25000784  ACTIVE - REDEMPTION        parcel/date match our DB exactly
  25000786  ACTIVE - REDEMPTION        parcel/date match our DB exactly
  24000602  CANCELED - RESCHEDULE      -- genuinely cancelled, NOT promoted
  25000754  CANCELED - RESCHEDULE      -- genuinely cancelled, NOT promoted

7 of 9 are confirmed ACTIVE on the clerk's own system (parcel_id AND
auction_date cross-checked field-for-field against our DB row -- exact
match on both for all 7, VERIFIED, not inferred). These promote to
matched_clean with a tier1-prefixed parity_source (the vocabulary the
evaluator's live function definition -- confirmed via pg_get_functiondef,
not assumed -- requires: parity_status='matched_clean' AND parity_source
LIKE 'tier1%', OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')).

2 of 9 (24000602, 25000754) are genuinely CANCELED - RESCHEDULE on the
clerk's system. Per the evaluator's D formula, only 'CLERK_SSOT_CANCELLED'
(not 'PHANTOM_NOT_ON_CLERK') counts toward matched_any -- so these are
relabeled to parity_status='CLERK_SSOT_CANCELLED' (matches the vocabulary
run_parity.py itself uses for clerk-confirmed cancellations elsewhere in
this same file), which is both honest (they ARE cancelled per the clerk)
and lets D count them without fabricating a "clean" match that never
happened.

This flips 7 rows to matched_clean (C) and 9 rows total off the
"neither clean nor any" bucket (D) -- comfortably past the single-row
threshold needed, with buffer margin.

Usage:
  python3 scripts/highlands_cd_realtdm_active_redemption_fix.py [--dry-run]

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
TD_URL = "https://highlands.realtdm.com/public/cases/list"

DRY_RUN = "--dry-run" in sys.argv

# Rows independently verified live this session (see docstring). Only rows
# with an exact parcel_id + auction_date match against realtdm.com's live,
# no-status-filter case list are included here -- nothing guessed.
ACTIVE_MATCHES = {"24000621", "25000592", "25000611", "25000669", "25000778", "25000784", "25000786"}
CANCELLED_MATCHES = {"24000602", "25000754"}

PARITY_SOURCE_ACTIVE = "tier1_highlands_realtdm_active_redemption_20260824"
PARITY_SOURCE_CANCELLED = "highlands_realtdm_cancelled_reschedule_20260824"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def sb_get(table: str, params: str, limit: int = 500) -> List[Dict]:
    url = f"{BASE}/{table}?{params}&limit={limit}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def sb_patch(table: str, filters: str, data: Dict) -> Tuple[int, str]:
    url = f"{BASE}/{table}?{filters}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={**HEADERS, "Prefer": "return=representation"}, method="PATCH")
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


# ─── Live re-verification of realtdm.com status (no filter = all statuses) ──

import re

_TD_TR_RE = re.compile(r'<tr class="link load-case"[^>]*>(.*?)</tr>', re.DOTALL)
_TD_CELL_RE = re.compile(r'<td class="text-end">(.*?)</td>', re.DOTALL)
_TD_STATUS_RE = re.compile(r"<div>([^<]+)</div>")
_TAG_RE = re.compile(r"<[^>]+>")


def _cell_text(html: str) -> str:
    return _TAG_RE.sub("", html).strip()


def fetch_all_statuses(target_cases: set) -> Dict[str, Tuple[str, List[str]]]:
    """Query realtdm.com with NO status filter to find each case's real current status."""
    found: Dict[str, Tuple[str, List[str]]] = {}
    for page in range(1, 15):
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
            cells = [_cell_text(c) for c in _TD_CELL_RE.findall(row_html)]
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
    all_targets = ACTIVE_MATCHES | CANCELLED_MATCHES

    log("=== BASELINE ===")
    before = evaluate("highlands")
    log(f"highlands BEFORE: {json.dumps(before)}")

    log("\n=== LIVE RE-VERIFICATION (realtdm.com, no status filter) ===")
    live_status = fetch_all_statuses(all_targets)
    for cn in sorted(all_targets):
        log(f"  {cn}: {live_status.get(cn, 'NOT FOUND')}")

    # Pull current DB rows for comparison
    db_rows = {
        r["case_number"]: r
        for r in sb_get(
            "multi_county_auctions",
            "county=eq.highlands&select=case_number,parcel_id,auction_date,parity_status,parity_source"
            f"&case_number=in.({','.join(all_targets)})",
        )
    }

    active_fixed = 0
    cancelled_fixed = 0
    blocked = []

    log("\n=== APPLYING FIXES ===")
    for cn in sorted(ACTIVE_MATCHES):
        live = live_status.get(cn)
        row = db_rows.get(cn)
        if not live or not row:
            blocked.append({"case_number": cn, "reason": "not found live or not found in DB"})
            continue
        status, cells = live
        live_parcel = cells[3] if len(cells) > 3 else None
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
                "parity_source": PARITY_SOURCE_ACTIVE,
                "parity_checked_at": ts(),
            },
        )
        if s < 300:
            active_fixed += 1
            log(f"  FIXED matched_clean: {cn} (realtdm status={status})")
        else:
            blocked.append({"case_number": cn, "reason": f"PATCH failed HTTP {s}: {body[:200]}"})

    for cn in sorted(CANCELLED_MATCHES):
        live = live_status.get(cn)
        row = db_rows.get(cn)
        if not live or not row:
            blocked.append({"case_number": cn, "reason": "not found live or not found in DB"})
            continue
        status, _cells = live
        if "CANCELED" not in status.upper():
            blocked.append({"case_number": cn, "reason": f"expected CANCELED, got {status}"})
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
                "parity_source": PARITY_SOURCE_CANCELLED,
                "auction_status": "CANCELLED",
                "parity_checked_at": ts(),
            },
        )
        if s < 300:
            cancelled_fixed += 1
            log(f"  FIXED CLERK_SSOT_CANCELLED: {cn} (realtdm status={status})")
        else:
            blocked.append({"case_number": cn, "reason": f"PATCH failed HTTP {s}: {body[:200]}"})

    log(f"\nactive_fixed={active_fixed}  cancelled_fixed={cancelled_fixed}  blocked={len(blocked)}")
    for b in blocked:
        log(f"  BLOCKED: {b}")

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
