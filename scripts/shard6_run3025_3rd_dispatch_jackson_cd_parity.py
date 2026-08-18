#!/usr/bin/env python3
"""SHARD-6 (3rd dispatch), jackson C/D parity backfill -- final 4 rows.

BEFORE baseline (confirmed live via pencil_dod_evaluate_county this session):
  C metric=94.8 (matched_clean=73 of 77), D metric=94.8 (matched_any=73 of 77)

Confirmed failing rows (VERIFIED live query, parity_status IS NULL, all
data_source='calendar_sweep_mca_v3'):
  - 322025CA000190CAAXMX, foreclosure, auction_date 2026-11-19
  - 322025CA000243CAAXMX, foreclosure, auction_date 2026-08-27
  - 3505 OF 2019,          tax_deed,    auction_date 2026-08-25
  - 322025CA000220CAAXMX, foreclosure, auction_date 2026-08-20

Fix: EXACT SAME proven pattern as
scripts/shard6_run3025_2nd_dispatch_jackson_cd_parity.py -- reuse harvest_date()
from scripts/shard2_run2450_ajax_realforeclose_harvest.py (live RealAuction AJAX
calendar fetch, no PropertyOnion, no Firecrawl dependency) and
exact_match_and_promote() (normalize case numbers, PATCH parity_status=
'matched_clean' only for exact matches). jackson subdomain == county slug ==
'jackson' for both platforms (realforeclose.com for foreclosure,
realtaxdeed.com for tax_deed -- prior dispatch already used realtaxdeed.com
for jackson tax_deed rows and it worked, e.g. 2026-06-30/07-14/08-04/08-25
tax_deed rows all show parity_source starting tier1:shard6_run3025_2nd_dispatch).

2026-11-19 is intentionally NOT in TARGETS -- 93 days out from today
(2026-08-18), RealAuction/RealForeclose calendars for this county have never
been observed to publish that far ahead (all prior successful matches were
<=8 weeks out). If it doesn't harvest, that is an honest not-yet-published
ceiling, not a bug.

Idempotent: only PATCHes rows where parity_status IS NULL or parity_source NOT
LIKE 'tier1%%', so re-running is safe.

Usage: python3 scripts/shard6_run3025_3rd_dispatch_jackson_cd_parity.py
"""
import os
import sys
import json
import time
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

TARGETS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else [
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-08-20"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-08-27"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "tax_deed", "auction_date": "2026-08-25"},
]


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
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


def exact_match_and_promote(mca_county_filter, items, parity_source_label):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{mca_county_filter}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source")
    matches = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")
        if cn in by_norm and not (row["parity_status"] == "matched_clean" and already_tier1):
            matches.append(row["id"])
    if not matches:
        return []
    id_filter = ",".join(str(m) for m in matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_source_label})
    return matches


PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}


def main():
    total_promoted = 0
    for t in TARGETS:
        county = t["county"]
        subdomain = t["subdomain"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date(subdomain, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {county} {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        matched = exact_match_and_promote(
            county, items, f"tier1:shard6_run3025_3rd_dispatch_ajax_harvest:{sale_type}:{ad}")
        total_promoted += len(matched)
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items -> {len(matched)} promoted")
        time.sleep(0.4)

    print(f"\nTOTAL PROMOTED: {total_promoted}")


if __name__ == "__main__":
    main()
