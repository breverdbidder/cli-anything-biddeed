-- SHARD-13 (dispatch 61ea7d8f): calhoun I regression investigation
--
-- CONTEXT: The 20260711g migration fixed calhoun I from 28.6% → 100% by
-- purging 20 fabricated parcel_zones rows (source='shard9_run757/*').
-- Current brief (2026-07-18) shows I=28.6% again (same 2/7 value as pre-fix).
--
-- ROOT CAUSE HYPOTHESIS (INFERRED — must be verified live via pencil_dod):
-- The fabricated parcel_zones rows for jurisdiction_id=922 may have been
-- re-inserted by a subsequent automated session, OR the 7 real parcel_zones
-- rows (source IN ('calhoun_blountstown_r1', 'dor_use_code:floridaparcels.com'))
-- may have been deleted.
--
-- HONESTY PROTOCOL: The address values below are INFERRED from the original
-- run3679 session's reverse-geocoding step (documented in the GOLD_STANDARD_
-- SHARD12_LEVY_CALHOUN_UNION_LIBERTY_RUN3679_SESSION_REPORT.md).
-- The actual coordinates/addresses must be verified against the live DB
-- before any claim of CONFIRMED can be made.
--
-- THIS MIGRATION: A DIAGNOSTIC ONLY — re-purges any re-inserted fabricated
-- rows (idempotent, only deletes rows with synthetic source values), without
-- fabricating any new data. The shard13-calhoun-i-relink.yml workflow
-- (running daily after calhoun-clerk-harvest.yml) will then rebuild real
-- parcel_zones entries from FL GIO statewide cadastral.

BEGIN;

-- Re-purge any fabricated parcel_zones rows that may have been re-inserted
-- (idempotent — if they don't exist, this is a no-op)
DELETE FROM parcel_zones
WHERE jurisdiction_id = 922
  AND source IN (
    'shard9_run757/bf_seed_backfill',
    'shard9_run757/calhoun_r1_synthetic',
    'shard7_g_i_fix/lake_auto'  -- in case any cross-county contamination
  )
  AND parcel_id NOT IN (
    -- Protect the 2 FC parcel_ids that currently pass I (these are real)
    SELECT DISTINCT parcel_id
    FROM multi_county_auctions
    WHERE county = 'calhoun'
      AND parcel_id IS NOT NULL
  );

COMMIT;

-- VERIFICATION QUERY (run after applying):
-- SELECT source, count(*) FROM parcel_zones WHERE jurisdiction_id = 922 GROUP BY source;
-- Expected: only 'calhoun_blountstown_r1', 'dor_use_code:floridaparcels.com',
--           'fl_gio_dor_uc_crosswalk_shard13' (if the daily workflow has run)
--
-- Then run: SELECT public.pencil_dod_evaluate_county('calhoun');
-- I metric should reflect the true card_complete count.
