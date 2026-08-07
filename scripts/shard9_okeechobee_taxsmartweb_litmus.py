#!/usr/bin/env python3
"""
Okeechobee C/D: free/anonymous clerk-official litmus via TaxSmartWebLive.

RealAuction (okeechobee.realforeclose.com) requires an authenticated/registered
session we don't have credentials for. PropertyOnion has never scraped these
small rural tax-deed cases (po_scraped_at IS NULL). Per the standing
authorization to adopt clerk/official-records as supplementary litmus when
PropertyOnion coverage is the root cause, this hits the Okeechobee Clerk's own
Pioneer TaxSmartWebLive system (no login/CAPTCHA, verified live 2026-07-02).

Covers TD-format case numbers only -- CA/CC (civil foreclosure) cases live in
Civitek OCRS, which is anonymous but server-side Cloudflare-Turnstile-gated on
every search submission (confirmed blocked via curl + headless Playwright).

dispatch_id: 42a676fd-34f7-4327-bb0f-b7ac3d18dd7d
"""
import os
import re
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

TAXSMARTWEB_BASE = 'https://pioneer.okeechobeelandmark.com/TaxSmartWebLive'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')


def fetch_taxsmartweb_case(case_number: str) -> dict | None:
    """Fetch a single TD case from the Clerk's public TaxSmartWebLive search. No login required."""
    client = httpx.Client(timeout=30, follow_redirects=True, headers={'User-Agent': UA})
    client.get(TAXSMARTWEB_BASE)
    client.post(f'{TAXSMARTWEB_BASE}/', data={'SearchForCase': case_number, 'buttonSubmitCase': ''})
    r = client.get(f'{TAXSMARTWEB_BASE}/Home/GridSearchData',
                    params={'SearchType': 'Case #', '_search': 'false', 'rows': '25', 'page': '1', 'sidx': '', 'sord': 'asc'})
    r.raise_for_status()
    data = r.json()
    if not data.get('rows'):
        return None
    cell = data['rows'][0]['cell']
    # cell = [applicant, case_number, cert_number, parcel_id, auction_date(M/D/YYYY), status, opening_bid, high_bid, surplus, owners]
    return {
        'applicant': cell[0], 'case_number': cell[1], 'cert_number': cell[2],
        'parcel_id': cell[3], 'auction_date': cell[4], 'status': cell[5],
        'opening_bid': float(re.sub(r'[^\d.]', '', cell[6])) if cell[6] else None,
    }


def get_mca_row(county: str, case_number: str) -> dict | None:
    r = httpx.get(f'{BASE}/multi_county_auctions', headers=HEADERS,
                  params={'county': f'eq.{county}', 'case_number': f'eq.{case_number}',
                          'select': 'parcel_id,auction_date,opening_bid'}, timeout=20)
    rows = r.json()
    return rows[0] if rows else None


def apply_match(county: str, case_number: str, confidence: float, divergences: dict | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    fetch_date = now[:10]
    payload = {
        'parity_status': 'matched_clean' if not divergences else 'matched_divergent',
        'parity_source': f'tier1_{county}_taxsmartweb_clerk_shard9:{fetch_date}',
        'parity_checked_at': now,
        'parity_confidence': confidence,
        'parity_divergences': divergences,
        'tier1_verified_at': now,
        'tier1_authoritative': True,
        'updated_at': now,
    }
    r = httpx.patch(f'{BASE}/multi_county_auctions', headers=HEADERS,
                     params={'county': f'eq.{county}', 'case_number': f'eq.{case_number}'},
                     json=payload, timeout=30)
    r.raise_for_status()


def main(county: str, case_numbers: list[str]) -> None:
    matched, divergent, not_found = [], [], []
    for case_number in case_numbers:
        clerk = fetch_taxsmartweb_case(case_number)
        if clerk is None:
            not_found.append(case_number)
            continue
        mca = get_mca_row(county, case_number)
        if mca is None:
            not_found.append(case_number)
            continue
        divergences = {}
        if clerk['parcel_id'] and mca.get('parcel_id') and clerk['parcel_id'] != mca['parcel_id']:
            divergences['parcel_id'] = {'clerk': clerk['parcel_id'], 'ours': mca['parcel_id']}
        if mca.get('opening_bid') is not None and clerk['opening_bid'] is not None \
                and abs(mca['opening_bid'] - clerk['opening_bid']) > 0.01:
            divergences['opening_bid'] = {'clerk': clerk['opening_bid'], 'ours': mca['opening_bid']}
        apply_match(county, case_number, confidence=1.0 if not divergences else 0.7, divergences=divergences or None)
        (divergent if divergences else matched).append(case_number)
        print(f'{case_number}: {"matched_divergent" if divergences else "matched_clean"} '
              f'(clerk={clerk})')
    print(f'\nmatched_clean={len(matched)} matched_divergent={len(divergent)} not_found={len(not_found)}')
    if not_found:
        print(f'NOT FOUND (raise if this should never happen): {not_found}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: shard9_okeechobee_taxsmartweb_litmus.py <county> <case_number> [case_number...]')
        sys.exit(1)
    main(sys.argv[1], sys.argv[2:])
