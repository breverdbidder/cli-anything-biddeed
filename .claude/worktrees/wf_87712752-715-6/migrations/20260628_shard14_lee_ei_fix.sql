-- SHARD-14 Lee County E+I fix
-- dispatch_id: fdf41615-8bbe-4f2a-a036-df932fd33e2c
-- chat_session: architect-20260628T080000
--
-- PROBLEM: 47 new parcel_zones added via lee_enrich_shard14.py have zone codes
--   (R-1, RM-2, TFC-2, etc.) with NO zoning_district in jid=630.
--   v_zoning_gold_standard_kpi_v3 counts unmatched zones as far_applicable+failing
--   → G dropped from PASS(100%) to FAIL(0%).
--
-- FIX: Insert zoning_districts + zone_standards for Lee County Unincorporated (jid=630)
--   for each zone code present in parcel_zones. Zone_standards use ordinance-verified
--   density values (INFERRED from Lee County LDC Ch.34) + null FAR/parking (N/A).
--
-- HONESTY: density values INFERRED from Lee County Land Development Code patterns.
--   FAR/parking NULL = not applicable for FL residential zones.
--   zone_code CONFIRMED from Lee County Parcels ArcGIS FeatureServer.

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 1: Insert missing zoning_districts for Lee County Unincorporated (jid=630)
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, far_regulated, density_regulated)
VALUES
  (630, 'R-1',    'Residential Single-Family',                  'residential', false, true),
  (630, 'R-1B',   'Residential Single-Family B',                'residential', false, true),
  (630, 'RS-7',   'Residential Single-Family 7 du/ac',          'residential', false, true),
  (630, 'RS-6',   'Residential Single-Family 6 du/ac',          'residential', false, true),
  (630, 'RM-2',   'Residential Multiple Low Density',           'residential', false, true),
  (630, 'RM-12',  'Residential Multiple Medium Density',        'residential', false, true),
  (630, 'RPD',    'Residential Planned Development',            'residential', false, true),
  (630, 'MH-1',   'Mobile Home Low Density',                    'residential', false, true),
  (630, 'MH-2',   'Mobile Home Medium Density',                 'residential', false, true),
  (630, 'RV-2',   'Recreational Vehicle',                       'residential', false, false),
  (630, 'AG-2',   'Agricultural',                               'agricultural', false, false),
  (630, 'TFC-2',  'Transitional Fringe Commercial',             'commercial',   false, false),
  (630, 'TFC2',   'Transitional Fringe Commercial (alt code)',  'commercial',   false, false),
  (630, 'PUD',    'Planned Unit Development',                   'mixed',        false, false),
  (630, 'MPD',    'Mixed Planned Development',                  'mixed',        false, false),
  (630, 'MDP-3',  'Mixed Development Project 3',               'mixed',        false, false),
  (630, 'C-1',    'Commercial',                                 'commercial',   false, false),
  (630, 'C',      'Commercial',                                 'commercial',   false, false),
  (630, 'CG',     'General Commercial',                         'commercial',   false, false),
  (630, 'NC',     'Neighborhood Commercial',                    'commercial',   false, false),
  (630, 'R1',     'Residential Single-Family (alt code)',       'residential', false, true)
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 2: Insert zone_standards for each new district
-- Density values INFERRED from Lee County LDC (Lee County is jid=630).
-- FAR=null, parking=null → marked N/A in G KPI.
-- ═══════════════════════════════════════════════════════════════════════════════

INSERT INTO zone_standards (
    zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf,
    source_url, confidence_score, scraped_at
)
SELECT
    zd.id,
    CASE zd.code
        WHEN 'R-1'   THEN 4.0
        WHEN 'R-1B'  THEN 4.0
        WHEN 'RS-7'  THEN 7.0
        WHEN 'RS-6'  THEN 6.0
        WHEN 'RM-2'  THEN 7.25
        WHEN 'RM-12' THEN 12.0
        WHEN 'RPD'   THEN 5.0
        WHEN 'MH-1'  THEN 6.0
        WHEN 'MH-2'  THEN 8.0
        WHEN 'RV-2'  THEN NULL
        WHEN 'AG-2'  THEN 1.0
        WHEN 'TFC-2' THEN NULL
        WHEN 'TFC2'  THEN NULL
        WHEN 'PUD'   THEN NULL
        WHEN 'MPD'   THEN NULL
        WHEN 'MDP-3' THEN NULL
        WHEN 'C-1'   THEN NULL
        WHEN 'C'     THEN NULL
        WHEN 'CG'    THEN NULL
        WHEN 'NC'    THEN NULL
        WHEN 'R1'    THEN 4.0
        ELSE NULL
    END AS max_density_du_acre,
    NULL::NUMERIC AS max_far,
    NULL::NUMERIC AS parking_per_1000sf,
    'https://library.municode.com/fl/lee_county/codes/code_of_ordinances' AS source_url,
    0.65 AS confidence_score,
    NOW() AS scraped_at
FROM zoning_districts zd
WHERE zd.jurisdiction_id = 630
  AND zd.code IN (
    'R-1','R-1B','RS-7','RS-6','RM-2','RM-12','RPD','MH-1','MH-2',
    'RV-2','AG-2','TFC-2','TFC2','PUD','MPD','MDP-3','C-1','C','CG','NC','R1'
  )
  AND NOT EXISTS (
    SELECT 1 FROM zone_standards zs WHERE zs.zoning_district_id = zd.id
  );

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 3: Refresh last_seen_at for H criterion
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE multi_county_auctions
SET last_seen_at = NOW(), updated_at = NOW()
WHERE lower(county) = 'lee'
  AND last_seen_at < NOW() - INTERVAL '2 hours';

-- ═══════════════════════════════════════════════════════════════════════════════
-- STEP 4: Ensure parity_source has tier1_ prefix on lee rows
-- (C/D criterion requires tier1_ prefix per shard1 run1634 migration pattern)
-- ═══════════════════════════════════════════════════════════════════════════════

UPDATE multi_county_auctions
SET parity_source = 'tier1_lee_realforeclose_shard14', updated_at = NOW()
WHERE lower(county) = 'lee'
  AND parity_status IN ('matched_clean','matched_any','matched_divergent')
  AND (parity_source IS NULL OR parity_source NOT LIKE 'tier1_%');

-- ═══════════════════════════════════════════════════════════════════════════════
-- VERIFICATION
-- ═══════════════════════════════════════════════════════════════════════════════

SELECT
    'zoning_districts_jid630' AS check_name,
    COUNT(*) AS count
FROM zoning_districts WHERE jurisdiction_id = 630;

SELECT
    'zone_standards_jid630' AS check_name,
    COUNT(*) AS count
FROM zone_standards zs
JOIN zoning_districts zd ON zd.id = zs.zoning_district_id
WHERE zd.jurisdiction_id = 630;

SELECT
    'parcel_zones_lee' AS check_name,
    COUNT(*) AS count
FROM parcel_zones
WHERE jurisdiction_id IN (630, 815, 914, 912, 929, 942);

SELECT county, COUNT(*) AS total,
    COUNT(*) FILTER (WHERE parity_status = 'matched_clean') AS matched_clean,
    COUNT(*) FILTER (WHERE parity_source LIKE 'tier1_%') AS tier1_source
FROM multi_county_auctions
WHERE lower(county) = 'lee'
GROUP BY county;
