#!/usr/bin/env python3
"""
shard8_baker_e_parcel_source_gap_diagnostic.py — Gold Standard shard-8 baker, run 3679

Diagnostic (NOT a fix) for baker's E/C/D/I gap: 6 cases (12 rows), all NULL on
parcel_id/property_address/lat/lon/assessed_value/parity_status/parity_source,
data_source='calendar_sweep_mca_v3'.

RESULT (VERIFIED live this session): this is a genuine SOURCE-DATA gap, not a
scraper or matcher bug.

  - 3 of the 6 cases (022025CA000148CAAXMX, 022026CA000007CAAXMX,
    022026CA000018CAAXMX) ARE live on baker.realforeclose.com's JSON UPDATE
    endpoint (confirmed on auction dates 2026-08-13 / 2026-08-20). Their
    judgment_amount/opening_bid are already correctly populated in
    multi_county_auctions from a prior sweep. BUT the source's own "Parcel ID"
    table cell is an empty link (href="...propertydetails.php?parcel=" with
    no parcel value) and there is NO "Property Address" field on the card at
    all for these 3 cases -- confirmed by diffing against the
    ALREADY-COMPLETE case 022025CA000038CAAXMX pulled from the exact same
    live page dump, which DOES show a populated parcel link
    (parcel=043S22000000000540) and a 2-line address. The parser/pipeline
    is proven to work correctly when the source has the data; it simply
    doesn't have it for these 3 cases yet (plaintiff/clerk hasn't filed the
    property details on RealAuction).

  - The other 3 cases (022025CA000108CAAXMX, 022025CA000117CAAXMX,
    022025CA000124CAAXMX) were NOT found on any of the 4 auction dates
    discoverable via forward/backward PREVIEW-page navigation from today
    (2026-04-23 back; 2026-07-16, 2026-08-13, 2026-08-20 forward) -- likely
    resolved/cancelled/removed from the active calendar.

  - bakerpa.com (the Baker County Property Appraiser site referenced by the
    working rows' parity_source 'tier1_baker_realforeclose_bakerpa_v1') is
    DOWN: HTTP 521 (Cloudflare: origin server unreachable) on 3 separate
    attempts this session. No fallback parcel lookup was available.

  - Firecrawl API returned HTTP 402 (out of credits) this session.
  - bakerclerk.com and recording.bakerclerk.com are Cloudflare-gated (403).
  - civitekflorida.com/ocrs/county/02/ (Baker OCRS court records) requires a
    stateful JSF/PrimeFaces click-through (public access consent + ViewState
    tokens) not reachable via plain requests/curl in this session's budget.

DO NOT re-run the calendar_sweep_mca.py's parse/upsert logic by importing it
-- that file has an explicit no-import guard (see its module docstring,
2026-07-20 incident). This script reimplements only the read-only discovery
+ JSON-fetch calls standalone, and does NOT write to Supabase.

Next-session TODO if bakerpa.com comes back online:
  1. Re-run this script's `dump_case_details()` for the 3 live cases to
     re-confirm the source still lacks parcel/address (RealAuction data can
     update as sale date approaches).
  2. If bakerpa.com is up, search it by owner name (extractable from the
     Baker Clerk's official record for each case, via OCRS or a headless
     browser session that can click through the JSF consent flow) to find
     the parcel independently of RealAuction's own (currently empty) link.
  3. For the 3 not-found cases, check whether they were cancelled/settled
     (would explain absence from the active calendar) via OCRS case search,
     or a wider backward date-navigation sweep (this session's nav-link
     traversal capped at 15 hops, ending at 2026-04-23).

Env (required): none read from the environment for this diagnostic --
requests-only, read-only, no Supabase writes.
"""
import re
import sys
import time
from datetime import date, datetime

import requests

UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
)

BASE_URL = 'https://baker.realforeclose.com'

TARGET_CASES = {
    '022025CA000108CAAXMX', '022025CA000117CAAXMX', '022025CA000124CAAXMX',
    '022025CA000148CAAXMX', '022026CA000007CAAXMX', '022026CA000018CAAXMX',
}


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Accept': 'text/html,*/*'})
    return s


def _parse_date(s: str) -> date | None:
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


def discover_forward_dates(session: requests.Session) -> list[date]:
    """Same technique as calendar_sweep_mca.py's discover_auction_dates(), reimplemented standalone."""
    seed_url = f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW'
    r = session.get(seed_url, timeout=30)
    if r.status_code != 200:
        print(f'seed page failed: HTTP {r.status_code}', file=sys.stderr)
        return []
    dates = {d for m in re.finditer(r'AuctionDate=([\d/]+)', r.text, re.IGNORECASE)
             if (d := _parse_date(m.group(1))) and d >= date.today()}
    return sorted(dates)


def get_json_page(session: requests.Session, auction_date: date) -> str:
    ts = int(time.time() * 1000)
    url = (f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=UPDATE'
           f'&FNC=LOAD&AREA=W&PageDir=0&doR=1&tx={ts}&bypassPage=0')
    date_str = auction_date.strftime('%m/%d/%Y')
    r = session.get(url, headers={
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_str}',
    }, timeout=30)
    if r.status_code != 200:
        return ''
    try:
        return r.json().get('retHTML', '')
    except ValueError:
        return ''


def dump_case_details(ret_html: str) -> dict[str, str]:
    """Return {case_number: raw_content_block} for every AITEM found.

    Field pattern mirrors calendar_sweep_mca.py's get_field(): label text,
    then ':@F', then arbitrary attrs up to '>', then the value, then '@G'.
    """
    out = {}
    parts = re.split(r'<div id="AITEM_(\d+)"', ret_html)
    for i in range(1, len(parts), 2):
        content = parts[i + 1] if i + 1 < len(parts) else ''
        m = re.search(r'Case #:@F[^>]*>(.*?)@G', content, re.DOTALL)
        if m:
            case_num = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if case_num:
                out[case_num] = content
    return out


def main() -> int:
    session = _session()
    status, _ = 200, None
    r = session.get(f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW', timeout=30)
    print(f'seed status={r.status_code}')

    dates = discover_forward_dates(session)
    print(f'forward dates discovered: {dates}')

    for d in dates:
        date_str = d.strftime('%m/%d/%Y').replace('/', '%2F')
        session.get(f'{BASE_URL}/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE={date_str}', timeout=30)
        ret_html = get_json_page(session, d)
        cases = dump_case_details(ret_html)
        hits = TARGET_CASES & set(cases)
        print(f'{d}: {len(cases)} cases on calendar, {len(hits)} target hits: {sorted(hits)}')
        for cn in hits:
            block = cases[cn]
            has_parcel = bool(re.search(r'parcel=[0-9A-Za-z\-]', block))
            has_addr = 'Property Address' in block
            print(f'  {cn}: has_parcel_value={has_parcel} has_property_address_field={has_addr}')
        time.sleep(1)

    return 0


if __name__ == '__main__':
    sys.exit(main())
