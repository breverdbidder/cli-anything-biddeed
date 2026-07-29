#!/usr/bin/env python3
"""GOLD STANDARD shard-3 (orange/gulf, dispatch 29a2f6d6) -- gulf county, letters B+F.

DIAGNOSIS (live, 2026-07-29): all 9 gulf tax_deed_outcomes rows carry
outcome='SOLD' but winning_bid IS NULL (never captured), so
multi_county_auctions.sold_amount is NULL for all 9 -> a.closed_sold=0 in
pencil_dod_evaluate_county -> B and F both show metric=null (0/0 -> FAIL).
gulfclerk.com/courts/tax-deeds/ only publishes SURPLUS amounts (post-sale
leftover funds), not the winning bid/sale price -- confirmed live, would be
a data-integrity error to treat surplus as sold_amount. The real winning
bid lives on the actual auction platform (gulf.realtaxdeed.com), which
403s anonymously -- same authenticated "Auction Results Report" (report_id
18) mechanism already proven for osceola/santa_rosa is reused here
verbatim, county-parameterized only.

Writes: multi_county_auctions PATCH (sold_amount, tier1_sold_amount,
tier1_sale_status, tier1_authoritative, tier1_verified_at, sold_amount_source)
for matched rows only; tax_deed_outcomes PATCH winning_bid for the same
9 pre-existing rows (currently NULL) -- UPDATE only, no INSERT (rows
already exist from the prior gulfclerk surplus-page enrichment). No
cron/DROP/TRUNCATE touched.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime, timezone

COUNTY = "gulf"
SUBDOMAIN = "gulf"
BASE = f"https://{SUBDOMAIN}.realtaxdeed.com"
HOME = f"{BASE}/index.cfm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv
DATA_SOURCE_TAG = "tier1:realtaxdeed_results_report:report18"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def build_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(opener, url, referer=None):
    hdrs = {"User-Agent": UA}
    if referer:
        hdrs["Referer"] = referer
    req = urllib.request.Request(url, headers=hdrs)
    with opener.open(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def post(opener, url, form, referer=None, extra_headers=None):
    hdrs = {"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded"}
    if referer:
        hdrs["Referer"] = referer
    if extra_headers:
        hdrs.update(extra_headers)
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with opener.open(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def login_and_drain_notices(opener):
    get(opener, HOME)
    user = os.environ.get("REALFORECLOSE_EMAIL") or os.environ.get("REALFORECLOSE_USERNAME")
    pw = os.environ["REALFORECLOSE_PASSWORD"]
    if not user or not pw:
        raise RuntimeError("REALFORECLOSE_EMAIL/USERNAME + REALFORECLOSE_PASSWORD required")

    status, body = post(opener, HOME, {
        "ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
        "USERNAME": user, "USERPASS": pw,
    }, referer=HOME)
    if '"isOk":"YES"' not in body:
        raise RuntimeError(f"RealAuction login failed (status={status}): {body[:300]}")
    log(f"{SUBDOMAIN}.realtaxdeed.com login OK (isOk=YES)", "VERIFIED")

    seen_nids = set()
    body = None
    for i in range(30):
        _, body = get(opener, HOME)
        title_m = re.search(r"<title>([^<]*)</title>", body)
        title = title_m.group(1) if title_m else ""
        if "Notice and alert" not in title:
            log(f"Notice queue drained after {i} accepts -> '{title.strip()}'", "VERIFIED")
            return body
        nid_m = re.search(r'NID="(\d+)"', body)
        nid = nid_m.group(1) if nid_m else None
        if not nid or nid in seen_nids:
            raise RuntimeError(f"Stuck on notice page (nid={nid}, seen={seen_nids})")
        seen_nids.add(nid)
        post(opener, HOME, {
            "zaction": "AJAX", "zmethod": "COM", "process": "NOTICE",
            "func": "ACCEPT", "showjson": "false", "NID": nid,
        }, referer=HOME)
    raise RuntimeError("Notice queue did not drain within 30 iterations")


def fetch_results_report(opener):
    results_url = f"{BASE}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18"
    _, body = get(opener, results_url, referer=HOME)
    repid_m = re.search(r"REPID=(\d+)&func=LoadData", body)
    if not repid_m:
        raise RuntimeError("Could not extract REPID from Report Viewer page")
    repid = repid_m.group(1)
    log(f"Report Viewer loaded, REPID={repid}", "VERIFIED")
    return results_url, repid


def apply_wide_filter(opener, results_url, repid, start_mmddyyyy, end_mmddyyyy):
    filter_qs = urllib.parse.urlencode({
        "start_date": start_mmddyyyy, "end_date": end_mmddyyyy,
        "Case_Number": "", "Bidder": "", "Parcel": "", "SoldTO": "NULL",
        "Is_user": "0", "auctStat": "NULL", "auctType": "NULL",
    })
    filter_url = (f"{BASE}/index.cfm?{filter_qs}&zaction=AJAX&zmethod=COM"
                  f"&process=REPVIEW&FUNC=FilterData&SHOWJSON=false&REPID={repid}")
    status, body = get(opener, filter_url, referer=results_url)
    log(f"FilterData applied ({start_mmddyyyy} - {end_mmddyyyy}): HTTP {status}", "VERIFIED")
    return body


def load_grid_page(opener, results_url, repid, page, rows=100):
    grid_url = (f"{BASE}/index.cfm?zaction=AJAX&zmethod=COM&Process=REPVIEW"
                f"&SHOWJSON=FALSE&REPID={repid}&func=LoadData")
    status, body = post(opener, grid_url, {
        "page": str(page), "rows": str(rows), "sidx": "ar.insert_dt", "sord": "desc",
    }, referer=results_url)
    try:
        data = json.loads(body)
    except Exception as e:
        raise RuntimeError(f"Grid response not JSON (HTTP {status}): {body[:300]}") from e
    return data


def load_all_grid_rows(opener, results_url, repid, rows_per_page=100, max_pages=20):
    all_rows = []
    first = load_grid_page(opener, results_url, repid, 1, rows_per_page)
    total_pages = int(first.get("total") or 1)
    all_rows.extend(first.get("rows", []))
    for p in range(2, min(total_pages, max_pages) + 1):
        pg = load_grid_page(opener, results_url, repid, p, rows_per_page)
        all_rows.extend(pg.get("rows", []))
    return all_rows, first.get("records"), total_pages


COLS = ["sale_date", "case_number_raw", "parcel", "bidder", "winning_bid_html", "deposit",
        "auction_balance", "clerk_fee", "rec_fee", "ea_fee", "popr_fee",
        "doc_stamps", "total_due", "auction_status", "_dup_case", "_blank"]

MONEY_RE = re.compile(r"\$([\d,]+\.\d{2})")


def to_float_from_html(cell_html):
    if not cell_html:
        return None
    m = MONEY_RE.search(cell_html)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_rows(raw_rows):
    out = []
    for row in raw_rows:
        cell = row.get("cell", [])
        d = dict(zip(COLS, cell))
        case_number = (d.get("case_number_raw") or "").strip() or None
        d["case_number"] = case_number
        d["case_number_norm"] = re.sub(r"[^A-Z0-9]", "", (case_number or "").upper())
        d["winning_bid_f"] = to_float_from_html(d.get("winning_bid_html"))
        out.append(d)
    return out


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== SHARD-3 GULF B/F FIX (RealAuction TaxDeed Results Report, report_id=18) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")
    log(f"BASELINE F: {baseline['F']}", "VERIFIED")

    opener = build_opener()
    login_and_drain_notices(opener)
    results_url, repid = fetch_results_report(opener)
    apply_wide_filter(opener, results_url, repid, "01/01/2023", "12/31/2026")
    raw_rows, records, total_pages = load_all_grid_rows(opener, results_url, repid, rows_per_page=100)
    log(f"Grid response: total_pages={total_pages} records={records} rows_returned={len(raw_rows)}",
        "VERIFIED")

    parsed = parse_rows(raw_rows)
    log(f"Parsed {len(parsed)} result rows from {SUBDOMAIN}.realtaxdeed.com Auction Results Report",
        "VERIFIED")
    if parsed:
        log(f"Sample row: {parsed[0]}", "VERIFIED")

    if not parsed:
        log("0 rows parsed from realtaxdeed results report for gulf -- "
            "BLOCKED, cannot backfill sold_amount from this source.", "VERIFIED")
        print("\n### RESULT: BLOCKED (0 rows from realtaxdeed results report)")
        sys.exit(2)

    by_case = {r["case_number_norm"]: r for r in parsed if r["case_number_norm"]}

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.tax_deed"
        f"&select=id,case_number,auction_status,sale_type,sold_amount,sold_amount_source,data_source")
    log(f"Fetched {len(mca_rows)} gulf tax_deed multi_county_auctions rows", "VERIFIED")

    matched = []
    skipped_not_sold = 0
    unmatched_no_report_row = 0
    for row in mca_rows:
        cn_norm = re.sub(r"[^A-Z0-9]", "", (row.get("case_number") or "").upper())
        if not cn_norm or cn_norm not in by_case:
            unmatched_no_report_row += 1
            continue
        rr = by_case[cn_norm]
        if rr["winning_bid_f"] is None:
            unmatched_no_report_row += 1
            continue
        if (rr.get("auction_status") or "").strip().lower() != "sold":
            skipped_not_sold += 1
            continue
        matched.append((row, rr))

    log(f"Matched {len(matched)} gulf rows to realtaxdeed results with "
        f"status=Sold and a non-null winning_bid "
        f"(skipped_not_sold={skipped_not_sold}, unmatched_no_report_row={unmatched_no_report_row})",
        "VERIFIED")

    if not matched:
        print("\n### RESULT: BLOCKED (0 case_number matches with a winning_bid found)")
        sys.exit(2)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mca_patched = 0
    td_updated = 0
    for row, rr in matched:
        if DRY_RUN:
            log(f"DRY-RUN would PATCH mca id={row['id']} sold_amount={rr['winning_bid_f']} "
                f"case={row['case_number']}", "UNTESTED")
            continue
        rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
            "sold_amount": rr["winning_bid_f"],
            "sold_amount_source": DATA_SOURCE_TAG,
            "sold_amount_captured_at": now_iso,
            "tier1_sold_amount": rr["winning_bid_f"],
            "tier1_sale_status": "sold",
            "tier1_authoritative": True,
            "tier1_verified_at": now_iso,
            "tier1_source_run_id": 20260729,
        })
        mca_patched += 1
        rest_patch(f"tax_deed_outcomes?case_number=eq.{urllib.parse.quote(row['case_number'])}&county=eq.{COUNTY}", {
            "winning_bid": rr["winning_bid_f"],
        })
        td_updated += 1

    log(f"mca_patched={mca_patched} td_outcomes_winning_bid_updated={td_updated}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER B: {after['B']}", "VERIFIED")
    log(f"AFTER F: {after['F']}", "VERIFIED")

    now_iso2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso2}")
    print("SELECT county, sold_amount_source, COUNT(*) FROM multi_county_auctions "
          "WHERE county='gulf' AND sold_amount IS NOT NULL GROUP BY county, sold_amount_source;")
    print(f"mca_patched={mca_patched} td_outcomes_winning_bid_updated={td_updated}")
    print(f"BEFORE B: {baseline['B']}")
    print(f"BEFORE F: {baseline['F']}")
    print(f"AFTER  B: {after['B']}")
    print(f"AFTER  F: {after['F']}")


if __name__ == "__main__":
    main()
