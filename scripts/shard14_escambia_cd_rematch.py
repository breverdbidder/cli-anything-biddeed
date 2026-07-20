#!/usr/bin/env python3
"""SHARD-14 Escambia C/D re-matcher: re-probe realtaxdeed.com for updated future dates.

dispatch_id: a7bdb48f-8748-4a1c-8539-d996dcda9e73
session: 2026-07-20

CONTEXT:
  Prior session (run-3679, 2026-07-11) confirmed 73 escambia tax_deed rows had zero
  overlap with the live realtaxdeed.com calendar for the 5 future auction dates
  (Aug-Dec 2026). These cases were likely redeemed/rescheduled since our original
  calendar sweep captured them.

  However, since then (Jul 11 -> Jul 20):
  - Additional MCA rows may have been added by background scrapers (denominator grew)
  - The realtaxdeed.com calendar for Aug/Sep 2026 dates may have updated with
    new case numbers that now match our gap rows

  This script re-runs the proven AJAX harvest+exact-match pipeline against all
  current escambia tax_deed rows with parity_status IS NULL, for all their
  distinct auction_dates.

ALSO: probes escambia.realforeclose.com for any new foreclosure gap rows.

Usage: python3 scripts/shard14_escambia_cd_rematch.py
Idempotent: harvest is read-only; promote only PATCHes NULL rows.
"""
import os
import json
import re
import time
import urllib.request
import urllib.parse
import http.cookiejar
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
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

COUNTY_SLUG = "escambia"
SUBDOMAIN = "escambia"


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


def promote_matches_scoped(sale_type, items, parity_source_label):
    by_norm = {}
    for it in items:
        cn = fixmod.norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.{sale_type}"
        "&parity_status=is.null"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,parity_status")
    matches = []
    for row in mca_rows:
        cn = fixmod.norm_case_number(row["case_number"])
        if cn in by_norm:
            matches.append(str(row["id"]))
    if not matches:
        return []
    id_filter = ",".join(matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_source_label})
    return matches


def run_lane(sale_type, domain, parity_source_label):
    null_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.{sale_type}"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")

    dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")})

    print(f"\n=== {sale_type} lane ({domain}) ===")
    print(f"  Gap rows: {len(null_rows)} across {len(dates)} dates: {dates}")

    all_promoted = []
    zero_harvest_dates = []

    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        try:
            items = fixmod.harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, domain)
        except Exception as e:
            print(f"  {d}: HARVEST ERROR: {e}")
            time.sleep(0.5)
            continue

        print(f"  {d}: harvested {len(items)} live AITEM records from {SUBDOMAIN}.{domain}")
        if items:
            promoted = promote_matches_scoped(sale_type, items, parity_source_label)
            print(f"    promoted {len(promoted)} rows: {promoted}")
            all_promoted.extend(promoted)
            if len(promoted) == 0 and len(items) > 0:
                print(f"    NOTE: {len(items)} live records but 0 matched our gap rows — "
                      f"likely redeemed/rescheduled since our sweep")
        else:
            zero_harvest_dates.append(d)
            print(f"    0 items from live calendar (no auction scheduled for this date yet?)")
        time.sleep(0.6)

    return all_promoted, zero_harvest_dates, len(null_rows), dates


def main():
    print(f"[{datetime.utcnow().isoformat()}] SHARD-14 Escambia C/D re-matcher")
    print("Probing escambia.realtaxdeed.com + escambia.realforeclose.com for updated calendars")

    td_promoted, td_zero, td_gap, td_dates = run_lane(
        "tax_deed", "realtaxdeed.com",
        f"tier1_realtaxdeed_escambia_shard14_{datetime.utcnow().strftime('%Y%m%d')}")

    fc_promoted, fc_zero, fc_gap, fc_dates = run_lane(
        "foreclosure", "realforeclose.com",
        f"tier1_realforeclose_escambia_shard14_{datetime.utcnow().strftime('%Y%m%d')}")

    total_promoted = td_promoted + fc_promoted

    print(f"\n=== SUMMARY ===")
    print(f"Tax deed:    {len(td_promoted)} promoted from {td_gap} gap rows ({len(td_dates)} dates)")
    print(f"Foreclosure: {len(fc_promoted)} promoted from {fc_gap} gap rows ({len(fc_dates)} dates)")
    print(f"TOTAL promoted: {len(total_promoted)}")
    print(f"Zero-harvest dates: tax_deed={td_zero} foreclosure={fc_zero}")
    print(json.dumps({
        "session": "shard14_escambia_cd_rematch",
        "tax_deed_gap_rows": td_gap,
        "tax_deed_dates": td_dates,
        "tax_deed_promoted": len(td_promoted),
        "tax_deed_promoted_ids": td_promoted,
        "tax_deed_zero_harvest_dates": td_zero,
        "foreclosure_gap_rows": fc_gap,
        "foreclosure_dates": fc_dates,
        "foreclosure_promoted": len(fc_promoted),
        "foreclosure_promoted_ids": fc_promoted,
        "foreclosure_zero_harvest_dates": fc_zero,
        "total_promoted": len(total_promoted),
    }))


if __name__ == "__main__":
    main()
