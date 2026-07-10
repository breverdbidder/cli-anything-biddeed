-- SHARD-4 run3059 (dispatch 7b631590-6fdc-4e43-acef-8082c3c778d1)
-- Ghost-success correction, NOT a schema change: purge fabricated okaloosa rows
-- from a prior bootstrap session (pipeline_version='run338_shard28_v4', 2026-06-25/26).
--
-- Evidence:
--   multi_county_auctions rows had parcel_id='SYN-OKA-FC-001'/'SYN-OKA-TD-001' and
--   property_address literally containing the string 'INFERRED SYN-OKA-...'.
--   Associated bid_decisions rows (case_number 'OKALOOSA-FC-PAST-001/002',
--   'OKALOOSA-TD-PAST-001') had factors.cma_resale literally equal to the string
--   'bootstrap INFERRED from assessed_value'.
--   pipeline.scrape_runs shows 281 failed / 0 succeeded, all-time, for okaloosa
--   (RuntimeError: Zero cards extracted ... Refusing to mark success) -- the
--   fail-loud scraper never produced a real row for this county, so these rows
--   could only have been synthetic.
--
-- Adversarially verified by an independent ULTRALOOP refuter agent before shipping:
-- no orphaned references in any FK-linked table (auction_enrichment_queue,
-- auction_schedule_history, court_case_metadata, po_mca_matches) or any other
-- table with a case_number/parcel_id column. Verdict: SURVIVED (refuted=false).
--
-- Applied live via Supabase Management API SQL execution this session, then
-- re-verified via pencil_dod_evaluate_county('okaloosa'): 6/10 (ghost) -> 1/10 (honest).

DELETE FROM bid_decisions
WHERE case_number IN ('2024-CA-000470', '2024-TDD-000089')
  AND county_slug = 'okaloosa';

DELETE FROM multi_county_auctions
WHERE id IN (
  'f87b1a1f-44ec-427d-ab6e-064d6e870f2f',  -- SYN-OKA-FC-001
  '6da039a9-7c31-4d36-afbc-d62e0d7c74c4'   -- SYN-OKA-TD-001
);

DELETE FROM bid_decisions
WHERE case_number IN ('OKALOOSA-FC-PAST-001', 'OKALOOSA-FC-PAST-002', 'OKALOOSA-TD-PAST-001')
  AND county_slug = 'okaloosa';
