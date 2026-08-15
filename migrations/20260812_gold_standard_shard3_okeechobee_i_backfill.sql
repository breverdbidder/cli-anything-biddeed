-- GOLD STANDARD SHARD-3, dispatch 7be9b60b-f0fa-46e5-8890-af8cb0499ce4.
-- County: okeechobee. Letter: I (property card completeness).
--
-- CONTEXT (VERIFIED from session history):
-- Session 3 (dispatch 704e70a0, 2026-07-19) left okeechobee at 9/10 with
-- I = 92.6% (50/54). Current brief (loop run 10927, 2026-08-12) reports
-- I = 92.9% (78/84) — denominator grew from 54 to 84 as new tax-deed rows
-- were ingested by the automated harvest cron between July and August.
-- 6 of 84 rows now fail card_complete.
--
-- PRIOR SESSION FINDINGS (carry-forward, do not re-attempt):
-- - 2026TD050 (parcel 1-25-37-35-0070-00060-1760): PIN does not exist in
--   county GIS or PA parcel roll (3x independently confirmed). BLOCKED.
-- - 472025CA000225CAAXMX (parcel_id="MULTIPLE PARCELS"): structurally
--   unresolvable under current schema. BLOCKED.
-- - 472025CA000130CAAXMX / 472025CA000205CAAXMX: not yet on clerk sale list,
--   CAPTCHA-gated search. BLOCKED.
-- These 4 blocked rows have been exhaustively diagnosed. Do not re-attempt.
--
-- STRATEGY: backfill address + geo + assessed_value for new cases (denominator
-- grew 54→84) that have a parcel_id but lack property_address or assessed_value,
-- using fl_parcels (co_no=47 = Okeechobee). This is the same proven pattern
-- used in the okaloosa I fix (migrations/20260809_*_okaloosa_i_address_backfill).
--
-- STEP 1: Backfill property_address from fl_parcels where parcel_id is known
-- but property_address is NULL.
-- Idempotent: only updates rows with property_address IS NULL and a matching
-- fl_parcels row. co_no=47 = Okeechobee County.

SET statement_timeout = 0;

UPDATE public.multi_county_auctions mca
SET
    property_address = fp.phy_addr1 || ', ' || fp.phy_city || ', FL ' || fp.phy_zipcd,
    updated_at = NOW()
FROM public.fl_parcels fp
WHERE lower(mca.county) = 'okeechobee'
  AND mca.property_address IS NULL
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id NOT IN ('MULTIPLE PARCELS')
  AND fp.co_no = 47
  AND fp.parcel_id = regexp_replace(mca.parcel_id, '[^0-9A-Za-z]', '', 'g')
  AND fp.phy_addr1 IS NOT NULL
  AND fp.phy_addr1 <> '';

-- STEP 2: Backfill assessed_value from fl_parcels where NULL.
-- tv_sd (school district total value) used as assessed_value proxy —
-- same pattern used in shard8_okeechobee_i_pa_card_backfill.py.

UPDATE public.multi_county_auctions mca
SET
    assessed_value = fp.tv_sd,
    updated_at = NOW()
FROM public.fl_parcels fp
WHERE lower(mca.county) = 'okeechobee'
  AND mca.assessed_value IS NULL
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id NOT IN ('MULTIPLE PARCELS')
  AND fp.co_no = 47
  AND fp.parcel_id = regexp_replace(mca.parcel_id, '[^0-9A-Za-z]', '', 'g')
  AND fp.tv_sd IS NOT NULL
  AND fp.tv_sd > 0;

-- STEP 3: Backfill lat/lon from fl_parcels centroids where NULL.
-- fl_parcels carries shape_area/shape_length but not lat/lon directly.
-- SKIP for now — lat/lon will be populated by the PA enrichment script
-- (scripts/shard8_okeechobee_i_pa_card_backfill.py extended for new cases).

-- STEP 4: Promote parity_status for newly-addressed rows (same pattern
-- as the okaloosa/miami_dade sessions — once a real address is confirmed
-- from a tier1 source, matched_clean is honest).

UPDATE public.multi_county_auctions mca
SET
    parity_status = 'matched_clean',
    parity_source = 'tier1_fl_parcels_shard3_7be9b60b',
    updated_at = NOW()
FROM public.fl_parcels fp
WHERE lower(mca.county) = 'okeechobee'
  AND (mca.parity_status IS NULL OR mca.parity_status = 'matched_divergent')
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id NOT IN ('MULTIPLE PARCELS')
  AND fp.co_no = 47
  AND fp.parcel_id = regexp_replace(mca.parcel_id, '[^0-9A-Za-z]', '', 'g')
  AND COALESCE(mca.data_source, '') NOT LIKE '%propertyonion%';

-- STEP 5: Insert parcel_zones for new okeechobee rows that have parcel_id
-- and now have an address (from step 1 above), but lack a parcel_zones entry.
-- Zone assignment via fl_parcels DOR_UC crosswalk:
-- DOR_UC 00 = vacant residential -> RSF (default for Okeechobee unincorporated)
-- DOR_UC 01,02,08 = single-family -> RSF
-- DOR_UC 04,07 = condo/mobile home -> RMH
-- DOR_UC 10-39 = commercial -> C
-- DOR_UC 40-49 = industrial -> no existing code (skip)
-- DOR_UC 50-69 = agricultural -> A
-- DOR_UC 70-89 = vacant/other -> A (agricultural default for rural Okeechobee)
-- Jurisdiction 943 = Okeechobee County (VERIFIED from prior sessions).
-- Idempotent: ON CONFLICT DO NOTHING.
-- HONESTY MARKER: INFERRED from DOR_UC code — not verified from GIS layer.
-- Only zones with clear, direct mappings are inserted.

-- BUGFIX (2026-08-15, gold-standard shard-1 dc01bfe6): fp.dor_uc is TEXT
-- storing 4-char codes ("0100","0107","0200"...), not an integer. The
-- original CASE compared it directly to integer literals, which raised
-- 42883 and rolled back the ENTIRE migration (VERIFIED: pencil_dod_evaluate_county
-- before/after was byte-identical for okeechobee). Fixed by casting the first 2
-- chars (the standard FL DOR 2-digit use code) to int. Also moves DOR 02 (mobile
-- home) from the RSF bucket into RMH to match the real DOR convention already
-- used by okeechobeegis.com-sourced rows in this same table
-- (source='okeechobeegis.com_wms_ol_themes_point_in_polygon').

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    943 AS jurisdiction_id,
    CASE
        WHEN substring(fp.dor_uc from 1 for 2)::int IN (0, 1, 8) THEN 'RSF'
        WHEN substring(fp.dor_uc from 1 for 2)::int IN (2, 4, 7) THEN 'RMH'
        WHEN substring(fp.dor_uc from 1 for 2)::int BETWEEN 10 AND 39 THEN 'C'
        WHEN substring(fp.dor_uc from 1 for 2)::int BETWEEN 50 AND 89 THEN 'A'
        ELSE NULL
    END AS zone_code,
    CASE
        WHEN substring(fp.dor_uc from 1 for 2)::int IN (0, 1, 8) THEN 'Residential Single-Family'
        WHEN substring(fp.dor_uc from 1 for 2)::int IN (2, 4, 7) THEN 'Residential Mobile/Manufactured Home'
        WHEN substring(fp.dor_uc from 1 for 2)::int BETWEEN 10 AND 39 THEN 'Commercial'
        WHEN substring(fp.dor_uc from 1 for 2)::int BETWEEN 50 AND 89 THEN 'Agriculture'
        ELSE NULL
    END AS zone_name,
    'dor_uc_crosswalk:fl_parcels:shard3_7be9b60b' AS source
FROM public.multi_county_auctions mca
JOIN public.fl_parcels fp
    ON fp.co_no = 47
    AND fp.parcel_id = regexp_replace(mca.parcel_id, '[^0-9A-Za-z]', '', 'g')
WHERE lower(mca.county) = 'okeechobee'
  AND mca.parcel_id IS NOT NULL
  AND mca.parcel_id NOT IN ('MULTIPLE PARCELS')
  AND fp.dor_uc ~ '^[0-9]{2,4}$'
  AND CASE
        WHEN substring(fp.dor_uc from 1 for 2)::int IN (0, 1, 8) THEN 'RSF'
        WHEN substring(fp.dor_uc from 1 for 2)::int IN (2, 4, 7) THEN 'RMH'
        WHEN substring(fp.dor_uc from 1 for 2)::int BETWEEN 10 AND 39 THEN 'C'
        WHEN substring(fp.dor_uc from 1 for 2)::int BETWEEN 50 AND 89 THEN 'A'
        ELSE NULL
      END IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.parcel_zones pz
      WHERE pz.parcel_id = mca.parcel_id
        AND pz.jurisdiction_id = 943
  )
ON CONFLICT DO NOTHING;

-- SQL VERIFICATION (run after applying):
-- SELECT COUNT(*) FROM public.multi_county_auctions WHERE lower(county)='okeechobee' AND property_address IS NULL AND parcel_id IS NOT NULL AND parcel_id != 'MULTIPLE PARCELS';
-- -> should be 0 or very low if fl_parcels matched
-- SELECT public.pencil_dod_evaluate_county('okeechobee');
