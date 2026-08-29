#!/usr/bin/env python3
"""Charlotte C (parity_clean) systemic investigation, 2026-08-29.

TASK: Charlotte C was FAIL at 57.6% (175/304 matched_clean), threshold 95%
(289/304 needed). Directive was to prioritize finding a SYSTEMIC root cause
(matcher bug, sale_type split, uncovered scrape batch, or key-format mismatch)
given the 114-row scale of the gap, before assuming a structural PropertyOnion
coverage ceiling -- and to check for a shared file another agent (charlotte:D)
might already be investigating.

STEP 1 -- live parity_status/sale_type breakdown (VERIFIED via direct query,
multi_county_auctions county=eq.charlotte):
    matched_clean / foreclosure          : 144
    CLERK_SSOT_CANCELLED / foreclosure   : 112   <-- the entire C/D gap
    matched_clean / tax_deed             :  31
    NULL / tax_deed                      :  10
    NULL / foreclosure                   :   7
    TOTAL                                : 304

D (matched_any, includes CLERK_SSOT_CANCELLED) = 287/304 = 94.4% (near-pass).
C (matched_clean, excludes CLERK_SSOT_CANCELLED by design) = 175/304 = 57.6%.
Gap D-C = 112, and ALL 112 are parity_status='CLERK_SSOT_CANCELLED'.

STEP 2 -- shared-file check (per directive, avoid duplicating charlotte:D's
investigation): git log shows commit 4c71df8a "Charlotte D criterion:
investigation confirms genuine data ceiling, no writes" landed the SAME DAY
(2026-08-29) via scripts/charlotte_d_run20260829_no_lever_ceiling_confirmed.py.
That session found the 17 D-gap NULL rows are 16 future auctions (08-31/09-01,
not yet occurred) + 1 unresolved RESCHEDULED case, and confirmed PropertyOnion
has ZERO litmus rows overlapping Charlotte's current cycle. No overlap with
this C investigation's root cause (C's gap is CLERK_SSOT_CANCELLED rows, not
NULL rows) -- no duplicated work.

STEP 3 -- matcher code review: scripts/clerk_ssot/run_parity.py (the shared
daily clerk_ssot reconciliation script referenced in the task prompt as a
likely common code path) does NOT run for Charlotte at all -- charlotte is
listed in that file's NO_PUBLIC_CALENDAR comment block (no ArcGIS/clerk-owned
public calendar; RealForeclose-only, gated). Charlotte's CLERK_SSOT_CANCELLED
rows were instead stamped by a series of Charlotte-specific one-off scripts
(charlotte_cd_tier1_run93161_parity_stamp.py, charlotte_c_run106703_...,
charlotte_cd_realforeclose_tier1_backfill_ch_cd.py, and the shard3 dispatch
8da53925 / 03af1f8b migrations), each using live Playwright fetches of
charlotte.realforeclose.com's PREVIEW pages and Charlotte's own
tier1_sale_status ingestion pipeline (tier1_authoritative=true,
tier1_source_run_id 93161/106703/124512/130088/139776). So there is no shared
systemic matcher bug in play here -- Charlotte was never wired into the
matcher these other counties use.

STEP 4 -- evaluator (public.pencil_dod_evaluate_county) C/D FILTER clauses,
confirmed live from supabase/migrations/20260810_gold_standard_shard3_lake_
clerk_ssot_cd_recognition.sql (current canonical definition):
    matched_clean := (parity_status='matched_clean' AND parity_source LIKE
                       'tier1%') OR parity_status IN ('PARITY_OK','CLERK_VERIFIED')
    matched_any   := matched_clean's predicate OR parity_status IN
                      ('matched_clean','matched_divergent') w/ tier1_source
                      OR parity_status='CLERK_SSOT_CANCELLED'
This is BY DESIGN, documented explicitly in that migration's own comment:
"CLERK_SSOT_CANCELLED as matched_any (not clean -- it represents a divergence
... which is the same class as matched_divergent, not a no-divergence-ever
clean match)". A cancelled/redeemed sale is correctly excluded from "clean
match to a completed sale" by definition -- this is intentional evaluator
design, not a bug to fix.

STEP 5 -- internal-consistency adversarial check on the 112 CLERK_SSOT_CANCELLED
rows (VERIFIED via direct query today):
  - tier1_sale_status breakdown: REDEEMED=103, CANCELED_PER_COUNTY=6,
    REDEEMED_AFTER_SALE=1, CANCELED=1, LISTED=1 (110/112 unambiguously a
    non-sale outcome)
  - sold_amount IS NOT NULL on 0/112 rows (zero evidence of a mislabeled
    completed sale hiding in this bucket)
  - parity_source values: 49 from clerk_ssot_tier1_stamp_shard3_8da53925,
    42 from tier1:realforeclose_ssot:gold_standard_shard3_03af1f8b_..., plus
    smaller batches from 3 other Charlotte-specific live-verify sessions --
    every row traces to a session that pasted live RealForeclose text
    ("Auction Status: Redeemed" / "Status Canceled per County") as evidence,
    not a blind bulk UPDATE.
  - the single tier1_sale_status='LISTED' row (case 25000134CA) carries a
    parity_source note "canceled_per_bankruptcy" from its own dedicated
    live-recheck session (20260815) -- tier1_sale_status is simply stale on
    that one row (not resynced after the manual bankruptcy-cancellation
    finding), not a parity_status error.

STEP 6 -- prior-session precedent: this is (by commit count) at least the
4th-5th independent Charlotte C investigation to reach the identical
conclusion -- commits/migrations aa74b685, 6817a96c,
20260824_gold_standard_shard3_8da53925_charlotte_i_d_fix.sql, and
20260825_gold_standard_shard3_03af1f8b_lee_charlotte_washington_fixes.sql all
independently confirmed "matched_clean excludes CLERK_SSOT_CANCELLED by
design; no new lever found; spot-checked a sample against live tier1_sale_
status and confirmed none are a mislabeled clean sale."

STEP 7 -- arithmetic ceiling check (this session): even in the maximally
generous (and dishonest) hypothetical where every one of the 112
CLERK_SSOT_CANCELLED rows were force-reclassified matched_clean, the metric
would be (175+112)/304 = 287/304 = 94.4% -- STILL below the 95% threshold,
because 2 of the 7 NULL rows (future 08-31/09-01 auctions, per charlotte:D's
same-day finding) also can't count. C is therefore not merely "hard" but
ARITHMETICALLY IMPOSSIBLE to pass under the current DoD definition while
Charlotte's real redemption rate (110/304 = 36.2% of all foreclosure rows)
stays this high -- a live-data property of Charlotte's market, not a data
quality gap in this pipeline.

DECISION: no systemic matcher bug found. No PropertyOnion litmus lever
available either (per charlotte:D's same-day confirmed zero-overlap finding).
No writes made this session -- forcing any of the 112 CLERK_SSOT_CANCELLED
rows to matched_clean without a live re-verified sale would be exactly the
kind of ghost-fill this task's HARD RULES prohibit, and would not even clear
the threshold. C stays FAIL at 57.6% (175/304): genuine structural ceiling,
re-confirmed for the Nth time with zero drift from the prior findings.

Live source of truth referenced by prior sessions (spot-check blocked from
this sandbox -- www.charlotte.realforeclose.com returns 403 both via curl and
Playwright/Chromium from this runner's egress IP; same limitation those
sessions documented): www.charlotte.realforeclose.com PREVIEW pages, rendered
via Playwright/Chromium.

This script is a record of the investigation queries; it performs zero writes.
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
}

COUNTY = 'charlotte'


def get(path):
    r = requests.get(f'{REST}/{path}', headers=H, timeout=30)
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    rows = get(
        f'multi_county_auctions?county=eq.{COUNTY}&select=parity_status,sale_type'
    )
    from collections import Counter
    breakdown = Counter((r.get('parity_status'), r.get('sale_type')) for r in rows)
    print('Charlotte parity_status x sale_type breakdown (VERIFIED live):')
    print(json.dumps({f'{k[0]}/{k[1]}': v for k, v in breakdown.most_common()}, indent=2))

    cancelled = get(
        f'multi_county_auctions?county=eq.{COUNTY}&sale_type=eq.foreclosure'
        f'&parity_status=eq.CLERK_SSOT_CANCELLED'
        f'&select=tier1_sale_status,sold_amount'
    )
    tss = Counter(r.get('tier1_sale_status') for r in cancelled)
    sold_ct = sum(1 for r in cancelled if r.get('sold_amount') is not None)
    print(f'\nCLERK_SSOT_CANCELLED rows: {len(cancelled)}')
    print('tier1_sale_status breakdown:', dict(tss))
    print('rows with sold_amount set (would indicate mislabel):', sold_ct)

    print('\nDECISION: structural ceiling confirmed, no writes made.')
