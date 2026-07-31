-- SHARD-C1 seminole C/D fix, dispatch ca56cc4d-4e7f-4234-814f-a1e6de065d52
-- Idempotent reflection of live PostgREST PATCH writes made this session
-- (direct psql/pooler auth confirmed non-functional in this sandbox; all
-- writes executed via REST, this file documents them for replay/audit).
--
-- Root cause: 8 seminole rows (all sale_type='foreclosure',
-- data_source='calendar_sweep_mca_v3', auction_date=2026-08-20) had
-- parity_status=NULL / parity_source=NULL. This is a NEW auction batch that
-- appeared after prior seminole fix passes (scripts/shard14_run3534_..._fix.py
-- et al.), which only covered auction dates through 2026-08-04. auctions_total
-- (133) already included these 8 rows in the denominator, so C/D sat at
-- 125/133 = 94.0% (below the 95% pass threshold) with zero fixable slack
-- until this new batch was harvested and matched.
--
-- Fix: live-harvested seminole.realforeclose.com's public AJAX
-- PREVIEW/UPDATE calendar for 08/20/2026 (scripts/shard2_run2450_ajax_realforeclose_harvest.py,
-- reused verbatim -- the same RealForeclose AJAX mechanism used fleet-wide).
-- All 8 gap case_numbers matched exactly against the live calendar, with
-- parcel_id/property_address/assessed_value already present in our DB
-- matching the harvested item byte-for-byte -- confirms genuine live data,
-- not fabricated. Promoted each to parity_status='matched_clean' with a
-- tier1-prefixed parity_source citing the harvest source/date.

UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:shard_c1_seminole_run_ca56cc4d_ajax_08202026:foreclosure:2026-08-20'
WHERE county = 'seminole'
  AND case_number IN (
    '2023CA004030',
    '2024CA000965',
    '2024CA002016',
    '2025CA000122',
    '2025CA000244',
    '2025CA000307',
    '2025CA000962',
    '2026CA000404'
  )
  AND (parity_status IS DISTINCT FROM 'matched_clean'
       OR parity_source NOT LIKE 'tier1%');
