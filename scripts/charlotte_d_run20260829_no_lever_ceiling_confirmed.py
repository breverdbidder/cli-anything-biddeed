#!/usr/bin/env python3
"""Charlotte County Gold Standard D fix — investigation only, ZERO writes made
(dispatch: 2026-08-29, criterion D parity_any, FAIL at 94.4% / 287/304, gap 2
rows to reach 95%/289 rows).

RESULT: genuine data ceiling. NO fix applied. This script documents the
investigation performed and the evidence for why the gap cannot be closed
honestly right now, per the task's HARD RULES (never write a value without a
verifiable external source; blank is always better than wrong).

INVESTIGATION (all live, this session):

1. Live query `multi_county_auctions` county=eq.charlotte, GROUP BY
   parity_status:
     matched_clean          175
     CLERK_SSOT_CANCELLED   112
     NULL                    17
   Total 304. matched_any (per canonical evaluator SQL in
   supabase/migrations/20260810_gold_standard_shard3_lake_clerk_ssot_cd_recognition.sql
   line 52-53) = matched_clean + matched_divergent(tier1%) +
   PARITY_OK/CLERK_VERIFIED/CLERK_SSOT_CANCELLED = 175+112 = 287/304 = 94.4%,
   matching the live pencil_dod_evaluate_county(D) output exactly.

2. Pulled full detail (case_number, auction_date, sale_type,
   tier1_sale_status, tier1_source_run_id, tier1_verified_at) for all 17 NULL
   rows. Breakdown by why each is NULL (today = 2026-08-29 per `date -u`):

   a. 26-0178 (10468 WILMINGTON BOULEVARD, ENGLEWOOD) — auction_date
      2026-08-25 (past), tier1_sale_status='RESCHEDULED',
      tier1_verified_at=2026-08-25T23:55Z, tier1_authoritative=true.
      Live-rechecked via Playwright (Bright Data residential browser proxy,
      BRIGHTDATA_BROWSER_WSS) against
      https://www.charlotte.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/25/2026
      -- rendered page shows 10 TAXDEED items only (Running/Waiting/
      Closed-or-Canceled areas), zero FORECLOSURE-type items, and case
      26-0178 / parcel 412002229018 does NOT appear anywhere on that date's
      calendar. Also scanned county calendar pages for 08/26, 08/29, 08/31,
      09/01, 09/02, 09/08, 09/15, 09/22, 09/29/2026 (08/27-08/28 timed out) --
      case 26-0178 / parcel 412002229018 appears on NONE of them. Genuinely
      rescheduled with no new date posted yet by the county. No honest status
      to stamp -- correctly left NULL, matching what tier1 ingestion already
      recorded.

   b. 6 rows, auction_date=2026-08-31 (2 days in the future), sale_type=
      foreclosure, tier1_sale_status='LISTED' (5 rows) or
      'CANCELED_PER_COUNTY' (1 row: 25001583CA), tier1_source_run_id=171721,
      tier1_verified_at=2026-08-29T16:10:00Z (fresh, same-day). Auction has
      not occurred yet -- no real outcome exists to record.
      NOTE: 25001583CA already reads CANCELED_PER_COUNTY in tier1 but was not
      parity-stamped; investigated as a possible quick win (see below).

   c. 10 rows, auction_date=2026-09-01 (3 days in the future), sale_type=
      tax_deed, tier1_sale_status=NULL, tier1_source_run_id=NULL (no tier1
      ingestion run has covered this date yet). Auction has not occurred.

3. PropertyOnion litmus check (per task instructions: grep for
   "propertyonion"/"parity_status" in scripts/, found `propertyonion_listings`
   table, fips_code=12015 for Charlotte -- confirmed via a general county
   query returning real Charlotte rows). Queried by street-name ILIKE for
   all 17 target addresses: several returned similarly-named/nearby-numbered
   properties (e.g. 27097 San Domingo Dr existed for 26-0257 -- exact street
   match) but EVERY candidate's auction_date was from 2018-2024, none in the
   2026-08/09 window. Confirmed with a direct query:
     `propertyonion_listings?fips_code=eq.12015&auction_date=gte.2026-08-01`
     -> [] (zero rows).
   Independently cross-checked against the repo's own
   `v_calendar_parity_vs_po` view for county=charlotte:
     tax_deed:    our_own=10, po_sourced_in_ours=0, po_bar=0, status=NO_BAR
     foreclosure: our_own=6,  po_sourced_in_ours=0, po_bar=0, status=NO_BAR
   PropertyOnion has NO coverage of Charlotte's current auction cycle. There
   is no genuine litmus counterpart for any of the 17 rows to match against.

4. Attempted a live-recheck fix for 25001583CA specifically (tier1 already
   says CANCELED_PER_COUNTY, same pattern as the charlotte_c_run106703 and
   charlotte_cd_tier1_run93161 precedent scripts that stamped
   CLERK_SSOT_CANCELLED off a live-confirmed cancellation). Attempted to
   re-verify live against the 08/31/2026 RealForeclose PREVIEW page via the
   same Bright Data Playwright path used successfully for step 2a; this
   specific fetch was blocked by Bright Data's own robots.txt enforcement
   ("Requested URL is restricted in accordance with robots.txt... Ask your
   account manager to get full access") -- an infrastructure-side block, not
   a data absence. Did NOT stamp CLERK_SSOT_CANCELLED on tier1's own say-so
   alone without a second live confirmation, to stay consistent with this
   repo's established two-source-corroboration pattern for cancellations.
   Flagging this as the one row with a plausible near-term lever (retry the
   live recheck once Bright Data access allows, or wait 2 days for the
   auction date to pass and let the normal tier1 ingestion run capture the
   final RealForeclose status naturally).

CONCLUSION: 0 of the 17 NULL rows can be honestly resolved today.
  - 1 row (26-0178) is a genuine unresolved reschedule (verified absent from
    9 forward calendar dates).
  - 6 rows (2026-08-31) and 10 rows (2026-09-01) are auctions that have not
    yet occurred (today=2026-08-29) -- no real outcome exists to record.
  - PropertyOnion, the litmus source named in the task, has zero rows
    overlapping Charlotte's live auction cycle -- confirmed both by direct
    query and by the repo's own v_calendar_parity_vs_po view.
Per task HARD RULES ("If you cannot find a real source for a row, LEAVE IT
NULL and report it as a genuine data ceiling" / "Do not force parity_status
to 'matched' without a verified counterpart row"), NO writes were made this
session. D remains FAIL at 94.4% (287/304). This is a timing ceiling that
will resolve naturally as tier1 ingestion captures real outcomes after
2026-08-31 and 2026-09-01 pass, plus a possible 1-row win on 25001583CA once
a live recheck succeeds.

This script makes zero database writes; it is documentation-only, matching
the "genuine data ceiling" reporting convention used by prior sessions
(e.g. charlotte_c_run106703_null_parity_fix_gsd2_84b6c4bb.py's C-criterion
ceiling section).
"""

if __name__ == '__main__':
    print("No writes made. See docstring for full investigation and evidence.")
    print("D remains FAIL at 94.4% (287/304) -- genuine timing/data ceiling, "
          "not a fixable matcher bug. All 17 NULL parity_status rows are "
          "either a genuinely unresolved reschedule (1) or future auctions "
          "that have not occurred yet (16). PropertyOnion has zero rows "
          "overlapping Charlotte's 2026-08/09 auction cycle (verified via "
          "v_calendar_parity_vs_po: po_bar=0 for both sale_types).")
