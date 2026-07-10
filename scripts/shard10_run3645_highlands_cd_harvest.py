#!/usr/bin/env python3
"""Highlands C/D fresh-attempt harvest (SHARD-10 run 3645, 2026-07-10).

Highlands sits at C=D=82.1%% (147/179) with 22 rows carrying parity_status IN
('mca_only','bootstrap_placeholder') -- 20 tax_deed rows dated 2026-08-05/2026-08-12
(case numbers 25000685-25000721 range) plus 2 foreclosure bootstrap placeholders
(HIGHLANDS-FC-2026-001 dated 2026-08-02, HIGHLANDS-FC-2026-002 dated 2026-08-17).

Prior sessions (shard4_run3059, shard12_run3534) already attempted a live harvest
against these same dates and found nothing published yet on RealAuction's calendar
(too far out at the time). Today is 2026-07-10 -- the 2026-08-02 date is now within
~3 weeks and 08-05/08-12 within ~4-5 weeks, so RealAuction may have since published
listings (calendars commonly populate ~30 days out). This script re-attempts the
exact same proven AJAX harvest mechanism for those specific dates only.

Reuses harvest_date()/parse_aitem_blocks() VERBATIM from
scripts/shard2_run2450_ajax_realforeclose_harvest.py (same proven AJAX mechanism) per
the SEARCH-FIRST MANDATE -- no reimplementation.

Matching: exact case_number string equality only (after light normalization strip of
non-alphanumerics) against the known unmatched case numbers already loaded from the DB
via PostgREST GET. No fuzzy/parcel-only matching -- BLANK > WRONG.

Uses PostgREST GET/PATCH exclusively (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY) since
the Postgres pooler and rpc/exec_sql are both dead this session.
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


# The 22 rows currently mca_only / bootstrap_placeholder for highlands, grouped by
# (sale_type, auction_date) exactly as they exist in multi_county_auctions today.
TARGETS = [
    {"county": "highlands", "sale_type": "tax_deed", "auction_date": "2026-08-05",
     "platform_domain": "realtaxdeed.com"},
    {"county": "highlands", "sale_type": "tax_deed", "auction_date": "2026-08-12",
     "platform_domain": "realtaxdeed.com"},
    {"county": "highlands", "sale_type": "foreclosure", "auction_date": "2026-08-02",
     "platform_domain": "realforeclose.com"},
]

LABEL_PREFIX = "shard10_run3645_highlands_ajax_harvest"


def main():
    total_parsed = 0
    total_matched = []
    still_unlisted = []

    for t in TARGETS:
        county = t["county"]
        sale_type = t["sale_type"]
        ad = t["auction_date"]
        platform = t["platform_domain"]
        y, m, d = ad.split("-")
        mmddyyyy = f"{m}/{d}/{y}"

        # Rows currently mca_only/bootstrap_placeholder for this exact county+auction_date.
        mca_rows = rest_get(
            f"multi_county_auctions?county=eq.{county}&auction_date=eq.{ad}"
            f"&sale_type=eq.{sale_type}"
            f"&parity_status=in.(mca_only,bootstrap_placeholder)"
            f"&select=id,case_number,parity_status,parity_source")
        if not mca_rows:
            print(f"{county} {sale_type} {ad}: no unmatched rows in DB for this date (skip)")
            continue

        try:
            items = harvest_date(county, county, mmddyyyy, platform_domain=platform)
        except Exception as e:
            print(f"HARVEST FAIL {county} {sale_type} {ad}: {e}")
            still_unlisted.extend(r["case_number"] for r in mca_rows)
            continue

        total_parsed += len(items)
        print(f"highlands {platform} {ad}: live calendar items parsed = {len(items)} "
              f"(db unmatched rows for this date = {len(mca_rows)})")

        by_norm = {}
        for it in items:
            cn = norm_case_number(it.get("case_number"))
            if cn:
                by_norm[cn] = it

        date_matches = []
        for row in mca_rows:
            cn = norm_case_number(row["case_number"])
            if cn in by_norm:
                date_matches.append(row)
            else:
                still_unlisted.append(row["case_number"])

        if date_matches:
            id_filter = ",".join(str(r["id"]) for r in date_matches)
            parity_source = f"tier1:{LABEL_PREFIX}:{sale_type}:{ad}"
            rest_patch(f"multi_county_auctions?id=in.({id_filter})",
                       {"parity_status": "matched_clean", "parity_source": parity_source})
            total_matched.extend((r["case_number"], parity_source) for r in date_matches)
            print(f"  -> matched+promoted {len(date_matches)}: "
                  f"{[r['case_number'] for r in date_matches]}")
        else:
            print(f"  -> 0 exact case_number matches against live calendar "
                  f"(live calendar {'is empty' if not items else 'has different case numbers'} "
                  f"for this date)")

        time.sleep(0.4)

    print(f"\nTOTAL live items parsed across all target dates = {total_parsed}")
    print(f"TOTAL matched_and_promoted = {len(total_matched)}")
    for cn, src in total_matched:
        print(f"  MATCHED {cn} -> {src}")
    print(f"TOTAL still not-yet-listed on live calendar = {len(still_unlisted)}")
    print("STILL UNLISTED case_numbers:", still_unlisted)

    if total_parsed > 0 and len(total_matched) == 0:
        raise RuntimeError(
            f"Silent failure check: {total_parsed} live calendar items parsed but 0 "
            f"matched to multi_county_auctions -- investigate case_number format before "
            f"assuming 'not listed yet'.")


if __name__ == "__main__":
    main()
