-- Gold Standard shard-4 (dispatch 0bb18a71): okeechobee I letter fix.
-- Applied live via Supabase REST (PostgREST) during the session, since direct
-- psql/SUPABASE_DB_PASSWORD access was unavailable (documented constraint,
-- decision_log ids 169/205/287). This file records the DML for the repo's
-- migration history; it is NOT re-applied automatically.
--
-- Before: pencil_dod_evaluate_county('okeechobee') I = FAIL 93.1% (81 of 87)
-- After:  pencil_dod_evaluate_county('okeechobee') I = PASS 95.3% (82 of 86)
-- okeechobee is now live 10/10 (full Gold Standard) -- no regressions on any
-- other letter (A/B/C/D/F/G/H/J all confirmed still PASS; E improved
-- 95.4%->97.7% as a side effect).

-- 1) Case 472025CA000223CAAXMX: full card enrichment (parcel_id/address/geo/
--    value/owner/legal_description), sourced live from the FL GIO Statewide
--    Cadastral ArcGIS FeatureServer (PARCEL_ID=10537350030004200090) and
--    corroborated against the Clerk-issued Notice of Action text on
--    NoticeRegistry. Verified by an independent adversarial-verify agent
--    (survived=true, fabrication_risk=none; see gold_standard_ultraloop_audit
--    id 19898-19903).
UPDATE public.multi_county_auctions
SET
  parcel_id = '1-05-37-35-0030-00420-0090',
  property_address = '3633 NW 38TH AVE',
  latitude = 27.2769225248107,
  longitude = -80.867540352942,
  assessed_value = 179957,
  market_value = 179957,
  owner_name = 'LUIS R. GONZALEZ',
  legal_description = 'Lot 9 Block 42 Basswood Inc Unit 3',
  plaintiff = 'LAKEVIEW LOAN SERVICING LLC'
WHERE county = 'okeechobee' AND case_number = '472025CA000223CAAXMX';

-- 2) Zone-link the newly-enriched parcel above via the proven okeechobeegis.com
--    WMS point-in-polygon method (scripts/gold_standard_okeechobee_i_wms_pixel_
--    20260808_9c6b9b03.py) -- single clean zoning_ResidentialSingleFamily hit,
--    no ambiguity, maps to the existing jurisdiction_id=943 RSF district code
--    already used by 60+ other okeechobee parcels.
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES (
  '1-05-37-35-0030-00420-0090', 943, 'RSF', 'Residential Single-Family',
  'okeechobeegis.com_wms_ol_themes_point_in_polygon;layer=zoning_ResidentialSingleFamily;xy_epsg2236=(699191.99,1069859.37);dispatch=0bb18a71;case=472025CA000223CAAXMX'
);

-- 3) Delete duplicate blank stub case '2025-CA-189'. Its enriched sibling row
--    '472025CA000189CAAXMX' already carries the real address/parcel/value for
--    the same real-world case (parcel 1-29-37-35-0010-00000-0890, same address
--    "2085 SW 19TH LN, OKEECHOBEE, FL 34974", same auction_date 2026-10-14) --
--    okeechobeeclerk.com's live calendar publishes the short case-number form
--    while calendar_sweep_mca_v3 already stores the 19th Circuit long form;
--    the existing _OKEECHOBEE_SHORT_RE/_OKEECHOBEE_LONG_RE canonicalization in
--    scripts/clerk_ssot/run_parity.py (added 2026-08-16 for cases 130/143/205)
--    already covers this case-number pair for parity matching, but does not
--    prevent the upstream ingestion cron from re-inserting the short-form stub
--    -- same recurring root cause as the 2026-08-16 fix, same safe remediation
--    (delete the blank duplicate, keep the enriched sibling).
--    Safety check performed live before deleting: 17 bid_decisions rows exist
--    under case_number='2025-CA-189' with no FK to multi_county_auctions.id
--    (same orphan pattern the 2026-08-16 session found and proceeded on) --
--    deletion does not orphan anything new.
DELETE FROM public.multi_county_auctions
WHERE county = 'okeechobee' AND case_number = '2025-CA-189';
