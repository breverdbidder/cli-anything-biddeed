#!/usr/bin/env python3
"""
Gold Standard shard-6, county=union, dispatch 95f77ed6-fc70-4c15-9db4-b9b64bef5d1c.

Continuation of scripts/shard10_run3645_union_b_cert223.py (2026-07-10), which
left two explicitly-flagged-but-not-yet-attempted follow-ups for UNION-TD-CERT223
(tax deed cert #223, parcel 32-05-20-22-018-0022-0):

  1. http://unioncountytc.com/ (Tax Collector) -- only the homepage was reviewed
     before; a cert-status lookup tool was never attempted.
  2. http://union.floridapa.com/ (Property Appraiser GIS, GrizzlyLogic iframe) --
     Playwright could not drive the nested #searchInput in the prior session;
     retry with more time / Firecrawl was flagged as worth trying.

RESULT (2026-07-18):

(1) unioncountytc.com DOES expose a real, working property/tax-bill search
    (POST /Property/search with a `propertynumber` field matching the FL GIO
    PARCELID format exactly). Searching parcel 32-05-20-22-018-0022-0 returns
    an 11-row delinquent-tax-history table (2015-2025) for owner
    "RIDGEWAY PORSHA T & HARMON III". Drilling into the most recent bill
    (2025, bill #577200 -> /Property/PriorBill) surfaces a "Delinquent Tax
    History" sub-table that explicitly lists:
        2025  R 577200-I   Cert #216   Outstanding $146.95   (still open)
        2017  R 531200-I   Cert #223   Outstanding $0.00, Accrued Penalties $0.00
    Cert #223 (tax year 2017) shows a fully-zeroed balance -- consistent with
    redemption (the delinquent tax was paid off), not with an unsold/still-
    outstanding certificate. No dollar SALE amount is exposed anywhere on
    this domain (the dedicated /Property/TaxDeed?TaxBillNo=... page is a
    static "contact the office" message, not a data lookup) -- this source
    corroborates but does not by itself prove redemption vs. sale.

(2) union.floridapa.com: one bounded Playwright attempt (multi-frame scan for
    #searchInput across ALL frames after a 30s+4s settle wait) found only the
    top-level frame loaded -- the GrizzlyLogic parcel-search iframe never
    appeared. Firecrawl (the suggested alternative) returned
    "Insufficient credits" on both /v1/map and /v1/scrape -- FIRECRAWL_API_KEY
    is set but the account has zero balance, a billing block not a code
    issue. This follow-up remains a genuine, disclosed residual.

THE DECIDING SOURCE: a fresh, TWICE-independently-fetched (Playwright, system
chromium) render of https://unionclerk.com/tax-deed-sales/ -- the exact page
the prior session found "still SCHEDULED" on 2026-07-10 -- now shows:
    STATUS: REDEEMED
    SALE DATE: 03/12/2026
    CERT #: 223
    PARCEL ID: 32-05-20-22-018-0022-0
    CERT HOLDER: J. R. Davis Trust
    OPENING BID: $2,336.32
This is the clerk's own authoritative page having been updated in the ~8 days
since the prior session (stale render then, not stale now). REDEEMED is a
definitive, non-sale outcome: the property owner paid off the certificate
before the tax deed sale could occur. This directly matches the $0.00
outstanding balance found independently on unioncountytc.com for the same
cert/parcel -- two independent domains (Clerk + Tax Collector) agree.

WRITE PERFORMED: auction_status corrected 'unknown_past_due' -> 'redeemed'.
sold_amount / tier1_sold_amount are correctly left NULL -- a redemption has
no sale price by definition; writing anything there would be fabrication.

EXPECTED (and observed) DoD IMPACT: NONE on B or F. Per the campaign brief's
own explicit caveat, "a bare status correction alone does not move B or F" --
closed_sold is defined as sold_amount IS NOT NULL, and a REDEEMED cert
structurally can never have a sold_amount. B/F remain FAIL/null
(closed_sold=0 of 3) before and after this fix, confirmed via
pencil_dod_evaluate_county('union') re-run post-PATCH. This is disclosed
as the correct, honest outcome -- not a missed opportunity.

Idempotent: PATCH only, scoped to county=union AND case_number=UNION-TD-CERT223.
"""
import asyncio
import json
import os
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
CASE_NUMBER = 'UNION-TD-CERT223'
PARCEL_ID = '32-05-20-22-018-0022-0'


async def render(url: str, wait_ms: int = 5000) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = await browser.new_page(user_agent=UA)
        await page.goto(url, timeout=45000, wait_until='domcontentloaded')
        await page.wait_for_timeout(wait_ms)
        text = await page.inner_text('body')
        await browser.close()
        return text


async def main() -> None:
    # Two independent fetches (double-fetch precedent from prior sessions).
    text1 = await render(TD_URL)
    text2 = await render(TD_URL)

    def status_of(text: str) -> str | None:
        if 'REDEEMED' in text.upper() and '223' in text and '32-05-20-22-018-0022-0' in text:
            return 'REDEEMED'
        if 'SCHEDULED' in text.upper() and '223' in text:
            return 'SCHEDULED'
        return None

    s1, s2 = status_of(text1), status_of(text2)
    print(f"fetch1 status={s1}  fetch2 status={s2}")

    if not (s1 == 'REDEEMED' and s2 == 'REDEEMED'):
        raise RuntimeError(
            f'FAIL-LOUD: expected both fetches to agree on REDEEMED for cert #223, '
            f'got fetch1={s1} fetch2={s2}. Do not proceed with a write on disagreement.')

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

    now = datetime.now(timezone.utc).isoformat()
    patch = {
        'auction_status': 'redeemed',
        'last_seen_at': now,
        'scraped_at': now,
    }
    pr = httpx.patch(
        f'{BASE}/multi_county_auctions', headers=HEADERS,
        params={'county': 'eq.union', 'case_number': f'eq.{CASE_NUMBER}'},
        json=patch, timeout=30)
    pr.raise_for_status()
    updated = pr.json()
    print(f"PATCHED auction_status -> redeemed for {CASE_NUMBER}: "
          f"{json.dumps(updated, default=str)}")

    print("\nNO sold_amount / tier1_sold_amount write -- redemption has no sale price.")
    print("Expected DoD impact: B and F unchanged (closed_sold stays 0 of 3).")


if __name__ == '__main__':
    asyncio.run(main())
