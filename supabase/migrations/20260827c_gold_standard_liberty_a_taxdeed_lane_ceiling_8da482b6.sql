-- Gold Standard dispatch 8da482b6: liberty letter A (dual-product lane coverage)
--
-- BEFORE (live, fetched via pencil_dod_evaluate_county('liberty') prior to fix):
--   A: { "pass": false, "detail": "fc=1 td=0", "metric": 0 }
--   public.auction_counties had ZERO row for Liberty at all — county was never
--   onboarded to the lane-registry table, even though a foreclosure lane
--   (libertyclerk.com/courts/foreclosure-sales/) already exists and is
--   populated (multi_county_auctions case '24-CA-22').
--
-- RESEARCH (live 2026-08-27):
--   1. Probed RealAuction tax-deed subdomain pattern used by neighboring
--      small NW-Florida counties (Gulf, Calhoun): https://liberty.realtaxdeed.com
--      -> HTTP 403 (unprovisioned subdomain; RealAuction does not host a
--      Liberty tax-deed lane). Also probed realtaxsale.com/realauction.com/
--      realbid.com liberty subdomains -> no DNS resolution (000).
--   2. Fetched the Liberty County Clerk of Court's own site (already the
--      trusted data_source for the existing foreclosure row):
--      https://libertyclerk.com/courts/tax-deeds/  -> HTTP 200, real page.
--      Verbatim page content: "Tax Deed Sales are held as scheduled and
--      noticed at 11:00 AM on the front steps of the Liberty County
--      Courthouse door" (per F.S. 197.502(5)). No online bidding platform —
--      sales are in-person courthouse-door auctions only.
--      Current listing state (verbatim from page): "There are no properties
--      on the list of tax deeds at this time."
--   3. No shared regional online tax-deed platform found for Liberty; the
--      clerk's own site is the sole authoritative tax-deed source.
--
-- DECISION:
--   Liberty DOES have a real, working, scrapable tax-deed source (the clerk's
--   own tax-deeds page), so we register the lane in auction_counties. It
--   currently has ZERO scheduled/published tax deed sales — genuinely
--   plausible for FL's least-populous county (~8,000 residents). Per
--   instructions, we do NOT fabricate a multi_county_auctions row for a lane
--   with no live listings. This is a structural ceiling (small-county sale
--   cadence), not a missing-source failure. A will remain fc=1 td=0 until a
--   future sweep of libertyclerk.com/courts/tax-deeds/ finds a real posted
--   tax deed case.
--
-- SQL RUN LIVE (via Supabase Management API, mocerqjnksmhcjzxrewo):

-- NOTE: foreclosure_platform_id/tax_deed_platform_id have FK constraints to
-- auction_platforms.platform_id. Liberty's clerk-built WordPress site is not
-- RealAuction; the correct pre-existing platform_id for "small-county,
-- clerk-run, no online bidding" is 'county_built' (surface_type=clerk_records,
-- case_type=tax_deed, requires_auth=false) — already used for exactly this
-- pattern elsewhere in the table, not invented for this row.
INSERT INTO public.auction_counties
  (fips_county, state_code, state_fips, county_name, county_fips,
   foreclosure_platform_id, foreclosure_url,
   tax_deed_platform_id, tax_deed_url,
   tax_lien_platform_id, tax_lien_url,
   clerk_records_platform_id, clerk_records_url,
   status, notes)
VALUES
  ('12077', 'FL', '12', 'Liberty', '077',
   'county_built', 'https://libertyclerk.com/courts/foreclosure-sales/',
   'county_built', 'https://libertyclerk.com/courts/tax-deeds/',
   NULL, NULL,
   'county_built', 'https://libertyclerk.com/courts/',
   'discovered',
   'No RealAuction tax-deed subdomain exists for Liberty (liberty.realtaxdeed.com -> 403). '
   'Tax deeds sold in-person at courthouse steps per F.S. 197.502(5), 11:00 AM EST, no online platform. '
   'As of 2026-08-27 the clerk''s own page states verbatim: "There are no properties on the list of tax deeds at this time." '
   'Zero live listings = structural ceiling for this county size (~8,000 residents), not a missing-source gap. '
   'Re-check libertyclerk.com/courts/tax-deeds/ periodically for a posted sale.');

-- No multi_county_auctions row inserted — zero real tax deed listings exist
-- to insert as of this session. Inventing one would violate the
-- never-fabricate guardrail.
--
-- AFTER (live, fetched via pencil_dod_evaluate_county('liberty') post-fix):
--   A metric is derived from auction_counties lane registration, not raw
--   multi_county_auctions counts alone — re-run the RPC after applying this
--   migration to confirm the actual post-fix value (see session verification).
