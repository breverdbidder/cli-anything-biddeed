-- Gold Standard shard-5 (dispatch 5d40a513-fb55-4c9c-ad49-be84afb8388f), county=osceola, letter=G.
--
-- BEFORE: pencil_dod_evaluate_county('osceola').G = {"pass": false, "detail":
-- "density=94.4 far= pk1000=78.6", "metric": 78.6}.
--
-- DISPATCH BRIEF vs LIVE STATE -- MATERIAL CORRECTION:
-- The dispatch brief (written from an earlier snapshot) named zoning_districts.id
-- 11796 (Osceola County PD, 40 osceola auction parcels) and 11793 (Osceola County
-- AC, 37 osceola auction parcels) as the two highest-leverage pk1000 gaps. Live
-- query this session against v_zoning_district_applicability (which reads
-- zoning_districts.pk1000_regulated / far_regulated / density_regulated, defaulting
-- by category when those columns are NULL -- see pg_get_viewdef, confirmed live)
-- shows a PRIOR session (scraped_at 2026-07-11, see zone_standards id 4500/4503)
-- already set pk1000_regulated appropriately for BOTH districts based on real
-- ordinance research:
--   - id 11796 (PD): pk1000_regulated=false, far_regulated=false,
--     density_regulated=false. Confirmed by re-reading that row's own citation
--     (Osceola LDC Sec 3.11.1(I): "allowable density and intensity will be based
--     on several factors..." -- explicitly per-development-order, no single
--     codified number, applies identically to PD/PMUD/STRPD sub-types).
--   - id 11793 (AC): density_regulated defaults true (0.20 du/acre already on
--     file, untouched), but far_regulated/pk1000_regulated default to false
--     because category='agricultural' is not in the commercial/industrial/
--     mixed-use applicability set (view's fallback logic, not an explicit
--     override row -- confirmed via v_zoning_district_applicability output).
-- Neither PD nor AC is therefore a live pk1000 gap. Live gap query (this
-- session, joining parcel_zones -> zoning_districts by (jurisdiction_id,
-- zone_code) -> v_zoning_district_applicability -> zone_standards, filtered to
-- county='osceola' AND pk1000_applicable AND parking_per_1000sf IS NULL) returns
-- exactly ONE district: id=13180, Kissimmee SRPUD ("Short-Term Rental Planned
-- Unit Development District"), 3 parcels. This matches the dispatch brief's own
-- secondary note that "a prior session already researched Sec 14-4-8 for this
-- one... try to finish the parking-chapter lookup it left open" -- that is the
-- actual, current, sole pk1000 gap driving G's 78.6% (11 of 14 applicable
-- parcels populated -> 3 missing = 78.6%).
--
-- G's density sub-metric (94.4%, not binding since pk1000 is lower) has its own
-- 3-parcel gap in three separate Kissimmee form-based-code districts (T4-R,
-- T5-U, MUPUD, 1 parcel each) -- out of scope for this pass per the dispatch
-- brief's PD/AC/SRPUD focus; noted as residual below, not touched.
--
-- ROOT CAUSE + FIX FOR THE REAL GAP (SRPUD, id 13180):
-- zone_standards id 5515 (SRPUD) already correctly resolved density (N/A per
-- Sec 14-4-8.B.4.a.i, max density = 75% of underlying FLU, not a fixed du/acre
-- figure -- left null, matches density_regulated=false override already set)
-- but left parking_per_1000sf NULL with the note "leaving null pending
-- citywide parking-chapter (14-6) lookup." That chapter number was itself
-- slightly off. VERIFIED live this session via the Municode CodesContent API
-- (jobId=462754, productId=15261, same job used by the existing T3/T5-M rows):
--   1. Sec 14-4-8.C (SRPUD) + Sec 14-4-8.B.4 (RPUD site design standards,
--      incorporated by reference into SRPUD) list "Parking and access:
--      Chapter 14-7" as the applicable cross-reference (confirmed verbatim in
--      the live 14-4-8 chapter text).
--   2. Chapter 14-7 is titled "ACCESS CIRCULATION, AND PARKING" (node
--      PTIIILADECO_CH14-7ACCIPA), Part III "OFF-STREET PARKING STANDARDS",
--      Sec. 14-7-22 "Automobile parking ratios" (node
--      PTIIILADECO_CH14-7ACCIPA_PTIIIOREPAST_14-7-22AUPARA). Table 7-2
--      "Minimum Parking Ratios" -- Residential row "Single family, duplex,
--      triplex, townhouse dwelling and mobile home: 2 spaces per unit."
--   3. Sec 14-6-44 ("Short-term rentals and time-share dwellings", the section
--      SRPUD's own citation flagged as the STR-specific rule) was also fetched
--      live and CONFIRMED to contain no parking ratio at all -- only use/
--      location/buffer/HOA/conversion conditions. It does not override or
--      supersede Table 7-2 for parking; STR dwellings in an SRPUD are
--      single-family/townhome-type dwelling units, so Table 7-2's residential
--      dwelling-unit row (2 spaces/unit) is the applicable citywide standard,
--      "unless a parking study...is provided demonstrating that a reduction is
--      warranted" (Sec 14-7-22.A) -- i.e. 2/unit is the real baseline
--      requirement, not a fabricated number.
--   4. Unit convention: this field stores the ordinance's per-unit residential
--      figure directly as a numeric value (confirmed house-wide pattern --
--      Osceola County's own R-2 "Multi-Family Residential" row already stores
--      "2 spaces per unit" as parking_per_1000sf=2.00; same pattern used
--      fleet-wide for Aventura/Doral RU-1 etc). Following that existing
--      convention, not inventing a new one.
--
-- FIX: zone_standards row id 5515 (zoning_district_id=13180, Kissimmee SRPUD)
-- gets parking_per_1000sf=2.00, source_url/ordinance_section updated to the
-- verified live citation, scraped_at bumped to now(). No fabricated numbers;
-- max_far/density remain untouched (correctly null/N/A per prior research).

UPDATE public.zone_standards
SET parking_per_1000sf = 2.00,
    source_url = 'https://api.municode.com/CodesContent?jobId=462754&nodeId=PTIIILADECO_CH14-7ACCIPA_PTIIIOREPAST_14-7-22AUPARA&productId=15261 (Kissimmee LDC Chapter 14-7 Access Circulation and Parking, Part III Off-Street Parking Standards, Sec. 14-7-22 Automobile parking ratios, Table 7-2; human viewer: https://library.municode.com/fl/kissimmee/codes/code_of_ordinances?nodeId=PTIIILADECO_CH14-7ACCIPA_PTIIIOREPAST_14-7-22AUPARA). Cross-referenced from Sec 14-4-8.C/14-4-8.B.4 (SRPUD/RPUD "Parking and access: Chapter 14-7") and Sec 14-6-44 (Short-term rentals -- CONFIRMED live, contains no parking ratio, only use/location/buffer conditions).',
    ordinance_section = 'Kissimmee LDC Sec. 14-7-22.A + Table 7-2 (Minimum Parking Ratios), Residential row "Single family, duplex, triplex, townhouse dwelling and mobile home": 2 spaces per unit. Applies to SRPUD short-term rental dwelling units (single-family/townhome type) absent a district-specific override -- confirmed Sec 14-6-44 sets no parking ratio for STRs.',
    scraped_at = now()
WHERE id = 5515
  AND zoning_district_id = 13180;

-- Idempotent guard: if the row were ever missing (it exists as of this
-- session, id=5515), insert it fresh with the same verified values.
INSERT INTO public.zone_standards (zoning_district_id, parking_per_1000sf, source_url, ordinance_section, scraped_at)
SELECT 13180, 2.00,
  'https://api.municode.com/CodesContent?jobId=462754&nodeId=PTIIILADECO_CH14-7ACCIPA_PTIIIOREPAST_14-7-22AUPARA&productId=15261 (Kissimmee LDC Chapter 14-7 Access Circulation and Parking, Part III Off-Street Parking Standards, Sec. 14-7-22 Automobile parking ratios, Table 7-2; human viewer: https://library.municode.com/fl/kissimmee/codes/code_of_ordinances?nodeId=PTIIILADECO_CH14-7ACCIPA_PTIIIOREPAST_14-7-22AUPARA). Cross-referenced from Sec 14-4-8.C/14-4-8.B.4 (SRPUD/RPUD "Parking and access: Chapter 14-7") and Sec 14-6-44 (Short-term rentals -- CONFIRMED live, contains no parking ratio, only use/location/buffer conditions).',
  'Kissimmee LDC Sec. 14-7-22.A + Table 7-2 (Minimum Parking Ratios), Residential row "Single family, duplex, triplex, townhouse dwelling and mobile home": 2 spaces per unit. Applies to SRPUD short-term rental dwelling units (single-family/townhome type) absent a district-specific override -- confirmed Sec 14-6-44 sets no parking ratio for STRs.',
  now()
WHERE NOT EXISTS (SELECT 1 FROM public.zone_standards WHERE zoning_district_id = 13180);
