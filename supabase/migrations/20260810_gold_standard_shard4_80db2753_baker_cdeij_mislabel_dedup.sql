-- Gold Standard shard-4 baker (dispatch 80db2753-d593-429f-bae8-e1c57b14bd41)
-- Root cause (VERIFIED live 2026-08-10): calendar_sweep_mca_v3 wrote TWO rows for
-- 7 baker foreclosure case numbers -- one correctly typed
-- (sale_type='foreclosure') and one mislabeled (sale_type='tax_deed',
-- source_platform='realtaxdeed') carrying the SAME 'CAAXMX' circuit-civil case
-- number. Baker's genuine tax deed cases carry a 'TDAXMX' suffix (confirmed by
-- the one legitimate tax-deed row: 022026XX000002TDAXMX). None of the 7
-- mislabeled duplicate rows have a TD-suffixed case number, so none are a real
-- second sale event -- they inflate pencil_dod_evaluate_county's per-row
-- denominator (auctions_total) for C/D/E/I/J without representing a second
-- real auction.
--
-- FK safety verified before writing this migration: none of the 7 target row
-- ids are referenced by auction_enrichment_queue.auction_id,
-- auction_schedule_history.auction_id, court_case_metadata.mca_id,
-- po_mca_matches.mca_id, or shapira_outcome_scorecard.mca_id (all zero-count).
-- bid_decisions/tax_deed_outcomes/foreclosure_outcomes key by case_number, not
-- row id, so removing the duplicate row leaves the case's outcome/decision
-- rows intact via the surviving canonical row.
--
-- Effect: auctions_total 17 -> 10 (matches the true count of 10 distinct
-- baker case numbers). This is a denominator-honesty fix, not a numerator
-- fabrication -- verify live before/after via
-- SELECT public.pencil_dod_evaluate_county('baker');

BEGIN;

DELETE FROM public.multi_county_auctions
WHERE id IN (
  '8609a5d3-7901-4c18-b0fa-dea8f22b0625', -- 022025CA000038CAAXMX mislabeled tax_deed dup (real row: 4528da0c, foreclosure/realforeclose)
  '45168366-215d-4bb5-8d39-a6bd3f4ea4fd', -- 022025CA000108CAAXMX mislabeled tax_deed dup (real row: d7c9bcb1, foreclosure/realforeclose)
  'e96320d2-9954-4b45-9e4f-6a010bcd3641', -- 022025CA000117CAAXMX mislabeled tax_deed dup (real row: 3a24573f, foreclosure)
  '510a2b07-058b-42e4-8b57-31bb09e135c6', -- 022025CA000124CAAXMX mislabeled tax_deed dup (real row: 2305e9f7, foreclosure)
  '68f47751-18e4-477f-a88a-068aedfc09c1', -- 022025CA000148CAAXMX mislabeled tax_deed dup (real row: a0006bbb, foreclosure/realforeclose)
  '0046c625-b09d-45f9-82d4-8525afa9f2ce', -- 022026CA000007CAAXMX mislabeled tax_deed dup (real row: 1e6e8282, foreclosure/realforeclose)
  'ba830663-c3ff-43f4-8c80-1e0825c3e7a6'  -- 022026CA000018CAAXMX mislabeled tax_deed dup (real row: ed847934, foreclosure/realforeclose)
)
AND county = 'baker';

COMMIT;
