#!/usr/bin/env python3
"""Levy County letters C/D (calendar parity) fix, GOLD STANDARD shard-2,
dispatch 72cb38f7.

Before: {"C": {"pass": false, "detail": "matched_clean=28", "metric": 93.3},
         "D": {"pass": false, "detail": "matched_any=28", "metric": 93.3}}

Two rows were blocking both letters. This script investigates both LIVE on
the Levy County clerk's own systems (no third-party aggregators trusted as
authoritative) and applies only what is confirmed by a real clerk record —
per HONESTY PROTOCOL / BLANK > WRONG, it does not force a false-positive
status on anything it could not verify.

Row 1 — case_number='2026-4162' (tax_deed), parity_status was
  'PHANTOM_NOT_ON_CLERK'. Investigated live via Levy's TaxSmartWeb app
  (online.levyclerk.com/TaxSmartWeb — NOT taxsmart.levyclerk.com, that
  hostname does not resolve; the real host was found via WebSearch after
  the raw hostname in the task description failed DNS). The app's
  grid-data JSON endpoint (Home/GridSearchData?SearchType=Case%20%23)
  returned exactly ONE matching row for a Case# search on "2026-4162":
    id=5038, CaseNumber="2026-4162TD", CertificateNumber="3710-23",
    ParcelID="09380-010-00" (EXACT match to our row's parcel_id),
    SaleDate="8/10/2026" (EXACT match to our row's auction_date),
    Status="SOLD", BaseBid="$1,171.86", HighBid="$6,100.00",
    Surplus="$4,882.86".
  The full case-detail page (Home/Details?id=5038) confirms every field:
  Legal description LOT 11 BLOCK 32 OAK RIDGE ESTATES, applicant BEAMIF A
  LLC, owners DONALD W FALLON / ALICE C SWANSON, Property Appraiser is
  qpublic.net/levy (Levy uses qPublic, not its own domain).
  VERDICT: this is a REAL, clerk-confirmed case — not a phantom. It was
  auctioned and sold on 2026-08-10 (matches auction_date). Updated to
  parity_status='PARITY_OK' with parity_source tagged to reflect the live
  clerk verification actually performed this session.

Row 2 — case_number='2025000075CAAXMX' (foreclosure), parity_status was
  NULL (placeholder row from a prior manual fix,
  data_source='cert-fix-criteria-1letter-manual-verify'). Investigated via
  Levy's OCRS (Online Court Records Search, Civitek-hosted at
  civitekflorida.com/ocrs/county/38/ — linked from
  levyclerk.com/.../electronic-court-records-access/). Successfully
  navigated the full stateful JSF flow (access-option -> disclaimer ->
  case-search tab, year=2025 / court type=CA / seq=000075) but the actual
  "Search" submit is gated behind a Cloudflare Turnstile CAPTCHA
  (onSearch2 -> validateUser() -> PrimeFaces.ab with a Turnstile token
  argument) that cannot be solved by a scripted session. This is a real,
  confirmed technical block on the ONLY authoritative source for this
  case, not a data-absence signal. Levy's public foreclosure-sales page
  (levyclerk.com/.../foreclosure-sales/) shows "There are no foreclosure
  sales available at this time" which is consistent with this case's
  auction_date of 2026-04-20 already being in the past (today is
  2026-08-13) and tells us nothing about whether the case itself is real.
  VERDICT: UNVERIFIABLE this session — left untouched. Reporting honestly
  per BLANK > WRONG rather than guessing a parity_status.

Usage:
  python3 scripts/gold_standard_shard2_levy_cd_dispatch72cb38f7.py            # dry-run
  python3 scripts/gold_standard_shard2_levy_cd_dispatch72cb38f7.py --apply    # write

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ACCESS_TOKEN
"""
import json
import os
import sys

import httpx

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_KEY']
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json', 'Prefer': 'return=representation',
}

# Only row 1 is actionable this session — verified live against Levy County's
# TaxSmartWeb clerk system (see docstring for full evidence chain).
PATCH_ROW_1 = {
    'county': 'levy',
    'case_number': '2026-4162',
    'body': {
        'parity_status': 'PARITY_OK',
        'parity_source': 'tier1_clerk_court_verified_manual_taxsmartweb_2026-08-13',
    },
}

# Row 2 (case_number='2025000075CAAXMX') is intentionally NOT included here:
# the Levy OCRS (civitekflorida.com/ocrs/county/38/) case-search submit is
# gated by a Cloudflare Turnstile CAPTCHA that could not be solved this
# session. No write is made for this row — leaving parity_status=NULL
# untouched rather than fabricating a value. See docstring for the full
# navigation trace (access-option -> disclaimer -> case-search tab reached
# successfully; only the final "Search" POST is CAPTCHA-gated).


def main():
    apply = '--apply' in sys.argv
    print('Row 1 (2026-4162, tax_deed): VERIFIED live on TaxSmartWeb — real, SOLD case, '
          'parcel_id and auction_date match exactly. Will set parity_status=PARITY_OK.')
    print('Row 2 (2025000075CAAXMX, foreclosure): UNVERIFIABLE this session — Levy OCRS '
          'case-search is behind a Cloudflare Turnstile CAPTCHA. NOT touched. '
          'Reported honestly per BLANK > WRONG.')

    if not apply:
        print('DRY RUN (no --apply flag). No DB writes performed.')
        print(json.dumps(PATCH_ROW_1, indent=2))
        return

    with httpx.Client(timeout=60) as c:
        r = c.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={'county': f"eq.{PATCH_ROW_1['county']}", 'case_number': f"eq.{PATCH_ROW_1['case_number']}"},
            content=json.dumps(PATCH_ROW_1['body']),
        )
        if r.status_code >= 400:
            raise RuntimeError(f'PATCH failed {r.status_code}: {r.text[:500]}')
        rows = r.json()
        if len(rows) != 1:
            raise RuntimeError(
                f'FAIL-LOUD: expected exactly 1 row updated for case_number=2026-4162, got {len(rows)}'
            )
        print(f'PATCHed 1 row: {json.dumps(rows[0], default=str)}')


if __name__ == '__main__':
    main()
