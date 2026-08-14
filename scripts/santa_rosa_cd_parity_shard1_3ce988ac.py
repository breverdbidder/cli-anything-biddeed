#!/usr/bin/env python3
"""Gold Standard shard-1 (dispatch 3ce988ac), santa_rosa C/D fix.

santa_rosa C and D were both FAIL at 94.6% (matched_clean=matched_any=105 of
111, need >=106). All 6 gap rows are foreclosure auctions with
data_source='calendar_sweep_mca_v3' and auction_date in the future
(2026-08-26 .. 2026-09-02) that had never been run through the parity
matcher (parity_status/parity_source both NULL). PropertyOnion has zero
coverage for these 6 case numbers/addresses (verified via direct
propertyonion_listings address search, fips_code=12113) -- confirmed
PO-coverage gap, not a matcher bug.

Per standing authorization, falls back to the county's own live tier1
auction source (santarosa.realforeclose.com) as the supplementary litmus.
This is the SAME AJAX harvester (scripts/shard2_run2450_ajax_realforeclose_harvest.py)
and SAME match/patch pattern already used successfully for the other 105
santa_rosa rows (parity_source prefix 'tier1:shard11_run3534_santa_rosa_ajax_harvest:...').
Verified live 2026-08-14: all 6 case numbers + property addresses are present
on the live santarosa.realforeclose.com AJAX calendar for their respective
auction dates, address strings match the DB rows exactly.

Fork of scripts/shard11_run3534_santa_rosa_cd_harvest.py, narrowed to only
the 3 auction dates covering the 6 gap rows.

Usage: python3 scripts/santa_rosa_cd_parity_shard1_3ce988ac.py
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

COUNTY = "santa_rosa"
SUBDOMAIN = "santarosa"
PLATFORM = "realforeclose.com"

# Exactly the 3 dates covering the 6 NULL-parity gap rows identified live.
TARGET_DATES = ["08/26/2026", "09/01/2026", "09/02/2026"]

GAP_CASE_NUMBERS = {
    "572025CA000469CAAXMX",
    "572025CA000619CAAXMX",
    "572025CA000897CAAXMX",
    "572025CA000824CAAXMX",
    "572025CA000343CAAXMX",
    "572025CA000513CAAXMX",
}


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


def main():
    # Fetch only the gap rows (NULL parity_status) up front for a tight, auditable diff.
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&parity_status=is.null"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value")
    print(f"gap rows found (parity_status IS NULL): {len(mca_rows)}")
    for r in mca_rows:
        print(f"  {r['case_number']}  {r['property_address']}")

    found_cns = {norm_case_number(r["case_number"]) for r in mca_rows}
    expected_cns = {norm_case_number(c) for c in GAP_CASE_NUMBERS}
    if found_cns != expected_cns:
        print(f"WARNING: live gap rows {found_cns} != expected {expected_cns} -- proceeding with LIVE set")

    patched = []
    parcel_backfilled = []
    for d in TARGET_DATES:
        items = _mod.harvest_date(SUBDOMAIN, COUNTY, d, platform_domain=PLATFORM)
        print(f"\n{d}: {len(items)} live calendar items harvested from santarosa.realforeclose.com")
        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        for row in mca_rows:
            cn = norm_case_number(row["case_number"])
            if cn not in by_norm:
                continue
            item = by_norm[cn]
            # Sanity check: address must actually match before we claim a litmus match.
            db_addr = (row.get("property_address") or "").upper()
            live_addr = (item.get("property_address") or "").upper()
            addr_ok = bool(db_addr) and bool(live_addr) and db_addr.split(",")[0].strip() == live_addr.split(",")[0].strip()
            print(f"  MATCH {row['case_number']}: db_addr='{db_addr}' live_addr='{live_addr}' addr_match={addr_ok}")
            if not addr_ok:
                print(f"    SKIP (address mismatch, not marking matched_clean)")
                continue

            parity_source = f"tier1:santa_rosa_cd_parity_shard1_3ce988ac:{item['aid']}:{d}"
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                           {"parity_status": "matched_clean", "parity_source": parity_source})
                patched.append(row["id"])
                print(f"    PATCHED parity_status=matched_clean parity_source={parity_source}")
            except Exception as e:
                print(f"    PATCH FAILED for {row['id']} ({row['case_number']}): {e}")
                continue

            # Opportunistic NULL-only backfill of parcel_id, consistent with prior sessions.
            patch_body = {}
            if not row.get("parcel_id") and is_real_parcel_id(item.get("parcel_id")):
                patch_body["parcel_id"] = item["parcel_id"]
            if not row.get("assessed_value") and item.get("assessed_value"):
                patch_body["assessed_value"] = item["assessed_value"]
            if patch_body:
                try:
                    rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                    parcel_backfilled.append(row["id"])
                    print(f"    also backfilled {list(patch_body.keys())}")
                except Exception as e:
                    print(f"    card/parcel patch FAILED for {row['id']}: {e}")
        time.sleep(0.6)

    print(f"\nTOTALS: parity_promoted={len(patched)} card_backfilled={len(parcel_backfilled)}")
    remaining = rest_get(f"multi_county_auctions?county=eq.{COUNTY}&parity_status=is.null&select=id")
    print(f"remaining NULL-parity rows after run: {len(remaining)}")


if __name__ == "__main__":
    main()
