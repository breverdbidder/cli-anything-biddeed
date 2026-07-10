-- SHARD-1 (leon/okeechobee/broward/flagler/liberty) — dispatch aab9f1da-a0da-4a2d-a18c-63b1a4d938da
-- Session: architect-20260710T000000
--
-- Two small, VERIFIED, non-fabricating fixes applied live 2026-07-10 during shard audit.
-- No outcome/zoning/parcel data was invented (see session decision log for the
-- honesty audit of prior shard7_liberty_fixes.py / shard3_flagler_b_i_fix.py,
-- which used a banned ghost-success pattern and were NOT reused here).

-- 1) BROWARD A-lane: taxdeed_platform/url were NULL in pipeline.counties even
--    though public.realauction_subdomains already carries a live, verified
--    broward.realtaxdeed.com row (is_active=true, http_status=200). This wires
--    the discovered platform into the county config so the existing
--    biddeed.enqueue_realauction_sweep() sweep (which reads realauction_subdomains,
--    not pipeline.counties) continues to cover it, and downstream tooling that
--    DOES key off pipeline.counties.taxdeed_* now sees the real config.
--    NOTE: this does not itself create tax_deed rows -- Broward currently shows
--    po_lots_count=0 for tax_deed on PropertyOnion too, so it is plausible there
--    are genuinely few/no live listings right now. A-criterion for broward will
--    only flip once a real scrape lands td rows.
UPDATE pipeline.counties
SET taxdeed_platform = 'realtaxdeed',
    taxdeed_url = 'https://broward.realtaxdeed.com/index.cfm?zaction=USER&zmethod=CALENDAR'
WHERE county_slug = 'broward'
  AND taxdeed_platform IS NULL;

-- 2) OKEECHOBEE C-criterion: 6 rows were parity_status='matched_divergent'
--    against PropertyOnion with 0.85-0.98 confidence, where PO shows the case
--    as Sold/Canceled but our row still says auction_status='upcoming' for an
--    auction_date that has already passed (all 6 dates predate 2026-07-10).
--    This is a genuine staleness bug, not fabricated -- PO is used ONLY as the
--    signal that these need re-verification against the primary RealForeclose
--    source, per canon ("PropertyOnion = litmus ONLY"). Flagging via the
--    existing needs_source_rescrape column so the real re-scrape pipeline picks
--    these up; auction_status is NOT being copied from PO directly.
UPDATE multi_county_auctions
SET needs_source_rescrape = true,
    rescrape_strategy = 'okeechobee_stale_upcoming_po_divergence_20260710'
WHERE county = 'okeechobee'
  AND parity_status = 'matched_divergent';
