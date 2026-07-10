-- SHARD-7: hernando E/I fix #2 — TaxSmart-verified TD parcel linkage + county-GIS zoning substrate
-- dispatch_id: 010a05ae-e4f8-488a-954f-6d0497384f23
-- Session: architect-20260702T080000 (gold standard shard-7: levy, bay, hernando)
--
-- CONTEXT: applied live via Supabase REST API (PATCH/POST). Continuation of today's earlier
-- hernando E/H/I migration (20260702_shard7_hernando_e_i_h_parcel_fix.sql, commit c75ddfc7),
-- which left 3 ambiguous tax-deed cases and 4 unzoned foreclosure parcels as documented gaps.
-- This migration closes 3 of those TD-linkage gaps and 3 of the 4 zoning gaps with real,
-- source-cited data (no guessing).
--
-- ============================================================================
-- PART 1: E — resolve 3 ambiguous tax-deed cases via Hernando Clerk's TaxSmart platform
-- ============================================================================
-- TaxSmart (https://or.hernandoclerk.com/TaxSmart/) exposes a jqGrid AJAX data endpoint at
-- /TaxSmart/Home/GridSearchData?SearchType=Case%20%23 that returns authoritative case->parcel
-- mapping (no auth/disclaimer gate). Queried live for the 3 cases previously ambiguous (2/32/8
-- FL GIO owner-name candidates respectively, per the 2026-06-24 migration's note). Each TaxSmart
-- result's "PropertyOwners" field was cross-checked against FL GIO OWN_NAME (CO_NO=37) at the
-- returned ParcelID and MATCHED EXACTLY for all 3:
--   2026-011TD: TaxSmart owner "MRS C O PUCKETT" == FL GIO "PUCKETT C O MRS" at
--     R14 223 19 2700 0090 0010 (JV=$5,192, Shyla Rd, Brooksville). TaxSmart Status=SALE
--     (not yet sold; matches our auction_date=2026-07-15 upcoming).
--   2026-018TD: TaxSmart owner "MICHAEL LEWIS BROWNING JR" == FL GIO "BROWNING MICHAEL LEWIS JR"
--     at R14 123 21 1280 0100 0070 (JV=$13,763, Tamer Ln, Dade City). Status=SALE.
--   2026-030TD: TaxSmart owner "FRANKLIN NUNEZ" == FL GIO "NUNEZ FRANKLIN" at
--     R11 123 21 0620 0000 2950 (JV=$22,527, Azalea Cir, Dade City). Status=SALE.
-- market_value = FL GIO "JV" field, CO_NO=37 (Hernando).
--
-- E impact (live-verified via pencil_dod_evaluate_county('hernando')):
--   parcel_linked 17/23 (73.9%) -> 20/23 (87.0%)
--
-- STILL UNRESOLVED (left NULL, no guessing): 22000840CA, 25000578CA, 25001007CA — all 3 are
-- circuit-court "CA" foreclosure cases (not tax-deed, so TaxSmart doesn't cover them). The
-- Hernando Clerk case-docket search (Civitek OCRS, civitekflorida.com/ocrs/county/27/) and the
-- LandmarkWeb official-records CaseNumberSearch (or.hernandoclerk.com/LandmarkWeb/) both require
-- an interactive/JS-driven session (disclaimer click-through + ASP.NET MVC array-indexed form
-- binding) that could not be reproduced with a plain HTTP session in this environment (confirmed
-- HTTP 500 on the CaseNumberSearch POST endpoint after replicating the disclaimer-accept cookie
-- flow — same failure the recon pass hit). No browser-automation tool (Playwright/firecrawl
-- browser) was available in this session. Needs follow-up with real browser automation.

UPDATE multi_county_auctions
SET parcel_id = 'R14 223 19 2700 0090 0010',
    property_address = 'SHYLA RD',
    city = 'BROOKSVILLE',
    zip = '34604',
    market_value = 5192
WHERE county = 'hernando' AND case_number = '2026-011TD';

UPDATE multi_county_auctions
SET parcel_id = 'R14 123 21 1280 0100 0070',
    property_address = 'TAMER LN',
    city = 'DADE CITY',
    zip = '33523',
    market_value = 13763
WHERE county = 'hernando' AND case_number = '2026-018TD';

UPDATE multi_county_auctions
SET parcel_id = 'R11 123 21 0620 0000 2950',
    property_address = 'AZALEA CIR',
    city = 'DADE CITY',
    zip = '33523',
    market_value = 22527
WHERE county = 'hernando' AND case_number = '2026-030TD';

-- ============================================================================
-- PART 2: I — zoning substrate for 3 of the 6 newly-linked foreclosure parcels
-- ============================================================================
-- Source: Hernando County ArcGIS FeatureServer
--   https://services2.arcgis.com/x5zvhhxfUuRDntRe/arcgis/rest/services/Zoning_Flu/FeatureServer/75
--   (field ZONING), point-in-polygon queried at each parcel's FL GIO centroid.
-- Standards source: official county PDF
--   https://hernandocounty.us/media/p54a0efr/residential-dimension-requirements.pdf
--   ("Hernando County Land Development Regulations, Zoning Districts and Dimensional
--   Requirements") — R1A and R1C rows.
--
-- These 3 parcels are in UNINCORPORATED Hernando County, governed by the County's own Land
-- Development Code (Appendix A), NOT Brooksville's municipal code — confirmed via the county
-- GIS layer returning a live polygon at each centroid (city-only parcels are absent from this
-- layer). A new jurisdiction "Hernando County (Unincorporated)" was created rather than reusing
-- the existing Brooksville jurisdiction_id=875 R-1A row, since the two ordinances are distinct.
--
-- max_density_du_acre is DERIVED (43560 / min_lot_sqft), not directly quoted from the ordinance
-- (the source PDF gives min lot size, not a density figure) — flagged via lower confidence_score
-- (0.75) and documented in ordinance_section. parking_per_unit=2.0 follows the same FL-typical
-- single-family default already used (uncited) in the existing Brooksville R-1A row for this
-- county (precedent set 2026-02-08). max_far intentionally NULL — not applicable to single-family
-- residential districts, consistent with the existing Brooksville R-1A row's treatment.
--
-- I impact (live-verified via pencil_dod_evaluate_county('hernando')):
--   card_complete 7/23 (30.4%) -> 10/23 (43.5%)
--
-- STILL UNRESOLVED (left unzoned, no guessing): 3 parcels zoned PDP(SF) (3407 Dow Ln, 30541
-- Satinleaf Run, 9824 Horizon Dr) — the county GIS layer's ZONE_NOTES field for these returns
-- literally "NO CASE NUMBER", meaning the specific Planned Development ordinance/case that sets
-- their dimensional standards cannot be traced through the GIS layer; would need a Hernando
-- County Planning Dept case-file lookup. 1 parcel zoned AR2 (32350 Marchmont Cir) — standards
-- live in County LDC Appendix A Art. IV §13 (Agricultural/Rural districts), but both the primary
-- mirror (hernandocounty.elaws.us, HTTP 503 throughout this session) and Municode direct fetch
-- (HTTP 403, bot-blocked) were unavailable. Source is real and findable; just not fetchable in
-- this session's window.

INSERT INTO jurisdictions (name, county, state, county_name, active, co_no, data_source, municode_url)
VALUES ('Hernando County (Unincorporated)', 'Hernando', 'FL', 'Hernando', true, 27,
        'shard7-hernando-county-gis-2026-07-02',
        'https://hernandocounty.us/media/p54a0efr/residential-dimension-requirements.pdf')
ON CONFLICT DO NOTHING;
-- NOTE: idempotent-replay caveat — jurisdictions has no unique constraint on (name,county), so a
-- second run of this INSERT would create a duplicate row. Applied once live 2026-07-02 (id=1330).

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
VALUES
  (1330, 'R1A', 'Residential (County) R1A', 'Residential', 'Hernando County unincorporated single-family residential district'),
  (1330, 'R1C', 'Residential (County) R1C', 'Residential', 'Hernando County unincorporated single-family residential district');
-- Applied live: R1A -> id=11256, R1C -> id=11257.

INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, front_setback_ft, side_setback_ft,
  rear_setback_ft, max_height_ft, max_stories, max_lot_coverage_pct, max_density_du_acre,
  parking_per_unit, source_url, confidence_score, ordinance_section
) VALUES
  (11256, 6000, 60.0, 25.0, 10.0, 20.0, 35, 2, 35.0, 7.26, 2.0,
   'https://hernandocounty.us/media/p54a0efr/residential-dimension-requirements.pdf', 0.75,
   'Appendix A Art. IV (Residential Dimension Requirements) - R1A row; max_density_du_acre derived from min_lot_sqft (43560/6000), not directly quoted; parking_per_unit is FL-typical SF default per existing Brooksville R-1A precedent, not county-cited'),
  (11257, 10000, 75.0, 25.0, 10.0, 20.0, 35, 2, 35.0, 4.36, 2.0,
   'https://hernandocounty.us/media/p54a0efr/residential-dimension-requirements.pdf', 0.75,
   'Appendix A Art. IV (Residential Dimension Requirements) - R1C row; max_density_du_acre derived from min_lot_sqft (43560/10000), not directly quoted; parking_per_unit is FL-typical SF default per existing Brooksville R-1A precedent, not county-cited');

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('R01 221 17 3340 0280 0110', 1330, 'R1C', 'Residential (County) R1C', 'hernando_county_gis_zoning_flu-2026-07-02'),
  ('R01 221 17 3350 0389 0150', 1330, 'R1C', 'Residential (County) R1C', 'hernando_county_gis_zoning_flu-2026-07-02'),
  ('R36 223 18 2690 0180 0090', 1330, 'R1A', 'Residential (County) R1A', 'hernando_county_gis_zoning_flu-2026-07-02');

-- VERIFICATION (run after apply):
-- SELECT public.pencil_dod_evaluate_county('hernando');
-- Expected: E metric 73.9 -> 87.0 (parcel_linked 17 -> 20 of 23)
--           I metric 30.4 -> 43.5 (card_complete 7 -> 10 of 23)
