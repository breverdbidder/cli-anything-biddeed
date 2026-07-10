-- SHARD-11 (clay, okeechobee, alachua, gadsden), Gold Standard daily session run 3025
-- dispatch_id: 18aeb9b9-8281-4991-aa6c-f5e4422d0c6d
-- Session: architect-20260704T160000
--
-- APPLIED LIVE via Supabase Management API SQL endpoint 2026-07-05 (this file is the
-- post-hoc idempotent record, per this campaign's established practice -- all statements
-- below are guarded by case_number IN (...) and a NOT-already-labeled predicate, safe to
-- re-run).
--
-- ══════════════════════════════════════════════════════════════════════════════
-- CLAY C/D: 18.5% -> 100.0% (8/10 -> 10/10, real gain -- clay is now full PASS)
-- ══════════════════════════════════════════════════════════════════════════════
-- ROOT CAUSE (CONFIRMED live via `select parity_status, parity_source, count(*) ...
-- group by 1,2`): 88 of clay's 108 auction rows had NEVER been compared against any
-- independent tier1 source -- 50 carried parity_status='mca_only'/parity_source=NULL
-- (an honest never-touched gap, not a mislabel), and a further 33 carried
-- parity_status IN ('matched_clean','matched_divergent') against
-- parity_source='propertyonion_litmus_source_not_tier1_shard8_20260702' -- correctly
-- excluded by the evaluator's `parity_source LIKE ''tier1%%''` filter since a
-- PropertyOnion-litmus comparison is not an independent tier1 source per canon (HARD
-- GUARDRAIL #1). This is NOT the ghost-success pattern this campaign has repeatedly had
-- to revert (see 20260703_shard10b_clay_ghost_success_fix_..., 20260704051404_clay_
-- tier1_only_to_matched_clean_reclass.sql) -- no relabeling of PropertyOnion-derived
-- matches occurred here; every row below was independently re-verified live this
-- session against the RealAuction (RealForeclose/RealTaxDeed) AJAX calendar itself.
--
-- METHOD: scripts/shard_gs_clay_okeechobee_cd_parity.py -- a corrected reuse of
-- scripts/shard2_run2450_ajax_realforeclose_harvest.py's harvest_date() (direct AJAX
-- fetch against the live RealAuction calendar, the same platform clay/okeechobee are
-- hosted on per pipeline.counties, confirmed live) plus
-- scripts/shard9_run3059_citrus_manatee_cd_parity.py's exact-case-number-match-and-
-- promote pattern, FIXED for the known continuance-date defect that script's own
-- docstring and the 20260705_shard11_run2820_..._cd_parity.sql migration both flag (a
-- case appearing on multiple historical calendar dates could get its parity_source
-- stamped with the WRONG date): this version scopes the match query to
-- (county, auction_date) instead of the whole county, so every promoted
-- parity_source date is the row's own real auction_date.
--
-- Ran against all 22 distinct (sale_type, auction_date) targets covering clay's 88
-- unmatched rows; 88 of 88 found an exact case_number match on the live calendar for
-- their own auction_date and were promoted to matched_clean. Full script output and
-- ULTRALOOP adversarial refuter results (3 independent refuters, one per ~15-row
-- sample, 45 of 88 clay rows + all 9 promoted okeechobee rows live-refetched) are in
-- the session's closing report.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('clay'):
--   BEFORE: C matched_clean=20  (18.5%%) FAIL | D matched_any=20  (18.5%%) FAIL
--   AFTER:  C matched_clean=108 (100.0%%) PASS | D matched_any=108 (100.0%%) PASS
-- clay is now 10/10 on every letter (A,B,C,D,E,F,G,H,I,J all PASS).
--
-- ══════════════════════════════════════════════════════════════════════════════
-- OKEECHOBEE C/D: D now PASS (70.0%% -> 100.0%%); C real gain but still FAIL (50.0%% ->
-- 80.0%%, 24 of 30 -- 6 rows remain genuine matched_divergent, not a coverage gap)
-- ══════════════════════════════════════════════════════════════════════════════
-- Same method as clay, run against okeechobee's 7 remaining foreclosure-side gap
-- targets (all promoted) plus 1 tax_deed date (2026-04-09) that returned 0 items from
-- realtaxdeed.com -- CONFIRMED live (pipeline.counties.taxdeed_platform is NULL for
-- okeechobee, not realtaxdeed) that okeechobee tax deeds are not actually on that
-- platform. The 2 remaining okeechobee TD rows (2026TD031, 2026TD033) were instead
-- independently re-verified via scripts/shard9_okeechobee_taxsmartweb_litmus.py's
-- fetch_taxsmartweb_case() against the Okeechobee Clerk's own TaxSmartWebLive system
-- (the county's already-proven TD litmus source, reused verbatim, same label format
-- as the prior shard9 session) -- both matched_clean, no divergence.
--
-- The remaining 6 okeechobee rows blocking C are already parity_source LIKE 'tier1%%'
-- (tier1_clerk_supp_shard5_run651) but parity_status='matched_divergent': a genuine,
-- previously-recorded status/date divergence (our row shows "upcoming" for an
-- auction_date now in the past while the litmus comparison recorded "Sold"/a different
-- date). INVESTIGATED this session: re-fetched the live RealForeclose PREVIEW/UPDATE
-- calendar for all 6 dates -- confirmed the cases still list on the PREVIEW calendar
-- (a pre-sale endpoint) but that endpoint carries no post-sale result/status field, so
-- it cannot resolve the divergence either way. NOT reclassified (would require a
-- RealAuction RESULTS-page or clerk-recorded-sale source this session did not build) --
-- left honestly FAIL rather than guessed. NO ACTION on these 6.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('okeechobee'):
--   BEFORE: C matched_clean=15 (50.0%%) FAIL | D matched_any=21 (70.0%%) FAIL
--   AFTER:  C matched_clean=24 (80.0%%) FAIL | D matched_any=30 (100.0%%) PASS
-- okeechobee is now 9/10 (only C remains FAIL; A,B,D,E,F,G,H,I,J all PASS).
--
-- ══════════════════════════════════════════════════════════════════════════════
-- ALACHUA and GADSDEN: investigated this session, no data fix applied (honest, see
-- closing report for full reasoning) --
--   alachua E/I: 3 of 40 rows have no usable parcel_id -- CONFIRMED live via the
--     RealForeclose AJAX harvester itself that the live calendar lists these 3 cases'
--     parcel field as "MULTIPLE PARCEL" / "Property Appraiser" (a link label, not a
--     real ID) with no property address -- a structural source gap, not a lookup
--     failure. A further 4 rows have a real parcel_id not present in
--     v_zoning_gold_standard_card (fleet-wide zoning-ingestion gap, out of an
--     auction-pipeline session's scope per the G/I playbook). NO ACTION (no guessing).
--   gadsden B/F/C/D: CONFIRMED unchanged from the 2026-07-02 shard-8 bootstrap's
--     explicit, reasoned refusal (scripts/shard8_gadsden_bootstrap.py) -- all 23
--     auctions are foreclosure-calendar/tax-deed NOTICES with zero post-sale results
--     available from gadsdenclerk.com (re-fetched this session, confirmed no status/
--     sold-price column exists even for the one auction_date now in the past), and
--     gadsdenclerk.com is the auctions' OWN ingestion source -- using it as its own
--     litmus would be circular ghost-success, which this session also refuses to do.
--     gadsden E is unchanged at 73.9%% (73.9%% ceiling from the 2026-07-04
--     20260704_shard11_gadsden_e_parcel_linkage.sql migration already in main -- the
--     remaining 6 rows are legal-description-only, not address-matchable). NO ACTION.
--
-- ══════════════════════════════════════════════════════════════════════════════
-- FINAL STATE (live pencil_dod_evaluate_county, 2026-07-05, this session):
--   clay:       10/10 PASS (was 8/10: C 18.5%%->100.0%%, D 18.5%%->100.0%%)
--   okeechobee:  9/10 (was 8/10: D 70.0%%->100.0%% now PASS; C 50.0%%->80.0%% real
--                gain, still FAIL)
--   alachua:     6/10 unchanged (investigated, no fixable gap found this session)
--   gadsden:     4/10 unchanged (investigated, confirmed prior honest ceiling holds)
--
-- VERIFICATION QUERIES (run after apply):
-- SELECT public.pencil_dod_evaluate_county('clay');
-- SELECT public.pencil_dod_evaluate_county('okeechobee');
-- SELECT public.pencil_dod_evaluate_county('alachua');
-- SELECT public.pencil_dod_evaluate_county('gadsden');

SET statement_timeout = 0;

-- clay: 6 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-09
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-09',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2023CA001623',
    '2024CA000127',
    '2025CA000119',
    '2025CA000514',
    '2025CA000668',
    '2025CA000750'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-09%');

-- clay: 5 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-11
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-11',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2024CA000157',
    '2024CA000275',
    '2025CA000288',
    '2025CA000304',
    '2025CA000507'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-11%');

-- clay: 2 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-18
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-18',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2024CA000906',
    '2025CA000434'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-18%');

-- clay: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-25
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-25',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2024CA000355'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-25%');

-- clay: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-30
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-30',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025CA000831'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-30%');

-- clay: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-04-01
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-04-01',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025CA000090'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-04-01%');

-- clay: 4 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-04-08
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-04-08',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2024CA000041',
    '2024CA000576',
    '2024CA000824',
    '2025CC001159'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-04-08%');

-- clay: 5 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-06
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-06',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2023CA000056',
    '2023CA001090',
    '2023CA001125',
    '2024CA000844',
    '2025CA000572'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-06%');

-- clay: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-13
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-13',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2023CA001056'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-13%');

-- clay: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-21
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-21',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025CA000727'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-21%');

-- clay: 3 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-03
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-03',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2023CA001336',
    '2024CA000682',
    '2025CA000858'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-03%');

-- clay: 4 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-10
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-10',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2023CA001019',
    '2024CA001140',
    '2025CA000721',
    '2026CC000123'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-10%');

-- clay: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-25
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-25',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025CA000739'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-06-25%');

-- clay: 8 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-01
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-01',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2024CA000001',
    '2024CA000459',
    '2024CC001395',
    '2025CA000259',
    '2025CA000545',
    '2025CA000974',
    '2025CA000999',
    '2025CC001656'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-01%');

-- clay: 7 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-09
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-09',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2022CA000673',
    '2024CA000613',
    '2025CA000475',
    '2025CA000759',
    '2025CA000843',
    '2025CA000977',
    '2025CA000994'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-09%');

-- clay: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-14
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-14',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2024CA000425'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-14%');

-- clay: 4 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-15
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-15',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025CA000658',
    '2025CA001157',
    '2025CA001210',
    '2025CC001490'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-15%');

-- clay: 4 case(s), source=tier1:shard_gs_20260705_ajax_harvest:tax_deed:2025-12-17
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2025-12-17',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025-0073TD',
    '2025-0082TD',
    '2025-0087TD',
    '2025-0108TD'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2025-12-17%');

-- clay: 3 case(s), source=tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-01-14
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-01-14',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025-0085TD',
    '2025-0095TD',
    '2025-0097TD'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-01-14%');

-- clay: 5 case(s), source=tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-01-28
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-01-28',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2025-0071TD',
    '2025-0089TD',
    '2025-0090TD',
    '2025-0098TD',
    '2025-0114TD'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-01-28%');

-- clay: 10 case(s), source=tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-08-19
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-08-19',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2026-0029TD',
    '2026-0030TD',
    '2026-0031TD',
    '2026-0036TD',
    '2026-0041TD',
    '2026-0043TD',
    '2026-0045TD',
    '2026-0051TD',
    '2026-0053TD',
    '2026-0054TD'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-08-19%');

-- clay: 11 case(s), source=tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-09-02
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-09-02',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'clay'
  AND case_number IN (
    '2026-0032TD',
    '2026-0033TD',
    '2026-0034TD',
    '2026-0038TD',
    '2026-0039TD',
    '2026-0044TD',
    '2026-0046TD',
    '2026-0048TD',
    '2026-0049TD',
    '2026-0050TD',
    '2026-0052TD'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:tax_deed:2026-09-02%');

-- okeechobee: 2 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-11
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-11',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN (
    '472025CA000045CAAXMX',
    '472025CA000112CAAXMX'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-03-11%');

-- okeechobee: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-06
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-06',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN (
    '472024CA000208CAAXMX'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-06%');

-- okeechobee: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-20
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-20',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN (
    '472025CA000225CAAXMX'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-05-20%');

-- okeechobee: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-08
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-08',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN (
    '472025CA000171CAAXMX'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-08%');

-- okeechobee: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-22
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-22',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN (
    '472025CC000239CCAXMX'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-07-22%');

-- okeechobee: 1 case(s), source=tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-08-19
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-08-19',
    parity_checked_at = now(), updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN (
    '472025CA000130CAAXMX'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1:shard_gs_20260705_ajax_harvest:foreclosure:2026-08-19%');

-- ══════════════════════════════════════════════════════════════════════════════
-- OKEECHOBEE tax_deed: 2026TD031 + 2026TD033 via TaxSmartWebLive (applied live via
-- scripts/shard9_okeechobee_taxsmartweb_litmus.py okeechobee 2026TD033 2026TD031;
-- both REDEEMED status, no divergence vs our data -- recorded here for completeness)
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_okeechobee_taxsmartweb_clerk_shard9:2026-07-02',
    parity_checked_at = now(), tier1_verified_at = now(), tier1_authoritative = true,
    parity_confidence = 1.0, updated_at = now()
WHERE lower(county) = 'okeechobee'
  AND case_number IN ('2026TD031', '2026TD033')
  AND (parity_status IS DISTINCT FROM 'matched_clean' OR parity_source NOT LIKE 'tier1_okeechobee_taxsmartweb%');
