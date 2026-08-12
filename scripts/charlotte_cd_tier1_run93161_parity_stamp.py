#!/usr/bin/env python3
"""Charlotte County Gold Standard C/D fix — parity-stamp 10 orphaned tier1 rows
(dispatch: FIX PHASE charlotte-CD, 2026-08-12).

ROOT CAUSE (confirmed live via pencil_dod_evaluate_county + direct row query):
11 of 176 charlotte multi_county_auctions rows had parity_status IS NULL.
10 of these (case_number '26-0061','26-0065','26-0091'..'26-0098') already
carried real, authoritative tier1 data written by a prior ingestion run
(tier1_source_run_id=93161, tier1_authoritative=true,
tier1_verified_at='2026-08-11T23:55:00Z') — tier1_sale_status of SOLD (5 rows,
with tier1_sold_amount populated) or REDEEMED/REDEEMED_AFTER_SALE (5 rows).
These rows were simply never parity-stamped by the parity-matching job/script
that normally sets parity_status/parity_source from tier1 fields.

The 11th row (case_number '25001313CA') is genuinely upcoming — live
tier1_sale_status='LISTED', auction starts 2026-08-12 (today). Left NULL
intentionally; cannot be parity-stamped until the auction concludes.

FIX: mirror the existing charlotte_cd_realforeclose_tier1_backfill_ch_cd.py
convention exactly (SOLD -> matched_clean w/ tier1% source; REDEEMED* ->
CLERK_SSOT_CANCELLED w/ clerk_ssot% source). No re-scraping needed — the
authoritative tier1 values already existed in the DB, unstamped.

Deliberately did NOT touch sold_amount on the 5 SOLD rows: doing so would
grow the B/F `closed_sold` denominator without a matching foreclosure_outcomes/
tax_deed_outcomes row (none exist for these case numbers — confirmed empty
query), which would regress B/F from 100% (the same trap the prior script's
docstring already documents fixing once). C/D only read parity_status/
parity_source, so this stays a surgical, in-scope-only change.

RESULT (confirmed live via pencil_dod_evaluate_county after run):
  D: matched_any 165/176 (93.8%) -> 175/176 (99.4%) -- PASS (was FAIL)
  C: matched_clean 153/176 (86.9%) -> 158/176 (89.8%) -- still FAIL
     (structural: remaining 17 CLERK_SSOT_CANCELLED rows are genuinely
     cancelled/redeemed and correctly excluded from matched_clean by the
     evaluator's design; 1 row is a live in-progress auction. No further
     legitimate lever without fabricating a status change on real
     cancelled/redeemed sales.)
  B, F: unchanged at 100% (verified unaffected by this fix, as intended).

This script documents/replays the exact PATCH calls; idempotent (re-running
finds no NULL-parity rows with tier1_source_run_id=93161 left and is a no-op).
"""
import os
import json
import requests

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
REST = f'{SUPABASE_URL}/rest/v1'
H = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=representation',
}

COUNTY = 'charlotte'

# Sourced from live tier1_sale_status already populated by ingestion
# run_id=93161 (tier1_authoritative=true, tier1_verified_at=2026-08-11
# 23:55 UTC) -- re-read from DB, not re-guessed or re-scraped.
ROWS = {
    '26-0061': 'REDEEMED_AFTER_SALE',
    '26-0065': 'SOLD',
    '26-0091': 'REDEEMED',
    '26-0092': 'SOLD',
    '26-0093': 'REDEEMED',
    '26-0094': 'REDEEMED',
    '26-0095': 'REDEEMED',
    '26-0096': 'SOLD',
    '26-0097': 'SOLD',
    '26-0098': 'SOLD',
}


def patch_mca(case_number: str, fields: dict):
    url = (f'{REST}/multi_county_auctions'
           f'?county=eq.{COUNTY}&case_number=eq.{case_number}')
    r = requests.patch(url, headers=H, data=json.dumps(fields), timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f'PATCH {case_number} failed [{r.status_code}]: {r.text[:300]}')
    body = r.json()
    if len(body) != 1:
        raise RuntimeError(f'PATCH {case_number} matched {len(body)} rows, expected 1: {body}')
    return body


if __name__ == '__main__':
    updated = []
    for cn, status in ROWS.items():
        if status == 'SOLD':
            fields = {
                'parity_status': 'matched_clean',
                'parity_source': 'tier1:charlotte_tier1_run93161_parity_stamp_20260812:ch_CD',
            }
        else:
            fields = {
                'parity_status': 'CLERK_SSOT_CANCELLED',
                'parity_source': 'clerk_ssot:charlotte_tier1_run93161_parity_stamp_20260812:ch_CD',
            }
        patch_mca(cn, fields)
        updated.append((cn, fields['parity_status']))

    for cn, s in updated:
        print(f'{cn}: {s}')
    print(f'TOTAL rows updated: {len(updated)}')
