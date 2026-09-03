#!/usr/bin/env python3
"""Leon C/D pipeline-lag fix, session 2026-09-03 (SUMMIT #19774 shard-2).

Same proven pattern as scripts/leon_c_d_j_pipeline_lag_20260808.py (forked
verbatim match_and_fix() from scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py):
the 15 leon rows with parity_status IS NULL are freshly calendar-swept future
auctions (created 2026-08-18..09-03, auction_date 2026-09-09..10-21) that have
not yet been through the leon parity harvester. This is a genuine lag, not a
broken pipeline -- confirmed by re-running the exact same live-harvest
technique that closed the prior 12-row batch on 2026-08-08. This is a fresh
batch (disjoint case numbers) that arrived after that session, not a
re-attempt of an exhausted lever.

Restricted via TARGET_CASE_NUMBERS to only these 15 rows; does not touch any
other leon row.
"""
import os
import re
import sys
import json
import time
import importlib.util
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

RUN_LABEL = "tier1:leon_shard2_19774_pipeline_lag_20260903_ajax_harvest"

TARGETS = [
    {"sale_type": "foreclosure", "auction_date": "2026-09-09"},
    {"sale_type": "foreclosure", "auction_date": "2026-09-17"},
    {"sale_type": "foreclosure", "auction_date": "2026-09-22"},
    {"sale_type": "tax_deed", "auction_date": "2026-09-16"},
    {"sale_type": "tax_deed", "auction_date": "2026-10-21"},
]

TARGET_CASE_NUMBERS = {
    "2025 CA 002239", "2025 CA 001417", "2025 CA 002217", "2025 CA 001594",
    "2025 CA 001669", "2025 CA 002578", "2025 CA 001519",
    "26-0103", "26-0106", "26-0102", "26-0097", "26-0098", "26-0099", "26-0096",
    "17-0185",
}

PLATFORM_DOMAIN = {"foreclosure": "realforeclose.com", "tax_deed": "realtaxdeed.com"}


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
    for row in mca_rows:
        if row["case_number"] not in target_case_numbers:
            continue
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm:
            continue
        item = by_norm[cn]
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": parity_source_label})
            parity_promoted.append(row["case_number"])
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
                parcel_backfilled.append(row["case_number"])
            except Exception as e:
                print(f"    card patch FAILED for {row['id']} ({row['case_number']}): {e}")

    return parity_promoted, parcel_backfilled


def main():
    total_promoted = []
    total_backfilled = []
    for t in TARGETS:
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"
        platform = PLATFORM_DOMAIN[sale_type]
        try:
            items = _mod.harvest_date("leon", "leon", mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"HARVEST FAIL leon {sale_type} {ad}: {e}")
            continue
        if not items:
            print(f"leon {sale_type} {ad}: 0 items from calendar")
            continue
        promoted, backfilled = match_and_fix("leon", items, f"{RUN_LABEL}:{sale_type}:{ad}", TARGET_CASE_NUMBERS)
        print(f"leon {sale_type} {ad}: {len(items)} calendar items -> parity={promoted} card_backfill={backfilled}")
        total_promoted.extend(promoted)
        total_backfilled.extend(backfilled)
        time.sleep(0.4)

    print(f"\nTOTALS: parity_promoted={len(total_promoted)} {total_promoted}")
    print(f"card_backfilled={len(total_backfilled)} {total_backfilled}")
    missing = TARGET_CASE_NUMBERS - set(total_promoted)
    if missing:
        print(f"NOT MATCHED (residual): {sorted(missing)}")


if __name__ == "__main__":
    main()
