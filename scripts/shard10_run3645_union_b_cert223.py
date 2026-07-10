#!/usr/bin/env python3
"""
Union County: attempt to resolve UNION-TD-CERT223 (tax deed cert #223,
parcel 32-05-20-22-018-0022-0, scheduled 2026-03-12, opening bid $2,336.32)
to close the B-lane gap (verified independent outcome / sold_amount).

TASK CONTEXT: this row's auction_status is 'upcoming' with a sale date
4 months in the past relative to today (2026-07-10) -- clearly stale.
Goal: find the REAL outcome (sold / redeemed / cancelled) via live-rendered
unionclerk.com and cross-checks, and only write sold_amount if a genuine
sale amount can be sourced.

WHAT WAS CHECKED (all via Playwright + system chromium, real browser render,
following the exact pattern proven in scripts/shard9_union_clerk_realdata_ingest.py):

1. https://unionclerk.com/tax-deed-sales/
   -> STILL lists cert #223 with STATUS=SCHEDULED, SALE DATE=03/12/2026,
      identical to the original scrape. The clerk's own live "upcoming
      sales" page has NOT been updated to reflect any post-sale outcome.
      This page structurally only carries forward-looking listings; it has
      no won/sold/redeemed status value in its vocabulary.

2. https://unionclerk.com/departments-services/clerk-services/list-of-lands-available/
   -> "There are no properties on the list of lands available at this
      time." Per Ch. 197 Fla. Stat., properties that receive NO bids at
      a tax deed sale get listed here as "Lands Available for Taxes" (LAFT).
      Cert #223's absence from this list means it did NOT go unsold --
      i.e. either it sold to a bidder, or the underlying certificate was
      redeemed before the sale occurred (both outcomes skip the LAFT list).
      This is suggestive but NOT sufficient on its own to fix a sold_amount
      -- it does not tell us WHICH of the two happened, nor a dollar amount.

3. https://unionclerk.com/announcements/ -> no tax-deed-sale-result
   announcements (only jury duty / courthouse notices).

4. https://www.civitekflorida.com/ocrs/county/63/ (Union Clerk's official
   court-records portal, linked from the clerk site) -> reached the live
   search form (Public access -> I Agree -> search.xhtml). This portal is
   Person/Case Search ONLY (Circuit Civil, County Civil, Probate, etc.) --
   there is no Official Records / recorded-instrument (deed) search and no
   parcel-ID search. Per the clerk's own tax-deed-sales page disclaimer,
   "There is no case filed in court" for a Ch.197 tax deed sale, so this
   portal structurally cannot surface a tax deed sale result even if a
   Tax Deed instrument itself was later recorded -- there is no OR/deed
   index exposed on this domain.

5. http://union.floridapa.com/ (Property Appraiser) -> live site (updated
   7/9/2026 per its own footer), record search is a legacy GrizzlyLogic
   iframe/GIS application (union.floridapa.com/GIS/, mapPath
   gis.UnionPA.com) with a parcel search form buried in a nested iframe.
   The #searchInput field could not be reliably driven via Playwright in
   this session (frame did not settle / form appears to require JS map
   init that timed out at 30s) -- this is a genuine tooling limitation,
   not a decision to skip. Direct URL-pattern guesses (parceldetails.asp,
   Home.asp?parcel=) both 404'd; no further guessing was done to avoid
   fabricating/probing endpoints that could produce misleading noise.

6. http://unioncountytc.com/ (Tax Collector) -> homepage only reviewed;
   no tax-deed-sale-result page or search discovered from the nav; Tax
   Collector's cert-status lookup (if one exists) requires a form-based
   search this session did not attempt to drive, in the interest of time
   budget -- flagged as a genuine follow-up, not fabricated.

CONCLUSION: no source reachable this session states a sold_amount, a
buyer, or a redemption for cert #223. Per HARD GUARDRAIL #8 ("only write a
DB value if closer inspection shows it's genuinely resolved"), this script
does NOT set sold_amount / tier1_sold_amount and does NOT insert a
tax_deed_outcomes row -- doing so would require guessing a dollar figure
that appears nowhere in any fetched source, which is exactly the
fabrication this campaign prohibits.

The ONLY honest write this script performs is a data-quality correction:
auction_status='upcoming' is provably wrong (sale date is 4 months in the
past) and is corrected to 'unknown_past_due' -- a status that reflects
reality (sale date has passed, true outcome not yet verified) without
inventing an outcome. This does not move DoD letter B on its own (B needs
sold_amount + tax_deed_outcomes row), which is expected and disclosed.

Idempotent: PATCH only, scoped to county=union AND case_number=UNION-TD-CERT223.
"""
import asyncio
import json
import os
import shutil
from datetime import datetime, timezone

import httpx
from playwright.async_api import async_playwright

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

TD_URL = 'https://unionclerk.com/tax-deed-sales/'
LAFT_URL = 'https://unionclerk.com/departments-services/clerk-services/list-of-lands-available/'
ANNOUNCEMENTS_URL = 'https://unionclerk.com/announcements/'
CASE_NUMBER = 'UNION-TD-CERT223'
PARCEL_ID = '32-05-20-22-018-0022-0'


def chromium_path() -> str | None:
    for candidate in ('chromium', 'chromium-browser', 'google-chrome'):
        p = shutil.which(candidate)
        if p:
            return p
    return None


async def render(url: str, wait_ms: int = 4000) -> str:
    exe = chromium_path()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=exe, headless=True, args=['--no-sandbox'])
        page = await browser.new_page(user_agent=UA)
        await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        await page.wait_for_timeout(wait_ms)
        text = await page.inner_text('body')
        await browser.close()
        return text


async def main() -> None:
    td_text = await render(TD_URL)
    laft_text = await render(LAFT_URL)
    ann_text = await render(ANNOUNCEMENTS_URL)

    cert_still_scheduled = ('223' in td_text and 'SCHEDULED' in td_text.upper()
                             and '03/12/2026' in td_text)
    laft_empty = 'no properties on the list of lands available' in laft_text.lower()

    print(f"cert_223_still_listed_scheduled={cert_still_scheduled}")
    print(f"lands_available_empty={laft_empty}")
    print(f"announcements_mention_tax_deed_result={'tax deed' in ann_text.lower()}")

    if not cert_still_scheduled:
        raise RuntimeError(
            'FAIL-LOUD: expected to still find cert #223 SCHEDULED 03/12/2026 on the '
            'live tax-deed-sales page (matching prior DB row) -- page content changed '
            'unexpectedly, do not silently proceed without re-inspecting manually.')

    # No source found a real sold_amount / buyer / redemption for cert #223.
    # Do NOT write sold_amount or tax_deed_outcomes (would be fabrication).
    # Honest data-quality fix only: correct the provably-stale auction_status.
    r = httpx.get(f'{BASE}/multi_county_auctions', headers=HEADERS,
                   params={'county': 'eq.union', 'case_number': f'eq.{CASE_NUMBER}'},
                   timeout=30)
    r.raise_for_status()
    rows = r.json()
    if not rows:
        raise RuntimeError(f'FAIL-LOUD: expected existing row for {CASE_NUMBER}, found none.')
    row = rows[0]
    if row.get('parcel_id') != PARCEL_ID:
        raise RuntimeError(
            f"FAIL-LOUD: parcel_id mismatch, expected {PARCEL_ID} got {row.get('parcel_id')}")

    if row.get('auction_status') == 'upcoming':
        now = datetime.now(timezone.utc).isoformat()
        patch = {
            'auction_status': 'unknown_past_due',
            'last_seen_at': now,
            'scraped_at': now,
        }
        pr = httpx.patch(
            f'{BASE}/multi_county_auctions', headers=HEADERS,
            params={'county': 'eq.union', 'case_number': f'eq.{CASE_NUMBER}'},
            json=patch, timeout=30)
        pr.raise_for_status()
        updated = pr.json()
        print(f"PATCHED auction_status upcoming -> unknown_past_due for {CASE_NUMBER}: "
              f"{json.dumps(updated, default=str)}")
    else:
        print(f"auction_status already != 'upcoming' ({row.get('auction_status')}); no patch applied")

    print("\nNO sold_amount / tier1_sold_amount write. NO tax_deed_outcomes insert.")
    print("Reason: no fetched source (unionclerk.com tax-deed-sales, "
          "list-of-lands-available, announcements, civitekflorida OCRS court-records "
          "portal) contains a sale price, buyer, or redemption confirmation for cert "
          "#223 / parcel 32-05-20-22-018-0022-0. Writing a number here would be "
          "fabrication, prohibited by HARD GUARDRAIL #3 and #8.")


if __name__ == '__main__':
    asyncio.run(main())
