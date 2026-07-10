-- GOLD STANDARD shard11 — bay county — G fix (unincorporated Bay County zoning districts)
-- dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af
--
-- Root cause: jurisdiction_id=1332 (Unincorporated Bay County) had ZERO rows in
-- zoning_districts, so 16 parcel_zones rows (R-1, R-2, R-5, C-1, C-3A, CSVH)
-- failed the LEFT JOIN in v_zoning_gold_standard_kpi_v3, defaulted to
-- applicable=true via COALESCE with NULL max_far/max_density, and dragged
-- down the density/far percentages that feed letter G.
--
-- Source: Bay County official "Zoning Bulk Regulations" table, BOCC-approved
-- 09/21/04, last revised 12/20/22, published at:
--   https://www.baycountyfl.gov/DocumentCenter/View/3008/Planning-and-Zoning-Bulk-Regulations-
-- Values below are transcribed VERBATIM from that PDF (fetched live this
-- session, saved to /tmp/bay_shard11/bulk_regs.pdf). No values invented.
--
-- R-1  Single-Family: density 8 du/acre (Urban), setbacks front20/side5/rear10,
--      no FAR (residential, backslash in source table = not applicable)
-- R-2  Single-Family & Duplex: density 15 du/acre (Urban), setbacks front20/side5/rear10
-- R-5  Multi-family: density 25 du/acre (Urban Service Area outside Coastal
--      Planning Area/BSTZ per footnote 9; capped at 15 du/acre inside BSTZ —
--      we record the general 25 du/acre figure per the primary table cell),
--      setbacks front25/side10/rear10, height 100ft (Urban)
-- C-1  Neighborhood Commercial: FAR 100%, setbacks front20/side5/rear20, height 35ft
-- C-3A General Commercial Low: FAR 100%, setbacks front25/side5/rear20, height 100ft
-- CSVH Conservation Habitation: density 2 du/acre (urban/suburban service areas,
--      footnote 12), FAR 40%, setbacks front25/side10/rear25, height 50ft,
--      max lot coverage 50%, min lot area 21,780 sqft (1/2 acre)

SET statement_timeout = 0;

BEGIN;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, effective_date)
VALUES
  (1332, 'R-1',  'Single-Family',                       'Residential', 'Zoning Bulk Regulations', '2022-12-20'),
  (1332, 'R-2',  'Single-Family and Duplex Dwellings',  'Residential', 'Zoning Bulk Regulations', '2022-12-20'),
  (1332, 'R-5',  'Multi-family',                        'Residential', 'Zoning Bulk Regulations', '2022-12-20'),
  (1332, 'C-1',  'Neighborhood Commercial',             'Commercial',  'Zoning Bulk Regulations', '2022-12-20'),
  (1332, 'C-3A', 'General Commercial Low',              'Commercial',  'Zoning Bulk Regulations', '2022-12-20'),
  (1332, 'CSVH', 'Conservation Habitation',             'Conservation','Zoning Bulk Regulations', '2022-12-20')
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, min_lot_width_ft, max_height_ft,
  front_setback_ft, side_setback_ft, rear_setback_ft,
  max_lot_coverage_pct, max_impervious_pct, max_far, max_density_du_acre,
  source_url, ordinance_section, effective_date, confidence_score
)
SELECT d.id, v.min_lot_sqft, v.min_lot_width_ft, v.max_height_ft,
       v.front_setback_ft, v.side_setback_ft, v.rear_setback_ft,
       v.max_lot_coverage_pct, v.max_impervious_pct, v.max_far, v.max_density_du_acre,
       'https://www.baycountyfl.gov/DocumentCenter/View/3008/Planning-and-Zoning-Bulk-Regulations-',
       'Zoning Bulk Regulations table', '2022-12-20', 0.95
FROM (VALUES
  ('R-1',  NULL::numeric, NULL::numeric, 45::numeric, 20::numeric, 5::numeric, 10::numeric, NULL::numeric, 60::numeric, NULL::numeric, 8::numeric),
  ('R-2',  NULL, NULL, 45, 20, 5, 10, NULL, 60, NULL, 15),
  ('R-5',  NULL, NULL, 100, 25, 10, 10, NULL, 75, NULL, 25),
  ('C-1',  NULL, 70, 35, 20, 5, 20, NULL, 60, 1.00, NULL),
  ('C-3A', NULL, 100, 100, 25, 5, 20, NULL, 75, 1.00, NULL),
  ('CSVH', 21780, 100, 50, 25, 10, 25, 50, NULL, 0.40, 2)
) AS v(code, min_lot_sqft, min_lot_width_ft, max_height_ft, front_setback_ft, side_setback_ft, rear_setback_ft, max_lot_coverage_pct, max_impervious_pct, max_far, max_density_du_acre)
JOIN zoning_districts d ON d.jurisdiction_id = 1332 AND d.code = v.code
WHERE NOT EXISTS (SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = d.id);

COMMIT;
