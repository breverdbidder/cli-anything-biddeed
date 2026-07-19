-- Gold Standard shard-1 (dispatch 42aac1fb) continuation: bradford zoning
-- substrate build. Fleet-wide diagnosis (2026-06-10) established that
-- letter G/I fleet-wide is a zoning-substrate loading problem, not an
-- auction-scraping problem. Bradford's specific gap: zoning_districts only
-- had codes for jurisdiction Starke (AGR, B-3, R-1A); Brooker (jurisdiction_id
-- 987) had ZERO rows, and no "Unincorporated Bradford County" jurisdiction
-- existed at all, even though 3 of 4 gap parcels are unincorporated (per
-- live Census TIGERweb point-in-polygon, layer 28 Incorporated Places).
--
-- Sources (all live-fetched and adversarially re-verified this session):
--   - Bradford County LDR (library.municode.com/fl/bradford_county, Appendix A
--     Art.4 Zoning Regulations) -- governs the unincorporated county.
--   - Town of Brooker's OWN LDR + Official Zoning Atlas (ncfrpc.org --
--     Brooker is NOT on municode; confirmed zero hits in municode's FL index).
--   - Bradford County's OWN Official Zoning Atlas (ncfrpc.org/.../BRZN24.pdf),
--     a georeferenced PDF (embedded NAD83 FL North State Plane GPTS control
--     points) used for coordinate-precise district-boundary overlay.
--   - Census TIGERweb (tigerWMS_Current/MapServer/28) for incorporation status.
--   - Bradford County Property Appraiser GIS (bradfordappraiser.com/gis/) for
--     parcel/owner/use-code confirmation (no zoning attribute exists there --
--     disclosed honestly; zone_code is atlas-derived, not a live GIS field).
--
-- Parcel-level results (adversarially verified, survived=true):
--   00077-0-00401 (Sec 1 T6S R20E) -- unincorporated (TIGERweb-confirmed) -- A-2
--   00441-0-00100 (Sec 25 T7S R20E) -- unincorporated (TIGERweb-confirmed) -- A-2
--   00868-0-01801 (Sec 11 T7S R21E) -- unincorporated (TIGERweb-confirmed) -- A-2
--   00273-0-01000 (Ward City Blk 15, Lots 10-11) -- INSIDE Brooker town limits
--     (TIGERweb GEOID 1208725) -- RSF/MH-1, via Brooker's own atlas + the 1904
--     Ward City plat overlay (bradfordappraiser.com/BradfordPA_PLATs/
--     WARD_CITY-page_1.pdf)
--
-- Baseline (pencil_dod_evaluate_county('bradford'), live before this migration):
--   I FAIL card_complete=0/5 (0.0%)

-- 1) Create the missing "Unincorporated Bradford County" jurisdiction
INSERT INTO jurisdictions (county, name, state, co_no)
SELECT 'Bradford', 'Unincorporated Bradford County', 'FL', 4
WHERE NOT EXISTS (
  SELECT 1 FROM jurisdictions WHERE county = 'Bradford' AND name = 'Unincorporated Bradford County'
);

-- 2) zoning_districts for Unincorporated Bradford County
--    Source: library.municode.com/fl/bradford_county, Appendix A -
--    Land Development Regulations, Article 4 - Zoning Regulations.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT j.id, v.code, v.name, v.category, v.description
FROM jurisdictions j
CROSS JOIN (VALUES
  ('CSV',      'Conservation',                                    'Conservation', 'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.3'),
  ('ESA-1',    'Environmentally Sensitive Areas',                  'Conservation', 'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.4'),
  ('ESA-2',    'Environmentally Sensitive Areas',                  'Conservation', 'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.4'),
  ('A-1',      'Agricultural (rural comp-plan areas)',             'Agricultural', 'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.5'),
  ('A-2',      'Agricultural (near-urban comp-plan areas)',        'Agricultural', 'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.5 -- confirmed zone for parcels 00077-0-00401, 00441-0-00100, 00868-0-01801'),
  ('RR',       'Rural Residential',                                'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.6'),
  ('RE',       'Residential, Estate',                              'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.7'),
  ('RSF-1',    'Residential, Single-Family',                       'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.8'),
  ('RSF-2',    'Residential, Single-Family',                       'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.8'),
  ('RSF-3',    'Residential, Single-Family',                       'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.8'),
  ('RSF/MH-1', 'Residential (Mixed), Single-Family/Mobile Home',   'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.9'),
  ('RSF/MH-2', 'Residential (Mixed), Single-Family/Mobile Home',   'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.9'),
  ('RSF/MH-3', 'Residential (Mixed), Single-Family/Mobile Home',   'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.9'),
  ('RMH-1',    'Residential, Mobile Home',                         'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.10'),
  ('RMH-2',    'Residential, Mobile Home',                         'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.10'),
  ('RMH-3',    'Residential, Mobile Home',                         'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.10'),
  ('RMH-P',    'Residential, Mobile Home Park',                    'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.11'),
  ('RMF-1',    'Residential, Multiple-Family',                     'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.12'),
  ('RMF-2',    'Residential, Multiple-Family',                     'Residential',  'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.12'),
  ('CN',       'Commercial, Neighborhood',                         'Commercial',   'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.13'),
  ('CG',       'Commercial, General',                              'Commercial',   'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.14'),
  ('CI',       'Commercial, Intensive',                            'Commercial',   'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.15'),
  ('ILW',      'Industrial, Light and Warehousing',                'Industrial',   'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.16'),
  ('I',        'Industrial',                                       'Industrial',   'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.17'),
  ('PRD',      'Planned Residential Development',                  'Planned',      'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.18'),
  ('PRRD',     'Planned Rural Residential Development',            'Planned',      'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.19'),
  ('PUD',      'Planned Unit Development',                         'Planned',      'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.20'),
  ('CHI',      'Commercial, Highway Interchange',                  'Commercial',   'Bradford County LDR (municode), Appx A Art.4 Sec.4.1.1 / Sec.4.21')
) AS v(code, name, category, description)
WHERE j.county = 'Bradford' AND j.name = 'Unincorporated Bradford County'
  AND NOT EXISTS (SELECT 1 FROM zoning_districts zd WHERE zd.jurisdiction_id = j.id AND zd.code = v.code);

-- 3) zoning_districts for Brooker (jurisdiction_id 987) -- was ZERO rows.
--    Source: Town of Brooker LDR (ncfrpc.org -- NOT on municode).
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description)
SELECT 987, v.code, v.name, v.category, v.description
FROM (VALUES
  ('A',        'Agricultural',                                    'Agricultural', 'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.5'),
  ('CG',       'Commercial, General',                             'Commercial',   'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.12'),
  ('CN',       'Commercial, Neighborhood',                        'Commercial',   'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.11'),
  ('CSV',      'Conservation',                                    'Conservation', 'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.3'),
  ('ESA-1',    'Environmentally Sensitive Areas',                 'Conservation', 'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.4'),
  ('ILW',      'Industrial, Light and Warehousing',                'Industrial',   'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.13'),
  ('PRD',      'Planned Residential Development',                 'Planned',      'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.14'),
  ('RMF-1',    'Residential, Multiple Family',                    'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.10'),
  ('RMF-2',    'Residential, Multiple Family',                    'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.10'),
  ('RMH-1',    'Residential, Mobile Home',                        'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.8'),
  ('RMH-2',    'Residential, Mobile Home',                        'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.8'),
  ('RMH-3',    'Residential, Mobile Home',                        'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.8'),
  ('RMH-P',    'Residential, Mobile Home Park',                   'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.9'),
  ('RSF-1',    'Residential, Single Family',                      'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.6'),
  ('RSF-2',    'Residential, Single Family',                      'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.6'),
  ('RSF-3',    'Residential, Single Family',                      'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.6'),
  ('RSF/MH-1', 'Residential (Mixed) Single Family/Mobile Home',   'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.7 -- confirmed zone for parcel 00273-0-01000 (Ward City Blk 15, fronting Charlotte Ave)'),
  ('RSF/MH-2', 'Residential (Mixed) Single Family/Mobile Home',   'Residential',  'Town of Brooker LDR (ncfrpc.org), Art.4 Sec.4.1.1 / Sec.4.7')
) AS v(code, name, category, description)
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts zd WHERE zd.jurisdiction_id = 987 AND zd.code = v.code);

-- 4) parcel_zones for the 4 auction parcels (3 unincorporated -> A-2 in the
--    new "Unincorporated Bradford County" jurisdiction; 1 inside Brooker town
--    limits -> RSF/MH-1 in jurisdiction 987).
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT v.parcel_id,
       (SELECT id FROM jurisdictions WHERE name = 'Unincorporated Bradford County' AND county = 'Bradford'),
       v.zone_code,
       'shard1_42aac1fb_continuation/VERIFIED:bradford_county_zoning_atlas_ncfrpc_georef_v1+tigerweb_incorporation_check'
FROM (VALUES
  ('00077-0-00401', 'A-2'),
  ('00441-0-00100', 'A-2'),
  ('00868-0-01801', 'A-2')
) AS v(parcel_id, zone_code)
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id);

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '00273-0-01000', 987, 'RSF/MH-1',
       'shard1_42aac1fb_continuation/VERIFIED:brooker_zoning_atlas_ncfrpc_georef_wardcity_plat_v1+tigerweb_geoid_1208725'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = '00273-0-01000');
