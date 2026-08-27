#!/usr/bin/env python3
"""Highlands C/D FIX phase (Gold Standard dispatch 8f944a71, 2026-08-27).

Re-runs a live RealAuction harvest for the 24 highlands rows whose
auction_date has now passed (08-18, 08-19, 08-26) that were previously
labeled parity_source='shard8_run6046_litmus_fallback:...' -- a label a
prior session applied WITHOUT independently confirming redemption/
cancellation against any real clerk source (see diagnose pass, confirmed
this session). Also probes 25000681GCAXMX (PHANTOM_NOT_ON_CLERK, no
parcel/address on file, auction_date 2026-08-26, also past) to see if a
real record now exists.

25000402GCAXMX (auction_date 2026-09-02) is intentionally NOT targeted --
still 6 days in the future as of today, not yet expected to be final.

Reuses harvest_date()/parse_aitem_blocks() VERBATIM from
scripts/shard2_run2450_ajax_realforeclose_harvest.py per SEARCH-FIRST
MANDATE -- no reimplementation. Matching is exact case_number string
equality (light normalization strip of non-alphanumerics) only --
BLANK > WRONG, no fuzzy/parcel-only matching.

Uses PostgREST GET/PATCH exclusively (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
since the Postgres pooler and rpc/exec_sql are both dead this session.
"""
import os
import re
import sys
import json
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shard2_run2450_ajax_realforeclose_harvest import harvest_date  # noqa: E402

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

LABEL_PREFIX = "tier1:gold_standard_8f944a71_highlands_cd_repast_harvest"


def norm_case_number(cn):
    return re.sub(r"[^A-Z0-9]", "", (cn or "").upper())


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body, timeout=90):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


TARGETS = [
    {"sale_type": "foreclosure", "auction_date": "2026-08-18", "platform_domain": "realforeclose.com"},
    {"sale_type": "foreclosure", "auction_date": "2026-08-19", "platform_domain": "realforeclose.com"},
    {"sale_type": "foreclosure", "auction_date": "2026-08-26", "platform_domain": "realforeclose.com"},
    {"sale_type": "tax_deed", "auction_date": "2026-08-26", "platform_domain": "realtaxdeed.com"},
]


def main():
    total_parsed = 0
    total_matched = []
    still_unlisted = []

    for t in TARGETS:
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        platform = t["platform_domain"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"

        gap_rows = rest_get(
            f"multi_county_auctions?county=eq.highlands&auction_date=eq.{ad}"
            f"&sale_type=eq.{sale_type}"
            f"&parity_source=like.shard8_run6046_litmus_fallback*"
            f"&select=id,case_number,parity_status,parity_source")
        # Also fold in the no-data PHANTOM row for foreclosure 08-26.
        if sale_type == "foreclosure" and ad == "2026-08-26":
            phantom = rest_get(
                f"multi_county_auctions?county=eq.highlands&auction_date=eq.{ad}"
                f"&sale_type=eq.{sale_type}&parity_status=eq.PHANTOM_NOT_ON_CLERK"
                f"&select=id,case_number,parity_status,parity_source")
            gap_rows.extend(phantom)

        if not gap_rows:
            print(f"highlands {sale_type} {ad}: no target rows in DB (skip)")
            continue

        try:
            items = harvest_date("highlands", "highlands", mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"HARVEST FAIL highlands {sale_type} {ad}: {e}")
            still_unlisted.extend(r["case_number"] for r in gap_rows)
            continue

        total_parsed += len(items)
        print(f"highlands {platform} {ad}: live items parsed = {len(items)} "
              f"(db target rows for this date = {len(gap_rows)})")

        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        date_matches = []
        for row in gap_rows:
            cn = norm_case_number(row["case_number"])
            if cn in by_norm:
                date_matches.append((row, by_norm[cn]))
            else:
                still_unlisted.append(row["case_number"])

        if date_matches:
            id_filter = ",".join(str(r["id"]) for r, _ in date_matches)
            parity_source = f"{LABEL_PREFIX}:{sale_type}:{ad}"
            rest_patch(f"multi_county_auctions?id=in.({id_filter})",
                       {"parity_status": "matched_clean", "parity_source": parity_source})
            total_matched.extend((r["case_number"], parity_source) for r, _ in date_matches)
            print(f"  -> matched+promoted {len(date_matches)}: "
                  f"{[r['case_number'] for r, _ in date_matches]}")
        else:
            print(f"  -> 0 exact case_number matches against live calendar "
                  f"(live calendar {'is empty' if not items else 'has different case numbers'} "
                  f"for this date)")

        time.sleep(0.4)

    print(f"\nTOTAL live items parsed across all target dates = {total_parsed}")
    print(f"TOTAL matched_and_promoted = {len(total_matched)}")
    for cn, src in total_matched:
        print(f"  MATCHED {cn} -> {src}")
    print(f"TOTAL still not-yet-listed / no match on live calendar = {len(still_unlisted)}")
    print("STILL UNMATCHED case_numbers:", still_unlisted)


if __name__ == "__main__":
    main()
