-- issue #19729 T3: per-row error isolation for seller_digest enrichment.
--
-- winnerdata.seller_digest_leads.row_enrichment_status currently has no way
-- to distinguish "vendor answered, nobody found" (NO_MATCH, correctly
-- 'complete') from "vendor never answered / bad request after retries"
-- (a real gap -- the row must be retriable, not silently indistinguishable
-- from a genuine miss). Adds 'error' to the existing CHECK constraint.
-- Additive only -- no existing row's status value is touched.

begin;

alter table winnerdata.seller_digest_leads
  drop constraint if exists seller_digest_leads_row_enrichment_status_check;

alter table winnerdata.seller_digest_leads
  add constraint seller_digest_leads_row_enrichment_status_check
  check (row_enrichment_status in (
    'not_started', 'running', 'complete', 'failed', 'skipped_dnc_incomplete', 'error'
  ));

commit;
