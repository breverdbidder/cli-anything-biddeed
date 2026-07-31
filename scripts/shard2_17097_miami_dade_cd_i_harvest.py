#!/usr/bin/env python3
"""Miami-Dade C/D/I harvest — SHARD-2, issue 17097, dispatch 83c11ccb.

Context: Since run3786 (2026-07-11) the miami_dade denominator grew from 356 to
422 (66 new auctions ingested). The evaluator now shows:
  C FAIL 94.3% (matched_clean=398/422)
  D FAIL 94.3% (matched_any=398/422)
  I FAIL 80.1% (card_complete=338/422)

The 66 new rows (and any residual from prior runs) are unmatched. This script:
  1. Queries all unmatched miami_dade rows (parity_status != matched_clean OR
     parity_source not tier1-labeled) from multi_county_auctions.
  2. Groups by (sale_type, auction_date), sweeps the RealAuction AJAX calendar
     for each date via harvest_date() from shard2_run2450_ajax_realforeclose_harvest.py.
  3. On exact case_number match: sets parity_status='matched_clean', tier1 parity_source.
  4. Also backfills parcel_id / property_address / assessed_value when missing (I fix).

Idempotent: only patches parity when not already tier1 matched_clean;
only backfills fields when existing value is NULL.

Usage: python3 scripts/shard2_17097_miami_dade_cd_i_harvest.py
Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (required)
"""
import json
import os
import re
import sys
import time
import importlib.util
import urllib.request
import urllib.error
from collections import Counter

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester",
    os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

COUNTY = "miami_dade"
SUBDOMAIN = "miamidade"
DISPATCH_TAG = "shard2_17097_83c11ccb"
PLATFORM_DOMAIN = {
    "foreclosure": "realforeclose.com",
    "tax_deed": "realtaxdeed.com",
}


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
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            })
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body, timeout=90):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(),
            method="PATCH",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def load_targets():
    """Query all miami_dade rows, return (ranked date targets, all rows)."""
    rows = rest_get(
        "multi_county_auctions"
        "?county=eq.miami_dade"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,case_number,sale_type,auction_date,parity_status,parity_source,"
        "parcel_id,property_address,assessed_value,market_value"
    )
    unmatched = [
        r for r in rows
        if not (
            r.get("parity_status") == "matched_clean"
            and (r.get("parity_source") or "").startswith("tier1")
        )
    ]
    c = Counter(
        (r["sale_type"], r["auction_date"])
        for r in unmatched
        if r.get("auction_date")
    )
    ranked = sorted(c.items(), key=lambda kv: -kv[1])
    print(
        f"diagnosis: {len(rows)} scored rows, {len(unmatched)} unmatched, "
        f"{len(ranked)} distinct (sale_type, date) pairs to sweep"
    )
    return [(st, ad) for (st, ad), _n in ranked], rows


def match_and_fix(items, parity_source_label, sale_type, auction_date):
    """Match harvested calendar items against DB rows for one (sale_type, date) pair.
    Returns (parity_promoted_ids, parcel_backfilled_ids, card_backfilled_ids)."""
    by_norm = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm[cn] = it

    mca_rows = rest_get(
        f"multi_county_auctions"
        f"?county=eq.{COUNTY}"
        f"&sale_type=eq.{sale_type}"
        f"&auction_date=eq.{auction_date}"
        f"&or=(data_source.neq.propertyonion,data_source.is.null)"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,"
        f"property_address,assessed_value"
    )

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
                rest_patch(
                    f"multi_county_auctions?id=eq.{row['id']}",
                    {"parity_status": "matched_clean", "parity_source": parity_source_label},
                )
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
    ranked_targets, _all_rows = load_targets()
    if not ranked_targets:
        print("No unmatched (sale_type, auction_date) pairs — nothing to sweep.")
        return 0

    totals = {"parity": 0, "parcel": 0, "card": 0}
    sweep_count = 0

    for sale_type, auction_date in ranked_targets:
        y, m, d = auction_date.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN.get(sale_type)
        if not platform:
            print(f"  SKIP {sale_type} {auction_date}: unknown platform")
            continue

        try:
            items = _mod.harvest_date(SUBDOMAIN, COUNTY, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"  HARVEST FAIL {sale_type} {auction_date}: {e}")
            continue

        sweep_count += 1
        if not items:
            print(f"  {sale_type} {auction_date}: 0 items from calendar (nothing to match)")
            time.sleep(0.3)
            continue

        try:
            parity, parcel, card = match_and_fix(
                items,
                f"tier1:{DISPATCH_TAG}_ajax_harvest:{sale_type}:{auction_date}",
                sale_type,
                auction_date,
            )
        except Exception as e:
            print(f"  MATCH FAIL {sale_type} {auction_date}: {e}")
            continue

        totals["parity"] += len(parity)
        totals["parcel"] += len(parcel)
        totals["card"] += len(card)
        print(
            f"  {sale_type} {auction_date}: {len(items)} calendar items -> "
            f"parity={len(parity)} parcel_id={len(parcel)} card={len(card)}"
        )
        time.sleep(0.4)

    print(
        f"\nTOTALS after {sweep_count} date sweeps: "
        f"parity_promoted={totals['parity']} "
        f"parcel_backfilled={totals['parcel']} "
        f"card_backfilled={totals['card']}"
    )
    if totals["parity"] == 0 and totals["parcel"] == 0 and totals["card"] == 0:
        print(
            "NOTE: zero new matches found. This may mean the residual rows are "
            "genuinely NOT on the RealAuction/RealTaxDeed calendar "
            "(wrong date, different platform, or login-walled cases). "
            "See session report for prior exhaustive sweep findings."
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
