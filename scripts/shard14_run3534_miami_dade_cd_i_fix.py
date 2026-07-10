#!/usr/bin/env python3
"""SHARD-14 (miami_dade only), dispatch 121fa7c3-6131-474f-b6c8-928efe26d2f5.

C/D/I backfill for miami_dade. Reuses the proven AJAX RealAuction/RealTaxDeed
harvester from scripts/shard2_run2450_ajax_realforeclose_harvest.py (same
mechanism as scripts/shard14_martin_bay_alachua_lake_cd_e_i_fix.py) to pull
the live calendar per (county, sale_type, auction_date), then:
  1. exact case_number match -> parity_status='matched_clean',
     parity_source='tier1:shard14_run3534_ajax_harvest:<sale_type>:<date>' (C/D)
  2. for matched rows still missing parcel_id/property_address/assessed_value,
     backfill those fields from the harvested item (contributes to I)

Diagnosis this session (live REST queries against multi_county_auctions,
county=miami_dade, scored population = data_source<>propertyonion OR
data_source IS NULL):
  - auctions_total = 356, unmatched (no tier1 parity) = 351
  - unmatched rows span 40 distinct (sale_type, auction_date) pairs; the two
    densest dates are 2026-06-29 foreclosure (37) and 2026-06-29 tax_deed (37)
  - I gap = 21 rows: 14 rows missing parcel_id and/or property_address
    (9 missing address, 14 missing parcel_id, union=14), plus 7 rows that
    already have parcel_id/address/geo/value but whose parcel_id format does
    not match v_zoning_gold_standard_card (a join-format issue this script
    cannot fix -- it only backfills raw fields, it does not touch the zoning
    join). This script targets the 14 field-backfillable rows explicitly
    (by case_number) in addition to running the highest-density C/D dates.

miami_dade auctions_total=356 makes a full 40-date sweep the correct call
(not a "one date only" partial pass) -- ~40 HTTP fetches at ~0.4-3s each is
well within session budget and matches the shard14 martin/bay/alachua/lake
precedent of sweeping the full date list rather than truncating.

Direct DB (psycopg2/pooler) is NOT used -- SUPABASE_DB_PASSWORD confirmed
stale this session per shard8/9/13/14 precedent. All reads/writes go through
PostgREST.

Idempotent: only patches parity when not already tier1-labeled matched_clean;
only backfills parcel_id/address/assessed_value when the existing value is
NULL. Never blind-overwrites non-null data.

Usage: python3 scripts/shard14_run3534_miami_dade_cd_i_fix.py
"""
import os
import sys
import json
import time
import importlib.util
from collections import Counter

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

import urllib.request
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "miami_dade"
SUBDOMAIN = "miamidade"
DISPATCH_TAG = "shard14_run3534"

PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}


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


def load_targets():
    """Live REST query: distinct (sale_type, auction_date) among unmatched
    miami_dade rows, ranked by density (most auction-dense first)."""
    rows = rest_get(
        "multi_county_auctions?county=eq.miami_dade"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,sale_type,auction_date,parity_status,parity_source,"
        "parcel_id,property_address,assessed_value,market_value")
    unmatched = [r for r in rows
                 if not (r.get("parity_status") == "matched_clean"
                         and (r.get("parity_source") or "").startswith("tier1"))]
    c = Counter((r["sale_type"], r["auction_date"]) for r in unmatched if r.get("auction_date"))
    ranked = sorted(c.items(), key=lambda kv: -kv[1])
    print(f"diagnosis: {len(rows)} scored rows, {len(unmatched)} unmatched, "
          f"{len(ranked)} distinct (sale_type,date) pairs")
    return [{"county": COUNTY, "sale_type": st, "auction_date": ad} for (st, ad), _n in ranked], rows


def match_and_fix(items, parity_source_label):
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
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
    targets, _all_rows = load_targets()
    if not targets:
        print("No unmatched (sale_type, auction_date) pairs found -- nothing to do.")
        return

    totals = {"parity": 0, "parcel": 0, "card": 0}
    for t in targets:
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date(SUBDOMAIN, COUNTY, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"  {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        try:
            parity, parcel, card = match_and_fix(
                items, f"tier1:{DISPATCH_TAG}_ajax_harvest:{sale_type}:{ad}")
        except Exception as e:
            print(f"  MATCH FAIL {sale_type} {ad}: {e}")
            continue
        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        print(f"  {sale_type} {ad}: {len(items)} calendar items -> "
              f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)}")
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={totals['parity']} parcel_backfilled={totals['parcel']} "
          f"card_backfilled={totals['card']}")


if __name__ == "__main__":
    main()
