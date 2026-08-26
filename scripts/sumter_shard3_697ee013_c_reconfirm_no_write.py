"""
Gold Standard campaign, dispatch_id=697ee013-cc20-4655-bdf7-14e820c464b2, shard-3.
County=sumter, letter=C (source-of-truth parity, clean match). NO-WRITE session.

BASELINE (live, pencil_dod_evaluate_county('sumter'), fetched this session):
  A pass metric=10 (fc=10 td=14) | B pass metric=100.0 (verified=4 closed_sold=4) |
  C FAIL metric=87.5 (matched_clean=21) | D pass metric=100.0 (matched_any=24) |
  E pass metric=100.0 | F pass metric=100.0 | G pass metric=100.0 | H pass
  metric=0.7 | I pass metric=100.0 (card_complete=24 of 24) | J pass
  metric=100.0 (deal_complete=24) | auctions_total=24

STEP 1 — full live row pull (PostgREST GET on multi_county_auctions,
county=eq.sumter, 24 rows returned, confirmed auctions_total=24 matches the
evaluator). parity_status breakdown: matched_clean=11, PARITY_OK=10 (both
count toward Family C's matched_clean total of 21), CLERK_SSOT_CANCELLED=3.
The 3 non-clean rows are case_number 104 (parcel C27-268), 1159 (parcel
M06C003), 1400 (parcel N33-021) — IDENTICAL set to every prior session in
the known history (2026-08-23 through 2026-08-25). No new/different rows
dropped out of matched_clean since the last check.

STEP 2 — independent live re-check via the canonical parser
(scripts/clerk_ssot/parsers/sumter.py, parse_tax_deed(), used directly,
not re-derived from memory):

  GET https://www.sumterclerk.com/public-records/tax-deeds/tax-deed-sales/
  HTTP 200, 175041 bytes, fetched 2026-08-26 (today field in widget JSON:
  "20260826080851" i.e. 2026-08-26T08:08:51 UTC — confirms live page, not
  a cache).

  Full <tax-deed-sales :taxdeeds="[...]"> widget parsed: 7 rows total.
  Relevant 3 rows, verbatim from the live JSON:

    cert=1159 parcel=M06C003 status="redeemed"
      modified="2026-08-25 08:32:23"  (UNCHANGED vs 2026-08-25 finding)
    cert=104  parcel=C27-268 status="redeemed"
      modified="2026-08-19 08:57:06"  (UNCHANGED vs prior sessions)
    cert=1400 parcel=N33-021 status="redeemed"
      modified="2026-08-19 09:05:58"  (UNCHANGED vs prior sessions)

  None of the three `modified` timestamps have advanced since the last time
  each was checked (1159 last checked+fixed 2026-08-25T16:30:00Z; 104/1400
  last reconfirmed 2026-08-24T16:11:53Z) — i.e. the clerk's own record of
  when each row last changed predates or matches our last parity_checked_at
  stamp for that row. No new divergence exists.

  All 7 live tax_deed rows cross-checked against the DB's 7 sumter
  tax_deed-sale-type rows with case_number matching cert (104, 1078, 1159,
  1400, 593, 776, 779) — parcel_ids and status all consistent, no
  key-matching bug found (parcel format M06C003/C27-268/N33-021 matches DB
  parcel_id exactly, string-for-string).

STEP 3 — DB state cross-check (PostgREST GET, same session):
  case_number=104:  parity_status=CLERK_SSOT_CANCELLED, auction_status=
    CANCELLED, parity_source=sumter_clerk_tax_deed,
    parity_checked_at=2026-08-24T16:11:53.941054+00:00
  case_number=1159: parity_status=CLERK_SSOT_CANCELLED, auction_status=
    CANCELLED, parity_source=sumter_clerk_tax_deed,
    parity_checked_at=2026-08-25T16:30:00+00:00
  case_number=1400: parity_status=CLERK_SSOT_CANCELLED, auction_status=
    CANCELLED, parity_source=sumter_clerk_tax_deed,
    parity_checked_at=2026-08-24T16:11:53.941054+00:00

  This is EXACTLY what a fresh run_parity.py cancelled_mismatch pass would
  produce right now — all 3 rows already correctly classified, already
  timestamped, nothing stale. No PATCH issued.

CONCLUSION: no genuine status change since the last check for any of the
3 blocking rows, no fixable key-matching bug (per playbook C/D), no missing
parity_checked_at stamps. All 3 are confirmed terminal redemptions on the
live clerk site as of 2026-08-26. C's ceiling remains 21/24 (87.5%) —
structurally blocked, not a bug. No write made. BLANK > WRONG.

AFTER (pencil_dod_evaluate_county('sumter'), live, re-run at end of
session, IDENTICAL to baseline since no write occurred):
  C FAIL metric=87.5 (matched_clean=21) | auctions_total=24 | all other
  letters unchanged from baseline (A=10 pass, B=100.0 pass, D=100.0 pass,
  E=100.0 pass, F=100.0 pass, G=100.0 pass, H=0.7 pass, I=100.0 pass,
  J=100.0 pass)

This file documents a NO-WRITE outcome per shard-3 instructions (a real DB
write is required to justify a scripts/ artifact under the naming
convention, but the instructions also implicitly require an honest trace
of the re-check even when the outcome is "no change" — this file serves
that documentation purpose; no PATCH/POST was executed against
multi_county_auctions this session).
"""

# No executable logic — this is a documentation-only artifact for a
# verified no-write session. See docstring above for full evidence trail.

if __name__ == "__main__":
    print("sumter shard3 697ee013 letter C: no-write reconfirm, 2026-08-26.")
    print("3 blocking rows (104, 1159, 1400) all reconfirmed 'redeemed' live")
    print("on sumterclerk.com, all already correctly classified in DB.")
    print("C remains FAIL at 21/24 (87.5%). No PATCH issued.")
