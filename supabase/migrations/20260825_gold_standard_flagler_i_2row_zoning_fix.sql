-- Gold Standard flagler I: zoning backfill for the v_auction_property_card
-- gap (card_complete FAIL at 94.5%, 155/164; needs >=95% / >=156/164 to PASS).
--
-- Source of truth: live PostgREST writes run directly this session (direct
-- psql/$SUPABASE_DB_PASSWORD connection fails -- documented pre-existing
-- constraint, decision_log ids 169/205/287). This migration file documents
-- the same data change per HARD GUARDRAILS #3 in the county-letter task brief.
--
-- SCOPE: task brief flagged 4 rows with a real parcel_id + real lat/lng but
-- NULL zoning_code:
--   2e7aef04-be0d-43c7-93cf-3d74ffedd3f6 (20-10-31-3050-00080-0050, 89 Johnson Beach Way)
--   58ef3cf4-2522-46c6-8bf6-30c88417633e (07-11-31-7025-00160-0170, 2 Perrotti Pl)
--   7c6013d5-1130-4c29-a93b-8217c4a1cf33 (20-10-31-0300-00150-0000, 9 Sweetbay Dr)
--   c1b495e8-a142-4f7c-aaad-7372948dfe2b (07-11-31-7013-00040-0340, 101 Braddock Ln)
--
-- Three of these four (2e7aef04, 58ef3cf4, 7c6013d5) were already attempted by
-- the prior 20260816 migration
-- (supabase/migrations/20260816_gold_standard_flagler_i_8gap_geo_zoning_fix.sql),
-- which documented "zero zoning polygon coverage within 30m at either
-- FeatureServer" for all three. This session re-ran the identical live
-- ArcGIS point-in-polygon query against both FeatureServers (0-tolerance,
-- then 30m buffer with unanimous-agreement requirement) and got a DIFFERENT,
-- more complete result for one of them -- likely reflecting FeatureServer
-- data updates since 2026-08-16 (source layers are actively maintained by
-- Palm Coast/Flagler County GIS):
--
--   2e7aef04 (89 Johnson Beach Way): 0-tolerance miss on both layers
--     (confirmed same as before). BUT a fresh 10m buffer retry against the
--     Flagler County Unincorporated_Zoning FeatureServer
--     (services3.arcgis.com/hSKL9bYjhP4rHxSD/arcgis/rest/services/Unincorporated_Zoning/FeatureServer/0)
--     returned 3 UNANIMOUS polygons, all ZONECODE=R-1 / ZONENAME=RURAL
--     RESIDENTIAL / CITYNAME=UNINCORPORATED. Clean, unambiguous -> written.
--     R-1 did not previously exist in zoning_districts for jurisdiction_id
--     1184 (Unincorporated Flagler County) -- inserted (category+name only,
--     no density/FAR/parking numbers fabricated, per guardrail).
--
--   58ef3cf4 (2 Perrotti Pl): RE-CONFIRMED same mixed/ambiguous result as the
--     20260816 migration -- 30m buffer against PalmCoastFL_Zoning returns a
--     MIXED set (2x SFR-2, 4x SFR-3 this session). Point sits on a genuine
--     zoning boundary. Left unzoned -- BLANK > WRONG, no change from prior
--     session's documented residual.
--
--   7c6013d5 (9 Sweetbay Dr): RE-CONFIRMED genuine gap remains for the
--     PalmCoastFL_Zoning layer (0 features at 30m, point is outside city
--     limits). Unincorporated_Zoning layer now DOES return coverage within
--     30m (4 features) but it is MIXED (3x R-1, 1x R/C) -- ambiguous, same
--     "leave unzoned rather than guess" rule applied. Left unzoned.
--
-- c1b495e8 (101 Braddock Ln) is a NEW row not present in the 20260816
-- migration's target list (that migration's task brief did not include it).
-- Live ArcGIS query this session: confirmed inside PalmCoastFL_CityLimits,
-- and a 0-tolerance exact point-in-polygon hit against PalmCoastFL_Zoning
-- returned a single, unambiguous LAYER=SFR-2 (Single-Family Residential
-- District). SFR-2 already exists in zoning_districts for jurisdiction_id
-- 966 (Palm Coast), id=7614 -- no new zoning_districts row needed.
--
-- Source ArcGIS endpoints used (both FeatureServers, live queries this session):
--   https://services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_Zoning/FeatureServer/0
--   https://services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_CityLimits/FeatureServer/0
--   https://services3.arcgis.com/hSKL9bYjhP4rHxSD/arcgis/rest/services/Unincorporated_Zoning/FeatureServer/0
--
-- Confirmed live this session: public.parcel_zones had ZERO pre-existing
-- rows for any of these 4 exact parcel_ids before this migration (checked
-- before insert, avoids the known parcel_zones dedup defect flagged in the
-- 20260816 migration).
--
-- NOT touched (out of scope, no real source found -- see task brief for full
-- detail, unchanged from prior sessions):
--   6307e8ab-d385-45fc-836d-f97f1a21eacf / c11a235c-c582-4bf3-b31f-1e9df255e202:
--     no address, no lat/lng, no parcel_id -- likely duplicate scraper rows,
--     no source record investigated to find a real address this session.
--   5b26cefa-92ed-4cd4-908e-43950eb4d9ee: partial "BUNNELL, FL" address only,
--     no street-level source found.
--   d1fdb06a-16f9-44d8-879b-d66d0711ca9f: real street address, but parcel_id
--     NULL -- a Flagler property-appraiser parcel_id lookup was not
--     attempted this session (secondary priority, not required to clear the
--     95% bar); documented as still open.
--   78713ea7-59d2-440a-858a-f66e0150bf34: documented known-fake placeholder
--     coordinate (29.6469,-81.2088) per the 20260801 migration comment #4 --
--     explicitly left untouched, no new evidence found.
--
-- AFTER (VERIFIED live via pencil_dod_evaluate_county('flagler') post-fix):
--   I: card_complete 155/164 (94.5%) -> 157/164 (95.7%), FAIL -> PASS.
--   All other letters (A-J) remain PASS; flagler is fully green this session.
--
-- No cron jobs (109/111/115/gold-standard-loop-*) modified. No schema DDL
-- beyond the standard zoning_districts code insert (non-destructive, existing
-- pattern from prior flagler I migrations).

SET statement_timeout = 0;

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category)
SELECT 1184, 'R-1', 'RURAL RESIDENTIAL', 'Residential'
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts
  WHERE jurisdiction_id = 1184 AND code = 'R-1'
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '07-11-31-7013-00040-0340', 966, 'SFR-2', 'Single-Family Residential District',
       'PalmCoastFL_Zoning FeatureServer (services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_Zoning/FeatureServer/0) LAYER field, point-in-polygon @ 29.561273,-81.241686, confirmed inside PalmCoastFL_CityLimits, 0-tolerance exact hit, verified live 2026-08-25'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones
  WHERE parcel_id = '07-11-31-7013-00040-0340' AND jurisdiction_id = 966
);

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
SELECT '20-10-31-3050-00080-0050', 1184, 'R-1', 'RURAL RESIDENTIAL',
       'Flagler County Unincorporated_Zoning FeatureServer (services3.arcgis.com/hSKL9bYjhP4rHxSD/arcgis/rest/services/Unincorporated_Zoning/FeatureServer/0) ZONECODE/ZONENAME field, point-in-polygon @ 29.617258375565,-81.193565937186, 0-tolerance miss but 10m buffer returned 3 unanimous R-1/CITYNAME=UNINCORPORATED polygons, verified live 2026-08-25'
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones
  WHERE parcel_id = '20-10-31-3050-00080-0050' AND jurisdiction_id = 1184
);
