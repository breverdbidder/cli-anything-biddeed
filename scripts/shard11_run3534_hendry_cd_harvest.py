#!/usr/bin/env python3
"""SHARD-11 run 3534, hendry C/D/E/I backfill (tax_deed only).

Reuses the proven AJAX RealAuction/RealTaxDeed harvester from
scripts/shard2_run2450_ajax_realforeclose_harvest.py plus the exact-match/patch
logic from scripts/shard9_flagler_cd_ajax_harvest.py (same proven pattern
already shipped for flagler/bay/martin/alachua/lake), applied to hendry.

SCOPE: hendry has 19 total rows. 17 are tax_deed (platform
hendry.realtaxdeed.com, online) -- these are harvested here. The other 2 are
sale_type='foreclosure' with fake-looking case numbers (HENDRY-FC-2026-001/002)
and county_auction_config confirms hendry foreclosures are fc_method='in_person'
with fc_url=null -- there is NO online RealAuction/RealForeclose platform for
hendry foreclosures to litmus-match against. Those 2 rows are deliberately left
untouched by this script (see session report; do not add a foreclosure target
here without a genuine independent source).

For each distinct tax_deed auction_date present in hendry's multi_county_auctions
rows:
  1. harvest the live RealTaxDeed calendar for that date via the AJAX endpoint
  2. exact-match by normalized case_number
  3. PATCH parity_status='matched_clean',
     parity_source='tier1:shard11_run3534_hendry_ajax_harvest:tax_deed:<date>'
  4. opportunistically backfill parcel_id/property_address/assessed_value when
     missing on the MCA row (idempotent -- only fills NULLs)

Direct DB (psycopg2/pooler) not used -- PostgREST only, consistent with prior
shard sessions (password auth confirmed stale).

Usage: python3 scripts/shard11_run3534_hendry_cd_harvest.py '<json targets>'
  targets: [{"county":"hendry","sale_type":"tax_deed","auction_date":"2026-07-16"}, ...]
  (defaults to hendry tax_deed 2026-07-16 if no argv given -- the one distinct
  date present among hendry's 17 tax_deed rows as of this session)
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

DEFAULT_TARGETS = [{"county": "hendry", "sale_type": "tax_deed", "auction_date": "2026-07-16"}]
TARGETS = json.loads(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TARGETS

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


def match_and_fix(county, items, parity_source_label):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{county}"
        f"&sale_type=eq.tax_deed"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")

    parity_promoted = []
    parcel_backfilled = []
    card_backfilled = []
    matched_case_numbers = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            continue
        item = by_norm[cn]
        matched_case_numbers.append(row["case_number"])
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

    unmatched = [r["case_number"] for r in mca_rows if norm_case_number(r["case_number"]) not in by_norm]
    return parity_promoted, parcel_backfilled, card_backfilled, matched_case_numbers, unmatched


def main():
    if not TARGETS:
        print("usage: shard11_run3534_hendry_cd_harvest.py '<json targets>'")
        sys.exit(1)

    totals = {"parity": 0, "parcel": 0, "card": 0}
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        if not ad:
            print(f"  {county} {sale_type}: skip (no auction_date)")
            continue
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
            time.sleep(0.4)
            continue
        try:
            parity, parcel, card, matched, unmatched = match_and_fix(
                county, items, f"tier1:shard11_run3534_hendry_ajax_harvest:{sale_type}:{ad}")
        except Exception as e:
            print(f"  MATCH FAIL {county} {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        print(f"  {county} {sale_type} {ad}: {len(items)} calendar items -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)}")
        print(f"    parity_promoted_ids={parity}")
        print(f"    matched_case_numbers={matched}")
        print(f"    unmatched_case_numbers={unmatched}")
        time.sleep(0.6)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']}")


if __name__ == "__main__":
    main()
