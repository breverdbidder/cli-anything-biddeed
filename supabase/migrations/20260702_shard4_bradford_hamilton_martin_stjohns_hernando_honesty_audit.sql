-- SHARD-4 (Gold Standard, dispatch_id 1ea48950-c02a-4f2e-9b65-8c7e8c31b025, session
-- architect-20260702T160000): bradford, hamilton, martin, st_johns, hernando.
--
-- This is an idempotent RECORD of live PATCH operations already applied via the
-- Supabase PostgREST API during this session. Re-running is safe (all statements
-- are guarded so they only touch rows already known by id/case_number).
--
-- METHOD: ran a Workflow (ultracode) that fanned one diagnostic subagent per county
-- to investigate C/D root cause against the LIVE pencil_dod_evaluate_county formula
-- (supabase/migrations/20260702_shard1_pencil_dod_cd_tier1_filter.sql -- matched_clean/
-- matched_any require parity_status set AND parity_source LIKE 'tier1%', i.e. a genuine
-- independent cross-source match, not mere parcel/case presence). Result: ZERO fixes
-- were proposed for ANY of the 5 counties -- every C/D failure traced to either an
-- honest absence of independent data (hernando) or fabricated/mislabeled data from
-- prior sessions (bradford, hamilton, martin = SEVERE; st_johns = PARTIAL). Two of
-- those findings were independently re-verified by the main loop (not just trusted
-- from the subagent) and corrected below. The rest are documented, not fixed --
-- BLANK > WRONG.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- BRADFORD: NO FIX. All 3 multi_county_auctions rows are synthetic bootstrap
-- placeholders from scripts/shard5_bradford_wakulla_bootstrap.py's build_placeholder_
-- rows() (used when the real RealForeclose/RealTaxDeed scrape returned nothing):
-- case numbers BRADFORD-FC-2026-001 / BRA-FC-2026-001 / BRA-TD-2026-001, parcel_ids
-- BRADFORD-PARCEL-0001/2/3, identical opening_bid=999.99, templated addresses, and
-- sold_amount==tier1_sold_amount on every row (self-referential, not independent).
-- Live-fetched confirmation this session: bradford.realforeclose.com and
-- bradford.realtaxdeed.com both 302 to the generic realauction.com homepage (no active
-- tenant); bradford.realtdm.com is a login-gated "TEST"/"Test Clerk" demo shell, not
-- live data. No honest replacement source is currently reachable. A prior fix attempt
-- (scripts/shard7_run1113_bradford_cd_parity.py) tried to force matched_clean/
-- matched_any via parcel_id+address presence alone -- exactly the E-disguised-as-C/D
-- ghost-success pattern 20260702_shard1_pencil_dod_cd_tier1_filter.sql exists to catch;
-- live data shows it did not stick (parity_status='mca_only' on all 3 rows already).
-- RECOMMENDATION (not executed): quarantine/flag these 3 rows as fabricated in a future
-- session (same class as today's okeechobee/polk/liberty/franklin/marion fabrication-
-- revert migrations), or leave C/D honestly FAIL pending a real Bradford Clerk source.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- HAMILTON: FIX APPLIED. All 10 TD-HAM-CERT* rows carried a flat sold_amount=
-- tier1_sold_amount=$5000.00 (traced to migration 20260627_shard9_run1113_madison_
-- flagler_hamilton.sql Section 8a: sold_amount = COALESCE(opening_bid, 5000), a
-- hardcoded placeholder default, not a scrape). Independently re-fetched
-- https://hamiltonclerk.com/tax-deeds/ live this session (main loop, not just the
-- diagnosing subagent) and cross-checked by parcel number: NONE of the 10 real
-- per-cert opening-bid amounts is $5000 (they range $973.44-$9,652.42), and 7 of 10
-- certs are marked REDEEMED on the clerk's own page (no sale ever occurred), yet the
-- DB had auction_status='sold' for all 10. BONUS FINDING (not corrected here, flagged
-- for a future session): the DB's parcel_id per cert is offset by one position versus
-- the clerk page's cert order (e.g. DB's CERT230 parcel 3139-160 = clerk's Cert 99
-- parcel; DB's CERT344 parcel 3599-198 = clerk's Cert 230 parcel) -- a row-misalignment
-- bug of the same class as 20260702_shard1b_manatee_row_misalignment_correction.sql.
-- Not auto-corrected here because the inferred remap is not independently confirmed to
-- the same certainty as the amount/status fabrication.
--
-- FIX: null out the fabricated sold_amount/tier1_sold_amount/sold_amount_source and
-- revert parity_status/parity_source to honest "no independent match" state for all 10
-- rows (opening bid is not the same as a winning/sold amount, so we do not backfill the
-- real opening-bid figures as sold_amount either -- that would just be a different
-- unverified number). Separately correct auction_status to 'redeemed' for the 7
-- confirmed-redeemed certs.
UPDATE multi_county_auctions
SET sold_amount = NULL,
    tier1_sold_amount = NULL,
    sold_amount_source = NULL,
    parity_status = 'mca_only',
    parity_source = 'unverified_fabricated_amount_reverted_shard4_20260702',
    parity_checked_at = now(),
    updated_at = now()
WHERE lower(county) = 'hamilton'
  AND case_number IN (
    'TD-HAM-CERT99','TD-HAM-CERT230','TD-HAM-CERT344','TD-HAM-CERT379','TD-HAM-CERT467',
    'TD-HAM-CERT557','TD-HAM-CERT559','TD-HAM-CERT597','TD-HAM-CERT599','TD-HAM-CERT688'
  )
  AND sold_amount = 5000.0 AND tier1_sold_amount = 5000.0; -- guard: only touch rows still at the fabricated value

UPDATE multi_county_auctions
SET auction_status = 'redeemed', updated_at = now()
WHERE lower(county) = 'hamilton'
  AND case_number IN ('TD-HAM-CERT99','TD-HAM-CERT230','TD-HAM-CERT344','TD-HAM-CERT467','TD-HAM-CERT557','TD-HAM-CERT559','TD-HAM-CERT688')
  AND auction_status = 'sold'; -- guard: only touch rows still incorrectly marked sold

-- VERIFIED live before/after via pencil_dod_evaluate_county('hamilton'):
--   BEFORE: C 47.6% FAIL | D 47.6% FAIL | B 100.0% (verified=13 closed_sold=13) PASS | F 100.0% (13/13) PASS
--   AFTER:  C 0.0% FAIL  | D 0.0% FAIL  | B 100.0% (verified=3 closed_sold=3) PASS  | F 100.0% (3/3) PASS
-- C/D honestly WORSE (matches today's shard8-clay precedent: correcting a false label
-- can legitimately reduce a metric -- this is the correct outcome, not a bug). B/F
-- remain PASS but on a much smaller, defensible base (the 3 real FC judgment-amount
-- rows scraped honestly by the original scripts/shard_hamilton_bootstrap.py, unrelated
-- to the TD fabrication) instead of a circular 13/13 built from the same fabricated
-- default in one transaction.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- MARTIN: NO FIX. All 29 rows' tier1-prefixed parity_source traces to presence/format-
-- based bulk UPDATEs (scripts/shard12_run1113_martin_fix.py phase_cd: "All 28 martin
-- cases are from court records -> matched_clean", zero external fetch) or a pure
-- string-rename (20260628_parity_source_tier1_prefix_17counties.sql), never an actual
-- cross-source comparison. The one supporting foreclosure_outcomes row (case
-- 25001123CAAXMX) is self-tagged data_source='...HYPOTHESIS' with a source_url that
-- 404s; scripts/shard6_verified_outcomes.py's CLERK_ENDPOINTS['martin'] base_url
-- (or.martin.fl.us) is NXDOMAIN -- the intended independent-source hostname does not
-- exist. This also taints B/F (currently false-PASS on this same single row) -- flagged
-- for follow-up, out of this migration's C/D scope. RECOMMENDATION (not executed):
-- revert parity_source/parity_status to an honest non-tier1 label following the
-- shard8-clay precedent (would make C/D worse, ~0% instead of 17.2%/44.8%), and replace
-- shard6_verified_outcomes.py's martin clerk endpoint before attempting any real fix.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- ST_JOHNS: FIX APPLIED. Two distinct ghost-success remnants found and corrected:
--  (1) 4 matched_clean rows (CA23-1271, CA24-1170, CA24-1501, CA24-1625) had zero
--      comparison evidence (parity_po_id NULL, parity_checked_at stamped exactly
--      2026-06-26T16:11:55, matching the already-reverted structural-rule migration
--      20260626_shard6_run651_all_counties.sql Section 2, self-labeled "honesty_marker:
--      INFERRED -- parity assigned by structural rule, not live comparison").
--  (2) 7 matched_divergent rows (CC24-1265, CA25-1169, CC24-2116, CA25-1481, CA25-0851,
--      CA22-0911, CC25-1235) carry REAL comparison evidence (parity_po_id set,
--      parity_confidence 0.85-0.98, parity_divergences populated with genuine
--      field-level diffs) but the compared-against source is PropertyOnion
--      (parity_po_id), and HARD GUARDRAIL #1 (PropertyOnion = litmus ONLY) forbids
--      labeling that as an independent tier1 match. parity_source was falsely
--      'tier1_platform_scrape'.
UPDATE multi_county_auctions
SET parity_status = 'mca_only',
    parity_source = 'unverified_structural_rule_reverted_shard4_20260702',
    parity_checked_at = now(),
    updated_at = now()
WHERE lower(county) = 'st_johns'
  AND case_number IN ('CA23-1271','CA24-1170','CA24-1501','CA24-1625')
  AND parity_status = 'matched_clean' AND parity_po_id IS NULL;

UPDATE multi_county_auctions
SET parity_source = 'propertyonion_litmus_compare_shard4_20260702', updated_at = now()
WHERE lower(county) = 'st_johns'
  AND case_number IN ('CC24-1265','CA25-1169','CC24-2116','CA25-1481','CA25-0851','CA22-0911','CC25-1235')
  AND parity_status = 'matched_divergent' AND parity_po_id IS NOT NULL
  AND parity_source = 'tier1_platform_scrape';

-- VERIFIED live before/after via pencil_dod_evaluate_county('st_johns'):
--   BEFORE: C 12.5% (4/32) FAIL | D 34.4% (11/32) FAIL
--   AFTER:  C 0.0% (0/32) FAIL  | D 0.0% (0/32) FAIL
-- Honestly WORSE, matching the shard8-clay precedent. E/I/B/F/G/H/J unaffected
-- (confirmed identical before/after: E 96.9%, I 96.9%, B 100.0%, F 100.0%).
-- Also noted, NOT touched by this migration: 3 rows (STJOHNS-TD-2026-001/002/003) show
-- the bootstrap-placeholder signature (sequential fake case numbers, sequential
-- parcel_ids 000{1,2,3}000000, no data_source, no trace in any tracked script) --
-- currently sitting honestly at parity_status='mca_only' so not corrupting C/D today,
-- but inflate the auctions_total denominator (32 vs a true 29) and should be quarantined
-- in a future session.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- HERNANDO: NO FIX -- and no fix needed. All 23 rows are honestly upcoming
-- (auction_date 2026-06-30 through 2026-07-28), zero rows in tax_deed_outcomes or
-- foreclosure_outcomes for hernando, so B/F correctly read null (no closed_sold
-- denominator) rather than a fabricated 0% or 100%. C/D's prior ghost-PASS
-- (100%/100% via E-linkage mislabeled as tier1) was ALREADY caught and honestly
-- reverted earlier today by 20260702_shard1_pencil_dod_cd_tier1_filter.sql -- current
-- 0%/0% is the correct honest state, not a regression to fix. hernando.realforeclose.com
-- and hernando.realtaxdeed.com both 403 (bot-blocked) to read-only curl/WebFetch this
-- session; hernandoclerk.com's public PDF page was confirmed (WebFetch) to contain only
-- forward-looking sale-date listings, not results -- no independent outcome source is
-- reachable read-only. E (87.0%) and I (43.5%) were already worked today by a
-- concurrent shard (20260702_shard7_hernando_e_i_h_parcel_fix.sql,
-- 20260702_shard7_hernando_e_i_taxsmart_countygis_fix.sql) and were correctly left
-- untouched by this migration per PARALLEL-FLEET RULES.
--
-- ══════════════════════════════════════════════════════════════════════════════════
-- ULTRALOOP AUDIT: 6 survival-vote rows logged to gold_standard_ultraloop_audit
-- (county_slug in bradford/hamilton/martin/st_johns/hernando, dispatch_id
-- 1ea48950-c02a-4f2e-9b65-8c7e8c31b025) documenting each finding and the concrete
-- evidence behind it, per the session's ULTRALOOP PROTOCOL certify-gate requirement.
--
-- VERIFICATION QUERIES (run after apply):
-- SELECT public.pencil_dod_evaluate_county('bradford');
-- SELECT public.pencil_dod_evaluate_county('hamilton');
-- SELECT public.pencil_dod_evaluate_county('martin');
-- SELECT public.pencil_dod_evaluate_county('st_johns');
-- SELECT public.pencil_dod_evaluate_county('hernando');
