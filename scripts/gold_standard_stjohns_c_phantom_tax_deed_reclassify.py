#!/usr/bin/env python3
"""Gold Standard st_johns letter C investigation (this dispatch).

TARGET: TD26-0024, TD26-0038, TD26-0034 (parity_status=PHANTOM_NOT_ON_CLERK,
auction_date=2026-08-19, 6 days in the past) + re-verify TD26-0031 (already
CLERK_SSOT_CANCELLED). All four are St Johns County tax-deed sales.

============================================================================
LIVE CROSS-CHECK (this session, via scripts/clerk_ssot/parsers/st_johns.py's
apps.stjohnsclerk.com/TaxSmart TributeWeb-style flow -- the official St Johns
Clerk tax-deed system)
============================================================================
parse_tax_deed() only ever queries SearchTypeStatus=2 ("SALE" -- upcoming,
not-yet-occurred). Since these 4 auctions were dated 2026-08-19 (in the past
relative to today, 2026-08-25), they have already dropped out of the "SALE"
window and legitimately return nothing from that endpoint -- this is why
run_parity.py's daily cron correctly flagged 3 of them PHANTOM_NOT_ON_CLERK
(no longer visible in the live upcoming-sale feed) rather than a parser bug.

To find their CURRENT resolved status, this script queries every other
TaxSmart status bucket the site exposes (BANKRUPTCY=8, CANCELLED=14,
CANCELLED/SCO=17, ESCHEATED=7, LANDS_AVAILABLE=5, NO_BID=11, REDEEMED=4,
SOLD=3) over a 90-day window bracketing today. Live result (2026-08-25):

  TD26-0024  parcel 243630-0000  -> REDEEMED  ($278,673.96 cert)
  TD26-0034  parcel 070291-1960  -> REDEEMED  ($40,761.62 cert)
  TD26-0038  parcel 194090-0000  -> CANCELLED ($84,778.01 cert)
  TD26-0031  parcel 026331-0300  -> REDEEMED  ($7,094.66 cert)  [re-verify]

All 4 parcel_ids match our stored parcel_id column exactly (dash/formatting
normalized). This is a genuine, current, official-clerk-confirmed outcome --
not a parser gap and not a stale DB snapshot.

============================================================================
WHY THIS DOES NOT MOVE LETTER C (matched_clean)
============================================================================
Every other clerk_ssot parser in this repo (dixie, franklin, calhoun, levy,
st_lucie, nassau, wakulla -- see scripts/clerk_ssot/parsers/*.py) treats
REDEEMED identically to CANCELLED: the tax certificate was redeemed by the
owner before the sale occurred, so the auction never happened. It is NOT a
clean "sale went off as scheduled" match. run_parity.py's own reconciliation
logic (scripts/clerk_ssot/run_parity.py lines ~324-350) routes any SSOT row
with cancelled=True to CLERK_SSOT_CANCELLED, never PARITY_OK.

pencil_dod_evaluate_county's own FILTER clause (supabase/migrations/
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql, lines
50-53) is explicit: CLERK_SSOT_CANCELLED counts toward matched_any (D) only,
never matched_clean (C) -- "it represents a divergence that clerk_ssot found
and corrected, which is the same class as matched_divergent, not a
no-divergence-ever clean match." Stamping these 4 rows PARITY_OK to move C
would misrepresent 4 cancelled/redeemed auctions as clean parity matches --
exactly the ghost-success anomaly class this campaign exists to reject.

============================================================================
WHAT THIS SCRIPT DOES
============================================================================
Corrects the 3 currently-PHANTOM rows to their true, live-clerk-confirmed
state (CLERK_SSOT_CANCELLED, matching the convention already used for
TD26-0031) -- an accuracy fix and a legitimate D-pool member, but NOT a C
fix, since C requires PARITY_OK/CLERK_VERIFIED and none of these 4 rows
qualify. TD26-0031 is re-verified (still REDEEMED live) and left untouched
(already correctly stamped).

============================================================================
LETTER C CONCLUSION: BLOCKED (genuine data ceiling, not a bug)
============================================================================
The only pool of rows that could move matched_clean toward the 105/110
threshold is exactly: 3 tax_deed PHANTOM rows (this script: confirmed
REDEEMED/CANCELLED, correctly NOT clean) + 1 tax_deed CLERK_SSOT_CANCELLED
row (TD26-0031: reconfirmed REDEEMED, correctly NOT clean) + 3 foreclosure
matched_divergent rows (CA24-1264, CA25-1742, CA25-1792 -- future auctions,
2026-09-17/24).

The foreclosure trio was separately investigated this session via a fresh
live RealForeclose AJAX pull (scripts/shard2_run2450_ajax_realforeclose_
harvest.py, subdomain='saintjohns' -- NOT 'stjohns', confirmed via the
existing realforeclose_aids.county_subdomain column). All 3 cases are found
live, with parcel_id/address/judgment_amount matching our stored row for
CA25-1742. However:
  - A prior session (scripts/gold_standard_shard4_st_johns_cd_parity_source_
    backfill.py, dispatch 7d59c973) already examined CA25-1742 specifically
    and deliberately left parity_status='matched_divergent' (only backfilled
    parity_source), meaning a real field-level divergence was found and
    intentionally not overridden.
  - This session found no new evidence resolving what that divergence is:
    parity_divergences is NULL on the live row and tier1_sale_status='LISTED'
    is itself neutral (consistent with "still scheduled", not proof of
    agreement or disagreement). The row was re-verified by an automated
    tier1 cron job today (tier1_source_run_id=159349, tier1_verified_at=
    2026-08-25T16:10 UTC) and STILL carries matched_divergent post-refresh --
    i.e. the automated pipeline itself, running today, did not reclassify it
    clean.
  - CA24-1264 and CA25-1792 carry parity_source=NULL entirely (never tier1-
    labeled), so even if flipped to matched_clean they would not satisfy the
    evaluator's "parity_source LIKE 'tier1%%'" requirement without a further,
    separately-evidenced parity_source backfill this session has no new
    evidence for.

Per this dispatch's explicit instruction ("do not force a match if the
divergence is real"), none of the 3 foreclosure rows are touched.

CONCLUSION: C stays below 105/110 as a correct, evidence-backed data state.
No further lever exists this session without either (a) new upstream tax-
deed rows landing that are genuine clean matches, or (b) a fresh, specific
diagnosis of what field the tier1 pipeline considers CA25-1742 divergent on
(outside a single-county dispatch's scope -- would need to inspect the
automated tier1 cron's comparison logic, not available as a standalone
script in this repo).

Usage:
  python3 scripts/gold_standard_stjohns_c_phantom_tax_deed_reclassify.py
  (re-runs the live TaxSmart cross-check, applies the CLERK_SSOT_CANCELLED
   correction to the 3 PHANTOM rows, prints before/after RPC eval)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import date, timedelta, datetime, timezone

import httpx

COUNTY = "st_johns"
SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE_URL = "https://apps.stjohnsclerk.com/TaxSmart"
GRID_URL = "https://apps.stjohnsclerk.com/TaxSmart/Home/GridSearchData"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# All non-"SALE" TaxSmart status buckets -- SALE (2) is the live-upcoming
# window already covered by scripts/clerk_ssot/parsers/st_johns.py.
RESOLVED_STATUSES = {
    "8": "BANKRUPTCY", "14": "CANCELLED", "17": "CANCELLED/SCO",
    "7": "ESCHEATED", "5": "LANDS_AVAILABLE", "11": "NO_BID",
    "4": "REDEEMED", "3": "SOLD",
}
CANCEL_LIKE = {"BANKRUPTCY", "CANCELLED", "CANCELLED/SCO", "REDEEMED"}

TARGET_CASES = ["TD26-0024", "TD26-0038", "TD26-0034", "TD26-0031"]


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def mmddyyyy(d):
    return f"{d.month}/{d.day}/{d.year}"


def fetch_resolved_statuses():
    """Query every non-SALE TaxSmart status bucket over a 90-day window
    bracketing today; return {case_number: {"status":..., "cell":...}}."""
    today = date.today()
    found = {}
    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as client:
        for val, name in RESOLVED_STATUSES.items():
            client.get(BASE_URL)
            client.post(BASE_URL, data={
                "SearchTypeStatus": val,
                "dateFromStatus": mmddyyyy(today - timedelta(days=60)),
                "dateToStatus": mmddyyyy(today + timedelta(days=30)),
                "buttonSubmitStatus": "Search for Status",
            })
            resp = client.get(GRID_URL, params={
                "SearchType": "Status", "rows": 500, "page": 1,
                "sidx": "SaleDate", "sord": "asc", "_search": "false", "nd": 1,
            })
            resp.raise_for_status()
            payload = resp.json()
            for row in payload.get("rows", []):
                cell = row.get("cell") or []
                if len(cell) < 6:
                    continue
                cn = cell[1]
                if cn in TARGET_CASES:
                    found[cn] = {"status": name, "parcel_id": cell[3], "cert": cell[2]}
    return found


def main():
    log("=== st_johns C parity investigation (PHANTOM tax_deed rows) ===")
    before = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BEFORE C: {before['C']}", "VERIFIED")
    log(f"BEFORE D: {before['D']}", "VERIFIED")

    db_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&case_number=in.({','.join(TARGET_CASES)})"
        "&select=case_number,parcel_id,auction_status,parity_status,parity_source")
    db_by_case = {r["case_number"]: r for r in db_rows}
    log(f"DB rows for {TARGET_CASES}: {json.dumps(db_by_case, indent=2)}", "VERIFIED")

    live = fetch_resolved_statuses()
    log(f"Live TaxSmart resolved-status cross-check: {json.dumps(live, indent=2)}", "VERIFIED")

    missing = [cn for cn in TARGET_CASES if cn not in live]
    if missing:
        log(f"BLOCKED: {missing} not found in ANY live TaxSmart status bucket "
            "-- genuine PHANTOM, cannot fix. Not touching.", "VERIFIED")

    updated = []
    for cn in TARGET_CASES:
        db_row = db_by_case.get(cn)
        live_row = live.get(cn)
        if not db_row or not live_row:
            continue
        # parcel_id sanity check: normalize by stripping non-digits.
        db_parcel = "".join(ch for ch in (db_row.get("parcel_id") or "") if ch.isdigit())
        live_parcel = "".join(ch for ch in live_row["parcel_id"] if ch.isdigit())
        if db_parcel != live_parcel:
            log(f"SKIP {cn}: parcel_id mismatch db={db_parcel} live={live_parcel} "
                "-- would need manual review, not auto-corrected.", "VERIFIED")
            continue
        if live_row["status"] not in CANCEL_LIKE:
            log(f"SKIP {cn}: live status {live_row['status']} is not cancel-like "
                "-- unexpected, needs manual review.", "VERIFIED")
            continue
        if db_row["parity_status"] == "CLERK_SSOT_CANCELLED":
            log(f"SKIP {cn}: already CLERK_SSOT_CANCELLED -- reconfirmed live "
                f"({live_row['status']}), no write needed.", "VERIFIED")
            continue
        # PHANTOM_NOT_ON_CLERK -> CLERK_SSOT_CANCELLED (accuracy fix; D-pool
        # only, does NOT move C -- see docstring).
        body = {
            "auction_status": "CANCELLED",
            "parity_status": "CLERK_SSOT_CANCELLED",
            "parity_source": "st_johns_clerk_tax_deed_resolved_status_sweep",
        }
        result = rest_patch(
            f"multi_county_auctions?county=eq.{COUNTY}&case_number=eq.{cn}", body)
        if len(result) != 1:
            raise RuntimeError(f"FAIL-LOUD: expected 1 row updated for {cn}, got {len(result)}")
        updated.append(cn)
        log(f"UPDATED {cn}: PHANTOM_NOT_ON_CLERK -> CLERK_SSOT_CANCELLED "
            f"(live status={live_row['status']})", "VERIFIED")

    log(f"Total rows updated: {len(updated)} -> {updated}", "VERIFIED")
    log("None of these updates move letter C (matched_clean) -- REDEEMED/"
        "CANCELLED are matched_any-only per pencil_dod_evaluate_county's own "
        "FILTER clause. See docstring for full C-blocked reasoning.", "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER C: {after['C']}", "VERIFIED")
    log(f"AFTER D: {after['D']}", "VERIFIED")

    print("\n### BEFORE/AFTER")
    print(json.dumps({"before": {k: before[k] for k in ("C", "D")},
                       "after": {k: after[k] for k in ("C", "D")}}, indent=2))


if __name__ == "__main__":
    main()
