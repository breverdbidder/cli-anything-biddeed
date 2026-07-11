#!/usr/bin/env python3
"""GOLD STANDARD shard10, dispatch 0a47f574-b17a-4d24-98c7-8ee032514f17, county=lee.

Forked verbatim (pattern) from scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py.
Targets the 47 lee foreclosure rows (14 auction dates, all sale_type=foreclosure --
tax_deed side already fully matched) still needing parity_status/parcel_id backfill
per pencil_dod_evaluate_county live diagnosis run3712 (E=248/273, C=250/273 matched_clean,
D=251/273 matched_any). Live RealAuction AJAX calendar harvest, exact case_number match,
opportunistic parcel_id/property_address/assessed_value backfill.

RESULT (executed live 2026-07-11, 13 date-groups, 47 target rows): 8 parcel_id backfilled
(all 2026-08-06), 1 parity_status/parity_source promoted (2026-03-12), 9 property_address/
assessed_value fields backfilled. E moved 248->256 of 273 (90.8%->93.8%, still FAIL, gate
95%). C/D unchanged in net terms -- the single parity promotion was a row already counted
matched_any from a prior session (no fresh gain). 12 of 13 dates parsed >0 calendar items
but matched 0 target case numbers: the 6 oldest dates (2026-03-05 .. 2026-05-28) return
today's *current* calendar contents for that AUCTIONDATE query param, which does not
reliably include long-past auction items once RealForeclose prunes/archives them -- these
target case numbers were not present in today's live pull despite the site returning other
items for the same date. Two rows (20-CA-005572, 25-CA-000992) were confirmed live to have
a real property_address but an unparseable parcel_id: RealForeclose renders the parcel
link's anchor text as literal "Property Appraiser" instead of the STRAP for these specific
AITEM blocks -- a genuine source-side limitation, not a bug in this harvester (the existing
is_real_parcel_id() guard correctly rejects it rather than fabricating a value from the
placeholder text). Remaining 17-row E gap and C/D gap require either (a) a parcel-appraiser
address lookup for the 4 rows that now carry a real property_address post-harvest, or (b)
re-harvesting the 6 stale dates closer to their original auction week (narrow window before
RealForeclose stops serving that AUCTIONDATE), or (c) an authenticated RealForeclose session
(REALFORECLOSE_EMAIL/PASSWORD available) which may expose archived results differently --
none attempted this session for time-budget reasons, documented here for the next session.
"""
import os
import sys
import json
import time
import importlib.util

_here = "/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/scripts"
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

TARGETS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else None
PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    import re
    if not pid:
        return False
    return bool(re.search(r"\d", pid)) and pid.strip().lower() != "property appraiser"


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                      headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def match_and_fix(county, items, parity_source_label, target_case_numbers=None):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    parity_promoted = []
    parcel_backfilled = []
    card_backfilled = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            continue
        if target_case_numbers is not None and row["case_number"] not in target_case_numbers:
            continue
        item = by_norm[cn]
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")

        try:
            if not (row["parity_status"] == "matched_clean" and already_tier1):
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": parity_source_label})
                parity_promoted.append(row["id"])
        except Exception as e:
            print(f"    parity patch FAILED for {row['id']} ({row['case_number']}): {e}")
            continue

        patch_body = {}
        if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
            patch_body["parcel_id"] = item["parcel_id"]
        if not row.get("property_address") and item.get("property_address"):
            patch_body["property_address"] = item["property_address"]
        if not row.get("assessed_value") and item.get("assessed_value"):
            patch_body["assessed_value"] = item["assessed_value"]
        if patch_body:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
            except Exception as e:
                print(f"    card/parcel patch FAILED for {row['id']} ({row['case_number']}): {e}")
                continue
            if "parcel_id" in patch_body:
                parcel_backfilled.append(row["id"])
            if "property_address" in patch_body or "assessed_value" in patch_body:
                card_backfilled.append(row["id"])

    return parity_promoted, parcel_backfilled, card_backfilled


def main():
    if not TARGETS:
        print("usage: lee_run3679_cd_e_i_ajax_harvest.py '<json targets>'")
        sys.exit(1)

    totals = {"parity": 0, "parcel": 0, "card": 0}
    any_parsed_zero_matched = []
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        target_cns = t.get("case_numbers")
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date(county, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {county} {sale_type} {ad}: {e}")
            continue
        n_parsed = len(items)
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        try:
            parity, parcel, card = match_and_fix(
                county, items, f"tier1:shard10_run3679_lee_ajax_harvest:{sale_type}:{ad}",
                target_case_numbers=target_cns)
        except Exception as e:
            print(f"  MATCH FAIL {county} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        print(f"  {county} {sale_type} {ad}: {n_parsed} calendar items -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)}")
        if n_parsed > 0 and len(parity) == 0:
            any_parsed_zero_matched.append((county, sale_type, ad, n_parsed))
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']}")
    if any_parsed_zero_matched:
        print("NOTE (not fatal, per-date, matches shard11/14 precedent): "
              f"parsed>0 but 0 promoted on: {any_parsed_zero_matched}")


if __name__ == "__main__":
    main()
