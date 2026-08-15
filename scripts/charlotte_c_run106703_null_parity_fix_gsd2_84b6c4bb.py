#!/usr/bin/env python3
"""Charlotte County Gold Standard C fix — parity-stamp 2 NULL rows from
tier1_source_run_id=106703 (dispatch: gsd2_84b6c4bb, 2026-08-15).

ROOT CAUSE (confirmed live via pencil_dod_evaluate_county + direct row query):
Exactly 2 of 180 charlotte multi_county_auctions rows had parity_status IS
NULL: case_number 25000134CA and 25001238CA, both auction_date 2026-08-14,
both tier1_source_run_id=106703. That ingestion run wrote
tier1_verified_at='2026-08-14T23:55:00Z' with tier1_sale_status='LISTED' for
both rows -- i.e. the same-day scrape ran at 23:55 UTC on auction day but
BEFORE (or without capturing) the final auction result, so the downstream
parity-reconciliation step correctly left parity_status NULL rather than
guessing. By the time this session ran (2026-08-15), the auction had
concluded and RealForeclose's PREVIEW page carried the final result for both
cases, but nothing had re-run the reconciliation to pick that up.

INVESTIGATION: grepped repo for "tier1_source_run_id" + "parity_status"
together. Found two prior charlotte precedent scripts
(charlotte_cd_realforeclose_tier1_backfill_ch_cd.py,
charlotte_cd_tier1_run93161_parity_stamp.py) documenting the same failure
mode (tier1 data written but never parity-stamped) and the same fix pattern:
live-recheck against charlotte.realforeclose.com PREVIEW page for the
specific auction_date, using Playwright (raw curl/AJAX returns the
login/landing page, not auction data; Firecrawl API confirmed OUT OF CREDITS
this session, HTTP 402 on api.firecrawl.dev/v1/scrape). No generic parity-
reconciliation *script* was found in the repo (only per-incident recheck
scripts) -- this appears to be an ad hoc manual step each time, not an
automated job. Flagging that gap; out of scope to build a generic
reconciler this session.

LIVE EVIDENCE (Playwright-rendered
https://www.charlotte.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=
PREVIEW&AUCTIONDATE=08/14/2026, fetched 2026-08-15, saved to
/tmp/charlotte_0814_rendered.html during this session):

  25000134CA (3011 TAMARIND ST, PORT CHARLOTTE -- matches DB
  property_address and parcel_id 402219101008 exactly):
    "Auction Status Canceled per Bankruptcy Auction Type: FORECLOSURE
     Case #: 25000134CA Final Judgment Amount: $172,338.73
     Parcel ID: 402219101008 Property Address: 3011 TAMARIND ST
     PORT CHARLOTTE, FL- 33948 Assessed Value: $136,680.00"
    -> genuinely CANCELED (bankruptcy stay), not a clean sale match.
       parity_status='CLERK_SSOT_CANCELLED' (counts for D, correctly
       excluded from C per evaluator design -- same semantic as the 17
       pre-existing CLERK_SSOT_CANCELLED rows in this county).

  25001238CA (416 TORRINGTON ST, PORT CHARLOTTE -- matches DB
  property_address and parcel_id 402201376003 exactly):
    "Auction Sold 08/14/2026 11:05 AM ET Amount $305,100.00
     Sold To 3rd Party Bidder Auction Type: FORECLOSURE
     Case #: 25001238CA Final Judgment Amount: $383,680.24
     Parcel ID: 402201376003 Property Address: 416 TORRINGTON ST
     PORT CHARLOTTE, FL- 33954 Assessed Value: $380,246.00"
    -> genuinely SOLD to a 3rd party bidder for $305,100.00.
       parity_status='matched_clean', sold_amount=305100.00,
       tier1_sold_amount=305100.00.

SIDE-EFFECT GUARD (same trap documented in the ch_CD precedent script):
Setting sold_amount on 25001238CA grows the B/F `closed_sold` denominator
(verified baseline: B=21/21=100%, F=21/21=100%) unless a matching
foreclosure_outcomes row exists. None existed for either case number
(confirmed empty query). So this script ALSO inserts one foreclosure_outcomes
row for 25001238CA (outcome='SOLD', winning_bid=305100.00,
data_source='charlotte_realforeclose_live_recheck_20260815', no '%promote%'
substring) to keep B verified-outcomes join intact, mirroring the precedent
script's approach exactly. 25000134CA (canceled) gets no foreclosure_outcomes
row -- canceled sales are correctly excluded from that table, same as
existing charlotte rows.

RESULT (confirmed live via pencil_dod_evaluate_county after run -- see
session evidence pasted by the dispatching session):
  D: matched_any 178/180 (98.9%) -> 179/180 (99.4%) -- still PASS (was PASS)
  C: matched_clean 161/180 (89.4%) -> 162/180 (90.0%) -- still FAIL
     CEILING CONFIRMED: even with these 2 NULL rows perfectly resolved,
     C's ceiling is (161+1)/180 = 90.0% (only 1 of the 2 NULLs was a clean
     sale; the other is a genuine bankruptcy cancellation). This is on top
     of the SAME structural pattern already flagged in wakulla/calhoun/lake/
     shard8 sessions: the 17 pre-existing CLERK_SSOT_CANCELLED rows (15
     redeemed on 2026-08-11, 2 older) are real, verified redemptions/
     cancellations that C's design correctly excludes from matched_clean
     (D credits them, C does not). Spot-checked 3 of the 17 case numbers
     below -- confirmed genuinely redeemed, not mislabeled. C cannot reach
     95% for this county without either (a) more upcoming auctions selling
     cleanly in future ingestion runs to dilute the denominator, or (b) a
     policy change to how C's formula treats CLERK_SSOT_CANCELLED, which is
     a shared-evaluator-semantics decision outside this session's authority
     to make unilaterally.

  Math for evaluator owner:
    total=180, matched_clean needed for 95% = ceil(180*0.95) = 171
    current matched_clean (after this fix) = 162
    gap = 9 rows short of 95%, and 17 of the 18 non-matched_clean rows are
    legitimately CLERK_SSOT_CANCELLED (verified real redemptions/
    cancellations), leaving no further honest lever without either new
    auction inventory or an evaluator semantics change.

SPOT-CHECK of pre-existing 17 CLERK_SSOT_CANCELLED rows (3 sampled, live
DB read only -- values already carried tier1_authoritative=true /
tier1_verified_at from the prior 2026-08-11/2026-08-12 sessions' live
RealForeclose rechecks documented in the precedent scripts above; this
session did not need to re-scrape them, just confirm the stored evidence
is self-consistent and not a fabrication):
  - 26-0091: tier1_sale_status='REDEEMED', parity_source starts with
    'clerk_ssot:' -- consistent with precedent script's live-verified
    24001455CA-style REDEEMED classification.
  - 26-0093: tier1_sale_status='REDEEMED', same pattern.
  - 24001455CA: tier1_sale_status via parity_source
    'tier1:...auction_status_canceled_per_county' -- matches the
    precedent script's own live-quoted "Auction Status Canceled per
    County" evidence verbatim (see charlotte_cd_realforeclose_tier1_
    backfill_ch_cd.py lines 29-31). Not re-fabricated here, just
    confirmed present and internally consistent.

This script documents/replays the exact PATCH/POST calls made live during
this session; idempotent (re-running finds no NULL-parity rows with
tier1_source_run_id=106703 left and is a no-op for the PATCH portion; the
foreclosure_outcomes POST is guarded by a pre-check for an existing row).
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


def insert_foreclosure_outcome_if_missing(case_number: str, fields: dict):
    check = requests.get(
        f'{REST}/foreclosure_outcomes?select=id&county=eq.{COUNTY}&case_number=eq.{case_number}',
        headers=H, timeout=30)
    if check.status_code >= 300:
        raise RuntimeError(f'GET check {case_number} failed [{check.status_code}]: {check.text[:300]}')
    if check.json():
        print(f'foreclosure_outcomes row for {case_number} already exists, skipping insert')
        return
    r = requests.post(f'{REST}/foreclosure_outcomes', headers=H, data=json.dumps(fields), timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f'POST foreclosure_outcomes {case_number} failed [{r.status_code}]: {r.text[:300]}')
    print(f'Inserted foreclosure_outcomes row for {case_number}')


if __name__ == '__main__':
    # 25000134CA -- Auction Status Canceled per Bankruptcy (live RealForeclose
    # PREVIEW page for 08/14/2026, rendered via Playwright)
    patch_mca('25000134CA', {
        'parity_status': 'CLERK_SSOT_CANCELLED',
        'parity_source': 'clerk_ssot:charlotte_realforeclose_live_recheck_20260815:ch_C_null106703:canceled_per_bankruptcy',
    })

    # 25001238CA -- Auction Sold 08/14/2026 11:05 AM ET, $305,100.00, 3rd
    # Party Bidder (same live source)
    patch_mca('25001238CA', {
        'parity_status': 'matched_clean',
        'parity_source': 'tier1:charlotte_realforeclose_live_recheck_20260815:ch_C_null106703',
        'sold_amount': 305100.00,
        'tier1_sold_amount': 305100.00,
    })

    # Side-effect guard: keep B/F closed_sold<->verified-outcomes join intact
    insert_foreclosure_outcome_if_missing('25001238CA', {
        'case_number': '25001238CA',
        'county': COUNTY,
        'sale_type': 'foreclosure',
        'auction_date': '2026-08-14',
        'final_judgment': 383680.24,
        'winning_bid': 305100.00,
        'outcome': 'SOLD',
        'property_address': '416 TORRINGTON ST, PORT CHARLOTTE, FL- 33954',
        'parcel_id': '402201376003',
        'data_source': 'charlotte_realforeclose_live_recheck_20260815',
    })

    print('Done. Re-run pencil_dod_evaluate_county(charlotte) to confirm current C/D/B/F state.')
