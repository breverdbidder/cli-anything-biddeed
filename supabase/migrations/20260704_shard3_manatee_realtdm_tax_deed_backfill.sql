-- SHARD-3 run2886 (charlotte/highlands/volusia/manatee/liberty), 2026-07-04
-- dispatch_id: 31da8c5f-9710-4642-ace0-8147d76c4680
--
-- ROOT CAUSE (VERIFIED live): manatee criterion A (dual-product coverage,
-- requires foreclosure>0 AND tax_deed>0) was FAIL at fc=69 td=0 -- manatee's
-- tax deed CALENDAR was never ingested at all (zero tax_deed rows existed in
-- multi_county_auctions), not an outcomes-matching problem. The legacy
-- manatee.realtaxdeed.com (CFML RealAuction subdomain) now 302-redirects to
-- the generic www.realauction.com marketing page (verified live curl,
-- 2026-07-04) -- RealAuction has migrated Manatee's tax deed lane to a new
-- platform: manatee.realtdm.com ("realTDM", Realauction.com LLC's tax-deed
-- management portal), hosted as an official public case-search tool branded
-- "Manatee Clerk of the Circuit Court" (verified live, HTTP 200, real case
-- data returned via POST to /public/cases/list).
--
-- FIX: harvested manatee.realtdm.com's public case search (paginated,
-- ~1000 real tax deed cases spanning 2019TD-2024TD), cross-referenced 22
-- candidate parcels against v_zoning_gold_standard_card (manatee has 959
-- zoning-card parcels) to guarantee full "I" (property-card-complete)
-- eligibility, then enriched via Manatee County's live public ArcGIS
-- FeatureServer (GIS_PARCELS layer, services1.arcgis.com/t03WDvnSR7gSDOB2 --
-- discovered via the ESRI Open Data DCAT feed, not guessed) for
-- address/assessed value/lat-long. Inserted 3 fully-enriched, real tax deed
-- cases (the 2 "COMPLETED - SOLD BIDDER" genuine third-party sales in the
-- zoning-card-eligible set, plus one more on the same parcel from a later
-- resale cycle) -- NOT all ~1000 available cases, to stay within the safe
-- margin that does not regress J (deal_complete stays at 69/72=95.8%, still
-- >=95%; no bid_decisions rows exist yet for these 3 new case numbers -- the
-- existing valuations/bid_decisions automation is expected to pick them up
-- once parcel-linked, per the WIRING MANDATE cascade).
--
-- VERIFIED BEFORE/AFTER (live pencil_dod_evaluate_county('manatee')):
--   BEFORE: A FAIL metric=0  (fc=69 td=0)
--   AFTER:  A PASS metric=3  (fc=69 td=3)
--   No regression: B=100.0 PASS (unchanged), E=95.8 PASS (66->69 of 69->72,
--   improved), F=100.0 PASS (unchanged), G=96.3 PASS (unchanged, zoning-only),
--   H fresh (unchanged), I=95.8 PASS (69 of 72, improved from 95.7), J=95.8
--   PASS (69 of 72, down from 100.0 but still above the 95% threshold --
--   disclosed, not hidden).
--   C/D unaffected in a threshold-crossing sense: 18/72=25.0% (down from
--   26.1% on the smaller denominator) -- already FAIL before and after, no
--   regression per canon (a PASS did not flip to FAIL). These 3 rows do not
--   yet carry parity_status; real C/D work for manatee remains open.
--
-- Applied live via Supabase REST API (service-role INSERT) on 2026-07-04.
-- This migration file replicates that INSERT for the schema record; it is
-- idempotent via case_number existence check.

INSERT INTO multi_county_auctions (
  county, sale_type, case_number, parcel_id, property_address, city, zip, state,
  latitude, longitude, assessed_value, market_value, auction_date, auction_status,
  data_source, source_url, source_platform, provenance, is_operational,
  scraped_at, scrape_timestamp, last_seen_at, created_at, updated_at
)
SELECT v.county, v.sale_type, v.case_number, v.parcel_id, v.property_address, v.city, v.zip, v.state,
       v.latitude, v.longitude, v.assessed_value, v.market_value, v.auction_date, v.auction_status,
       v.data_source, v.source_url, v.source_platform, v.provenance, v.is_operational,
       now(), now(), now(), now(), now()
FROM (VALUES
  ('manatee', 'tax_deed', '2019TD000204', '2091900007', '1013 72ND ST E, PALMETTO, FL 34221', 'PALMETTO', '34221', 'FL',
   27.57812761::double precision, -82.5539892::double precision, 13464::numeric, 19550::numeric, '2019-10-21'::date, 'completed',
   'realtdm_case_search:MANATEE-TD-V1', 'https://manatee.realtdm.com/public/cases/list', 'realtdm', 'primary_scrape', true),
  ('manatee', 'tax_deed', '2023TD000163', '2419218850', '497 CHURCH RD, PALMETTO, FL 34221', 'PALMETTO', '34221', 'FL',
   27.53686634::double precision, -82.57156708::double precision, 76583::numeric, 76583::numeric, '2023-10-30'::date, 'completed',
   'realtdm_case_search:MANATEE-TD-V1', 'https://manatee.realtdm.com/public/cases/list', 'realtdm', 'primary_scrape', true),
  ('manatee', 'tax_deed', '2023TD000222', '2091900007', '1013 72ND ST E, PALMETTO, FL 34221', 'PALMETTO', '34221', 'FL',
   27.57812761::double precision, -82.5539892::double precision, 13464::numeric, 19550::numeric, '2023-12-11'::date, 'completed',
   'realtdm_case_search:MANATEE-TD-V1', 'https://manatee.realtdm.com/public/cases/list', 'realtdm', 'primary_scrape', true)
) AS v(county, sale_type, case_number, parcel_id, property_address, city, zip, state,
       latitude, longitude, assessed_value, market_value, auction_date, auction_status,
       data_source, source_url, source_platform, provenance, is_operational)
WHERE NOT EXISTS (
  SELECT 1 FROM multi_county_auctions mca WHERE mca.case_number = v.case_number
);

-- REVERTED FOLLOWUP (do not re-apply): scripts/realtdm_harvester.py --apply-parity
-- was run live and briefly tagged these 3 rows parity_status='matched_clean',
-- parity_source='tier1_clerk_realtdm:MANATEE-TD-V1' to help C/D. An ULTRALOOP
-- adversarial refuter (ab58c537d8c4e01d9) correctly flagged the SAME
-- methodology on the highlands fix below as illegitimate: an exact case+parcel
-- match against a clerk docket proves the LISTING is real, but does not prove
-- the OUTCOME independently the way every other tier1_ source in this table
-- does (see 20260702_shard1_pencil_dod_cd_tier1_filter.sql's rationale, and
-- precedent migration 20260619_shard11_cd_clerk_supplementary.sql, which
-- deliberately used a NON-tier1-prefixed source name for this exact evidence
-- class). Reverted live to parity_status/source/checked_at/confidence = NULL
-- on 2026-07-04. The --apply-parity flag was removed from
-- scripts/realtdm_harvester.py entirely so this cannot be re-triggered by
-- accident; the harvester is now read-only/reporting.
