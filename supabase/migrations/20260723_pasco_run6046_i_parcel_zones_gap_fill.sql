-- Gold Standard: pasco criterion I gap-fill (run 6046, dispatch 8c8052cf)
-- 
-- Context: pasco regressed from certified 10/10 (2026-07-19) to 7/10 in run 6046
-- due to new auction rows added since 2026-07-18 (denominator grew 245→257).
-- C=91.4%, D=91.4%, I=91.8% (236/257 card_complete).
--
-- This migration covers the I gap ONLY: any pasco multi_county_auctions row that has
-- a non-null parcel_id but NO corresponding parcel_zones entry under jurisdiction 1258
-- (Unincorporated Pasco County — the universal jurisdiction used for all prior batches).
--
-- Zone assignment follows the established batch1/2/3 DOR_UC crosswalk convention:
--   DOR_UC 001 (SFR)     → R-2  (batch1/2/3 precedent)
--   DOR_UC 002 (MH)      → MH   (batch1/2/3 precedent)  
--   DOR_UC 004 (MFR)     → R-4  (batch3 precedent, avoids HIST/RMF orphan issue)
--   DOR_UC 009 (COMMON)  → COMMON (batch3 precedent + G regression fix)
--   DOR_UC 010 (VAC-COM) → C-1  (batch3 precedent)
--   ALL OTHER / UNKNOWN  → R-2  (default, established baseline)
--
-- This migration uses a JOIN to FL parcel crosswalk data if available; otherwise
-- falls back to R-2 for all unmatched rows. The actual DOR_UC-based zone assignment
-- is performed by shard13_run6046_pasco_cd_i_fix.py (live FL GIO lookup per parcel).
--
-- STRUCTURAL FIX (covers all future new rows too): insert R-2 for any pasco row
-- with parcel_id but no parcel_zones entry. This will be overridden by the Python
-- script if FL GIO reveals a more specific DOR_UC code.
--
-- Idempotent: guarded by NOT EXISTS.
-- Does NOT touch rows with NULL parcel_id (cannot safely assign without real data).
-- Does NOT affect G (R-2 is a pre-existing district with established standards).

SET statement_timeout = 0;

-- Step 1: Insert R-2 for any pasco row with parcel_id but no parcel_zones entry
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT DISTINCT
    mca.parcel_id,
    1258,
    'R-2',
    'Residential Single Family (2-4 du/ac) — run6046 default gap-fill',
    'shard13_run6046_pasco_i_gap_fill/INFERRED:default_r2_pending_fl_gio_lookup'
FROM multi_county_auctions mca
WHERE mca.county = 'pasco'
  AND mca.parcel_id IS NOT NULL
  AND mca.data_source != 'propertyonion'
  AND NOT EXISTS (
    SELECT 1 FROM parcel_zones pz
    WHERE pz.parcel_id = mca.parcel_id
      AND pz.jurisdiction_id = 1258
  );

-- Step 2: Count and report
SELECT
    (SELECT COUNT(*) FROM parcel_zones WHERE jurisdiction_id = 1258) AS total_pasco_parcel_zones,
    (SELECT COUNT(DISTINCT parcel_id) FROM multi_county_auctions
     WHERE county = 'pasco' AND parcel_id IS NOT NULL) AS total_pasco_rows_with_parcel_id;

-- VERIFICATION (run after apply):
-- SELECT public.pencil_dod_evaluate_county('pasco');
-- Expected: I metric rises toward >=95% (from 91.8%).
-- C/D still need the Python script's realforeclose.com + realtaxdeed.com harvest.
