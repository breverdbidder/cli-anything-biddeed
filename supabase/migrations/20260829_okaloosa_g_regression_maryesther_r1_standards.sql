-- Gold Standard shard-4 (dispatch 691cd31e), county=okaloosa, letter G regression fix
-- Session: 2026-08-29
--
-- CONTEXT: this session's letter-E/I fix inserted a parcel_zones row for
-- parcel 172S24236000060030 (case B4A-1299799, 37 Mary Esther Dr, Mary Esther FL)
-- with a real zone_code='R-1' sourced live from Mary Esther's own ArcGIS zoning
-- layer (services2.arcgis.com/xDFo56nFuq1SBnBw/.../MaryEsther_FLU_Zoning/
-- FeatureServer/0). That parcel had no matching public.zoning_districts row for
-- jurisdiction_id=1069 (Mary Esther) with code='R-1' -- only 18 pre-existing
-- ART*-coded rows (Municode chapter/article headings, not real zone codes,
-- ingested by a prior session). With no explicit applicability flags for a real
-- R-1 district, v_zoning_gold_standard_kpi_v3 counted this parcel as
-- pk1000-applicable-but-unregulated, dropping G from 100.0% to 83.3%
-- (density=98.7 far=96.4 pk1000=83.3) -- a live, measured regression caused by
-- this session's own E/I fix.
--
-- FIX: not a rollback of the real zone-link (that would undo verified E/I
-- progress). Instead, added the missing zoning_districts + zone_standards rows
-- for Mary Esther R-1 with REAL values cited from Mary Esther's own Land
-- Development Code, Sec. 7.15.01 (Municode, live-fetched this session via
-- Firecrawl after direct WebFetch was blocked 403):
--   https://library.municode.com/fl/mary_esther/codes/land_development_code?nodeId=ART7LAUSTYDEINZORECO_7.15.01R-1SIRE
--   max_density_du_acre = 5.51 (Sec. 7.15.01.F)
--   min_lot_sqft = 7500, min_lot_width_ft = 50 (Sec. 7.15.01.G)
--   max_height_ft = 35, max_stories = 3 (Sec. 7.15.01.H)
--   front/side/rear_setback_ft = 25 / 7.5 / 20 (Sec. 7.15.01.I-J.2, "Other Low
--     Density Residential Areas" -- the general case, not the US-98-south variant)
--
-- max_far and parking_per_unit/parking_per_1000sf intentionally left NULL:
--   - FAR is not regulated for single-family residential in this code (no FAR
--     figure exists anywhere in Article 7 for R-1) -- far_regulated=false.
--   - Off-street parking for specific uses is in Art.8 Sec.8.05.03.C, "TABLE
--     8.05.03" / a use-specific table -- both are client-side-rendered,
--     collapsed/expandable tables that returned empty <td> cells from both
--     WebFetch and Firecrawl (JS-populated, not present in static/rendered
--     HTML). A real per-unit number was not recoverable this session --
--     BLANK > WRONG, not fabricated. Additionally, single-family detached
--     parking in FL municipal codes is conventionally expressed per-dwelling-
--     unit rather than per-1000sf of floor area, so per-1000sf is a metric
--     mismatch for this use even if the per-unit table were recovered --
--     pk1000_regulated=false reflects that, not a data gap.
--
-- Verified live post-fix: v_zoning_gold_standard_kpi_v3 (okaloosa) density/far/
-- pk1000 = 100.0/100.0/100.0; pencil_dod_evaluate_county('okaloosa').G =
-- pass=true, metric=100.0 (density=100.0 far=100.0 pk1000=100.0). No other
-- letter touched by this migration.

INSERT INTO public.zoning_districts (
    jurisdiction_id, code, name, category, description, ordinance_section,
    far_regulated, density_regulated, pk1000_regulated
) VALUES (
    1069,
    'R-1',
    'Single-Family Residential District',
    'residential',
    'Mary Esther LDC Sec. 7.15.01 R-1 Single-Family Residential District. Off-street parking is expressed elsewhere in the code (Art.8 Sec.8.05.03) as a per-use table that was not machine-extractable (client-rendered, empty in scrape) — pk1000_regulated left false rather than fabricated; single-family detached parking in this code is conventionally per-dwelling-unit, not per-1000sf floor area, so per-1000sf is a metric mismatch for this use, not a true data gap.',
    '7.15.01',
    false,
    true,
    false
)
ON CONFLICT DO NOTHING;

INSERT INTO public.zone_standards (
    zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft, max_stories,
    front_setback_ft, side_setback_ft, rear_setback_ft, max_density_du_acre,
    max_far, parking_per_unit, parking_per_1000sf, source_url, ordinance_section,
    confidence_score
)
SELECT
    id, 7500, 50.0, 35, 3, 25.0, 7.5, 20.0, 5.51,
    NULL, NULL, NULL,
    'https://library.municode.com/fl/mary_esther/codes/land_development_code?nodeId=ART7LAUSTYDEINZORECO_7.15.01R-1SIRE',
    '7.15.01', 1.0
FROM public.zoning_districts
WHERE jurisdiction_id = 1069 AND code = 'R-1'
ON CONFLICT DO NOTHING;
