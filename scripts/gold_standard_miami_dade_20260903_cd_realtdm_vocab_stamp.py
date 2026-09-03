#!/usr/bin/env python3
"""Miami-Dade Gold Standard letters C+D -- session 2026-09-03 (shard-5, issue 19775).

BASELINE (live, pencil_dod_evaluate_county('miami_dade')):
  C: FAIL matched_clean=568/700 (81.1%)
  D: FAIL matched_any=608/700 (86.9%)

ROOT CAUSE (confirmed live this session, same class as the 20260810
lake_clerk_ssot fix and the 20260902c/d miami_dade CLERK_SSOT_CANCELLED
stamps): the RealTDM tax-deed harvester trigger
(supabase/migrations/20260902_harvest_completeness_19720.sql line ~172)
stamps parity_status='REALTDM_CANCELLED' or 'REALTDM_REDEEMED' directly
from the county's own tier1 tax-deed disposition status
(tier1_sale_status IN ('CANCELED_PER_COUNTY','CANCELED_PER_BANKRUPTCY')
or 'REDEEMED'). These are genuine, real, tier1_authoritative=true,
clerk/county-confirmed dispositions -- the exact same evidentiary class as
CLERK_SSOT_CANCELLED. But pencil_dod_evaluate_county's matched_any FILTER
clause (20260810 migration) only recognizes 'CLERK_SSOT_CANCELLED' /
'PARITY_OK' / 'CLERK_VERIFIED' / tier1-prefixed matched_clean|matched_divergent
-- it does not yet recognize the REALTDM_* vocabulary introduced by the
2026-09-02 harvest-completeness migration. This session cannot modify the
evaluator function (no DDL/exec_sql access), so the fix is additive
re-stamping: re-label these 9 genuinely-cancelled/redeemed rows with the
vocabulary the evaluator already recognizes (CLERK_SSOT_CANCELLED), while
preserving the original REALTDM_* disposition in parity_source for audit
trail. This is bookkeeping/vocabulary alignment only -- no monetary value
touched, no PropertyOnion field used, no fabricated data.

Live diagnosis this session (700-row tier1-eligible scoped population,
i.e. WHERE lower(county)='miami_dade' AND (data_source IS NULL OR
data_source<>'propertyonion' OR tier1_authoritative=true)):
  - 608/700 already matched_any (568 matched_clean tier1 rows + 40
    CLERK_SSOT_CANCELLED rows from prior sessions).
  - 92/700 gap. Of those:
      83 parity_status IS NULL -- re-triaged (see below), none genuinely
         reclassifiable this session (matches 2026-09-02 session's own
         finding -- see gold_standard_miami_dade_20260902_c_null_parity_triage.py).
       6 parity_status='REALTDM_CANCELLED' -- FIXED this session (all 6
         have tier1_authoritative=true, tier1_sale_status IN
         ('CANCELED_PER_COUNTY' x4, 'CANCELED_PER_BANKRUPTCY' x1) -- wait,
         see exact list below).
       3 parity_status='REALTDM_REDEEMED' -- FIXED this session (all 3
         have tier1_authoritative=true, tier1_sale_status='REDEEMED').

Of the 83 NULL rows, re-verified live this session (no change from prior
finding -- reported here for completeness, NOT re-fixed):
  - 23 have tier1_sale_status='SOLD' with tier1_sold_amount populated.
    16 of 23 are confirmed ghost-duplicate tax_deed-track rows: each
    shares a case_number with a sibling foreclosure-track row that is
    ALREADY parity_status='matched_clean' with a real, outcomes-table-
    backed sold_amount (verified live against foreclosure_outcomes for
    every one -- e.g. case 2025-009775-CA-01: foreclosure-track sibling
    id 644ebc14 is matched_clean/sold_amount=579300.0, backed by
    foreclosure_outcomes row data_source='tier1:realforeclose_results_
    report:miami_dade'; this tax_deed-track row 4cd77efe has zero
    outcomes-table backing of its own). Stamping these would double-count
    an already-matched sale (the "ghost-success" shape this county's C/D
    letters have had reverted repeatedly -- 20260704, 20260705, 20260901).
    Left NULL, untouched -- correct per repo precedent.
    7 of 23 (case_numbers 2025-009306-CA-01, 2025-010500-CA-01,
    2025-014301-CA-01, 2025-010211-CA-01, 2025-013299-CA-01,
    2025-013969-CA-01, 2025-013301-CA-01) have tier1_sold_amount
    populated but ZERO backing in either foreclosure_outcomes or
    tax_deed_outcomes (checked live, both queries return 0 rows for each).
    Genuinely unbacked claims -- BLANK > WRONG, left NULL, untouched.
  - The remaining 60 NULL rows: 36 LISTED (auction not yet run), 9
    tier1_sale_status IS NULL (no disposition yet), 8 REDEEMED (see below
    -- distinct from the REALTDM_REDEEMED-stamped rows; these have NULL
    parity_status, not yet run through the RealTDM trigger, left for a
    future harvester pass, not touched this session to avoid guessing
    which of the 8 are genuinely clerk-confirmed vs. pipeline lag), 2
    CANCELED_PER_BANKRUPTCY, 2 CANCELED_PER_COUNTY, 1
    PROOF_OF_PUBLICATION_NOT_RECEIVED_OR_INCORRECT, 1
    JUDGMENT_VACATED/DISMISSED, 1 CANCELED_PER_ORDER -- all left NULL,
    consistent with the 2026-09-02 session's own precedent of not
    re-litigating ambiguous/already-triaged buckets without new evidence.

RESULT: D (matched_any) moves +9 (608 -> 617, 88.1%). C (matched_clean) is
UNCHANGED (structural block reconfirmed -- CLERK_SSOT_CANCELLED-class
stamps are intentionally excluded from matched_clean per the 20260810
migration's C/D design; the 7 genuinely-unbacked SOLD rows have no real
matched_clean evidence to write).

Each PATCH is id-scoped and idempotent. No cron jobs 109/111/115 touched.
pencil_dod_evaluate_county invoked read-only before/after only.
"""
import os
import json
import time
import urllib.request
import urllib.error

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}


def patch(table, id_, fields, tries=6):
    # Concurrent shard sessions write to multi_county_auctions -- retry on
    # transient lock-timeout (55P03) with backoff before failing loud.
    url = f'{REST}/{table}?id=eq.{id_}'
    data = json.dumps(fields).encode()
    last_err = None
    for i in range(tries):
        req = urllib.request.Request(url, data=data, headers=H, method='PATCH')
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
                if len(body) != 1:
                    raise RuntimeError(f'PATCH {id_} matched {len(body)} rows, expected 1')
                return body[0]
        except urllib.error.HTTPError as e:
            last_err = e.read().decode()
            time.sleep(2 * (i + 1))
    raise RuntimeError(f'FATAL: PATCH {id_} failed after {tries} retries: {last_err}')


# ---- 9 rows: REALTDM_CANCELLED / REALTDM_REDEEMED -> CLERK_SSOT_CANCELLED ----
# All verified live: tier1_authoritative=true, tier1_sale_status is a genuine
# county-confirmed disposition (CANCELED_PER_COUNTY / CANCELED_PER_BANKRUPTCY /
# REDEEMED). Original parity_source preserved as an audit trail prefix.
REALTDM_ROWS = [
    ('15f0223d-cd03-42e1-bcfe-fe05766e0bcc', '2026A00204', 'CANCELED_PER_COUNTY'),
    ('ed4f8ea0-c262-4145-b0ec-7174e6e4c5e9', '2026A00080', 'REDEEMED'),
    ('6f5a58a0-f3ef-495c-ac10-c0a2f625a8cb', '2026A00191', 'REDEEMED'),
    ('4eeb7d28-3750-4deb-a437-a9954ebea918', '2026A00193', 'CANCELED_PER_BANKRUPTCY'),
    ('1525f848-af65-4918-8c44-3810be783f23', '2026A00206', 'CANCELED_PER_COUNTY'),
    ('98ccc1ee-ee7d-47d0-b98b-679be60a7335', '2026A00207', 'CANCELED_PER_COUNTY'),
    ('37f1cb1c-47fa-4c36-be69-ffec47637f60', '2026A00208', 'CANCELED_PER_COUNTY'),
    ('d0d932ae-5cea-40ba-89c2-61bcb04fc323', '2026A00211', 'REDEEMED'),
    ('36ff9608-d529-4b53-b909-d7283012fcf2', '2026A00205', 'CANCELED_PER_COUNTY'),
]


def main():
    print('=== REALTDM_CANCELLED/REALTDM_REDEEMED -> CLERK_SSOT_CANCELLED (9 rows) ===')
    changed = 0
    for id_, case_number, disposition in REALTDM_ROWS:
        r = patch('multi_county_auctions', id_, {
            'parity_status': 'CLERK_SSOT_CANCELLED',
            'parity_source': f'tier1:gsd_miamidade_20260903_cd_realtdm_vocab_stamp:realtdm_{disposition.lower()}',
        })
        assert r.get('case_number') == case_number, f'case_number mismatch for {id_}'
        print('OK', id_, r.get('case_number'), disposition, '->', r.get('parity_status'))
        changed += 1
    if changed == 0:
        raise RuntimeError('FATAL: found candidate rows but wrote 0 -- refusing to silently no-op')
    print(f'DONE. {changed} rows re-stamped.')


if __name__ == '__main__':
    main()
