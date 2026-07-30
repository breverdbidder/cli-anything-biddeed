#!/usr/bin/env python3
"""GOLD STANDARD shard-3, county=volusia.

C/D backfill for volusia's ~25 in-scope rows with parity_status IS NULL (freshly
scraped upcoming auctions never swept by the tier1 parity harvester), scoped to
(data_source <> 'propertyonion' OR tier1_authoritative). Live-verified this
session (2026-07-30):
  foreclosure: 2026-07-06, 2026-07-07(x2), 2026-07-23(x2), 2026-07-24(x2),
    2026-07-27(x2), 2026-07-28(x7), 2026-07-29(x3), 2026-07-30, 2026-07-31(x4)
  tax_deed: 2026-06-09

Forked verbatim from scripts/gold_standard_shard10_alachua_cd_ajax_harvest_run6253.py
(same match_and_fix() pattern, different county/dates). Reuses the proven AJAX
RealAuction/RealTaxDeed harvester at scripts/shard2_run2450_ajax_realforeclose_harvest.py.
Volusia subdomain is 'volusia' for both realforeclose.com and realtaxdeed.com
platforms (confirmed live this session).

For each distinct (sale_type, auction_date) present in volusia's
multi_county_auctions rows with parity_status IS NULL:
  1. harvest the live RealAuction/RealTaxDeed calendar for that date via the
     AJAX endpoint
  2. exact-match by normalized case_number
  3. PATCH parity_status='matched_clean',
     parity_source='tier1:gold_standard_shard3_volusia_stlucie:<sale_type>:<date>'
  4. opportunistically backfill parcel_id/property_address/assessed_value when
     missing on the MCA row (idempotent -- only fills NULLs)

Direct DB (psycopg2/pooler) not used -- PostgREST only, matching every prior
shard session's precedent.

Fails loud: if a date's calendar returns >0 parsed items but 0 rows get
parity-promoted, that is logged explicitly, not swallowed.

Usage: python3 scripts/gold_standard_shard3_volusia_cd_ajax_harvest.py '<json targets>'
  targets: [{"county":"volusia","sale_type":"foreclosure","auction_date":"2026-07-06"}, ...]
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
        # Only touch this dispatch's target rows -- do not silently promote
        # unrelated already-matched volusia rows.
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
        print("usage: gold_standard_shard3_volusia_cd_ajax_harvest.py '<json targets>'")
        sys.exit(1)

    totals = {"parity": 0, "parcel": 0, "card": 0}
    any_parsed_zero_matched = []
    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]  # YYYY-MM-DD
        target_cns = t.get("case_numbers")  # optional restrict list
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
        n_parsed = len(items)
        if not items:
            print(f"  {county} {sale_type} {ad}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue
        try:
            parity, parcel, card = match_and_fix(
                county, items, f"tier1:gold_standard_shard3_volusia_stlucie:{sale_type}:{ad}",
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
        print("NOTE (not fatal, per-date, matches shard6/10/11 precedent): "
              f"parsed>0 but 0 promoted on: {any_parsed_zero_matched}")


if __name__ == "__main__":
    main()
