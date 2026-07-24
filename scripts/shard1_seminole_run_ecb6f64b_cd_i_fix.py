#!/usr/bin/env python3
"""SHARD-1 seminole 2nd firing, dispatch ecb6f64b-26ab-4147-86a9-8b5baedd69cc.

Re-baseline (live, this session) found auctions_total grew 105->111 since the
2026-07-18 fix (which raised C/D to 105/105 matched_clean). The 6 new rows
(all created 2026-07-21 to 2026-07-23, parity_status IS NULL) are:
  2023CA003414  fc 2026-07-23  realforeclose
  2025CA002000  fc 2026-07-23  realforeclose
  2024CC004907  fc 2026-07-28  realforeclose
  2023CC005751  fc 2026-08-11  realforeclose
  2025CA000344  fc 2026-08-11  realforeclose
  20260057/2024-003818  tax_deed 2026-09-10  realtaxdeed

Reuses the proven AJAX RealAuction harvester (scripts/shard2_run2450_ajax_realforeclose_harvest.py)
and the same match_and_fix pattern as the prior firing's
scripts/shard14_run3534_seminole_cd_e_i_fix.py: exact case_number match against
the live calendar -> parity_status='matched_clean',
parity_source='tier1:shard1_ecb6f64b_seminole_ajax_harvest:<sale_type>:<date>' (C/D).
For matched rows still missing parcel_id/property_address/assessed_value,
backfill those from the harvested item (contributes to I).

Idempotent: only patches parity when not already tier1-labeled matched_clean;
only backfills card fields when the existing value is NULL.

Usage: python3 scripts/shard1_seminole_run_ecb6f64b_cd_i_fix.py
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
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "seminole"
PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}

# Diagnosed live this session (2026-07-24): exact set of parity_status IS NULL
# rows in seminole's scored population (see session report for the full query).
TARGET_DATES = [
    ("foreclosure", "2026-07-23"),
    ("foreclosure", "2026-07-28"),
    ("foreclosure", "2026-08-11"),
    ("tax_deed", "2026-09-10"),
]


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


def match_and_fix(county, items, parity_source_label, sale_type, auction_date):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}&sale_type=eq.{sale_type}&auction_date=eq.{auction_date}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    parity_promoted = []
    parcel_backfilled = []
    card_backfilled = []
    unmatched_case_numbers = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            if row.get("parity_status") is None:
                unmatched_case_numbers.append(row["case_number"])
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

    return parity_promoted, parcel_backfilled, card_backfilled, unmatched_case_numbers


def main():
    totals = {"parity": 0, "parcel": 0, "card": 0}
    all_unmatched = []
    for sale_type, ad in TARGET_DATES:
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date(COUNTY, COUNTY, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {COUNTY} {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"  {COUNTY} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        try:
            parity, parcel, card, unmatched = match_and_fix(
                COUNTY, items, f"tier1:shard1_ecb6f64b_seminole_ajax_harvest:{sale_type}:{ad}", sale_type, ad)
        except Exception as e:
            print(f"  MATCH FAIL {COUNTY} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        all_unmatched.extend(unmatched)
        print(f"  {COUNTY} {sale_type} {ad}: {len(items)} calendar items -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)} unmatched={unmatched}")
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']} still_unmatched={all_unmatched}")


if __name__ == "__main__":
    main()
