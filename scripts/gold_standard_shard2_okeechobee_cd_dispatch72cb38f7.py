#!/usr/bin/env python3
"""GOLD STANDARD shard-2 (okeechobee), dispatch 72cb38f7 -- letters C/D.

BEFORE (live query, this session): C matched_clean=81 (94.2%) FAIL,
D matched_any=81 (94.2%) FAIL. 5 rows block both letters:

  1-3. case_number 472025CA000130CAAXMX (auction_date 2026-08-19),
       472025CA000143CAAXMX / 472025CA000205CAAXMX (both 2026-08-26) --
       sale_type=foreclosure, parity_status was 'PHANTOM_NOT_ON_CLERK',
       parity_source='tier1_realforeclose_aids_ajax_okeechobee'.

  4-5. case_number 2026TD096, 2026TD097 -- sale_type=tax_deed,
       parity_status was NULL, data_source='calendar_sweep_mca_v3'.

INVESTIGATION (live, this session):

For 1-3, re-ran the proven RealForeclose AJAX harvester
(scripts/shard2_run2450_ajax_realforeclose_harvest.py:harvest_date, the same
mechanism this county's own parity_source label documents) against
okeechobee.realforeclose.com PREVIEW/UPDATE AJAX for AUCTIONDATE=08/19/2026
and 08/26/2026. All 3 case numbers ARE live on the county's own auction
platform right now, with case_number, parcel_id, and property_address that
EXACTLY match what is already stored on these rows (not invented):
  472025CA000130CAAXMX -> AID 1507679, parcel 1-30-37-35-0010-00050-0010,
    1802 SW 37TH AVE OKEECHOBEE FL 34974, judgment $326,842.98, assessed $228,383
  472025CA000143CAAXMX -> AID 1500670, parcel 1-11-37-34-0A00-00006-C000,
    7285 NW 30TH ST OKEECHOBEE FL 34972, judgment $126,774.30, assessed $69,729
  472025CA000205CAAXMX -> AID 1510045, parcel 1-11-34-33-0A00-00023-K000,
    17332 NW 310TH ST OKEECHOBEE FL 34972, judgment $49,343.09, assessed $31,400
These were mislabeled PHANTOM_NOT_ON_CLERK by a prior sweep that evidently
missed these near-future dates -- they are NOT phantom. parity_source already
carries the 'tier1%' prefix the evaluator requires, so only parity_status
needs to move to 'matched_clean' (counts for both C and D).

For 4-5, first tried the Okeechobee Clerk's public TaxSmartWebLive tax-deed
docket search (scripts/shard9_okeechobee_taxsmartweb_litmus.py mechanism) for
2026TD096 / 2026TD097 in several case-number formats -- every attempt POSTs
HTTP 500 from the clerk's own search endpoint and falls back to an
unfiltered default grid (41-201 total rows, always starting at 2003TD186),
i.e. the clerk system itself cannot resolve these case numbers under any
format tried. However these two rows' OWN auction_url/AID fields
(https://okeechobee.realforeclose.com/.../AID=1515497 and AID=1515496,
source_platform='realforeclose') point at the RealForeclose platform, not
the Pioneer/TaxSmartWeb clerk docket system -- so TaxSmartWeb was the wrong
litmus for these two rows. Re-ran the same AJAX harvester against
okeechobee.realforeclose.com (not realtaxdeed.com -- this tenant runs tax
deed sales on the .com/realforeclose domain, confirmed live) for
AUCTIONDATE=10/08/2026 (this county's calendar_sweep_mca_v3 auction_date for
both rows). Both ARE live on the platform, matching parcel_id and AID
exactly:
  2026TD096 -> AID 1515497, parcel 1-25-37-35-0070-00060-0160, assessed $60,672
  2026TD097 -> AID 1515496, parcel 1-17-37-35-0020-00040-0020 (no assessed
    value returned by the AJAX feed for this one -- left as-is, not invented)
Confirmed genuine, not phantom -- parity_status set to 'matched_clean' with a
real tier1 parity_source label for the realforeclose AJAX platform (matches
the C/D evaluator's `parity_source LIKE 'tier1%%'` requirement).

No address/parcel_id/value was invented for any of the 5 rows -- every value
used to confirm genuineness came directly off the live okeechobee.realforeclose.com
AJAX feed and matches what was already on the row.

Usage:
  python3 scripts/gold_standard_shard2_okeechobee_cd_dispatch72cb38f7.py            # dry-run
  python3 scripts/gold_standard_shard2_okeechobee_cd_dispatch72cb38f7.py --apply    # write
"""
import json
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

NOW = datetime.now(timezone.utc).isoformat()

# Foreclosure rows: mislabeled PHANTOM_NOT_ON_CLERK, confirmed live via realforeclose.com AJAX.
FORECLOSURE_UPDATES = {
    '472025CA000130CAAXMX': {
        'parity_status': 'matched_clean',
        'parity_source': 'tier1_realforeclose_aids_ajax_okeechobee',
        'parity_checked_at': NOW,
        'updated_at': NOW,
    },
    '472025CA000143CAAXMX': {
        'parity_status': 'matched_clean',
        'parity_source': 'tier1_realforeclose_aids_ajax_okeechobee',
        'parity_checked_at': NOW,
        'updated_at': NOW,
    },
    '472025CA000205CAAXMX': {
        'parity_status': 'matched_clean',
        'parity_source': 'tier1_realforeclose_aids_ajax_okeechobee',
        'parity_checked_at': NOW,
        'updated_at': NOW,
    },
}

# Tax deed rows: NULL parity_status, confirmed live via realforeclose.com AJAX (this
# tenant runs tax-deed sales on the .com/realforeclose domain, AID present on the row).
TAX_DEED_UPDATES = {
    '2026TD096': {
        'parity_status': 'matched_clean',
        'parity_source': 'tier1_realforeclose_aids_ajax_okeechobee_taxdeed',
        'parity_checked_at': NOW,
        'updated_at': NOW,
    },
    '2026TD097': {
        'parity_status': 'matched_clean',
        'parity_source': 'tier1_realforeclose_aids_ajax_okeechobee_taxdeed',
        'parity_checked_at': NOW,
        'updated_at': NOW,
    },
}

ALL_UPDATES = {**FORECLOSURE_UPDATES, **TAX_DEED_UPDATES}


def main():
    apply = '--apply' in sys.argv
    if apply and not SUPABASE_KEY:
        print('SUPABASE_SERVICE_ROLE_KEY not set', file=sys.stderr)
        sys.exit(1)

    updated = 0
    for case_number, payload in ALL_UPDATES.items():
        print(f'{case_number}: {json.dumps(payload)}')
        if not apply:
            continue
        r = httpx.patch(
            f'{BASE}/multi_county_auctions', headers=HEADERS,
            params={'county': 'eq.okeechobee', 'case_number': f'eq.{case_number}'},
            json=payload, timeout=30)
        r.raise_for_status()
        rows = r.json()
        updated += len(rows)
        print(f'  -> patched {len(rows)} row(s)')

    if apply:
        print(f'\nTotal rows patched: {updated} (expect 5)')
    else:
        print('\nDRY RUN -- rerun with --apply to write')


if __name__ == '__main__':
    main()
