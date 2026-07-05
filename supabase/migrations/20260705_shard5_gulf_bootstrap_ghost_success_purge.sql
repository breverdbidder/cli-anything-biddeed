-- SHARD-5 run3025 (baker/hillsborough/gulf/putnam/collier): gulf fixture contamination purge
-- dispatch_id: d9210c60-335b-4a88-a422-0afee09d472b
-- Session: architect-20260704T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-05 via Supabase Management API SQL against
-- multi_county_auctions, tax_deed_outcomes, foreclosure_outcomes for lower(county)='gulf'):
--
-- 1. FABRICATED AUCTION ROWS (6 rows, data_source='shard5_bootstrap'): case numbers
--    GULF-FC-2026-001/002/003 and GULF-TD-2026-001/002/003 do not match any real Florida
--    court case-number format (compare to gulf's genuine rows, e.g. "23-2024-CA-000097-CAAXMX").
--    All 6 have parity_status='mca_only', parity_source='tier1_clerk_court', sold_amount=NULL,
--    created_at clustered at 2026-06-19 11:14:30 (same-second batch insert -- a synthetic seed,
--    not a scrape). This is the same "shard5-loop472-seed fixture contamination" class already
--    identified and purged for holmes/union in commit f97c6b70. It was NOT yet cleaned for gulf.
--    Before this purge, these 6 rows supplied gulf's ENTIRE tax_deed side of criterion A
--    (td=3 metric) -- gulf's real (non-fabricated) rows are 100% foreclosure, ZERO tax_deed.
--    So gulf's live A=PASS (fc=13 td=3) was a ghost success entirely propped up by fixture rows.
--
-- 2. FABRICATED PARITY STAMPS on otherwise-real auction rows (5 rows, real case numbers,
--    data_source in (realforeclose, NULL)): parity_source values
--    'tier1:shard_gulf_run20260705_ajax_harvest:foreclosure:<date>' (4 rows, with fabricated
--    future auction dates embedded in the label -- 2026-07-23 and 2026-09-10 are after today,
--    2026-07-05) and 'tier1_matched_clean_bootstrap' (1 row). None of the 5 have sold_amount or
--    tier1_sold_amount populated, and none have a matching case_number in tax_deed_outcomes or
--    foreclosure_outcomes for gulf (checked by case_number, lower(county)='gulf'). These stamps
--    inflated matched_clean from the true 5 (genuinely tier1_foreclosure_outcome-backed, real
--    dollar sold amounts $87,500/$295,000/$62,000/$128,000/$215,000) to a false 10, i.e. C/D
--    read 62.5%% live instead of the honest 31.25%% (5 of 16) / 50%% (5 of 10 real auctions).
--    Both readings still FAIL the 95%% gate, so this did not flip a PASS, but it is a false
--    "verified" stamp sitting in the base table exactly like the putnam precedent
--    (20260705_shard5_run2753_putnam_cd_ghost_success_revert.sql) -- a data-integrity risk for
--    any future join/dashboard that doesn't share the evaluator's parity_source LIKE 'tier1%%'
--    AND real-outcome-backing assumption.
--
-- ADVERSARIAL CHECK PERFORMED: confirmed zero rows anywhere in tax_deed_outcomes or
-- foreclosure_outcomes for lower(county)='gulf' reference any of the 6 fabricated case numbers
-- or the 5 falsely-stamped case numbers. Confirmed the 5 genuinely tier1_foreclosure_outcome
-- rows are untouched by this migration (different parity_source, real sold_amount).
--
-- ACTION: delete the 6 fabricated auction rows outright (they are not real auctions -- keeping
-- them as NULL-parity placeholders would still corrupt A/E/G/I/J denominators). Null the
-- fabricated parity stamp on the 5 real-but-falsely-stamped rows so they honestly show as
-- unmatched pending real RealAuction/clerk verification (network egress to gulf.realforeclose.com
-- returned HTTP 403 from this sandbox this session -- live re-harvest deferred, UNTESTED).

BEGIN;

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'gulf'
   AND data_source = 'shard5_bootstrap'
   AND case_number ~ '^GULF-(FC|TD)-2026-[0-9]+$';

UPDATE multi_county_auctions
   SET parity_status     = NULL,
       parity_source     = NULL,
       parity_confidence = NULL,
       parity_checked_at = NULL,
       updated_at        = now()
 WHERE lower(county) = 'gulf'
   AND (parity_source LIKE 'tier1:shard_gulf_run20260705_ajax_harvest:%'
        OR parity_source = 'tier1_matched_clean_bootstrap');

INSERT INTO honesty_violations
  (id, domain, claim, tag_used, actual_truth, severity, session_source, corrective_action, resolved)
VALUES
  (gen_random_uuid(), 'GOLD_STANDARD_CAMPAIGN',
   'gulf criterion A passed live (fc=13 td=3) and C/D read 62.5%% (matched_clean=10 of 16)',
   'VERIFIED',
   '6 of gulf''s 16 in-scope multi_county_auctions rows were fabricated fixture data (data_source=shard5_bootstrap, non-Florida-format case numbers GULF-FC/TD-2026-00N, same-second batch insert 2026-06-19 11:14:30) supplying gulf''s entire tax_deed side of A. A separate 5 rows carried fabricated parity_source stamps (tier1:shard_gulf_run20260705_ajax_harvest:* with future auction dates, and tier1_matched_clean_bootstrap) with zero backing in tax_deed_outcomes/foreclosure_outcomes and no sold_amount. Gulf''s only real, outcome-backed matched_clean rows are 5 (tier1_foreclosure_outcome, real sold amounts). Real gulf auctions are 100%% foreclosure, 0%% tax_deed -- A genuinely fails once fixtures are removed.',
   'CRITICAL',
   'architect-20260704T160000 (dispatch d9210c60-335b-4a88-a422-0afee09d472b)',
   'Deleted the 6 fabricated shard5_bootstrap auction rows. Nulled parity_status/parity_source/parity_confidence/parity_checked_at on the 5 falsely-stamped real rows. See supabase/migrations/20260705_shard5_gulf_bootstrap_ghost_success_purge.sql.',
   true);

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('d9210c60-335b-4a88-a422-0afee09d472b', 'fallback', 'gulf', 'A',
   'gulf A passes with fc=13 td=3',
   '{"verdict":"CONFIRMED_GHOST_SUCCESS","evidence":"all 3 real-scoped td rows were data_source=shard5_bootstrap fixture inserts with non-FL-format case numbers (GULF-TD-2026-001/002/003); zero real gulf tax_deed auctions exist in multi_county_auctions; real fc rows total 10, real td rows total 0"}'::jsonb,
   false),
  ('d9210c60-335b-4a88-a422-0afee09d472b', 'fallback', 'gulf', 'C',
   'gulf C reads 62.5%% (matched_clean=10 of 16)',
   '{"verdict":"CONFIRMED_GHOST_SUCCESS_PARTIAL","evidence":"5 of the 10 matched_clean rows carried fabricated parity_source (tier1:shard_gulf_run20260705_ajax_harvest:* with future dates not yet occurred, or tier1_matched_clean_bootstrap) with sold_amount NULL and zero matching case_number in tax_deed_outcomes/foreclosure_outcomes; honest matched_clean=5, all real (tier1_foreclosure_outcome, real dollar sold amounts)"}'::jsonb,
   false),
  ('d9210c60-335b-4a88-a422-0afee09d472b', 'fallback', 'gulf', 'D',
   'same claim as C, for matched_any',
   '{"verdict":"CONFIRMED_GHOST_SUCCESS_PARTIAL","evidence":"same root cause as C"}'::jsonb,
   false);

COMMIT;
