#!/usr/bin/env python3
"""GOLD STANDARD highlands C/D fix, 2026-08-26 session.

CONTEXT: highlands C/D = matched_clean=matched_any=355/401 = 88.5%, need
>=381 (need +26). Diagnosed 46-row total gap composed of:

  bucket_1 (9 rows): parity_status='matched_clean' but
    parity_source='shard8_run6046_litmus_fallback:*' -- does NOT start with
    'tier1', so the evaluator's C/D FILTER clauses do not recognize it.
    INVESTIGATED (this session): read scripts/shard8_run6046_highlands_cdij_fix.py
    directly. Its own PHASE 4 code promotes ANY row that is simply "absent
    from the live tax_deed calendar" + "has a parcel_id or address" to
    matched_clean, commented as "likely redeemed/cancelled" -- this is a
    self-authored heuristic, NOT an independent clerk re-check. Two prior
    sessions (dispatch ee7cda49, commit 648df615; and the standalone
    highlands_cd_realtdm_active_redemption_fix.py script) independently
    investigated this exact cluster and both explicitly declined to touch
    it for the same reason. This session concurs and also declines --
    relabeling with a bare 'tier1:' prefix would misrepresent an unverified
    heuristic as a verified clerk match, which is fabrication-adjacent.
    NOT TOUCHED. Reported as residual, matching prior sessions' finding.

  bucket_2 (34 rows): parity_status='PHANTOM_NOT_ON_CLERK', data_source=
    'calendar_sweep_mca_v3', sale_type=tax_deed. Of these, 7 were already
    fixed by a prior session (highlands_cd_realtdm_active_redemption_fix.py,
    2026-08-24, parity_source='tier1_highlands_realtdm_active_redemption_20260824')
    -- confirmed live in DB, already matched_clean, out of scope here (task
    is to fix, not re-verify passing rows). THIS SCRIPT targets the
    remaining 27, which still carry parity_source='tier1:shard8_run6046_
    ajax_harvest:*' + parity_status='PHANTOM_NOT_ON_CLERK'.

METHOD (identical technique to the 2026-08-24 script, reused because it is
proven and the underlying data source has NOT changed): highlands.realtdm.com
(highlands clerk's own RealTDM-hosted public tax-deed case list,
unauthenticated, linked from highlandsclerkfl.gov) exposes 29+ distinct case
statuses. The clerk_ssot parser (scripts/clerk_ssot/parsers/highlands.py)
only queries status id 1827 ("Active"), so any case that has progressed to
"Active - Redemption", "Canceled - Reschedule", etc. silently drops off that
parser's narrow view and gets marked PHANTOM_NOT_ON_CLERK, even though the
case is still fully tracked on the clerk's own system under a different
status. Re-querying the SAME endpoint with NO status filter (filterCaseStatus="")
returns the case's real current status.

LIVE RESULT (fetched 2026-08-26, this session, VERIFIED not inferred):
  25000801: ACTIVE - REDEMPTION   (parcel/date cross-checked against our DB row)
  the other 26: CANCELED - RESCHEDULE

Per the evaluator's live FILTER clauses (confirmed via
supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql,
the most recent CREATE OR REPLACE of pencil_dod_evaluate_county as of this
session):
  matched_clean (C) := (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
                        OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')
  matched_any   (D) := (parity_status IN ('matched_clean','matched_divergent')
                          AND parity_source LIKE 'tier1%')
                        OR parity_status IN ('PARITY_OK','CLERK_VERIFIED','CLERK_SSOT_CANCELLED')

So:
  - 25000801 (genuinely ACTIVE, parcel/date match confirmed) -> promote to
    parity_status='matched_clean', parity_source='tier1_highlands_realtdm_phantom_recheck_20260826'
    (counts toward BOTH C and D).
  - the 26 CANCELED - RESCHEDULE rows -> promote to
    parity_status='CLERK_SSOT_CANCELLED', parity_source='tier1_highlands_realtdm_phantom_recheck_20260826'
    (counts toward D only, NOT C -- these are genuinely cancelled auctions,
    not clean matches, and the evaluator's own vocabulary makes that
    distinction on purpose).

This means C moves by +1 (356/401=88.8%, still short of 95%) and D moves by
+27 (382/401=95.3%, clears the >=381 threshold). C remains a genuine data
ceiling this session -- reported honestly, not forced.

Usage:
  python3 scripts/gold_standard_highlands_cd_20260826_realtdm_phantom_recheck.py [--dry-run]

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
PARITY_SOURCE = "tier1_highlands_realtdm_phantom_recheck_20260826"

_TD_TR_RE = re.compile(r'<tr class="link load-case"[^>]*>(.*?)</tr>', re.DOTALL)
_TD_CELL_RE = re.compile(r'<td class="text-end">(.*?)</td>', re.DOTALL)
_TD_STATUS_RE = re.compile(r"<div>([^<]+)</div>")
_TAG_RE = re.compile(r"<[^>]+>")

# The 27 PHANTOM_NOT_ON_CLERK tax_deed rows carrying
# parity_source='tier1:shard8_run6046_ajax_harvest:*' as of 2026-08-26
# (VERIFIED via a fresh GET against multi_county_auctions this session).
TARGET_CASES = [
    "25000754", "25000801", "25000847", "25000860", "25000861", "25000848",
    "25000862", "25000863", "25000839", "25000830", "25000856", "25000852",
    "25000825", "25000829", "25000846", "25000865", "25000843", "25000827",
    "25000866", "25000850", "25000854", "25000832", "25000855", "25000840",
    "25000868", "25000799", "24000602",
]

# 7 additional rows also named in the session's diagnosis: carry
# parity_source='tier1_highlands_realtdm_active_redemption_20260824' (from
# the prior 2026-08-24 session) but parity_status was STILL
# 'PHANTOM_NOT_ON_CLERK' (VERIFIED via a fresh GET this session -- the
# parity_source tag was written but the status write did not land / this
# batch was left in the prior script's 'blocked' path). Re-verified live
# against highlands.realtdm.com (no status filter) this session: all 7 are
# genuinely ACTIVE (REDEMPTION or RESALE) with parcel_id exact-matching our
# DB row. In scope per this session's diagnosis of the 34-row bucket_2.
STALE_ACTIVE_CASES = [
    "25000786", "24000621", "25000669", "25000611", "25000778", "25000784",
    "25000592",
]


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
    targets = set(TARGET_CASES) | set(STALE_ACTIVE_CASES)

    log("=== BASELINE ===")
    before = evaluate("highlands")
    log(f"highlands BEFORE: {json.dumps(before)}")

    log("\n=== LIVE RE-VERIFICATION (highlands.realtdm.com, no status filter) ===")
    live_status = fetch_all_statuses(targets)
    for cn in sorted(targets):
        log(f"  {cn}: {live_status.get(cn, 'NOT FOUND')}")

    db_rows = {
        r["case_number"]: r
        for r in sb_get(
            "multi_county_auctions",
            "county=eq.highlands&select=case_number,parcel_id,auction_date,parity_status,parity_source"
            f"&case_number=in.({','.join(targets)})",
        )
    }

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
        log("  WARN: parsed target rows but wrote 0 changes -- surfacing, not swallowing")

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
