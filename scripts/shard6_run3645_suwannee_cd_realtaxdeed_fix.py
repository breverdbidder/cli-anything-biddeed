#!/usr/bin/env python3
"""SHARD-6 run3645 suwannee C/D backfill via live suwannee.realtaxdeed.com AJAX calendar.

Reuses the proven RealForeclose/RealTaxDeed AJAX harvester
(scripts/shard2_run2450_ajax_realforeclose_harvest.py harvest_date(), same
mechanism verified fleet-wide for pinellas/santa_rosa/miami_dade/seminole). Suwannee
has 9 total auctions, all tax_deed, all upcoming, auction_date=2026-08-06; live
harvest against suwannee.realtaxdeed.com for that date returns 8 items including
all 7 currently-unmatched case numbers, each with a parcel_id that exact-matches
our stored parcel_id (independent field corroboration, not just case-number
presence).

Idempotent: only patches parity when not already tier1-labeled matched_clean.
DB writes via PostgREST only (direct pooler confirmed stale, per fleet-wide
findings this run).
"""
import importlib.util
import json
import os
import re
import time
import urllib.request

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "harvester", os.path.join(_here, "shard2_run2450_ajax_realforeclose_harvest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
COUNTY = "suwannee"
RUN_LABEL = "tier1:shard6_run3645_suwannee_realtaxdeed_ajax:tax_deed:2026-08-06"


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
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    items = _mod.harvest_date("suwannee", COUNTY, "08/06/2026", platform_domain="realtaxdeed.com")
    print(f"live harvest items: {len(items)}")
    by_case = {re.sub(r'\D', '', it.get('case_number') or ''): it for it in items if it.get('case_number')}

    rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&parity_status=is.null"
        f"&select=id,case_number,parcel_id,auction_date,sale_type")
    print(f"unmatched {COUNTY} rows: {len(rows)}")

    promoted, mismatched, not_found = [], [], []
    for row in rows:
        cn_key = re.sub(r'\D', '', row["case_number"] or '')
        item = by_case.get(cn_key)
        if not item:
            not_found.append(row["case_number"])
            continue
        our_parcel = re.sub(r'\D', '', row.get("parcel_id") or "")
        their_parcel = re.sub(r'\D', '', item.get("parcel_id") or "")
        if not our_parcel or not their_parcel or our_parcel != their_parcel:
            mismatched.append((row["case_number"], our_parcel, their_parcel))
            continue
        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": RUN_LABEL})
            promoted.append(row["case_number"])
            print(f"  {row['case_number']}: parcel CONFIRMED {our_parcel} -> matched_clean")
        except Exception as e:
            print(f"  PATCH FAIL {row['case_number']}: {e}")
        time.sleep(0.3)

    print(f"\nTOTALS: promoted={len(promoted)} mismatched={len(mismatched)} not_found={len(not_found)}")
    for cn, op_, tp in mismatched:
        print(f"  MISMATCH {cn} ours={op_} theirs={tp}")
    for cn in not_found:
        print(f"  NOT_FOUND {cn}")

    if len(rows) > 0 and not promoted and not mismatched and not not_found:
        raise RuntimeError("Silent failure: rows present but zero outcomes recorded")


if __name__ == "__main__":
    main()
