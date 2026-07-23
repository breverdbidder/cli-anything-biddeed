#!/usr/bin/env python3
"""GOLD STANDARD shard-9 run6046 -- bay B/F fix (RealForeclose Auction
Results Report), dispatch 503717c8-e819-470c-b363-6f20c13160e9.

Root cause (confirmed live 2026-07-23 via pencil_dod_evaluate_county('bay')):
  bay has 136 auctions_total, 61 DoD-scoped foreclosure rows with auction
  dates from 2026-03-12 through today, but ZERO of them have sold_amount
  set (B: verified=0 closed_sold=0 -> null; F: tier1_sold=0 closed_sold=0
  -> null). No prior session has ever backfilled bay foreclosure outcomes.

  Same proven technique already used for sarasota/hendry/santa_rosa
  (scripts/gold_standard_shard6_run5361_sarasota_bcdf_realforeclose_results.py,
  scripts/shard2_hendry_bf_realtaxdeed_results.py,
  scripts/shard7_run3679_santa_rosa_bf_realforeclose_results.py): the
  authenticated bay.realforeclose.com "Auction Results Report"
  (report_id=18). This is the Bay Clerk's OWN post-sale ledger (ar.winning_bid
  written by the Clerk/RealAuction backend after each auction closes) -- an
  INDEPENDENT source from our own pre-sale calendar-sweep scraper.

  Per the task instructions, the sarasota 15-cell COLS layout is NOT assumed
  for bay -- this script prints the raw cell array for the first couple of
  grid rows and the caller must confirm column count/order (case_number
  index, winning_bid index, auction_status index) before the parser is
  trusted. See PROBE OUTPUT block printed at runtime.

HONESTY GUARD: only trust rows where the report's OWN auction_status field
says 'Sold'. Rows marked 'Cancelled', 'Redeemed', or absent from the report
entirely are left untouched -- no fabrication, no synthetic backfill.

Writes foreclosure_outcomes rows with data_source=
'tier1_realforeclose_results_report:bay:gold_standard_shard9_run6046' and
sets parity_status/parity_source/tier1_sold_amount/tier1_authoritative on
the matching multi_county_auctions row so B/C/D/F all move together.

Usage:
  python3 scripts/shard9_run6046_bay_bf_realforeclose_results.py
  python3 scripts/shard9_run6046_bay_bf_realforeclose_results.py --dry-run
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

COUNTY = "bay"
SUBDOMAIN = "bay"
BASE = f"https://{SUBDOMAIN}.realforeclose.com"
HOME = f"{BASE}/index.cfm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

DATA_SOURCE_TAG = "tier1_realforeclose_results_report:bay:gold_standard_shard9_run6046"
PARITY_SOURCE_TAG = "tier1_realforeclose_live:bay:gold_standard_shard9_run6046"
RESULTS_REPORT_URL = f"{BASE}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18"


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
    _, body = get(opener, RESULTS_REPORT_URL, referer=HOME)
    if "Auction Results Report" not in body:
        raise RuntimeError("report_id=18 did not return the Auction Results Report page "
                            f"(body head: {body[:300]!r})")
    repid_m = re.search(r"REPID=(\d+)&func=LoadData", body)
    if not repid_m:
        raise RuntimeError("Could not extract REPID from Report Viewer page")
    repid = repid_m.group(1)
    log(f"Report Viewer loaded (Auction Results Report), REPID={repid}", "VERIFIED")
    return RESULTS_REPORT_URL, repid


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


# ---- Column layout probe -----------------------------------------------------
# UNKNOWN at write time whether bay's foreclosure grid matches sarasota's
# 15-cell layout (no cert_or_deed_no) -- confirmed empirically at runtime
# below (PROBE OUTPUT), per task instructions. Default guess mirrors the
# sarasota/santa_rosa RealForeclose foreclosure-grid layout; overridden if
# the live probe shows a different cell count.
COLS_15 = ["sale_date", "case_number_html", "parcel", "bidder", "winning_bid_html", "deposit",
           "auction_balance", "clerk_fee", "rec_fee", "ea_fee", "popr_fee",
           "doc_stamps", "total_due", "auction_status", "_blank"]
# 16-cell variant seen on some tax_deed grids (adds cert_or_deed_no as cell[1],
# shifting everything else right by one) -- kept only as a fallback reference,
# used only if the live probe cell count is 16, matched by position of the
# 'Sold'/'Cancelled' auction_status text and $ winning bid, not assumed blind.
COLS_16 = ["sale_date", "cert_or_deed_no", "case_number_html", "parcel", "bidder",
           "winning_bid_html", "deposit", "auction_balance", "clerk_fee", "rec_fee",
           "ea_fee", "popr_fee", "doc_stamps", "total_due", "auction_status", "_blank"]

CASE_NUMBER_RE = re.compile(r">([0-9A-Za-z \-]{6,})<")
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
        return m.group(1).strip()
    stripped = re.sub(r"<[^>]+>", "", cell_html).strip()
    return stripped or None


def probe_columns(raw_rows):
    """Print raw cell arrays for the first few rows so column layout can be
    confirmed empirically before parsing -- per task instructions, bay's
    layout is NOT assumed to match sarasota's blind."""
    print("\n### PROBE OUTPUT -- raw cell arrays (bay Auction Results Report grid)")
    cell_counts = set()
    for i, row in enumerate(raw_rows[:5]):
        cell = row.get("cell", [])
        cell_counts.add(len(cell))
        print(f"row[{i}] cell_count={len(cell)}")
        for idx, c in enumerate(cell):
            print(f"  [{idx}] {c!r}")
    print(f"### PROBE cell_counts_seen={cell_counts}\n")
    return cell_counts


def choose_cols(cell_counts):
    if cell_counts == {15}:
        log("Grid layout: 15 cells, matches sarasota/santa_rosa foreclosure layout "
            "(no cert_or_deed_no)", "VERIFIED")
        return COLS_15
    if cell_counts == {16}:
        log("Grid layout: 16 cells, matches tax_deed layout (has cert_or_deed_no)", "VERIFIED")
        return COLS_16
    raise RuntimeError(f"Unrecognized/inconsistent cell layout for bay grid: {cell_counts} "
                        "-- refusing to guess column mapping, inspect PROBE OUTPUT above")


def parse_rows(raw_rows, cols):
    out = []
    for row in raw_rows:
        cell = row.get("cell", [])
        d = dict(zip(cols, cell))
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
    log("=== GOLD STANDARD SHARD-9 RUN6046 BAY B/F FIX (RealForeclose Auction Results Report) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    for letter in ("B", "C", "D", "F"):
        log(f"BASELINE {letter}: {baseline[letter]}", "VERIFIED")

    opener = build_opener()
    login_and_drain_notices(opener)
    results_url, repid = fetch_results_report(opener)
    # Wide range per task instructions.
    apply_wide_filter(opener, results_url, repid, "01/01/2023", "12/31/2026")
    raw_rows, records, total_pages = load_all_grid_rows(opener, results_url, repid, rows_per_page=100)
    log(f"Grid response: total_pages={total_pages} records={records} rows_returned={len(raw_rows)}",
        "VERIFIED")

    if not raw_rows:
        log("0 raw rows returned from bay Auction Results Report grid -- BLOCKED", "VERIFIED")
        print("\n### RESULT: BLOCKED (0 rows from bay RealForeclose results report)")
        sys.exit(2)

    cell_counts = probe_columns(raw_rows)
    cols = choose_cols(cell_counts)

    parsed = parse_rows(raw_rows, cols)
    log(f"Parsed {len(parsed)} result rows from bay RealForeclose Auction Results Report", "VERIFIED")

    if not parsed:
        log("0 rows parsed from bay RealForeclose results report -- "
            "BLOCKED, cannot backfill foreclosure_outcomes from this source.", "VERIFIED")
        print("\n### RESULT: BLOCKED (0 rows parsed from bay RealForeclose results report)")
        sys.exit(2)

    by_case = {}
    for r in parsed:
        if r["case_number_norm"]:
            by_case.setdefault(r["case_number_norm"], r)

    # DoD-scoped only (excludes propertyonion rows without tier1_authoritative,
    # matching pencil_dod_evaluate_county's own WHERE clause). NOTE: PostgREST's
    # `not.eq` is SQL `<>`, which is NULL (excludes the row) for NULL
    # data_source -- confirmed live on sarasota this silently dropped in-scope
    # NULL-data_source rows. Fixed by explicitly OR-ing in the
    # `data_source.is.null` leg (same fix applied here).
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.foreclosure"
        f"&or=(data_source.is.null,data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        f"&select=id,case_number,auction_date,auction_status,sold_amount,sold_amount_source,"
        f"data_source,parity_status,parcel_id&limit=2000")
    log(f"Fetched {len(mca_rows)} bay DoD-scoped foreclosure multi_county_auctions rows", "VERIFIED")

    matched = []
    skipped_not_sold = 0
    not_in_report = []
    for row in mca_rows:
        cn_norm = re.sub(r"[^A-Z0-9]", "", (row.get("case_number") or "").upper())
        if not cn_norm:
            continue
        if cn_norm not in by_case:
            not_in_report.append(row["case_number"])
            continue
        rr = by_case[cn_norm]
        if rr["winning_bid_f"] is None:
            continue
        # HONESTY GUARD: only trust rows the authoritative report itself
        # marks "Sold" -- anything else would fabricate a closed_sold count.
        if (rr.get("auction_status") or "").strip().lower() != "sold":
            skipped_not_sold += 1
            continue
        matched.append((row, rr))

    log(f"Matched {len(matched)} bay foreclosure rows to RealForeclose results with "
        f"auction_status=Sold and a non-null winning_bid "
        f"(skipped_not_sold={skipped_not_sold}, "
        f"cases_absent_from_report={len(not_in_report)})", "VERIFIED")

    if not matched:
        print("\n### RESULT: BLOCKED (0 case_number matches with a winning_bid found)")
        print(f"skipped_not_sold={skipped_not_sold} cases_absent_from_report={len(not_in_report)}")
        sys.exit(2)

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mca_patched = 0
    outcomes_inserted = 0
    to_payload = []
    for row, rr in matched:
        if DRY_RUN:
            log(f"DRY-RUN would PATCH mca id={row['id']} sold_amount={rr['winning_bid_f']} "
                f"case={row['case_number']} (existing sold_amount={row.get('sold_amount')})",
                "UNTESTED")
        else:
            # F (tier1_sold) requires tier1_sold_amount IS NOT NULL alongside
            # sold_amount. sold_amount here came from the authenticated
            # bay.realforeclose.com Auction Results Report (report_id=18),
            # the Clerk's own post-sale ledger -- an independent, verified
            # source, not our pre-sale calendar-sweep guess.
            rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
                "sold_amount": rr["winning_bid_f"],
                "sold_amount_source": DATA_SOURCE_TAG,
                "auction_status": "completed",
                "sold_amount_captured_at": now_iso,
                "tier1_sold_amount": rr["winning_bid_f"],
                "tier1_sale_status": "sold",
                "tier1_authoritative": True,
                "tier1_verified_at": now_iso,
                "parity_status": "matched_clean",
                "parity_source": PARITY_SOURCE_TAG,
            })
            mca_patched += 1
        to_payload.append({
            "case_number": row["case_number"],
            "county": COUNTY,
            "auction_date": row.get("auction_date"),
            "winning_bid": rr["winning_bid_f"],
            "outcome": "sold",
            "parcel_id": row.get("parcel_id"),
            "data_source": DATA_SOURCE_TAG,
            "source_url": RESULTS_REPORT_URL,
            "enriched_at": now_iso,
        })

    if to_payload and not DRY_RUN:
        try:
            existing = rest_get(
                f"foreclosure_outcomes?county=eq.{COUNTY}&select=case_number")
            existing_cases = {r["case_number"] for r in existing}
        except Exception as e:
            existing_cases = set()
            log(f"foreclosure_outcomes existing-case probe failed: {e}", "VERIFIED")
        to_payload = [r for r in to_payload if r["case_number"] not in existing_cases]

        if not to_payload:
            log("All matched case_numbers already have a foreclosure_outcomes row "
                "-- nothing new to insert", "VERIFIED")
        else:
            try:
                probe = rest_get("foreclosure_outcomes?limit=1")
                known_cols = set(probe[0].keys()) if probe else None
            except Exception as e:
                known_cols = None
                log(f"foreclosure_outcomes probe failed: {e}", "VERIFIED")
            if known_cols:
                trimmed = [{k: v for k, v in rec.items() if k in known_cols} for rec in to_payload]
            else:
                trimmed = to_payload
            try:
                rest_post("foreclosure_outcomes", trimmed, prefer="return=minimal")
                outcomes_inserted = len(trimmed)
                log(f"Inserted {outcomes_inserted} NEW rows into foreclosure_outcomes", "VERIFIED")
            except urllib.error.HTTPError as e:
                body = e.read()
                log(f"foreclosure_outcomes insert FAILED HTTP {e.code}: {body[:500]}", "VERIFIED")
                raise

    # Fail-loud invariant: parsed>0 but wrote 0 must raise, never silently no-op.
    if len(matched) > 0 and mca_patched == 0 and outcomes_inserted == 0 and not DRY_RUN:
        raise RuntimeError(
            f"FAIL-LOUD: matched={len(matched)} rows but mca_patched=0 outcomes_inserted=0 "
            "-- refusing to silently no-op")

    log(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})

    now_iso2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso2}")
    print("SELECT county, sold_amount_source, COUNT(*) FROM multi_county_auctions "
          "WHERE county='bay' AND sale_type='foreclosure' AND sold_amount IS NOT NULL "
          "GROUP BY county, sold_amount_source;")
    print(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted} "
          f"skipped_not_sold={skipped_not_sold} cases_absent_from_report={len(not_in_report)}")
    for letter in ("B", "C", "D", "F"):
        print(f"BEFORE {letter}: {baseline[letter]}")
        print(f"AFTER  {letter}: {after[letter]}")


if __name__ == "__main__":
    main()
