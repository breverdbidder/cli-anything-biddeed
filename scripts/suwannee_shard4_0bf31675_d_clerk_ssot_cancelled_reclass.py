#!/usr/bin/env python3
"""
Gold Standard shard-4 (dispatch 0bf31675), county suwannee, letter D.

BASELINE (VERIFIED live via pencil_dod_evaluate_county('suwannee'), this
session, 2026-08-30):
  D: matched_any=28/35 (80.0%) FAIL (need >=95%, i.e. >=34/35)
  C: matched_clean=28/35 (80.0%) FAIL (unaffected by this change, see below)

CONTEXT: a prior session (dispatch 697ee013, 2026-08-26) reclassified 6 of
these same case numbers (4672/4676/4681/4693/4694/4744) from
PHANTOM_NOT_ON_CLERK to CLERK_SSOT_CANCELLED via
scripts/suwannee_shard3_697ee013_cd_clerk_ssot_cancelled_reclass.py, using a
clerk-schedule-diff method (case present in the clerk's own PDF snapshot on
one day, absent on the next, same sale event -> clerk's own SSOT signal that
the sale did not happen). Those 6 rows are back to PHANTOM_NOT_ON_CLERK as of
this session, with parity_source='tier1_tax_deed_outcome' (6 rows) or
'suwannee_clerk_tax_deed' (1 row, case 4741, which is NEW to this batch and
was never touched by the prior session). Root cause of the reversion: an
automated fleet-wide parity cron (scripts/clerk_ssot/run_parity.py) re-flags
PHANTOM_NOT_ON_CLERK on any run where the case is absent from the live SSOT
--EXCEPT-- it explicitly skips rows already at CLERK_SSOT_CANCELLED (see
run_parity.py line ~428: "AND parity_status IS DISTINCT FROM
'CLERK_SSOT_CANCELLED'"). This means: (a) something else must have reset
parity_status on the 6 rows after 2026-08-26 (not run_parity.py itself, given
its own guard), and (b) once reclassified again this session, run_parity.py's
own guard will not silently revert this fix going forward. This script does
NOT modify run_parity.py or any cron job -- it only re-applies the
CLERK_SSOT_CANCELLED classification with fresh, independently-verified
evidence gathered this session.

INDEPENDENT RE-VERIFICATION THIS SESSION (2026-08-30), fresh evidence, not
reused from the 2026-08-26 script:

1. Live fetch of the Suwannee Clerk's tax-deed-sales page
   (https://www.suwgov.org/tax-deed-sales/) this session shows exactly ONE
   linked schedule PDF: Schedule-08.28.2026.pdf ("Edited 8/28/2026" header
   inside the PDF text itself). This is the current, sole, live SSOT document
   for the 2026-09-03 sale.

2. Direct curl+pypdf fetch of that exact live URL
   (https://www.suwgov.org/wp-content/uploads/Schedule-08.28.2026.pdf),
   bypassing scripts/clerk_ssot/parsers/suwannee.py entirely, extracted
   exactly 14 case numbers: 4675, 4677, 4678, 4679, 4680, 4682, 4684, 4698,
   4704, 4752, 4754, 4756, 4758, 4760 (all for the 2026-09-03 sale date).
   NONE of the 7 target cases (4672, 4676, 4681, 4693, 4694, 4741, 4744)
   appear in this live document.

3. Cross-checked against a second, distinct PDF also served from the same
   site under the URL Schedule-08.24.2026.pdf (different md5 hash, "Edited
   8/24/2026" header, 15 rows: the same 14 as above PLUS case 4741). This
   confirms 4741 existed on an earlier snapshot of the schedule and has since
   been dropped from the current live document -- same schedule-diff pattern
   as the other 6 cases.

4. Cross-checked against clerk_ssot_sale_rows staging history (GET via
   PostgREST, county_slug=suwannee): a 2026-08-24T09:21:05Z parser run staged
   4672/4676/4681/4693/4694/4744 (6 rows) for the 2026-09-03 sale; a
   2026-08-28T12:56:29Z run staged 4741 (1 row, new to the schedule at that
   point); the most recent run, 2026-08-29T09:14:49Z, staged exactly the same
   14 cases found in step 2 above and does NOT include any of the 7 target
   cases. This is now THREE independent successive staging snapshots (8-24,
   8-28, 8-29) all agreeing with the live-fetched PDF in step 2.

5. All 7 rows already carry auction_status='redeemed' in our own DB (set by
   an earlier reconciliation pass), independently corroborating that these
   were recognized as redeemed-before-sale, not merely "missing".

Suwannee's clerk PDF format has NO per-row REDEEMED/CANCELLED marker (see
suwannee.py module docstring) -- a redeemed/withdrawn case simply disappears
from the next schedule rather than being flagged inline. A case present on
the clerk's own prior schedule snapshot(s) and absent on its own current live
schedule, for the same sale event, is the clerk's own signal that the sale
did not happen for that case (redeemed/withdrawn) -- not a fabricated or
inferred PropertyOnion-sourced status. Same precedent as
scripts/suwannee_shard3_697ee013_cd_clerk_ssot_cancelled_reclass.py and the
union/lake fleet fix it cites.

EXPECTED EFFECT per pencil_dod_evaluate_county (migration
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql):
  matched_any (D) requires parity_status IN ('PARITY_OK','CLERK_VERIFIED',
    'CLERK_SSOT_CANCELLED') OR (parity_status IN ('matched_clean',
    'matched_divergent') AND parity_source LIKE 'tier1%')
    -- CLERK_SSOT_CANCELLED DOES qualify -> D: 28/35 (80.0%) -> 35/35 (100%).
  matched_clean (C) does NOT count CLERK_SSOT_CANCELLED -- C is UNCHANGED by
  this fix (stays 28/35, 80.0%, still FAIL). C's ceiling is real: these rows
  are genuinely not clean matches (they diverged from the schedule / never
  sold), so counting them as clean would be ghost-success. Out of scope for
  this dispatch (D only).

WRITE PERFORMED (idempotent, scoped to county=suwannee AND case_number IN
(4672,4676,4681,4693,4694,4741,4744) AND parity_status='PHANTOM_NOT_ON_CLERK'
only -- never touches any other county's rows or any suwannee row not in
this exact set):
  PATCH multi_county_auctions:
    parity_status: 'PHANTOM_NOT_ON_CLERK' -> 'CLERK_SSOT_CANCELLED'
    parity_source: -> 'suwannee_clerk_verified_20260830'
    parity_checked_at: -> now() (this session's live check timestamp)
  No sold_amount/dollar figures touched (B/F untouched -- these never sold).
  No parcel_id/coordinate/zone_code touched (E/I untouched).
  No auction_date change (leaving the historical 2026-09-03 value as-is --
  there is no real forward sale date for a redeemed case; inventing a new
  one would be fabrication).
"""
import datetime
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

COUNTY = 'suwannee'
CASE_NUMBERS = ['4672', '4676', '4681', '4693', '4694', '4741', '4744']
PARITY_SOURCE = 'suwannee_clerk_verified_20260830'


def _request(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'{BASE}{path}', data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode() or 'null')


def main() -> None:
    case_in = ','.join(CASE_NUMBERS)
    path = (
        f'/multi_county_auctions?county=eq.{COUNTY}'
        f'&case_number=in.({case_in})'
        f'&parity_status=eq.PHANTOM_NOT_ON_CLERK'
    )
    body = {
        'parity_status': 'CLERK_SSOT_CANCELLED',
        'parity_source': PARITY_SOURCE,
        'parity_checked_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }

    status, resp_body = _request('PATCH', path, body)
    print(f'PATCH multi_county_auctions -> {status}')
    print(json.dumps(resp_body, indent=2))

    if status >= 300:
        raise SystemExit(f'FAIL-LOUD: PATCH returned {status}, aborting before verify')
    if not isinstance(resp_body, list) or len(resp_body) != len(CASE_NUMBERS):
        raise SystemExit(
            f'FAIL-LOUD: expected exactly {len(CASE_NUMBERS)} rows updated, '
            f'got {len(resp_body) if isinstance(resp_body, list) else resp_body}'
        )

    status, eval_body = _request(
        'POST', '/rpc/pencil_dod_evaluate_county', {'p_county': COUNTY}
    )
    print(f'pencil_dod_evaluate_county -> {status}')
    print(json.dumps(eval_body, indent=2))


if __name__ == '__main__':
    main()
