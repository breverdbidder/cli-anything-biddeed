#!/usr/bin/env python3
"""SHARD-8 charlotte C/D litmus wiring run (2026-07-10).

Executes the harvest_date_paginated() + exact_match_and_promote() helpers that
scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py defined but never
actually invoked for charlotte (that file's __main__ only prints its own docstring).
86 of 103 charlotte multi_county_auctions rows have parity_status IS NULL --
VERIFIED this session those rows have never been through ANY litmus matcher, not
just a stale one. This script runs the RealAuction AJAX harvest against
charlotte.realforeclose.com for every foreclosure auction_date currently NULL in
our frozen calendar, then exact-case-number-matches against multi_county_auctions
and promotes to parity_status='matched_clean' with parity_source='realauction_ajax_harvest'.

Charlotte has NO taxdeed_platform configured in pipeline.counties (verified null) --
tax_deed rows (31, all NULL) are OUT OF SCOPE for this script; they need a tax-deed
lane that does not exist yet (see residual gap in session report).

Usage: python3 scripts/shard8_charlotte_litmus_run.py
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


harvester = _load("shard2_harvest", "shard2_run2450_ajax_realforeclose_harvest.py")
fixmod = _load("shard8_fix", "shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY_SLUG = "charlotte"
SUBDOMAIN = "charlotte"
PLATFORM_DOMAIN = "realforeclose.com"


def rest_get(path):
    import urllib.request
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    null_rows = rest_get(
        "multi_county_auctions?county=eq.charlotte&sale_type=eq.foreclosure"
        "&parity_status=is.null&select=id,auction_date,case_number"
        "&or=(data_source.neq.propertyonion,data_source.is.null)")
    dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")})
    print(f"[{datetime.utcnow().isoformat()}] charlotte foreclosure NULL-parity dates: {dates}")
    print(f"Total NULL foreclosure rows targeted: {len(null_rows)}")

    all_promoted = []
    for d in dates:
        mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
        items = fixmod.harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, PLATFORM_DOMAIN)
        print(f"  {d} ({mmddyyyy}): harvested {len(items)} live AITEM records from charlotte.realforeclose.com")
        if items:
            promoted = fixmod.exact_match_and_promote(
                COUNTY_SLUG, "charlotte", items, "realauction_ajax_harvest_shard8_run3563")
            print(f"    promoted {len(promoted)} rows to matched_clean: {promoted}")
            all_promoted.extend(promoted)
        time.sleep(0.5)

    print(f"TOTAL promoted this run: {len(all_promoted)}")
    print(json.dumps({"dates_checked": dates, "null_rows_targeted": len(null_rows),
                       "total_promoted": len(all_promoted), "promoted_ids": all_promoted}))


if __name__ == "__main__":
    main()
