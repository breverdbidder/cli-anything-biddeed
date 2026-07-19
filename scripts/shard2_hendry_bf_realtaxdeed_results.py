#!/usr/bin/env python3
"""SHARD-2, hendry B/F fix (RealTaxDeed Auction Results Report).

Root cause (confirmed live 2026-07-19 against multi_county_auctions):
  17 hendry rows are tax_deed cases dated auction_date=2026-07-16 (3 days
  before "today" 2026-07-19, i.e. this sale date has already happened in
  real life) but auction_status is still stuck at 'upcoming' with
  sold_amount=NULL for every row. pencil_dod_evaluate_county's `closed_sold`
  denominator (count WHERE sold_amount IS NOT NULL) is 0 for hendry, so both
  B (verified outcomes / closed_sold) and F (tier1_sold / closed_sold) show
  NULL/0 with metric=null -- "no data" rather than a real failure. This is
  a data-completeness prerequisite gap, not a sourcing problem from scratch.
  The other 3 hendry rows are genuinely future foreclosure cases (2026-08-05,
  2026-09-30) and are correctly left untouched.

Fix: pull real winning-bid amounts from hendry.realtaxdeed.com's
authenticated "Auction Results Report" (report_id=18 -- SAME report_id as
santa_rosa's RealForeclose instance; RealTaxDeed and RealForeclose are the
same underlying RealAuction platform family, same login/notice-drain/report
flow, confirmed live). This is hendry Clerk's OWN post-sale ledger -- an
INDEPENDENT source from our own calendar-sweep scraper (data_source=
'calendar_sweep_mca_v3' on multi_county_auctions is our own pre-sale scrape;
the Report Viewer's ar.winning_bid column is written by the Clerk/RealAuction
backend after each auction closes, which we have never written ourselves).
This satisfies the "PropertyOnion=litmus only, never an independent source"
guardrail (nothing here touches PropertyOnion).

Session sequence discovered live against hendry.realtaxdeed.com (identical
to scripts/shard7_run3679_santa_rosa_bf_realforeclose_results.py):
  1. GET /index.cfm unauthenticated -> title "...-Splash Page" (login
     required, confirmed).
  2. POST /index.cfm ZACTION=AJAX&ZMETHOD=LOGIN&func=LOGIN&USERNAME=..&
     USERPASS=.. -> {"isOk":"YES","docsreq":"YES"}.
  3. GET /index.cfm repeatedly; each returns a "Notice and alert" page with
     a fresh NID until the queue drains (hendry took 3 accepts, vs santa
     rosa's variable count) -> dismissed via POST zaction=AJAX&zmethod=COM&
     process=NOTICE&func=ACCEPT&NID=<nid>. Looped with a defensive cap of 30.
  4. GET /index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18 -> Report
     Viewer, title "Auction Results Report" (confirmed same report_id as
     santa_rosa -- NOT assumed, discovered live: page <h1> reads "Auction
     Results Report"). REPID extracted via regex from the page body.
  5. GET .../index.cfm?<filter fields>&zaction=AJAX&zmethod=COM&
     process=REPVIEW&FUNC=FilterData&SHOWJSON=false&REPID=<repid> widening
     start_date/end_date to 01/01/2023-12/31/2026.
  6. POST .../index.cfm?zaction=AJAX&zmethod=COM&Process=REPVIEW&
     SHOWJSON=FALSE&REPID=<repid>&func=LoadData (jqGrid datatype:'json',
     mtype:'POST') -> {"rows":[{"cell":[sale_date, case_number, parcel,
     bidder, winning_bid_html, deposit, ..., auction_status, cert_or_deed_no,
     ""]}, ...]}. hendry's grid returns case_number as PLAIN TEXT in cell[1]
     (e.g. "25-99"), unlike santa_rosa's HTML-anchor-wrapped case number --
     confirmed live, handled below without assuming the santa_rosa markup.

HONESTY GUARD (same as santa_rosa reference script): only trust rows where
the report's OWN auction_status field says 'Sold'. Additionally -- confirmed
live for hendry -- 7 of the 17 target case numbers (25-36, 25-37, 25-38,
25-39, 25-40, 25-41, 25-43) do NOT appear ANYWHERE in the Auction Results
Report at all (checked both by full date-range dump and by per-case
Case_Number filter query, records=[] for every one). These are NOT
fabricated as sold -- they are left untouched, exactly per the "if 0/partial
matches, do not fabricate" instruction. Only the 10 case numbers that
actually appear with auction_status='Sold' are written.

Usage:
  python3 scripts/shard2_hendry_bf_realtaxdeed_results.py
  python3 scripts/shard2_hendry_bf_realtaxdeed_results.py --dry-run
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

COUNTY = "hendry"
SUBDOMAIN = "hendry"
BASE = f"https://{SUBDOMAIN}.realtaxdeed.com"
HOME = f"{BASE}/index.cfm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

DATA_SOURCE_TAG = "tier1:realtaxdeed_results_report:hendry"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


# ---- RealTaxDeed session helpers -------------------------------------------

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
    """Login, then dismiss the notice queue. Returns final page body."""
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
        raise RuntimeError(f"RealTaxDeed login failed (status={status}): {body[:300]}")
    log("RealTaxDeed login OK (isOk=YES)", "VERIFIED")

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
    """Load the Auction Results Report page (report_id=18), extract REPID.

    report_id=18 was NOT assumed -- confirmed live: the returned page's
    <h1> reads "Auction Results Report" (same report_id as santa_rosa's
    RealForeclose instance, discovered by direct probe, not guessed).
    """
    results_url = f"{BASE}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18"
    _, body = get(opener, results_url, referer=HOME)
    if "Auction Results Report" not in body:
        raise RuntimeError("report_id=18 did not return the Auction Results Report page")
    repid_m = re.search(r"REPID=(\d+)&func=LoadData", body)
    if not repid_m:
        raise RuntimeError("Could not extract REPID from Report Viewer page")
    repid = repid_m.group(1)
    log(f"Report Viewer loaded (Auction Results Report), REPID={repid}", "VERIFIED")
    return results_url, repid


def apply_wide_filter(opener, results_url, repid, start_mmddyyyy, end_mmddyyyy, case_number=""):
    filter_qs = urllib.parse.urlencode({
        "start_date": start_mmddyyyy,
        "end_date": end_mmddyyyy,
        "Case_Number": case_number,
        "Bidder": "",
        "Parcel": "",
        "SoldTO": "NULL",
        "Is_user": "0",
        "auctStat": "NULL",
        "auctType": "NULL",
    })
    filter_url = (f"{BASE}/index.cfm?{filter_qs}&zaction=AJAX&zmethod=COM"
                  f"&process=REPVIEW&FUNC=FilterData&SHOWJSON=false&REPID={repid}")
    status, body = get(opener, filter_url, referer=results_url)
    log(f"FilterData applied ({start_mmddyyyy} - {end_mmddyyyy}, case={case_number!r}): "
        f"HTTP {status}", "VERIFIED")
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


# hendry's grid returns case_number as PLAIN TEXT in cell[1] (confirmed live
# -- NOT an HTML anchor like santa_rosa's case_number_html column). Column
# order otherwise matches the santa_rosa reference script's COLS layout.
COLS = ["sale_date", "case_number", "parcel", "bidder", "winning_bid_html", "deposit",
        "auction_balance", "clerk_fee", "rec_fee", "ea_fee", "popr_fee",
        "doc_stamps", "total_due", "auction_status", "cert_or_deed_no", "_blank"]

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
        case_number = (d.get("case_number") or "").strip()
        d["case_number"] = case_number
        d["case_number_norm"] = re.sub(r"[^A-Z0-9]", "", case_number.upper())
        d["winning_bid_f"] = to_float_from_html(d.get("winning_bid_html"))
        out.append(d)
    return out


# ---- Supabase REST helpers ---------------------------------------------------

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


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read()) if prefer.startswith("return=representation") else None


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                  "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== SHARD-2 HENDRY B/F FIX (RealTaxDeed Auction Results Report) ===")

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
    log(f"Parsed {len(parsed)} result rows from RealTaxDeed Auction Results Report", "VERIFIED")

    if not parsed:
        log("0 rows parsed from RealTaxDeed results report for hendry -- "
            "BLOCKED, cannot backfill sold_amount from this source.", "VERIFIED")
        print("\n### RESULT: BLOCKED (0 rows from RealTaxDeed results report)")
        sys.exit(2)

    by_case = {r["case_number_norm"]: r for r in parsed if r["case_number_norm"]}

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,auction_date,auction_status,sold_amount,sold_amount_source,data_source")
    log(f"Fetched {len(mca_rows)} hendry multi_county_auctions rows", "VERIFIED")

    matched = []
    skipped_not_sold = 0
    not_in_report = []
    for row in mca_rows:
        cn_norm = re.sub(r"[^A-Z0-9]", "", (row.get("case_number") or "").upper())
        if not cn_norm:
            continue
        if cn_norm not in by_case:
            # Only relevant for the 17 tax_deed cases already flagged upcoming
            # with a past sale date; the 3 genuinely-future foreclosure cases
            # simply won't be in this report yet and are expected misses.
            not_in_report.append(row["case_number"])
            continue
        rr = by_case[cn_norm]
        if rr["winning_bid_f"] is None:
            continue
        # HONESTY GUARD: only trust rows the authoritative report itself
        # marks "Sold" -- anything else (e.g. a stray winning_bid on a
        # Cancelled row) would fabricate a closed_sold count.
        if (rr.get("auction_status") or "").strip().lower() != "sold":
            skipped_not_sold += 1
            continue
        matched.append((row, rr))

    log(f"Matched {len(matched)} hendry rows to RealTaxDeed results with "
        f"auction_status=Sold and a non-null winning_bid "
        f"(skipped_not_sold={skipped_not_sold}, "
        f"cases_absent_from_report={sorted(not_in_report)})", "VERIFIED")

    if not matched:
        print("\n### RESULT: BLOCKED (0 case_number matches with a winning_bid found)")
        sys.exit(2)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mca_patched = 0
    outcomes_inserted = 0
    to_payload = []
    for row, rr in matched:
        if DRY_RUN:
            log(f"DRY-RUN would PATCH mca id={row['id']} sold_amount={rr['winning_bid_f']} "
                f"case={row['case_number']}", "UNTESTED")
        else:
            # F (tier1_sold) requires tier1_sold_amount IS NOT NULL alongside
            # sold_amount. sold_amount here came from the authenticated
            # hendry.realtaxdeed.com Auction Results Report (report_id=18),
            # the Clerk's own post-sale ledger -- an independent, verified
            # source, not our pre-sale calendar-sweep guess. Stamping
            # tier1_sold_amount/tier1_authoritative from that same verified
            # fetch is honest attribution, not a ghost-success loop.
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
                "sold_amount": rr["winning_bid_f"],
                "sold_amount_source": DATA_SOURCE_TAG,
                "auction_status": "sold",
                "sold_amount_captured_at": now_iso,
                "tier1_sold_amount": rr["winning_bid_f"],
                "tier1_sale_status": "sold",
                "tier1_authoritative": True,
                "tier1_verified_at": now_iso,
            })
            mca_patched += 1
        to_payload.append({
            "case_number": row["case_number"],
            "county": COUNTY,
            "auction_date": row.get("auction_date"),
            "winning_bid": rr["winning_bid_f"],
            "outcome": "sold",
            "data_source": DATA_SOURCE_TAG,
            "source_url": f"{BASE}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18",
            "enriched_at": now_iso,
        })

    if to_payload and not DRY_RUN:
        try:
            existing = rest_get(
                f"tax_deed_outcomes?county=eq.{COUNTY}&select=case_number")
            existing_cases = {r["case_number"] for r in existing}
        except Exception as e:
            existing_cases = set()
            log(f"tax_deed_outcomes existing-case probe failed: {e}", "VERIFIED")
        to_payload = [r for r in to_payload if r["case_number"] not in existing_cases]

        if not to_payload:
            log("All matched case_numbers already have a tax_deed_outcomes row "
                "-- nothing new to insert", "VERIFIED")
        else:
            try:
                probe = rest_get("tax_deed_outcomes?limit=1")
                known_cols = set(probe[0].keys()) if probe else None
            except Exception as e:
                known_cols = None
                log(f"tax_deed_outcomes probe failed: {e}", "VERIFIED")
            if known_cols:
                trimmed = [{k: v for k, v in rec.items() if k in known_cols} for rec in to_payload]
            else:
                trimmed = to_payload
            try:
                rest_post("tax_deed_outcomes", trimmed, prefer="return=minimal")
                outcomes_inserted = len(trimmed)
                log(f"Inserted {outcomes_inserted} NEW rows into tax_deed_outcomes", "VERIFIED")
            except urllib.error.HTTPError as e:
                body = e.read()
                log(f"tax_deed_outcomes insert FAILED HTTP {e.code}: {body[:500]}", "VERIFIED")

    log(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}", "VERIFIED")

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
          "WHERE county='hendry' AND sold_amount IS NOT NULL "
          "GROUP BY county, sold_amount_source;")
    print(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}")
    print(f"BEFORE B: {baseline['B']}")
    print(f"BEFORE F: {baseline['F']}")
    print(f"AFTER  B: {after['B']}")
    print(f"AFTER  F: {after['F']}")


if __name__ == "__main__":
    main()
