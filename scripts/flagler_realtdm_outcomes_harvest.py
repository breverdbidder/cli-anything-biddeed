#!/usr/bin/env python3
"""Flagler tax-deed outcome harvest via flagler.realtdm.com public portal.

Root cause fixed: criteria B/F for flagler were FAIL because closed
tax_deed auctions (auction_status IN ('sold','completed')) had
multi_county_auctions.sold_amount = NULL for all 30 rows, and zero
corresponding rows existed in public.tax_deed_outcomes. This script
independently harvests the REAL winning bid + winner name per case from
flagler.realtdm.com (a public, no-login RealTDM tax-deed portal; same
platform family as scripts/realtdm_county_sweep.py, but that script only
captures the case-list card, which does NOT include a sale dollar figure).

Discovered 2026-07-23: the case-list card (POST /public/cases/list) gives
status/dates/parcel/surplus only. The authoritative winning-bid dollar
figure lives in the "Fees" AJAX tab of the case-details view:
  POST /public/cases/dspFees   body: caseID=<id>&pageNum=1&control=
  -> text field "Winning Bid" under "Post Auction Case Fees"
Cross-checked arithmetic on case 25-002 TDC (caseID 80365):
  Winning Bid $4,100.00 - Statutory (Opening) Bid $2,276.01 = $1,823.99
  which exactly matches "Surplus To Disburse" on the Disbursements tab.
Winner name comes from POST /public/cases/dspCaseParties, party type
"WINNING BIDDER".

Flow per case_number:
  1. POST /public/cases/list with filterCaseNumber=<short case #> to resolve
     data-caseID and cross-check the case-list status string.
  2. POST /public/cases/dspFees with caseID -> parse "Winning Bid" $ amount
     (and "Statutory (Opening) Bid" as opening_bid).
  3. POST /public/cases/dspCaseParties with caseID -> parse WINNING BIDDER
     party name (may be absent if county retained / no 3rd-party bidder).
  4. POST /public/cases/dspCaseSummary with caseID -> property address.

Writes to public.tax_deed_outcomes (INSERT, data_source=
'flagler_realtdm:FLAGLER-TD-V1') for every case where a real "Winning Bid"
figure was found. Does NOT write multi_county_auctions.sold_amount directly
(promote_tier1_from_outcomes RPC handles that promotion path per project
convention).

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
Usage: python3 scripts/flagler_realtdm_outcomes_harvest.py [--dry-run]
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

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE = "https://flagler.realtdm.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
DATA_SOURCE = "flagler_realtdm:FLAGLER-TD-V1"
DRY_RUN = "--dry-run" in sys.argv


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def post(op, path, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded",
                 "Referer": BASE + "/public/cases/details"})
    with op.open(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


def money(s):
    if s is None:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def find_case_id(op, case_number_full):
    short = case_number_full.split()[0]
    html = post(op, "/public/cases/list", {
        "filterPageNumber": "1", "filterFiltered": "1", "sectionRouteCode": "",
        "isPublic": "1", "filterCaseNumber": short,
    })
    for blk in html.split('data-caseID="')[1:]:
        cid_m = re.match(r"(\d+)", blk)
        case_m = re.search(r"CASE #([^<]+)<", blk)
        status_m = re.search(r'opacity-75">([^<]+)<', blk)
        if case_m and case_m.group(1).strip() == case_number_full and cid_m:
            return cid_m.group(1), (status_m.group(1).strip() if status_m else None)
    return None, None


def get_fees(op, case_id):
    html = post(op, "/public/cases/dspFees", {"caseID": case_id, "pageNum": "1", "control": ""})
    text = re.sub("<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    wb_m = re.search(r"Winning Bid \$([\d,]+\.\d{2})", text)
    ob_m = re.search(r"Statutory \(Opening\) Bid \$([\d,]+\.\d{2})", text)
    return money(wb_m.group(1) if wb_m else None), money(ob_m.group(1) if ob_m else None)


def get_winner(op, case_id):
    html = post(op, "/public/cases/dspCaseParties", {"caseID": case_id, "pageNum": "1", "control": ""})
    # match the desktop <table> rows: name in <span class="text-black">, type in following div
    for m in re.finditer(
        r'<span class="text-black">([^<]+)</span>\s*<div class="text-dark mt-1">([^<]+)</div>', html):
        name, ptype = m.group(1).strip(), m.group(2).strip()
        if ptype.upper() == "WINNING BIDDER":
            return re.sub(r"\s+", " ", name)
    return None


def get_address_parcel(op, case_id):
    html = post(op, "/public/cases/dspCaseSummary", {"caseID": case_id, "pageNum": "1", "control": ""})
    addr_m = re.search(
        r'Property Address</div>\s*<div class="data-value text-end">\s*([^<]+)<br/>\s*([^<]+)', html)
    address = None
    if addr_m:
        address = f"{addr_m.group(1).strip()}, {addr_m.group(2).strip()}"
    return address


def main():
    rows = rest_get(
        "multi_county_auctions?county=eq.flagler&sale_type=eq.tax_deed"
        "&auction_status=in.(sold,completed)"
        "&select=id,case_number,parcel_id,auction_date,auction_status")
    print(f"target flagler tax_deed sold/completed rows: {len(rows)}")
    if not rows:
        print("FAIL-LOUD: zero target rows found, expected 30")
        sys.exit(1)

    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    op.open(urllib.request.Request(BASE + "/public/cases/list", headers={"User-Agent": UA}), timeout=30).read()

    inserted = []
    skipped = []
    for row in rows:
        cn = row["case_number"]
        case_id, status = find_case_id(op, cn)
        if not case_id:
            skipped.append((cn, "case_id_not_found"))
            print(f"  {cn}: NOT FOUND on live realtdm case search")
            time.sleep(0.6)
            continue

        winning_bid, opening_bid = get_fees(op, case_id)
        if winning_bid is None:
            skipped.append((cn, f"no_winning_bid_field status={status!r}"))
            print(f"  {cn}: case_id={case_id} status={status!r} -- NO Winning Bid field found, skipped")
            time.sleep(0.6)
            continue

        winner = get_winner(op, case_id)
        address = get_address_parcel(op, case_id)
        time.sleep(0.6)

        outcome_row = {
            "case_number": cn,
            "county": "flagler",
            "auction_date": row["auction_date"],
            "opening_bid": opening_bid,
            "winning_bid": winning_bid,
            "outcome": "sold_3rd_party" if winner else "sold",
            "winner_name": winner,
            "property_address": address,
            "parcel_id": row.get("parcel_id"),
            "data_source": DATA_SOURCE,
            "source_url": f"{BASE}/public/cases/details?caseID={case_id}",
        }
        print(f"  {cn}: case_id={case_id} status={status!r} winning_bid=${winning_bid:,.2f} "
              f"opening_bid=${opening_bid if opening_bid is not None else 0:,.2f} winner={winner!r}")

        if DRY_RUN:
            inserted.append(outcome_row)
            continue

        try:
            rest_post("tax_deed_outcomes", outcome_row)
            inserted.append(outcome_row)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")
            print(f"  INSERT FAIL {cn}: {e} :: {body}")
            skipped.append((cn, f"insert_fail:{body[:200]}"))

    print(f"\nTOTALS: inserted={len(inserted)} skipped={len(skipped)} (of {len(rows)} target rows)")
    for r in inserted:
        print(f"  {'[DRY] ' if DRY_RUN else ''}INSERTED {r['case_number']} winning_bid={r['winning_bid']}")
    for cn, reason in skipped:
        print(f"  SKIPPED {cn}: {reason}")

    if len(rows) > 0 and not inserted and not skipped:
        raise RuntimeError("Silent failure: rows present but zero outcomes recorded")


if __name__ == "__main__":
    main()
