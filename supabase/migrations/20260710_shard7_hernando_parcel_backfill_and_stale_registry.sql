-- SHARD-7 (hernando) — backfill 1 verified parcel_id + deactivate stale RealAuction registry row
--
-- E gap fix (VERIFIED): hernando.realtaxdeed.com Area-C AJAX scrape (2026-07-10, dispatch
-- 1f745e08) found case 2026-011TD live on the auction calendar with parcel_id
-- "R14 223 19 2700 0090 0010", address "SHYLA RD, BROOKSVILLE, FL- 34604" -- matches the
-- address already on file for this case, just missing parcel_id. Other 4 of 5 E-gap cases
-- (2024-077TD, 2026-018TD, 2026-023TD, 2026-024TD) were NOT found across 6 auction dates
-- probed (Area A + Area C) -- not fabricated, left null pending further discovery.
UPDATE public.multi_county_auctions
SET parcel_id = 'R14 223 19 2700 0090 0010',
    updated_at = now()
WHERE lower(county) = 'hernando'
  AND case_number = '2026-011TD'
  AND parcel_id IS NULL;

-- Registry cleanup (CONFIRMED via pipeline.scrape_runs: 327/327 all-time runs for
-- hernando_realforeclose failed with "Zero cards extracted"). pipeline.counties already
-- correctly documents hernando foreclosure sales as in-person courthouse (Room 245, Tue/Thu
-- 11AM, scraped via hernando_clerk_pdf / shard3_hernando_fc_scraper.py), NOT RealAuction.
-- The realauction_subdomains 'foreclosure' row for hernando is a stale auto-discovered entry
-- (subdomain resolves/200s but has no real published foreclosure auctions) that has burned
-- 327 wasted GHA runs. Deactivating it only (not the tax_deed row, which IS real and live).
UPDATE public.realauction_subdomains
SET is_active = false,
    notes = COALESCE(notes, '') || ' | 2026-07-10 shard7 (dispatch 1f745e08): deactivated -- 327/327 all-time scrape_runs failed (Zero cards extracted); hernando foreclosure sales are in-person courthouse per pipeline.counties.foreclosure_platform=hernando_clerk_pdf, not RealAuction. tax_deed row left active (real, live, verified 200 + parseable calendar).',
    updated_at = now()
WHERE county_slug = 'hernando' AND sale_type = 'foreclosure' AND platform = 'realforeclose';
