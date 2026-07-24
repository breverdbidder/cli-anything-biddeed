#!/usr/bin/env python3
"""GOLD STANDARD shard-8 (okeechobee), dispatch_id ac288257-fde4-4e26-a8d7-abb78447619f.

C/D parity backfill for 8 okeechobee rows added to multi_county_auctions after the
campaign brief's last snapshot (case_number 2026TD040/045/046/047/048/079/080/081,
sale_type='foreclosure', auction_date 2026-08-06 or 2026-09-24 -- confirmed live via
direct SQL: these 8 are the ONLY rows in okeechobee failing
`parity_status='matched_clean' AND parity_source LIKE 'tier1%'` out of 65 total rows).

Reuses scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date() verbatim
(same okeechobee.realforeclose.com AJAX mechanism already proven for these 8 case
numbers -- pre-run live 2026-07-24, harvested 12+3=15 AITEM rows into
realforeclose_aids, all 8 target case_numbers present with real parcel_id and, for
5 of 8, real assessed_value straight from the county's own auction platform).

exact_match_and_promote_scoped() below is copied verbatim from
scripts/shard_gs_clay_okeechobee_cd_parity.py (date-scoped match, avoids the
continuance-date mislabel defect documented in that file) -- reimplemented here
rather than dynamically imported because that module runs TARGETS = json.loads(...)
at import time (reads sys.argv / /tmp/targets.json), which breaks a clean import.

Usage: python3 scripts/shard8_okeechobee_cd_parity_new_dates.py
"""
import importlib.util
import json
import os
import re
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

TARGETS = [
    {"county": "okeechobee", "sale_type": "foreclosure", "auction_date": "2026-08-06"},
    {"county": "okeechobee", "sale_type": "foreclosure", "auction_date": "2026-09-24"},
]
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
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        items = _harvester.harvest_date(county, county, mmddyyyy, platform_domain=platform)
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            continue
        matched = exact_match_and_promote_scoped(
            county, ad, items, f"tier1:shard8_run_ac288257_ajax_harvest:{sale_type}:{ad}")
        total_promoted += len(matched)
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items -> {len(matched)} promoted")

    print(f"\nTOTAL PROMOTED: {total_promoted}")


if __name__ == "__main__":
    main()
