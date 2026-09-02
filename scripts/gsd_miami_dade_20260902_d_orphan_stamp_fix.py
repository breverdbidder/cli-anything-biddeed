#!/usr/bin/env python3
"""Miami-Dade Gold Standard D fix -- session 2026-09-02.

See supabase/migrations/20260902_shard3_miami_dade_d_orphan_stamp_fix.sql for
the full root-cause analysis and before/after evidence. This is the 5th
recurrence of the recurring orphan-stamp gap for this county (previously
partially fixed 2026-07-04, 2026-07-05, 2026-08-25, and 2026-09-01) -- new
tier1_authoritative rows keep landing faster than the parity-reconciliation
step processes them.

Live scope this session: 38 rows with parity_status IS NULL AND
tier1_authoritative=true (35 additional rows with tier1_authoritative=false
are fresh-scrape pipeline lag from 2026-09-02T07:55:38Z and are deliberately
NOT touched -- correctly NULL pending their own first tier1 pass).

Classification of the 38 (classify-don't-guess, same pattern as 20260901
gold_standard_shard3_miami_dade_20260901_cd_fix.py):
  3  -> CLERK_SSOT_CANCELLED (genuine tier1-confirmed cancellations:
        CANCELED_PER_BANKRUPTCY x2, CANCELED_PER_ORDER x1)
  23 -> LEFT NULL. All 23 are tier1_sale_status='SOLD' with tier1_sold_amount
        populated but sold_amount NULL. Checked every one against sibling rows
        sharing the same case_number: 22 of 23 are tax_deed-track duplicate
        rows whose case's real, backed sale already lives on a separate
        foreclosure-track row that is already parity_status='matched_clean'
        with a real sold_amount (e.g. case 2025-018996-CA-01: foreclosure-
        track row 0d2328b9 is matched_clean/sold_amount=701100.0; this tax_deed
        -track row ac859d1d has no outcome-table backing of its own). Stamping
        these would double-count an already-matched sale -- the exact
        "ghost-success" shape independently found and reverted 3x previously
        for this county (see 20260901 migration file). The 1 remaining SOLD
        row (case 2025-009306-CA-01, id 91e82064) has no sibling row and no
        matching foreclosure_outcomes/tax_deed_outcomes row at all -- checked
        live, both queries returned zero rows -- so it is also left NULL as a
        genuinely unbacked claim.
  10 -> LEFT NULL (tier1_sale_status='LISTED', auction not yet resolved).
  1  -> LEFT NULL (JUDGMENT_VACATED/DISMISSED, ambiguous disposition, not
        researched further this session).
  1  -> LEFT NULL (PROOF_OF_PUBLICATION_NOT_RECEIVED_OR_INCORRECT, not final).

Each PATCH is id-scoped and idempotent -- a re-run just re-applies the same
target state. No row's sold_amount was set to a fabricated value. No
PropertyOnion field used as an authoritative source. Cron jobs 109/111/115
not touched. pencil_dod_evaluate_county / gold_standard_loop /
gold_standard_certify not modified or invoked mid-session (verification-only
RPC calls before/after).
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


# ---- 3 rows -> CLERK_SSOT_CANCELLED (genuine tier1-confirmed cancellations) ----
CANCELLED = [
    'b9368d4d-dd17-4ca3-9d5d-acbbf4f1f511',  # 2025-018900-CA-01, CANCELED_PER_ORDER
    '1359ae14-dd49-42df-8218-58fcb003148a',  # 2025-000133-CA-01, CANCELED_PER_BANKRUPTCY
    '1d6fbd29-28f9-4097-bfb2-e4d190d17f06',  # 2018-011148-CA-01, CANCELED_PER_BANKRUPTCY
]


def main():
    print('=== CLERK_SSOT_CANCELLED (3 rows, genuine cancellations) ===')
    for id_ in CANCELLED:
        r = patch('multi_county_auctions', id_, {
            'parity_status': 'CLERK_SSOT_CANCELLED',
            'parity_source': 'tier1:gsd_miamidade_20260902_d:realauction_tier1_cancelled_status',
        })
        print('OK', id_, r.get('case_number'))
    print('DONE')


if __name__ == '__main__':
    main()
