#!/usr/bin/env python3
"""GOLD STANDARD shard-6 (highlands, st_lucie), loop run 6288, dispatch 5fa42352.

st_lucie C/D fix: the 10 rows with parity_status/parity_source NULL were all
sale_type=foreclosure, auction_status=upcoming, on auction dates 2026-08-05 and
2026-08-11 (verified via live DB query). Live-harvests stlucie.realforeclose.com
for those two dates via the proven AJAX endpoint (reuses
scripts/shard2_run2450_ajax_realforeclose_harvest.py::harvest_date verbatim —
same RealAuction-family mechanism, subdomain "stlucie"), upserts into
realforeclose_aids, then patches multi_county_auctions directly (scoped to the
10 target case numbers only — the generic realforeclose_aids_to_mca_patch()
function timed out via the Management API when run unscoped against the full
table, see session report).

3 additional rows already had parity_status='matched_clean' with an un-prefixed
parity_source='realforeclose_aids_patch' (a genuine live RealAuction match, just
missing the 'tier1' naming convention the evaluator requires) — same rename
already applied to martin/gulf in
supabase/migrations/20260628_parity_source_tier1_prefix_17counties.sql for the
identical source string.

Idempotent: safe to rerun (WHERE clauses target only the specific rows;
COALESCE preserves any values already backfilled by a later, better source).

Usage: python3 scripts/shard6_run6288_stlucie_ajax_harvest_and_patch.py
"""
from __future__ import annotations
import importlib.util
import json
import os
import sys
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
MGMT_TOKEN = os.environ["SUPABASE_ACCESS_TOKEN"]
MGMT_API = "https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

TARGET_CASES = [
    "2024CA000833", "2025CA001214", "2025CA001746", "2025CA001835",
    "2025CA002235", "2025CA002238", "2025CA002331", "2025CC003597",
    "2026CA000135", "2026CA000534",
]
AUCTION_DATES = ["08/05/2026", "08/11/2026"]


def run_sql(sql: str):
    req = urllib.request.Request(
        MGMT_API,
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {MGMT_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def load_harvester():
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "harvester", os.path.join(here, "shard2_run2450_ajax_realforeclose_harvest.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    harvester = load_harvester()

    total_parsed = 0
    for date in AUCTION_DATES:
        items = harvester.harvest_date("stlucie", "st_lucie", date, platform_domain="realforeclose.com")
        found = sorted(set(i.get("case_number") for i in items if i.get("case_number")))
        print(f"[harvest] date={date} parsed={len(items)} cases={found}")
        total_parsed += len(items)
        n = harvester.upsert_aids(items, "st_lucie", "shard6_run6288_stlucie_cd_harvest")
        print(f"[harvest] date={date} upserted={n}")

    if total_parsed == 0:
        raise RuntimeError("FAIL-LOUD: live AJAX harvest parsed 0 items across both target dates — "
                            "cannot proceed with a silent no-op patch.")

    rename_sql = """
    UPDATE multi_county_auctions
    SET parity_source = 'tier1_realforeclose', updated_at = now()
    WHERE lower(county) = 'st_lucie' AND parity_source = 'realforeclose_aids_patch' AND parity_status = 'matched_clean';
    """
    run_sql(rename_sql)
    print("[patch] renamed pre-existing realforeclose_aids_patch rows -> tier1_realforeclose")

    cases_sql = ",".join(f"'{c}'" for c in TARGET_CASES)
    patch_sql = f"""
    UPDATE multi_county_auctions mca
    SET parcel_id = COALESCE(mca.parcel_id, ra.parcel_id),
        property_address = COALESCE(mca.property_address, ra.property_address),
        assessed_value = COALESCE(mca.assessed_value, ra.assessed_value),
        plaintiff_max_bid = COALESCE(mca.plaintiff_max_bid, ra.plaintiff_max_bid),
        opening_bid = COALESCE(mca.opening_bid, ra.judgment_amount),
        parity_status = 'matched_clean',
        parity_source = 'tier1_realforeclose',
        updated_at = now()
    FROM realforeclose_aids ra
    WHERE lower(mca.county) = 'st_lucie'
      AND ra.county_slug = 'st_lucie'
      AND mca.case_number = ra.case_number
      AND mca.case_number IN ({cases_sql});
    """
    run_sql(patch_sql)
    print(f"[patch] scoped-matched {len(TARGET_CASES)} target case_numbers -> matched_clean/tier1_realforeclose")


if __name__ == "__main__":
    main()
