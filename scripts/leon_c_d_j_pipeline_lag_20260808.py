#!/usr/bin/env python3
"""Leon C/D/J pipeline-lag fix, session 2026-08-08.

The 12 leon rows with parity_status IS NULL are freshly calendar-swept
future auctions (created 2026-08-04..08, auction_date 2026-08-12..09-16)
that simply have not yet been through the leon parity harvester. This is
a genuine lag, not a broken/stuck pipeline for leon: this session live-
harvested leon.realforeclose.com (foreclosure) and leon.realtaxdeed.com
(tax_deed) AJAX calendars for every distinct auction_date among the 12
rows and confirmed all 12 case numbers are present on the live official
county platform (same authoritative source used by the prior 188
matched_clean leon rows, e.g. parity_source
'tier1:shard11_run3645_ajax_harvest:...' /
'tier1:shard4_run_d88f924a...:...'). PropertyOnion was NOT used as a
source -- only as nothing at all here; realforeclose.com/realtaxdeed.com
ARE leon's own official auction platforms.

Forked verbatim match_and_fix() pattern from
scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py, restricted via
target_case_numbers to only the 12 rows this session diagnosed as
parity_status IS NULL (does not touch the other 188 already-matched leon
rows).
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

RUN_LABEL = "tier1:leon_pipeline_lag_20260808_ajax_harvest"

TARGETS = [
    {"sale_type": "foreclosure", "auction_date": "2026-08-07"},
    {"sale_type": "foreclosure", "auction_date": "2026-08-11"},
    {"sale_type": "foreclosure", "auction_date": "2026-08-12"},
    {"sale_type": "foreclosure", "auction_date": "2026-08-13"},
    {"sale_type": "foreclosure", "auction_date": "2026-08-21"},
    {"sale_type": "tax_deed", "auction_date": "2026-09-16"},
]

TARGET_CASE_NUMBERS = {
    "2025 CA 001437", "2024 CA 000949", "2025 CA 001408", "2025 CA 001590",
    "2025 CA 000092", "2025 CA 001461", "2025 CA 000455", "2023 CA 002248",
    "2024 CA 000626", "2025 CA 001767", "2025 CA 001511", "16-0726",
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
        print(f"NOT MATCHED (residual): {missing}")


if __name__ == "__main__":
    main()
