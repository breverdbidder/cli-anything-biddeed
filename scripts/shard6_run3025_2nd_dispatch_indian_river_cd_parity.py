#!/usr/bin/env python3
"""SHARD-6 (2nd dispatch), indian_river C/D parity backfill.

C/D parity backfill for indian_river. Root cause (confirmed live 2026-07-05 via
pencil_dod_evaluate_county + direct query): indian_river had 77 total non-PO auction
rows with C (matched_clean=57 of 77, 74.0%) and D (matched_any=65 of 77, 84.4%) both
failing the DoD gate. 20 rows are parity_status IS NULL or not matched_clean, spread
across 16 auction dates from 2025-10-09 through 2026-07-09.

Fix: reuse the exact proven pattern from scripts/shard9_run3059_citrus_manatee_cd_parity.py
(itself built on scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date()) --
pull the live RealAuction AJAX calendar per auction_date/sale_type (no PropertyOnion, no
Firecrawl dependency), normalize case numbers (strip non-alnum, uppercase), and PATCH
multi_county_auctions rows to parity_status='matched_clean' ONLY for exact case_number
matches against rows where data_source is not PropertyOnion-derived.

Delta from shard9's script: indian_river's RealAuction subdomain ('indian-river', with a
hyphen) differs from the DB county slug ('indian_river', with an underscore), so this
script takes subdomain and county_slug as SEPARATE fields (shard9's citrus/manatee had
subdomain == county_slug so it didn't need this split).

Idempotent: only PATCHes rows where parity_status IS NULL or parity_source NOT LIKE
'tier1%%', so re-running is safe.

Usage: python3 scripts/shard6_run3025_2nd_dispatch_indian_river_cd_parity.py '<json targets>'
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

# (county, subdomain, sale_type, auction_date MM/DD/YYYY) targets with unmatched/mislabeled
# rows, pulled live from multi_county_auctions this session.
TARGETS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else None


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
    if not TARGETS:
        print("usage: shard6_run3025_2nd_dispatch_indian_river_cd_parity.py '<json targets>'")
        sys.exit(1)

    total_promoted = 0
    for t in TARGETS:
        county = t["county"]
        subdomain = t.get("subdomain", county)
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date(subdomain, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {county} ({subdomain}) {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"  {county} ({subdomain}) {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        matched = exact_match_and_promote(
            county, items, f"tier1:shard6_run3025_2nd_dispatch_ajax_harvest:{sale_type}:{ad}")
        total_promoted += len(matched)
        print(f"  {county} ({subdomain}) {sale_type} {ad}: {len(items)} calendar items -> {len(matched)} promoted")
        time.sleep(0.4)

    print(f"\nTOTAL PROMOTED: {total_promoted}")


if __name__ == "__main__":
    main()
