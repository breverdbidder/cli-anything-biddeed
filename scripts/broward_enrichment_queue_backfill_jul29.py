#!/usr/bin/env python3
"""
broward_enrichment_queue_backfill_jul29.py

Backfills opening_bid + assessed_value for the 25 Broward County foreclosure
lots enqueued in auction_enrichment_queue (enqueued_by=claude-chat-audit-jul29).

Root cause: broward.realforeclose.com migrated to an AJAX-templated auction
listing (zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD&AREA={R|W|C}) instead of the
older server-rendered PREVIEW page used by Brevard/Duval. The static PREVIEW
page still renders (title "Preview Items For Sale") but its Running/Waiting/
Closed sections are empty placeholders filled in client-side by that AJAX
call — no login required, confirmed anonymous access works.

Pipeline per auction_date present in the queue:
  1. GET the PREVIEW page for that date (primes session context server-side).
  2. For AREA in R (running), W (waiting), C (closed/canceled):
       paginate FNC=LOAD (PageDir=0 first call, then PageDir=1) until a page
       returns no new AIDs, parsing the @-token-templated AITEM blocks for
       case_number / judgment_amount ("Final Judgment Amount") / parcel_id.
  3. Match parsed case_numbers against the 25 queued Broward cases.
  4. For each match: PATCH multi_county_auctions.opening_bid = judgment_amount.
  5. If parcel_id is a lookupable BCPA folio, fetch assessed_value/market_value
     from web.bcpa.net and PATCH those too.
  6. Mark the queue row 'completed' with fields_enriched for anything patched.
     Unmatched rows are left 'queued' and reported as misses — no fabrication.

Env required: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from datetime import datetime, timezone

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
HOST = "https://broward.realforeclose.com"
BCPA_ENDPOINT = "https://web.bcpa.net/BcpaClient/search.aspx/getParcelInformation"
FOLIO_RE = re.compile(r"^\d{4,6}[A-Z]{0,2}\d{2,6}$")
CASE_RE = re.compile(r"^(?:CACE|COCE|CONO)-\d\d-\d+$")

# ── Supabase REST helpers ─────────────────────────────────────────────────────
def _H(extra=None):
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h

def sb_get(path, params=""):
    url = f"{SB_URL}/rest/v1/{path}"
    if params:
        url += ("&" if "?" in path else "?") + params
    req = urllib.request.Request(url, headers=_H())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def sb_patch(path, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{path}", data=body, headers=_H(), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

# ── broward.realforeclose.com scraping ────────────────────────────────────────
def money_to_float(s):
    if not s:
        return None
    m = re.search(r"\$?([\d,]+\.?\d*)", str(s))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None

ITEM_RE = re.compile(
    r'<div id="AITEM_(\d+)".*?aid="(\d+)".*?'
    r'Case #:@F @CAD_DTA">.*?>([A-Z]+-\d\d-\d+)</a>.*?'
    r'Final Judgment Amount:@F tabindex="0" @CAD_DTA">([^@]*?)@G'
    r'(?:.*?Parcel ID:@F tabindex="0"@CAD_DTA">(?:<a[^>]*>([^<]*)</a>|([^@]*?)@G))?',
    re.DOTALL,
)

def parse_area_items(ret_html):
    items = {}
    for m in ITEM_RE.finditer(ret_html):
        aid, aid2, case_number, judgment_raw, parcel_a, parcel_b = m.groups()
        parcel_id = (parcel_a or parcel_b or "").strip() or None
        items[case_number] = {
            "aid": aid,
            "case_number": case_number,
            "judgment_amount": money_to_float(judgment_raw),
            "parcel_id": parcel_id,
        }
    return items

class BrowardRF:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def _get(self, url, hdrs=None):
        r = urllib.request.Request(url, headers={"User-Agent": UA, **(hdrs or {})})
        try:
            with self.opener.open(r, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  GET {url} error: {e}", file=sys.stderr)
            return ""

    def scrape_date(self, mdy):
        """Returns dict case_number -> {aid, judgment_amount, parcel_id} for one auction date."""
        self._get(f"{HOST}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW"
                  f"&AUCTIONDATE={mdy.replace('/', '%2F')}")
        found = {}
        for area in ("R", "W", "C"):
            seen_aids = set()
            page_dir, do_r = 0, 1
            for _ in range(15):  # safety cap on pagination
                loadurl = (f"{HOST}/index.cfm?zaction=AUCTION&Zmethod=UPDATE&FNC=LOAD"
                           f"&AREA={area}&PageDir={page_dir}&doR={do_r}&tx={int(time.time()*1000)}"
                           f"&bypassPage=0")
                resp = self._get(loadurl, {"X-Requested-With": "XMLHttpRequest"})
                idx = resp.find('{"retHTML"')
                if idx < 0:
                    break
                try:
                    body = json.loads(resp[idx:])
                except json.JSONDecodeError:
                    break
                items = parse_area_items(body.get("retHTML", ""))
                new_aids = {v["aid"] for v in items.values()} - seen_aids
                if not new_aids:
                    break
                seen_aids |= new_aids
                found.update(items)
                page_dir, do_r = 1, 0
                time.sleep(0.4)
        return found

# ── BCPA assessed/market value lookup ─────────────────────────────────────────
def fetch_bcpa(folio):
    body = json.dumps({"folioNumber": folio, "taxyear": "", "action": "CURRENT", "use": ""}).encode()
    req = urllib.request.Request(
        BCPA_ENDPOINT, data=body,
        headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read())
    except Exception as e:
        return None, f"http_error:{e}"
    d = payload.get("d")
    if not d:
        return None, "no_data"
    parcels = d.get("parcelInfok__BackingField") or []
    if not parcels:
        return None, "no_parcel_info"
    p = parcels[0]
    just_value = money_to_float(p.get("justValue"))
    taxable_county = money_to_float(p.get("taxableAmountCounty"))
    if just_value is None and taxable_county is None:
        return None, "no_value_fields"
    return {
        "market_value": just_value,
        "assessed_value": taxable_county if taxable_county is not None else just_value,
    }, None

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    queue = sb_get("auction_enrichment_queue",
                    "county=eq.broward&status=eq.queued&enqueued_by=eq.claude-chat-audit-jul29"
                    "&select=case_number")
    target_cases = sorted({r["case_number"] for r in queue})
    print(f"Queue: {len(target_cases)} Broward cases to enrich")

    cases_q = ",".join(urllib.parse.quote(c) for c in target_cases)
    mca_rows = sb_get("multi_county_auctions",
                       f"county=eq.broward&case_number=in.({cases_q})"
                       f"&select=case_number,auction_date,opening_bid,assessed_value,parcel_id")
    mca_by_case = {r["case_number"]: r for r in mca_rows}
    print(f"multi_county_auctions: {len(mca_rows)} matching rows found")

    dates_needed = sorted({r["auction_date"] for r in mca_rows if r.get("auction_date")})
    print(f"Auction dates to scrape: {dates_needed}")

    rf = BrowardRF()
    scraped = {}
    for iso_date in dates_needed:
        y, mo, d = iso_date.split("-")
        mdy = f"{mo}/{d}/{y}"
        print(f"\n=== Scraping {mdy} ===")
        day_items = rf.scrape_date(mdy)
        print(f"  {len(day_items)} unique cases found across R/W/C")
        scraped.update(day_items)
        time.sleep(1)

    print(f"\nTotal unique cases scraped across all dates: {len(scraped)}")

    enriched, misses = [], []
    for case_number in target_cases:
        mca = mca_by_case.get(case_number)
        if not mca:
            misses.append((case_number, "not_in_mca"))
            continue
        item = scraped.get(case_number)
        if not item:
            misses.append((case_number, "not_found_on_realforeclose"))
            continue

        patch = {}
        fields_enriched = []
        if mca.get("opening_bid") is None and item.get("judgment_amount"):
            patch["opening_bid"] = item["judgment_amount"]
            fields_enriched.append("opening_bid")

        parcel_id = item.get("parcel_id") or mca.get("parcel_id")
        if mca.get("assessed_value") is None and parcel_id and FOLIO_RE.match(parcel_id):
            bcpa, err = fetch_bcpa(parcel_id)
            time.sleep(0.5)
            if bcpa and bcpa.get("assessed_value") is not None:
                patch["assessed_value"] = bcpa["assessed_value"]
                if bcpa.get("market_value") is not None:
                    patch["market_value"] = bcpa["market_value"]
                fields_enriched.append("assessed_value")
            else:
                print(f"  BCPA miss for {case_number} folio={parcel_id}: {err}")

        if not patch:
            misses.append((case_number, "no_new_fields_to_patch"))
            continue

        st, body = sb_patch(
            f"multi_county_auctions?county=eq.broward&case_number=eq.{urllib.parse.quote(case_number)}",
            patch)
        if st not in (200, 204):
            misses.append((case_number, f"patch_failed_http_{st}:{body[:150]}"))
            continue

        completed_at = datetime.now(timezone.utc).isoformat()
        st_q, body_q = sb_patch(
            f"auction_enrichment_queue?county=eq.broward&case_number=eq.{urllib.parse.quote(case_number)}",
            {"status": "completed", "completed_at": completed_at, "fields_enriched": fields_enriched})
        enriched.append((case_number, patch, st_q, body_q))
        print(f"  ENRICHED {case_number}: {patch}")

    print("\n=== SUMMARY ===")
    print(f"Enriched: {len(enriched)} / {len(target_cases)}")
    print(f"Missed:   {len(misses)}")
    for c, reason in misses:
        print(f"  MISS {c}: {reason}")

if __name__ == "__main__":
    main()
