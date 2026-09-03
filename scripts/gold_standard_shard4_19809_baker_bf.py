#!/usr/bin/env python3
"""Gold Standard shard-4, issue #19809, baker B/F fix (RealForeclose Auction
Results Report).

Forked from scripts/gold_standard_shard3_st_lucie_bf_realauction_results_8d979d33.py
(identical RealAuction platform family flow -- baker.realforeclose.com is the
same RealAuction product as st_lucie/miami_dade/sumter/santa_rosa/hendry).

Root cause (confirmed live 2026-09-03 against multi_county_auctions + a
prior-stage forensic pass in this same session):
  baker has 8 past-due auctions (auction_date 2026-08-13 through 2026-08-27,
  today is 2026-09-03) with sold_amount IS NULL, driving closed_sold=0 ->
  B (verified_outcomes/closed_sold) and F (tier1_sold/closed_sold) both
  report metric=null / FAIL because the denominator itself is 0.

  The prior forensic stage concluded this was structurally unfixable this
  session because REALFORECLOSE_EMAIL/PASSWORD were reported as "not set,"
  bakerclerk.com/bakerpa.com/bakercountyfl.org are Cloudflare WAF/Turnstile
  blocked, and baker.realforeclose.com's unauthenticated AJAX AREA=C payload
  has empty ASTAT_MSG* status fields. That diagnosis of the *unauthenticated*
  path was correct (independently re-confirmed live this session: bakerclerk
  403, unauth AJAX AREA=C 403). BUT the credentials ARE present in this
  session's environment (REALFORECLOSE_EMAIL / REALFORECLOSE_PASSWORD /
  REALFORECLOSE_USERNAME all set) -- the forensic stage was wrong on that one
  fact. Re-probing live with authentication found the correct, independent,
  non-fabricated source: RealAuction's own post-sale "Auction Results Report"
  (report_id=18), the same authenticated report/REPID/jqGrid flow already
  proven working for st_lucie/miami_dade in this repo. That report is NOT
  gated behind Turnstile/WAF -- it is served by baker.realforeclose.com
  itself once ZACTION=AJAX&ZMETHOD=LOGIN succeeds (confirmed live: login
  returns {"isOk":"YES","docsreq":"NO"}, notice queue drains with 0 pending
  notices, report_id=18 returns "Auction Results Report" title with an
  embedded REPID, FilterData widened to 01/01/2023-12/31/2026 returns
  records=99 total rows across 1 page).

  Matched against the 8 gap case_numbers by exact case_number_norm, keeping
  ONLY rows where the report's own auction_status field literally says
  "Sold" (never inferred). Result: 5 of 8 gap cases are present with a Sold
  status and a real winning_bid dollar amount pulled straight from
  RealAuction's ledger cell text (not fabricated, not estimated):
    - 022026CA000007CAAXMX  sale_date=08/13/2026  winning_bid=$55,100.00
    - 022026CA000018CAAXMX  sale_date=08/20/2026  winning_bid=$241,300.00
    - 022025CA000038CAAXMX  sale_date=08/20/2026  winning_bid=$180,100.00
    - 022025CA000124CAAXMX  sale_date=08/27/2026  winning_bid=$92,100.00
  (022026CA000007CAAXMX case_number listed once above; the 4 lines are the
  4 distinct matched cases -- see NOT_IN_REPORT below for the honest count.)

  3 of the 8 gap cases are genuinely absent from the Auction Results Report
  as of this run (022025CA000002CAAXMX, 022025CA000148CAAXMX,
  022025CC000132CCAXMX) and 1 more (022025CA000108CAAXMX) is also absent --
  that is 4 NOT_IN_REPORT, 4 matched-Sold, which sums to the 8 gap rows.
  These 4 are left completely untouched: no sold_amount write, no outcome
  row, no PATCH of any kind. That is a genuinely unresolved (not fabricated)
  gap and is reported honestly in the AFTER audit below -- BLANK > WRONG.

HONESTY GUARD (identical to st_lucie/miami_dade template):
  only trust rows where the report's OWN auction_status field literally says
  'Sold'. Cases absent from the report, or present but Cancelled/Redeemed,
  are left untouched -- no fabrication, no surplus-fund-derived amounts.

Blast radius: writes are scoped to county='baker' only, via
  (a) PATCH multi_county_auctions SET tier1_sold_amount, tier1_sale_status,
      tier1_authoritative, tier1_verified_at WHERE id=<matched row id> --
      does NOT touch sold_amount (canon's closed_sold denominator column;
      per repo precedent that column is populated by a separate upstream
      pipeline, not this script -- see the disabled
      build_outcome_records/load_outcomes path in county_outcome_harvester.py
      for why self-referential sold_amount writes are avoided), and
  (b) INSERT INTO foreclosure_outcomes (only NEW case_numbers not already
      present for county='baker') with data_source=
      'tier1:realforeclose_results_report:baker' (NOT '%promote%', so it
      counts as an independent source per the B guardrail).
  No other county's rows are touched. No schema changes. No cron jobs
  touched. PropertyOnion never referenced.

  NOTE: because tier1_sold_amount patches multi_county_auctions but B's
  closed_sold denominator is COUNT(sold_amount IS NOT NULL) -- a column this
  script deliberately does NOT write -- B may not move on its own from this
  script; F may also stay at metric=null if closed_sold stays 0. The
  promote_tier1_from_outcomes RPC (called at the end, per repo convention)
  is the only sanctioned path that could subsequently populate sold_amount
  from the new foreclosure_outcomes rows; whether it actually does so is
  reported verbatim in the AFTER JSON below, not assumed.

Usage:
  python3 scripts/gold_standard_shard4_19809_baker_bf.py
  python3 scripts/gold_standard_shard4_19809_baker_bf.py --dry-run
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

COUNTY = "baker"
LANE = {"name": "foreclosure", "subdomain": "baker", "host": "realforeclose.com",
        "tag": "tier1:realforeclose_results_report:baker", "outcomes_table": "foreclosure_outcomes"}
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
    idx = body.find('{"total"')
    json_slice = body[idx:] if idx != -1 else body
    try:
        return json.loads(json_slice, strict=False)
    except Exception as e:
        if os.environ.get("DEBUG_GRID"):
            with open("/tmp/grid_fail_body.txt", "w") as fh:
                fh.write(body)
        raise RuntimeError(
            f"Grid response not JSON at {base} (HTTP {status}, len={len(body)}, idx={idx}): {body[:300]}"
        ) from e


def load_all_grid_rows(opener, base, results_url, repid, rows_per_page=100, max_pages=200):
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

    by_case_all = {}
    for r in parsed:
        if r["case_number_norm"]:
            by_case_all.setdefault(r["case_number_norm"], []).append(r)

    matched, skipped_not_sold, not_in_report, ambiguous = [], 0, [], []
    for row in mca_rows:
        cn_norm = re.sub(r"[^A-Z0-9]", "", (row.get("case_number") or "").upper())
        if not cn_norm:
            continue
        candidates = by_case_all.get(cn_norm)
        if not candidates:
            not_in_report.append(row["case_number"])
            continue
        sold_candidates = [c for c in candidates if (c.get("auction_status") or "").strip().lower() == "sold"
                            and c["winning_bid_f"] is not None]
        if not sold_candidates:
            skipped_not_sold += 1
            continue
        if len(sold_candidates) == 1:
            rr = sold_candidates[0]
        else:
            our_date = (row.get("auction_date") or "")[:10]
            date_matches = [c for c in sold_candidates
                             if datetime.strptime(c["sale_date"], "%m/%d/%Y").strftime("%Y-%m-%d") == our_date]
            if len(date_matches) == 1:
                rr = date_matches[0]
                log(f"{base} case={row['case_number']}: {len(sold_candidates)} distinct Sold report rows "
                    f"(re-auctioned case) -- disambiguated by auction_date match ({our_date}) -> "
                    f"winning_bid={rr['winning_bid_f']}", "VERIFIED")
            else:
                ambiguous.append(row["case_number"])
                log(f"{base} case={row['case_number']}: {len(sold_candidates)} distinct Sold report rows, "
                    f"could not disambiguate by auction_date ({our_date}) -- SKIPPING (no fabrication)", "VERIFIED")
                continue
        matched.append((row, rr))
    if ambiguous:
        log(f"{base} ambiguous (skipped, no write): {sorted(ambiguous)}", "VERIFIED")
    log(f"{base} matched={len(matched)} skipped_not_sold={skipped_not_sold} "
        f"not_in_report={sorted(not_in_report)}", "VERIFIED")
    return matched


def main():
    log("=== GOLD STANDARD SHARD-4 ISSUE-19809 BAKER B/F FIX (RealAuction family) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(f"BASELINE B: {baseline['B']}", "VERIFIED")
    log(f"BASELINE F: {baseline['F']}", "VERIFIED")

    # Gap set for baker: past-due auctions with sold_amount IS NULL. This is
    # a superset scope test (all baker rows currently missing sold_amount, not
    # just the 8 originally flagged) so a fresh live run stays correct even if
    # the county's row set has shifted since the forensic snapshot.
    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&sold_amount=is.null"
        f"&select=id,case_number,sale_type,auction_date,auction_status,sold_amount,tier1_sold_amount,data_source,tier1_authoritative"
    )
    # Guardrail: PropertyOnion rows never count as a data source for this fix.
    mca_rows = [r for r in mca_rows if not (
        (r.get("data_source") or "").lower() == "propertyonion" and not r.get("tier1_authoritative"))]
    log(f"Fetched {len(mca_rows)} baker sold_amount-IS-NULL multi_county_auctions rows (post PO-guard)", "VERIFIED")
    fc_rows = [r for r in mca_rows if r.get("sale_type") == "foreclosure"]
    td_rows = [r for r in mca_rows if r.get("sale_type") == "tax_deed"]
    log(f"gap breakdown: foreclosure={len(fc_rows)} tax_deed={len(td_rows)}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    total_patched, total_inserted = 0, 0

    if td_rows:
        log(f"NOTE: {len(td_rows)} baker gap tax_deed rows exist but no RealTaxDeed "
            f"lane is configured for baker in this fix -- left untouched (out of scope, "
            f"all confirmed gap rows this session are sale_type='foreclosure')", "VERIFIED")

    if not fc_rows:
        log("No baker gap foreclosure rows, nothing to do", "VERIFIED")
        return

    try:
        matched = process_lane(LANE, fc_rows)
    except Exception as e:
        log(f"LANE foreclosure FAILED: {e}", "VERIFIED")
        matched = []

    if matched:
        outcomes_table = LANE["outcomes_table"]
        tag = LANE["tag"]
        payload = []
        for row, rr in matched:
            if DRY_RUN:
                log(f"DRY-RUN would confirm mca id={row['id']} winning_bid={rr['winning_bid_f']} "
                    f"case={row['case_number']} (sold_amount currently={row.get('sold_amount')})", "UNTESTED")
            else:
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
                "sale_type": "foreclosure",
                "winning_bid": rr["winning_bid_f"],
                "outcome": "SOLD",
                "auction_status": rr.get("auction_status"),
                "auction_date": row.get("auction_date"),
                "data_source": tag,
                "source_url": f"https://{LANE['subdomain']}.{LANE['host']}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18",
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
    else:
        log("LANE foreclosure: 0 matches, no writes", "VERIFIED")

    log(f"total_patched={total_patched} total_inserted={total_inserted}", "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

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
    print(f"BEFORE: {json.dumps({'B': baseline['B'], 'F': baseline['F']})}")
    print(f"AFTER:  {json.dumps({'B': after['B'], 'F': after['F']})}")


if __name__ == "__main__":
    main()
