-- SHARD-3 (okaloosa) 2026-07-19: Okaloosa Bid4Assets platform correction +
-- NEW real live auction rows scraped from the county's actual live source.
--
-- Root cause (see pipeline.counties.notes for okaloosa for the full 5+
-- session history): okaloosa.realforeclose.com and okaloosa.realtaxdeed.com
-- are BOTH dead (302-redirect to the realauction.com marketing splash,
-- confirmed repeatedly). The county migrated to Bid4Assets. foreclosure_
-- platform/url were already corrected to bid4assets in a prior session;
-- taxdeed_platform/url were still stale (realtaxdeed) and are fixed here.
--
-- The actual 38 new multi_county_auctions rows (26 foreclosure, 12 tax_deed)
-- plus 3 foreclosure_outcomes rows for genuinely closed 2026-07-16 sales
-- were written live via scripts/okaloosa_bid4assets_harvest.py during this
-- session (upsert via PostgREST, not SQL) -- this migration file documents
-- the platform/url correction only; it does not re-insert the scraped rows
-- (those are idempotent via the harvester's own on_conflict upsert and are
-- re-runnable via the okaloosa-bid4assets-harvest.yml GHA cron).

SET statement_timeout = 0;

UPDATE pipeline.counties
SET taxdeed_platform = 'bid4assets',
    taxdeed_url = 'https://www.bid4assets.com/OkaloosaFLTax/listings'
WHERE county_slug = 'okaloosa';
