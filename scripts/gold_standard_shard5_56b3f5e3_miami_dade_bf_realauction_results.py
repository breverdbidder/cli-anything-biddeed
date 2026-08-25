#!/usr/bin/env python3
"""Gold Standard shard-5, dispatch 56b3f5e3, miami_dade B/F fix (RealForeclose +
RealTaxDeed Auction Results Reports).

Forked from scripts/gold_standard_shard6_run6148_sumter_bf_realauction_results.py
(identical RealAuction platform family flow, confirmed live 2026-08-25 for
miamidade.realforeclose.com and miamidade.realtaxdeed.com -- both return HTTP
200 with a normal browser User-Agent, same "RealForeclose/RealTaxDeed" splash
page family as sumter/santa_rosa/hendry/etc).

Root cause (confirmed live 2026-08-25 against multi_county_auctions):
  miami_dade has 24 closed_sold rows (sold_amount IS NOT NULL, all
  sale_type='foreclosure', auction_status='sold'). B (letter) requires each
  closed_sold row to have an INDEPENDENT corroborating row in
  foreclosure_outcomes/tax_deed_outcomes (data_source NOT ILIKE '%promote%').
  Only 5 of 24 have one today (data_source='realforeclose_miami_dade_po_confirmed',
  a PropertyOnion-sourced outcome from a prior session) -> B=20.8%, FAIL
  (canon requires 95-105%). F requires tier1_sold_amount IS NOT NULL on the
  mca row itself (in addition to sold_amount) -> 15 of 24 have it -> F=62.5%,
  FAIL (canon requires >=95%).

Fix: miami_dade runs the standard RealAuction platform for BOTH lanes
  (foreclosure_url=miamidade.realforeclose.com; taxdeed_url=
  miamidade.realtaxdeed.com). This is the fleet's canonical Letter-B/F
  playbook: Auction Results Report (report_id=18) is the Clerk/RealAuction
  backend's own post-sale ledger -- independent of our pre-sale
  calendar-sweep scrape, independent of the existing PropertyOnion-derived
  outcomes rows, and independent of the realauction_bidhistory_modal winner
  harvest that already populated sold_amount on the mca rows themselves.

miami_dade-specific delta from the sumter template (miami_dade is a much
larger/busier county -- confirmed live: thousands of historical rows in the
Auction Results Report vs sumter's 11):
  - Only insert an outcome row when BOTH (a) the case_number exists in
    miami_dade's multi_county_auctions closed_sold set AND (b) the report's
    own status field says "Sold" for that case -- never insert unmatched
    report rows wholesale (matches template's honesty guard, just called out
    explicitly here since miami_dade's report body is orders of magnitude
    bigger than sumter's).
  - foreclosure_outcomes schema for this fleet uses `winning_bid`, not
    `sold_amount` (confirmed live via existing miami_dade rows sourced
    'realforeclose_miami_dade_po_confirmed') -- the template's dynamic
    known_cols probe+trim already handles this without a schema assumption.
  - All 24 closed_sold miami_dade rows are sale_type='foreclosure' (confirmed
    live query) -- the taxdeed lane is exercised defensively (0 rows -> no-op)
    in case future closed tax_deed rows appear, matching template symmetry.

HONESTY GUARD (identical to sumter/santa_rosa/hendry): only trust rows where
the report's OWN auction_status field literally says 'Sold'. Cases absent
from the report, or present but Cancelled/Redeemed, are left untouched -- no
fabrication, no surplus-fund-derived amounts.

Usage:
  python3 scripts/gold_standard_shard5_56b3f5e3_miami_dade_bf_realauction_results.py
  python3 scripts/gold_standard_shard5_56b3f5e3_miami_dade_bf_realauction_results.py --dry-run
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

COUNTY = "miami_dade"
LANES = [
    {"name": "foreclosure", "subdomain": "miamidade", "host": "realforeclose.com",
     "tag": "tier1:realforeclose_results_report:miami_dade", "outcomes_table": "foreclosure_outcomes"},
    {"name": "taxdeed", "subdomain": "miamidade", "host": "realtaxdeed.com",
     "tag": "tier1:realtaxdeed_results_report:miami_dade", "outcomes_table": "tax_deed_outcomes"},
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
    # miami_dade (unlike sumter) wraps the jqGrid JSON in ~800+ chars of leading
    # whitespace/template noise before the actual `{"total": ...}` payload
    # (confirmed live 2026-08-25). Locate the JSON start explicitly instead of
    # assuming the whole body is JSON.
    idx = body.find('{"total"')
    json_slice = body[idx:] if idx != -1 else body
    try:
        # miami_dade's LoadData response embeds raw unescaped control
        # characters (literal tabs) inside some plaintiff-name cell strings
        # (confirmed live 2026-08-25, e.g. "...Residential Accredit \tLoans,
        # Inc...") which strict-mode json rejects. sumter's smaller dataset
        # never hit this; strict=False tolerates it without changing values.
        return json.loads(json_slice, strict=False)
    except Exception as e:
        if os.environ.get("DEBUG_GRID"):
            with open("/tmp/grid_fail_body.txt", "w") as fh:
                fh.write(body)
        raise RuntimeError(
            f"Grid response not JSON at {base} (HTTP {status}, len={len(body)}, idx={idx}): {body[:300]}"
        ) from e


def load_all_grid_rows(opener, base, results_url, repid, rows_per_page=100, max_pages=200):
    """miami_dade is much larger than sumter (thousands of historical rows vs
    11) -- max_pages raised from the template's 20 to 200 (up to 20,000 rows
    at 100/page) so the wide 2023-2026 date filter doesn't get silently
    truncated for a busy county."""
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
    (hendry-style) since we don't know miami_dade's variant ahead of time."""
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
    log("=== GOLD STANDARD SHARD-5 DISPATCH-56b3f5e3 MIAMI_DADE B/F FIX (RealAuction family) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")
    log(f"BASELINE F: {baseline['F']}", "VERIFIED")

    # Only closed_sold rows matter for B/F -- scope the report-match universe
    # to exactly what the evaluator counts, not all 594 miami_dade rows.
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sold_amount=not.is.null"
        f"&select=id,case_number,sale_type,auction_date,auction_status,sold_amount,sold_amount_source,tier1_sold_amount,data_source")
    log(f"Fetched {len(mca_rows)} miami_dade closed_sold multi_county_auctions rows", "VERIFIED")
    fc_rows = [r for r in mca_rows if r.get("sale_type") == "foreclosure"]
    td_rows = [r for r in mca_rows if r.get("sale_type") == "tax_deed"]
    log(f"closed_sold breakdown: foreclosure={len(fc_rows)} tax_deed={len(td_rows)}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_patched, total_inserted = 0, 0

    for lane, rows in (("foreclosure", fc_rows), ("taxdeed", td_rows)):
        lane_cfg = next(l for l in LANES if l["name"] == lane)
        if not rows:
            log(f"No miami_dade closed_sold rows for lane={lane}, skipping", "VERIFIED")
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
                log(f"DRY-RUN would confirm mca id={row['id']} winning_bid={rr['winning_bid_f']} "
                    f"case={row['case_number']} (sold_amount already={row.get('sold_amount')})", "UNTESTED")
            else:
                # sold_amount already populated on these rows via the winner-harvest
                # pipeline; we do NOT overwrite it here (that value has its own
                # provenance). We DO set tier1_sold_amount/tier1_* so Letter F can
                # see it, and rely on the independent outcomes-table INSERT below
                # for Letter B's corroboration requirement.
                rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {
                    "tier1_sold_amount": rr["winning_bid_f"],
                    "tier1_sale_status": "sold",
                    "tier1_authoritative": True,
                    "tier1_verified_at": now_iso,
                })
                total_patched += 1
            rec = {
                "case_number": row["case_number"],
                "county": COUNTY,
                "sale_type": lane if lane == "foreclosure" else "tax_deed",
                "winning_bid": rr["winning_bid_f"],
                "outcome": "SOLD",
                "auction_status": rr.get("auction_status"),
                "auction_date": row.get("auction_date"),
                "data_source": tag,
                "source_url": f"https://{lane_cfg['subdomain']}.{lane_cfg['host']}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18",
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
            already_covered = len(payload) - len(new_payload)
            if already_covered:
                log(f"{outcomes_table}: {already_covered} matched cases already have an independent outcome row (skipped, no dup)",
                    "VERIFIED")
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

    # Carry sold amounts from outcomes tables into multi_county_auctions.tier1_sold_amount
    # (Letter F's actual denominator source) via the fleet's canonical promote RPC.
    try:
        promote_result = rpc("promote_tier1_from_outcomes", {})
        log(f"promote_tier1_from_outcomes -> {promote_result}", "VERIFIED")
    except Exception as e:
        promote_result = None
        log(f"promote_tier1_from_outcomes FAILED: {e}", "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"AFTER B: {after['B']}", "VERIFIED")
    log(f"AFTER F: {after['F']}", "VERIFIED")

    now_iso2 = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso2}")
    print("SELECT county, sold_amount_source, COUNT(*) FROM multi_county_auctions "
          "WHERE county='miami_dade' AND sold_amount IS NOT NULL GROUP BY county, sold_amount_source;")
    print(f"total_patched={total_patched} total_inserted={total_inserted} promote_result={promote_result}")
    print(f"BEFORE B: {baseline['B']}")
    print(f"BEFORE F: {baseline['F']}")
    print(f"AFTER  B: {after['B']}")
    print(f"AFTER  F: {after['F']}")


if __name__ == "__main__":
    main()
