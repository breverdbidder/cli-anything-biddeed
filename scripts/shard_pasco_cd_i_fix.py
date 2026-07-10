#!/usr/bin/env python3
"""SHARD pasco C/D + I fix, dispatch 11df373c-d3d3-4778-b489-2c32d7af5545 (2026-07-10).

Root cause (VERIFIED this session via live queries against multi_county_auctions):
  - 202 in-scope rows for pasco. 104 matched_clean (parity_source='tier1_realtaxdeed_
    pasco_soldstatus:2026-07-05'). Gap = 98 rows:
      * 10 rows: parity_status IS NULL -- never run through ANY matcher. All
        sale_type='foreclosure', auction_date 2026-07-07..2026-07-21 (recent/future
        dates). Same wiring-gap pattern seen in charlotte/hillsborough this session.
      * 88 rows: parity_status='mca_only' (data_source in {'realforeclose',
        'calendar_sweep_mca_v3'}) -- a prior matcher DID run and found no live
        counterpart. VERIFIED the auction_date span for these is 2026-03-09 through
        2026-07-15 (34 distinct dates) -- far wider than a ~14-day litmus lookback
        window. That is the actual root cause: prior matcher runs only ever checked
        recent dates and never re-harvested the older auction dates these rows sit on.
        Case-number format sampled (e.g. 51-2025-CA-003392-CAAX-WS) matches the
        standard norm_case_number() regex expectation -- no normalization bug found.

Fix: run harvest_date_paginated() + exact_match_and_promote() (imported from
scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py, NOT copy-pasted) against
pasco.realforeclose.com for the UNION of all NULL and mca_only foreclosure auction_dates
currently in scope. This re-harvests the full date range the mca_only rows actually span,
not just a recent window.

pasco.foreclosure_platform = realforeclose (VERIFIED via pipeline.counties). No tax_deed
gap rows exist (all 98 gap rows are sale_type='foreclosure'), so realtaxdeed.com is out of
scope for this fix.

Usage: python3 scripts/shard_pasco_cd_i_fix.py
Idempotent: harvest upserts on `aid`; promote only PATCHes rows not already matched_clean.
"""
import os
import sys
import time
import json
import importlib.util
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "pasco"
SUBDOMAIN = "pasco"
PLATFORM_DOMAIN = "realforeclose.com"
PARITY_SOURCE_LABEL = "tier1_realauction_ajax_harvest_pasco_run11df373c"


def rest_get(path):
    import urllib.request
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    # NULL rows (never matched)
    null_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.foreclosure"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")
    # mca_only rows (matcher ran, found nothing live at the time -- re-harvest their
    # actual full date span since prior runs likely only checked recent dates)
    mca_only_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.foreclosure"
        "&parity_status=eq.mca_only&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")

    dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")}
                   | {r["auction_date"][:10] for r in mca_only_rows if r.get("auction_date")})
    print(f"[{datetime.utcnow().isoformat()}] pasco foreclosure NULL+mca_only dates: {dates}")
    print(f"NULL rows targeted: {len(null_rows)}  mca_only rows targeted: {len(mca_only_rows)}"
          f"  total distinct dates: {len(dates)}")

    all_promoted = []
    zero_harvest_dates = []
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, PLATFORM_DOMAIN)
        print(f"  {d} ({mmddyyyy}): harvested {len(items)} live AITEM records from pasco.realforeclose.com")
        if items:
            promoted = fixmod.exact_match_and_promote(
                COUNTY_SLUG, "pasco", items, PARITY_SOURCE_LABEL)
            print(f"    promoted {len(promoted)} rows to matched_clean: {promoted}")
            all_promoted.extend(promoted)
            if len(promoted) == 0:
                print(f"    WARNING: parsed {len(items)} live records but promoted 0 for {d} -- "
                      f"live auction exists but no case_number matched our rows for this date.")
        else:
            zero_harvest_dates.append(d)
        time.sleep(0.5)

    print(f"TOTAL promoted this run: {len(all_promoted)}")
    print(f"Dates with zero live harvest (likely off calendar / no live auction found): {zero_harvest_dates}")
    print(json.dumps({"dates_checked": dates, "null_rows_targeted": len(null_rows),
                       "mca_only_rows_targeted": len(mca_only_rows),
                       "total_promoted": len(all_promoted), "promoted_ids": all_promoted,
                       "zero_harvest_dates": zero_harvest_dates}))


if __name__ == "__main__":
    main()
