-- Gold Standard shard-6 refire, dispatch aa77d789, run6148: Naples R1-7.5 density,
-- materially different angle from the lot-size-inversion approach reverted earlier
-- the same day (20260724u migration, gold_standard_ultraloop_audit id=9229 survived=false).
--
-- Prior attempt: implied density via min-lot-size inversion (43,560/7,500=5.8 du/acre),
-- refuted because the LDC district text states no density figure and because
-- subdivision-yield density != per-parcel entitlement for an already-platted lot.
--
-- THIS fix uses a different source category entirely: the City of Naples
-- Comprehensive Plan (Ch. 163 F.S. mandated) Future Land Use Element, which states
-- a maximum density DIRECTLY (not derived from lot area) for the Future Land Use
-- Category that R1-7.5 falls under:
--   - naples2045.com Comprehensive Plan (updated 2024), F.L.U.E. page 5: intensity/
--     density table row "Low Density Residential -- 0-6 dwelling units per acre"
--   - F.L.U.E. page 17, Policy 1-1(b): "'Low Density Residential' areas ... intended
--     to accommodate single-family or other similar residential uses of up to a
--     maximum of six (6) dwelling units per net acre"
--   - F.L.U.E. page 25: the comp plan's own annexation zoning-conversion table
--     states directly "RSF-4 -> R1-7.5 -> Low Density Residential"
--   - Corroborated via live City of Naples ArcGIS REST spatial crosswalk
--     (g.naplesgov.com/arcgis/rest/services/Planning/{Zoning,FutureLandUse}/MapServer/0):
--     area-weighted overlap of all 18 R1-7.5 zoning polygons citywide against the
--     FutureLandUse layer = 97.3% within CATEGORY=RESIDENTIAL/SUBCATEGORY=LOW DENSITY.
--
-- Adversarially verified: independent refuter re-fetched the PDF and both ArcGIS
-- layers itself, redid the polygon crosswalk properly (all 18 polygons, area-weighted,
-- not 2 cherry-picked points), and found the F.L.U.E. 25 conversion table as a third
-- independent corroborating line the original claim hadn't cited. survived=true.
-- gold_standard_ultraloop_audit id=9303.
--
-- Confidence: CONFIRMED (1.0). Live DB effect (verified): collier G density
-- sub-metric 98.8 -> 100.0. Letter G stays FAIL, correctly gated by the unrelated,
-- separately-diagnosed C-4/C-5 FAR structural gap (LDC regulates FAR per-use, not
-- per-district -- schema limitation, out of scope for this fix).

UPDATE zone_standards
SET max_density_du_acre = 6,
    source_url = 'https://www.naples2045.com/wp-content/uploads/2025/08/1-Current-City-of-Naples-Comprehensive-Plan-updated-2024.pdf (FLUE pages F.L.U.E. 5, 17, 25)',
    ordinance_section = 'Comp Plan FLUE Policy 1-1(b), Low Density Residential (0-6 du/net acre); annexation conversion table (F.L.U.E. 25) states RSF-4 -> R1-7.5 -> Low Density Residential',
    confidence_score = 1.0
WHERE zoning_district_id = 6470;  -- Naples R1-7.5
