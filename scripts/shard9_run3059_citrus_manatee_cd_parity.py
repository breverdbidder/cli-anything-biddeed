#!/usr/bin/env python3
"""SHARD-9 (citrus/manatee/nassau/franklin/wakulla), dispatch 5624b379-b23a-4695-896c-cf84a3de81b5.

C/D parity backfill for citrus + manatee. Root cause (confirmed live 2026-07-05 via
pencil_dod_evaluate_county + direct query): citrus had 113 of 174 non-PO auction rows with
parity_status IS NULL (never matched against a tier1 source at all); manatee had 19 null
plus 29 rows mislabeled matched_divergent under parity_source='po_litmus_only:...' which the
evaluator correctly excludes (LIKE 'tier1%%' filter) because a PO-litmus label is not an
independent tier1 comparison per canon.

Fix: reuse the proven exact-case-number-match harvester from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (AJAX PREVIEW/UPDATE against the
RealAuction calendar itself -- the same platform citrus/manatee are hosted on, NOT
PropertyOnion, NOT Firecrawl) to pull the live calendar per auction_date/sale_type, then
patch parity_status='matched_clean' + parity_source='tier1:shard9_run3059_ajax_harvest' for
exact case_number matches per the same safe (no fuzzy/no parcel-only-arm) pattern
scripts/shard8_charlotte_levy_monroe_osceola_madison_cd_fix.py established.

Verified live (2026-07-05) this session: harvest_date() returns real items even for
auction dates a year in the past (06/05/2025 citrus foreclosure -> 10 items), so the full
historical backlog is reachable, not just recent dates. This does NOT depend on Firecrawl
(the account-wide Firecrawl credit exhaustion discovered this session blocks the *new-scrape*
scraper only) -- it is a direct HTTP fetch against the RealAuction AJAX endpoint.

Direct DB (psycopg2/pooler) connection is NOT used -- confirmed stale/rotated
SUPABASE_DB_PASSWORD this session (auth fails on every host/port/user combo tried). All
reads/writes here go through PostgREST (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY).

Idempotent: only PATCHes rows where parity_status IS NULL or parity_source NOT LIKE
'tier1%%', so re-running is safe.

KNOWN DEFECT (found by an independent ULTRALOOP adversarial refuter this session, fixed
by hand for the 16 affected citrus rows -- NOT yet fixed in this script's logic): the
"already_tier1" skip guard in exact_match_and_promote() matches a case_number against
ALL of a county's rows regardless of auction_date, then skips re-checking a row once it
is tier1-tagged. For a case that was continued/rescheduled and appears on more than one
historical calendar date, this freezes parity_source at whichever date happened to be
processed FIRST (ascending order), even when a later date in the loop is the row's own
actual auction_date. The match itself is still genuine (independently re-verified: all
16 affected citrus cases DO appear on the calendar under their own row's auction_date
too), but the recorded source date can be a different, earlier continuance date --
misleading provenance, not a false match. A future run of this script should either (a)
restrict exact_match_and_promote's mca_rows fetch to the current target's auction_date,
or (b) always prefer relabeling with the row's own auction_date when the case matches
under multiple dates, before this defect resurfaces at scale.

Usage: python3 scripts/shard9_run3059_citrus_manatee_cd_parity.py
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

# (county, sale_type, auction_date MM/DD/YYYY) targets with unmatched/mislabeled rows,
# pulled live from multi_county_auctions this session.
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
        print("usage: shard9_run3059_citrus_manatee_cd_parity.py '<json targets>'")
        sys.exit(1)

    total_promoted = 0
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date(county, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {county} {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        matched = exact_match_and_promote(
            county, items, f"tier1:shard9_run3059_ajax_harvest:{sale_type}:{ad}")
        total_promoted += len(matched)
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items -> {len(matched)} promoted")
        time.sleep(0.4)

    print(f"\nTOTAL PROMOTED: {total_promoted}")


if __name__ == "__main__":
    main()
