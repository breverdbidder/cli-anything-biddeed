#!/usr/bin/env python3
"""SHARD-14 martin (loop run 6288), dispatch a9cb3cc1-eda1-4a56-9a53-dedf15803742.

C/D gap: 2 rows out of 38 -- 25000316CAAXMX (foreclosure 2026-07-30, parity_status
NULL, never harvested) and 2024-001-TD-MARTIN (tax_deed 2026-08-15, parity_status
mca_only, prior sessions' 07-18 attempt found 0 live calendar items for that date
too far out at the time; retrying now it's closer).

Reuses the proven AJAX RealAuction/RealTaxDeed harvester
(scripts/shard2_run2450_ajax_realforeclose_harvest.py) exactly as prior martin
sessions (shard4/84d095d7, shard14/2a2b2667) did -- same mechanism, this
dispatch's own label so provenance is traceable to this session specifically
(the 2026-07-18 session's ULTRALOOP refuter caught a copy-pasted foreign-county
label bug from reusing another script's hardcoded string; this session's label
is dispatch-scoped from the start to avoid repeating that class of bug).

Idempotent: only patches parity when not already tier1-labeled matched_clean;
only backfills parcel_id/address/assessed_value when the existing value is NULL.

Usage: python3 scripts/shard14_martin_9d22d82f_run6288_cd_e_i_fix.py
"""
import json
import os
import re
import sys
import time
import importlib.util
import urllib.error
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}

TARGETS = [
    {"county": "martin", "sale_type": "foreclosure", "auction_date": "2026-07-30"},
    {"county": "martin", "sale_type": "tax_deed", "auction_date": "2026-08-15"},
]


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
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


def match_and_fix(county, items, parity_source_label, only_case_numbers=None):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    parity_promoted, parcel_backfilled, card_backfilled = [], [], []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if only_case_numbers and cn not in only_case_numbers:
            continue
        if cn not in by_norm:
            continue
        item = by_norm[cn]
        already_tier1 = (row.get("parity_source") or "").startswith("tier1")

        try:
            if not (row["parity_status"] == "matched_clean" and already_tier1):
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": parity_source_label})
                parity_promoted.append((row["id"], row["case_number"]))
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
    totals = {"parity": 0, "parcel": 0, "card": 0}
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
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items")
        if not items:
            time.sleep(0.3)
            continue
        try:
            parity, parcel, card = match_and_fix(
                county, items,
                f"tier1:shard14_a9cb3cc1_run6288_ajax_harvest:{sale_type}:{ad}")
        except Exception as e:
            print(f"  MATCH FAIL {county} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        for rid, cn in parity:
            print(f"    MATCHED {cn} -> parity_status=matched_clean")
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']}")


if __name__ == "__main__":
    main()
