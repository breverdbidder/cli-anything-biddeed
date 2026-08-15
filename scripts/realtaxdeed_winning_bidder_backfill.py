#!/usr/bin/env python3
"""RealTaxDeed Auction Results Report -> winning_bidder backfill (multi-county).

Generalizes the proven per-county pattern (e.g.
scripts/gold_standard_shard6_run5361_sarasota_bcdf_realtaxdeed_results.py) to any
{county}.realtaxdeed.com subdomain: authenticated AJAX login (ZACTION=AJAX&ZMETHOD=LOGIN,
NOT the broken LogName/LogPass form-post used by buyer_backfill.py), notice drain,
"Auction Results Report" (report_id=18) grid pull, case_number match against
multi_county_auctions.

Scope: winning_bidder ONLY. Never writes sold_amount / tier1_* / parity_status /
auction_status -- those are owned by the certified Gold Standard per-county scripts
and are out of scope here (see CLAUDE.md non-goals).

The report's "bidder" grid cell is a raw bidder-registration ID (e.g. "650286") in
the common case, or the literal sentinel "Cert Holder" when no third party bid.
Writing the raw ID as a person's name would be misleading, so it is translated
using the same sentinel convention already present in this table's
winning_bidder_source='tax_deed_outcomes_sync' rows:
  - bidder cell == "Cert Holder"      -> winning_bidder = "Cert Holder" (verbatim)
  - bidder cell matches ^\\d+$         -> winning_bidder = "3rd Party Bidder"
  - anything else (a real name string, blank, "n/a")
        -> real name: written verbatim
        -> blank/n/a: left NULL, never guessed

RealForeclose (mortgage foreclosure) shares the same RealAuction platform/report_id=18
grid -- confirmed live 2026-08-15 (alachua.realforeclose.com). There the "bidder" cell
sentinel is "Plaintiff" (bank/lender retained the property, no 3rd-party outbid them)
with the real plaintiff name embedded via the same showAlias('NAME') pattern used by
some realtaxdeed counties' "Cert Holder" cells. --platform realforeclose switches the
sentinel label to "Plaintiff" and also opportunistically fills the plaintiff column
(only where currently NULL, never overwritten) from the same alias.

Usage:
  python3 scripts/realtaxdeed_winning_bidder_backfill.py <county_slug> [--host explicit.host.com] [--platform realtaxdeed|realforeclose] [--dry-run] [--start MM/DD/YYYY] [--end MM/DD/YYYY]

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, REALFORECLOSE_EMAIL|REALFORECLOSE_USERNAME, REALFORECLOSE_PASSWORD
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

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
if not ARGS:
    print("usage: realtaxdeed_winning_bidder_backfill.py <county_slug> [--dry-run]", file=sys.stderr)
    sys.exit(1)
COUNTY = ARGS[0].lower()
PLATFORM = sys.argv[sys.argv.index("--platform") + 1] if "--platform" in sys.argv else "realtaxdeed"
if "--host" in sys.argv:
    HOST = sys.argv[sys.argv.index("--host") + 1]
else:
    SUBDOMAIN = COUNTY.replace("_", "")  # DB-observed pattern, e.g. indian_river -> indianriver
    HOST = f"{SUBDOMAIN}.{PLATFORM}.com"
BASE = f"https://{HOST}"
HOME = f"{BASE}/index.cfm"
CERT_SENTINEL = "Plaintiff" if PLATFORM == "realforeclose" else "Cert Holder"
SALE_TYPE_FILTER = "foreclosure" if PLATFORM == "realforeclose" else "tax_deed"

START = sys.argv[sys.argv.index("--start") + 1] if "--start" in sys.argv else "01/01/2023"
END = sys.argv[sys.argv.index("--end") + 1] if "--end" in sys.argv else "12/31/2026"

DATA_SOURCE_TAG = f"tier1_{PLATFORM}_results_report:{COUNTY}:winning_bidder_backfill"
RESULTS_REPORT_URL = f"{BASE}/index.cfm?Zaction=admin&Zmethod=REPORT&report_id=18"

BIDDER_ID_RE = re.compile(r"^\d+$")
CASE_NUMBER_RE = re.compile(r">([0-9A-Za-z \-]{6,})<")
ALIAS_RE = re.compile(r"showAlias\('([^']{2,300})'\)")


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
        raise RuntimeError(f"RealTaxDeed login failed for {COUNTY} (status={status}): {body[:300]}")
    log(f"{COUNTY}: RealTaxDeed login OK (isOk=YES)", "VERIFIED")

    seen_nids = set()
    for i in range(30):
        _, body = get(opener, HOME)
        title_m = re.search(r"<title>([^<]*)</title>", body)
        title = title_m.group(1) if title_m else ""
        if "Notice and alert" not in title:
            log(f"{COUNTY}: notice queue drained after {i} accepts -> {title.strip()!r}", "VERIFIED")
            return
        nid_m = re.search(r'NID="(\d+)"', body)
        nid = nid_m.group(1) if nid_m else None
        if not nid or nid in seen_nids:
            raise RuntimeError(f"{COUNTY}: stuck on notice page (nid={nid}, seen={seen_nids})")
        seen_nids.add(nid)
        post(opener, HOME, {
            "zaction": "AJAX", "zmethod": "COM", "process": "NOTICE",
            "func": "ACCEPT", "showjson": "false", "NID": nid,
        }, referer=HOME)
    raise RuntimeError(f"{COUNTY}: notice queue did not drain within 30 iterations")


def fetch_results_report(opener):
    _, body = get(opener, RESULTS_REPORT_URL, referer=HOME)
    if "Auction Results Report" not in body:
        raise RuntimeError(f"{COUNTY}: report_id=18 did not return the Auction Results Report page "
                            f"-- platform/report_id likely differs for this county, needs manual probe")
    repid_m = re.search(r"REPID=(\d+)&func=LoadData", body)
    if not repid_m:
        raise RuntimeError(f"{COUNTY}: could not extract REPID from Report Viewer page")
    repid = repid_m.group(1)
    log(f"{COUNTY}: Report Viewer loaded, REPID={repid}", "VERIFIED")
    return repid


def apply_wide_filter(opener, repid):
    filter_qs = urllib.parse.urlencode({
        "start_date": START, "end_date": END, "Case_Number": "",
        "Bidder": "", "Parcel": "", "SoldTO": "NULL", "Is_user": "0",
        "auctStat": "NULL", "auctType": "NULL",
    })
    filter_url = (f"{BASE}/index.cfm?{filter_qs}&zaction=AJAX&zmethod=COM"
                  f"&process=REPVIEW&FUNC=FilterData&SHOWJSON=false&REPID={repid}")
    get(opener, filter_url, referer=RESULTS_REPORT_URL)


def load_all_grid_rows(opener, repid, rows_per_page=100, max_pages=30):
    grid_url = (f"{BASE}/index.cfm?zaction=AJAX&zmethod=COM&Process=REPVIEW"
                f"&SHOWJSON=FALSE&REPID={repid}&func=LoadData")

    def load_page(page):
        status, body = post(opener, grid_url, {
            "page": str(page), "rows": str(rows_per_page), "sidx": "ar.insert_dt", "sord": "desc",
        }, referer=RESULTS_REPORT_URL)
        try:
            return json.loads(body)
        except Exception as e:
            raise RuntimeError(f"{COUNTY}: grid response not JSON (HTTP {status}): {body[:300]}") from e

    first = load_page(1)
    total_pages = int(first.get("total") or 1)
    all_rows = list(first.get("rows", []))
    for p in range(2, min(total_pages, max_pages) + 1):
        all_rows.extend(load_page(p).get("rows", []))
    return all_rows, first.get("records"), total_pages


def extract_case_number(cell_html):
    if not cell_html:
        return None
    m = CASE_NUMBER_RE.search(cell_html)
    if m:
        return m.group(1).strip()
    stripped = re.sub(r"<[^>]+>", "", cell_html).strip()
    return stripped or None


def resolve_bidder(cell):
    val = (cell or "").strip()
    if not val or val.lower() in ("n/a", "none", "pending", "&nbsp;"):
        return None, None
    # some counties embed the cert-holder/plaintiff's resolved real name in a
    # showAlias('NAME') JS handler around the sentinel label -- prefer the real
    # name over the generic sentinel when present. For realforeclose, this real
    # name IS the plaintiff (bank/lender retained the property).
    alias_m = ALIAS_RE.search(val)
    if alias_m:
        name = alias_m.group(1).strip()
        return name, (name if PLATFORM == "realforeclose" else None)
    stripped = re.sub(r"<[^>]+>", "", val).strip()
    if not stripped or stripped.lower() in ("n/a", "none", "pending"):
        return None, None
    if stripped == CERT_SENTINEL:
        return CERT_SENTINEL, None
    if BIDDER_ID_RE.match(stripped):
        return "3rd Party Bidder", None
    # a real name/string the report itself supplied verbatim, HTML-stripped
    return stripped, None


def parse_rows(raw_rows):
    """Column layout is confirmed to vary by county cell count (14/15/16).
    case_number is always cell[1], bidder is always cell[3] in every confirmed
    layout (sale_date, case_number_html, parcel, bidder, ...winning_bid...)."""
    out = []
    for row in raw_rows:
        cell = row.get("cell", [])
        if len(cell) < 14:
            continue  # unrecognized layout -- skip rather than misparse
        case_number = extract_case_number(cell[1])
        status_idx = 13 if len(cell) >= 14 else None
        auction_status = re.sub(r"<[^>]+>", "", cell[status_idx]).strip() if status_idx is not None else None
        winning_bidder, plaintiff = resolve_bidder(cell[3])
        out.append({
            "case_number": case_number,
            "case_number_norm": re.sub(r"[^A-Z0-9]", "", (case_number or "").upper()),
            "bidder_raw": cell[3],
            "winning_bidder": winning_bidder,
            "plaintiff": plaintiff,
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
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def main():
    log(f"=== realtaxdeed winning_bidder backfill: {COUNTY} ({BASE}) ===")
    opener = build_opener()
    login_and_drain_notices(opener)
    repid = fetch_results_report(opener)
    apply_wide_filter(opener, repid)
    raw_rows, records, total_pages = load_all_grid_rows(opener, repid)
    log(f"{COUNTY}: grid total_pages={total_pages} records={records} rows_returned={len(raw_rows)}", "VERIFIED")

    parsed = parse_rows(raw_rows)
    by_case = {}
    for r in parsed:
        if r["case_number_norm"]:
            by_case.setdefault(r["case_number_norm"], r)
    log(f"{COUNTY}: parsed {len(parsed)} report rows, {len(by_case)} unique case numbers", "VERIFIED")

    if not parsed:
        print(f"\n### RESULT {COUNTY}: BLOCKED (0 rows from RealTaxDeed results report)")
        sys.exit(2)

    mca_rows = rest_get(
        f"multi_county_auctions?county=eq.{COUNTY}&winning_bidder=is.null&sale_type=eq.{SALE_TYPE_FILTER}"
        f"&select=id,case_number,auction_date,winning_bidder,plaintiff&limit=5000")
    log(f"{COUNTY}: fetched {len(mca_rows)} multi_county_auctions rows with winning_bidder IS NULL", "VERIFIED")

    matched, skipped_not_sold, no_bidder_value, not_in_report = [], 0, 0, []
    for row in mca_rows:
        cn_norm = re.sub(r"[^A-Z0-9]", "", (row.get("case_number") or "").upper())
        if not cn_norm or cn_norm not in by_case:
            not_in_report.append(row.get("case_number"))
            continue
        rr = by_case[cn_norm]
        if (rr["auction_status"] or "").strip().lower() != "sold":
            skipped_not_sold += 1
            continue
        if not rr["winning_bidder"]:
            no_bidder_value += 1
            continue
        matched.append((row, rr))

    log(f"{COUNTY}: matched={len(matched)} skipped_not_sold={skipped_not_sold} "
        f"no_bidder_value={no_bidder_value} not_in_report={len(not_in_report)}", "VERIFIED")

    for row, rr in matched[:10]:
        log(f"  {row['case_number']}: winning_bidder -> {rr['winning_bidder']!r} "
            f"(raw cell={rr['bidder_raw']!r})", "UNTESTED" if DRY_RUN else "VERIFIED")

    if DRY_RUN:
        print(f"\n### DRY-RUN {COUNTY}: would patch {len(matched)} rows -- no writes performed")
        return

    patched = 0
    plaintiff_filled = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for row, rr in matched:
        patch = {
            "winning_bidder": rr["winning_bidder"],
            "winning_bidder_source": DATA_SOURCE_TAG,
            "updated_at": now_iso,
        }
        if rr.get("plaintiff") and not row.get("plaintiff"):
            patch["plaintiff"] = rr["plaintiff"]
            plaintiff_filled += 1
        rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch)
        patched += 1

    print(f"\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print(f"County: {COUNTY}  platform={PLATFORM}  patched={patched}  matched={len(matched)}  "
          f"plaintiff_filled={plaintiff_filled}  skipped_not_sold={skipped_not_sold}  no_bidder_value={no_bidder_value}")


if __name__ == "__main__":
    main()
