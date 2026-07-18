#!/usr/bin/env python3
"""Pasco C/D tax-deed lane fix (2026-07-18 gold-standard fixer session, pasco C/D
continuation of scripts/shard_pasco_cd_i_fix.py).

Root cause (VERIFIED this session via live pencil_dod_evaluate_county + direct DB query):
  245 in-scope pasco rows. Foreclosure lane already fixed this session (12 NULL rows
  re-harvested + promoted via shard_pasco_cd_i_fix.py, all exact case_number matches).
  The remaining gap is 31 rows, ALL sale_type='tax_deed', parity_status IS NULL,
  auction_date=2026-08-27 (single future date). 104 other tax_deed rows are already
  matched_clean under parity_source='tier1_realtaxdeed_pasco_soldstatus:2026-07-05'
  (that label's origin script was never committed to the repo, only its DB output
  persisted -- this fix uses a fresh dated label instead of reusing the old one).

  Probed pasco.realtaxdeed.com live (PREVIEW+AJAX UPDATE, same RealAuction platform
  markup as escambia.realtaxdeed.com / pasco.realforeclose.com) for 2026-08-27 BEFORE
  writing this script: got 21 live AITEM records with real case_number/parcel_id/
  assessed_value populated. Cross-checked 4 sample in-scope case numbers against the
  live set: 2 of 4 matched exactly. The calendar for this date IS populated -- not a
  structural dead-end -- but the live harvest (21 items) is smaller than our 31
  in-scope rows, so a full run is expected to promote a majority, not necessarily all
  31. Any rows left unmatched after a full max_pages=15 harvest are treated as
  genuinely accrual-blocked for this date (not yet listed live on realtaxdeed.com) and
  are left untouched -- no forced/blanket promotion.

Fix: run harvest_date_paginated() (platform_domain='realtaxdeed.com') + a
sale_type='tax_deed'-scoped exact_match_and_promote() variant (this file's own
promote_matches, mirroring scripts/shard_escambia_cd_taxdeed_fix.py's pattern) against
pasco.realtaxdeed.com for 2026-08-27. Only promotes rows whose normalized case_number
is present in the live AJAX response for that exact auction_date.

Usage: python3 scripts/shard_pasco_cd_taxdeed_fix.py
Idempotent: harvest is read-only; promote only PATCHes rows not already matched_clean.
"""
import os
import json
import time
import urllib.request
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
PLATFORM_DOMAIN = "realtaxdeed.com"
PARITY_SOURCE_LABEL = "tier1_realtaxdeed_pasco_run20260718"


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


def promote_matches(items):
    """Exact normalize_case_number match ONLY, scoped to pasco tax_deed NULL rows."""
    by_norm = {}
    for it in items:
        cn = fixmod.norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.tax_deed"
        "&parity_status=is.null"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,parity_status")
    matches = []
    for row in mca_rows:
        cn = fixmod.norm_case_number(row["case_number"])
        if cn in by_norm:
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": PARITY_SOURCE_LABEL})
    return matches


def main():
    null_rows = rest_get(
        "multi_county_auctions?county=eq.pasco&sale_type=eq.tax_deed"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")
    dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")})
    print(f"[{datetime.utcnow().isoformat()}] pasco tax_deed NULL dates: {dates}")
    print(f"NULL rows targeted: {len(null_rows)}  total distinct dates: {len(dates)}")

    all_promoted = []
    zero_harvest_dates = []
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, PLATFORM_DOMAIN)
        print(f"  {d} ({mmddyyyy}): harvested {len(items)} live AITEM records from "
              f"pasco.realtaxdeed.com")
        if items:
            promoted = promote_matches(items)
            print(f"    promoted {len(promoted)} rows to matched_clean: {promoted}")
            all_promoted.extend(promoted)
            if len(promoted) == 0:
                print(f"    WARNING: parsed {len(items)} live records but promoted 0 for {d} -- "
                      f"live auction exists but no case_number matched our rows for this date.")
        else:
            zero_harvest_dates.append(d)
        time.sleep(0.5)

    print(f"TOTAL promoted this run: {len(all_promoted)}")
    print(f"Dates with zero live harvest: {zero_harvest_dates}")
    unmatched = len(null_rows) - len(all_promoted)
    print(f"Rows remaining unmatched (genuinely accrual-blocked for now -- not yet "
          f"listed live on realtaxdeed.com for this date, left untouched): {unmatched}")
    print(json.dumps({"dates_checked": dates, "null_rows_targeted": len(null_rows),
                       "total_promoted": len(all_promoted), "promoted_ids": all_promoted,
                       "zero_harvest_dates": zero_harvest_dates,
                       "unmatched_remaining": unmatched}))


if __name__ == "__main__":
    main()
