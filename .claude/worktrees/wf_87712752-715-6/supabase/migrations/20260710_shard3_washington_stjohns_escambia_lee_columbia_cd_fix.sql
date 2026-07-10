-- GOLD STANDARD SHARD-3 (dispatch b466d99d-cd0c-49ee-96c1-be28b2a3d2b6)
-- Counties: washington, st_johns, escambia, lee, columbia
--
-- ROOT CAUSE #1 (fleet-wide, VERIFIED live): GH Actions secrets
-- SUPABASE_SERVICE_ROLE_KEY and SUPABASE_DB_PASSWORD were stale for an
-- unknown prior window, causing every scraper write and every H-freshness
-- "trigger-safe stamp" workflow to 401/auth-fail while still reporting
-- workflow conclusion=success (caught HTTPError, no re-raise). All 5 shard
-- counties' H had been stuck FAIL for >3 days as a result. The secret was
-- already corrected upstream at 2026-07-09T20:10:57Z (before this session
-- started) but no workflow had run since — this session manually dispatched
-- the real scrapers (gold-standard-shard1-daily target=washington,
-- gold-standard-shard6-run651 for st_johns, shard9-daily-scraper for lee,
-- calendar-sweep-dark-counties for escambia/st_johns/columbia,
-- shard7-columbia-scraper) to land fresh data and confirm H recovers.
-- Same historical failure mode as commit 2530c0b6 (35 days of silent 401s).
--
-- ROOT CAUSE #2 (escambia, lee): tax-deed/foreclosure calendar rows added
-- by later calendar sweeps were never run through the tier1 RealAuction AJAX
-- matcher (parity_status/parity_source both NULL) — same pattern as the
-- prior 20260704_shard1_run2820cont3_escambia_stlucie_lee_cd_realforeclose_aids
-- migration this session extends. Fresh paginated AJAX harvest
-- (scripts/realforeclose_aids_paginated_harvest.py) for the missing dates +
-- re-run of the identical idempotent county-scoped matching UPDATE below.
--
-- REGRESSION CAUSED + FIXED WITHIN THIS SESSION: dispatching
-- calendar-sweep-dark-counties (needed to test the secret fix broadly)
-- pulled in new escambia tax-deed rows and new st_johns foreclosure rows
-- faster than they could be matched/enriched, transiently dropping
-- escambia C/D/I/J and st_johns C/D/E/I/J below their pre-session PASS
-- state. Recovered via: (1) a second AJAX harvest+match pass for the new
-- dates, (2) Shapira-formula J backfill for the newly-added rows lacking
-- bid_decisions (scoped ad-hoc scripts, not committed — same formula/
-- factors contract as scripts/shard9_j_generator.py, all factors carry
-- honesty_marker=INFERRED per the existing pattern). st_johns's aids table
-- also had a pre-existing parser bug (some AITEM blocks parse
-- "Property Appraiser" / "MULTIPLE PARCELS" as literal parcel_id — flagged
-- below, NOT fixed this session) — the matching UPDATE for st_johns adds a
-- regex guard so those placeholder strings are never written as parcel_id.
--
-- KNOWN RESIDUALS (not fixed this session, honest accounting):
--   escambia I: 78.5% — 71 tax-deed rows added by the calendar sweep lack
--     property_address/assessed_value/lat-long. Needs a Property Appraiser
--     enrichment pass, not a parity/matching fix.
--   escambia/lee C/D: genuine RealAuction calendar ceiling — re-harvest
--     confirmed the remaining unmatched case numbers are not present on the
--     live AJAX calendar for their dates (verified, not assumed).
--   lee E/I: 24 rows matched_clean via case number but realforeclose_aids
--     itself carried no parcel_id for those AIDs. Needs Lee County Property
--     Appraiser GIS lookup (endpoint not yet identified this session).
--   st_johns E/I: 6 rows blocked by the aids parser bug above (4) plus 2
--     genuinely unlinked.
--   columbia: A/B/C/D/F/I still fail. Tax-deed lane was never configured
--     for this county (fc=9 td=0) and none of its 9 auctions have closed
--     yet, so B/F are structurally null (not a gap to force — BLANK>WRONG).
--     C/D need a second independent source; columbia_clerk_html IS the
--     court's own direct feed, so self-stamping tier1 without a genuine
--     cross-source comparison would be exactly the ghost-success pattern
--     this file elsewhere documents fixing — deliberately left FAIL rather
--     than gamed.
--
-- VERIFIED RESULTS (pencil_dod_evaluate_county, live, before -> after):
--   washington: 9/10 -> 10/10  (H: FAIL 47.1 -> PASS 0.2)   *** CERTIFIED ***
--   st_johns:   9/10 -> 8/10   (H: FAIL 79.9 -> PASS; C/D: 100->100 after
--               dip-and-recover; net E now 83.8% FAIL, was 100% at a
--               denominator of 32 before the sweep grew it to 37 — see
--               residuals above)
--   escambia:   7/10 -> 7/10   (H: FAIL 79.9 -> PASS; C/D: 75.9% -> 77.0%
--               after dip-and-recover; I newly FAIL at 78.5% — residual
--               above; J: 98.5% -> 100%)
--   lee:        5/10 -> 6/10   (H: FAIL 79.9 -> PASS; C: 89.7% -> 91.6%;
--               D: 90.1% -> 91.9%; E/I unchanged — residual above)
--   columbia:   2/10 -> 4/10   (H: FAIL 85.7 -> PASS; J: 0% -> 100% via
--               Shapira formula backfill, ARV sourced Redfin county median)
-- Full before/after JSON pasted in the session decision log / issue comment
-- per SHIP GATE.

-- Idempotent tier1 case-number / parcel-id matching UPDATE (verbatim pattern
-- from 20260704_shard1_run2820cont3_escambia_stlucie_lee_cd_realforeclose_aids,
-- extended to st_johns with a parcel_id sanity guard against the aids parser
-- bug documented above).
DO $$
DECLARE v_county text;
BEGIN
  FOREACH v_county IN ARRAY ARRAY['escambia','lee','st_johns'] LOOP
    EXECUTE format($f$
      UPDATE multi_county_auctions mca
      SET parity_status = 'matched_clean',
          parity_source = 'tier1_realforeclose_aids_%1$s',
          parcel_id = COALESCE(mca.parcel_id,
                       CASE WHEN ra.parcel_id ~ '^[0-9-]+$' THEN ra.parcel_id ELSE NULL END),
          updated_at = now()
      FROM realforeclose_aids ra
      WHERE ra.county_slug = %1$L
        AND lower(mca.county) = %1$L
        AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR mca.tier1_authoritative = true)
        AND NOT (COALESCE(mca.parity_status,'') IN ('matched_clean','matched_divergent')
                 AND COALESCE(mca.parity_source,'') LIKE 'tier1%%')
        AND normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    $f$, v_county);

    EXECUTE format($f$
      UPDATE multi_county_auctions mca
      SET parity_status = 'matched_divergent',
          parity_source = 'tier1_realforeclose_aids_%1$s',
          updated_at = now()
      FROM realforeclose_aids ra
      WHERE ra.county_slug = %1$L
        AND lower(mca.county) = %1$L
        AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR mca.tier1_authoritative = true)
        AND NOT (COALESCE(mca.parity_status,'') IN ('matched_clean','matched_divergent')
                 AND COALESCE(mca.parity_source,'') LIKE 'tier1%%')
        AND mca.parcel_id IS NOT NULL AND ra.parcel_id IS NOT NULL AND mca.parcel_id = ra.parcel_id
        AND normalize_case_number(mca.case_number) IS DISTINCT FROM normalize_case_number(ra.case_number)
    $f$, v_county);
  END LOOP;
END $$;
