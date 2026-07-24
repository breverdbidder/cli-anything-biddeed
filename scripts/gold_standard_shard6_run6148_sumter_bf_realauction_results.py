#!/usr/bin/env python3
"""Gold Standard shard-6, run6148, sumter B/F fix (RealForeclose + RealTaxDeed
Auction Results Reports).

Root cause (confirmed live 2026-07-24 against multi_county_auctions):
  All 11 sumter rows have auction_date in the past (2026-01-08 through
  2026-07-09) but ZERO have sold_amount populated, so
  pencil_dod_evaluate_county's `closed_sold` denominator (count WHERE
  sold_amount IS NOT NULL) is 0 -> both B and F show metric=null ("no data"),
  not a real failure. A prior session (scripts/shard10_run3645_sumter_bf_outcomes.py)
  correctly declined to derive winning_bid = opening_bid + surplus from the
  sumterclerk.com surplus-funds Google Sheet, since Fla. Stat. 197.582 surplus
  is proceeds minus ALL statutory disbursements (cert face + interest + fees),
  not simply proceeds minus opening_bid -- that identity does not hold, so it
  would have fabricated a number.

Fix: pipeline.counties confirms sumter runs the standard RealAuction platform
family for BOTH lanes (foreclosure_platform='realforeclose',
foreclosure_url=sumter.realforeclose.com; taxdeed_platform='realtaxdeed',
taxdeed_url=sumter.realtaxdeed.com) -- this is the fleet's canonical Letter-F
playbook source ("tier1 sold-amount verification via authenticated RealAuction
result pages"), NOT yet tried for sumter (the existing sumterclerk_* data_source
rows came from the county Clerk's own site, a different host). Both lanes'
Auction Results Report (report_id=18, confirmed live at report18 across 11+
counties in this fleet: santa_rosa, hendry, sarasota, bay, ...) is the
Clerk/RealAuction backend's own post-sale ledger -- independent of our
pre-sale calendar-sweep scrape and independent of PropertyOnion.

Session sequence (identical family flow, confirmed per-host):
  1. POST /index.cfm ZACTION=AJAX&ZMETHOD=LOGIN&func=LOGIN&USERNAME=..&USERPASS=..
  2. Drain "Notice and alert" interstitial queue via NOTICE/ACCEPT loop (cap 30).
  3. GET /index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18 -> extract REPID.
  4. GET .../FilterData widened to 01/01/2023-12/31/2026.
  5. POST .../LoadData (jqGrid) -> {"rows":[{"cell":[...]}]}.

HONESTY GUARD (same as santa_rosa/hendry reference scripts): only trust rows
where the report's OWN auction_status field says 'Sold'. Cases absent from
the report, or present but Cancelled/Redeemed, are left untouched -- no
fabrication.

Usage:
  python3 scripts/gold_standard_shard6_run6148_sumter_bf_realauction_results.py
  python3 scripts/gold_standard_shard6_run6148_sumter_bf_realauction_results.py --dry-run
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

COUNTY = "sumter"
LANES = [
    {"name": "foreclosure", "subdomain": "sumter", "host": "realforeclose.com",
     "tag": "tier1:realforeclose_results_report:sumter", "outcomes_table": "foreclosure_outcomes"},
    {"name": "taxdeed", "subdomain": "sumter", "host": "realtaxdeed.com",
     "tag": "tier1:realtaxdeed_results_report:sumter", "outcomes_table": "tax_deed_outcomes"},
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv


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


def post(opener, url, form, referer=None):
    hdrs = {"User-Agent": UA, "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded"}
    if referer:
        hdrs["Referer"] = referer
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with opener.open(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", errors="replace")


def login_and_drain_notices(opener, base, home):
    get(opener, home)
    user = os.environ.get("REALFORECLOSE_EMAIL") or os.environ.get("REALFORECLOSE_USERNAME")
    pw = os.environ["REALFORECLOSE_PASSWORD"]
    if not user or not pw:
        raise RuntimeError("REALFORECLOSE_EMAIL/USERNAME + REALFORECLOSE_PASSWORD required")
    status, body = post(opener, home, {
        "ZACTION": "AJAX", "ZMETHOD": "LOGIN", "func": "LOGIN",
        "USERNAME": user, "USERPASS": pw,
    }, referer=home)
    if '"isOk":"YES"' not in body:
        raise RuntimeError(f"login failed at {base} (status={status}): {body[:300]}")
    log(f"{base} login OK (isOk=YES)", "VERIFIED")

    seen_nids = set()
    for i in range(30):
        _, body = get(opener, home)
        title_m = re.search(r"<title>([^<]*)</title>", body)
        title = title_m.group(1) if title_m else ""
        if "Notice and alert" not in title:
            log(f"{base} notice queue drained after {i} accepts -> '{title.strip()}'", "VERIFIED")
            return body
        nid_m = re.search(r'NID="(\d+)"', body)
        nid = nid_m.group(1) if nid_m else None
        if not nid or nid in seen_nids:
            raise RuntimeError(f"Stuck on notice page at {base} (nid={nid}, seen={seen_nids})")
        seen_nids.add(nid)
        post(opener, home, {
            "zaction": "AJAX", "zmethod": "COM", "process": "NOTICE",
            "func": "ACCEPT", "showjson": "false", "NID": nid,
        }, referer=home)
    raise RuntimeError(f"Notice queue did not drain within 30 iterations at {base}")


def fetch_results_report(opener, base, home):
    results_url = f"{base}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18"
    _, body = get(opener, results_url, referer=home)
    if "Auction Results Report" not in body:
        raise RuntimeError(f"report_id=18 did not return Auction Results Report at {base}")
    repid_m = re.search(r"REPID=(\d+)&func=LoadData", body)
    if not repid_m:
        raise RuntimeError(f"Could not extract REPID from Report Viewer page at {base}")
    repid = repid_m.group(1)
    log(f"{base} Report Viewer loaded, REPID={repid}", "VERIFIED")
    return results_url, repid


def apply_wide_filter(opener, base, results_url, repid, start_mmddyyyy, end_mmddyyyy):
    filter_qs = urllib.parse.urlencode({
        "start_date": start_mmddyyyy, "end_date": end_mmddyyyy,
        "Case_Number": "", "Bidder": "", "Parcel": "",
        "SoldTO": "NULL", "Is_user": "0", "auctStat": "NULL", "auctType": "NULL",
    })
    filter_url = (f"{base}/index.cfm?{filter_qs}&zaction=AJAX&zmethod=COM"
                  f"&process=REPVIEW&FUNC=FilterData&SHOWJSON=false&REPID={repid}")
    status, body = get(opener, filter_url, referer=results_url)
    log(f"{base} FilterData applied ({start_mmddyyyy} - {end_mmddyyyy}): HTTP {status}", "VERIFIED")
    return body


def load_grid_page(opener, base, results_url, repid, page, rows=100):
    grid_url = (f"{base}/index.cfm?zaction=AJAX&zmethod=COM&Process=REPVIEW"
                f"&SHOWJSON=FALSE&REPID={repid}&func=LoadData")
    status, body = post(opener, grid_url, {
        "page": str(page), "rows": str(rows), "sidx": "ar.insert_dt", "sord": "desc",
    }, referer=results_url)
    try:
        return json.loads(body)
    except Exception as e:
        raise RuntimeError(f"Grid response not JSON at {base} (HTTP {status}): {body[:300]}") from e


def load_all_grid_rows(opener, base, results_url, repid, rows_per_page=100, max_pages=20):
    all_rows = []
    first = load_grid_page(opener, base, results_url, repid, 1, rows_per_page)
    total_pages = int(first.get("total") or 1)
    all_rows.extend(first.get("rows", []))
    for p in range(2, min(total_pages, max_pages) + 1):
        pg = load_grid_page(opener, base, results_url, repid, p, rows_per_page)
        all_rows.extend(pg.get("rows", []))
    return all_rows, first.get("records"), total_pages


MONEY_RE = re.compile(r"\$([\d,]+\.\d{2})")
CASE_NUMBER_RE = re.compile(r">([0-9A-Za-z\-]{8,})<")


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
    """Column layout probed live per-lane in main(); this handles both the
    HTML-anchor case_number variant (santa_rosa-style) and plain-text
    (hendry-style) since we don't know sumter's variant ahead of time."""
    out = []
    for row in raw_rows:
        cell = row.get("cell", [])
        if len(cell) < 14:
            continue
        sale_date, case_html, parcel, bidder, bid_html = cell[0], cell[1], cell[2], cell[3], cell[4]
        auction_status = cell[13] if len(cell) > 13 else None
        case_number = extract_case_number(case_html) or (case_html or "").strip()
        out.append({
            "sale_date": sale_date,
            "case_number": case_number,
            "case_number_norm": re.sub(r"[^A-Z0-9]", "", (case_number or "").upper()),
            "parcel": parcel,
            "winning_bid_f": to_float_from_html(bid_html),
            "auction_status": auction_status,
        })
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


def process_lane(lane, mca_rows):
    base = f"https://{lane['subdomain']}.{lane['host']}"
    home = f"{base}/index.cfm"
    opener = build_opener()
    login_and_drain_notices(opener, base, home)
    results_url, repid = fetch_results_report(opener, base, home)
    apply_wide_filter(opener, base, results_url, repid, "01/01/2023", "12/31/2026")
    raw_rows, records, total_pages = load_all_grid_rows(opener, base, results_url, repid)
    log(f"{base} grid: total_pages={total_pages} records={records} rows_returned={len(raw_rows)}",
        "VERIFIED")
    parsed = parse_rows(raw_rows)
    log(f"{base} parsed {len(parsed)} result rows", "VERIFIED")
    by_case = {r["case_number_norm"]: r for r in parsed if r["case_number_norm"]}

    matched, skipped_not_sold, not_in_report = [], 0, []
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
        if (rr.get("auction_status") or "").strip().lower() != "sold":
            skipped_not_sold += 1
            continue
        matched.append((row, rr))
    log(f"{base} matched={len(matched)} skipped_not_sold={skipped_not_sold} "
        f"not_in_report={sorted(not_in_report)}", "VERIFIED")
    return matched


def main():
    log("=== GOLD STANDARD SHARD-6 RUN-6148 SUMTER B/F FIX (RealAuction family) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")
    log(f"BASELINE F: {baseline['F']}", "VERIFIED")

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}"
        f"&select=id,case_number,sale_type,auction_date,auction_status,sold_amount,sold_amount_source,data_source")
    log(f"Fetched {len(mca_rows)} sumter multi_county_auctions rows", "VERIFIED")
    fc_rows = [r for r in mca_rows if r.get("sale_type") == "foreclosure"]
    td_rows = [r for r in mca_rows if r.get("sale_type") == "tax_deed"]

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_patched, total_inserted = 0, 0

    for lane, rows in (("foreclosure", fc_rows), ("taxdeed", td_rows)):
        lane_cfg = next(l for l in LANES if l["name"] == lane)
        if not rows:
            log(f"No sumter rows for lane={lane}, skipping", "VERIFIED")
            continue
        try:
            matched = process_lane(lane_cfg, rows)
        except Exception as e:
            log(f"LANE {lane} FAILED: {e}", "VERIFIED")
            continue

        if not matched:
            log(f"LANE {lane}: 0 matches, no writes", "VERIFIED")
            continue

        outcomes_table = lane_cfg["outcomes_table"]
        tag = lane_cfg["tag"]
        payload = []
        for row, rr in matched:
            if DRY_RUN:
                log(f"DRY-RUN would PATCH mca id={row['id']} sold_amount={rr['winning_bid_f']} "
                    f"case={row['case_number']}", "UNTESTED")
            else:
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
                    "sold_amount": rr["winning_bid_f"],
                    "sold_amount_source": tag,
                    "sold_amount_captured_at": now_iso,
                    "tier1_sold_amount": rr["winning_bid_f"],
                    "tier1_sale_status": "sold",
                    "tier1_authoritative": True,
                    "tier1_verified_at": now_iso,
                })
                total_patched += 1
            rec = {
                "case_number": row["case_number"],
                "county": COUNTY,
                "sold_amount": rr["winning_bid_f"],
                "winning_bid": rr["winning_bid_f"],
                "outcome": "sold" if outcomes_table == "tax_deed_outcomes" else None,
                "auction_status": rr.get("auction_status"),
                "sale_date": rr.get("sale_date"),
                "auction_date": row.get("auction_date"),
                "data_source": tag,
                "source_url": f"https://{lane_cfg['subdomain']}.{lane_cfg['host']}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18",
                "captured_at": now_iso,
                "enriched_at": now_iso,
            }
            payload.append({k: v for k, v in rec.items() if v is not None})

        if payload and not DRY_RUN:
            try:
                existing = rest_get(f"{outcomes_table}?county=eq.{COUNTY}&select=case_number")
                existing_cases = {r["case_number"] for r in existing}
            except Exception as e:
                existing_cases = set()
                log(f"{outcomes_table} existing-case probe failed: {e}", "VERIFIED")
            new_payload = [r for r in payload if r["case_number"] not in existing_cases]
            if not new_payload:
                log(f"{outcomes_table}: all matched cases already have a row", "VERIFIED")
            else:
                try:
                    probe = rest_get(f"{outcomes_table}?limit=1")
                    known_cols = set(probe[0].keys()) if probe else None
                except Exception as e:
                    known_cols = None
                    log(f"{outcomes_table} probe failed: {e}", "VERIFIED")
                trimmed = ([{k: v for k, v in rec.items() if k in known_cols} for rec in new_payload]
                           if known_cols else new_payload)
                try:
                    rest_post(outcomes_table, trimmed, prefer="return=minimal")
                    total_inserted += len(trimmed)
                    log(f"Inserted {len(trimmed)} NEW rows into {outcomes_table}", "VERIFIED")
                except urllib.error.HTTPError as e:
                    body = e.read()
                    log(f"{outcomes_table} insert FAILED HTTP {e.code}: {body[:500]}", "VERIFIED")

    log(f"total_patched={total_patched} total_inserted={total_inserted}", "VERIFIED")

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
          "WHERE county='sumter' AND sold_amount IS NOT NULL GROUP BY county, sold_amount_source;")
    print(f"total_patched={total_patched} total_inserted={total_inserted}")
    print(f"BEFORE B: {baseline['B']}")
    print(f"BEFORE F: {baseline['F']}")
    print(f"AFTER  B: {after['B']}")
    print(f"AFTER  F: {after['F']}")


if __name__ == "__main__":
    main()
