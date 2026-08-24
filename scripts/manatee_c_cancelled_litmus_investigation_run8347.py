#!/usr/bin/env python3
"""Manatee letter C investigation (dispatch run8347, 2026-08-24).

RESULT: NO FIX APPLIED. This is a diagnose-and-document run, same pattern as
scripts/gold_standard_shard1_6a9e3c3a_stlucie_c_parity_fix.py -- concludes the
current C=93.4% gap is a genuinely correct data state (11 legitimately
cancelled auctions), not a matcher bug or fixable divergence, so per Honesty
Protocol / SHIP GATE this script performs ZERO writes.

============================================================================
BACKGROUND
============================================================================
pencil_dod_evaluate_county() (live def: supabase/migrations/
20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql) computes,
for manatee, over the 166 in-scope multi_county_auctions rows (data_source
<> 'propertyonion' OR tier1_authoritative = true -- PropertyOnion rows never
enter this denominator at all; it is not "litmus" for C/D, it is excluded
unless independently tier1-confirmed):

  matched_clean := count(*) FILTER (
      (parity_status='matched_clean' AND parity_source LIKE 'tier1%')
      OR parity_status IN ('PARITY_OK','CLERK_VERIFIED'))
  matched_any   := matched_clean's rows OR (matched_divergent tier1%)
                    OR parity_status='CLERK_SSOT_CANCELLED'

Live breakdown of all 166 manatee in-scope rows (VERIFIED via PostgREST,
2026-08-24):
  matched_clean (tier1% / PARITY_OK)      155  (93.4%)
  CLERK_SSOT_CANCELLED                     11  (parity_source=
                                                 manatee_clerk_foreclosure)
  ---------------------------------------------
  matched_any = 155 + 11 = 166 -> D = 100.0% (already passing)

Threshold for C: 166 * 0.95 = 157.7 -> need matched_clean >= 158.
Current matched_clean = 155. Gap = 3 rows minimum, and the ONLY pool of rows
that could move is exactly the 11 CLERK_SSOT_CANCELLED rows above -- there
are zero other non-clean, non-cancelled rows in scope (matched_any=166=
auctions_total, i.e. every row already resolves to clean-or-cancelled).

============================================================================
THE 11 ROWS
============================================================================
case_number             auction_date  db auction_status
2024CA001675AX           2026-08-18   CANCELLED
2025CA002974AX           2026-08-19   CANCELLED
2018CA003716AX           2026-08-19   upcoming (stale auction_status field;
                                       parity correctly says cancelled -- see
                                       live re-check below. Cosmetic only,
                                       does not feed C/D.)
2025CA002617AX           2026-08-26   CANCELLED
2026CC000389AX           2026-09-01   CANCELLED
2025CA002646AX           2026-09-02   CANCELLED
2025CA001955AX           2026-09-02   CANCELLED
2026CA000403AX           2026-09-02   CANCELLED
2025CA002328AX           2026-09-08   CANCELLED
412025CC000720CCAXMA     2026-09-22   CANCELLED (long-form wrapper of the
                                       clerk's own 2025CC000720AX)
412024CA000409CAAXMA     2026-10-28   CANCELLED (long-form wrapper of the
                                       clerk's own 2024CA000409AX)

============================================================================
ROOT-CAUSE FINDING (why this is NOT fixable by reclassification)
============================================================================
Ran scripts/clerk_ssot/parsers/manatee.py::parse_foreclosure() live against
records.manateeclerk.com/CourtRecords/Search/ForeclosureSales -- the
Manatee Clerk's own official public-records hub, i.e. the pre-authorized
primary/authoritative source for this county (NOT RealForeclose itself,
NOT PropertyOnion -- PropertyOnion is litmus-only per this task's mandate
and is never treated as authoritative here) -- during this session, live,
2026-08-24:

  parsed 91 rows from the clerk's current foreclosure-sales listing.

Cross-matched all 11 DB rows currently marked CLERK_SSOT_CANCELLED against
this fresh live pull by case_number (the 2 long-form manatee wrapper case
numbers -- "41" + YYYY + TYPE + NNNNNN + repeated TYPE + "AXMA"/"AXMB" --
were mapped to their short-form clerk-native core per the documented pattern
in scripts/manatee_ei_dedup_merge_7ad7b689.py before matching):

  - 11/11 found in the live clerk feed, same case number, same sale_date
  - 11/11 show raw_comment "CANCELLED ONLINE" -- the clerk's own live status
    token -- RIGHT NOW, independently of our DB and independently of
    PropertyOnion
  - 0 mismatches (no row where the live clerk record has flipped back to
    PENDING ONLINE or SOLD ONLINE)

So the clerk source of truth -- the SAME authoritative fallback source this
pipeline is instructed to check per the task, distinct from and never
PropertyOnion -- independently reconfirms, today, that all 11 rows are
genuinely cancelled foreclosure auctions. This is not a PropertyOnion
coverage gap, not a stale DB snapshot, and not a matcher bug; it is a
verified-correct divergence between "matched something" (D, correctly 100%)
and "matched with zero field divergence" (C).

Per the same migration's own documented rationale
(20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql, lines
18-27): CLERK_SSOT_CANCELLED is intentionally counted as matched_any (D) but
NOT matched_clean (C), because "it represents a divergence that clerk_ssot
found and corrected" -- the exact same class as matched_divergent.
Recognizing it as matched_clean would misrepresent a cancelled auction as a
clean parity match, which is precisely the class of anomaly the ULTRALOOP
adversarial-verify stage exists to reject. This is the identical fact
pattern already adjudicated for st_lucie in
scripts/gold_standard_shard1_6a9e3c3a_stlucie_c_parity_fix.py.

============================================================================
WHY 3+ MORE CLEAN ROWS CANNOT BE MANUFACTURED HONESTLY
============================================================================
The only lever that could move C is reclassifying some subset of these 11
CLERK_SSOT_CANCELLED rows to matched_clean. Doing so would require either:
  (a) the clerk's live record flipping back to an active sale status (false
      for all 11, re-verified live this session), or
  (b) weakening the evaluator's CLERK_SSOT_CANCELLED exclusion rule, which
      would silently inflate C for every other clerk_ssot county
      (brevard, gadsden, highlands, okeechobee, st_johns, suwannee, union,
      wakulla, lake, manatee, st_lucie, ...) using the exact same fabricated
      logic the st_lucie investigation already rejected.
Neither is available without either fabricating data or reintroducing the
ghost-success failure mode this metric exists to catch. No write action is
taken.

============================================================================
COSMETIC NOTE (not scored, not fixed here -- flagged for a future session)
============================================================================
2018CA003716AX has db auction_status='upcoming' while parity_status is
correctly CLERK_SSOT_CANCELLED (confirmed cancelled live). auction_status is
not read by pencil_dod_evaluate_county's C/D FILTER clauses (it uses
parity_status only), so this has zero effect on the metric. Left untouched
per Karpathy K3 (surgical changes) -- fixing an unrelated cosmetic field
was not requested by this task and is not in scope.

dispatch_id: run8347 (manatee letter C investigation)
"""

import os
import sys

import httpx

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_KEY', '')
BASE = f'{SUPABASE_URL}/rest/v1'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

TARGET_CASES = [
    '2024CA001675AX', '2025CA002974AX', '2018CA003716AX', '2025CA002617AX',
    '2026CC000389AX', '2025CA002646AX', '2025CA001955AX', '2026CA000403AX',
    '2025CA002328AX', '412025CC000720CCAXMA', '412024CA000409CAAXMA',
]


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'clerk_ssot'))
    from parsers import manatee  # noqa: E402

    with httpx.Client(timeout=60) as client:
        # 1. pull the 11 target rows live from the DB
        r = client.get(f'{BASE}/multi_county_auctions', headers=HEADERS, params={
            'select': 'case_number,auction_date,auction_status,parity_status,parity_source',
            'case_number': f'in.({",".join(TARGET_CASES)})',
        })
        db_rows = {row['case_number']: row for row in r.json()}
        print(f'DB rows found: {len(db_rows)}/{len(TARGET_CASES)}')

        # 2. live clerk pull (the authoritative primary source for manatee,
        #    NEVER PropertyOnion)
        clerk_rows = {row['case_number']: row for row in manatee.parse_foreclosure()}
        print(f'Live manatee clerk foreclosure rows parsed: {len(clerk_rows)}')

        # 3. map long-form wrappers to their short-form clerk-native core
        import re
        long_re = re.compile(r'^41(\d{4})(CA|CC)(\d{6})(CA|CC)AX')

        def short_form(case_number: str) -> str:
            m = long_re.match(case_number)
            if not m:
                return case_number
            return f'{m.group(1)}{m.group(2)}{m.group(3)}AX'

        confirmed = 0
        for case in TARGET_CASES:
            clerk_key = short_form(case)
            clerk_row = clerk_rows.get(clerk_key)
            db_row = db_rows.get(case)
            if clerk_row and clerk_row['cancelled']:
                confirmed += 1
                print(f'  {case} (clerk key {clerk_key}): CONFIRMED live CANCELLED '
                      f'ONLINE, sale_date={clerk_row["sale_date"]} '
                      f'(db auction_date={db_row.get("auction_date") if db_row else None})')
            else:
                print(f'  {case} (clerk key {clerk_key}): NOT reconfirmed live '
                      f'(clerk_row={clerk_row}) -- would need manual follow-up')

        print(f'\nConfirmed genuinely cancelled: {confirmed}/{len(TARGET_CASES)}')
        print('No PATCH issued. All 11 rows are correctly classified '
              'CLERK_SSOT_CANCELLED (matched_any, not matched_clean).')

        # 4. print live eval for the record
        import json
        ev = client.post(f'{BASE}/rpc/pencil_dod_evaluate_county', headers=HEADERS,
                          content=json.dumps({'p_county': 'manatee'})).json()
        print('\n=== pencil_dod_evaluate_county(manatee) — unchanged (no writes) ===')
        print(json.dumps(ev, indent=2))


if __name__ == '__main__':
    main()
