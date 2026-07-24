-- GOLD STANDARD shard-5 (pinellas): letter I (property-card completeness) real fix
-- run5361 / dispatch (Pinellas I task)
--
-- BASELINE (CONFIRMED live via pencil_dod_evaluate_county('pinellas'), session start):
--   I: pass=false, metric=94.9, detail="card_complete=373 of 393"
--   (A,B,C,D,E,F,G,H,J all PASS, unaffected by this migration)
--
-- CONTEXT (read before this session per task instructions):
--   supabase/migrations/20260711h_gold_standard_shard4_pinellas_i_j_fix_run3713.sql and
--   20260711i_gold_standard_shard4_pinellas_ghost_success_correction_run3713.sql document
--   TWO known-bad prior patterns for this exact county+letter, deliberately NOT repeated here:
--     1. A blanket county-centroid lat=27.9/lon=-82.72 + assessed_value=150000 default,
--        applied to every null-geo pinellas row on 2026-06-24 (20260624_shard9_pinellas_cdij_fix.sql)
--        with zero per-parcel verification.
--     2. Three parcel_zones rows keyed on the literal garbage strings 'MULTIPLE PARCELS',
--        'Property Appraiser', 'SINGLE MEMBER INTEREST' (jurisdiction_id=635, zone_code='R-1',
--        source='shard9_pinellas_cdij_fix/synthetic') that spuriously satisfied the I
--        evaluator's zone_code join for any row that scraped one of those same garbage
--        strings into its own parcel_id column. Deleted 2026-07-11 as ghost-success; NOT
--        re-added here.
--   Both prior write patterns are why this migration only writes REAL, per-row-verified data
--   (address-matched against a live authoritative GIS source) and inserts parcel_zones rows
--   keyed on the REAL recovered 18-digit Pinellas folio, never on a garbage label.
--
-- DIAGNOSIS (reproduced live this session, matches task brief):
--   19 rows failed card_complete. Two sub-patterns:
--   (a) 9 rows had parcel_id literally 'Property Appraiser' (7), 'MULTIPLE PARCELS' (3, only 3
--       actually null-address+null-parcel and structurally unfixable -- no single address exists
--       for a multi-parcel bulk sale), 'SINGLE MEMBER INTEREST' (1, also null-address). Of the
--       9 'Property Appraiser'-keyed rows, 7 carried a real, resolvable property_address; 2
--       ("8543 13TH STREET N # C" and "333 BATH CLUB BLVD S") could NOT be independently
--       verified against the live Accela Address Points GIS layer (closest matches were
--       "8543 10TH ST N" -- different street number, not a confident match -- and no address
--       "333 BATH CLUB BLVD S" exists at all in that block, which runs ...329,335... with no
--       333). Per NEVER-LIE these 2 are left as an honest residual, NOT guessed.
--   (b) Rows with a real-looking 18-digit parcel_id that failed to resolve in
--       v_zoning_gold_standard_card. Root cause CONFIRMED: a 6-digit prefix transposition bug
--       in the scraper -- e.g. DB parcel_id '153010637100000120' vs the real Pinellas folio
--       '103015637100000120' for the same parcel (12766 Seminole Blvd Lot 12, Largo) -- verified
--       by an exact address match against egis.pinellas.gov's own Accela Address Points layer.
--       This same transposition pattern was independently confirmed on 2 more rows below
--       (2559 38th Ave N: DB '163102163440070090' vs real '023116163440070090'; 1416 40th Ave N:
--       DB '163101771660060130' vs real '013116771660060130' -- in both cases the digits after
--       the 6-digit section/township/range prefix match exactly, only the prefix ordering
--       differs, which is diagnostic of a section/township/range field-order scraping bug, not
--       a coincidence).
--
-- SOURCES USED (live, this session, all fetched via curl):
--   1. https://egis.pinellas.gov/gis/rest/services/Accela/AccelaAddressParcel/MapServer/0
--      (Pinellas County enterprise GIS, Address Points layer) -- used to recover the real
--      18-digit PIN_NUM + MUNICIPALITY for every address, confirming exact unit-level address
--      match (e.g. "12766 SEMINOLE BLVD LOT 12" / "FULLADDR") before accepting a PIN.
--   2. https://maps.largo.com/arcgis/rest/services/Largo_GIS_Viewer_Map/MapServer/247
--      ("Parcels" layer) -- this is countywide Pinellas Property Appraiser (PCPAO) tax-roll
--      data re-published via the City of Largo's ArcGIS portal (confirmed by the presence of
--      parcels with Tax_District_Name = ST PETERSBURG, CLEARWATER, PINELLAS PARK, LARGO, and
--      unincorporated fire districts -- i.e. it is not Largo-only). Fields used, all real and
--      queried per-parcel by exact PIN or by Site_Address_Number + Site_Address_Street_Name:
--        - Parcel_Centroid_Latitude / Parcel_Centroid_Longitude (real per-parcel centroid, NOT
--          a county- or city-level default)
--        - Assessed_Property_Value (real PCPAO assessed value for the current tax roll)
--        - FDOR_Land_Use_Code (real Florida DOR use-code digit, e.g. 1=Single Family,
--          4=Condominium, 2=Mobile Home)
--        - Full_Site_Address_Line_1 -- cross-checked against multi_county_auctions.property_address
--          for every row below before accepting the match (unit number match required, e.g.
--          "# 114B", "# B-3", "# 209" all matched exactly).
--   3. https://egis.pinellas.gov/gis/rest/services/Accela/AccelaAddressParcel/MapServer/1
--      (Parcel polygon layer) and the FL GIO statewide cadastral FeatureServer
--      (services9.arcgis.com/.../Florida_Statewide_Cadastral/FeatureServer/0) were BOTH tried
--      for a direct zoning-district lookup and BOTH failed for Pinellas (co_no=52): layer 1
--      returns "Failed to execute query" (HTTP 400) on every WHERE clause tested (a broken
--      server-side join, not a network issue -- layer 0 on the same MapServer works fine); the
--      FL GIO FeatureServer times out or 000s on every CO_NO=52-scoped query tried (matches the
--      prior 2026-07-11 session's independently documented finding of the same endpoint being
--      unusable for Pinellas). fl_parcels (local table, supposedly co_no=52=Pinellas) was also
--      checked and found to actually contain MARION county data (OCALA/DUNNELLON/SUMMERFIELD
--      addresses) under co_no=52 -- a pre-existing mislabeling bug in that table, out of scope
--      to fix here, logged for whoever owns fl_parcels ingestion. No Largo-specific or
--      Pinellas-unincorporated zoning-DISTRICT (as opposed to future-land-use) layer was found
--      reachable from this sandbox after checking PPC_Data (municipality zoning overlays for
--      Belleair/Indian Rocks Beach/etc, none of which cover any of the 13 rows below) and the
--      "Unincorporated Zoning Layer" (id 243) which returned zero features for the one row
--      confirmed unincorporated-tax-district that was point-in-polygon tested.
--
-- ZONE_CODE METHOD (honesty_marker = INFERRED, matches fleet-wide convention): per
-- scripts/ingest_county.py's DOR_UC_MAP (the same crosswalk used for EVERY county's baseline
-- zoning_assignments ingestion, zone_confidence='low'), the REAL per-parcel FDOR_Land_Use_Code
-- fetched above is crosswalked to a zone_code: 1->"SFR", 4->"MFR-CONDO", 2->"MH". This is a
-- real DOR classification fetched per-parcel from an authoritative GIS source, not a blanket
-- default -- it varies per row based on the actual land use of that specific parcel (7 condos,
-- 5 single-family, 1 mobile home), which is the opposite of the reverted R-1-for-everyone
-- pattern from 2026-06-24/07-11.
--
-- WRITES (13 rows -- all rows from both sub-patterns with an independently verified real
-- address match; the 2 unmatchable 'Property Appraiser' rows and the 3 structurally-address-
-- less 'MULTIPLE PARCELS'/'SINGLE MEMBER INTEREST' rows are correctly left untouched):
--   1. UPDATE multi_county_auctions: parcel_id (corrected to the real folio), latitude,
--      longitude, assessed_value -- keyed by case_number, idempotent via case_number match.
--   2. INSERT INTO parcel_zones: one row per real folio, jurisdiction_id resolved to the
--      correct real Pinellas municipality (or 635 = Pinellas County Unincorporated) per the
--      Accela Address layer's own MUNICIPALITY field, zone_code from the DOR crosswalk above,
--      source clearly tagged so this is auditable and distinguishable from the reverted
--      synthetic rows.
--
-- VERIFICATION: run after applying --
--   SELECT public.pencil_dod_evaluate_county('pinellas');
-- Expected: I metric rises from 373/393 (94.9%) to at least 386/393 (98.2%) -- i.e. 13 new
-- passes -- comfortably clearing the >=374/393 (95%) threshold. A,B,C,D,E,F,G,H,J unaffected.

SET statement_timeout = 0;

-- ── STEP 1: correct parcel_id + real per-parcel geo/value on multi_county_auctions ─────────

UPDATE multi_county_auctions SET
  parcel_id = '103015637100000120',
  latitude = 27.88901908, longitude = -82.78917851,
  assessed_value = 39202.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522023CC009988XXCOCO';

UPDATE multi_county_auctions SET
  parcel_id = '363015903180002080',
  latitude = 27.82648625, longitude = -82.74697675,
  assessed_value = 83323.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CA001203XXCICI';

UPDATE multi_county_auctions SET
  parcel_id = '342915393840020100',
  latitude = 27.90964934, longitude = -82.79379582,
  assessed_value = 183341.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CA002480XXCICI';

UPDATE multi_county_auctions SET
  parcel_id = '202916326910010142',
  latitude = 27.94037771, longitude = -82.72479819,
  assessed_value = 431464.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522026CC000983XXCOCO';

UPDATE multi_county_auctions SET
  parcel_id = '023116163440070090',
  latitude = 27.80679886, longitude = -82.66852596,
  assessed_value = 53281.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522023CA006732XXCICI';

UPDATE multi_county_auctions SET
  parcel_id = '013116771660060130',
  latitude = 27.80788210, longitude = -82.65350999,
  assessed_value = 87194.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522023CA000579XXCICI';

UPDATE multi_county_auctions SET
  parcel_id = '253016177540003040',
  latitude = 27.84901796, longitude = -82.64802694,
  assessed_value = 67698.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522023CC000670XXCOCO';

UPDATE multi_county_auctions SET
  parcel_id = '243015082530080180',
  latitude = 27.86220221, longitude = -82.75396224,
  assessed_value = 137003.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CA005643XXCICI';

UPDATE multi_county_auctions SET
  parcel_id = '312816432150052090',
  latitude = 28.01126293, longitude = -82.72996742,
  assessed_value = 32271.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CC011301XXCOCO';

UPDATE multi_county_auctions SET
  parcel_id = '302716218010043030',
  latitude = 28.11057745, longitude = -82.73782882,
  assessed_value = 144086.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CA003098XXCICI';

UPDATE multi_county_auctions SET
  parcel_id = '342716725860020023',
  latitude = 28.08716586, longitude = -82.69615355,
  assessed_value = 65886.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CC008981XXCOCO';

UPDATE multi_county_auctions SET
  parcel_id = '073016690580000490',
  latitude = 27.88231721, longitude = -82.73065600,
  assessed_value = 155365.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CC008483XXCOCO';

UPDATE multi_county_auctions SET
  parcel_id = '292816776430023070',
  latitude = 28.01857203, longitude = -82.72739454,
  assessed_value = 121258.00,
  updated_at = NOW()
WHERE county = 'pinellas' AND case_number = '522025CA004668XXCICI';

-- ── STEP 2: real parcel_zones rows, keyed on the real recovered folio, DOR-crosswalked ─────

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('103015637100000120', 859, 'MH',        'Mobile Home',                 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc002'),
  ('363015903180002080', 635, 'MFR-CONDO', 'Multi-Family Residential Condominium', 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc004'),
  ('342915393840020100', 859, 'SFR',       'Single Family Residential',   'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc001'),
  ('202916326910010142', 856, 'MFR-CONDO', 'Multi-Family Residential Condominium', 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc004'),
  ('023116163440070090', 814, 'SFR',       'Single Family Residential',   'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc001'),
  ('013116771660060130', 814, 'SFR',       'Single Family Residential',   'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc001'),
  ('253016177540003040', 814, 'MFR-CONDO', 'Multi-Family Residential Condominium', 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc004'),
  ('243015082530080180', 635, 'SFR',       'Single Family Residential',   'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc001'),
  ('312816432150052090', 856, 'MFR-CONDO', 'Multi-Family Residential Condominium', 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc004'),
  ('302716218010043030', 635, 'MFR-CONDO', 'Multi-Family Residential Condominium', 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc004'),
  ('342716725860020023', 635, 'MFR-CONDO', 'Multi-Family Residential Condominium', 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc004'),
  ('073016690580000490', 898, 'SFR',       'Single Family Residential',   'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc001'),
  ('292816776430023070', 856, 'MFR-CONDO', 'Multi-Family Residential Condominium', 'pinellas_i_fix_20260724/largo_gis_parcels_layer247_dor_uc004')
ON CONFLICT DO NOTHING;

-- ── Verification query ──────────────────────────────────────────────────────
SELECT public.pencil_dod_evaluate_county('pinellas');
