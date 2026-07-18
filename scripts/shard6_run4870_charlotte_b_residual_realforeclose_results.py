#!/usr/bin/env python3
"""SHARD-6 run4870, charlotte B-metric residual close (2026-07-18).

Baseline (VERIFIED live via pencil_dod_evaluate_county at session start):
  B fails at metric=89.5 (verified=17 closed_sold=19). All other letters pass.

The 2 residual closed_sold rows have NO independent outcome row anywhere
(tax_deed_outcomes/foreclosure_outcomes), both data_source='propertyonion',
sold_amount='0.0' (placeholder), tier1_authoritative=true:
  25000552CA  auction_date 2026-06-05
  25000869CA  auction_date 2026-06-10

Prior session (scripts/shard9_charlotte_b_metric_independent_outcome_backfill.py,
2026-07-11) left these 2 (of an original 7) unresolved, explicitly blocked on:
  (a) RealForeclose.com PREVIEW pages returning empty case listings via curl, and
  (b) Charlotte Clerk Benchmark court-records portal requiring JS session
      interaction with no Firecrawl key configured that session.

THIS SESSION: FIRECRAWL_API_KEY is present but the account itself is exhausted
(VERIFIED via GET https://api.firecrawl.dev/v1/team/credit-usage ->
remaining_credits=0 on a 100000-credit plan, and POST /v1/scrape -> HTTP 402
"Insufficient credits" for both the target Benchmark URL and a neutral test URL
https://example.com). Firecrawl is therefore NOT usable this session despite
the key being set -- reported honestly as residual for Firecrawl specifically.

Instead, this script reuses the PROVEN pattern from
scripts/shard7_run3679_santa_rosa_bf_realforeclose_results.py: authenticated
login to charlotte.realforeclose.com (REALFORECLOSE_USERNAME/PASSWORD, present
in this environment) + the "Auction Results Report" (report_id=18), which is
the Clerk/RealAuction backend's own POST-sale ledger -- independent of our
pre-sale calendar-sweep scraper and independent of PropertyOnion.

Only case_number matches whose OWN report row has auction_status=Sold (exact,
case-insensitive) are trusted, per the same honesty guard as the santa_rosa
script (a stray winning_bid can appear on Cancelled rows -- last-high-bid-
before-cancellation artifact, not a real sale). If report auction_status is
Cancelled/Redeemed/anything other than Sold, NO outcome row is inserted and NO
sold_amount is overwritten -- reported as residual instead of fabricated.

Usage:
  python3 scripts/shard6_run4870_charlotte_b_residual_realforeclose_results.py
  python3 scripts/shard6_run4870_charlotte_b_residual_realforeclose_results.py --dry-run
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

COUNTY = "charlotte"
SUBDOMAIN = "charlotte"
BASE = f"https://{SUBDOMAIN}.realforeclose.com"
HOME = f"{BASE}/index.cfm"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

TARGET_CASE_NUMBERS = ["25000552CA", "25000869CA"]

DRY_RUN = "--dry-run" in sys.argv

DATA_SOURCE_TAG = "tier1:realforeclose_results_report:report18"


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


def load_all_grid_rows(opener, results_url, repid, rows_per_page=100, max_pages=40):
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
    log("=== SHARD-6 RUN-4870 CHARLOTTE B RESIDUAL FIX (RealForeclose Results Report) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")

    opener = build_opener()
    login_and_drain_notices(opener)
    results_url, repid = fetch_results_report(opener)
    # Wide range covering both target auction dates (2026-06-05, 2026-06-10).
    apply_wide_filter(opener, results_url, repid, "01/01/2023", "12/31/2026")
    raw_rows, records, total_pages = load_all_grid_rows(opener, results_url, repid, rows_per_page=100)
    log(f"Grid response: total_pages={total_pages} records={records} rows_returned={len(raw_rows)}",
        "VERIFIED")

    parsed = parse_rows(raw_rows)
    log(f"Parsed {len(parsed)} result rows from RealForeclose Auction Results Report", "VERIFIED")

    target_norms = {re.sub(r"[^A-Z0-9]", "", c.upper()) for c in TARGET_CASE_NUMBERS}
    by_case = {r["case_number_norm"]: r for r in parsed if r["case_number_norm"]}

    for cn in TARGET_CASE_NUMBERS:
        norm = re.sub(r"[^A-Z0-9]", "", cn.upper())
        hit = by_case.get(norm)
        if hit:
            log(f"FOUND {cn}: status={hit.get('auction_status')!r} "
                f"winning_bid_html={hit.get('winning_bid_html')!r} "
                f"sale_date={hit.get('sale_date')!r}", "VERIFIED")
        else:
            log(f"NOT FOUND in report grid: {cn}", "VERIFIED")

    if not parsed:
        log("0 rows parsed from RealForeclose results report for charlotte -- "
            "BLOCKED, cannot resolve residual from this source.", "VERIFIED")
        print("\n### RESULT: BLOCKED (0 rows from RealForeclose results report)")
        sys.exit(2)

    # Fetch the 2 target charlotte MCA rows.
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&case_number=in.({','.join(TARGET_CASE_NUMBERS)})"
        f"&select=id,case_number,auction_status,sold_amount,tier1_sold_amount,"
        f"tier1_authoritative,data_source")
    log(f"Fetched {len(mca_rows)} target charlotte multi_county_auctions rows", "VERIFIED")

    matched = []
    skipped_not_sold = []
    not_found = []
    for row in mca_rows:
        cn_norm = re.sub(r"[^A-Z0-9]", "", (row.get("case_number") or "").upper())
        rr = by_case.get(cn_norm)
        if not rr:
            not_found.append(row["case_number"])
            continue
        if rr["winning_bid_f"] is None:
            skipped_not_sold.append((row["case_number"], "no winning_bid in report"))
            continue
        if (rr.get("auction_status") or "").strip().lower() != "sold":
            skipped_not_sold.append((row["case_number"], rr.get("auction_status")))
            continue
        matched.append((row, rr))

    log(f"Matched {len(matched)} rows to RealForeclose results with "
        f"auction_status=Sold and a non-null winning_bid "
        f"(skipped_not_sold={skipped_not_sold}, not_found={not_found})", "VERIFIED")

    if not matched:
        print("\n### RESULT: BLOCKED (0 case_number matches with auction_status=Sold + winning_bid)")
        print(f"not_found={not_found}")
        print(f"skipped_not_sold={skipped_not_sold}")
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
                "tier1_sold_amount": rr["winning_bid_f"],
                "tier1_sale_status": "sold",
                "tier1_authoritative": True,
                "tier1_verified_at": now_iso,
                "tier1_source_run_id": 4870,
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
        try:
            existing = rest_get(
                f"foreclosure_outcomes?county=eq.{COUNTY}&select=case_number")
            existing_cases = {r["case_number"] for r in existing}
        except Exception as e:
            existing_cases = set()
            log(f"foreclosure_outcomes existing-case probe failed: {e}", "VERIFIED")
        fo_payload = [r for r in fo_payload if r["case_number"] not in existing_cases]

        if not fo_payload:
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
                trimmed = [{k: v for k, v in rec.items() if k in known_cols} for rec in fo_payload]
            else:
                trimmed = fo_payload
            try:
                rest_post("foreclosure_outcomes", trimmed, prefer="return=minimal")
                outcomes_inserted = len(trimmed)
                log(f"Inserted {outcomes_inserted} NEW rows into foreclosure_outcomes", "VERIFIED")
            except urllib.error.HTTPError as e:
                body = e.read()
                log(f"foreclosure_outcomes insert FAILED HTTP {e.code}: {body[:500]}", "VERIFIED")

    log(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER B: {after['B']}", "VERIFIED")

    now_iso2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso2}")
    print("SELECT case_number, sold_amount, sold_amount_source FROM multi_county_auctions "
          f"WHERE county='charlotte' AND case_number IN ({','.join(repr(c) for c in TARGET_CASE_NUMBERS)});")
    print(f"mca_patched={mca_patched} outcomes_inserted={outcomes_inserted}")
    print(f"BEFORE B: {baseline['B']}")
    print(f"AFTER  B: {after['B']}")


if __name__ == "__main__":
    main()
