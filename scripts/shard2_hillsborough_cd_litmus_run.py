#!/usr/bin/env python3
"""SHARD-2 hillsborough C/D litmus wiring run (2026-07-10), dispatch
11df373c-d3d3-4778-b489-2c32d7af5545.

Same root cause as the charlotte shard8 fix (commit 45c8ac59,
scripts/shard8_charlotte_litmus_run.py): 174 of 916 hillsborough
multi_county_auctions rows have parity_status IS NULL and have NEVER been run
through any litmus matcher -- this is a wiring gap, not a coverage gap.

Split (VERIFIED live query this session):
  - foreclosure: 114 rows (89 data_source IS NULL/tier1_authoritative=true,
    22 data_source='realforeclose', 3 data_source IS NULL/tier1_authoritative=false*)
  - tax_deed: 60 rows (59 data_source='realtaxdeed', 1 data_source IS NULL/tier1=true)
  (*count drifted slightly between diagnosis and this run's live re-query --
  data changes live, this script re-queries fresh rather than trusting the
  session-brief numbers.)

Platform verification done live this session (both endpoints return HTTP 200
via the shared fetch() helper, using its cookie-jar + desktop UA):
  - foreclosure -> https://hillsborough.realforeclose.com  (pipeline.counties
    foreclosure_platform='realforeclose' -- CONFIRMED correct)
  - tax_deed    -> https://hillsborough.realtaxdeed.com  (pipeline.counties
    taxdeed_platform column says 'realauction' but taxdeed_url is
    hillsborough.realtaxdeed.com -- CONFIRMED the .realtaxdeed.com domain is
    the one that actually serves the AJAX PREVIEW/UPDATE endpoints;
    hillsborough.realauction.com does not even resolve (DNS NXDOMAIN))

Usage: python3 scripts/shard2_hillsborough_cd_litmus_run.py
Idempotent: harvest upserts on `aid`; promote only PATCHes rows where
parity_status != 'matched_clean'.
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

COUNTY_SLUG = "hillsborough"
SUBDOMAIN = "hillsborough"

# sale_type -> platform_domain (VERIFIED live this session, see docstring)
PLATFORM_BY_SALE_TYPE = {
    "foreclosure": "realforeclose.com",
    "tax_deed": "realtaxdeed.com",
}

RUN_DATE = "20260710"


def rest_get(path):
    import urllib.request
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    all_promoted = []
    total_null_targeted = 0

    for sale_type, platform_domain in PLATFORM_BY_SALE_TYPE.items():
        null_rows = rest_get(
            f"multi_county_auctions?county=eq.{COUNTY_SLUG}&sale_type=eq.{sale_type}"
            "&parity_status=is.null&select=id,auction_date,case_number"
            "&or=(data_source.neq.propertyonion,data_source.is.null)")
        dates = sorted({r["auction_date"][:10] for r in null_rows if r.get("auction_date")})
        total_null_targeted += len(null_rows)
        print(f"[{datetime.utcnow().isoformat()}] hillsborough {sale_type} NULL-parity dates: {dates}")
        print(f"Total NULL {sale_type} rows targeted: {len(null_rows)}")

        parity_source_label = f"tier1_realauction_ajax_harvest_shard2_hillsborough_{RUN_DATE}_{sale_type}"

        for d in dates:
            mmddyyyy = datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
            try:
                items = fixmod.harvest_date_paginated(SUBDOMAIN, COUNTY_SLUG, mmddyyyy, platform_domain)
            except Exception as e:
                print(f"  {d} ({mmddyyyy}) [{sale_type}]: harvest FAILED: {e}")
                continue
            print(f"  {d} ({mmddyyyy}) [{sale_type}]: harvested {len(items)} live AITEM records "
                  f"from {SUBDOMAIN}.{platform_domain}")
            if items:
                promoted = fixmod.exact_match_and_promote(
                    COUNTY_SLUG, COUNTY_SLUG, items, parity_source_label)
                print(f"    promoted {len(promoted)} rows to matched_clean: {promoted}")
                if len(promoted) == 0:
                    print(f"    NOTE: parsed {len(items)}>0 live records but promoted 0 for {d} "
                          f"({sale_type}) -- no exact case_number match, not a silent failure.")
                all_promoted.extend(promoted)
            time.sleep(0.5)

    print(f"TOTAL NULL rows targeted (foreclosure+tax_deed): {total_null_targeted}")
    print(f"TOTAL promoted this run: {len(all_promoted)}")
    print(json.dumps({"null_rows_targeted": total_null_targeted,
                       "total_promoted": len(all_promoted), "promoted_ids": all_promoted}))


if __name__ == "__main__":
    main()
