#!/usr/bin/env python3
"""Miami-Dade Gold Standard letter C -- session 2026-09-02.

See supabase/migrations/20260902c_miami_dade_c_null_parity_triage.sql for the
full root-cause analysis. This script performs the live PostgREST writes; each
PATCH is id-scoped and re-running it is safe (idempotent).

Full triage of the 73 parity_status IS NULL rows (miami_dade, non-propertyonion,
tier1_authoritative-eligible population, county='miami_dade'):

  31 rows -- 2026-09-02T07:55:38 batch, sale_date Oct 2026 (future, unresolved).
             Left NULL: no auction has happened yet, nothing to match.
  24 rows -- pre-existing "wrong-track ghost" rows already identified and
             correctly reverted to NULL by the prior session
             (20260901_shard3_miami_dade_cd_ghost_success_correction.sql /
             gold_standard_shard3_miami_dade_20260901_cd_fix.py). Re-verified
             live this session: each row is sale_type=tax_deed with its only
             matching foreclosure_outcomes row being sale_type=foreclosure for
             the SAME case_number (a different track of the same case) --
             the outcome does not back the tax_deed row. Left NULL, untouched.
   5 rows -- data_source=realauction_winner_harvest, tier1_authoritative=false,
             tier1_sale_status NULL, zero foreclosure_outcomes/tax_deed_outcomes
             backing found live. Genuinely unknown. Left NULL, untouched.
  10 rows -- tier1_sale_status=LISTED, sale_date=2026-09-03 (auction has not
             yet run). Left NULL: correctly unresolved.
   1 row  -- tier1_sale_status=JUDGMENT_VACATED/DISMISSED. Ambiguous per prior
             session's precedent (not treated as clean match or cancellation
             without further research). Left NULL, untouched.
   2 rows -- tier1_sale_status IN (CANCELED_PER_ORDER, CANCELED_PER_BANKRUPTCY),
             tier1_authoritative=true, data_source=realtaxdeed (county's own
             tier1 harvester, non-propertyonion). Genuine clerk-confirmed
             cancellations -- FIXED this session: stamped
             parity_status='CLERK_SSOT_CANCELLED' (counts toward D=matched_any
             by design; deliberately excluded from C=matched_clean per the
             20260810 lake_clerk_ssot migration's C/D distinction).
  ---
  73 total

RESULT: C (matched_clean) numerator does NOT move -- none of the 73 rows had
real matched_clean evidence (verified live against foreclosure_outcomes and
tax_deed_outcomes for every non-future, non-wrong-track row). C is a confirmed
structural block at 568/687 = 82.7%, unchanged, consistent with the 2026-09-01
session's own finding that this county's C ceiling is a canon-level structural
block, not a further-fixable data gap. This 2-row fix only corrects
bookkeeping for D (matched_any) by moving 2 rows out of the "unknown" NULL
bucket into their correct clerk-confirmed-cancellation bucket.
"""
import os
import json
import urllib.request

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}


def patch(table, id_, fields):
    url = f'{REST}/{table}?id=eq.{id_}'
    data = json.dumps(fields).encode()
    req = urllib.request.Request(url, data=data, headers=H, method='PATCH')
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())
        if len(body) != 1:
            raise RuntimeError(f'PATCH {id_} matched {len(body)} rows, expected 1')
        return body[0]


# ---- 2 rows -> CLERK_SSOT_CANCELLED (genuine tier1-confirmed cancellations) ----
CANCELLED = [
    'b9368d4d-dd17-4ca3-9d5d-acbbf4f1f511',  # 2025-018900-CA-01, CANCELED_PER_ORDER
    '1359ae14-dd49-42df-8218-58fcb003148a',  # 2025-000133-CA-01, CANCELED_PER_BANKRUPTCY
]


def main():
    print('=== CLERK_SSOT_CANCELLED (2 rows, genuine tier1-confirmed cancellations) ===')
    for id_ in CANCELLED:
        r = patch('multi_county_auctions', id_, {
            'parity_status': 'CLERK_SSOT_CANCELLED',
            'parity_source': 'tier1:gsd_miamidade_20260902_c_triage:realtaxdeed_tier1_cancelled_status',
        })
        print('OK', id_, r.get('case_number'), r.get('tier1_sale_status'))
    print('DONE')


if __name__ == '__main__':
    main()
