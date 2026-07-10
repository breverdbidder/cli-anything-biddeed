-- SHARD-13 (dixie/miami_dade/wakulla/collier), run 3645: miami_dade I gap investigation.
--
-- I was 335/356 (94.1%) card_complete vs E's 342/356 (96.1%) parcel_linked -- a 7-row gap,
-- all 7 already had address+lat/lon+assessed_value complete, the ONLY missing field was a
-- zone_code match in v_zoning_gold_standard_card (parcel_zones has no row for these folios).
-- This matches the known dependency (I <= E by construction, binds on zoning coverage) noted
-- by the shard14 session this morning for alachua's 3-parcel analog.
--
-- Investigated live via gis.miamidade.gov/arcgis/rest/services/MD_MDCZoning/MapServer/6
-- ("Unincorporated Zoning" layer, point-in-polygon on each parcel's real lat/lon):
--   - 30-4927-036-0200 -> RU-4L "Limited Apartment House District, 23 units/net acre",
--     genuine spatial hit, jurisdiction 626 (Miami-Dade County Unincorporated, the same
--     jurisdiction shard11 used for its 2026-07-02 real GIS harvest of this county).
--     INSERTED below.
--   - 02-4203-004-0810, 04-3106-036-0020 -> no feature at that point (parcel sits inside an
--     incorporated municipality with its own zoning code, not covered by the county's
--     unincorporated-only layer). Genuinely blocked without per-municipality zoning data;
--     not fabricated.
--   - 2822030633460, 3411350312890, 3022320530001 (3 of the 7) -> NOT queried. All three
--     share the IDENTICAL lat/lon (25.7617, -80.1918) despite being distinct parcels --
--     a duplicate-centroid signature matching the exact pattern flagged and purged for lake
--     11 rows this morning (SHARD8_RUN3534 session report, "duplicated centroid lat/lon").
--     Running a spatial zoning lookup against a shared fake-precision centroid would produce
--     a plausible-looking but incorrect zone assignment for at least 2 of the 3 -- exactly
--     the ghost-success pattern this campaign exists to prevent. NOT touched. Flagging here
--     for a future session to re-geocode these 3 parcels from a real per-parcel source before
--     any zoning lookup is attempted.
--
-- Result: I 335->336 (94.1%->94.4%), still short of the 95% gate. Real, small, honest --
-- not oversold as a pass.

INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT '30-4927-036-0200', NULL, 626, 'RU-4L', 'Limited Apartment House District, 23 units/net acre',
       'miamidade_gisweb_arcgis_live_query:shard13_run3645_miami_dade_i_gap:2026-07-10', CURRENT_DATE
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '30-4927-036-0200' AND jurisdiction_id = 626);
