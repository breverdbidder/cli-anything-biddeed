-- HIGHLANDS C/D: ghost-row purge (denominator honesty) + NULL-parity live-harvest
-- investigation. No matched_clean rows added -- gap is real, not fabricated.
--
-- CONTEXT: task asked to move highlands C/D (>=95% matched_clean required, 170/179)
-- off the 147/179 (82.1%) baseline. Two independent sub-investigations:
--
-- 1. GHOST ROWS (case_number HIGHLANDS-FC-2026-001/002, parity_status='bootstrap_placeholder'):
--    Confirmed synthetic -- property_address literally 'TBD HIGHLANDS FL', opening_bid
--    NULL, data_source 'realforeclose:shard5-highlands-fc-v1' (a seed/bootstrap label
--    not used by any real scraper elsewhere in the county), no foreclosure_outcomes /
--    tax_deed_outcomes rows attached. This is the EXACT same signature already
--    identified and deleted once before by migration
--    20260702_shard6_calhoun_monroe_sumter_highlands_synthetic_bootstrap_cleanup.sql
--    (created_at then was pre-2026-07-02; these 2 rows have created_at=2026-07-03,
--    i.e. they were RE-INSERTED by a bootstrap/seed job after that cleanup ran).
--    DELETED again here -- shrinks the honest denominator from 179 to 177, matching
--    prior-session precedent and CLAUDE.md HARD GUARDRAILS ghost-purge policy.
--    No outcome-table rows existed to clean up (verified via SELECT before delete).
--
-- 2. 30 NULL-parity rows (data_source='calendar_sweep_mca_v3', sale_type=tax_deed,
--    auction_date in {2026-08-05, 2026-08-12, 2026-08-19}, case_number range
--    25000685-25000743): real-looking rows (real Sebring/Lake Placid addresses, real
--    opening bids, real STRAP-style parcel data) -- NOT synthetic. Attempted live
--    parity match via scripts/shard2_run2450_ajax_realforeclose_harvest.py's
--    harvest_date() against highlands.realtaxdeed.com for all 3 exact auction dates
--    (both AREA=W and AREA=C, fully paginated). The harvester is PROVEN correct for
--    this county/date range: it independently re-derived the exact case-number set
--    that is already parity_status='matched_clean' for 2026-08-19 (e.g. 25000725,
--    25000667, 25000729, 25000728, 25000680, 25000732, 25000659, 25000708, 25000733,
--    25000679, 25000758, 25000756, 25000731, 25000734, 25000727 all appeared in the
--    live 29-item harvest AND already carry parity_source
--    'tier1:shard4_run3059_2nd_pass_ajax_harvest:...'). Also checked 4 adjacent dates
--    (07/22, 07/29, 08/26, 09/02/2026) for a reschedule -- no hits.
--    RESULT: zero of the 30 case numbers appear on the live RealAuction calendar for
--    their claimed dates or any nearby date. This is an HONEST GAP, not a scraper
--    defect -- calendar_sweep_mca_v3 ingested these case numbers from a source that is
--    currently ahead of / divergent from what RealAuction's own AJAX calendar
--    publishes for 2026-08-05/12/19. NO writes made to these 30 rows. parity_status
--    left NULL. Fabricating a matched_clean here would violate the HONESTY PROTOCOL
--    ("a fabricated match is worse than leaving it NULL").
--
-- VERIFIED via pencil_dod_evaluate_county BEFORE (2026-07-11, this session):
--   highlands: auctions_total=179  C fail(matched_clean=147, 82.1)  D fail(matched_any=147, 82.1)
-- VERIFIED via pencil_dod_evaluate_county AFTER (2026-07-11, this session, post-delete):
--   highlands: auctions_total=177  C fail(matched_clean=147, 83.1)  D fail(matched_any=147, 83.1)
--   (147/177 = 83.1%, still below the 95%/170-of-179(now 168-of-177) gate -- NOT SHIPPED,
--   reported as an honest residual, see session report)
--
-- OUT OF SCOPE: no other county touched. No cron/gold_standard_loop() invoked.

BEGIN;

DELETE FROM foreclosure_outcomes
 WHERE lower(county) = 'highlands'
   AND case_number IN ('HIGHLANDS-FC-2026-001','HIGHLANDS-FC-2026-002');

DELETE FROM tax_deed_outcomes
 WHERE lower(county) = 'highlands'
   AND case_number IN ('HIGHLANDS-FC-2026-001','HIGHLANDS-FC-2026-002');

DELETE FROM multi_county_auctions
 WHERE lower(county) = 'highlands'
   AND case_number IN ('HIGHLANDS-FC-2026-001','HIGHLANDS-FC-2026-002');

-- NOTE: no gold_standard_ultraloop_audit row inserted here -- that table's dispatch_id
-- column is a live FK into summit_chat_dispatch (verified this session), so an
-- ad-hoc/manual session has no valid dispatch_id to attach. The evidence trail for
-- this fix lives in this migration's header comment + the session report instead.

COMMIT;
