#!/usr/bin/env python3
"""
Gold Standard shard-3 (dispatch 697ee013-cc20-4655-bdf7-14e820c464b2), county
suwannee, letters C/D.

BASELINE (VERIFIED live via pencil_dod_evaluate_county('suwannee'), this
session, 2026-08-26):
  C: matched_clean=29/35 (82.9%) FAIL (need >=95%, i.e. >=34/35)
  D: matched_any=29/35   (82.9%) FAIL (same threshold)
  A/B/E/F/G/H/I/J all PASS, unaffected by this change.

ROOT CAUSE (evidence chain, all live-verified this session):
1. multi_county_auctions has 35 suwannee rows: 4 foreclosure (all
   matched_clean via tier1:clerk_fc_direct) + 31 tax_deed.
2. Of the 31 tax_deed rows: 8 are matched_clean (tax_deed sales that already
   closed, parity_source=tier1_official_platform_open_auction_parcel), 15 are
   parity_status='PARITY_OK' (clerk_ssot clean matches against the CURRENT
   live schedule), and 6 are parity_status='PHANTOM_NOT_ON_CLERK':
   case_number 4672, 4676, 4681, 4693, 4694, 4744.
3. scripts/clerk_ssot/parsers/suwannee.py fetches ONE PDF per upcoming sale
   event from www.suwgov.org/tax-deed-sales/ (currently
   Schedule-08.24.2026.pdf, sale date 2026-09-03). Re-ran this parser live
   this session: returns exactly 15 rows (4675,4677,4678,4679,4680,4682,
   4684,4698,4704,4741,4752,4754,4756,4758,4760) -- matches all 15 PARITY_OK
   rows exactly, confirms none of the 6 PHANTOM cases are on the current
   schedule.
4. Checked scripts/clerk_ssot/parsers/suwannee.py's own staging history in
   clerk_ssot_sale_rows (GET via PostgREST, county_slug=suwannee): a PRIOR
   run on 2026-08-24T09:21:05Z staged 20 rows for the SAME 2026-09-03 sale
   date, INCLUDING all 6 of the now-phantom cases (4672/2024-1229,
   4676/2024-2663, 4681/2019-2273, 4693/2024-2221, 4694/2024-2275,
   4744/2024-377). The very next parser run, 2026-08-25T09:18:01Z, staged
   only 15 rows for the same sale date -- the 6 cases are GONE from the
   clerk's own published schedule between those two runs.
5. Independently re-fetched the exact live PDF URL
   (https://www.suwgov.org/wp-content/uploads/Schedule-08.24.2026.pdf) fresh
   this session (2026-08-26) via direct curl+pypdf (bypassing the parser
   entirely, to rule out a parser bug) -- confirms the SAME 15 rows, same 6
   cases absent.
6. All 6 PHANTOM rows already carry auction_status='redeemed' in our own DB
   (set by an earlier reconciliation pass, corroborating independently that
   these were recognized as redeemed-before-sale, not merely "missing").

Suwannee's clerk PDF format has NO per-row REDEEMED/CANCELLED marker (see
suwannee.py module docstring) -- it only ever lists currently-active upcoming
sales, so a redeemed case simply disappears from the next PDF rather than
being flagged inline. This is the same structural shape fixed for union
(scripts/union_gsd3_0c873526_c_d_ssot_cancelled_fix.py, migration
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql): a case
present on the clerk's OWN prior schedule and absent on its OWN current
schedule, for the same sale event, is the clerk's own signal that the sale
did not happen for that case (redeemed/withdrawn) -- not a fabricated or
inferred PropertyOnion-sourced status.

CONCLUSION: parity_status='PHANTOM_NOT_ON_CLERK' is the WRONG classification
for these 6 rows (it implies "never existed on the clerk's calendar at all" /
data-entry error). The correct classification, per the union/lake fleet
precedent, is 'CLERK_SSOT_CANCELLED' -- the clerk's own record (two
successive snapshots of its own published schedule) confirms these sales
were cancelled/redeemed pre-sale.

Per pencil_dod_evaluate_county's evaluator (migration
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql):
  matched_clean (C) requires parity_status IN ('PARITY_OK','CLERK_VERIFIED')
    OR (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
    -- CLERK_SSOT_CANCELLED does NOT qualify (correctly -- a cancelled sale
    is a divergence the SSOT found, not a no-divergence clean match).
  matched_any (D) requires parity_status IN ('PARITY_OK','CLERK_VERIFIED',
    'CLERK_SSOT_CANCELLED') OR (parity_status IN ('matched_clean',
    'matched_divergent') AND parity_source LIKE 'tier1%')
    -- CLERK_SSOT_CANCELLED DOES qualify.
So this fix is EXPECTED to flip D from 29/35 (82.9%) to 35/35 (100%, PASS),
while C stays at 29/35 (82.9%, still FAIL) -- C's structural ceiling here is
real: these 6 rows are genuinely not clean matches (they never sold /
diverged from the original schedule), so counting them as "clean" would be
ghost-success. C needs 5 more real net-new clean-matched rows (34/35) which
does not exist in the current 35-row denominator without new auction
ingestion -- out of scope for this session (no fabrication).

WRITE PERFORMED (idempotent, scoped to county=suwannee AND
case_number IN (4672,4676,4681,4693,4694,4744) AND
parity_status='PHANTOM_NOT_ON_CLERK' only -- never touches any other
county's rows or any suwannee row not in this exact set):
  PATCH multi_county_auctions:
    parity_status: 'PHANTOM_NOT_ON_CLERK' -> 'CLERK_SSOT_CANCELLED'
    parity_source: -> 'suwannee_clerk_tax_deed:schedule-diff 2026-08-24->
                        2026-08-25 (case present in prior PDF snapshot,
                        absent in current+re-fetched-live PDF for same
                        2026-09-03 sale date); auction_status=redeemed
                        already set, corroborating'
    parity_checked_at: -> now() (this session's live check timestamp)
  No sold_amount/dollar figures touched (B/F untouched -- these never sold).
  No parcel_id/coordinate/zone_code touched (E/I untouched).
  No auction_date change (leaving the historical 2026-09-03 value as-is --
  there is no real forward sale date for a redeemed case; inventing a new
  one would be fabrication).
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

COUNTY = 'suwannee'
CASE_NUMBERS = ['4672', '4676', '4681', '4693', '4694', '4744']

PARITY_SOURCE = (
    'suwannee_clerk_tax_deed:schedule-diff 2026-08-24->2026-08-25 '
    '(case present in clerk_ssot_sale_rows staged 2026-08-24T09:21:05Z '
    'snapshot of Schedule-08.24.2026.pdf, absent in 2026-08-25T09:18:01Z '
    'snapshot and in a fresh independent re-fetch of the same live PDF URL '
    'this session, 2026-08-26, both for the same 2026-09-03 sale date; '
    'auction_status=redeemed already set in DB, corroborating)'
)

PATCH_BODY = {
    'parity_status': 'CLERK_SSOT_CANCELLED',
    'parity_source': PARITY_SOURCE,
    'parity_checked_at': None,  # set to now() server-side via separate call below
}


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
    body = dict(PATCH_BODY)
    body['parity_checked_at'] = 'now()'  # PostgREST needs a literal value, handled below

    # PostgREST doesn't evaluate SQL functions in JSON PATCH bodies; use an
    # explicit ISO timestamp captured at request time instead.
    import datetime
    body['parity_checked_at'] = datetime.datetime.utcnow().isoformat() + 'Z'

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
