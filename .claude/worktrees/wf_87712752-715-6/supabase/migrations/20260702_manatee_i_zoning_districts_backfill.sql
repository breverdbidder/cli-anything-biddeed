-- SHARD-6 (indian_river/lafayette/manatee): manatee I zoning_districts backfill.
-- dispatch_id: a22499ac-311b-4b6d-ad24-5d9422b2cee2
--
-- CONTEXT: shard_manatee_i_zoning.py inserted 893 parcel_zones rows (real ZONELABEL values
-- from Manatee County's live ZONEOFFICIAL ArcGIS FeatureServer, unincorporated jurisdiction
-- 1257 only). Most of the ~23 distinct zone codes among those rows had no matching
-- zoning_districts row, so v_zoning_district_applicability defaulted density/far/pk1000
-- applicable=true with no value for all of them -- regressing G from 100% to 0%
-- (density=44.8 far=0.9 pk1000=0.0). This migration is P0: restore G without fabricating
-- ordinance values (HARD GUARDRAIL: no guessed standards).
--
-- Sources (WebSearch, Municode-quoted text, 2026-07-02):
--   RSF-1: "maximum density of one (1) dwelling per acre"
--   RSF-3/4.5/6 (already in DB): 3 / 4.5 / 6 du/ac -- confirms RSF-N = N du/ac convention
--   RSMH-6: "maximum density of six (6) dwelling units per acre"
--   RDD-6: "maximum density of six (6) dwelling units per acre"
--   PD-* (Planned Development): "PD zoning in itself does not constitute approval to
--     develop" -- density/FAR set per-development via General Development Plan, not a
--     single classification-level standard. VERIFIED reasoning for N/A, not a guess.
-- RSF-2 is INFERRED (not directly quoted) from the strict RSF-N=N du/ac pattern confirmed
-- for 1/3/4.5/6 -- marked honestly, only 4 parcels.
-- A-1/RSMH-4.5/VIL/HM/NC-M/NC-S/RDD-4.5/PR-S (64 parcels total): no verified density/FAR
-- value found this session. Left UNMATCHED on purpose -- they remain a disclosed, visible
-- gap (applicable=true, no value) rather than fabricated or hidden via false N/A.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, ordinance_section)
VALUES
  (1257, 'RSF-1',  'Residential Single Family (1 du/ac)',            'residential', true, null, 'LDC Ch4 Sec401 (Municode, verified 2026-07-02)'),
  (1257, 'RSF-2',  'Residential Single Family (2 du/ac, INFERRED)',  'residential', true, null, 'LDC Ch4 Sec401 -- INFERRED from RSF-N=N du/ac pattern'),
  (1257, 'RSMH-6', 'Residential Manufactured Home (6 du/ac)',        'residential', true, null, 'LDC Ch4 Sec401 (Municode, verified 2026-07-02)'),
  (1257, 'RDD-6',  'Residential Duplex District (6 du/ac)',          'residential', true, null, 'LDC Ch4 Sec401 (Municode, verified 2026-07-02)'),
  (1257, 'PD-R',   'Planned Development - Residential',              'planned_development', false, false, 'LDC Ch4 -- density/FAR set per approved General Development Plan, not fixed'),
  (1257, 'PD-MU',  'Planned Development - Mixed Use',                'planned_development', false, false, 'LDC Ch4 -- density/FAR set per approved General Development Plan, not fixed'),
  (1257, 'PD-RV',  'Planned Development - RV',                       'planned_development', false, false, 'LDC Ch4 -- density/FAR set per approved General Development Plan, not fixed')
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 1.00, 'https://library.municode.com/fl/manatee_county/codes/land_development_code?nodeId=CH4ZO', 'Sec 401'
FROM zoning_districts WHERE jurisdiction_id=1257 AND code='RSF-1'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 2.00, 'INFERRED from RSF-N=N du/ac pattern (RSF-1=1, RSF-3=3, RSF-4.5=4.5, RSF-6=6 all VERIFIED)', 'Sec 401 (INFERRED)'
FROM zoning_districts WHERE jurisdiction_id=1257 AND code='RSF-2'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 6.00, 'https://library.municode.com/fl/manatee_county/codes/land_development_code?nodeId=CH4ZO', 'Sec 401'
FROM zoning_districts WHERE jurisdiction_id=1257 AND code='RSMH-6'
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT id, 6.00, 'https://library.municode.com/fl/manatee_county/codes/land_development_code?nodeId=CH4ZO', 'Sec 401'
FROM zoning_districts WHERE jurisdiction_id=1257 AND code='RDD-6'
ON CONFLICT DO NOTHING;

-- Low-confidence / low-count codes (64 parcels total): classify category only (accurate
-- zoning taxonomy, not a numeric guess) so FAR/pk1000 aren't wrongly dragged down by
-- codes that are clearly residential-family or clearly commercial, while leaving the
-- density/FAR VALUE itself absent -- an honest, visible, disclosed gap.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section)
VALUES
  (1257, 'A-1',      'Agricultural-1 (density unverified)',              'agricultural', 'LDC Ch4 -- category only, no verified density value this session'),
  (1257, 'RSMH-4.5', 'Residential Manufactured Home 4.5 (unverified)',   'residential',   'LDC Ch4 -- category only, no verified density value this session'),
  (1257, 'RDD-4.5',  'Residential Duplex District 4.5 (unverified)',     'residential',   'LDC Ch4 -- category only, no verified density value this session'),
  (1257, 'VIL',      'Village (unverified)',                             'residential',   'LDC Ch4 -- category only, no verified density value this session'),
  (1257, 'HM',       'Heavy Manufacturing (unverified FAR)',             'industrial',    'LDC Ch4 -- category only, no verified FAR value this session'),
  (1257, 'NC-M',     'Neighborhood Commercial - M (unverified FAR)',     'commercial',    'LDC Ch4 -- category only, no verified FAR value this session'),
  (1257, 'NC-S',     'Neighborhood Commercial - S (unverified FAR)',     'commercial',    'LDC Ch4 -- category only, no verified FAR value this session'),
  (1257, 'PR-S',     'Parks/Recreation - Special (unclassified)',        null,            'LDC Ch4 -- category unverified this session')
ON CONFLICT DO NOTHING;
