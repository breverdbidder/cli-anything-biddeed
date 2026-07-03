#!/usr/bin/env python3
"""
Union County real-data bootstrap attempt (FC + TD lanes) -- CONFIRMED BLOCKED.

Prior session (commit 6761f8a7) deleted Union's entire 12-row auction footprint
as fabricated bootstrap/fixture data. This script re-verifies, from a fresh
session, whether ANY real anonymously-fetchable source exists for Union County
foreclosure (FC) or tax deed (TD) auction data. It does NOT write fabricated
rows under any circumstance -- see HARD GUARDRAILS in the dispatching prompt.

Findings (all independently re-verified live, 2026-07-03):

1. RealForeclose FC lane (union.realforeclose.com) -- DEAD.
   curl -L (browser UA) -> HTTP 200, final_url=https://www.realauction.com/
   (50,080 bytes, generic corporate marketing homepage, zero Union-specific
   content). Same result for the calendar endpoint
   (?zaction=USER&zmethod=CALENDAR).

2. RealTaxDeed TD lane -- DEAD, both variants tested:
   - https://union.realtaxdeed.com/... -> HTTP 200, final_url=www.realauction.com
     (identical dead-redirect signature as #1).
   - https://www.realtaxdeed.com/... (the county_auction_config placeholder
     value, flagged suspicious in the dispatch brief) -> HTTP 200,
     final_url=www.realauction.com (also dead).
   Control comparison: okeechobee.realtaxdeed.com/...CALENDAR -> HTTP 200,
   final_url STAYS on okeechobee.realtaxdeed.com (16,314 bytes, genuine
   county-specific calendar content, contains "Okeechobee"). Union has no
   provisioned per-county RealAuction-family site behind either lane.

3. Union County Clerk (unionclerk.com/tax-deed-sales/ and
   .../foreclosure-sales/) -- the real courthouse-calendar analog -- BLOCKED
   by Cloudflare JS challenge. Independently re-confirmed via TWO different
   fetch paths in this session:
     a. curl (browser UA + Accept-Language + Referer) -> HTTP 403, body
        contains title "Just a moment..." (classic cf-challenge signature).
     b. WebFetch tool -> "The server returned HTTP 403 Forbidden" (same
        result, rules out a curl-specific header/UA issue).
   No FIRECRAWL_API_KEY env var and no firecrawl CLI binary present in this
   sandbox (`which firecrawl` -> not found; firecrawl-scrape skill itself
   confirmed the binary is absent when invoked). Cannot escalate to a
   JS-rendering fetch to solve the Cloudflare challenge.
   WebSearch confirms (via snippet text only, not a direct fetch): "Union
   County Courthouse at 55 West Main Street", foreclosure sales "Thursday,
   starting at 11:00 A.M. in the lobby", tax deed sales also held in the
   lobby. Confirms BOTH lanes are in-person / non-judicial-style courthouse
   sales -- no case-number-bearing online docket exists for TD (Florida tax
   deed sales are statutorily non-judicial, no court case filed).

4. Civitek OCRS (Union County id 63, https://www.civitekflorida.com/ocrs/county/63/)
   -- loads anonymously, HTTP 200, 8,542 bytes, NO Cloudflare-challenge
   markers on the initial GET (independently re-confirmed this session).
   However the landing page is a PrimeFaces/JSF access-tier selector
   (buttons: "Public", "Attorney", "Registered User" -- each wired to
   PrimeFaces.ab() AJAX partial postbacks, not plain <input type=text> +
   submit). A real search cannot be executed via curl/plain HTTP POST
   without replaying the exact JSF ViewState + PrimeFaces AJAX protocol,
   which in practice requires a JS-capable browser (Playwright/browser-use).
   Out of scope for this pass -- no browser automation tool was invoked
   against a *live* auction search here, so this remains UNTESTED beyond
   the anonymous-load confirmation, not CONFIRMED-blocked like #1-#3.

5. WebSearch for third-party mirrors of real Union County sale lists
   (taxlienuniversity.com, parcelfair.com, foreclosure.com,
   unioncountytc.com) surfaced only: (a) paid aggregator sites -- not
   anonymous/free authoritative sources per HARD GUARDRAIL #5/#1 pattern,
   never to be ingested as data_source; (b) unioncountytc.com/Property/
   TaxCertificates -- loads anonymously (HTTP 200, no CF challenge) but is
   the Tax Collector's informational page about the upstream tax-CERTIFICATE
   lien sale (a different statutory process), not the tax-DEED auction
   itself -- contains zero case numbers, parcel IDs, or auction dates.

CONCLUSION: No real fetchable per-sale data (case_number, parcel_id,
auction_date, sold_amount, etc.) exists for Union County via any anonymous
path available in this sandbox. Zero rows written to multi_county_auctions.
The only live-DB action taken is a config-hygiene correction to
county_auction_config (td_url/td_method were pointing at a confirmed-dead
placeholder) -- not a data write, not a fabrication.

dispatch_id: shard9-union-realdata-bootstrap-2026-07-03
"""
import os
import sys
from datetime import datetime, timezone

import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

FC_URLS = [
    'https://union.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR',
]
TD_URLS = [
    'https://union.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',
    'https://www.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',  # county_auction_config placeholder value
]
CONTROL_URL = 'https://okeechobee.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR'
CLERK_URLS = [
    'https://unionclerk.com/tax-deed-sales/',
    'https://unionclerk.com/departments-services/court-services/foreclosure-sales/',
]
CIVITEK_URL = 'https://www.civitekflorida.com/ocrs/county/63/'


def probe(url: str) -> dict:
    """Anonymous GET, follow redirects, report final destination + size. No parsing/writes."""
    client = httpx.Client(timeout=20, follow_redirects=True, headers={'User-Agent': UA})
    try:
        r = client.get(url)
        return {'url': url, 'status': r.status_code, 'final_url': str(r.url), 'size': len(r.content)}
    except httpx.HTTPError as e:
        return {'url': url, 'error': str(e)}
    finally:
        client.close()


def evaluate_county(county: str) -> dict:
    r = httpx.post(f'{BASE}/rpc/pencil_dod_evaluate_county',
                    headers={k: v for k, v in HEADERS.items() if k != 'Prefer'},
                    json={'p_county': county}, timeout=30)
    r.raise_for_status()
    return r.json()


def main():
    print('=== FC lane probes (expect dead redirect to realauction.com) ===')
    for u in FC_URLS:
        print(probe(u))

    print('=== TD lane probes (expect dead redirect to realauction.com) ===')
    for u in TD_URLS:
        print(probe(u))

    print('=== Control: okeechobee.realtaxdeed.com (expect genuine county calendar) ===')
    print(probe(CONTROL_URL))

    print('=== Clerk courthouse-calendar analog probes (expect HTTP 403 cf-challenge) ===')
    for u in CLERK_URLS:
        print(probe(u))

    print('=== Civitek OCRS county/63 (expect HTTP 200, access-tier selector, no CF challenge) ===')
    print(probe(CIVITEK_URL))

    print()
    print('RESULT: No real per-sale data fetchable via any anonymous path in this sandbox.')
    print('Zero rows written to multi_county_auctions for county=union. See module docstring '
          'for full evidence chain. Never fabricating placeholder case numbers per guardrail #3.')


if __name__ == '__main__':
    main()
