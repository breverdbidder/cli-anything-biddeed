#!/usr/bin/env python3
"""PINELLAS C/D 28-row parity gap closure, Gold Standard session 2026-08-28.

TARGET: pinellas C (matched_clean>=95%, need >=443/466), D (matched_any>=95%,
need >=443/466).
Baseline (VERIFIED live, session start, via pencil_dod_evaluate_county('pinellas')):
  C FAIL 93.8% (matched_clean=437/466)
  D FAIL 93.8% (matched_any=437/466)
28 gap rows, all parity_status IS NULL, all non-PropertyOnion (data_source
not propertyonion), exact case_numbers listed in TARGET_CASES below.

METHOD (independent live verification against pinellas.realforeclose.com,
identical platform/session mechanism already proven in
scripts/pinellas_cdij_parity_shard1_3ce988ac.py and
scripts/shard2_run2450_ajax_realforeclose_harvest.py -- reused, not
reimplemented):

  1. Unauthenticated AJAX harvest (harvest_date_paginated, imported from
     scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py) against
     the live PREVIEW/UPDATE calendar for every distinct auction_date among
     the 28 targets (08/18, 08/20, 08/25, 08/26, 08/27, 09/02/2026). All 28
     target case_numbers were found on this calendar for their exact
     auction_date (confirms every row corresponds to a real, current
     RealAuction listing) -- but this endpoint carries no status/outcome
     field, so it alone cannot establish sold vs canceled vs still-scheduled.

  2. Authenticated Auction Results Report (report_id=18, via
     pinellas_cdij_parity_shard1_3ce988ac.login_and_drain_notices +
     fetch_results_report_rows) -- the Clerk's own authoritative outcome
     grid, independent of our pre-sale calendar-sweep scraper. 12 of the 28
     targets appear here with auction_status='Sold' and a real winning_bid
     cell -> matched_clean, sold_amount backfilled/reconciled from the
     report's own figure.

  3. Authenticated live DAYLIST page (per-auction-date, via
     pinellas_cdij_parity_shard1_3ce988ac.pw_login_and_drain_notices +
     fetch_daylist_page / parse_daylist_for_case) for the remaining 16 not
     in the Results Report:
       - 8 confirmed "Auction Starts" (still scheduled, upcoming) ->
         matched_clean (real, currently-scheduled listing; no fabricated
         sold status).
       - 8 confirmed "Auction Status: Canceled per County/Order" (live,
         independent confirmation of the cancellation our DB already
         carried in auction_status) -> CLERK_SSOT_CANCELLED per this repo's
         canon: counts toward D (matched_any), deliberately excluded from C
         (matched_clean). NOTE: case 522024CA002012XXCICI was carried in our
         DB as auction_status='upcoming' (09/02/2026) but the live DAYLIST
         shows it is actually now Canceled per County -- this script also
         corrects auction_status for that one row to canceled_per_county
         since the platform's own live status supersedes our stale sweep.

  HONESTY GUARD: every one of the 28 targets was independently located on
  the live platform (0 not_found this run). If any target had NOT been
  located, it would be left with parity_status untouched and reported as a
  genuine residual -- no fabrication.

Writes on multi_county_auctions (only for the 28 targets, only where
parity_status IS NULL -- re-verified immediately before each PATCH so a
re-run of this script is a no-op):
  sold (12 rows):
    parity_status='matched_clean'
    parity_source='tier1_realforeclose_results_report:pinellas:20260828_cd28gap'
    sold_amount (from Results Report winning_bid, only if DB value was NULL
      -- for the 3 rows where auction_status was already 'completed' with no
      sold_amount on file, this backfills it from the same authoritative
      report row)
    auction_status='sold' (only if not already a sold/completed variant)
  upcoming (8 rows):
    parity_status='matched_clean'
    parity_source='tier1_realforeclose_daylist:pinellas:20260828_cd28gap'
    (no status/amount fabricated -- still scheduled per the live calendar)
  canceled (8 rows):
    parity_status='CLERK_SSOT_CANCELLED'
    parity_source='tier1_realforeclose_daylist:pinellas:20260828_cd28gap'
    auction_status corrected to canceled_per_county for 522024CA002012XXCICI
      only (the one row whose DB status was stale/wrong per live DAYLIST)

Usage:
  python3 scripts/gold_standard_pinellas_cd_28gap_20260828.py --dry-run
  python3 scripts/gold_standard_pinellas_cd_28gap_20260828.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


shard8 = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")
pcdij = _load("pinellas_cdij", "pinellas_cdij_parity_shard1_3ce988ac.py")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

RESULTS_SOURCE = "tier1_realforeclose_results_report:pinellas:20260828_cd28gap"
DAYLIST_SOURCE = "tier1_realforeclose_daylist:pinellas:20260828_cd28gap"

# 28 parity_status IS NULL case_numbers, VERIFIED live at session start
# against multi_county_auctions (dispatch = this session).
TARGET_CASES = [
    "522025CA004305XXCICI", "522024CA003659XXCICI", "522025CA005870XXCICI",
    "522025CA004880XXCICI", "522025CA001620XXCICI", "522025CA001347XXCICI",
    "522025CA006354XXCICI", "522025CA006903XXCICI", "522024CA002012XXCICI",
    "522025CA004087XXCICI", "522025CA005826XXCICI", "522026CA001582XXCICI",
    "522026CA001378XXCICI", "522026CA000826XXCICI", "522025CA005219XXCICI",
    "522018CA002258XXCICI", "522025CA004597XXCICI", "522025CA000980XXCICI",
    "522025CA000490XXCICI", "522026CC000372XXCOCO", "522026CA000403XXCICI",
    "522025CA005628XXCICI", "522025CA005825XXCICI", "522026CC001205XXCOCO",
    "522025CC011379XXCOCO", "522026CC001238XXCOCO", "522026CA001066XXCICI",
    "522026CA001318XXCICI",
]

# Distinct auction dates among the 28 targets (MM/DD/YYYY, unauth PREVIEW
# calendar harvest only used to confirm calendar presence, not outcome).
HARVEST_DATES = ["08/18/2026", "08/20/2026", "08/25/2026", "08/26/2026",
                  "08/27/2026", "09/02/2026"]


def norm(cn: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}",
                                  headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, level="INFO", tag="VERIFIED"):
    print(f"[{ts()}] {level} [{tag}]: {msg}", flush=True)


def main():
    log("=== PINELLAS C/D 28-ROW PARITY GAP CLOSURE (session 2026-08-28) ===")
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    for letter in ("C", "D"):
        log(f"BASELINE {letter}: {baseline[letter]}")

    cn_list = ",".join(TARGET_CASES)
    rows = rest_get(
        f"multi_county_auctions?county=eq.pinellas&case_number=in.({cn_list})"
        f"&select=id,case_number,parity_status,sold_amount,auction_status,data_source")
    by_case = {r["case_number"]: r for r in rows}
    missing = [c for c in TARGET_CASES if c not in by_case]
    if missing:
        log(f"FAIL-LOUD: {len(missing)} targets not found in DB: {missing}", "ERROR")

    # Step 1: unauth calendar harvest -- confirms live presence, not outcome.
    calendar_hits = {}
    for d in HARVEST_DATES:
        items = shard8.harvest_date_paginated("pinellas", "pinellas", d, "realforeclose.com")
        log(f"calendar harvest {d}: {len(items)} items")
        for it in items:
            cn = norm(it.get("case_number"))
            if cn:
                calendar_hits[cn] = d
    not_on_calendar = [c for c in TARGET_CASES if norm(c) not in calendar_hits]
    if not_on_calendar:
        log(f"FAIL-LOUD: {len(not_on_calendar)} targets not found on any live "
            f"calendar date checked: {not_on_calendar}", "ERROR")

    # Step 2: authenticated Results Report -- authoritative sold outcomes.
    opener = pcdij.build_opener()
    pcdij.login_and_drain_notices(opener)
    raw_results = pcdij.fetch_results_report_rows(opener)
    if not raw_results:
        log("FAIL-LOUD: Auction Results Report returned 0 rows -- cannot treat "
            "as a clean signal", "ERROR")
        sys.exit(2)
    by_case_results = pcdij.parse_results_rows(raw_results)
    log(f"Results Report: {len(by_case_results)} unique case_numbers parsed")

    sold_targets = {}
    remaining = []
    for cn in TARGET_CASES:
        rr = by_case_results.get(norm(cn))
        if rr and (rr.get("auction_status") or "").strip().lower() == "sold" and rr.get("winning_bid_f") is not None:
            sold_targets[cn] = rr
        else:
            remaining.append(cn)
    log(f"Sold via Results Report: {len(sold_targets)} of {len(TARGET_CASES)}")

    # Step 3: authenticated live DAYLIST for the remainder.
    daylist_outcomes = {}
    if remaining:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=pcdij.UA)
            pcdij.pw_login_and_drain_notices(page)
            cache = {}
            date_rows = rest_get(
                f"multi_county_auctions?county=eq.pinellas&case_number=in.({','.join(remaining)})"
                f"&select=case_number,auction_date")
            date_by_cn = {r["case_number"]: r["auction_date"] for r in date_rows}
            for cn in remaining:
                ad = date_by_cn.get(cn)
                if not ad:
                    daylist_outcomes[cn] = (None, "no_auction_date_on_file", None)
                    continue
                y, m, d = ad.split("-")
                mmddyyyy = f"{m}/{d}/{y}"
                if mmddyyyy not in cache:
                    cache[mmddyyyy] = pcdij.fetch_daylist_page(page, mmddyyyy)
                kind, status_text, address = pcdij.parse_daylist_for_case(cache[mmddyyyy], cn)
                daylist_outcomes[cn] = (kind, status_text, address)
                log(f"DAYLIST {cn} ({mmddyyyy}): {kind} / {status_text}")
            browser.close()

    not_found = [cn for cn, (kind, *_r) in daylist_outcomes.items() if kind is None]
    if not_found:
        log(f"FAIL-LOUD: {len(not_found)} targets could not be independently "
            f"verified on live RealAuction: {not_found}", "ERROR")

    if DRY_RUN:
        print("\n### DRY-RUN -- no writes")
        print("sold_targets:", json.dumps({k: v for k, v in sold_targets.items()}, default=str, indent=2))
        print("daylist_outcomes:", json.dumps(daylist_outcomes, default=str, indent=2))
        return

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    patched_clean = 0
    patched_cancelled = 0
    status_corrected = 0

    for cn, rr in sold_targets.items():
        db_row = by_case.get(cn)
        if not db_row or db_row["parity_status"] is not None:
            continue  # idempotent guard: never overwrite existing classification
        payload = {
            "parity_status": "matched_clean",
            "parity_source": RESULTS_SOURCE,
        }
        if db_row.get("sold_amount") is None and rr.get("winning_bid_f") is not None:
            payload["sold_amount"] = rr["winning_bid_f"]
        if db_row.get("auction_status") not in ("sold", "completed"):
            payload["auction_status"] = "sold"
        resp = rest_patch(f"multi_county_auctions?id=eq.{db_row['id']}&parity_status=is.null", payload)
        if resp:
            patched_clean += 1
        else:
            log(f"FAIL-LOUD: PATCH for {cn} (sold) returned 0 rows -- parity_status "
                f"was likely no longer NULL at write time", "ERROR")

    for cn, (kind, status_text, address) in daylist_outcomes.items():
        db_row = by_case.get(cn)
        if not db_row or db_row["parity_status"] is not None:
            continue
        if kind == "upcoming":
            payload = {"parity_status": "matched_clean", "parity_source": DAYLIST_SOURCE}
            resp = rest_patch(f"multi_county_auctions?id=eq.{db_row['id']}&parity_status=is.null", payload)
            if resp:
                patched_clean += 1
            else:
                log(f"FAIL-LOUD: PATCH for {cn} (upcoming) returned 0 rows", "ERROR")
        elif kind == "canceled":
            payload = {"parity_status": "CLERK_SSOT_CANCELLED", "parity_source": DAYLIST_SOURCE}
            if db_row.get("auction_status") not in (
                    "canceled_per_county", "canceled_per_order", "canceled"):
                payload["auction_status"] = "canceled_per_county"
                status_corrected += 1
            resp = rest_patch(f"multi_county_auctions?id=eq.{db_row['id']}&parity_status=is.null", payload)
            if resp:
                patched_cancelled += 1
            else:
                log(f"FAIL-LOUD: PATCH for {cn} (canceled) returned 0 rows", "ERROR")
        else:
            continue  # not_found -- leave untouched, already logged above

    log(f"Patched matched_clean={patched_clean}, CLERK_SSOT_CANCELLED={patched_cancelled}, "
        f"auction_status corrections={status_corrected}")

    after = rpc("pencil_dod_evaluate_county", {"p_county": "pinellas"})
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("SELECT parity_status, count(*) FROM multi_county_auctions WHERE county='pinellas' "
          f"AND case_number IN ({','.join(repr(c) for c in TARGET_CASES)}) GROUP BY parity_status;")
    for letter in ("C", "D"):
        print(f"BEFORE {letter}: {baseline[letter]}")
        print(f"AFTER  {letter}: {after[letter]}")


if __name__ == "__main__":
    main()
