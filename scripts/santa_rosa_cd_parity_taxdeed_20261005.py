#!/usr/bin/env python3
"""Gold Standard santa_rosa C/D fix -- 2026-10-05 tax_deed sale gap rows.

santa_rosa C and D are tied FAIL at 94.1% (matched_clean=matched_any=111 of
118, need >=113). All 7 gap rows are brand-new tax_deed cases for the
2026-10-05 sale with parity_status/parity_source both NULL -- never run
through the parity matcher. This is the tax_deed-platform sibling of
scripts/santa_rosa_cd_parity_shard1_3ce988ac.py, which handled the
foreclosure-platform (realforeclose.com) gap for this same county using the
same AJAX harvester. That harvester's harvest_date() already accepts a
platform_domain param and is verified byte-identical across
realforeclose.com and realtaxdeed.com auction.js (see docstring in
scripts/shard2_run2450_ajax_realforeclose_harvest.py).

Verified live 2026-08-25: all 7 case numbers are present on the live
santarosa.realtaxdeed.com AJAX calendar for AUCTIONDATE=10/05/2026, with
parcel_id matching exactly (case_number + parcel_id both used as the
cross-check per CANON GUARDRAILS -- property_address for one row is
"NO ADDRESS ON TAX ROLL" on both DB and live source so address-only
matching would false-negative it; parcel_id is the reliable join key for
tax_deed rows in this county).

Convention (matched from santa_rosa_cd_parity_shard1_3ce988ac.py, the prior
C/D fix for this exact county): parity_status='matched_clean',
parity_source prefixed 'tier1:<script>:<aid>:<date>'.

Usage: python3 scripts/santa_rosa_cd_parity_taxdeed_20261005.py
"""
import os
import re
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

COUNTY = "santa_rosa"
SUBDOMAIN = "santarosa"
PLATFORM = "realtaxdeed.com"
AUCTION_DATE = "10/05/2026"

GAP_CASE_NUMBERS = {
    "2026033", "2026134", "2026138", "2026140", "2026141", "2026143", "2026149",
}


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def norm_parcel_id(pid):
    return re.sub(r"[^A-Z0-9]", "", (pid or "").upper())


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
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.tax_deed&parity_status=is.null"
        f"&select=id,case_number,parity_status,parity_source,parcel_id,property_address,assessed_value,auction_date")
    print(f"gap rows found (parity_status IS NULL, sale_type=tax_deed): {len(mca_rows)}")
    for r in mca_rows:
        print(f"  {r['case_number']}  parcel_id={r['parcel_id']}  {r['property_address']}  auction_date={r['auction_date']}")

    found_cns = {norm_case_number(r["case_number"]) for r in mca_rows}
    expected_cns = {norm_case_number(c) for c in GAP_CASE_NUMBERS}
    if found_cns != expected_cns:
        print(f"WARNING: live gap rows {found_cns} != expected {expected_cns} -- proceeding with LIVE set")

    items = _mod.harvest_date(SUBDOMAIN, COUNTY, AUCTION_DATE, platform_domain=PLATFORM)
    n_parsed = len(items)
    print(f"\n{AUCTION_DATE}: {n_parsed} live calendar items harvested from {SUBDOMAIN}.{PLATFORM}")
    if n_parsed == 0:
        raise RuntimeError("FAIL-LOUD: harvest_date returned 0 items for a date known to have 7 cases -- "
                            "site down or scrape broke, not a real zero. Aborting, no writes made.")

    by_norm_case = {}
    for it in items:
        cn = norm_case_number(it.get("case_number"))
        if cn:
            by_norm_case[cn] = it

    patched = []
    skipped = []
    card_backfilled = []
    for row in mca_rows:
        cn = norm_case_number(row["case_number"])
        if cn not in by_norm_case:
            print(f"  NO MATCH on live calendar for {row['case_number']} -- SKIP (not stamping)")
            skipped.append(row["id"])
            continue
        item = by_norm_case[cn]

        # Cross-check key: parcel_id (property_address unreliable here -- one
        # gap row is "NO ADDRESS ON TAX ROLL" on both sides, which would
        # trivially "match" as equal strings but isn't a meaningful litmus).
        db_pid = norm_parcel_id(row.get("parcel_id"))
        live_pid = norm_parcel_id(item.get("parcel_id"))
        pid_ok = bool(db_pid) and bool(live_pid) and db_pid == live_pid
        print(f"  MATCH {row['case_number']}: db_parcel='{row.get('parcel_id')}' live_parcel='{item.get('parcel_id')}' parcel_match={pid_ok} aid={item.get('aid')}")

        if not pid_ok:
            print(f"    SKIP (parcel_id mismatch, not marking matched_clean)")
            skipped.append(row["id"])
            continue

        parity_source = f"tier1:santa_rosa_cd_parity_taxdeed_20261005:{item['aid']}:{AUCTION_DATE}"
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": parity_source,
                        "parity_checked_at": "now()"})
            patched.append(row["id"])
            print(f"    PATCHED parity_status=matched_clean parity_source={parity_source}")
        except Exception as e:
            print(f"    PATCH FAILED for {row['id']} ({row['case_number']}): {e}")
            skipped.append(row["id"])
            continue

        # Opportunistic NULL-only backfill of assessed_value, consistent with
        # prior sessions' pattern (does not affect C/D, purely additive).
        patch_body = {}
        if not row.get("assessed_value") and item.get("assessed_value"):
            patch_body["assessed_value"] = item["assessed_value"]
        if patch_body:
            try:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                card_backfilled.append(row["id"])
                print(f"    also backfilled {list(patch_body.keys())}")
            except Exception as e:
                print(f"    card patch FAILED for {row['id']}: {e}")

    print(f"\nTOTALS: parsed={n_parsed} parity_promoted={len(patched)} skipped={len(skipped)} card_backfilled={len(card_backfilled)}")
    if n_parsed > 0 and len(patched) == 0:
        raise RuntimeError(f"Silent failure: {n_parsed} items parsed but 0 rows patched. Aborting with non-zero exit.")

    remaining = rest_get(f"multi_county_auctions?county=eq.{COUNTY}&parity_status=is.null&select=id")
    print(f"remaining NULL-parity rows after run (county-wide): {len(remaining)}")


if __name__ == "__main__":
    main()
