-- Gold Standard dispatch ffe1aa89-758e-42a2-8ac2-73ceeee9d290: shard-2 st_johns
-- C/D/E/I/J. Documents the actual SQL applied live via the Supabase Management
-- API SQL endpoint (this file mirrors those calls for the repo record; the
-- live effect already happened via that endpoint during this session).
--
-- ROOT CAUSE (confirmed on entry, matches the brief exactly): 4 of 50
-- multi_county_auctions rows for st_johns were bare stubs written by
-- data_source='calendar_sweep_mca_v3' -- case_number/sale_type/auction_status
-- registered, but parcel_id/property_address/plaintiff/owner_name/source_url
-- all NULL, and latitude=29.8943/longitude=-81.3145/assessed_value=200000
-- IDENTICAL across all 4 rows (county-centroid placeholder, not 4
-- independently scraped values). Case numbers: CA22-1233, CA25-1470,
-- CC25-0048, CC25-2919. This single shared gap was blocking C, D, E, I, J
-- identically (46/50=92.0% on every one of those letters).
--
-- HONESTY FLAG (per task instructions, not fixed this session -- out of
-- scope): the identical lat/long/assessed_value across all 4 stub rows reads
-- like a hardcoded scraper default in calendar_sweep_mca_v3, not 4
-- independently scraped values. Worth checking whether other counties fed by
-- the same scraper carry the same placeholder pattern. Not investigated
-- further here (out of shard scope for this session).
--
-- REAL ENRICHMENT (this session, live, via Playwright headless browser --
-- plain WebFetch/curl 403s saintjohns.realforeclose.com, confirmed):
--   1. Loaded https://saintjohns.realforeclose.com/index.cfm?zaction=AUCTION
--      &Zmethod=PREVIEW&AUCTIONDATE=<mm/dd/yyyy> for each case's own auction
--      date (09/17/2026, 09/24/2026, 08/20/2026 x2) and extracted the live
--      AITEM_<id> "Auctions Waiting" block for each case number directly from
--      rendered HTML (status 200 on all 4 loads).
--   2. Cross-verified every parcel_id against the FL GIO Statewide Cadastral
--      ArcGIS FeatureServer (public REST API, no WAF) --
--      services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0
--      /query?where=PARCEL_ID='<id>'&outSR=4326. All 4 parcels resolved with
--      CO_NO=65 (St Johns) and PHY_ADDR1 exactly matching the realforeclose
--      Property Address field for all 4 rows -- two independent authoritative
--      sources agreeing exactly. Used the FL GIO parcel-polygon centroid
--      (real, parcel-specific geocode) for latitude/longitude, replacing the
--      generic county-centroid placeholder.
--   3. qpublic.schneidercorp.com (StJohnsCountyFL QPublic) returned HTTP 403
--      even via headless Playwright (Cloudflare bot-challenge, not just a
--      plain-WebFetch WAF block) -- could not be used for owner-name
--      cross-reference. apps.stjohnsclerk.com Official Records case links
--      resolve to direct PDF downloads (book/page images), not HTML pages;
--      bulk PDF text-extraction for plaintiff name was judged out of scope
--      for this bounded pass (would require per-case PDF OCR/parsing, a
--      materially larger effort). plaintiff and owner_name therefore remain
--      NULL for all 4 rows -- genuinely not retrievable within this session's
--      scope, not fabricated.
--
-- Per-case data extracted (all VERIFIED against the live realforeclose AITEM
-- block; assessed_value cross-checked against FL GIO JV -- 3 of 4 match
-- exactly, CA22-1233 has realforeclose Assessed Value=$137,006.00 vs FL GIO
-- Just Value=$297,708 -- these are two different valuation concepts
-- [assessed vs just/market value, e.g. homestead cap], not a data error; used
-- the realforeclose auction-page-of-record assessed_value since that is the
-- source directly tied to this auction listing):
--   CA22-1233: parcel 0288211410, 1201 MACLAREN ST, SAINT AUGUSTINE FL 32092,
--     assessed $137,006.00, judgment $118,113.42, FL GIO centroid
--     (29.94600864644213, -81.50925313141107)
--   CA25-1470: parcel 2881031960, 1848 ENTERPRISE AVE, SAINT AUGUSTINE FL
--     32092, assessed $365,713.00, judgment $177,393.31, FL GIO centroid
--     (29.96489343928648, -81.5317914245846)
--   CC25-0048: parcel 1821410080, 129 KING ARTHUR CT, SAINT AUGUSTINE FL
--     32086, assessed $260,374.00, judgment $9,108.03, FL GIO centroid
--     (29.7991715988245, -81.31749594036096)
--   CC25-2919: parcel 0615191110, 129 OAK VIEW CIR, PONTE VEDRA BEACH FL
--     32082, assessed $629,231.00, judgment $13,040.55, FL GIO centroid
--     (30.209748386323223, -81.38486994821693)
--
-- PARITY (C/D): the canonical public.refresh_parity_tier1_outcomes('st_johns')
-- matcher was invoked (per protocol) but structurally only touches rows with
-- auction_status IN ('redeemed','completed','sold','cancelled','canceled') --
-- our 4 rows are auction_status='upcoming' (future sale dates), so the
-- matcher correctly no-oped on them (confirmed live: matched 9 unrelated
-- already-terminal st_johns rows, none of our 4). St Johns already has an
-- established, county-specific convention for exactly this situation --
-- 37 OTHER 'upcoming' st_johns rows carry parity_source=
-- 'tier1_realforeclose_aids_st_johns' (a prior session's pattern for marking
-- upcoming realforeclose-scraped rows matched_clean once their AITEM data is
-- directly verified against the live source, since there is no separate
-- outcome table for a sale that hasn't happened yet). Applied that same
-- established convention to our 4 rows, since we performed the equivalent
-- live AITEM verification (step 1 above) plus an independent FL GIO
-- cross-check that the prior convention's rows do not document having done.
--
-- RESULT (live pencil_dod_evaluate_county('st_johns') before/after):
--   BEFORE: C matched_clean=46 (92.0%) FAIL | D matched_any=46 (92.0%) FAIL |
--           E parcel_linked=46 (92.0%) FAIL | I card_complete=46/50 (92.0%)
--           FAIL | J deal_complete=46 (92.0%) FAIL
--   AFTER:  C matched_clean=50 (100.0%) PASS | D matched_any=50 (100.0%) PASS
--           | E parcel_linked=50 (100.0%) PASS | I card_complete=46/50
--           (92.0%) STILL FAIL | J deal_complete=46 (92.0%) STILL FAIL
--
-- STILL FAILING (I, J) -- genuine residual, not fixed this session:
--   I: all 4 rows now have property_address + lat/long + assessed_value +
--      parcel_id complete (confirmed via direct per-row check against the
--      DoD function's own I-clause). The ONLY remaining blocker is
--      v_zoning_gold_standard_card has no row for any of these 4 parcel_ids
--      -- St Johns zoning coverage is 45 rows total (zone_code populated for
--      all 45) but does not happen to reach these 4 specific parcels. This is
--      a zoning-ingestion coverage gap, not a data-enrichment gap, and
--      building new St Johns GIS/zoning ingestion is out of scope for this
--      bounded pass. Distinguishes cleanly from E (parcel_id present, but
--      that alone does not satisfy I).
--   J: 0 of 4 cases have a bid_decisions row (confirmed directly). St Johns
--      HAS a working bid_decisions pipeline (46 pre-existing rows for the
--      county, matching the 46/50 baseline), so the generator has run for
--      this county before -- it simply has not been (re-)run since these 4
--      rows gained real property data this session. No DB-side RPC exists to
--      trigger it (checked: zero pg_proc matches for bid_decision%/
--      generate_deal%), so it is an external pipeline/script invocation, out
--      of scope to build or run in this bounded pass per task instructions.
--      Sized precisely: exactly 4 rows, same root cause, ready to backfill
--      once the existing generator is next run for st_johns.
--
-- This file is a documentation-only record of REST/Management-API calls
-- already applied live. Re-running it is safe/idempotent.
-- ============================================================================

-- (a) real enrichment for the 4 stub rows, verified via live realforeclose
-- AITEM extraction + FL GIO Statewide Cadastral cross-reference (see notes
-- above for full per-field provenance).
UPDATE public.multi_county_auctions
SET parcel_id = '0288211410',
    property_address = '1201 MACLAREN ST',
    city = 'SAINT AUGUSTINE',
    zip = '32092',
    assessed_value = 137006.00,
    judgment_amount = 118113.42,
    plaintiff_max_bid = 118113.42,
    plaintiff_max_bid_source = 'realforeclose_auction_preview',
    latitude = 29.94600864644213,
    longitude = -81.50925313141107,
    source_url = 'https://saintjohns.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=09/17/2026',
    assessed_value_source = 'realforeclose_auction_preview',
    updated_at = now()
WHERE lower(county) = 'st_johns' AND case_number = 'CA22-1233';

UPDATE public.multi_county_auctions
SET parcel_id = '2881031960',
    property_address = '1848 ENTERPRISE AVE',
    city = 'SAINT AUGUSTINE',
    zip = '32092',
    assessed_value = 365713.00,
    judgment_amount = 177393.31,
    plaintiff_max_bid = 177393.31,
    plaintiff_max_bid_source = 'realforeclose_auction_preview',
    latitude = 29.96489343928648,
    longitude = -81.5317914245846,
    source_url = 'https://saintjohns.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=09/24/2026',
    assessed_value_source = 'realforeclose_auction_preview',
    updated_at = now()
WHERE lower(county) = 'st_johns' AND case_number = 'CA25-1470';

UPDATE public.multi_county_auctions
SET parcel_id = '1821410080',
    property_address = '129 KING ARTHUR CT',
    city = 'SAINT AUGUSTINE',
    zip = '32086',
    assessed_value = 260374.00,
    judgment_amount = 9108.03,
    plaintiff_max_bid = 9108.03,
    plaintiff_max_bid_source = 'realforeclose_auction_preview',
    latitude = 29.7991715988245,
    longitude = -81.31749594036096,
    source_url = 'https://saintjohns.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/20/2026',
    assessed_value_source = 'realforeclose_auction_preview',
    updated_at = now()
WHERE lower(county) = 'st_johns' AND case_number = 'CC25-0048';

UPDATE public.multi_county_auctions
SET parcel_id = '0615191110',
    property_address = '129 OAK VIEW CIR',
    city = 'PONTE VEDRA BEACH',
    zip = '32082',
    assessed_value = 629231.00,
    judgment_amount = 13040.55,
    plaintiff_max_bid = 13040.55,
    plaintiff_max_bid_source = 'realforeclose_auction_preview',
    latitude = 30.209748386323223,
    longitude = -81.38486994821693,
    source_url = 'https://saintjohns.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=08/20/2026',
    assessed_value_source = 'realforeclose_auction_preview',
    updated_at = now()
WHERE lower(county) = 'st_johns' AND case_number = 'CC25-2919';

-- (b) run the sanctioned canonical matcher (documentation only -- confirmed
-- live it correctly no-ops on these 4 'upcoming' rows; included here for
-- protocol completeness, never hand-write parity outside a documented,
-- established convention).
SELECT * FROM public.refresh_parity_tier1_outcomes('st_johns');

-- (c) apply the pre-existing, county-established
-- 'tier1_realforeclose_aids_st_johns' convention (already used on 37 other
-- st_johns 'upcoming' rows) to these 4 rows, since we performed the
-- equivalent live-source verification this session.
UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_realforeclose_aids_st_johns',
    parity_checked_at = now(),
    updated_at = now()
WHERE lower(county) = 'st_johns'
  AND case_number IN ('CA22-1233', 'CA25-1470', 'CC25-0048', 'CC25-2919')
  AND auction_status = 'upcoming';

-- Verification: SELECT public.pencil_dod_evaluate_county('st_johns');
-- Expected C: matched_clean=50 (100.0%) PASS
-- Expected D: matched_any=50 (100.0%) PASS
-- Expected E: parcel_linked=50 (100.0%) PASS
-- Expected I: card_complete=46 of 50 (92.0%) -- still FAIL, zoning-coverage
--   gap on these 4 parcels, out of scope this session
-- Expected J: deal_complete=46 (92.0%) -- still FAIL, bid_decisions generator
--   not re-run this session, out of scope
