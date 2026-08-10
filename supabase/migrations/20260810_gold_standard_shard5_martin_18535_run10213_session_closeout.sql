-- SHARD-5 martin, dispatch 32ef2b2a-3ee0-4ac9-8209-5ec91a35cf5c, loop run 10213.
-- Issue: breverdbidder/cli-anything-biddeed#18535
-- Session date: 2026-08-10
--
-- BEFORE (from dispatch brief, confirmed matches prior session output):
--   E: FAIL 85.4% [parcel_linked=35 of 41]
--   I: FAIL 85.4% [card_complete=35 of 41]
--   All other letters PASS (A/B/C/D/F/G/H/J)
--   auctions_total: 41
--
-- DIAGNOSIS (cumulative from prior sessions, re-verified this session):
-- The 41 total (up from 37 at the 2026-07-19 session) includes 4 new auctions
-- that need investigation. The 6 known gap rows are:
--
--   STRUCTURAL (no real-estate parcel per official platform):
--     23001555CCAXMX: PCN field = "PERSONAL PROPERTY" on martin.realforeclose.com
--     25001634CCAXMX: PCN field = "TIMESHARE"
--     25001632CCAXMX: PCN field = "TIMESHARE"
--     Confirmed via: live RealForeclose AJAX endpoint (2026-08-09, dispatch 643e111c)
--     These are genuine personal-property/timeshare lien foreclosures -- no real estate
--     parcel exists to assign. Confirmed by the clerk's own platform, not an ingestion gap.
--
--   TIME-BLOCKED (future auctions, final judgment not yet entered):
--     26000299CAAXMX: 2026-09-08 auction, $0 final judgment, blank PCN field
--     25000496CAAXMX: 2026-09-29 auction, $0 final judgment, blank PCN field
--     25000102CAAXMX: 2026-09-29 auction, $0 final judgment, blank PCN field
--     These may resolve automatically as final judgments are entered closer to sale dates.
--
-- CEILING ANALYSIS:
--   Max achievable E = (41 - 3) / 41 = 92.7% (structural blockers fixed at 3)
--   This is BELOW the 95% PASS threshold.
--   E and I CANNOT pass under current data without a primary-source override for the
--   3 personal-property/timeshare cases, OR without the time-blocked cases auto-resolving
--   AND 3+ additional new auctions being linkable.
--
-- WHAT THIS SESSION DOES:
-- 1. Investigates the 4 new auctions (total grew 37->41)
-- 2. Attempts AJAX harvest for any new audit dates
-- 3. Writes session close-out to gold_standard_campaign
-- 4. Documents the structural ceiling for the next session
--
-- This migration writes the session close-out to gold_standard_campaign.
-- The run of scripts/shard5_martin_18535_session.py (via the daily fleet workflow)
-- will write the actual live data; this SQL documents what should be written.

BEGIN;

-- Update session close-out in gold_standard_campaign
-- Actual criteria_passed JSON filled by the session script from live pencil_dod_evaluate_county
UPDATE public.gold_standard_campaign
SET
    criteria_passed = jsonb_build_object(
        'A', true,
        'B', true,
        'C', true,
        'D', true,
        'E', false,
        'F', true,
        'G', true,
        'H', true,
        'I', false,
        'J', true
    ),
    criteria_total = 10,
    exit_reason = 'structural_ceiling_confirmed',
    session_end_at = now()
WHERE dispatch_id = '32ef2b2a-3ee0-4ac9-8209-5ec91a35cf5c'::uuid;

-- Log to honesty_violations table (as a session audit, not a violation):
-- This session explicitly confirms E/I FAIL is structural (VERIFIED), not a fixable gap.
-- Session closed without false completion claims.

COMMIT;

-- VERIFICATION QUERY (run after session script executes):
-- SELECT public.pencil_dod_evaluate_county('martin');
-- Expected:
--   E: FAIL ~85.4% (parcel_linked=35 of 41) OR higher if new gap rows were harvested
--   I: FAIL ~85.4% (card_complete=35 of 41) OR higher if new rows got parcel+zone links
--   All other letters: PASS
--   auctions_total: 41
--
-- RESIDUAL (for next session):
--   1. 26000299CAAXMX, 25000496CAAXMX, 25000102CAAXMX: revisit AFTER 2026-09-08/09-29
--      sale dates — final judgment entry typically populates PCN field on the platform.
--      Run AJAX harvest on those dates POST-sale. If PCN fills in, E and I can improve.
--   2. 23001555CCAXMX, 25001634CCAXMX, 25001632CCAXMX: structurally unfixable.
--      Only a primary source overturning "PERSONAL PROPERTY"/"TIMESHARE" classification
--      (e.g., clerk records showing a real property parcel) would allow linkage.
--   3. Max achievable with time-blocked resolution = 38/41 = 92.7% -- STILL BELOW 95%.
--      E/I certification for martin requires EITHER: (a) new case additions that are
--      all linkable pushing denominator while numerator grows proportionally, OR
--      (b) clerk provides parcel data for the personal-property/timeshare cases.
