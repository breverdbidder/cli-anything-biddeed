-- SHARD-11 (miami_dade) I closeout, final parcel: E-M (Palmetto Bay).
-- dispatch_id: 7a6b2043-0106-46ec-8afa-c8362cb2b9bc
--
-- The ULTRALOOP research workflow's E-M finding was blocked from the primary
-- Municode text (403/503) and its specific numeric claims (32% lot coverage,
-- 68% open space, 35ft/2 story) were REJECTED by the adversarial refuter as
-- unsourced. This session independently re-fetched Palmetto Bay's OWN
-- official zoning FAQ page directly (https://www.palmettobay-fl.gov/1674/E-M-
-- Zoning-District, HTTP 200, fetched 2026-07-02) rather than relying on the
-- subagent's account -- confirms the 32% lot coverage and 35ft/2-story
-- figures verbatim, plus a minimum lot size of 15,000 net sq ft, and no
-- mention of FAR anywhere on the page (lot coverage % and height/stories are
-- the governing intensity controls, the same pattern already established for
-- every other single-family residential district in this dataset: RU-1,
-- RU-2, R-1, T3-R).
--
-- category='residential', far_regulated=false follow directly from the
-- above. density_regulated=true with max_density_du_acre computed from the
-- confirmed 15,000 sq ft minimum lot size (43,560 sq ft/acre / 15,000 =
-- 2.9 du/acre) -- arithmetic on a verified ordinance fact, not a guess.
INSERT INTO jurisdictions (name, county, county_name, state)
SELECT 'Palmetto Bay', 'Miami-Dade', 'Miami-Dade', 'FL'
WHERE NOT EXISTS (
  SELECT 1 FROM jurisdictions
  WHERE name = 'Palmetto Bay' AND lower(coalesce(county_name, county)) = 'miami-dade'
);

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated, ordinance_section)
SELECT j.id, 'E-M', 'Estate Modified Single Family District', 'residential', false, true,
       'Palmetto Bay Planning & Zoning FAQ, E-M Zoning District'
FROM jurisdictions j
WHERE j.name = 'Palmetto Bay' AND lower(coalesce(j.county_name, j.county)) = 'miami-dade'
  AND NOT EXISTS (SELECT 1 FROM zoning_districts d WHERE d.jurisdiction_id = j.id AND d.code = 'E-M');

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, min_lot_sqft, max_lot_coverage_pct, max_height_ft, source_url, ordinance_section)
SELECT d.id, 2.90, 15000, 32, 35,
       'https://www.palmettobay-fl.gov/1674/E-M-Zoning-District',
       'Palmetto Bay Planning & Zoning FAQ, E-M Zoning District'
FROM zoning_districts d
JOIN jurisdictions j ON j.id = d.jurisdiction_id
WHERE j.name = 'Palmetto Bay' AND lower(coalesce(j.county_name, j.county)) = 'miami-dade' AND d.code = 'E-M'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '33-5022-008-0170', j.id, 'E-M', 'Estate Modified Single Family District',
       'palmettobay_fl_gov_official_faq:shard11_miami_dade:2026-07-02', CURRENT_DATE
FROM jurisdictions j
WHERE j.name = 'Palmetto Bay' AND lower(coalesce(j.county_name, j.county)) = 'miami-dade'
  AND NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '33-5022-008-0170');
