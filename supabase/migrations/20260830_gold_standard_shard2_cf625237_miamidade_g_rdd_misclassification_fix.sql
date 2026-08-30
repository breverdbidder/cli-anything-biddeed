-- Gold Standard shard-2 (dispatch cf625237): miami_dade G fix
-- Session: 2026-08-30, county=miami_dade, letter=G (zoning_min = LEAST(density,far,pk1000))
-- Before: G FAIL, density=98.1 far=95.0 pk1000=66.7 (metric=66.7, pk1000 binding)
-- After:  G still FAIL, density=98.1 far=100.0 pk1000=80.0 (metric=80.0) -- real progress, one
--         genuine residual remains (documented below, not fabricated).
--
-- Root cause (VERIFIED live via Supabase REST this session): a Hialeah parcel
-- (parcel_zones.id=873632, parcel_id=04-2021-031-5030, jurisdiction_id=935,
-- zone_code='RDD', source='miami_dade_arcgis_municipalzone_live_verified',
-- inserted 2026-08-29 by a prior session) had NO matching zoning_districts row
-- for (935,'RDD'). v_zoning_gold_standard_kpi_v3's applicability CTE defaults an
-- unmatched zone_code to pk1000_applicable=true (and far/density too) via
-- COALESCE(...,true) -- incorrectly counting a purely RESIDENTIAL parcel in the
-- FAR and parking-per-1000sf (commercial/industrial-GFA metrics) denominators.
-- 'RDD' = Residential Development District, confirmed via Hialeah Land
-- Development Code Sec. 98-1605 (Article V, Division 29, Hialeah Heights) --
-- cross-checked live against zoneomics.com's Hialeah code mirror, category is
-- explicitly residential, not commercial/industrial/mixed-use.
--
-- Fix: register the real RDD district with pk1000_regulated=false (same
-- override-column precedent already live fleet-wide for other genuinely
-- non-GFA-parking residential/RV districts -- zoning_districts id=10716/11216/
-- 11233/11234/11235, independently re-confirmed live during adversarial verify).
-- This removed the RDD parcel from BOTH the pk1000 and far applicable-denominator
-- (it had defaulted true on both), moving pk1000 66.7%->80.0% (4/6->4/5) and far
-- 95.0%->100.0% (19/20->19/19) as a side effect. density stayed 98.1% unchanged
-- (residential legitimately keeps density_applicable=true by the KPI view's own
-- default rule -- correct, not a regression).
--
-- Live effect (already applied via Supabase REST during this session, this
-- migration is a documentation/audit-trail record of that write, matching fleet
-- convention -- e.g. 20260718s_gold_standard_shard12_okeechobee_pk1000_regulated_override_column.sql):
INSERT INTO zoning_districts (id, jurisdiction_id, code, name, category, ordinance_section, pk1000_regulated)
SELECT 14338, 935, 'RDD', 'Residential Development District', 'residential',
  'Hialeah Land Development Code Sec. 98-1605 (Article V, Division 29, Hialeah Heights)', false
WHERE NOT EXISTS (SELECT 1 FROM zoning_districts WHERE id = 14338);

-- Residual (genuinely unresolved this session, NOT fabricated -- BLANK > WRONG):
--   Miami Beach 'MXE' (Mixed Use Entertainment District, zoning_districts.id=14273,
--   jurisdiction_id=960, zone_standards.id=6402) has far_regulated=true/max_far=2.0
--   populated but parking_per_1000sf is NULL and remains the sole cause G is still
--   FAIL at 80.0%. Miami Beach Code Sec. 130-31 (Parking District boundary
--   definitions) and Sec. 142-545 (MXE development regs) both returned HTTP 403
--   on Municode; the elaws.us mirror that serves other Miami Beach sections timed
--   out on 4 attempts for these two specific sections. No ordinance-backed numeric
--   ratio or pk1000_regulated=false exemption could be confirmed this session --
--   left NULL rather than guessed. Next session: try a different Municode mirror
--   or a direct records request for Miami Beach Code Sec. 130-31/142-545 text.
