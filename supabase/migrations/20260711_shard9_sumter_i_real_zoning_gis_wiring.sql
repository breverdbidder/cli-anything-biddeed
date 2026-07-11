-- ============================================================
-- Sumter I fix — REAL zoning wiring from Sumter County GIS
-- Dispatch: ddbb047c-3aca-44b8-821a-58a26d127732 (Gold Standard shard-9, run3679)
-- Counties: sumter only
-- ============================================================
--
-- CONTEXT (VERIFIED live 2026-07-11):
--   property_address / latitude / longitude / assessed_value / market_value
--   were ALREADY backfilled for all 10 real (parcel_id-bearing) sumter
--   multi_county_auctions rows by a prior session
--   (scripts/shard9_run3645_sumter_i_parcel_enrichment.py, commit 69e9f72a).
--   Confirmed live: pencil_dod_evaluate_county('sumter') still shows
--   I: card_complete=0 of 11 DESPITE that enrichment, because
--   v_zoning_gold_standard_card had only 4 sumter rows total, 2 of which
--   are SYNTHETIC placeholders (SYN-SUM-FC-001, SYN-SUM-TD-001, source=
--   'sumter_g_i_fix/synthetic') and 2 of which (D27K017, D36J130, source=
--   'shard1_inferred:2026-06-26') are real-looking but do not match ANY of
--   our 10 real parcel_ids. Zero real parcel_zones linkage existed for our
--   actual 10 sumter auction parcels. THIS is the true I blocker, not the
--   enrichment (which was already correct).
--
-- FIX (this migration): insert REAL parcel_zones rows for the 10 real
-- sumter parcel_ids, sourced LIVE from Sumter County's own public ArcGIS
-- FeatureServer (ground-truth authority, same class of source as BCPAO/
-- FL DOR used elsewhere in this project):
--
--   County unincorporated + The Villages layer (parcel-keyed):
--     https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/
--       FLU_Zoning/FeatureServer/11  (field: Parcel, attr: Zone_Type)
--   Wildwood municipal layer (PIN-keyed):
--     https://gis.sumtercountyfl.gov/sumtergis/rest/services/Interactive/
--       FLU_Zoning/FeatureServer/10  (field: PIN, attr: Zoning_Cur)
--
-- Every one of the 10 real parcel_ids was queried live by exact
-- Parcel/PIN match (not point-in-polygon, not inference) and returned
-- exactly one polygon feature with a real zone code:
--
--   D03F058  RPUD   (county layer 11, jurisdiction 1325 Sumter County)
--   R14X015  R2M    (county layer 11, jurisdiction 1325 Sumter County)
--   D09E270  RPUD   (county layer 11, jurisdiction 1325 Sumter County)
--   G03A014  RPUD   (county layer 11, jurisdiction 1325 Sumter County)
--   J34A003  R2C    (county layer 11, jurisdiction 1325 Sumter County)
--   J16C019  R2M    (county layer 11, jurisdiction 1325 Sumter County)
--   D20G135  R-2    (Wildwood layer 10, jurisdiction 950 Wildwood)
--   G05R062  R-3    (Wildwood layer 10, jurisdiction 950 Wildwood)
--   G07F008  MHP    (Wildwood layer 10, jurisdiction 950 Wildwood)
--   G06F064  RMU    (Wildwood layer 10, jurisdiction 950 Wildwood)
--
-- 2025-CA-000255 (cancelled foreclosure, no parcel_id anywhere) is
-- correctly NOT included — no parcel exists to link. It remains in the
-- I denominator (card_rows counts all 11 auction rows) but can never
-- satisfy the numerator without a parcel_id, which no live source has
-- (see run3679 residual notes).
--
-- NOT WRITTEN in this migration (deliberately out of scope):
--   zone_standards (setbacks/height/density/FAR/parking) for the 7 real
--   zone codes above (RPUD, R2M, R2C, R-2, R-3, MHP, RMU). The
--   v_zoning_gold_standard_card view LEFT JOINs zone_standards, and I's
--   card_complete definition only requires zone_code IS NOT NULL from
--   parcel_zones (NOT any zone_standards field) — so this migration is
--   sufficient for I on its own merits without fabricating setback/
--   density numbers we did not scrape from a real ordinance. Scraping
--   Sumter's actual LDC (Land Development Code) per-district standards
--   for these 7 codes across 2 jurisdictions is a real, larger task
--   (Phase 4 of the county-expansion pipeline) sized as a residual for a
--   future session — this migration does NOT touch zone_standards, only
--   zone_code linkage (parcel_zones + zoning_districts registration).
-- ============================================================

SET statement_timeout = 0;

-- ── Step 1: zoning_districts — register the 7 real zone codes we found ──────
-- (category/description are structural metadata, not fabricated standards)

INSERT INTO zoning_districts (code, name, jurisdiction_id, category, description)
VALUES
    ('RPUD', 'Residential Planned Unit Development', 1325, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=RPUD), queried live by exact Parcel match 2026-07-11.'),
    ('R2M',  'Residential 2 - Manufactured', 1325, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=R2M), queried live by exact Parcel match 2026-07-11.'),
    ('R2C',  'Residential 2 - Conventional', 1325, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 11 (Zone_Type=R2C), queried live by exact Parcel match 2026-07-11.'),
    ('R-2',  'Residential 2 (Wildwood)', 950, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 10 Wildwood Zoning (Zoning_Cur=R-2), queried live by exact PIN match 2026-07-11.'),
    ('R-3',  'Residential 3 (Wildwood)', 950, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 10 Wildwood Zoning (Zoning_Cur=R-3), queried live by exact PIN match 2026-07-11.'),
    ('MHP',  'Manufactured Home Park (Wildwood)', 950, 'residential',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 10 Wildwood Zoning (Zoning_Cur=MHP), queried live by exact PIN match 2026-07-11.'),
    ('RMU',  'Residential Mixed Use (Wildwood)', 950, 'mixed_use',
     'Real zone code from Sumter County GIS FLU_Zoning FeatureServer layer 10 Wildwood Zoning (Zoning_Cur=RMU), queried live by exact PIN match 2026-07-11.')
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- ── Step 2: parcel_zones — link the 10 real parcel_ids to their real zone ────

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
VALUES
    ('D03F058', 'D03F058', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=D03F058:2026-07-11'),
    ('R14X015', 'R14X015', 1325, 'R2M', 'Residential 2 - Manufactured',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=R14X015:2026-07-11'),
    ('D09E270', 'D09E270', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=D09E270:2026-07-11'),
    ('G03A014', 'G03A014', 1325, 'RPUD', 'Residential Planned Unit Development',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=G03A014:2026-07-11'),
    ('J34A003', 'J34A003', 1325, 'R2C', 'Residential 2 - Conventional',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=J34A003:2026-07-11'),
    ('J16C019', 'J16C019', 1325, 'R2M', 'Residential 2 - Manufactured',
     'sumter_gis_live:FLU_Zoning/FeatureServer/11:Parcel=J16C019:2026-07-11'),
    ('D20G135', 'D20G135', 950, 'R-2', 'Residential 2 (Wildwood)',
     'sumter_gis_live:FLU_Zoning/FeatureServer/10:PIN=D20G135:2026-07-11'),
    ('G05R062', 'G05R062', 950, 'R-3', 'Residential 3 (Wildwood)',
     'sumter_gis_live:FLU_Zoning/FeatureServer/10:PIN=G05R062:2026-07-11'),
    ('G07F008', 'G07F008', 950, 'MHP', 'Manufactured Home Park (Wildwood)',
     'sumter_gis_live:FLU_Zoning/FeatureServer/10:PIN=G07F008:2026-07-11'),
    ('G06F064', 'G06F064', 950, 'RMU', 'Residential Mixed Use (Wildwood)',
     'sumter_gis_live:FLU_Zoning/FeatureServer/10:PIN=G06F064:2026-07-11')
ON CONFLICT (tax_account, jurisdiction_id) DO UPDATE SET
    zone_code = EXCLUDED.zone_code,
    zone_name = EXCLUDED.zone_name,
    source    = EXCLUDED.source;

-- ── Verification ─────────────────────────────────────────────────────────────

SELECT 'parcel_zones sumter' AS check_name, pz.parcel_id, pz.jurisdiction_id, pz.zone_code, pz.source
FROM parcel_zones pz
JOIN jurisdictions j ON j.id = pz.jurisdiction_id
WHERE lower(COALESCE(j.county_name, j.county)) = 'sumter'
ORDER BY pz.parcel_id;

SELECT 'card_view sumter' AS check_name, county, parcel_id, tax_account, zone_code
FROM v_zoning_gold_standard_card
WHERE lower(county) = 'sumter'
ORDER BY parcel_id;
