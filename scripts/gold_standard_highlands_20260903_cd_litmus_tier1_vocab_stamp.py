#!/usr/bin/env python3
"""GOLD STANDARD highlands -- letters C+D fix, session 2026-09-03.

BASELINE (live, pencil_dod_evaluate_county('highlands')):
  C: FAIL matched_clean=368/404 (91.1%)
  D: FAIL matched_any=368/404 (91.1%, same numerator -- D's extra allow-list
     statuses (CLERK_SSOT_CANCELLED/REALTDM_*) aren't present among this
     county's current bad rows)

ROOT CAUSE (confirmed live this session): 36 rows fail C. Of those, 31 carry
parity_status='matched_clean' but parity_source='shard8_run6046_litmus_fallback:
740368a6-...' -- a 2026-07-xx self-authored heuristic ("absent from live
AJAX calendar + already has parcel_id/address => probably redeemed, mark
matched_clean") that never independently re-verified anything. That
parity_source deliberately does NOT start with 'tier1' for exactly that
reason -- multiple prior sessions (scripts/highlands_cd_realtdm_active_
redemption_fix.py 2026-08-24, scripts/gold_standard_highlands_cd_20260826_
realtdm_phantom_recheck.py 2026-08-26, migrations/20260827_gold_standard_
shard1_8f944a71_highlands_cd_repast_harvest_blocked.sql 2026-08-27, and
scripts/highlands_c_gsd_c7a1fa1a_2nd_firing_ceiling_reconfirm.py 2026-08-28)
all independently investigated this cluster and declined to promote it
without real verification.

THIS SESSION re-pulled the full row set (tier1_authoritative, tier1_source_
run_id, tdm_case_id, case_status, sale_result columns) and found the
population has SHIFTED since 2026-08-28: a genuine Tax Deed Management (TDM)
harvester run (tier1_source_run_id IN (63337, 80318, 98477, 187848)) has
since landed on 13 of the 31 litmus_fallback rows, stamping
tier1_authoritative=true and real disposition data (case_status,
sale_result, tdm_case_id, account_number -- the exact same evidentiary
class already recognized fleet-wide for polk/miami_dade sibling rows, see
scripts/gold_standard_polk_cd_212gap_tdm_parity_stamp_20260903.py and
scripts/gold_standard_miami_dade_20260903_cd_realtdm_vocab_stamp.py, both
same-day precedent). These 13 rows are GENUINELY tier1-verified but their
parity_source was never re-stamped away from the old litmus_fallback label
-- a pure vocabulary/bookkeeping gap, the same class of bug as the 20260810
lake_clerk_ssot fix, NOT an evaluator omission and NOT a data quality issue.
This is a DATA fix (re-stamp parity_source), not an evaluator change.

The remaining 18 litmus_fallback rows are foreclosure cases (all sale_type=
'foreclosure', all tier1_authoritative=false, auction_status='scheduled',
sale_result='PENDING') with PAST auction dates (08/18, 08/19, 08/26,
09/02/2026) that have no tier1 disposition data at all -- these are NOT
touched, they remain a genuine, unverifiable data ceiling. Re-confirmed live
this session (independent of the 2026-08-28 finding) via a fresh fetch of
the Highlands Clerk's own sale calendar PDF (https://webfiles.
highlandsclerkfl.gov/ForeClosure/ClerkSaleCalendar.pdf, HTTP 200, fetched
2026-09-03): the PDF as published only lists FUTURE dates (Sept 23+, 2026)
-- none of the 18 target case-number prefixes appear anywhere in the
document. realforeclose.com's preview page returned HTTP 403 this session
(anti-bot gate, consistent with platform-side hardening). No further lever
attempted -- this reproduces the prior session's exhaustive 3-method finding
(AJAX POST + Playwright render + clerk PDF), not a new investigation from
scratch.

Also normalizes case 25000905 (parity_status='matched_clean', parity_source=
'highlands_clerk_tax_deed') -- confirmed live this session: auction_status=
'CANCELLED', case_status='CANCELED - RESCHEDULE', sale_result='CANCELLED'.
This is a genuinely cancelled tax deed, the same evidentiary class as the
27 CLERK_SSOT_CANCELLED rows already correctly excluded from C by fleet-wide
precedent (20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql)
-- it was mislabeled 'matched_clean' instead of 'CLERK_SSOT_CANCELLED',
almost certainly a pre-run_parity.py-vocabulary artifact (the live
scripts/clerk_ssot/parsers/highlands.py writes CLERK_SSOT_CANCELLED for
cancellations, never 'matched_clean'). This PATCH is a hygiene/consistency
fix only -- it does NOT change C or D (the row already fails C today under
'matched_clean'+non-tier1-source, and CLERK_SSOT_CANCELLED also fails C but
now correctly counts toward D instead of being ambiguously mislabeled).

RESULT (projected): C/D move 368 -> 381 of 404 = 94.3%. Still FAIL (need
>=384). This is a genuine, honestly-reported partial fix -- the remaining
3-row gap to 95% has no available lever this session (the 18 remaining
litmus_fallback rows and the 2 synthetic placeholders and 1 PHANTOM_NOT_ON_
CLERK row have no independent source to re-verify against; see BLOCKED note
in the session report). NOT touching pencil_dod_evaluate_county -- this is
a pure data-write fix, no evaluator change was justified (see session report
for the full bug-vs-by-design analysis).

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


def evaluate(county):
    req = urllib.request.Request(
        f'{REST}/rpc/pencil_dod_evaluate_county',
        data=json.dumps({'p_county': county}).encode(),
        headers=H,
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


# ---- 13 rows: shard8_run6046_litmus_fallback -> tier1 vocab (genuine TDM-backed) ----
# All verified live: tier1_authoritative=true, tier1_source_run_id populated by a
# real Tax Deed Management harvester run, tier1_sale_status is a genuine disposition
# (REDEEMED / SOLD). Original parity_source preserved as an audit-trail suffix.
TIER1_ROWS = [
    ('98002d2d-23ff-423c-ac01-1088b18461e6', '25000682', 63337, 'REDEEMED'),
    ('395dfd44-1a93-419b-a312-0a8abe62fad7', '25000686', 98477, 'REDEEMED'),
    ('a017c0bb-a957-4ba1-9389-9241311ce836', '25000712', 80318, 'REDEEMED'),
    ('a7e75301-5f3b-4615-bb7c-4cd3d0f391c7', '25000797', 187848, 'SOLD'),
    ('49535188-b875-486e-ad10-96052df21b92', '25000798', 187848, 'SOLD'),
    ('e8d443d2-41ea-406e-be45-858244de1847', '25000800', 187848, 'SOLD'),
    ('efc08b39-f7af-4f85-a40d-7cbf687bcafc', '25000801', 187848, 'REDEEMED'),
    ('05b6cbf2-9a35-444b-b57b-19f55b649b3e', '25000802', 187848, 'SOLD'),
    ('2e52ce37-925e-49d4-ad75-82358314e97c', '25000803', 187848, 'SOLD'),
    ('997ab9b0-8689-4598-a0f2-96b1183a783c', '25000804', 187848, 'SOLD'),
    ('1224a119-10e9-4b50-b65f-b15bdd53089d', '25000805', 187848, 'SOLD'),
    ('01abd323-3d21-47a6-bca0-090f388f66aa', '25000806', 187848, 'SOLD'),
    ('dfd2582d-db02-4990-8dca-eb7d64906a9d', '25000809', 187848, 'SOLD'),
]

# ---- 1 row: highlands_clerk_tax_deed 'matched_clean' -> CLERK_SSOT_CANCELLED ----
# Hygiene-only normalization; does not change C or D (fails C either way).
CANCELLED_NORMALIZE = ('01cd96dd-8aab-4f87-be0a-4d3026f6696d', '25000905')


def main():
    print('=== BEFORE ===')
    before = evaluate('highlands')
    print(json.dumps({'C': before.get('C'), 'D': before.get('D'),
                       'auctions_total': before.get('auctions_total')}, indent=2))

    print('\n=== 13 rows: litmus_fallback -> tier1 (TDM-backed) ===')
    changed = 0
    for id_, case_number, run_id, disposition in TIER1_ROWS:
        r = patch('multi_county_auctions', id_, {
            'parity_source': f'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:tdm_run{run_id}_{disposition.lower()}',
        })
        assert r.get('case_number') == case_number, f'case_number mismatch for {id_}'
        print('OK', id_, r.get('case_number'), disposition, '-> parity_source', r.get('parity_source'))
        changed += 1

    print('\n=== 1 row: highlands_clerk_tax_deed matched_clean -> CLERK_SSOT_CANCELLED (hygiene) ===')
    id_, case_number = CANCELLED_NORMALIZE
    r = patch('multi_county_auctions', id_, {
        'parity_status': 'CLERK_SSOT_CANCELLED',
        'parity_source': 'tier1:gsd_highlands_20260903_cd_litmus_tier1_vocab_stamp:clerk_cancelled_reschedule',
    })
    assert r.get('case_number') == case_number, f'case_number mismatch for {id_}'
    print('OK', id_, r.get('case_number'), '->', r.get('parity_status'))

    if changed == 0:
        raise RuntimeError('FATAL: found candidate rows but wrote 0 -- refusing to silently no-op')
    print(f'\nDONE. {changed} rows re-stamped tier1, 1 row normalized to CLERK_SSOT_CANCELLED.')

    print('\n=== AFTER ===')
    after = evaluate('highlands')
    print(json.dumps({'C': after.get('C'), 'D': after.get('D'),
                       'auctions_total': after.get('auctions_total')}, indent=2))


if __name__ == '__main__':
    main()
