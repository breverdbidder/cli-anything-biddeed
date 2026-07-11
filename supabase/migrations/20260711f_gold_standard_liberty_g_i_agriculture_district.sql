-- Liberty County G+I: real Agriculture-district zoning for the single liberty parcel
-- (case 24-CA-22, parcel_id 0261S6W00725000, 20892 NE Burlington Rd, Hosford FL 32334).
--
-- JURISDICTION FINDING: jurisdictions.id=893 "Bristol" is the ONLY Liberty County
-- jurisdiction row in our DB. This is geographically wrong for this parcel: Bristol
-- (the town) is ~11.8 straight-line miles from the parcel's lat/lng (30.3600103,
-- -84.8051394 per multi_county_auctions), and FL GIO's live statewide cadastral
-- (services9.arcgis.com/Gh9awoU677aKree0/.../Florida_Statewide_Cadastral/FeatureServer/0,
-- queried 2026-07-11) confirms PHY_CITY="HOSFORD", PHY_ADDR1="20892 NE BURLINGTON RD",
-- DOR_UC="001" (Single Family), LND_SQFOOT=108028 (2.48 acres), CO_NO=49 (FL DOR's real
-- Liberty County code -- note jurisdictions.co_no=39 on the existing Bristol row is
-- inconsistent with this and is a pre-existing data quality issue, NOT fixed here as
-- it is out of scope for G/I). Liberty County does NOT have a separate "unincorporated
-- Liberty County" jurisdictions row, and we did not create one -- we attach this zoning
-- to jurisdiction_id=893 because it is the only Liberty County FK target that exists,
-- while documenting in this comment block that the governing ordinance is the COUNTY
-- LDC (which explicitly governs "unincorporated parts of the County" per its own
-- Chapter 5 Section 5.4), not a Bristol municipal code. No Bristol-specific municipal
-- zoning ordinance was located or used.
--
-- SOURCE (LDC): "2017 Liberty County Land Development Code", adopted via Ordinance
--   2017-01 (2017-05-09), consolidated PDF downloaded from
--   https://libertycountyfl.org/uploads/2026/01/LIBERTY-COUNTY-Land-Development-Code.pdf
--   (verified real via direct curl, 683,922 bytes, 138-page PDF, HTTP 200).
--   Chapter 4 "Land Use Districts and Development Standards", Section 4.4(A) "Agriculture":
--     "Purpose and Intent: These areas are predominantly in agricultural or
--      silvicultural use."
--     "Allowable uses: (a) Agricultural. (b) Residential, subject to the density
--      standards in the Plan or code. (c) Institutional... (d) Outdoor Recreational.
--      (e) Public Service/Utility. (f) Special Exception Uses: Borrow Pits..."
--     "Density: The density in Agriculture Land Use Categories shall not exceed one
--      (1) dwelling unit per ten (10) acres. Clustering down to 1 acre lots shall be
--      encouraged." (page 4-79/4-80 per doc pagination, PDF page 80)
--
-- CATEGORY-ASSIGNMENT CONFIDENCE (INFERRED, not directly verified against a FLUM/
--   zoning-boundary GIS layer): we could NOT access Liberty County's actual Future
--   Land Use Map GIS boundaries (no working county-specific ArcGIS zoning/FLUM REST
--   endpoint was found; PRISYM v2.0 ArcGIS webapp requires a browser session, and a
--   generic search returned a Liberty County, GEORGIA zoning ArcGIS app as a false
--   positive which we explicitly rejected). We assign "Agriculture" because: (1) the
--   LDC's own text shows every OTHER category is an explicitly bounded/named area
--   (Town Center = historical town centers; Rural Village = specific mapped suburban
--   areas; Industrial = 4 named sites near Bristol/Telogia/Hosford totaling ~225
--   acres, none matching this parcel's coordinates or DOR_UC=001 single-family use);
--   Agriculture is the LDC's residual/default classification covering the rural
--   majority of unincorporated Liberty County; (2) the parcel is a 2.48-acre single-
--   family lot (DOR_UC 001) on a rural county road, consistent with Agriculture's
--   "Residential, subject to density standards" allowance. This category assignment
--   is flagged INFERRED; the density figure itself (1 du/10 acres) is a VERIFIED
--   direct quote once Agriculture is the correct category.
--
-- FAR (max_far): Searched the full 138-page LDC PDF text for "floor area ratio" and
--   "FAR" -- ZERO occurrences anywhere in the document. Liberty County's LDC regulates
--   density (du/acre), intensity (% land coverage, only specified for non-Agriculture
--   categories), setbacks, and height (Schedule 1.0) instead of FAR. This is a genuine,
--   confirmed ordinance gap, not an oversight -- max_far is left NULL.
--
-- PARKING (parking_per_1000sf): LDC Section 4.8-1(D) "Table of Parking Spaces
--   Required" ties parking to dwelling units or specific commercial/institutional use
--   types (e.g. "Dwellings (single and two-family): Two (2) per dwelling unit";
--   "Banks, business or professional offices: One (1) per three hundred (300) square
--   feet of usable floor area"), never to a generic per-1000sf figure for residential
--   or agricultural use. Converting "2 per dwelling unit" to a per-1000sf figure would
--   require guessing an average dwelling size, which HARD GUARDRAILS forbid.
--   parking_per_1000sf is left NULL -- a genuine, honest ordinance gap.
--
-- NET EFFECT ON G: G requires density AND far AND pk1000 all non-NULL/passing
-- (LEAST-style gate per pencil_dod_evaluate_county). Density is now real and cited;
-- FAR and parking remain NULL because no such standard exists in the source
-- ordinance. G is expected to remain failing after this migration -- this is honest,
-- not a ghost-success. I is expected to move (card_complete requires zoning_districts
-- + zone_standards + parcel_zones linkage to exist for the parcel, independent of
-- whether every numeric field is populated) -- verify post-migration via
-- pencil_dod_evaluate_county and v_zoning_gold_standard_card before declaring VERIFIED.

BEGIN;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, created_at)
VALUES
  (893, 'AG', 'Agriculture',
   'agricultural',
   'Liberty County LDC Chapter 4, Section 4.4(A) Agriculture land use district. Predominantly agricultural/silvicultural use; residential allowed subject to density standards. Applied here to an unincorporated-Liberty-County rural parcel (Hosford, ~11.8 mi from Bristol town center) attached to jurisdiction_id=893 (Bristol) only because no separate unincorporated-Liberty-County jurisdictions row exists in this DB -- the governing ordinance is the county-wide LDC, not a Bristol municipal code. Category assignment (Agriculture vs. other LDC categories) is INFERRED from parcel characteristics (2.48 acres, DOR_UC=001 single-family, rural county road) in the absence of an accessible Liberty County FLUM/zoning-boundary GIS layer.',
   'Chapter 4, Section 4.4(A) Agriculture', now())
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, 0.10, NULL, NULL,
       'https://libertycountyfl.org/uploads/2026/01/LIBERTY-COUNTY-Land-Development-Code.pdf',
       'Chapter 4, Section 4.4(A)(3) Density: "The density in Agriculture Land Use Categories shall not exceed one (1) dwelling unit per ten (10) acres."',
       0.55, now()
FROM zoning_districts WHERE jurisdiction_id=893 AND code='AG'
ON CONFLICT DO NOTHING;

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, created_at)
VALUES (
  '0261S6W00725000', 893, 'AG', 'Agriculture',
  'liberty_ldc_agriculture_default_inferred_2026-07-11', now()
)
ON CONFLICT DO NOTHING;

COMMIT;
