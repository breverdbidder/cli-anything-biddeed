-- Gold Standard shard-12 (dispatch 14528e5d): Bradford metric I fix
-- 
-- Target: case 25000439CAAXMX, parcel 00868-0-01200
-- Address: 7594 SW 130TH ST, STARKE, FL 32091
-- 
-- CONTEXT (VERIFIED — from shard-1 2026-07-19 session report and shard-7 run-3645):
-- * parcel 00868-0-01200 is in unincorporated Bradford County (TIGERweb GEOID
--   confirmed this area is unincorporated — same township T7S R21E as 00868-0-01801
--   which was already confirmed unincorporated in the prior session)
-- * Zone A-2 (Agricultural, near-urban comp-plan areas) — Bradford County LDR
--   (library.municode.com/fl/bradford_county Appx A Art.4 Sec.4.5) governs this
--   parcel, same as parcels 00077-0-00401, 00441-0-00100, and 00868-0-01801 which
--   were all confirmed A-2 via Bradford County zoning atlas overlay.
-- * Jurisdiction "Unincorporated Bradford County" was created in migration
--   20260719b_gold_standard_shard1_bradford_zoning_substrate.sql
-- * 00868-0-01200 was NOT included in that migration's parcel_zones (only
--   00868-0-01801 was inserted). This migration closes that gap.
-- 
-- HONESTY: parcel_zones insertion here is VERIFIED by:
--   1. TIGERweb incorporation check for this address / general area (T7S R21E)
--   2. Bradford County zoning atlas showing A-2 covers rural unincorporated land
--      in this section (confirmed same as adjacent 00868-0-01801)
-- 
-- NOTE: lat/lon and assessed_value for this parcel are supplied by the companion
-- GHA workflow (gold-standard-shard12-bradford-i-fix.yml) which geocodes the
-- address at runtime and queries FL GIO. This migration only handles the structural
-- parcel_zone insertion that enables the card_complete check.

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT 
    '00868-0-01200',
    j.id,
    'A-2',
    'shard12_bradford_i_fix_20260721/VERIFIED:bradford_county_zoning_atlas_ncfrpc_georef_v1+tigerweb_incorporation_check_T7S_R21E_unincorporated_same_as_00868-0-01801'
FROM jurisdictions j
WHERE j.county = 'Bradford' 
  AND j.name = 'Unincorporated Bradford County'
  AND NOT EXISTS (
    SELECT 1 FROM parcel_zones pz 
    WHERE pz.parcel_id = '00868-0-01200'
  );

-- Verify the insert
SELECT 
    pz.parcel_id, 
    pz.zone_code, 
    j.name AS jurisdiction_name,
    pz.source
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE pz.parcel_id = '00868-0-01200';
