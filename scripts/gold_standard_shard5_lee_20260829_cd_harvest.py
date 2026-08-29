#!/usr/bin/env python3
"""GOLD STANDARD lee C/D/I fix, 2026-08-29 session (task: "Lee C/D/I/J: size and fix
the 118-row new-batch gap" per TaskList item #2).

Forked verbatim (pattern) from scripts/gold_standard_shard10_lee_cd_e_i_ajax_harvest_run3679.py,
itself forked from scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py. Retargeted at the
107 lee rows scraped 2026-08-27T21:07 .. 2026-08-29T04:20 that never went through the
parity-matching pipeline (parity_status IS NULL for all 107, vs 341 older rows all
parity_status='matched_clean' with a tier1-prefixed parity_source, confirmed live via
`multi_county_auctions?county=eq.lee&parity_status=is.null&created_at=gte.2026-08-27T00:00:00`
-> 108 rows, 107 of which fall into the 5 buckets below; the 108th is a stray
2021-05-19 foreclosure row outside scope, left untouched).

TARGET BUCKETS (auctions_total grew 330->448 since lee last hit 10/10 on 2026-08-25):
  foreclosure 2026-08-27  x8
  foreclosure 2026-09-03  x11
  foreclosure 2026-09-10  x1
  tax_deed    2026-09-01  x42
  tax_deed    2026-09-15  x45
  (= 107, all near-term real calendar dates on the county's own AJAX calendar)

Uses harvest_date() from scripts/shard2_run2450_ajax_realforeclose_harvest.py against the
LIVE RealForeclose (foreclosure) / RealTaxDeed (tax_deed) AJAX calendar for lee, exact-matches
by normalized case_number against multi_county_auctions rows (scoped to non-PropertyOnion /
tier1-eligible rows), and where matched: PATCHes parity_status='matched_clean' + a
parity_source starting with 'tier1:' (required prefix for the C/D evaluator filter
parity_source LIKE 'tier1%'), and opportunistically backfills parcel_id/property_address/
assessed_value from the AJAX item if the MCA row is missing them and the AJAX item has real
data (not a placeholder like literal 'Property Appraiser' text -- see is_real_parcel_id()).
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
    {"county": "lee", "sale_type": "foreclosure", "auction_date": "2026-08-27"},
    {"county": "lee", "sale_type": "foreclosure", "auction_date": "2026-09-03"},
    {"county": "lee", "sale_type": "foreclosure", "auction_date": "2026-09-10"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-09-01"},
    {"county": "lee", "sale_type": "tax_deed", "auction_date": "2026-09-15"},
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

    # Scope to the exact bucket: only NULL-parity rows for this county/sale_type/auction_date.
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
                f"tier1:shard5_lee_20260829_ajax_harvest:{sale_type}:{ad}")
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
