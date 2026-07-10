#!/usr/bin/env python3
"""SHARD-6 run3645 flagler C/D backfill via flagler.realtdm.com public case search.

Reuses the live-source discovery from SHARD-9 run3534 (2026-07-10, session report
SHARD9_RUN3534_BAY_STJOHNS_FLAGLER_MADISON_SESSION_REPORT.md): flaglerclerk.gov links
to https://flagler.realtdm.com/public/cases/list, a public no-login RealTDM case-search
portal. POSTing filterCaseNumber against the real HTML <form id="caseFiltersForm">
(action=public/cases/list, fields filterPageNumber/filterFiltered/sectionRouteCode/
isPublic/filterCaseNumber) returns the case card server-rendered (no JS execution
needed) with CASE #, status, Parcel Number, Sale Date.

That session closed 2 of 15 unmatched cases (25-027/25-028 TDC, both "Active - Sold
Bidder") and correctly left 3 "Completed - Redeemed" cases NULL (legitimate non-sale,
not a matcher gap). This run targets the remaining 10 unmatched flagler rows, all
auction_date=2026-08-11 (upcoming, case_status not yet known at brief time).

Match rule: parity_status -> matched_clean ONLY if the live case card's own
Parcel Number matches our row's existing parcel_id exactly (independent field
corroboration, not just case-number presence) -- same standard as the tier1 AJAX
matchers used fleet-wide (shard2/shard9/shard14).

Idempotent: skips rows already parity_status=matched_clean with a tier1 source.
DB writes via PostgREST only (direct pooler confirmed stale, per every prior
shard8/9/13/14 session finding).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE = "https://flagler.realtdm.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
RUN_LABEL = "tier1:shard6_run3645_flagler_realtdm_case_search:2026-07-10"


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


def search_case(op, case_number_short):
    """case_number_short: the numeric/short form realtdm indexes on, e.g. '26-029'
    (our DB stores the full '26-029 TDC' form; realtdm's own filter matches on the
    short prefix and returns the full case card)."""
    data = urllib.parse.urlencode({
        "filterPageNumber": "1", "filterFiltered": "1", "sectionRouteCode": "",
        "isPublic": "1", "filterCaseNumber": case_number_short,
    }).encode()
    req = urllib.request.Request(
        BASE + "/public/cases/list", data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                 "Referer": BASE + "/public/cases/list"})
    with op.open(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", "ignore")

    cards = []
    for blk in html.split('data-caseid="')[1:]:
        case_m = re.search(r"CASE #([^<]+)<", blk)
        status_m = re.search(r'opacity-75">([^<]+)<', blk)
        parcel_m = re.search(r"Parcel Number</div>\s*<div class=\"data-value text-end\">([^<]*)<", blk)
        sale_m = re.search(r"Sale Date</div>\s*<div class=\"data-value text-end\">([^<]*)<", blk)
        if not case_m:
            continue
        cards.append({
            "case_number": case_m.group(1).strip(),
            "status": (status_m.group(1).strip() if status_m else ""),
            "parcel_number": re.sub(r"\D", "", parcel_m.group(1)) if parcel_m else "",
            "sale_date": sale_m.group(1).strip() if sale_m else "",
        })
    return cards


def main():
    rows = rest_get(
        "multi_county_auctions?county=eq.flagler&parity_status=is.null"
        "&select=id,case_number,parcel_id,auction_date,auction_status")
    print(f"unmatched flagler rows: {len(rows)}")

    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(urllib.request.Request(BASE + "/public/cases/list", headers={"User-Agent": UA}), timeout=30).read()

    promoted = []
    excluded = []
    not_found = []
    for row in rows:
        cn = row["case_number"]  # e.g. "26-029 TDC"
        short = cn.split()[0]  # "26-029"
        try:
            cards = search_case(op, short)
        except Exception as e:
            print(f"  SEARCH FAIL {cn}: {e}")
            time.sleep(1.0)
            continue
        match = next((c for c in cards if c["case_number"] == cn), None)
        if not match:
            not_found.append(cn)
            print(f"  {cn}: NOT FOUND on live realtdm case search")
            time.sleep(0.6)
            continue

        our_parcel = re.sub(r"\D", "", row.get("parcel_id") or "")
        their_parcel = match["parcel_number"]
        if not our_parcel or not their_parcel or our_parcel != their_parcel:
            excluded.append((cn, match["status"], "parcel_mismatch_or_missing",
                              our_parcel, their_parcel))
            print(f"  {cn}: status={match['status']!r} parcel MISMATCH ours={our_parcel!r} theirs={their_parcel!r} -- NOT promoted")
            time.sleep(0.6)
            continue

        status_lower = match["status"].lower()
        if "redeem" in status_lower:
            # legitimate non-sale outcome, same rule SHARD-9 run3534 applied -- leave NULL
            excluded.append((cn, match["status"], "redeemed_non_sale", our_parcel, their_parcel))
            print(f"  {cn}: status={match['status']!r} -- redeemed, legitimately excluded (not promoted)")
            time.sleep(0.6)
            continue

        try:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}",
                       {"parity_status": "matched_clean", "parity_source": RUN_LABEL})
            promoted.append((cn, match["status"]))
            print(f"  {cn}: status={match['status']!r} parcel CONFIRMED -> matched_clean")
        except Exception as e:
            print(f"  PATCH FAIL {cn}: {e}")
        time.sleep(0.6)

    print(f"\nTOTALS: promoted={len(promoted)} excluded={len(excluded)} not_found={len(not_found)}")
    for cn, st in promoted:
        print(f"  PROMOTED {cn} ({st})")
    for cn, st, reason, op_, tp in excluded:
        print(f"  EXCLUDED {cn} ({st}) reason={reason} ours={op_} theirs={tp}")
    for cn in not_found:
        print(f"  NOT_FOUND {cn}")

    if len(rows) > 0 and not promoted and not excluded and not not_found:
        raise RuntimeError("Silent failure: rows present but zero outcomes recorded")


if __name__ == "__main__":
    main()
