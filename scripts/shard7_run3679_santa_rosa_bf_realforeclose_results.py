#!/usr/bin/env python3
"""SHARD-7 run3679, santa_rosa B/F fix.

Root cause (confirmed live 2026-07-11 against multi_county_auctions):
  17 santa_rosa rows have auction_status='sold' but ZERO have sold_amount
  populated, so pencil_dod_evaluate_county's `closed_sold` denominator
  (count WHERE sold_amount IS NOT NULL) is 0 -> both B (verified outcomes /
  closed_sold) and F (tier1_sold / closed_sold) show NULL/0 with metric=null,
  i.e. "no data" rather than a real failure -- this is a data-completeness
  prerequisite gap, not a sourcing problem from scratch.

Fix: pull real winning-bid amounts from santarosa.realforeclose.com's
authenticated "Auction Results Report" (report_id=18), which is Santa Rosa
Clerk's OWN RealAuction platform record of actual sale outcomes -- an
INDEPENDENT source from our own calendar-sweep scraper (data_source=
'realforeclose' on multi_county_auctions is our own pre-sale scrape; the
Report Viewer's ar.winning_bid column is the post-sale ledger written by the
Clerk/RealAuction backend after the auction closes, which we have never
written ourselves). This satisfies the "PropertyOnion=litmus only, never an
independent source" guardrail (nothing here touches PropertyOnion) and gives
us case_number-matched sold amounts to:
  1. UPDATE multi_county_auctions.sold_amount (+ sold_amount_source) for the
     17 rows the calendar-sweep already flagged auction_status='sold'.
  2. INSERT into foreclosure_outcomes (case_number, county, sold_amount/
     winning_bid, data_source='tier1:realforeclose_results_report:<repid>')
     so Letter B's EXISTS-join against foreclosure_outcomes has a row to
     match, with data_source NOT containing 'promote' (reserved for the
     promotion pipeline) and NOT PropertyOnion-derived.

Session sequence discovered live against santarosa.realforeclose.com:
  1. POST /index.cfm  ZACTION=AJAX&ZMETHOD=LOGIN&func=LOGIN&USERNAME=..&USERPASS=..
     (from CORE/System/JS/logform.js #LogButton click handler)
  2. GET /index.cfm repeatedly; each returns a "Notice and alert" interstitial
     page with a fresh NID until the queue is drained. Each is dismissed via
     POST /index.cfm zaction=AJAX&zmethod=COM&process=NOTICE&func=ACCEPT&
     NID=<nid> (from CORE/System/JS/notice.js AcceptNotice()). Looped until a
     non-notice title appears or a NID repeats (defensive cap 30 iterations).
  3. GET /index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18 -> Report Viewer
     page. Its jqGrid config embeds a fresh per-session REPID (extracted via
     regex from the page body).
  4. GET /index.cfm?<filter fields>&zaction=AJAX&zmethod=COM&process=REPVIEW&
     FUNC=FilterData&SHOWJSON=false&REPID=<repid>  (mirrors the page's own
     UpdateFilters() JS: every .filter input's id=value pair). Widens
     start_date/end_date beyond the page's default last-30-days window so all
     17 sold auctions we care about (back to 2026-03) are included.
  5. POST /index.cfm?zaction=AJAX&zmethod=COM&Process=REPVIEW&SHOWJSON=FALSE&
     REPID=<repid>&func=LoadData  (jqGrid datatype:'json', mtype:'POST') with
     page/rows/sidx/sord -> returns {"rows":[{"cell":[sale_date, case_id,
     parcel, bidder, winning_bid, deposit, ..., auction_status]}, ...]}.

No Firecrawl needed -- this sandbox's outbound IP was NOT WAF-blocked
(confirmed: unauthenticated PREVIEW/AJAX calls in
scripts/shard2_run2450_ajax_realforeclose_harvest.py already worked live
against this same host earlier in this session).

Usage:
  python3 scripts/shard7_run3679_santa_rosa_bf_realforeclose_results.py
  python3 scripts/shard7_run3679_santa_rosa_bf_realforeclose_results.py --dry-run
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

COUNTY = "santa_rosa"
SUBDOMAIN = "santarosa"
BASE = f"https://{SUBDOMAIN}.realforeclose.com"
HOME = f"{BASE}/index.cfm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

DATA_SOURCE_TAG = "tier1:realforeclose_results_report:report18"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


# ---- RealForeclose session helpers -----------------------------------------

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
        raise RuntimeError(f"RealForeclose login failed (status={status}): {body[:300]}")
    log("RealForeclose login OK (isOk=YES)", "VERIFIED")

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
    """Load the Auction Results Report page (report_id=18), extract REPID."""
    results_url = f"{BASE}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18"
    _, body = get(opener, results_url, referer=HOME)
    repid_m = re.search(r"REPID=(\d+)&func=LoadData", body)
    if not repid_m:
        raise RuntimeError("Could not extract REPID from Report Viewer page")
    repid = repid_m.group(1)
    log(f"Report Viewer loaded, REPID={repid}", "VERIFIED")
    return results_url, repid


def apply_wide_filter(opener, results_url, repid, start_mmddyyyy, end_mmddyyyy):
    """Mirror the page's UpdateFilters() JS: widen date range, clear other filters.

    IMPORTANT: SoldTO/Is_user/auctStat/auctType must be the <option value="...">
    attribute values from the rendered form (NOT the visible label text) or the
    server 500s and redirects to zaction=HOME&zmethod=error:
      SoldTO:    NULL (All) | "= -98" (Plaintiff) | "= -97" (Cert Holder) | "> 0" (3rd Party)
      Is_user:   0 (None) | 1 (Auctions I Won) | 2 (Auctions I Did Not Win)
      auctStat:  NULL (All) | 5 (Sold) | 6 (Cancelled)
      auctType:  NULL (All) | 1 (Foreclosure) | 2 (Taxdeed)
    """
    filter_qs = urllib.parse.urlencode({
        "start_date": start_mmddyyyy,
        "end_date": end_mmddyyyy,
        "Case_Number": "",
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
    """Paginate through all pages of the Auction Results Report grid."""
    all_rows = []
    first = load_grid_page(opener, results_url, repid, 1, rows_per_page)
    total_pages = int(first.get("total") or 1)
    all_rows.extend(first.get("rows", []))
    for p in range(2, min(total_pages, max_pages) + 1):
        pg = load_grid_page(opener, results_url, repid, p, rows_per_page)
        all_rows.extend(pg.get("rows", []))
    return all_rows, first.get("records"), total_pages


COLS = ["sale_date", "case_number_html", "parcel", "bidder", "winning_bid_html", "deposit",
        "auction_balance", "clerk_fee", "rec_fee", "ea_fee", "popr_fee",
        "doc_stamps", "total_due", "auction_status", "_blank"]

CASE_NUMBER_RE = re.compile(r">([0-9A-Za-z\-]{8,})<")
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


def extract_case_number(cell_html):
    if not cell_html:
        return None
    m = CASE_NUMBER_RE.search(cell_html)
    if m:
        return m.group(1)
    # fallback: plain text cell (no anchor)
    stripped = re.sub(r"<[^>]+>", "", cell_html).strip()
    return stripped or None


def parse_rows(raw_rows):
    out = []
    for row in raw_rows:
        cell = row.get("cell", [])
        d = dict(zip(COLS, cell))
        case_number = extract_case_number(d.get("case_number_html"))
        d["case_number"] = case_number
        d["case_number_norm"] = re.sub(r"[^A-Z0-9]", "", (case_number or "").upper())
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
    log("=== SHARD-7 RUN-3679 SANTA ROSA B/F FIX (RealForeclose Results Report) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")
    log(f"BASELINE F: {baseline['F']}", "VERIFIED")

    opener = build_opener()
    login_and_drain_notices(opener)
    results_url, repid = fetch_results_report(opener)
    # Wide range covering all santa_rosa auction_date values we have on file.
    apply_wide_filter(opener, results_url, repid, "01/01/2023", "12/31/2026")
    raw_rows, records, total_pages = load_all_grid_rows(opener, results_url, repid, rows_per_page=100)
    log(f"Grid response: total_pages={total_pages} records={records} rows_returned={len(raw_rows)}",
        "VERIFIED")

    parsed = parse_rows(raw_rows)
    log(f"Parsed {len(parsed)} result rows from RealForeclose Auction Results Report", "VERIFIED")
    if parsed:
        log(f"Sample row: {parsed[0]}", "VERIFIED")

    if not parsed:
        log("0 rows parsed from RealForeclose results report for santa_rosa -- "
            "BLOCKED, cannot backfill sold_amount from this source.", "VERIFIED")
        print("\n### RESULT: BLOCKED (0 rows from RealForeclose results report)")
        sys.exit(2)

    by_case = {r["case_number_norm"]: r for r in parsed if r["case_number_norm"]}

    # Fetch santa_rosa MCA rows that are missing sold_amount.
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,auction_status,sold_amount,sold_amount_source,data_source")
    log(f"Fetched {len(mca_rows)} santa_rosa multi_county_auctions rows", "VERIFIED")

    matched = []
    skipped_not_sold = 0
    for row in mca_rows:
        cn_norm = re.sub(r"[^A-Z0-9]", "", (row.get("case_number") or "").upper())
        if not cn_norm or cn_norm not in by_case:
            continue
        rr = by_case[cn_norm]
        if rr["winning_bid_f"] is None:
            continue
        # HONESTY GUARD: the Report Viewer sometimes carries a stray winning_bid
        # figure on rows whose OWN auction_status is "Cancelled" (observed live,
        # e.g. case 572024CA000533CAAXMX: bid=$161,000.00 but status=Cancelled --
        # almost certainly a last-high-bid-before-cancellation artifact, not an
        # actual sale). Only trust rows the authoritative report itself marks
        # "Sold" -- anything else would fabricate a closed_sold count.
        if (rr.get("auction_status") or "").strip().lower() != "sold":
            skipped_not_sold += 1
            continue
        matched.append((row, rr))

    log(f"Matched {len(matched)} santa_rosa rows to RealForeclose results with "
        f"auction_status=Sold and a non-null winning_bid "
        f"(skipped_not_sold={skipped_not_sold})", "VERIFIED")

    if not matched:
        print("\n### RESULT: BLOCKED (0 case_number matches with a winning_bid found)")
        sys.exit(2)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mca_patched = 0
    outcomes_inserted = 0
    fo_payload = []
    for row, rr in matched:
        if DRY_RUN:
            log(f"DRY-RUN would PATCH mca id={row['id']} sold_amount={rr['winning_bid_f']} "
                f"case={row['case_number']}", "UNTESTED")
        else:
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
                "sold_amount": rr["winning_bid_f"],
                "sold_amount_source": DATA_SOURCE_TAG,
                "sold_amount_captured_at": now_iso,
            })
            mca_patched += 1
        fo_payload.append({
            "case_number": row["case_number"],
            "county": COUNTY,
            "sold_amount": rr["winning_bid_f"],
            "winning_bid": rr["winning_bid_f"],
            "auction_status": rr.get("auction_status"),
            "sale_date": rr.get("sale_date"),
            "data_source": DATA_SOURCE_TAG,
            "captured_at": now_iso,
        })

    if fo_payload and not DRY_RUN:
        # Discover actual foreclosure_outcomes columns via a 1-row probe first,
        # then trim payload to only columns that exist (avoid 400s on unknown cols).
        try:
            probe = rest_get("foreclosure_outcomes?limit=1")
            known_cols = set(probe[0].keys()) if probe else None
        except Exception as e:
            known_cols = None
            log(f"foreclosure_outcomes probe failed: {e}", "VERIFIED")
        if known_cols:
            trimmed = [{k: v for k, v in rec.items() if k in known_cols} for rec in fo_payload]
        else:
            trimmed = fo_payload
        try:
            rest_post("foreclosure_outcomes", trimmed,
                      prefer="return=minimal,resolution=merge-duplicates")
            outcomes_inserted = len(trimmed)
            log(f"Inserted/merged {outcomes_inserted} rows into foreclosure_outcomes", "VERIFIED")
        except urllib.error.HTTPError as e:
            body = e.read()
            log(f"foreclosure_outcomes insert FAILED HTTP {e.code}: {body[:500]}", "VERIFIED")

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
          "WHERE county='santa_rosa' AND sold_amount IS NOT NULL "
          "GROUP BY county, sold_amount_source;")
    print(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}")
    print(f"BEFORE B: {baseline['B']}")
    print(f"BEFORE F: {baseline['F']}")
    print(f"AFTER  B: {after['B']}")
    print(f"AFTER  F: {after['F']}")


if __name__ == "__main__":
    main()
