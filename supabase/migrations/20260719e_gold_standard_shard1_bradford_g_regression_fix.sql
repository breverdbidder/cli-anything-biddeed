-- Gold Standard shard-1 (dispatch 42aac1fb) continuation: fix a live G
-- regression introduced by migration 20260719b (bradford_zoning_substrate).
--
-- That migration added 4 real parcel_zones rows (zone codes A-2 x3,
-- RSF/MH-1 x1) without corresponding zone_standards rows. Per
-- v_zoning_district_applicability, both Agricultural and Residential
-- categories are density_applicable=true by default (only commercial/
-- industrial are density-exempt), so these 4 parcels counted as
-- "applicable but missing density data" and dropped bradford's G metric
-- from 100.0% (3/3, on the pre-existing fake bootstrap rows) to 42.9% (3/7).
--
-- Fix: backfill REAL ordinance-sourced max_density_du_acre (+ min_lot_sqft)
-- for the two new district codes, live-fetched this session:
--   Bradford County A-2 ("Agricultural, near-urban comp-plan areas"):
--     LDR Appx A Art.4 Sec.4.5.6 "Minimum lot area: Five acres" (base
--     standard; a conditional 1-acre exception exists under comp-plan
--     policy I.2.2 but is not the district-wide default) -> 217,800 sf
--     min lot, 0.2 du/acre.
--   Town of Brooker RSF/MH-1: LDR Sec.4.7.6 "Minimum lot area 20,000
--     square feet" -> 2.18 du/acre (43,560 / 20,000).

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 217800, 0.2,
       'shard1_42aac1fb_continuation/VERIFIED:library.municode.com/fl/bradford_county Appx A Art.4 Sec.4.5.6 (base 5-acre min lot standard)',
       'Sec. 4.5.6', 0.9
FROM zoning_districts zd
JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE j.name = 'Unincorporated Bradford County' AND j.county = 'Bradford' AND zd.code = 'A-2'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);

INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, max_density_du_acre, source_url, ordinance_section, confidence_score)
SELECT zd.id, 20000, 2.18,
       'shard1_42aac1fb_continuation/VERIFIED:ncfrpc.org/MapsAndPlans/CitiesAndTowns/Brooker/LDR_Brooker19_Salmon.pdf Sec.4.7.6 (20,000sf min lot)',
       'Sec. 4.7.6', 0.9
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 987 AND zd.code = 'RSF/MH-1'
  AND NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id);
