#!/usr/bin/env python3
"""SHARD-1 escambia C/D fix (2026-08-01, loop run 7858, dispatch 9757eae6).

Baseline from dispatch brief (VERIFIED via pencil_dod_evaluate_county):
  escambia C=D=88.5% (matched_clean=354 / auctions_total=400)

Prior session history:
  - shard14_run5361 (2026-07-20): promoted 270 rows C/D=79.4%
  - shard14 2nd firing (2026-07-20 +3.5h): promoted 274 rows C/D=80.6%
  - shard14_escambia_dispatch_a7bdb48f session report documents residual = 66 tax_deed rows
    genuinely unmatched by exact case_number (upstream divergence: our calendar-sweep
    source vs RealAuction TD certificate list for far-future dates)
  - Current brief shows 88.5% (354/400) which implies significant forward progress since then

This script re-probes all NULL-parity escambia rows against current live RealAuction
calendars. Key change since last run: foreclosure dates in Aug 2026 may now be posted;
existing tax_deed dates may have new listings as they approach. Dates probed dynamically
from the NULL-parity rows themselves (not hardcoded) to handle any new auction dates
that have been ingested since the last fix session.

Idempotent: only PATCHes rows with parity_status IS NULL (not already matched_clean).
Exact case_number match only (no fuzzy/parcel-only arm -- per 2026-07-02 sentinel guard).

Usage: python3 scripts/shard1_9757eae6_escambia_cd_fix.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import os
import re
import json
import time
import importlib.util
import urllib.request
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "escambia"
PARITY_SOURCE = "tier1_realauction_escambia_shard1_run7858_9757eae6"


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    # Fetch all NULL-parity non-PO escambia rows
    gap_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&parity_status=is.null&select=id,case_number,sale_type,auction_date&limit=300")
    print(f"[{datetime.utcnow().isoformat()}Z] escambia NULL-parity rows: {len(gap_rows)}")

    if not gap_rows:
        print("No gap rows — already fully matched or nothing to fix.")
        return

    # Separate by sale_type to probe correct platform
    fc_dates = sorted({r["auction_date"][:10] for r in gap_rows
                       if r.get("sale_type") == "foreclosure" and r.get("auction_date")})
    td_dates = sorted({r["auction_date"][:10] for r in gap_rows
                       if r.get("sale_type") == "tax_deed" and r.get("auction_date")})
    print(f"Foreclosure dates to probe: {fc_dates}")
    print(f"Tax deed dates to probe: {td_dates}")

    live_items = {}

    for d in fc_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        try:
            items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, mmddyyyy, "realforeclose.com")
            print(f"  realforeclose {d} ({mmddyyyy}): {len(items)} live items")
            for it in items:
                cn = norm_case_number(it.get("case_number"))
                if cn:
                    live_items[cn] = it
        except Exception as e:
            print(f"  realforeclose {d}: ERROR {e}")
        time.sleep(0.5)

    for d in td_dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        try:
            items = fixmod.harvest_date_paginated(COUNTY_SLUG, COUNTY_SLUG, mmddyyyy, "realtaxdeed.com")
            print(f"  realtaxdeed {d} ({mmddyyyy}): {len(items)} live items")
            for it in items:
                cn = norm_case_number(it.get("case_number"))
                if cn:
                    live_items[cn] = it
        except Exception as e:
            print(f"  realtaxdeed {d}: ERROR {e}")
        time.sleep(0.5)

    print(f"Total live items harvested: {len(live_items)}")

    # Match by normalized case_number
    matches = []
    for row in gap_rows:
        cn = norm_case_number(row.get("case_number"))
        if cn and cn in live_items:
            matches.append(row)

    print(f"Exact case_number matches: {len(matches)}")
    for m in matches:
        print(f"  {m['id']} {m['case_number']} {m.get('sale_type')} {m.get('auction_date')}")

    if matches:
        ids = ",".join(str(m["id"]) for m in matches)
        resp = rest_patch(
            f"multi_county_auctions?id=in.({ids})",
            {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE})
        print(f"Patched {len(resp)} rows to matched_clean")

    residual = len(gap_rows) - len(matches)
    print(f"Residual (genuinely unmatched, not forced): {residual}")
    print(json.dumps({
        "county": COUNTY_SLUG, "gap_rows": len(gap_rows),
        "live_items_harvested": len(live_items),
        "exact_matches": len(matches), "residual": residual,
        "parity_source": PARITY_SOURCE
    }))


if __name__ == "__main__":
    main()
