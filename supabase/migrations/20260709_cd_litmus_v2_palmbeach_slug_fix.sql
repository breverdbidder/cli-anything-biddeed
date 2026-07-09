-- C/D LITMUS V2 (issue #10981 follow-up) — fix county_slug mismatch that made
-- Palm Beach silently fall back to FloridaBidder (Cloudflare-blocked) instead
-- of its real, working RealAuction platform.
--
-- Root cause (VERIFIED 2026-07-09): county_auction_config stores Palm Beach as
-- county_slug='palmbeach' (no underscore), while every other consumer
-- (multi_county_auctions.county, cd_litmus_parity_v2.county_slug, the V2
-- harvest script's PRIORITY_COUNTIES list) uses 'palm_beach'. The harvester's
-- lookup `WHERE county_slug IN ('palm_beach', ...)` never matched the
-- 'palmbeach' row, so it always treated Palm Beach as having no online
-- platform even though fc_method/td_method are both 'online' with live URLs
-- (palmbeach.realforeclose.com / palmbeach.realtaxdeed.com) that the Jul 6
-- 2026 harvest run already proved reachable (source_count=32 fc / 97 td).
--
-- No other code references the literal 'palmbeach' string (grepped repo-wide),
-- so renaming the slug to match every other table's convention is safe.
UPDATE public.county_auction_config
SET county_slug = 'palm_beach'
WHERE county_slug = 'palmbeach';
