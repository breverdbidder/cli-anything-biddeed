#!/usr/bin/env python3
"""GOLD STANDARD shard (clay/okeechobee/alachua/gadsden), dispatch_id
18aeb9b9-8281-4991-aa6c-f5e4422d0c6d, session architect-20260704T160000.

C/D parity backfill for clay (88 of 108 rows never matched against an independent
tier1 source) and okeechobee (8 remaining rows). Root cause (confirmed live
2026-07-05 via pencil_dod_evaluate_county + direct SQL against
multi_county_auctions): the bulk of clay's rows carry parity_status='mca_only'
with parity_source NULL or an old 'tier1_clerk_supp_shard5_run651' label that
covers only a 20-row subset -- an honest coverage gap, not a mislabel (confirmed
via `select parity_status, parity_source, count(*) ... group by 1,2` -- no
PropertyOnion-derived rows are being miscounted as tier1 here).

Reuses scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date()
verbatim (direct AJAX fetch against the RealAuction calendar itself -- clay and
okeechobee both run realforeclose.com/realtaxdeed.com per pipeline.counties,
confirmed live via `select * from pipeline.counties where county_slug in (...)`).

FIX APPLIED to the known defect in scripts/shard9_run3059_citrus_manatee_cd_parity.py
(flagged in that file's own docstring and in
supabase/migrations/20260705_shard11_run2820_..._cd_parity.sql's WASHINGTON
section): that script's exact_match_and_promote() matches a case_number against
ALL of a county's rows regardless of auction_date, so a continued/rescheduled
case can get its parity_source stamped with the WRONG calendar date. This
version scopes the mca_rows fetch to county AND auction_date, so the promoted
parity_source always reflects the row's own real auction_date.

okeechobee's taxdeed_platform is NULL in pipeline.counties (not realtaxdeed) --
the 2 remaining okeechobee tax_deed rows (2026TD031, 2026TD033) are instead
verified via scripts/shard9_okeechobee_taxsmartweb_litmus.py's
fetch_taxsmartweb_case() against the Okeechobee Clerk's own TaxSmartWebLive
system (already the county's proven TD-format litmus source).

Usage: python3 scripts/shard_gs_clay_okeechobee_cd_parity.py
"""
import os
import re
import sys
import json
import time
import importlib.util
import urllib.request
from datetime import datetime, timezone

_here = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_here, f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_harvester = _load("shard2_run2450_ajax_realforeclose_harvest")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

TARGETS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.load(open("/tmp/targets.json"))
PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}


def norm_case_number(cn):
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


def exact_match_and_promote_scoped(county, auction_date, items, parity_source_label):
    """Scoped to (county, auction_date) -- avoids the continuance-date mislabel defect."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}&auction_date=eq.{auction_date}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source")
    matches = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        already_tier1_this_date = (row.get("parity_source") or "").startswith("tier1") \
            and row["parity_status"] in ("matched_clean", "matched_divergent")
        if cn in by_norm and not already_tier1_this_date:
            matches.append(row["id"])
    if not matches:
        return []
    now = datetime.now(timezone.utc).isoformat()
    id_filter = ",".join(str(m) for m in matches)
    rest_patch(f"multi_county_auctions?id=in.({id_filter})",
               {"parity_status": "matched_clean", "parity_source": parity_source_label,
                "parity_checked_at": now, "updated_at": now})
    return matches


def main():
    total_promoted = 0
    per_county = {}
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _harvester.harvest_date(county, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {county} {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        matched = exact_match_and_promote_scoped(
            county, ad, items, f"tier1:shard_gs_20260705_ajax_harvest:{sale_type}:{ad}")
        total_promoted += len(matched)
        per_county[county] = per_county.get(county, 0) + len(matched)
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items -> {len(matched)} promoted")
        time.sleep(0.4)

    print(f"\nTOTAL PROMOTED: {total_promoted}")
    print(f"PER COUNTY: {per_county}")


if __name__ == "__main__":
    main()
