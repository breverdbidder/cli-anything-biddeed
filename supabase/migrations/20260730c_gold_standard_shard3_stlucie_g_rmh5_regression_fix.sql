-- GOLD STANDARD shard-3 (volusia, st_lucie): fix a self-caused G regression.
--
-- This session's E/I zoning-link fix inserted parcel_zones row for parcel
-- 1312-701-0085-000-2 (case 26-009, St Lucie tax deed) with zone_code='RMH-5'
-- under jurisdiction_id=1400 (St Lucie County Unincorporated), but no
-- zoning_districts row existed for that (jurisdiction_id, code) pair.
--
-- v_zoning_gold_standard_kpi_v3's LEFT JOIN chain (parcel_zones -> zoning_districts
-- -> v_zoning_district_applicability -> zone_standards) defaults far_applicable/
-- pk1000_applicable to TRUE via COALESCE(...,true) whenever the zoning_districts
-- row is entirely missing. That made this single new parcel the ONLY
-- "applicable" FAR/parking parcel countywide with no standard on file, collapsing
-- st_lucie's pct_far_of_applicable/pct_pk1000_of_applicable to 0.0/0.0 and
-- flipping letter G from PASS(97.9) to FAIL(0) -- confirmed live and root-caused
-- by an adversarial verify pass this session (not a pre-existing, unrelated issue).
--
-- CONFIRMED via St. Lucie County Land Development Code (Ch. III Sec. 3.01.00,
-- Ch. VII Sec. 7.04.00 -- library.municode.com/HTML/14641/level2/CHIIIZODI_3.01.00ZODIUSRE.html):
-- "The RMH-5 Residential Mobile Home zoning district is designed to provide for
-- the permanent location of mobile homes for residential purposes." This is a
-- residential district; FAR and parking-per-1000sf are commercial/industrial
-- floor-area-based metrics that St Lucie's LDC does not apply to residential
-- mobile-home districts (residential parking/density standards are stated
-- per-dwelling-unit and per-acre, not per-1000sf of floor area). Marking
-- far_regulated/pk1000_regulated explicit FALSE here reflects that confirmed
-- district classification, not an attempt to force a pass.
--
-- max_density_du_acre is intentionally NOT set (left for a future session to
-- source from LDC Sec. 7.04.00) -- an honest gap, not a guess. This parcel will
-- still count as one density-applicable-but-missing-standard row; it does not
-- threaten st_lucie's density metric (97.2% with headroom).
--
-- NOTE: an analogous 1-parcel regression exists for VOLUSIA (M1 / Daytona Beach,
-- confirmed genuinely industrial via live GIS attribute Z_DESCRIP='IND (Industrial)'
-- at maps1.vcgov.org CountywideZoning MapServer) -- FAR/parking ARE legitimately
-- applicable to that industrial parcel, and this session could NOT source a real
-- FAR/parking standard for Daytona Beach M-1 (municode.com blocked direct fetch,
-- the city's own M1 PDF was not machine-readable, and Firecrawl API returned
-- HTTP 402). Per BLANK > WRONG this was left unresolved; volusia G remains FAIL
-- pending real ordinance research on Daytona Beach M-1 FAR/parking standards --
-- do not fabricate a value in a future session either, source it for real.

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, ordinance_section, far_regulated, pk1000_regulated)
VALUES (1400, 'RMH-5', 'RMH-5 Residential Mobile Home', 'residential', 'St. Lucie County LDC Ch. III Sec. 3.01.00 / Ch. VII Sec. 7.04.00', false, false)
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

-- Verification: SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county='st_lucie';
-- expected: pct_far_of_applicable / pct_pk1000_of_applicable back to NULL (0 applicable rows),
-- pct_density_of_applicable unchanged at ~97.2.
