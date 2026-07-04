#!/usr/bin/env python3
"""
realTDM harvester — SHARD-3 run2886 (2026-07-04)

RealAuction has migrated several FL counties' tax-deed case management off the
legacy {county}.realtaxdeed.com CFML subdomain onto a new platform:
{county}.realtdm.com/public/cases/list -- a public, clerk-of-court-branded
case-search portal (verified live for charlotte, highlands, liberty, manatee,
volusia on 2026-07-04; see public.realauction_subdomains sale_type='tdm' rows,
last_verified 2026-06-18, for the full fleet-wide discovery list).

This script is READ-ONLY. It fetches a county's live case list and reports:
  - liveness of {county}.realtdm.com
  - total real (non-propertyonion) auctions in multi_county_auctions
  - how many of those case_numbers exist in the realtdm portal with an exact
    parcel_id match (evidence the listing is real -- useful for A/E work)
  - how many realtdm cases do NOT yet exist in multi_county_auctions at all
    (candidates for an A-criterion tax_deed coverage backfill, IF the county
    is missing that sale_type entirely -- see the manatee migration this
    session for a worked, hand-enriched example)

It never writes to the database. An earlier version of this script had an
--apply-parity flag that tagged exact case+parcel matches as tier1_ C/D
litmus confirmations; an ULTRALOOP adversarial refuter correctly rejected
that on 2026-07-04 (existence-in-docket is not the same as independent
OUTCOME verification, which is what every other tier1_ source in this table
represents -- see supabase/migrations/20260704_shard3_manatee_realtdm_tax_deed_backfill.sql
for the full writeup). The flag was removed rather than left as a footgun.

Usage:
  python3 scripts/realtdm_harvester.py --county highlands
  python3 scripts/realtdm_harvester.py --county manatee
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}Z] {msg}", flush=True)


def sb_headers(extra=None):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def sb_get(table, params):
    rows, offset = [], 0
    while True:
        q = dict(params)
        q["limit"] = 1000
        q["offset"] = offset
        url = f"{SUPABASE_URL}/rest/v1/{table}?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(url, headers=sb_headers())
        data = json.loads(urllib.request.urlopen(req, timeout=30).read())
        rows.extend(data)
        if len(data) < 1000:
            break
        offset += 1000
    return rows


def fetch_realtdm_cases(county, max_pages=6):
    """POST to {county}.realtdm.com/public/cases/list, paginate until a page
    comes back below the empty-state size threshold."""
    host = f"https://{county}.realtdm.com"
    cj_url = f"{host}/public/cases/list"
    cases = []
    for page in range(1, max_pages + 1):
        data = urllib.parse.urlencode({
            "filterPageNumber": page, "filterFiltered": 1, "isPublic": 1,
            "filterSaleDateStart": "01/01/2015", "filterSaleDateStop": "12/31/2026",
            "filterCasesPerPage": 500,
        }).encode()
        req = urllib.request.Request(cj_url, data=data, method="POST",
                                      headers={"Content-Type": "application/x-www-form-urlencoded",
                                               "User-Agent": UA})
        try:
            html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as e:
            log(f"  {host} page {page}: unreachable ({e})")
            break
        tbl = html.find('<table class="table public">')
        if tbl < 0:
            break
        rows = html[tbl:].split('<tr class="link load-case"')[1:]
        if not rows:
            break
        page_cases = []
        for r in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)
            if len(tds) < 6:
                continue
            status = re.findall(r'<div>([^<]*)</div>', tds[0])[-1] if tds[0] else None
            case_num = re.sub('<.*?>', '', tds[1]).strip()
            parcel = tds[4].strip()
            sale_date = tds[5].strip()
            page_cases.append({"status": status, "case": case_num, "parcel": parcel, "sale_date": sale_date})
        cases.extend(page_cases)
        if len(rows) < 400:  # short page -> last page
            break
        time.sleep(0.5)
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", required=True)
    args = ap.parse_args()
    county = args.county.lower()

    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY not set — cannot query database")
        sys.exit(1)

    log(f"=== realTDM harvester — {county.upper()} ===")
    live_cases = fetch_realtdm_cases(county)
    log(f"realtdm live case list: {len(live_cases)} rows")
    if not live_cases:
        log(f"{county}.realtdm.com returned no case data — not live/populated for this county")
        return

    mca = sb_get("multi_county_auctions",
                 {"county": f"eq.{county}", "case_number": "not.like.PO-*",
                  "select": "id,case_number,parcel_id,parity_status,parity_source,sale_type"})
    log(f"multi_county_auctions (real, non-propertyonion): {len(mca)} rows")

    by_case = {c["case"]: c for c in live_cases if c["case"]}
    exact_matches = 0
    for m in mca:
        t = by_case.get(m["case_number"])
        if not t:
            continue
        if m["parcel_id"] and t["parcel"] and m["parcel_id"] == t["parcel"]:
            exact_matches += 1

    new_cases_not_in_mca = len(by_case) - sum(1 for m in mca if m["case_number"] in by_case)
    log(f"exact case+parcel matches against our existing rows: {exact_matches}")
    log(f"realtdm cases with no corresponding multi_county_auctions row at all: {new_cases_not_in_mca}")
    log("This is a reporting tool only. A case+parcel match against a clerk "
        "docket confirms the LISTING is real (useful evidence for A/E work and "
        "for sourcing new auction rows by hand, per the manatee migration this "
        "session) -- it does NOT by itself qualify as a tier1_ independent "
        "OUTCOME verification for C/D (an ULTRALOOP adversarial refuter caught "
        "this distinction live on 2026-07-04; see "
        "supabase/migrations/20260704_shard3_manatee_realtdm_tax_deed_backfill.sql). "
        "Do not auto-write parity_status from this script.")


if __name__ == "__main__":
    main()
