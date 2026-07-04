-- SHARD-1 run2820 continuation-3 (dispatch 835df3a0-44ce-4a12-8e3e-de64c1b880a3)
-- Counties: escambia, st_lucie, lee (brevard already 10/10; bradford handled separately)
--
-- ROOT CAUSE (verified live via pencil_dod_evaluate_county before touching anything):
--   escambia C/D stuck at 4.1% because escambia's tax-deed lane (242 of 266 auctions,
--   data_source=calendar_sweep_mca_v3) had NEVER been run through ANY parity matcher —
--   realforeclose_aids had zero TAXDEED rows for escambia (only 32 FORECLOSURE rows).
--   st_lucie C/D stuck at 25.0% for the same reason (realforeclose_aids had only 18
--   FORECLOSURE rows, no TAXDEED coverage) -- discovered st_lucie's "realtaxdeed"
--   data_source label is a MISNOMER: source_url inspection shows these rows actually
--   come from stlucie.realforeclose.com (one unified RealAuction subdomain serves BOTH
--   foreclosure and tax-deed for this county; stlucie.realtaxdeed.com 302-redirects to
--   the generic realauction.com marketing page, i.e. does not exist as a real site).
--   lee C/D stuck at 54.2% despite realforeclose_aids ALREADY having good coverage
--   (218 FORECLOSURE + 37 TAXDEED rows) because the matching function had simply never
--   been run for lee this cycle, plus 5 rows carried a stale non-"tier1_" prefixed
--   parity_source ("shard9_cd_parity_fix_tier1litmus") from a prior session that does
--   not satisfy the evaluator's `parity_source LIKE 'tier1%%'` filter (left as-is here;
--   legitimacy of that prior label was independently audited in the Verify workflow
--   phase of this session, see session report).
--
-- FIX: (1) live AJAX harvest of the RealAuction PREVIEW/UPDATE endpoint (paginated via
-- PageDir until exhausted) for escambia.realtaxdeed.com (upcoming tax-deed dates
-- 07/01, 08/05, 09/02, 10/07, 11/04/2026), stlucie.realforeclose.com (07/01, 07/07,
-- 07/08/2026), and lee.realforeclose.com / lee.realtaxdeed.com (07/09, 07/16, 07/23,
-- 07/30, 08/18/2026) into realforeclose_aids (idempotent upsert on `aid`, see
-- scripts/shard2_run2450_ajax_realforeclose_harvest.py harvester, reused verbatim
-- with pagination added — see /tmp/escambia_full_harvest.py logic ported here).
-- (2) county-scoped matching UPDATEs below (NOT the shared, unscoped, cross-join
-- `realforeclose_aids_to_mca_patch()` function, which timed out against the full 245K
-- row multi_county_auctions table this session -- avoid calling it unscoped again).
--
-- These UPDATEs are idempotent (WHERE ... NOT already tier1-matched) — safe to re-run.

-- Exact case-number match -> matched_clean, tier1-prefixed per canon.
DO $$
DECLARE v_county text;
BEGIN
  FOREACH v_county IN ARRAY ARRAY['escambia','st_lucie','lee'] LOOP
    EXECUTE format($f$
      UPDATE multi_county_auctions mca
      SET parity_status = 'matched_clean',
          parity_source = 'tier1_realforeclose_aids_%1$s',
          parcel_id = COALESCE(mca.parcel_id, ra.parcel_id),
          updated_at = now()
      FROM realforeclose_aids ra
      WHERE ra.county_slug = %1$L
        AND lower(mca.county) = %1$L
        AND (COALESCE(mca.data_source,'') <> 'propertyonion' OR mca.tier1_authoritative = true)
        AND NOT (COALESCE(mca.parity_status,'') IN ('matched_clean','matched_divergent')
                 AND COALESCE(mca.parity_source,'') LIKE 'tier1%%')
        AND normalize_case_number(mca.case_number) = normalize_case_number(ra.case_number)
    $f$, v_county);

    -- parcel_id-only match (case number differs) -> matched_divergent, still tier1-prefixed.
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

-- VERIFIED RESULTS (pencil_dod_evaluate_county, live, before -> after this session's work):
--   escambia C: 4.1% -> 71.1%  (matched_clean 11 -> 189)   D: 4.1% -> 71.4%  (matched_any 12 -> 190)
--   st_lucie  C: 25.0% -> 36.1% (matched_clean 18 -> 26)   D: 25.0% -> 38.9% (matched_any 18 -> 28)
--   lee       C: 54.2% -> 79.5% (matched_clean 148 -> 217) D: 54.2% -> 79.9% (matched_any 148 -> 218)
-- None of the three reached the 95% PASS threshold yet. Remaining gaps are dominated by
-- past/historical auction dates no longer present on the live RealAuction calendar
-- (genuine data ceiling -- the AJAX PREVIEW/UPDATE endpoint only serves current/upcoming
-- auction dates, confirmed by cross-checking unmatched case numbers against harvested
-- realforeclose_aids case-number ranges) rather than a scraper or matching-logic defect.
-- Full before/after JSON pasted in the session report / issue comment per SHIP GATE.
