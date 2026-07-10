#!/usr/bin/env python3
"""SHARD-14 seminole, dispatch 121fa7c3-6131-474f-b6c8-928efe26d2f5.

C/D/E/I backfill for seminole. Reuses the proven AJAX RealAuction/RealTaxDeed
harvester from scripts/shard2_run2450_ajax_realforeclose_harvest.py (same
mechanism as scripts/shard14_martin_bay_alachua_lake_cd_e_i_fix.py) to pull
the live calendar per (sale_type, auction_date), then:
  1. exact case_number match -> parity_status='matched_clean',
     parity_source='tier1:shard14_run3534_seminole_ajax_harvest:<sale_type>:<date>' (C/D)
  2. for matched rows still missing parcel_id, backfill parcel_id from the
     harvested item (E) -- the AJAX item already carries parcel_id/assessed_value/address
  3. for matched rows still missing property_address/assessed_value, backfill
     those too (contributes to I's address+value fields)

Diagnosis this session (live REST query against multi_county_auctions,
county=eq.seminole, excluding data_source=propertyonion unless
tier1_authoritative): auctions_total=99. 12 rows not tier1 matched_clean
(all sale_type=foreclosure), on auction_date 2026-07-23 (7), 2026-08-04 (3),
2026-07-28 (1), 2026-07-30 (1). 7 rows missing parcel_id, on auction_date
2026-06-30 (3), 2026-07-23 (3), 2026-08-04 (1) -- these overlap partially
with the not-matched set. All target dates are sale_type=foreclosure ->
platform_domain=realforeclose.com, subdomain=seminole (confirmed by existing
rows' parity_source values like 'tier1_realforeclose_ajax_seminole').

Direct DB (psycopg2/pooler) is NOT used -- confirmed stale this session,
consistent with prior shard8/9/13/14 findings. All reads/writes go through
PostgREST.

Idempotent: only patches parity when not already tier1-labeled matched_clean;
only backfills parcel_id/address/assessed_value when the existing value is NULL.

Usage: python3 scripts/shard14_run3534_seminole_cd_e_i_fix.py
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

# Diagnosed live this session: every not-tier1-matched or no-parcel_id row in
# seminole's scored population falls on one of these (sale_type, date) pairs.
TARGET_DATES = [
    ("foreclosure", "2026-06-30"),
    ("foreclosure", "2026-07-23"),
    ("foreclosure", "2026-07-28"),
    ("foreclosure", "2026-07-30"),
    ("foreclosure", "2026-08-04"),
]


def norm_case_number(cn):
    import re
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def is_real_parcel_id(pid):
    """Some AITEM blocks decode the parcel-appraiser link as its own anchor text
    ('Property Appraiser') instead of the parcel number -- a pre-existing parser
    gap in shard2's decoder. A real parcel_id always contains at least one digit."""
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
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
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
    totals = {"parity": 0, "parcel": 0, "card": 0}
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
            parity, parcel, card = match_and_fix(
                COUNTY, items, f"tier1:shard14_run3534_seminole_ajax_harvest:{sale_type}:{ad}", sale_type, ad)
        except Exception as e:
            print(f"  MATCH FAIL {COUNTY} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        print(f"  {COUNTY} {sale_type} {ad}: {len(items)} calendar items -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)}")
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']}")


if __name__ == "__main__":
    main()
