#!/usr/bin/env python3
"""GOLD STANDARD shard3, county=st_lucie: C/D/E parity backfill for the 8
rows with parity_status IS NULL:
  - 2 foreclosure, auction_date 2026-08-12 (2025CC004353, 2025CC005297)
  - 6 tax_deed,    auction_date 2026-08-17 (26-009, 26-017, 26-024, 26-029,
    26-034, 26-045)

KEY FINDING (verified live this session): pipeline.counties lists
st_lucie's taxdeed_platform as NULL and stlucie.realtaxdeed.com returns
HTTP 403 / zero AJAX results. St Lucie's tax deed sales actually run on
stlucie.realforeclose.com itself, tagged auction_type='TAXDEED' within the
same RealForeclose AJAX calendar feed used for foreclosures. So BOTH
sale_type groups are harvested from platform_domain='realforeclose.com' for
this county -- matching is done purely by normalized case_number, ignoring
the auction_type label already stored in our DB (our sale_type='tax_deed'
rows are correctly the TAXDEED items in this feed).

Forked verbatim (match_and_fix pattern) from
scripts/gold_standard_shard10_alachua_cd_ajax_harvest_run6253.py, itself
forked from scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py. Reuses
scripts/shard2_run2450_ajax_realforeclose_harvest.py::harvest_date().

PostgREST only (no direct psycopg2/pooler connection used).

Usage: python3 scripts/gold_standard_shard3_stlucie_cd_ajax_harvest.py
"""
import os
import re
import sys
import json
import time
import importlib.util
import urllib.error
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "st_lucie"
SUBDOMAIN = "stlucie"
PLATFORM = "realforeclose.com"  # both foreclosure AND tax_deed live here for st_lucie

TARGETS = [
    {"sale_type": "foreclosure", "auction_date": "2026-08-12",
     "case_numbers": ["2025CC004353", "2025CC005297"]},
    {"sale_type": "tax_deed", "auction_date": "2026-08-17",
     "case_numbers": ["26-009", "26-017", "26-024", "26-029", "26-034", "26-045"]},
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
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
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


def match_and_fix(county, items, parity_source_label, target_case_numbers):
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
        if row["case_number"] not in target_case_numbers:
            continue
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            print(f"    {row['case_number']}: NOT FOUND live -> leaving parity_status NULL (honest gap)")
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
    today = time.strftime("%Y%m%d", time.gmtime())
    totals = {"parity": 0, "parcel": 0, "card": 0}
    any_parsed_zero_matched = []
    for t in TARGETS:
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        target_cns = t["case_numbers"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        try:
            items = _mod.harvest_date(SUBDOMAIN, COUNTY, mmddyyyy, platform_domain=PLATFORM)
        except Exception as e:
            print(f"  HARVEST FAIL {COUNTY} {sale_type} {ad}: {e}")
            continue
        n_parsed = len(items)
        if not items:
            print(f"  {COUNTY} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        try:
            parity, parcel, card = match_and_fix(
                COUNTY, items,
                f"tier1:gold_standard_shard3_stlucie:{sale_type}:{ad}",
                target_case_numbers=target_cns)
        except Exception as e:
            print(f"  MATCH FAIL {COUNTY} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        print(f"  {COUNTY} {sale_type} {ad}: {n_parsed} calendar items -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)}")
        if n_parsed > 0 and len(parity) == 0:
            any_parsed_zero_matched.append((COUNTY, sale_type, ad, n_parsed))
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']}")
    if any_parsed_zero_matched:
        print("NOTE (not fatal): parsed>0 but 0 promoted on: "
              f"{any_parsed_zero_matched}")


if __name__ == "__main__":
    main()
