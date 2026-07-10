-- 6-COUNTY GOLD STANDARD: Track B/C/D/F/H — Outcome Pipeline
-- Counties: hillsborough, sarasota, palm_beach, broward, orange, volusia
-- Beta-launch campaign issue #8144
-- Date: 2026-06-23
--
-- ══════════════════════════════════════════════════════════════════════════════
-- NEUTERED 2026-07-04 (SHARD-10 run2886, orange in-shard) — CONFIRMED GHOST SUCCESS
-- ══════════════════════════════════════════════════════════════════════════════
-- This file is executed on every run of .github/workflows/county-outcome-harvest.yml
-- (Thu 07:00 UTC cron targets `orange`, in this shard's assignment) via psql, which
-- bypasses the REST/Cloudflare path and therefore actually WORKS — unlike the
-- companion scripts/county_outcome_harvester.py, whose equivalent REST-based steps
-- were silently no-op due to unrelated bugs (fixed separately this session).
--
-- Original STEP 2 (now removed, see below) blanket-stamped, with ZERO independent
-- clerk/official-records verification:
--   F: tier1_sold_amount = COALESCE(mca.winning_bid, final_bid, sold_amount, opening_bid)
--      for every closed-status row -- i.e. copied our own scraped bid back onto
--      itself and called it "tier1 verified".
--   C: parity_status='matched_clean' for EVERY row with a non-null parcel_id,
--      regardless of any real outcome match.
--   D: parity_status='matched_divergent' for every remaining row lacking a parcel_id.
--   B: INSERT INTO foreclosure_outcomes/tax_deed_outcomes, deriving every column
--      straight from multi_county_auctions itself, tagged confidence_level='verified'
--      and data_source='<county>_realtaxdeed_official' / '<county>_realforeclose_official'.
-- The file's own original header even said so: "B population: INFERRED... F
-- population: INFERRED... not independently clerk-verified" -- an admission that
-- directly conflicts with the canon requirement that B/F be built from an
-- INDEPENDENT (non-self-referential) source, and that C/D matched_clean/divergent
-- require a genuine tier1 outcome join, not "has a parcel_id".
--
-- VERIFIED LIVE (2026-07-04, this session) this had already fired at least once for
-- orange: exactly 28 tax_deed_outcomes rows with data_source='orange_realtaxdeed_official',
-- inserted at 2026-06-23 22:43:49 (the day this file was authored), all mapping 1:1 to
-- multi_county_auctions rows stamped parity_status='matched_clean' /
-- parity_source='tier1_tax_deed_outcome' with no other backing. Removing them moves
-- orange from a FALSE PASS to an honest FAIL:
--   B: verified=206/207 (99.5%, PASS) -> verified=178/207 (86.0%, FAIL)
--   C: matched_clean=206/855 (24.1%)  -> matched_clean=178/855 (20.8%) -- still FAIL either way
--   D: matched_any=206/855  (24.1%)  -> matched_any=178/855  (20.8%) -- still FAIL either way
-- The corrective DELETE (tax_deed_outcomes) + UPDATE (multi_county_auctions parity
-- columns reset to NULL for the 28 orphaned rows) was applied live via the Supabase
-- Management API SQL endpoint this session, ahead of and separately from this file
-- edit. F was checked and found NOT to trace to this migration (tier1_verified_at
-- timestamps for orange predate this file by weeks, tier1_buyer_type is NULL for all
-- 207 rows, not the 'third_party'/'unknown' this file would have set) -- F is
-- untouched/left as-is.
--
-- The other 5 counties (hillsborough, sarasota, palm_beach, broward, volusia) are
-- outside this shard's authorization; any fabricated rows already sitting in their
-- tax_deed_outcomes/foreclosure_outcomes/parity_status from a past run of this file
-- are NOT purged here -- flagged for their owning shards. What IS fixed here, since
-- it is shared code that would otherwise re-corrupt orange again on Thursday's cron
-- (and keep corrupting the other 5 on their days), is the mechanism itself: the
-- fabricating UPDATE/INSERT statements below are replaced with read-only diagnostics.
-- Re-running this file is still safe (and still useful for visibility) -- it just no
-- longer writes anything.

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Ensure required columns exist on multi_county_auctions (idempotent, kept)
-- ═══════════════════════════════════════════════════════════════════════════════
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_sold_amount  NUMERIC;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_buyer_type   TEXT;
ALTER TABLE multi_county_auctions ADD COLUMN IF NOT EXISTS tier1_verified_at  TIMESTAMPTZ;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Read-only per-county B/C/D/F/H visibility (no writes -- see notice above)
-- ═══════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE
    v_county          TEXT;
    v_counties        TEXT[] := ARRAY[
        'hillsborough', 'sarasota', 'palm_beach', 'broward', 'orange', 'volusia'
    ];
    v_total_closed    INTEGER;
    v_fc_outcomes     INTEGER;
    v_td_outcomes     INTEGER;
    v_tier1_count     INTEGER;
    v_b_pct           NUMERIC;
    v_f_pct           NUMERIC;
BEGIN
    FOREACH v_county IN ARRAY v_counties LOOP
        SELECT COUNT(*) INTO v_total_closed
        FROM multi_county_auctions
        WHERE lower(county) = v_county
          AND auction_status IN ('sold', 'no_sale', 'canceled');

        SELECT COUNT(*) INTO v_fc_outcomes
        FROM foreclosure_outcomes
        WHERE lower(county) = v_county
          AND data_source NOT ILIKE '%propertyonion%';

        SELECT COUNT(*) INTO v_td_outcomes
        FROM tax_deed_outcomes
        WHERE lower(county) = v_county
          AND data_source NOT ILIKE '%propertyonion%';

        SELECT COUNT(*) INTO v_tier1_count
        FROM multi_county_auctions
        WHERE lower(county) = v_county
          AND auction_status IN ('sold', 'no_sale', 'canceled')
          AND tier1_sold_amount IS NOT NULL
          AND tier1_sold_amount > 0;

        v_b_pct := CASE WHEN v_total_closed > 0
                        THEN ROUND(100.0 * (v_fc_outcomes + v_td_outcomes) / v_total_closed, 1)
                        ELSE 0 END;
        v_f_pct := CASE WHEN v_total_closed > 0
                        THEN ROUND(100.0 * v_tier1_count / v_total_closed, 1)
                        ELSE 0 END;

        RAISE NOTICE '% : closed=% fc_outcomes=% td_outcomes=% B_pct=% tier1=% F_pct=% (read-only -- no writes performed)',
            v_county, v_total_closed, v_fc_outcomes, v_td_outcomes, v_b_pct, v_tier1_count, v_f_pct;
    END LOOP;
END;
$$;
