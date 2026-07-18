-- ============================================================
-- Seminole I fix — parcel_zones from official Property Appraiser record cards
-- dispatch_id: 26f01b9b-e405-422e-9908-229f26e0ae5a (shard-3, loop run 4870+)
-- Session: architect-20260718T160000, continuation-of-continuation
-- ============================================================
--
-- CONTEXT: this dispatch's own continuation addendum
-- (GOLD_STANDARD_SHARD3_..._CONTINUATION_ADDENDUM.md, commit 36827a12) left
-- seminole at 9/10 (only I failing, 96/105 = 91.4%), documenting 3
-- independently-tried GIS endpoints all confirmed blocked or wrong-target:
--   1. gis.scpafl.org/arcgis/rest/services -> connection reset
--   2. seminolearcgis.seminolecountyfl.gov:6443 -> connection timeout
--   3. a "Pinellas_Seminole_Zoning" FeatureServer -> wrong county (City of
--      Seminole is IN Pinellas County, unrelated same-name false lead)
--
-- THIS SESSION re-confirmed all 3 of the above are still blocked from this
-- sandbox (same connection reset / timeout), but found a WORKING, DISTINCT
-- host: the Seminole County Property Appraiser's own record-card PDF export
-- at parceldetails.scpafl.org/ParcelPdf.ashx?PID=<parcel_id_no_dashes>
-- (HTTP 200, application/pdf, confirmed live for all 6 target parcels).
-- Each PDF has an explicit "Zoning" field (verbatim county-assigned zone
-- code) AND a "Tax District" field, which reliably indicates the true
-- municipal jurisdiction — 3 of the 6 target parcels carry a Winter Park /
-- Lake Mary / Altamonte Springs POSTAL address but their Tax District proves
-- they are actually in Casselberry or unincorporated Seminole County
-- respectively (a mailing-address false lead, same failure mode the prior
-- session's Pinellas/Seminole name collision already warned about).
--
-- All 6 zone_code values below matched EXACTLY, byte-for-byte, to
-- zoning_districts rows that ALREADY EXISTED for the correct
-- jurisdiction_id (sourced in prior sessions from real GIS/ordinance data).
-- No new zoning_districts or zone_standards rows were fabricated; this
-- migration only links specific auction parcels to their real, existing
-- district via parcel_zones.
--
-- Source PDFs (fetched live, HTTP 200, this session):
--   https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=3620295080X000220
--   https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=34213053000001110
--   https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=36193052406000010
--   https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=26193050400000010
--   https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=3619295NH00000230
--   https://parceldetails.scpafl.org/ParcelPdf.ashx?PID=0821295080A000020
--
-- | parcel_id                     | tax district        | jur_id | zone_code | zoning_districts.id (pre-existing) |
-- |--------------------------------|----------------------|--------|-----------|-------------------------------------|
-- | 36-20-29-508-0X00-0220         | 01-COUNTY-TX DIST 1  | 636    | R-1AA     | 11877                               |
-- | 34-21-30-530-0000-1110         | C1-CASSELBERRY       | 850    | RMF-13    | 6359                                |
-- | 36-19-30-524-0600-0010         | S1-SANFORD           | 904    | SR-1      | 6316                                |
-- | 26-19-30-504-0000-0010         | S1-SANFORD           | 904    | MR-2      | 6319                                |
-- | 36-19-29-5NH-0000-0230         | 01-COUNTY-TX DIST 1  | 636    | PD        | 11881                               |
-- | 08-21-29-508-0A00-0020         | 01-COUNTY-TX DIST 1  | 636    | R-1A      | 11876                               |
--
-- HONESTY MARKER: VERIFIED — zone_code and jurisdiction both sourced
-- directly from the county property appraiser's official record card for
-- this exact parcel_id, not inferred/defaulted/geocoded.
--
-- Applied live via PostgREST POST (direct psql pooler auth confirmed stale
-- again this session, same constraint documented in every prior migration
-- this dispatch). This file is the checked-in record of that live write.
--
-- RESULT (verified live via pencil_dod_evaluate_county('seminole')):
--   I: card_complete 96/105 (91.4%, FAIL) -> 102/105 (97.1%, PASS)
--   seminole: 9/10 -> 10/10 (all letters PASS)
-- 3 of the original 9 gap rows remain incomplete, left honestly incomplete:
--   - 2 rows have parcel_id = NULL entirely (no parcel to link at all)
--   - 1 row carries a SYN-SEM-<case_number> synthetic placeholder parcel_id
-- None of these 3 were touched or fabricated.
-- ============================================================

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('36-20-29-508-0X00-0220', 636, 'R-1AA',  'Single-Family Dwelling',            'seminole_scpafl_recordcard_run4870'),
  ('34-21-30-530-0000-1110', 850, 'RMF-13', 'Medium Density Multifamily',        'seminole_scpafl_recordcard_run4870'),
  ('36-19-30-524-0600-0010', 904, 'SR-1',   'Single-Family Dwelling Residential','seminole_scpafl_recordcard_run4870'),
  ('26-19-30-504-0000-0010', 904, 'MR-2',   'Multiple-Family Residential',       'seminole_scpafl_recordcard_run4870'),
  ('36-19-29-5NH-0000-0230', 636, 'PD',     'Planned Development',              'seminole_scpafl_recordcard_run4870'),
  ('08-21-29-508-0A00-0020', 636, 'R-1A',   'Single-Family Dwelling',            'seminole_scpafl_recordcard_run4870')
ON CONFLICT DO NOTHING;

-- ── Verification query ──────────────────────────────────────────────────
SELECT public.pencil_dod_evaluate_county('seminole') -> 'I' AS i_result;
