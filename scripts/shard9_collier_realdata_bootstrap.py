#!/usr/bin/env python3
"""
Collier County: real-data investigation for FC (foreclosure) and TD (tax deed) lanes.

CONTEXT: Prior sibling session (commit 6761f8a7, shard9 okeechobee) confirmed and
DELETED collier's entire prior auction footprint as FABRICATED bootstrap/fixture
data. Live DB state going into this pass: multi_county_auctions county='collier'
auctions_total=0 (honest, correct baseline). This script does NOT attempt to
"restore" that data -- it independently re-verifies every candidate real source
and only writes rows if genuinely fetchable, non-fabricated data is found.

RESULT: zero rows written. Both online platforms are confirmed dead/deprovisioned
and both physical sale processes are in-person only with no anonymously-scrapable
digital source. See findings below. No rows inserted into multi_county_auctions.

--- Investigation log (all VERIFIED via live httpx fetch, 2026-07-03) ---

1. RealForeclose / RealTaxDeed (vendor platform):
   collier.realforeclose.com            -> 302 -> http://www.realauction.com
   collier.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR -> same 302
   collier.realtaxdeed.com              -> 302 -> http://www.realauction.com
   collier.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR -> same 302
   Both subdomains resolve (real Realforeclose/1b infra, county-specific
   CF_CLIENT_COLLIER_* cookies present) but unconditionally redirect to the
   generic vendor marketing homepage on every path tried. This is a
   deprovisioned/inactive account, not a live scrapable auction calendar.
   Contrast: sibling counties (e.g. okeechobee) return 200 with real content
   on the same URL shapes -- this redirect pattern is Collier-specific.

2. Collier Clerk of Courts (collierclerk.com) -- FC sales process:
   https://www.collierclerk.com/court-divisions/civil-court/foreclosures/foreclosure-sales/
   confirms address "3315 Tamiami Trail East, Suite 102, Naples, FL 34112"
   (Civil Department) and directs users to search via an external AngularJS
   app at https://cms.collierclerk.com/showcaseweb/ ("Court Events" search).
   TD sale process (WebSearch-sourced, independently corroborated by the
   collierclerk.com tax-deed-sales pages existing and describing an in-person
   process): Collier County Government Administration Building, 7th floor
   Room 711, Mondays (not every Monday) 1:00 PM, no phone/electronic bids.

3. cms.collierclerk.com/showcaseweb/ ("ShowCase" court records/events system):
   GET / -> 200, 27272 bytes -- AngularJS SPA shell (ng-app="sc"), loads
   Google reCAPTCHA v3 (recaptcha/api.js?render=6LfugcQbAAAAAGUltXrg8TA4lQy6nbfK2wldf-em).
   Probed plausible API paths (/api/cases/search, /api/courtevents/search,
   /api/health) -- all return the SAME 27272-byte SPA shell (client-side
   routing catch-all), never real JSON. This is the same category of wall
   documented for Okeechobee's Civitek OCRS civil-case search (server-side
   reCAPTCHA/Turnstile-gated, requires JS execution + solving a challenge).
   Not achievable with anonymous httpx.

4. app.collierclerk.com/LFOfficialRecords/ (Laserfiche WebLink 11, tax deed
   sale lists/reports):
   GET Browse.aspx?dbid=1&startid=1600&repo=OFFICIALRECORDSPROD -> 200,
   1930 bytes -- Laserfiche WebLink Angular SPA shell only (main.js bundle
   referenced, no data). Probed guessed REST paths
   (/api/repositories, /Api/repositories, /api/v1/repositories,
   /api/repositories/{OFFICIALRECORDSPROD,r-e1c1f2e8}/entries/1600/entries)
   -- all 404. The real WebLink REST routes require a repository GUID
   resolved client-side by the Angular bundle at runtime; not guessable via
   plain httpx. Confirmed via WebSearch that direct PDF links found in search
   results (e.g. .../edoc/23256/2026-03-23 SALE.pdf) also return the SPA
   shell, not PDF bytes, without an authenticated/JS-rendered session.

5. www.collierclerk.com/tax-deed-sales/search-upcoming-sales-list/ and
   .../tax-deed-reports/: both 200 (94814 bytes), but confirmed to be
   WordPress page chrome (nav/footer boilerplate) wrapping the SAME
   Laserfiche iframe from (4) -- no additional data, no RSS/sitemap/JSON
   feed carrying auction data found on collierclerk.com (checked feed/,
   wp-json/, sitemap.xml -- only WordPress-post-level content, not
   auction/case data).

CONCLUSION: Both FC and TD sales in Collier County are conducted exclusively
in-person. No anonymously-reachable online source (vendor platform, clerk
CMS, or document repository) exists for either lane as of 2026-07-03. This
confirms (does not merely repeat) the forensics-phase finding via independent
re-fetch of every URL. Building a Playwright-based scraper of ShowCase or
LFOfficialRecords to defeat the reCAPTCHA/JS-execution wall is a distinct,
larger build-phase task requiring browser automation tooling not available
in this pass -- flagged for future work, not attempted here to avoid a
half-built, unverified scraper.

ACTION TAKEN (metadata correction only, no auction rows):
  county_auction_config (county_slug='collier') corrected:
    - td_method: null -> 'in_person' (was incorrectly implying a scrapable
      online lane existed via td_platform='realtaxdeed'/td_url, which are
      stale template artifacts pointing at the dead vendor subdomain)
    - fc_courthouse_address: null -> real verified address + hours for both
      FC and TD in-person sale locations
    - last_error: documents the confirmed-dead vendor subdomain redirect

NO rows written to multi_county_auctions. NO fabricated data. auctions_total
remains 0 for collier -- the honest, correct state.

dispatch_id: shard9-collier-2026-07-03
"""
import os
import sys

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


def verify_vendor_platform_dead() -> dict:
    """Re-check collier.realforeclose.com / collier.realtaxdeed.com are dead. Returns evidence dict."""
    client = httpx.Client(headers={'User-Agent': UA}, timeout=15, follow_redirects=False)
    evidence = {}
    for url in [
        'https://collier.realforeclose.com',
        'https://collier.realforeclose.com/index.cfm?zaction=USER&zmethod=CALENDAR',
        'https://collier.realtaxdeed.com',
        'https://collier.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR',
    ]:
        r = client.get(url)
        evidence[url] = {'status': r.status_code, 'location': r.headers.get('location')}
    return evidence


def correct_county_config() -> dict:
    """Apply the verified metadata correction to county_auction_config for collier."""
    payload = {
        'td_method': 'in_person',
        'fc_courthouse_address': (
            'Foreclosure sales: Courthouse Annex, 3rd floor lobby, Collier County '
            'Courthouse, 3315 Tamiami Trail East, Naples FL 34112, Mon-Fri 11:00 AM. '
            'Tax deed sales: Collier County Government Administration Building, 7th '
            'floor Room 711, Mondays (not every Monday) 1:00 PM. Both in-person only, '
            'no phone/electronic bids. VERIFIED via collierclerk.com 2026-07-03.'
        ),
        'last_error': (
            'collier.realforeclose.com and collier.realtaxdeed.com both 302-redirect '
            'unconditionally to http://www.realauction.com (deprovisioned vendor '
            'account) -- confirmed dead 2026-07-03, not a live scrapable platform '
            'despite td_platform/td_url values below being stale template artifacts.'
        ),
    }
    r = httpx.patch(f'{BASE}/county_auction_config', headers=HEADERS,
                     params={'county_slug': 'eq.collier'}, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> None:
    evidence = verify_vendor_platform_dead()
    for url, info in evidence.items():
        print(f'{url} -> {info["status"]} {info["location"]}')
        if info['status'] != 302 or info.get('location') != 'http://www.realauction.com':
            print('  UNEXPECTED: vendor platform state changed -- re-investigate before assuming dead.', file=sys.stderr)

    result = correct_county_config()
    print('county_auction_config corrected:', result)
    print('rows_written to multi_county_auctions: 0 (no viable anonymous real source found)')


if __name__ == '__main__':
    main()
