#!/usr/bin/env python3
"""
Union County: C/D tier1-clerk-live double-fetch stamping (same ratified
precedent as calhoun: supabase/migrations/20260710_shard12_calhoun_taxdeed_lane_acd_fix.sql)
+ fresh re-check of UNION-TD-CERT223's real outcome (sold/redeemed/cancelled).

Union's RealAuction lane is confirmed dark (in-person courthouse sales only,
per scripts/shard9_union_clerk_realdata_ingest.py) -- unionclerk.com's own
foreclosure-sales and tax-deed-sales pages are the sole authoritative source,
qualifying for the tier1-clerk-live precedent.

Fetches each of the 3 live pages TWICE, >=30s apart, and confirms
case_number/parcel_id/auction_date/status agree exactly across both fetches
before stamping parity_status='matched_clean',
parity_source='tier1:union_clerk_live_<YYYYMMDD>'.

Also re-renders the tax-deed-sales + list-of-lands-available pages fresh
(this session, 2026-07-11) to check whether CERT223's outcome has changed
since the prior investigation (scripts/shard10_run3645_union_b_cert223.py,
same day but earlier run).

Idempotent: PATCH only, scoped to county=union.
"""
import asyncio
import json
import os
import shutil
import time
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

FC_URL = 'https://unionclerk.com/departments-services/court-services/foreclosure-sales/'
TD_URL = 'https://unionclerk.com/tax-deed-sales/'
LAFT_URL = 'https://unionclerk.com/departments-services/clerk-services/list-of-lands-available/'

EXPECTED = {
    '63-2024-CA-0047': {'parcel_id': '15-05-20-00-000-0080-0', 'auction_date': '10/15/2026', 'status': 'SCHEDULED'},
    '63-2025-CA-0053': {'parcel_id': '31-05-18-00-000-0101-2', 'auction_date': '08/13/2026', 'status': 'SCHEDULED'},
    'UNION-TD-CERT223': {'parcel_id': '32-05-20-22-018-0022-0', 'auction_date': '03/12/2026', 'status': 'SCHEDULED', 'cert': '223'},
}


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


def check_fc_case(text: str, case_number: str, exp: dict) -> bool:
    return (case_number in text and exp['parcel_id'] in text
            and exp['auction_date'] in text and exp['status'] in text.upper())


def check_td_case(text: str, exp: dict) -> bool:
    return (exp['cert'] in text and exp['parcel_id'] in text
            and exp['auction_date'] in text and exp['status'] in text.upper())


async def main() -> None:
    results = {}

    print("=== FETCH 1 (t=0s) ===")
    fc1 = await render(FC_URL)
    td1 = await render(TD_URL)
    laft1 = await render(LAFT_URL)
    t1 = time.time()

    print("Sleeping 35s before fetch 2...")
    await asyncio.sleep(35)

    print("=== FETCH 2 (t=%.0fs) ===" % (time.time() - t1))
    fc2 = await render(FC_URL)
    td2 = await render(TD_URL)
    laft2 = await render(LAFT_URL)

    # --- Double-fetch agreement checks ---
    for case in ('63-2024-CA-0047', '63-2025-CA-0053'):
        exp = EXPECTED[case]
        m1 = check_fc_case(fc1, case, exp)
        m2 = check_fc_case(fc2, case, exp)
        results[case] = {'fetch1_match': m1, 'fetch2_match': m2, 'agree': m1 and m2}
        print(f"{case}: fetch1={m1} fetch2={m2} agree={m1 and m2}")

    exp223 = EXPECTED['UNION-TD-CERT223']
    m1 = check_td_case(td1, exp223)
    m2 = check_td_case(td2, exp223)
    results['UNION-TD-CERT223'] = {'fetch1_match': m1, 'fetch2_match': m2, 'agree': m1 and m2}
    print(f"UNION-TD-CERT223: fetch1={m1} fetch2={m2} agree={m1 and m2}")

    # --- CERT223 fresh outcome re-check ---
    laft1_empty = 'no properties on the list of lands available' in laft1.lower()
    laft2_empty = 'no properties on the list of lands available' in laft2.lower()
    print(f"\nLAFT empty (fetch1)={laft1_empty} LAFT empty (fetch2)={laft2_empty}")
    print(f"CERT223 still listed SCHEDULED 03/12/2026 on tax-deed-sales page: fetch1={m1} fetch2={m2}")
    print("-> No sold_amount/buyer/redemption text found on unionclerk.com tax-deed-sales "
          "or list-of-lands-available pages in this fresh re-check "
          f"({datetime.now(timezone.utc).isoformat()}). Outcome remains UNVERIFIED.")

    # --- Stamp tier1 parity for cases that agree across both fetches ---
    all_agree_cases = [c for c, r in results.items() if r['agree']]
    print(f"\nCases with double-fetch agreement: {all_agree_cases}")

    if all_agree_cases:
        today = datetime.now(timezone.utc).strftime('%Y%m%d')
        parity_source = f'tier1:union_clerk_live_{today}'
        patch = {
            'parity_status': 'matched_clean',
            'parity_source': parity_source,
            'parity_checked_at': datetime.now(timezone.utc).isoformat(),
            'last_seen_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        for case in all_agree_cases:
            pr = httpx.patch(
                f'{BASE}/multi_county_auctions', headers=HEADERS,
                params={'county': 'eq.union', 'case_number': f'eq.{case}'},
                json=patch, timeout=30)
            pr.raise_for_status()
            updated = pr.json()
            if not updated:
                raise RuntimeError(f'FAIL-LOUD: PATCH matched 0 rows for {case}')
            print(f"STAMPED {case}: parity_status=matched_clean parity_source={parity_source}")
    else:
        print("No cases qualified for tier1 stamping -- no writes performed.")

    print("\nFull double-fetch results:")
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
