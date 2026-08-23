#!/usr/bin/env python3
"""
Gold Standard shard-3 (dispatch 0c873526-996a-4f5d-9123-99836d1d585f), county
union, letters C/D. Third session on this specific case; prior sessions
(dispatch 003dc46a run 12346, and this dispatch's own union_bf_cert223_
duprocess_deed_resolution.py on 2026-08-18) both confirmed case
63-2025-CA-0053 absent from unionclerk.com's live foreclosure-sales
calendar AND absent from a DuProcess parcel/legal-desc search, and left it
classified parity_status='PHANTOM_NOT_ON_CLERK'.

BASELINE (VERIFIED live via pencil_dod_evaluate_county('union'), 2026-08-23):
  C: matched_clean=2/3 (66.7%) FAIL
  D: matched_any=2/3   (66.7%) FAIL
  (both need the 1 remaining row, UNION-TD-CERT223 + 63-2024-CA-0047 already
  matched_clean via tier1:union_clerk_live_20260711 / union_clerk_foreclosure)

THIS SESSION -- NEW FINDING (genuinely new signal since 2026-08-18):
Re-ran the identical DuProcess Official Records portal
(recording.unionclerk.com/DuProcessWebInquiry/) that the 08-18 session used
for the B/F cert-223 fix, but with a DIFFERENT search angle: Name="TD BANK"
(the case's plaintiff) + file-date >= 2026-01-01, instead of Parcel ID /
Legal Description (both of which correctly return 0 rows -- no *deed* was
ever recorded against this parcel, because no sale ever completed).
That surfaced 4 real recorded instruments for TD BANK NA in 2026, none of
which the 08-18 session's parcel/legal-desc searches could have found:

  1. Inst #20260000062, Book 480 Page 6, JUDGMENT, filed 01/12/2026 4:34:33pm
     "REPORT AND RECOMMENDATION OF THE GENERAL MAGISTRATE, FINAL JUDGMENT OF
     FORECLOSURE" -- Case No. 63-2025-CA-000053-CAAM (= our 63-2025-CA-0053),
     TD Bank N.A. vs Linda Andrews Scott (a/k/a Linda P. Scott) et al.
     Page 5/8 explicitly states:
       "Parcel Identification Number 31-05-18-00-000-0101-2"  <- EXACT match
        to our DB parcel_id
       "Property Address: 9534 NW 44th Lane, Lake Butler, FL 32054" <- EXACT
        match to our DB property_address
       Sale of Property scheduled FEBRUARY 26, 2026, 11:00am, Union County
       Courthouse.
     This single document conclusively proves 63-2025-CA-0053 is NOT a
     data-entry/typo/phantom case -- it is real, its parcel_id and address
     were scraped correctly, and it did have a foreclosure judgment entered.

  2. Inst #20260001913, Book 489 Page 561, ORDER, filed 08/03/2026 2:02:33pm
     "ORDER GRANTING TD BANK'S MOTION TO CANCEL FORECLOSURE SALE, VACATE
     FINAL JUDGMENT OF FORECLOSURE AND FOR LEAVE TO AMEND COMPLAINT AND CASE
     CAPTION..." -- same case no. 63-2025-CA-000053-CAAM. Ordered and
     adjudged:
       "2. The foreclosure sale currently scheduled for August 13, 2026 is
           hereby CANCELED."   <- matches our DB auction_date exactly
       "3. The Final Judgment of Foreclosure entered on January 12, 2026, is
           hereby VACATED."
       "4. The Amended Complaint... adds Brittany C. Andrews as a party."
       "5. Case Management Conference... Friday, August 21, 2026."
     This is why the case never appears on unionclerk.com's live "Upcoming
     Foreclosure Sales" list (re-confirmed live this session via
     scripts/clerk_ssot/parsers/union.parse_foreclosure() -> 1 row returned,
     only 63-2024-CA-0047, case 0053 absent) -- there is no scheduled sale
     to list. The case is alive (Case Management Conference set for
     2026-08-21) but has no sale date pending an amended complaint.

CONCLUSION: parity_status='PHANTOM_NOT_ON_CLERK' was WRONG (it implies the
case doesn't exist / was fabricated). The correct classification, per
fleet-wide precedent (see scripts/lake_c_ssot_cancelled_reschedule_recheck_
7bcb4434.py and migration 20260810_gold_standard_shard3_lake_clerk_ssot_cd_
recognition.sql), is parity_status='CLERK_SSOT_CANCELLED' -- a case the
clerk's own court record (not PropertyOnion, not an inference) confirms was
cancelled/vacated. Per that migration's evaluator logic:
  matched_clean (C) requires parity_status IN ('PARITY_OK','CLERK_VERIFIED')
    OR (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
    -- CLERK_SSOT_CANCELLED does NOT qualify (a cancelled sale is not a
    clean match by design -- it is a divergence the SSOT check found).
  matched_any (D) requires parity_status IN ('PARITY_OK','CLERK_VERIFIED',
    'CLERK_SSOT_CANCELLED') OR (parity_status IN ('matched_clean',
    'matched_divergent') AND parity_source LIKE 'tier1%')
    -- CLERK_SSOT_CANCELLED DOES qualify.
So this fix is EXPECTED to flip D to 100% (3/3) while leaving C at 66.7%
(2/3) -- C's structural ceiling for this 3-row denominator is real and
correctly unmovable without a second real clean-matched row appearing
(there are only 3 total union rows; UNION-TD-CERT223 and 63-2024-CA-0047
are already both matched_clean).

WRITE PERFORMED (idempotent, scoped to case_number=63-2025-CA-0053 AND
county=union):
  PATCH multi_county_auctions:
    parity_status: 'PHANTOM_NOT_ON_CLERK' -> 'CLERK_SSOT_CANCELLED'
    parity_source: -> 'union_clerk_official_records:recording.unionclerk.com/
                        DuProcessWebInquiry/Inst-20260001913'
    parity_checked_at: -> now() (this session's live check timestamp)
  No sold_amount/dollar figures touched (B/F untouched, correctly -- this
  case never sold, it was cancelled pre-sale).
  No parcel_id/coordinate/zone_code touched (E/I untouched).
  No auction_date change: leaving auction_date=2026-08-13 as the historical
  scraped value (matches what was true when unionclerk_official scraped it
  on 2026-07-03) rather than fabricating a new date -- the case currently
  has NO scheduled sale date per the cancellation order, so there is no
  real forward date to write, and inventing one would be fabrication.
"""
import json
import os
import urllib.request

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

CASE_NUMBER = '63-2025-CA-0053'
COUNTY = 'union'

PATCH_BODY = {
    'parity_status': 'CLERK_SSOT_CANCELLED',
    'parity_source': (
        'union_clerk_official_records:recording.unionclerk.com/'
        'DuProcessWebInquiry/Inst-20260001913 (Order Granting Motion to '
        'Cancel Foreclosure Sale and Vacate Final Judgment, Case '
        '63-2025-CA-000053-CAAM, filed 2026-08-03, Book 489 Page 561; '
        'cross-referenced against Inst-20260000062 Final Judgment of '
        'Foreclosure, filed 2026-01-12, Book 480 Page 6, confirming exact '
        'parcel_id 31-05-18-00-000-0101-2 and property_address 9534 NW '
        '44th Lane match)'
    ),
}


def _request(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'{BASE}{path}', data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode() or 'null')


def main() -> None:
    path = f'/multi_county_auctions?case_number=eq.{CASE_NUMBER}&county=eq.{COUNTY}'
    status, body = _request('PATCH', path, PATCH_BODY)
    print(f'PATCH multi_county_auctions -> {status}')
    print(json.dumps(body, indent=2))

    if status >= 300:
        raise SystemExit(f'FAIL-LOUD: PATCH returned {status}, aborting before verify')
    if isinstance(body, list) and len(body) != 1:
        raise SystemExit(f'FAIL-LOUD: expected exactly 1 row updated, got {len(body) if isinstance(body, list) else body}')

    status, body = _request(
        'POST', '/rpc/pencil_dod_evaluate_county', {'p_county': COUNTY}
    )
    print(f'pencil_dod_evaluate_county -> {status}')
    print(json.dumps(body, indent=2))


if __name__ == '__main__':
    main()
