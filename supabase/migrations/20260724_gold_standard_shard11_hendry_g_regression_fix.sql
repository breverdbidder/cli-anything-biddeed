-- GOLD STANDARD shard-11, county=hendry (dispatch bebd50e5, loop run 6148).
--
-- REGRESSION CAUGHT LIVE: the I-fix in this session's prior migration
-- (20260724_gold_standard_shard11_hendry_i_second_pass_geo_zoning.sql) inserted
-- a parcel_zones row with zone_code='RR' (case 25-45, parcel
-- "1 33 44 07 030 0008-005.0") -- a real code returned by Hendry County's own
-- Zoning FeatureServer, genuinely distinct from the sibling 'RR-F' code
-- already in this DB. But no zoning_districts row exists for 'RR' in the
-- Hendry Unincorporated jurisdiction (id 1399), so
-- v_zoning_gold_standard_kpi_v3's LEFT JOIN to zoning_districts/
-- v_zoning_district_applicability produced NULLs for this parcel, and that
-- view's COALESCE(a.far_applicable, true) / COALESCE(a.pk1000_applicable, true)
-- defaults treat an unmatched district as APPLICABLE rather than N/A. Verified
-- live: G flipped from PASS (density=100.0 far=100.0 pk1000=<null, ignored>) to
-- FAIL (density=98.1 far=93.8 pk1000=0.0) immediately after that migration.
--
-- FIX: add the missing zoning_districts row for 'RR' so it joins correctly.
-- Regulatory classification mirrors its already-verified sibling rural-
-- residential districts in this exact jurisdiction (RR-F, RR-WE): category=
-- 'residential', far_regulated/pk1000_regulated left NULL (same as siblings),
-- density_regulated=true. This is a categorical/structural inference from an
-- identical real district family already established in this DB by a prior
-- session's ordinance research (both are "Rural Residential" LDC districts
-- with no FAR or parking-per-1000sf regulation) -- NOT an invented numeric
-- standard. max_density_du_acre for 'RR' is deliberately left NULL rather than
-- guessed (BLANK > WRONG); this is a disclosed residual gap (1 of the
-- district's applicable parcels missing a density value), sized at ~98%
-- density coverage county-wide -- still comfortably above the 95% gate.

SET statement_timeout = 0;

BEGIN;

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated)
VALUES (1399, 'RR', 'Rural Residential', 'residential', NULL, NULL, true)
ON CONFLICT DO NOTHING;

COMMIT;
