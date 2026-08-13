-- GOLD STANDARD shard-5 charlotte-only, key charlotte-G (letter G, density sub-metric).
--
-- ROOT CAUSE (verified live via v_zoning_gold_standard_kpi_v3 for county='charlotte' this
-- session): parcels=169, density_applicable_parcels=168, density_na_parcels=1,
-- pct_density_of_applicable=86.9 (FAIL, need >=95.0 i.e. >=160 of 168). far_applicable_parcels=0
-- (FAR is N/A for all charlotte parcels, not a blocker). pk1000 already 100.0% (PASS).
--
-- Ranked the Charlotte zoning districts with parcels but NULL max_density_du_acre (join
-- parcel_zones -> zoning_districts -> zone_standards, county='charlotte', all jurisdiction_id=813
-- "unincorporated Charlotte County"):
--   MHC   (13807) 6 parcels  -- Sec. 3-9-37, Manufactured home conventional
--   AG    (13805) 5 parcels  -- Sec. 3-9-30, Agriculture
--   CG    (13397) 4 parcels  -- Sec. 3-9-42, Commercial general
--   PD    (13395) 2 parcels  -- Sec. 3-9-45, Planned development
--   RE5   (13808) 1 parcel   -- Sec. 3-9-32, Residential estate (RE-5 column)
--   RMF10 (13809) 1 parcel   -- Sec. 3-9-34, Residential multifamily (RMF-10 column)
--   BBI   (13806) 1 parcel   -- Sec. 3-9-52, Bridgeless Barrier Island
--   DOR-000 (11296, VAC-RES)   1 parcel -- DOR use-code crosswalk placeholder, NOT a real
--                                          Municode zoning district; no ordinance section exists
--                                          to source a density value from. Left as documented gap.
--   DOR-004 (11294, MFR-CONDO) 1 parcel -- same as above; DOR crosswalk placeholder. Left as gap.
--
-- SOURCE: library.municode.com/fl/charlotte_county/codes/code_of_ordinances, Part III Land
-- Development and Growth Management, Chapter 3-9 Zoning, Article II District Regulations.
-- (Direct fetch of library.municode.com and the charlottecounty-fl.elaws.us mirror both
-- failed from this sandbox -- SPA behind an auth'd content API on the former, no route to host
-- on the latter. Retrieved the live, current ordinance text -- sourced from and citing the same
-- library.municode.com URLs -- via the Zoneomics mirror at
-- zoneomics.com/code/charlotte-county-unincorporated-FL/chapter_2, which embeds the full
-- Article II chapter text server-side per section, each carrying its own Municode citation.)
--
-- Verified section text pulled this session, "Development standards" table per section:
--   Sec. 3-9-30 AG:    Density (units/acres) = "1 per 10 acres"      -> 0.1 du/acre
--   Sec. 3-9-32 RE-5:  Density (units/acres) = "1 per 5 acres"       -> 0.2 du/acre (RE-5 column)
--   Sec. 3-9-34 RMF-10: Density (units/acre) = 10                    -> 10 du/acre (RMF-10 column)
--   Sec. 3-9-37 MHC:   Density (units/acre)  = 5                     -> 5 du/acre
--   Sec. 3-9-42 CG:    Density (units/acre)  = 0                     -> 0 du/acre (commercial-only
--                       district, no residential density permitted by right -- a real ordinance
--                       value, not a missing one)
--   Sec. 3-9-52 BBI:   Density (units/acre)  = 1 (lots created on/after 10-22-1990)
--                                                                     -> 1 du/acre
--
-- PD (13395, 2 parcels) deliberately NOT backfilled: Sec. 3-9-45(c)(2)(a) states "The maximum
-- density permitted within a PD shall be limited to the density indicated on the adopted future
-- land use map for the underlying land use" -- i.e. PD has no single fixed district-level
-- density in the ordinance; it is parcel/FLU-dependent. Any single number here would be a
-- fabrication. Left as a documented, genuinely-open gap.
--
-- Expected result: 146 currently-populated + 18 newly-populated (AG 5 + MHC 6 + CG 4 + BBI 1 +
-- RE5 1 + RMF10 1) = 164 of 168 applicable parcels = 97.6% (>=95.0 threshold, PASS). Remaining
-- gap = PD (2 parcels, genuinely FLU-dependent, no fixed ordinance value exists) + DOR-000/
-- DOR-004 (2 parcels, DOR crosswalk placeholders with no corresponding Municode section).

INSERT INTO public.zone_standards (
  zoning_district_id, max_density_du_acre, source_url, ordinance_section,
  confidence_score, scraped_at
)
VALUES
  -- Sec. 3-9-30, Agriculture (AG): "Density (units/acres) 1 per 10 acres" = 0.1 du/acre.
  (13805, 0.1,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE',
   '3-9-30', 0.85, now()),

  -- Sec. 3-9-32, Residential estate (RE), RE-5 column: "Density (units/acres) 1 per 5 acres"
  -- = 0.2 du/acre.
  (13808, 0.2,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE',
   '3-9-32', 0.85, now()),

  -- Sec. 3-9-34, Residential multifamily (RMF), RMF-10 column: "Density (units/acre) 10".
  (13809, 10,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE',
   '3-9-34', 0.85, now()),

  -- Sec. 3-9-37, Manufactured home conventional (MHC): "Density (units/acre) 5".
  (13807, 5,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE',
   '3-9-37', 0.85, now()),

  -- Sec. 3-9-42, Commercial general (CG): "Density (units/acre) 0" -- a real ordinance value;
  -- CG permits no residential density by right.
  (13397, 0,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE',
   '3-9-42', 0.85, now()),

  -- Sec. 3-9-52, Bridgeless Barrier Island (BBI): "Density (units/acre) 1" (lots created on/after
  -- 10-22-1990 column; the pre-1990 column reads "1 unit/lot" which is not an acre-based rate).
  (13806, 1,
   'https://library.municode.com/fl/charlotte_county/codes/code_of_ordinances?nodeId=PTIIILADEGRMA_CH3-9ZO_ARTIIDIRE',
   '3-9-52', 0.85, now())
ON CONFLICT DO NOTHING;
