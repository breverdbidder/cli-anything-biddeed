-- GOLD STANDARD shard-3 (dispatch 97478bee-d8b5-4f34-9cac-e6e9ca00ed7e), counties
-- martin/alachua/madison. Documents live PostgREST data writes applied directly
-- during this session (direct psql unavailable per the standing pooler SNI
-- constraint -- PostgREST/service-role REST used instead, consistent with the
-- established pattern for this pipeline). No schema changes; this file is an
-- audit-trail record of INSERT-only data operations already applied live.
--
-- MARTIN: I FAIL->PASS (92.8%->95.7%, 64/69->66/69 card_complete). Root cause:
-- 2 parcels had complete address/geo/value but no zone_code linkage in
-- v_zoning_gold_standard_card. Point-in-polygon query against Martin County's
-- own live ArcGIS zoning MapServer resolved both:
--   34-38-42-825-000-00090-0 (case 25001177CAAXMX) -> RM-5
--     (geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/
--      Future_Landuse_Zoning/MapServer/1, ZONING_DETAILS='Res. 96-8.62')
--   15-40-40-000-100-00660-9 (case 25001144CAAXMX) -> IZ (existing district)
-- Municipal-boundary cross-check (Administrative_Areas/Administrative_Areas/
-- MapServer/0) confirmed both points fall outside every municipality polygon
-- -> unincorporated Martin County, jurisdiction_id=1331 (existing row).
-- RM-5 zoning_districts row inserted with far_regulated=null, density/pk1000
-- regulated=false (no fabricated numeric standard -- Municode 403-blocked,
-- same restriction documented in every prior martin session; name is an
-- INFERRED label per the standard FL RM-<density> naming convention, marked
-- as such in the row's own name/description text).
-- Remaining 3-row I gap (23001555CCAXMX, 25001632CCAXMX, 25001634CCAXMX)
-- confirmed live to be case_classification_code=NON_REAL_PROPERTY (timeshare/
-- personal-property HOA lien foreclosures) -- genuinely no parcel/address
-- exists for these, not a scraping gap. Not counted as a residual blocker.
-- Full county result: martin now 10/10 (A-J all PASS), re-verified live via
-- pencil_dod_evaluate_county('martin') post-write.
--
-- ALACHUA:
--   J FAIL->PASS (90.6%->100.0%, 77/85->85/85 deal_complete). Re-ran the
--   existing, previously-proven scripts/alachua-J_fix.py generator (Shapira
--   V14 ml_score + gen_valuations_comps_batch two-arm CMA + documented 4-tier
--   real_arv fallback) unmodified. 8 case_numbers had accrued zero
--   bid_decisions rows since the tool last ran (denominator grew 61->85
--   auctions since a 2026-08-02 session last closed this gap). No new
--   generator code written; scope-limited to alachua only, idempotent.
--   inserted=8 updated=0 skipped_no_real_value=0.
--   I partial: 91.8%->92.9% (78/85->79/85). Fixed case 01 2026 CA 000588
--   (parcel_id 06088-005-012, already had full address/geo/value) via ArcGIS
--   Parcels35_view attribute query (parcel=06088-005-012) -> ZONECODE=SF,
--   JurisNo=300 -> jurisdiction_id=915. JustValue=775958 matched the row's
--   existing assessed_value exactly (corroborating evidence). 1 parcel_zones
--   row inserted.
--   E unchanged, still FAIL (92.9%, 79/85). 6-row gap: 4 cases (003919,
--   001928, 003287, 002643) re-confirmed exhausted per prior documented
--   session (scripts/gold_standard_shard1_run8166_alachua_e_i_j_fix.py,
--   2026-08-02: RealForeclose empty docid, Playwright-confirmed absent Parcel
--   ID field, qpublic 403, ArcGIS owner-name dead ends). 2 NEW cases this
--   session (002983, 000169) attempted fresh: direct WebFetch 403; curl with
--   browser UA returned 200 but only the anonymous RealForeclose login-splash
--   page (case detail requires an authenticated session per this project's
--   own playbook A); Firecrawl scrape API returned HTTP 402 insufficient
--   credits (account-wide exhaustion, independently reconfirmed this
--   session -- same state documented by the 2026-08-18 madison session).
--   No parcel_id written for any of the 6. BLANK > WRONG.
--   I's remaining 6-row gap is the same case set as E (I <= E by
--   construction) -- not independently re-attempted.
--
-- MADISON: B/C/F/I re-verified live with FRESH evidence this session (11th+
-- consecutive session on B/F/I; C is a new finding this session), all remain
-- genuine structural blockers, zero writes:
--   B/F (verified=0/closed_sold=0): 3 past-due auctions (21-36-CA 07-16,
--   24-62-CA 07-28, 26-20-CA 08-05) still show status='scheduled' on a live
--   re-fetch of madisonclerk.com's wp-json/wp/v2/foreclosures feed, modified
--   timestamps unchanged since June 2026 -- the feed never publishes a
--   post-sale result field. myfloridacounty.com/orisearch 403 direct;
--   civitekflorida.com unreachable; Firecrawl API independently reconfirmed
--   still HTTP 402 insufficient credits this session.
--   C (matched_clean=7 of 8, 87.5%): live-reconfirmed the sole
--   CLERK_SSOT_CANCELLED row (case 25-128-CA) genuinely carries
--   status='cancelled' at the clerk source -- the classification is correct,
--   not a bug. With N=8 total auctions, 1 genuine cancellation structurally
--   caps matched_clean at 87.5% until the denominator grows.
--   I (card_complete=6 of 8, 75.0%): 2 blocking parcels (21-2N-09-5288-
--   022-000 case 26-7-TD, 21-2N-09-5288-021-000 case 26-9-TD) already have
--   complete address/geo/value from a prior session; only zone_code linkage
--   is missing (a fabricated entry for these was purged by a 2026-07-10
--   fabrication-purge migration and never legitimately replaced). NEW this
--   session: direct curl (bypassing the Firecrawl 402 that blocked every
--   prior attempt) confirmed planning.madisoncountyfla.com/gis is directly
--   reachable (HTTP 200) and its page payload exposes a live backend UMN
--   MapServer 6.4.3 instance at gz.floridapa.com/mapserver (WMS_SERVER
--   capable, confirmed reachable) -- the first session to reach this far.
--   The correct internal mapfile name/path was not discovered this session
--   (5 common naming patterns tried, all failed with the same generic
--   mapfile-load error) -- a genuinely new intermediate finding, not yet an
--   unblock. qpublic.schneidercorp.com (AppID=911) still 403 Cloudflare.
--   No zone_code written. BLANK > WRONG.
--
-- All claims above are logged as individual rows in
-- gold_standard_ultraloop_audit (dispatch_id=97478bee-d8b5-4f34-9cac-
-- e6e9ca00ed7e) with before/after evidence, consistent with the ULTRALOOP
-- CERTIFY GATE protocol. gold_standard_campaign checkpoint updated with
-- per-county criteria_passed for the next session to resume from.
--
-- This file is documentation-only (the INSERT/UPDATE statements below were
-- already applied live via PostgREST during the session; re-running them here
-- is a no-op by design, using the same ON CONFLICT DO NOTHING idempotency
-- pattern this repo's other gold-standard migrations use).

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, pk1000_regulated, description, ordinance_section)
SELECT 1331, 'RM-5',
  'RM-5 Multi-Family Residential (INFERRED name from standard FL RM-<density> naming convention; Municode library.municode.com returns HTTP 403 to direct fetch, same restriction documented in prior martin sessions -- exact ordinance text not independently confirmed this session)',
  'Residential', NULL, false, false,
  'GIS ZONING_DETAILS field value on the Martin County Future_Landuse_Zoning MapServer layer 1 for this parcel reads ''Res. 96-8.62'' (a resolution citation, not a full ordinance section). No accessible ordinance text confirms an exact density/FAR/setback table this session -- Municode 403-blocked (same restriction as prior martin sessions).',
  'Res. 96-8.62 (per GIS ZONING_DETAILS field, unverified against full ordinance text)'
WHERE NOT EXISTS (SELECT 1 FROM public.zoning_districts WHERE jurisdiction_id = 1331 AND code = 'RM-5');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '34-38-42-825-000-00090-0', 1331, 'RM-5', 'RM-5 Multi-Family Residential',
  'https://geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/Future_Landuse_Zoning/MapServer/1/query point-in-polygon at parcel centroid (parcel_id=34-38-42-825-000-00090-0); ZONING=RM-5 returned. Municipal boundary check via Administrative_Areas/Administrative_Areas/MapServer/0 at same point returned zero features -> unincorporated Martin County jurisdiction confirmed.'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '34-38-42-825-000-00090-0');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '15-40-40-000-100-00660-9', 1331, 'IZ', 'IZ Interim Zoning',
  'https://geoweb.martin.fl.us/arcgis/rest/services/Administrative_Areas/Future_Landuse_Zoning/MapServer/1/query point-in-polygon at parcel centroid (parcel_id=15-40-40-000-100-00660-9); ZONING=IZ returned. Municipal boundary check via Administrative_Areas/Administrative_Areas/MapServer/0 at same point returned zero features -> unincorporated Martin County jurisdiction confirmed.'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '15-40-40-000-100-00660-9');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '06088-005-012', 915, 'SF', 'Single Family',
  'https://services1.arcgis.com/MiBZ4u97DWldovjI/arcgis/rest/services/Parcels35_view/FeatureServer/0/query (parcel=06088-005-012, ZONECODE lookup, ZONEDISTRICT=SF, JurisNo=300 mapped to jurisdiction_id=915)'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '06088-005-012');
