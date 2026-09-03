#!/usr/bin/env python3
"""GOLD STANDARD shard-4 (issue #19809), washington I/J follow-up: real
address+assessed_value backfill for the 31 rows left over after
scripts/gold_standard_shard4_19809_washington_cdij_backfill.py's phase 1/2 ran
(those rows already had parity_status set by phase 1 but were missing base
card fields entirely -- the original parity-promote step only writes
parity_status/parity_source, it assumes address/value already exist, which
was true for the 6 prior batches but not this one).

VERIFIED live this session: washington.realtaxdeed.com's 2026-07-21 AJAX
calendar (harvest_date()) DOES carry real property_address + assessed_value
for these case_numbers (confirmed by direct harvest_date() call). This script
writes ONLY the real harvested values -- no fabrication.

HONEST RESIDUAL (documented, not fixed): 17 of the 31 target case_numbers
have NO match on the live 2026-07-21 calendar (harvest returned 15 items,
matching only 14 of these 31 by case_number) -- these are either delisted,
continued to another date not yet re-surfaced, or a case_number formatting
mismatch. Left untouched rather than guessed. Additionally, NONE of these
rows get latitude/longitude from this fix -- the harvested addresses are
street-only (no house number, typical for vacant tax-deed lots) and the US
Census geocoder (tested live) returns zero matches for street-only
addresses; Washington County's property-appraiser GIS did not resolve to a
working endpoint in this session's time budget. Fabricating a city-centroid
lat/lon would be ghost-success and is explicitly banned by campaign policy --
left honestly blank. This means I stays capped below 95% until a real
parcel-level geocode source is found for washington (future session).

Usage: python3 scripts/gold_standard_shard4_19809_washington_i_value_backfill.py
"""
import importlib.util
import json
import os
import urllib.request
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("h", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_harvester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_harvester)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Content-Type": "application/json"}
COUNTY = "washington"
AUCTION_DATE = "2026-07-21"


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    gap_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&select=case_number,property_address,assessed_value,market_value"
        "&assessed_value=is.null&market_value=is.null")
    print(f"target rows (no assessed/market value): {len(gap_rows)}")

    items = _harvester.harvest_date(COUNTY, COUNTY, "07/21/2026", platform_domain="realtaxdeed.com")
    by_case = {it["case_number"]: it for it in items if it.get("case_number")}
    print(f"live calendar items for {AUCTION_DATE}: {len(items)}")

    now = datetime.now(timezone.utc).isoformat()
    updated, no_match = 0, []
    for r in gap_rows:
        it = by_case.get(r["case_number"])
        if not it or not it.get("assessed_value") or not it.get("property_address"):
            no_match.append(r["case_number"])
            continue
        body = {"property_address": it["property_address"], "assessed_value": it["assessed_value"], "updated_at": now}
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?case_number=eq.{r['case_number']}&county=eq.{COUNTY}",
            data=json.dumps(body).encode(), method="PATCH", headers={**HEADERS, "Prefer": "return=minimal"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"PATCH failed {r['case_number']}: HTTP {resp.status}")
        updated += 1

    print(f"updated={updated} no_calendar_match={len(no_match)}: {sorted(no_match)}")
    print(json.dumps({"updated": updated, "no_calendar_match_case_numbers": sorted(no_match)}))


if __name__ == "__main__":
    main()
