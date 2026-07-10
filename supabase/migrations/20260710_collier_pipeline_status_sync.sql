-- Sync pipeline.counties for collier to the verified state already established in
-- county_auction_config (2026-07-03 investigation, scripts/shard9_collier_realdata_bootstrap.py):
-- collier.realforeclose.com / collier.realtaxdeed.com both 302-redirect to a deprovisioned
-- RealAuction vendor account. Collier FC/TD sales are conducted in-person only. collierclerk.com's
-- court systems (ShowCase, Laserfiche WebLink) require authenticated/JS sessions with no
-- anonymously-scrapable feed -- confirmed no ingestible data source exists (same pattern as
-- lafayette/glades). This is a metadata-accuracy fix only; no auction rows are created.
UPDATE pipeline.counties
SET
  foreclosure_platform = 'clerk_inperson',
  foreclosure_url = 'https://www.collierclerk.com/court-divisions/civil-court/foreclosures/foreclosure-sales/',
  taxdeed_platform = 'clerk_inperson',
  taxdeed_url = 'https://www.collierclerk.com/tax-deed-sales/search-upcoming-sales-list/',
  pipeline_status = 'blocked',
  pipeline_health = 'inactive',
  notes = 'Auto-seeded 2026-05-20 from realauction_subdomains (stale, uncorroborated) | 2026-07-03 shard9_collier_realdata_bootstrap: collier.realforeclose.com and collier.realtaxdeed.com both confirmed 302-redirect to http://www.realauction.com (deprovisioned vendor account, not a live scrapable calendar). Collier FC/TD sales conducted in-person only (FC: Courthouse Annex 3rd floor, Mon-Fri 11am; TD: County Admin Bldg 7th floor Rm 711, some Mondays 1pm) per county_auction_config. collierclerk.com court systems (cms.collierclerk.com ShowCase, app.collierclerk.com Laserfiche WebLink) require authenticated/JS sessions -- no anonymously scrapable feed found. 2026-07-10 shard7 session: synced this row to match county_auction_config (was stale pending/NULL, misleadingly implying unconfigured rather than verified-dead). realauction_subdomains.is_active=true for collier is STALE/WRONG, superseded by this live finding -- do not treat product_count from realauction_multi_product_counties_v as authoritative for collier. Letter A intentionally remains FAIL: no real online source exists to ingest auctions from; do NOT fabricate multi_county_auctions rows to force a pass (two prior scripts, shard5_a_lane_collier.py and shard5_collier_real_data.py, exist in this repo for exactly that purpose and must NOT be run -- same ghost-success pattern already caught and reverted for okeechobee).'
WHERE county_slug = 'collier';
