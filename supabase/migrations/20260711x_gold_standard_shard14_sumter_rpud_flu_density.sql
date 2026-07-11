-- ============================================================
-- Gold Standard shard-14 (sumter) RE-FIRE -- RPUD FLU + density residual
-- Re-fire of dispatch 8ee11dd1-d767-46a5-aa82-496902d6a9d8's residual
-- ============================================================
--
-- RESIDUAL BEING CLOSED: prior session (8ee11dd1) left zoning_districts
-- id=11471 (RPUD, jurisdiction=Sumter County/1325) with max_density_du_acre
-- = NULL because Sumter Land Development Code Sec. 13-422(c) ties RPUD
-- density to the parcel's Future Land Use (FLU) category, and
-- parcel_zones.future_land_use was NULL for the 3 affected parcels
-- (D03F058, G03A014, D09E270) -- nothing to cross-reference.
--
-- NEW SOURCE FOUND THIS SESSION (VERIFIED live, not previously checked):
-- Sumter County's own ArcGIS Server hosts a DEDICATED unincorporated-county
-- Future Land Use layer that the prior session did not find (prior session
-- only checked the "Interactive/FLU_Zoning" FeatureServer's municipal FLU
-- layers 0-4, which are Bushnell/Center Hill/Coleman/Webster/Wildwood only
-- -- none cover unincorporated county parcels like these 3):
--
--   https://gis.sumtercountyfl.gov/sumtergis/rest/services/
--     DevelopmentServices/Development_Services/MapServer/5
--   ("Unincorporated Future Land Use" layer -- confirmed live via
--   ?f=json describe call, HTTP 200)
--
-- This layer has NO parcel-id attribute field (only Current_FLU/Prior_FLU/
-- Past_FLU/ACREAGE/geometry), so it was queried by spatial point-intersect
-- using each parcel's polygon centroid (computed from the exact ring
-- coordinates already on file in zoning_districts.source_url /
-- prior migration's Zoning FeatureServer/11 query, same spatial reference
-- wkid 102659/2237). Each centroid was independently sanity-checked
-- against Zoning FeatureServer/11 (attribute Parcel=<id>) to confirm the
-- point actually lands inside the correct parcel polygon before trusting
-- the spatial join -- all 3 confirmed exact Parcel-name match.
--
-- LIVE QUERY RESULTS (2026-07-11), all HTTP 200, features returned:
--   D03F058  Current_FLU=MU  (Mixed Use), ACREAGE=5.71
--   G03A014  Current_FLU=MU  (Mixed Use), ACREAGE=16.20
--   D09E270  Current_FLU=MU  (Mixed Use), ACREAGE=50.68
--
-- DENSITY VALUE: Sumter's Chapter 1 Future Land Use Element GOPs PDF
-- (https://www.sumtercountyfl.gov/DocumentCenter/View/41855/
-- Chapter-1-Future-Land-Use-GOPs, live fetch HTTP 200, 2762566 bytes,
-- text-extracted via pypdf) Table 1.1 "Future Land Uses Maximum Density
-- or Intensity" gives the generic "Mixed-use" category as EITHER
-- 4 du/acre (outside UDA) or 8 du/acre (inside UDA), both "Must be
-- developed as a Planned Unit Development or Development of Regional
-- Impact per Policy 1.2.8" -- exactly the RPUD linkage Sec. 13-422(c)
-- requires. HOWEVER, all 3 parcels sit within The Villages (addresses:
-- 2621 Caribe Dr / 1575 Hollyberry Pl / 3288 Shelby St, The Villages FL
-- 32162 -- on file in multi_county_auctions from prior sessions), which
-- is governed by a MORE SPECIFIC project overlay policy in the same
-- Comprehensive Plan: Policy 1.11.1 (Tri-County Villages DRI Community
-- Plan) and Policy 1.11.2 (Villages of Sumter DRI Community Plan), pages
-- 36-38 of the same PDF. BOTH overlay policies independently state the
-- IDENTICAL maximum residential density for their respective PUD areas:
--   "The maximum residential density for the project is 5.4 residential
--   dwelling units per net residential area as applied throughout the
--   project" -- verbatim, same figure, in both Policy 1.11.1 and
--   Policy 1.11.2. Since the generic Table 1.1 MU row is explicitly
--   superseded within a designated DRI/PUD community-plan area (that is
--   the entire mechanism Sec. 13-422(c) and Policy 1.2.8 point to), and
--   both possible Villages overlays land on the same number, 5.4 du/acre
--   is used here as the applicable, cross-verified, project-specific
--   value rather than the coarser 4/8 generic range.
--
-- CONFIDENCE: VERIFIED for FLU="MU" (live spatial query, sanity-checked
-- against independent zoning-layer parcel match). VERIFIED for the 5.4
-- du/acre figure existing in the Comp Plan text (live PDF fetch + text
-- extraction). INFERRED (not VERIFIED) that these exact 3 parcels fall
-- within the Villages of Sumter PUD / Tri-County Villages PUD boundary
-- specifically (no GIS layer was found that draws that specific DRI
-- boundary as a separate queryable attribute -- Current_FLU only
-- distinguishes generic "MU" from other categories, not "MU-in-Villages-
-- DRI" vs "MU-elsewhere"). This inference is well-supported (all 3
-- addresses are literally "The Villages, FL 32162", the county's own FLU
-- layer confirms MU zoning contiguous with RPUD, and both possible DRI
-- overlays give the same number) but is flagged INFERRED rather than
-- VERIFIED per Honesty Protocol, since no live source draws the DRI
-- polygon boundary itself for direct point-in-polygon confirmation.

UPDATE parcel_zones
SET future_land_use = 'MU',
    source = source || ' | future_land_use=MU sourced from Sumter County GIS DevelopmentServices/Development_Services MapServer layer 5 (Unincorporated Future Land Use), spatial point-intersect query on parcel centroid, live 2026-07-11'
WHERE parcel_id IN ('D03F058', 'G03A014', 'D09E270')
  AND future_land_use IS NULL;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
VALUES (
  11471,
  5.40,
  'https://www.sumtercountyfl.gov/DocumentCenter/View/41855/Chapter-1-Future-Land-Use-GOPs',
  'Sumter County Unified Comprehensive Plan 2023, Chapter 1 Future Land Use Element, Policy 1.11.1 (Tri-County Villages DRI Community Plan) / Policy 1.11.2 (Villages of Sumter DRI Community Plan): "The maximum residential density for the project is 5.4 residential dwelling units per net residential area as applied throughout the project" -- applied here per Sec. 13-422(c) RPUD-to-FLU cross-reference, FLU=MU (Mixed Use, Table 1.1) for parcels D03F058/G03A014/D09E270, all located within The Villages DRI/PUD community-plan area. INFERRED (not VERIFIED) that these specific parcels fall within the Villages-of-Sumter vs Tri-County-Villages DRI boundary specifically -- both give the identical 5.4 du/acre figure so the distinction does not change the value.',
  0.75,
  now()
)
ON CONFLICT DO NOTHING;
