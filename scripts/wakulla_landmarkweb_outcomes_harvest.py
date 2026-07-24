#!/usr/bin/env python3
"""
Wakulla County Clerk LandmarkWeb -- Tax Deed Outcomes Harvester

Scrapes recorded tax-deed sale outcomes (grantee, consideration, book/page,
instrument #) from Wakulla's official-records search by sweeping documents
where grantor contains "WAKULLA COUNTY CLERK OF COURT" within a date range,
then fetching the detail page for each hit and writing verified outcomes to
Supabase (multi_county_auctions.sold_amount/tier1_sold_amount + an
INDEPENDENT tax_deed_outcomes row per case).

WORKING RECIPE (verified live 2026-07-24, cross-checked by two independent
agent sessions, against https://www.wakullaclerk.com/landmarkweb, Pioneer
Technology Group LandmarkWeb v1.5.103.0):

  1. GET  /LandmarkWeb/                       -> session cookie (ASP.NET_SessionId)
  2. POST /LandmarkWeb/Search/SetDisclaimer   -> body MUST be a real POST with
     Content-Length set (data=b''). A truly bodyless POST triggers an IIS
     "411 Length Required" error on this server.
  3. POST /LandmarkWeb/Search/NameSearch      -> sets server-side search
     criteria (grantor name contains-match + doctype + date range). Returns
     an HTML results SHELL with an empty <tbody> -- not parsed for data, its
     only job is to set session state for step 4.
  4. POST /LandmarkWeb/Search/GetSearchResults -> the real data call. Plain
     jQuery DataTables server-side params (draw/start/length) return JSON
     rows for whatever criteria step 3 set on the session. A 200 response
     with recordsTotal=0 means no criteria are active yet (step 3 was
     skipped or no-opped), not necessarily "nothing found".
  5. POST /LandmarkWeb/Document/Index          -> detail page for one hit,
     keyed by the internal docid extracted from GetSearchResults row field
     "25" (formatted "hidden_<docid>"). Consideration/Grantor/Grantee/
     Book-Page/Record-Date are parsed off the label/value table on this page.

NOT exercised live: DocumentTypeSearch (doctype-only, no name filter). The
NameSearch recipe here (grantor contains "WAKULLA COUNTY CLERK OF COURT",
doctype=20/DEED) is what was actually proven end-to-end (99/99 records for
2026, including confirming a genuine gap at case 2026-TXD-097 -- no bidder,
no deed recorded, not a scraper defect).

SSL note: the cert on wakullaclerk.com is EXPIRED -- verify=False is required
for this legitimate government site (read-only GET/POST only, no credentials
submitted).

Env (required to write, optional for --dry-run): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success, 1 = fatal error, 2 = zero new outcomes found (not a failure)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

BASE = "https://www.wakullaclerk.com/LandmarkWeb"
GRANTOR_FILTER = "WAKULLA COUNTY CLERK OF COURT"
DOCTYPE_DEED = "20"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

DATA_SOURCE_PREFIX = "wakulla_landmarkweb"


def build_session() -> requests.Session:
    """Steps 1-2: establish session cookie + accept disclaimer."""
    s = requests.Session()
    s.verify = False
    requests.packages.urllib3.disable_warnings()
    s.headers.update({"User-Agent": UA})

    r = s.get(f"{BASE}/", timeout=30)
    r.raise_for_status()

    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    r = s.post(f"{BASE}/Search/SetDisclaimer", data=b"", headers=headers, timeout=30)
    r.raise_for_status()
    return s


def name_search(s: requests.Session, name: str, begin_date: str, end_date: str,
                 doctype: str = DOCTYPE_DEED, match_type: str = "1",
                 record_count: str = "2000") -> None:
    """Step 3: POST Search/NameSearch to set server-side search criteria."""
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/search/index?theme=.blue&section=NAME",
    }
    data = {
        "searchLikeType": match_type,   # 0=Starts With, 1=Contains, 2=Equals
        "type": "0",                     # partyType: 0=Both, 1=Direct, 2=Reverse
        "name": name,
        "doctype": doctype,
        "bookType": "0",
        "beginDate": begin_date,          # mm/dd/yyyy
        "endDate": end_date,              # mm/dd/yyyy
        "recordCount": record_count,
        "exclude": "false",
        "ReturnIndexGroups": "false",
        "townName": "",
        "selectedNamesIds": "",
        "includeNickNames": "false",
        "selectedNames": "",
        "mobileHomesOnly": "false",
    }
    r = s.post(f"{BASE}/Search/NameSearch", data=data, headers=headers, timeout=30)
    r.raise_for_status()


def get_search_results(s: requests.Session, length: str = "2000") -> dict:
    """Step 4: POST Search/GetSearchResults -- the actual DataTables data call."""
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/search/index?theme=.blue&section=NAME",
    }
    data = {"draw": "1", "start": "0", "length": length}
    r = s.post(f"{BASE}/Search/GetSearchResults", data=data, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def extract_docid(row: dict) -> str:
    return row.get("25", "").replace("hidden_", "").strip()


def extract_case_number(row: dict) -> str:
    raw = row.get("5", "")
    return raw.split("<div")[0].strip()


def get_detail(s: requests.Session, docid: str) -> str:
    """Step 5: POST Document/Index for the full detail page of one hit."""
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{BASE}/search/index?theme=.blue&section=NAME",
    }
    data = {"id": docid, "row": "1", "navigationType": ""}
    r = s.post(f"{BASE}/Document/Index", data=data, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def parse_detail_fields(html: str) -> dict:
    """Parse the label/value table on the Document/Index detail page."""
    fields = {}
    for m in re.finditer(
        r'for="([^"]+)"[^>]*>\s*([^<]+)</label>\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>',
        html, re.S,
    ):
        label = m.group(2).strip()
        val = m.group(3)
        val = re.sub(r"<br\s*/?>", " | ", val)
        val = re.sub(r"<div[^>]*></div>", " / ", val)
        val = re.sub(r"\s+", " ", val).strip().rstrip("|").strip()
        fields[label] = val
    return fields


def parse_money(raw: str):
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.]", "", raw)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def harvest(begin_date: str, end_date: str) -> list:
    """Sweep NameSearch+GetSearchResults, filter to the clerk-as-grantor tax
    deed rows, fetch + parse detail for each hit."""
    s = build_session()
    name_search(s, GRANTOR_FILTER, begin_date, end_date, doctype=DOCTYPE_DEED,
                match_type="1", record_count="2000")
    results = get_search_results(s, length="2000")

    total = results.get("recordsTotal", 0)
    print(f"GetSearchResults: recordsTotal={total}", file=sys.stderr)

    outcomes = []
    for row in results.get("data", []):
        grantor_raw = row.get("5", "")
        if GRANTOR_FILTER not in grantor_raw:
            continue

        case_number = extract_case_number(row)
        docid = extract_docid(row)
        if not docid:
            continue

        detail_html = get_detail(s, docid)
        fields = parse_detail_fields(detail_html)

        outcomes.append({
            "case_number": case_number,
            "docid": docid,
            "instrument_number": fields.get("Instrument #", ""),
            "book_page": fields.get("Book/Page", ""),
            "record_date": fields.get("Record Date", ""),
            "doc_type": fields.get("Doc Type", ""),
            "grantor": fields.get("Grantor", ""),
            "grantee": fields.get("Grantee", ""),
            "consideration_raw": fields.get("Consideration", ""),
        })
        time.sleep(0.5)

    return outcomes


def normalize_case_number(raw_case: str) -> str:
    """LandmarkWeb grantor text uses '2026 TXD 093'; our DB uses '2026-TXD-093'."""
    parts = raw_case.split()
    if len(parts) == 3 and parts[1].upper() == "TXD":
        return f"{parts[0]}-TXD-{parts[2]}"
    return raw_case


def supabase_write(outcomes: list) -> int:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    h_insert = dict(h, Prefer="return=minimal")

    written = 0
    for o in outcomes:
        amount = parse_money(o["consideration_raw"])
        if amount is None:
            continue  # no consideration on this doc type (e.g. foreclosure judgments) -- nothing to write

        case_number = normalize_case_number(o["case_number"])
        source = f"{DATA_SOURCE_PREFIX}:auto_harvest"

        existing = requests.get(
            f"{url}/rest/v1/multi_county_auctions",
            headers=h, params={"county": "eq.wakulla", "case_number": f"eq.{case_number}",
                                "select": "sold_amount"},
            timeout=30,
        )
        existing.raise_for_status()
        rows = existing.json()
        if rows and rows[0].get("sold_amount") is not None:
            continue  # already captured, don't overwrite an existing (possibly manually-verified) value

        patch = {
            "sold_amount": amount,
            "sold_amount_source": source,
            "tier1_sold_amount": amount,
            "tier1_authoritative": True,
            "winning_bidder": o["grantee"],
            "winning_bidder_source": source,
            "auction_status": "sold",
        }
        resp = requests.patch(
            f"{url}/rest/v1/multi_county_auctions",
            headers=h, params={"county": "eq.wakulla", "case_number": f"eq.{case_number}"},
            data=json.dumps(patch), timeout=30,
        )
        resp.raise_for_status()
        if resp.status_code not in (200, 204):
            continue

        auction_date = None
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", o["record_date"])
        if m:
            mm, dd, yyyy = m.groups()
            auction_date = f"{yyyy}-{mm}-{dd}"

        out_row = {
            "case_number": case_number,
            "county": "wakulla",
            "auction_date": auction_date,
            "winning_bid": amount,
            "outcome": "SOLD",
            "winner_name": o["grantee"],
            "data_source": source,
            "source_url": f"{BASE}/",
        }
        ins = requests.post(
            f"{url}/rest/v1/tax_deed_outcomes",
            headers=h_insert, data=json.dumps(out_row), timeout=30,
        )
        if ins.status_code == 201:
            written += 1

    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=None, help="mm/dd/yyyy (default: 30 days ago)")
    parser.add_argument("--end", default=None, help="mm/dd/yyyy (default: today)")
    parser.add_argument("--dry-run", action="store_true", help="print findings, do not write to Supabase")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    start = args.start or (now - timedelta(days=30)).strftime("%m/%d/%Y")
    end = args.end or now.strftime("%m/%d/%Y")
    for d in (start, end):
        datetime.strptime(d, "%m/%d/%Y")

    outcomes = harvest(start, end)
    print(json.dumps(outcomes, indent=2))

    if args.dry_run:
        print(f"DRY RUN: {len(outcomes)} candidate documents found, nothing written", file=sys.stderr)
        sys.exit(0 if outcomes else 2)

    written = supabase_write(outcomes)
    print(f"Wrote {written} new outcome rows to Supabase", file=sys.stderr)
    sys.exit(0 if written > 0 else 2)


if __name__ == "__main__":
    main()
