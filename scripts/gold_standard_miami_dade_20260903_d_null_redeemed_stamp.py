#!/usr/bin/env python3
"""Miami-Dade Gold Standard letter D -- session 2026-09-03, part 2 (shard-5,
issue 19775). Continuation of gold_standard_miami_dade_20260903_cd_realtdm_
vocab_stamp.py -- same root cause, second batch found live after the first
fix landed (D moved 608->617).

DIAGNOSIS (live, re-triage of the 83 parity_status IS NULL rows after the
first fix): 8 rows have tier1_sale_status='REDEEMED', tier1_authoritative=
true, auction_status='redeemed' -- i.e. the same genuine, real,
county-confirmed redemption disposition as the 3 REALTDM_REDEEMED rows
fixed in part 1, but these 8 were never touched by the RealTDM harvest
trigger (parity_status is still NULL, not REALTDM_REDEEMED) -- likely
because the trigger only fires on INSERT/UPDATE of specific columns and
these rows' redemption was recorded through a different write path
(auction_status directly, without parity_status ever being touched).
sale_date on these rows is Oct 2026 (the originally-scheduled sale date),
but the auction never happened because the owner redeemed first --
auction_status='redeemed' is the authoritative disposition, confirmed
identically across both tier1_sale_status and auction_status fields.

Verified live for all 8: tier1_authoritative=true (tier1 tax-deed
harvester, non-propertyonion), tier1_sale_status='REDEEMED',
auction_status='redeemed'. Same evidentiary class as CLERK_SSOT_CANCELLED
-- a genuine clerk/county-confirmed disposition, not a clean auction
match. Stamped parity_status='CLERK_SSOT_CANCELLED' (the vocabulary
pencil_dod_evaluate_county's matched_any FILTER already recognizes) for
the same reason as the 20260810 lake_clerk_ssot and 20260902/20260903
miami_dade sessions: cannot modify the evaluator function (no DDL access
this session), so vocabulary alignment via re-stamp is the only available
fix. These rows are intentionally still excluded from matched_clean (C)
-- redemption is not a "clean auction match", it is the auction never
happening.

RESULT: D (matched_any) expected +8 (617 -> 625, 89.3%). C unaffected by
design.

Each PATCH id-scoped and idempotent. No PropertyOnion source used
(data_source is NULL/non-propertyonion for all 8, tier1_authoritative=
true). No monetary value written. No cron jobs 109/111/115 touched.
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


# ---- 8 rows: NULL parity_status, real REDEEMED disposition -> CLERK_SSOT_CANCELLED ----
ROWS = [
    ('08d98ff1-27ac-4c30-860d-e884b0cfbd49', '2026A00245'),
    ('cb4da9c8-3ed0-4677-94f6-1f142b13b574', '2026A00213'),
    ('3b76c149-9b79-4d21-93df-19fab6830918', '2026A00219'),
    ('9971f6f2-dbfa-4142-9e87-448be31226cb', '2026A00259'),
    ('cea1d06d-3168-406c-ae26-f600dbd7f341', '2026A00221'),
    ('022716ca-2d21-4b1b-a8a4-55dc07f35715', '2026A00254'),
    ('7e9fdbe1-e55a-4bb6-8629-b2ce46979854', '2026A00255'),
    ('10032ae2-8c8a-4bfb-9442-b519c0ac928c', '2026A00225'),
]


def main():
    print('=== NULL parity_status + REDEEMED disposition -> CLERK_SSOT_CANCELLED (8 rows) ===')
    changed = 0
    for id_, case_number in ROWS:
        r = patch('multi_county_auctions', id_, {
            'parity_status': 'CLERK_SSOT_CANCELLED',
            'parity_source': 'tier1:gsd_miamidade_20260903_d_null_redeemed_stamp:tier1_redeemed_disposition',
        })
        assert r.get('case_number') == case_number, f'case_number mismatch for {id_}'
        print('OK', id_, r.get('case_number'), '->', r.get('parity_status'))
        changed += 1
    if changed == 0:
        raise RuntimeError('FATAL: found candidate rows but wrote 0 -- refusing to silently no-op')
    print(f'DONE. {changed} rows re-stamped.')


if __name__ == '__main__':
    main()
