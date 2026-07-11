#!/usr/bin/env python3
"""Escambia C/D tax-deed lane fix, dispatch (2026-07-11 gold-standard fixer session).

Root cause (VERIFIED this session via live pencil_dod_evaluate_county + direct DB query):
  331 in-scope escambia rows. 255 matched_clean, all on the FORECLOSURE lane
  (parity_source in tier1_realforeclose_aids_escambia / tier1_realforeclose_escambia /
  tier1_foreclosure_outcome). The remaining 76 rows are ALL sale_type='tax_deed',
  parity_status IS NULL, auction_date spanning 2026-08-05..2026-12-02 (5 distinct future
  dates: 08/05, 09/02, 10/07, 11/04, 12/02). No tier1 matcher has ever run against
  escambia.realtaxdeed.com (tax deed lane) -- only the realforeclose (foreclosure) lane
  has one wired (tier1_realforeclose_aids_escambia, 221 tax_deed rows already matched via
  a DIFFERENT batch -- see note below).

  NOTE: 221 escambia tax_deed rows are ALREADY matched_clean under parity_source=
  'tier1_realforeclose_aids_escambia' -- this label is misleading (a realFORECLOSE label
  reused for tax deed rows) but those 221 rows are NOT in scope here; they already pass.
  Only the 76 NULL rows are the target of this fix.

  Probed escambia.realtaxdeed.com live via the shared harvest_date_paginated() helper
  (AJAX PREVIEW/UPDATE mechanism, same as realforeclose -- confirmed realtaxdeed.com uses
  the identical RealAuction platform markup) for all 5 target dates BEFORE writing this
  script: got 60-61 live AITEM records per date, all with real case_number/parcel_id/
  auction_type=TAXDEED/property_address/assessed_value populated. The calendar for these
  far-future Nov/Dec 2026 dates IS populated -- not a structural dead-end.

Fix: run harvest_date_paginated() (platform_domain='realtaxdeed.com') + a case_number-only
exact_match_and_promote() variant (this file's own promote_matches, NOT the shared one --
the shared one filters mca_county_filter without a sale_type guard; here we deliberately
scope the match to sale_type='tax_deed' rows only, since escambia has both lanes and we
don't want to accidentally touch foreclosure rows) against escambia.realtaxdeed.com for
the 5 target dates. Only promotes rows whose normalized case_number is present in the live
AJAX response for that exact auction_date -- no fuzzy/parcel-only arm, no forced match.

Usage: python3 scripts/shard_escambia_cd_taxdeed_fix.py
Idempotent: harvest is read-only; promote only PATCHes rows not already matched_clean.
"""
import os
import re
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

COUNTY_SLUG = "escambia"
SUBDOMAIN = "escambia"
PLATFORM_DOMAIN = "realtaxdeed.com"
PARITY_SOURCE_LABEL = "tier1_realtaxdeed_escambia"


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
    """Exact normalize_case_number match ONLY, scoped to escambia tax_deed NULL rows."""
    by_norm = {}
    for it in items:
        cn = fixmod.norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        "multi_county_auctions?county=eq.escambia&sale_type=eq.tax_deed"
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
        "multi_county_auctions?county=eq.escambia&sale_type=eq.tax_deed"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")
    dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")})
    print(f"[{datetime.utcnow().isoformat()}] escambia tax_deed NULL dates: {dates}")
    print(f"NULL rows targeted: {len(null_rows)}  total distinct dates: {len(dates)}")

    all_promoted = []
    zero_harvest_dates = []
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, PLATFORM_DOMAIN)
        print(f"  {d} ({mmddyyyy}): harvested {len(items)} live AITEM records from "
              f"escambia.realtaxdeed.com")
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
    print(json.dumps({"dates_checked": dates, "null_rows_targeted": len(null_rows),
                       "total_promoted": len(all_promoted), "promoted_ids": all_promoted,
                       "zero_harvest_dates": zero_harvest_dates}))


if __name__ == "__main__":
    main()
