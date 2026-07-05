#!/usr/bin/env python3
"""SHARD-6 (2nd dispatch), run3025 -- jackson C/D parity backfill.

BEFORE baseline (confirmed live via pencil_dod_evaluate_county this session):
  C metric=3.2 (matched_clean=2 of 63), D metric=3.2 (matched_any=2 of 63)

Root cause (confirmed live via direct query this session): jackson has 61 of 63
non-PO auction rows with parity_status either NULL or not matched_clean -- 8 remaining
'realforeclose' foreclosure rows across 9 auction dates, plus 53 'calendar_sweep_mca_v3'
tax_deed rows across 3 auction dates. Zero rows have data_source containing
'propertyonion' or a case_number starting 'PO-' for this county -- there is nothing to
exclude on that basis, but the exclusion filter is still applied verbatim per canon.

Fix: EXACT SAME proven pattern as scripts/shard9_run3059_citrus_manatee_cd_parity.py --
reuse harvest_date() from scripts/shard2_run2450_ajax_realforeclose_harvest.py (live
RealAuction AJAX calendar fetch, no PropertyOnion, no Firecrawl dependency) and
exact_match_and_promote() (normalize case numbers, PATCH parity_status='matched_clean'
only for exact matches). The only adaptation: harvest_date() takes subdomain and
county_slug as separate args upstream (e.g. indian_river's RealForeclose subdomain is
'indian-river' with a hyphen while the DB county slug has an underscore) -- for jackson
both happen to be 'jackson', but this script keeps them as separate fields per target
dict to stay consistent with the general pattern rather than hardcoding the coincidence.

Idempotent: only PATCHes rows where parity_status IS NULL or parity_source NOT LIKE
'tier1%%', so re-running is safe.

Usage: python3 scripts/shard6_run3025_2nd_dispatch_jackson_cd_parity.py
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
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-04-16"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-05-07"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-05-14"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-06-11"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-07-09"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-07-16"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-07-23"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-07-30"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "foreclosure", "auction_date": "2026-08-27"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "tax_deed", "auction_date": "2026-06-30"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "tax_deed", "auction_date": "2026-07-14"},
    {"county": "jackson", "subdomain": "jackson", "sale_type": "tax_deed", "auction_date": "2026-08-04"},
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
            county, items, f"tier1:shard6_run3025_2nd_dispatch_ajax_harvest:{sale_type}:{ad}")
        total_promoted += len(matched)
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items -> {len(matched)} promoted")
        time.sleep(0.4)

    print(f"\nTOTAL PROMOTED: {total_promoted}")


if __name__ == "__main__":
    main()
