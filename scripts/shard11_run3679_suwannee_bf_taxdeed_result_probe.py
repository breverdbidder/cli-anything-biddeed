#!/usr/bin/env python3
"""GOLD STANDARD shard-11, county=suwannee, run3679 (2026-07-11 follow-up session).

Session goal: B and F were failing (verified=0/tier1_sold=0, closed_sold=0 -- both
KPIs divide by closed_sold = count(*) FILTER (WHERE sold_amount IS NOT NULL)). Prior
session (see gold_standard_shard11_suwannee_a_i_fix.py) had already established A is
structurally blocked (0 live foreclosure listings). This session re-verified A fresh
(still blocked, unchanged) and investigated a NEW lever surfaced by live SQL: 2 of the
9 tax-deed rows (case_number 4666, 4667; auction_date=2026-07-09) have an auction_date
in the past relative to today (2026-07-11) while still carrying auction_status=
'upcoming'. If those 2 auctions had actually resulted/sold, that would be the FIRST
non-zero closed_sold value for this county and would let B/F be computed for the
first time.

METHOD (bare curl gets HTTP 403 from suwannee.realtaxdeed.com's WAF -- must use a
real desktop User-Agent, confirmed live this session):

  1. GET the calendar (zaction=USER&zmethod=CALENDAR). The 07/09/2026 day cell
     carries a real, live-updated 'CALACT / CALSCH' counter (Active/completed count
     vs Scheduled count) baked directly into the HTML: this session found
     CALACT=0, CALSCH=2 -- i.e. the clerk's own site says 0 of the 2 scheduled
     tax-deed auctions for that date have completed, fetched twice for consistency.

  2. Hit the same AJAX endpoint used by scripts/shard2_run2450_ajax_realforeclose_harvest.py
     (zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA={W,C}&AUCTIONDATE=07/09/2026&PageDir=0)
     against Zmethod=PREVIEW (returns the 2 real AITEM blocks, case 4666/4667, exact
     parcel_id + address match to our DB rows -- confirms live site and our DB agree
     on WHICH auctions these are) and Zmethod=RESULTS (returns an EMPTY rlist for both
     AREA=W and AREA=C -- the results grid has zero rows, i.e. no sale has been
     posted).

  3. In the PREVIEW AITEM blocks, the ASTAT_MSGA/B/C/D and ASTAT_MSG_SOLDTO_MSG divs
     (where a winning bidder / sold status would be rendered once the site has a
     result) are all empty strings for both cases.

  4. Independent cross-check via the Suwannee County Property Appraiser's GSA-corp
     parcel-detail pages (same source as the prior session's I-fix,
     suwannee-search.gsacorp.io/parcel/<TRS-prefixed-parcel-id>) for both parcels:
     the most recent Document/Transfer/Sales History entry is 2009-01-01 (case 4666,
     parcel 1104S12E10591001000, Warranty Deed, Grantor JOHNSON TIMOTHY, $20,000) and
     1996-04-01 (case 4667, parcel 1402S11E11016001003, Warranty Deed, Grantor GARCIA
     JORGE & LOIDA ELVIA, $19,000) respectively. No new 2026 deed is recorded on
     either parcel's own transfer history, which is the strongest independent
     confirmation available (deed recordation lags the auction by days-to-weeks, but
     a court/clerk RESULTS grid with zero entries + zero SOLDTO text is decisive on
     its own).

CONCLUSION: all 4 independent signals agree the 07/09/2026 tax-deed sale has NOT been
resulted/recorded yet -- the clerk has not posted outcomes, despite auction_date being
technically in the past relative to today. This is a stale *timing* label (the row
should arguably be requeried more frequently as its date approaches/passes), but it is
NOT evidence of a sale that our pipeline is failing to capture. Per HARD RULES (fail-
loud, BLANK > WRONG), no auction_status was changed, no sold_amount was written, and no
tax_deed_outcomes row was inserted. B and F remain correctly blocked at closed_sold=0
this session -- this is real county state, not a pipeline gap.

RESIDUAL / FOR A FUTURE SESSION: re-run this exact probe (or a scheduled cron variant)
every few days. The moment CALACT flips from 0 to >0 on suwannee.realtaxdeed.com for
this date (or the RESULTS AJAX rlist becomes non-empty), that is the trigger to:
  1. parse the ASTAT_MSG_SOLDTO_MSG winner name + winning bid amount from the AITEM
     block (same parser as scripts/shard2_run2450_ajax_realforeclose_harvest.py /
     scripts/fill_opening_bids_brevard_duval.py already handle this HTML shape)
  2. UPDATE multi_county_auctions SET sold_amount=..., auction_status='closed' (or
     'sold') WHERE case_number IN ('4666','4667')
  3. INSERT one tax_deed_outcomes row per case with data_source starting with
     'realauction_ajax_results:' (NOT 'promote'/'propertyonion' -- independent source)
  4. re-run pencil_dod_evaluate_county('suwannee') to confirm B/F move off null

This script is READ-ONLY / probe-only; no writes were made to Supabase this session.
Re-running requires network egress to suwannee.realforeclose.com,
suwannee.realtaxdeed.com, and suwannee-search.gsacorp.io.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

# Verbatim decode table from scripts/shard2_run2450_ajax_realforeclose_harvest.py
AJAX_SUBS = [
    ("@A", '<div class="'),
    ("@B", "</div>"),
    ("@C", 'class="'),
    ("@D", "<div>"),
    ("@E", "AUCTION"),
    ("@F", "</td><td"),
    ("@G", "</td></tr>"),
    ("@H", "<tr><td "),
    ("@I", "table"),
    ("@J", 'p_back="NextCheck='),
    ("@K", 'style="Display:none"'),
    ("@L", "/index.cfm?zaction=auction&zmethod=details&AID="),
]

TARGET_CASES = {
    "4666": {"parcel_id": "10591001000", "gsa_parcel_id": "1104S12E10591001000"},
    "4667": {"parcel_id": "11016001003", "gsa_parcel_id": "1402S11E11016001003"},
}
AUCTION_DATE_MMDDYYYY = "07/09/2026"
BASE = "https://suwannee.realtaxdeed.com"


def _get(url, cj=None, headers=None):
    hdrs = {"User-Agent": UA_DESKTOP}
    if headers:
        hdrs.update(headers)
    if cj is not None:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        req = urllib.request.Request(url, headers=hdrs)
        return opener.open(req, timeout=20).read().decode("utf-8", errors="replace")
    req = urllib.request.Request(url, headers=hdrs)
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", errors="replace")


def decode_ajax_html(ret_html):
    rh = ret_html
    for token, replacement in AJAX_SUBS:
        rh = rh.replace(token, replacement)
    return rh


def strip_html(s):
    if not s:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(s))).strip() or None


def check_calendar_status():
    """Returns (calact, calsch) for AUCTION_DATE_MMDDYYYY, or None if not found."""
    html = _get(f"{BASE}/index.cfm?zaction=USER&zmethod=CALENDAR")
    dayid = AUCTION_DATE_MMDDYYYY
    idx = html.find(f"dayid='{dayid}'")
    if idx < 0:
        return None
    window = html[idx:idx + 400]
    m = re.search(r'CALACT">(\d+)</span> / <span class="CALSCH">(\d+)', window)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def fetch_ajax(zmethod, cj=None):
    """Fetch PREVIEW/RESULTS shell + AJAX FNC=LOAD grid; returns (aitem_blocks, rlists)."""
    if cj is None:
        cj = http.cookiejar.CookieJar()
    preview_url = f"{BASE}/index.cfm?zaction=AUCTION&Zmethod={zmethod}&AUCTIONDATE={AUCTION_DATE_MMDDYYYY}"
    _get(preview_url, cj)
    aitems, rlists = [], {}
    for area in ("W", "C"):
        prev_rlist = None
        for page_dir in range(5):
            ts = int(time.time() * 1000)
            ajax_url = (f"{BASE}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                        f"&AREA={area}&AUCTIONDATE={urllib.parse.quote(AUCTION_DATE_MMDDYYYY)}"
                        f"&PageDir={page_dir}&doR=0&tx={ts}&bypassPage=0&test=1")
            try:
                body = _get(ajax_url, cj, headers={"Referer": preview_url,
                                                     "X-Requested-With": "XMLHttpRequest"})
            except (urllib.error.URLError, TimeoutError):
                break
            try:
                data = json.loads(body)
            except Exception:
                break
            rlist = data.get("rlist") or ""
            rlists[f"{area}_{page_dir}"] = rlist
            if not rlist or rlist == prev_rlist:
                break
            prev_rlist = rlist
            ret_html = data.get("retHTML") or ""
            if ret_html:
                decoded = decode_ajax_html(ret_html)
                starts = [m.start() for m in re.finditer(r'<div\s+id="AITEM_\d+"', decoded)]
                starts.append(len(decoded))
                for i in range(len(starts) - 1):
                    b = decoded[starts[i]:starts[i + 1]]
                    aidm = re.search(r'aid="(\d+)"', b)
                    if not aidm:
                        continue
                    case_m = re.search(r'Case #:</td>\s*<td[^>]*>\s*([0-9]+)', b)
                    sold_m = re.search(r'ASTAT_MSG_SOLDTO_MSG[^>]*>([^<]*)</div>', b)
                    aitems.append({
                        "aid": aidm.group(1),
                        "case_number": strip_html(case_m.group(1)) if case_m else None,
                        "sold_to_text": strip_html(sold_m.group(1)) if sold_m else None,
                    })
            time.sleep(0.3)
    return aitems, rlists


def check_pa_transfer_history(gsa_parcel_id):
    """Returns the most recent transfer-history date string found, or None."""
    html = _get(f"https://suwannee-search.gsacorp.io/parcel/{gsa_parcel_id}")
    text = re.sub(r"\s+", " ", re.sub(r"\|+", "|", re.sub(r"<[^>]+>", "|", html)))
    m = re.search(r"Sales History\|[^|]*\|Instrument /\|Official Record\|Official Record\|Date\|"
                  r"Type\|V/I\|Sale Price\|Ownership\|Red Flag\|[A-Z]+\| \|[\d/]+\|[\d/]+\|"
                  r"([\d-]+)\|([^|]+)\|", text)
    return (m.group(1), m.group(2)) if m else None


def main():
    print("=== A re-check: suwannee.realforeclose.com (foreclosure lane) ===")
    fc_html = _get("https://suwannee.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR")
    dayid_count = len(re.findall(r"dayid='", fc_html))
    print(f"  HTTP 200, {len(fc_html)} bytes, {dayid_count} highlighted auction days -> "
          f"{'BLOCKED (0 listings, confirmed)' if dayid_count == 0 else 'UNEXPECTED -- listings now present, investigate'}")

    print("\n=== B/F lever check: cases 4666/4667 (auction_date 07/09/2026) ===")
    cal = check_calendar_status()
    print(f"  Calendar CALACT/CALSCH for {AUCTION_DATE_MMDDYYYY}: {cal}")

    preview_items, _ = fetch_ajax("PREVIEW")
    print(f"  PREVIEW AITEM blocks found: {len(preview_items)}")
    for it in preview_items:
        print(f"    case={it['case_number']} aid={it['aid']} sold_to_text={it['sold_to_text']!r}")

    _, results_rlists = fetch_ajax("RESULTS")
    print(f"  RESULTS AJAX rlists: {results_rlists}")

    print("\n=== Independent PA transfer-history cross-check ===")
    for case, meta in TARGET_CASES.items():
        th = check_pa_transfer_history(meta["gsa_parcel_id"])
        print(f"  case {case} ({meta['gsa_parcel_id']}): most recent transfer = {th}")

    print("\nCONCLUSION: if CALACT==0, RESULTS rlists are all empty, sold_to_text is "
          "empty for both AITEMs, and PA transfer-history shows no 2026 entry -- the "
          "sale has NOT resulted. Do not write sold_amount/auction_status/tax_deed_outcomes.")


if __name__ == "__main__":
    main()
