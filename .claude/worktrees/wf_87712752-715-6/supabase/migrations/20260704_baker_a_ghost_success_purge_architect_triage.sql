-- ARCHITECT TRIAGE (issue #10157, dispatch a9e6feb9-f30a-4098-bd85-df7cf12e9736)
-- 2026-07-04: baker A-criterion ghost-success purge
--
-- FINDING: baker's live pencil_dod_evaluate_county() reported 10/10 (A: fc=1 td=1), but the
-- "foreclosure" record was a fabricated duplicate of baker's single genuine tax_deed case
-- (022026XX000002TDAXMX) -- identical auction_date, address, winning_bid=78000.0. baker's
-- county_auction_config.fc_method='in_person' with no fc_url/fc_calendar, so no scraper could
-- have produced an independent foreclosure record. This also explains why baker's earlier
-- first_certified_at=2026-06-25 certification was revoked 2026-07-02 (same timestamp as
-- holmes' revocation -- a bulk V6-gate-tightening sweep): the original cert was likely never
-- honest.
--
-- FIX: delete the 3 fabricated rows (idempotent -- safe to re-run if already gone).
-- RESULT: pencil_dod_evaluate_county('baker') now honestly returns 9/10 (only A fails: fc=0 td=1).

DELETE FROM public.multi_county_auctions
WHERE id = '5f7c7c0a-ba2d-4f0a-bf6a-5c7a755b3267'
  AND county = 'baker'
  AND case_number = '022026XX000002TDAXMX'
  AND sale_type = 'foreclosure';

DELETE FROM public.foreclosure_outcomes
WHERE id = 'efa0df48-555e-49c1-8220-586cc873e633'
  AND county = 'baker'
  AND case_number = '022026XX000002TDAXMX';

DELETE FROM public.bid_decisions
WHERE id = 17503
  AND county_slug = 'baker'
  AND case_number = '022026XX000002TDAXMX';

-- Ultraloop audit row documenting the refutation (already inserted live via Management API
-- during this session as id 3413; this INSERT is the idempotent repo-record of that same row).
INSERT INTO public.gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
SELECT
  'a9e6feb9-f30a-4098-bd85-df7cf12e9736', 'fallback', 'baker', 'A',
  'REFUTED prior apparent A PASS (fc=1 td=1) -- fabricated duplicate foreclosure record purged; '
  'honest re-eval is fc=0 td=1, FAILS',
  jsonb_build_object(
    'honesty_marker', 'CONFIRMED',
    'method', 'cross-table diff on case_number=022026XX000002TDAXMX',
    'county_auction_config_fc_method', 'in_person',
    'rows_deleted', jsonb_build_array(
      'multi_county_auctions:5f7c7c0a-ba2d-4f0a-bf6a-5c7a755b3267',
      'foreclosure_outcomes:efa0df48-555e-49c1-8220-586cc873e633',
      'bid_decisions:17503'
    ),
    'honest_reeval', jsonb_build_object('A', jsonb_build_object('pass', false, 'metric', 0, 'detail', 'fc=0 td=1'))
  ),
  false
WHERE NOT EXISTS (
  SELECT 1 FROM public.gold_standard_ultraloop_audit
  WHERE dispatch_id = 'a9e6feb9-f30a-4098-bd85-df7cf12e9736'
    AND county_slug = 'baker' AND letter = 'A'
);

-- SQL VERIFICATION (run after applying)
-- SELECT public.pencil_dod_evaluate_county('baker');
--   Expected: 9/10, only "A" pass=false (fc=0 td=1)
-- SELECT EXISTS (SELECT 1 FROM public.gold_standard_certifications
--   WHERE county_slug = ANY('{baker,escambia,st_lucie,holmes,hamilton}'::text[]) AND certified);
--   Expected: false (DoD still not met -- baker needs one real foreclosure record; see BLOCKED
--   comment on issue #10157)
