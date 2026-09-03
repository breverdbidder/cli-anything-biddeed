#!/usr/bin/env python3
"""GOLD STANDARD lee C/D/E fix, session 2026-09-03.

Forked verbatim (pattern) from scripts/gold_standard_shard5_lee_20260829_cd_harvest.py
(itself forked from scripts/gold_standard_shard10_lee_cd_e_i_ajax_harvest_run3679.py /
scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py). Retargeted at the 211 lee rows
with parity_status IS NULL (confirmed live via pencil_dod_evaluate_county('lee') diagnosis
this session: C=345/680 matched_clean 50.7%, D=345/680 matched_any 50.7%, E=502/680
parcel_linked 73.8%). Of the 335-row C/D gap, 124 rows are parity_status='REALTDM_REDEEMED'
(tax certificate redeemed pre-sale -- a genuine cancellation, intentionally excluded from
both matched_clean AND matched_any by the shared eval formula, same structural class as
sumter/gadsden's CLERK_SSOT_CANCELLED precedent -- NOT touched by this script, see session
report). The remaining 211 rows have parity_status IS NULL: 1 foreclosure (2026-09-03) and
210 tax_deed spread across 6 future auction dates (2026-09-15, 09-22, 09-29, 10-06, 10-20,
10-27) that were harvested into multi_county_auctions but never run through the live
RealTaxDeed/RealForeclose AJAX parity matcher. This script closes that gap via live
calendar harvest, exact case_number match, and opportunistic parcel_id/property_address/
assessed_value backfill (which also feeds E and I).
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

TARGETS = [
    {"county": "lee", "sale_type": "foreclosure", "auction_date": "2026-09-03"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-09-15"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-09-22"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-09-29"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-10-06"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-10-20"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-10-27"},
]
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


def match_and_fix(county, sale_type, auction_date, items, parity_source_label):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    # Scope to the exact bucket: only NULL-parity rows for this county/sale_type/auction_date,
    # excluding PropertyOnion litmus rows (never eligible for tier1 promotion).
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}&sale_type=eq.{sale_type}"
        f"&auction_date=eq.{auction_date}&parity_status=is.null"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    parity_promoted = []
    parcel_backfilled = []
    card_backfilled = []
    unmatched = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            unmatched.append(row["case_number"])
            continue
        item = by_norm[cn]

        try:
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

    return parity_promoted, parcel_backfilled, card_backfilled, unmatched, len(mca_rows)


def main():
    totals = {"parity": 0, "parcel": 0, "card": 0, "target_rows": 0}
    any_parsed_zero_matched = []
    all_unmatched = []
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]
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
            parity, parcel, card, unmatched, n_target = match_and_fix(
                county, sale_type, ad, items,
                f"tier1:gold_standard_lee_20260903_cd_e_null_parity_harvest:{sale_type}:{ad}")
        except Exception as e:
            print(f"  MATCH FAIL {county} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        totals["target_rows"] += n_target
        print(f"  {county} {sale_type} {ad}: {n_parsed} calendar items, {n_target} target MCA rows -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)} unmatched={len(unmatched)}")
        if unmatched:
            all_unmatched.extend([(sale_type, ad, cn) for cn in unmatched])
        if n_parsed > 0 and len(parity) == 0:
            any_parsed_zero_matched.append((county, sale_type, ad, n_parsed))
        time.sleep(0.4)

    print(f"\nTOTALS: target_rows={totals['target_rows']} parity_promoted={totals['parity']} "
          f"parcel_backfilled={totals['parcel']} card_backfilled={totals['card']}")
    if any_parsed_zero_matched:
        print("NOTE (not fatal, per-date, matches shard10/11/14 precedent): "
              f"parsed>0 but 0 promoted on: {any_parsed_zero_matched}")
    if all_unmatched:
        print(f"UNMATCHED case_numbers (not found in live calendar pull, {len(all_unmatched)} total):")
        for sale_type, ad, cn in all_unmatched:
            print(f"    {sale_type} {ad}: {cn}")


if __name__ == "__main__":
    main()
