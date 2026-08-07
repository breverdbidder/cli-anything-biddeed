#!/usr/bin/env python3
"""GOLD STANDARD shard-5 marion, dispatch 9e12d062.

C/D-fail diagnosis (verified live this session): 32 marion rows in the
evaluator's population (lower(county)='marion' AND (data_source<>'propertyonion'
OR tier1_authoritative=true)) are NOT parity_status='matched_clean' with a
tier1% parity_source. All 32 already carry a real, scraped parcel_id/address/
assessed_value (not placeholder) except 2 rows carrying the 'MULTIPLE PARCELS'
string, which are already matched_clean via a non-tier1 source
(realforeclose_aids_patch) and are left untouched here (cannot honestly be
labeled tier1 -- reported as residual).

Of the remaining 30:
  - 24 are sale_type=foreclosure, auction_date 2026-07-23..2026-08-10. Live
    re-harvested via the marion.realforeclose.com AJAX endpoint (reusing
    scripts/shard2_run2450_ajax_realforeclose_harvest.py verbatim, same
    mechanism that wrote the existing 'tier1_realforeclose_ajax_marion' /
    'tier1_realforeclose_marion' PASS rows) across every distinct auction_date
    present in the 24-row set. All 24 case_numbers were found live with an
    EXACT parcel_id match against the DB value already on the row -- zero
    mismatches. Promoted to parity_status='matched_clean',
    parity_source='tier1_realforeclose_ajax_marion_shard5_9e12d062'.
  - 6 are sale_type=tax_deed, auction_date 2026-07-22. Live re-harvested via
    marion.realtaxdeed.com (same script, platform_domain='realtaxdeed.com').
    4 of 6 (208092021, 210332021, 235122021, 248122021) were found live with
    an exact parcel_id match -- promoted to parity_status='matched_clean',
    parity_source='tier1_realtaxdeed_marion_shard5_9e12d062'.
    2 of 6 (219282021, 219342021) were NOT found on the live 2026-07-22
    calendar (checked, also not on adjacent dates 07/20-07/24) -- these cases
    appear to have been withdrawn/redeemed/cancelled from the live auction
    calendar since their original scrape (created_at 2026-07-24). Left
    UNTOUCHED, reported as residual gap. No fabrication.

Idempotent: only patches rows not already tier1-labeled matched_clean; only
touches rows whose live-harvested parcel_id exactly matches the existing
DB parcel_id (never overwrites with a different value, never invents one).

Usage: python3 scripts/gold_standard_shard5_marion_cd_parity_fix_9e12d062.py
"""
import os
import json
import time
import importlib.util
import urllib.request
import urllib.error

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "marion"

FC_DATES = ["07/23/2026", "07/27/2026", "07/28/2026", "07/29/2026", "07/30/2026",
            "08/03/2026", "08/04/2026", "08/05/2026", "08/06/2026", "08/08/2026",
            "08/10/2026"]
TD_DATES = ["07/22/2026"]

FC_PARITY_SOURCE = "tier1_realforeclose_ajax_marion_shard5_9e12d062"
TD_PARITY_SOURCE = "tier1_realtaxdeed_marion_shard5_9e12d062"


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def harvest_all(dates, platform_domain):
    by_cn = {}
    for d in dates:
        try:
            items = _mod.harvest_date(COUNTY, COUNTY, d, platform_domain=platform_domain)
        except Exception as e:
            print(f"  HARVEST FAIL {platform_domain} {d}: {e}")
            continue
        for it in items:
            cn = it.get("case_number")
            if cn:
                by_cn[cn] = it
        time.sleep(0.3)
    return by_cn


def main():
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        f"&select=id,case_number,sale_type,auction_date,parity_status,parity_source,parcel_id"
    )
    # PostgREST neq-on-null gap (documented precedent in
    # gold_standard_shard9_marion_j_generator.py) -- also fetch data_source IS NULL rows.
    mca_rows_null_ds = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&data_source=is.null&tier1_authoritative=eq.true"
        f"&select=id,case_number,sale_type,auction_date,parity_status,parity_source,parcel_id"
    )
    seen_ids = {r["id"] for r in mca_rows}
    for r in mca_rows_null_ds:
        if r["id"] not in seen_ids:
            mca_rows.append(r)
            seen_ids.add(r["id"])

    target = [r for r in mca_rows
              if not (r.get("parity_status") == "matched_clean"
                      and (r.get("parity_source") or "").startswith("tier1"))]
    print(f"{COUNTY}: {len(mca_rows)} in population, {len(target)} not tier1-matched_clean")

    fc_targets = [r for r in target if r["sale_type"] == "foreclosure" and r.get("parcel_id") and r["parcel_id"] != "MULTIPLE PARCELS"]
    td_targets = [r for r in target if r["sale_type"] == "tax_deed" and r.get("parcel_id") and r["parcel_id"] != "MULTIPLE PARCELS"]
    skipped_placeholder = [r for r in target if r.get("parcel_id") == "MULTIPLE PARCELS"]
    skipped_no_parcel = [r for r in target if not r.get("parcel_id")]

    print(f"  fc_targets={len(fc_targets)} td_targets={len(td_targets)} "
          f"skipped_placeholder={len(skipped_placeholder)} skipped_no_parcel={len(skipped_no_parcel)}")

    live_fc = harvest_all(FC_DATES, "realforeclose.com")
    live_td = harvest_all(TD_DATES, "realtaxdeed.com")
    print(f"  live_fc harvested {len(live_fc)} unique case_numbers")
    print(f"  live_td harvested {len(live_td)} unique case_numbers")

    promoted = []
    mismatched = []
    not_found = []

    for r in fc_targets:
        cn = r["case_number"]
        item = live_fc.get(cn)
        if not item:
            not_found.append(cn)
            continue
        if str(item.get("parcel_id")) != str(r["parcel_id"]):
            mismatched.append((cn, r["parcel_id"], item.get("parcel_id")))
            continue
        rest_patch(f"multi_county_auctions?id=eq.{r['id']}",
                   {"parity_status": "matched_clean", "parity_source": FC_PARITY_SOURCE})
        promoted.append(cn)

    for r in td_targets:
        cn = r["case_number"]
        item = live_td.get(cn)
        if not item:
            not_found.append(cn)
            continue
        if str(item.get("parcel_id")) != str(r["parcel_id"]):
            mismatched.append((cn, r["parcel_id"], item.get("parcel_id")))
            continue
        rest_patch(f"multi_county_auctions?id=eq.{r['id']}",
                   {"parity_status": "matched_clean", "parity_source": TD_PARITY_SOURCE})
        promoted.append(cn)

    print(f"\nPROMOTED: {len(promoted)} -> {promoted}")
    print(f"NOT_FOUND_LIVE (residual, untouched): {len(not_found)} -> {not_found}")
    print(f"MISMATCHED (residual, untouched -- would require overwrite): {len(mismatched)} -> {mismatched}")
    print(f"SKIPPED_PLACEHOLDER (MULTIPLE PARCELS, non-tier1, untouched): "
          f"{len(skipped_placeholder)} -> {[r['case_number'] for r in skipped_placeholder]}")
    print(f"SKIPPED_NO_PARCEL: {len(skipped_no_parcel)} -> {[r['case_number'] for r in skipped_no_parcel]}")


if __name__ == "__main__":
    main()
