-- Gold Standard shard-4 baker (dispatch 80db2753-d593-429f-bae8-e1c57b14bd41)
-- The mislabeled-duplicate bug fixed by 20260810_..._baker_cdeij_mislabel_dedup.sql
-- RECURRED live during this same session: a fresh sale_type='tax_deed',
-- source_platform='realtaxdeed' duplicate row for case 022025CA000148CAAXMX
-- appeared at 2026-08-10 16:15 UTC (id 3f121c21-ab3d-40f2-a95d-e3351e485698),
-- ~1h45m after the first cleanup. That timestamp does NOT match
-- calendar-sweep-dark-counties.yml's cron ('15 5 * * *' = 05:15 UTC), so this
-- was a manual workflow_dispatch -- almost certainly a concurrent shard
-- session's run, not this session's.
--
-- Root cause NOT fully confirmed. Live re-check this session (2026-08-10,
-- both baker.realtaxdeed.com and baker.realforeclose.com, AREA=W page 1)
-- shows the source card's own "Auction Type" field literally reads
-- "FORECLOSURE" for case 148 on both subdomains, and
-- .github/scripts/calendar_sweep_mca.py's current _resolve_sale_type() /
-- _SALE_TYPE_FIELD_MAP ('foreclosure' -> 'foreclosure') SHOULD therefore
-- resolve both lanes to the SAME on_conflict key (county,case_number,
-- sale_type) and merge into one row, not create a second. Why the actual
-- dispatched run diverged from this expectation is unresolved -- candidate
-- explanations not yet checked: (a) a matrix cell hit a different AREA/page
-- where the Auction Type field failed to parse and fell back to the job's
-- fixed SALE_TYPE env var, (b) version skew between the dispatched run's
-- checked-out commit and this session's HEAD. FK safety re-verified (zero
-- references in auction_enrichment_queue/auction_schedule_history/
-- court_case_metadata/po_mca_matches/shapira_outcome_scorecard) before this
-- delete, same as the original cleanup.
--
-- NEXT SESSION: do not re-guess a fix to calendar_sweep_mca.py or
-- calendar-sweep-dark-counties.yml without first capturing a live GHA run
-- log for a baker matrix cell to see which AREA/page/lane actually produced
-- the mislabeled row -- this migration is a stopgap, not a permanent fix.
-- If it keeps recurring, the durable fix is almost certainly in the scraper
-- itself (39 counties depend on that file -- do not touch it on a guess).

BEGIN;

DELETE FROM public.multi_county_auctions
WHERE id = '3f121c21-ab3d-40f2-a95d-e3351e485698'
  AND county = 'baker'
  AND case_number = '022025CA000148CAAXMX'
  AND sale_type = 'tax_deed';

COMMIT;
