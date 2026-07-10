-- SHARD-11 (palm_beach, miami_dade): miami_dade criterion I backfill
-- dispatch_id: 7a6b2043-0106-46ec-8afa-c8362cb2b9bc
-- Session: architect-20260702T080000
--
-- LIVE VERIFICATION (2026-07-02, this session, before writing this fix):
-- palm_beach: pencil_dod_evaluate_county('palm_beach') = 10/10 already gold.
-- miami_dade: pencil_dod_evaluate_county('miami_dade') = 9/10 (A,B,C,D,E,F,G,H,J
-- pass; only I fails at 91.8%, card_complete=326 of 355). The brief's C/D/E
-- numbers for miami_dade (3.7%) are STALE -- prior shards already fixed those.
--
-- ROOT CAUSE (I criterion = property_address + lat/lon + assessed/market value +
-- parcel_id linked to a zoned row in v_zoning_gold_standard_card): 29 of 355
-- miami_dade rows fail. 9 have no parcel_id at all (garbage case types --
-- "MULTIPLE PARCELS" / "Property Appraiser" / "ALCOHOLIC BEVERAGE LICENSE"
-- placeholder addresses, alimony/lien/business-license cases with no single
-- resolvable parcel) -- left untouched, not fabricated. Of the remaining 20,
-- 9 have real Miami-Dade 13-digit folio numbers that exist in fl_parcels
-- (FL DOR NAL, VERIFIED) with real centroid_lat/centroid_lng + jv/av_sd, but
-- were missing lat/lon + value on multi_county_auctions and (8 of the 9) had
-- no parcel_zones row. 3 folios (28-2210-014-3240, 30-2107-023-0020,
-- 30-4935-018-0250) do NOT exist in fl_parcels at all -- left unresolved
-- (fail-loud, not guessed) rather than force-matched to a nearby folio.
--
-- Zone codes for the 8 parcels needing a parcel_zones row were queried LIVE
-- against Miami-Dade's official zoning ArcGIS service
-- (gisweb.miamidade.gov/arcgis/rest/services/LandManagement/MD_Zoning/MapServer,
-- layer 1 = Unincorporated Zoning, layer 2 = Municipal Zoning) via a
-- point-in-polygon query on each parcel's fl_parcels centroid. Palmetto Bay
-- had no jurisdictions row -- added below (E-M zone). Miami/Miami
-- Gardens/Doral/unincorporated jurisdictions already existed.
--
-- AUDIT FLAG (out of scope for this fix, reported not silently fixed): 5
-- pre-existing miami_dade parcel_zones rows (incl. 35-3007-003-0250, which is
-- why it only needed geo+value here, not a zoning insert) carry
-- source='shard3_miami_dade_fix_v1_HYPOTHESIS' -- unverified guessed zoning
-- from a prior shard, counted toward the currently-passing G/I metrics. Not
-- touched here (boundaries: this session owns only the I-criterion gap on
-- palm_beach/miami_dade); flagged for a future ULTRALOOP refuter pass on G.

-- 1) Add missing Palmetto Bay jurisdiction (Miami-Dade)
INSERT INTO jurisdictions (name, county, county_name, state)
SELECT 'Palmetto Bay', 'Miami-Dade', 'Miami-Dade', 'FL'
WHERE NOT EXISTS (
  SELECT 1 FROM jurisdictions
  WHERE name = 'Palmetto Bay' AND lower(coalesce(county_name, county)) = 'miami-dade'
);

-- 2) parcel_zones inserts -- live ArcGIS point-in-polygon query, 2026-07-02
WITH j AS (
  SELECT id, name FROM jurisdictions
  WHERE lower(coalesce(county_name, county)) = 'miami-dade'
    AND name IN ('Miami-Dade County (Unincorporated)', 'Miami', 'Miami Gardens', 'Doral', 'Palmetto Bay')
)
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT v.parcel_id, j.id, v.zone_code, v.zone_name,
       'miamidade_gisweb_arcgis_live_query:shard11_miami_dade:2026-07-02', CURRENT_DATE
FROM (VALUES
  ('30-4018-001-0860', 'Miami-Dade County (Unincorporated)', 'RU-1', 'Single-family Residential District 7,500 ft2 net'),
  ('30-5936-005-0500', 'Miami-Dade County (Unincorporated)', 'RU-1', 'Single-family Residential District 7,500 ft2 net'),
  ('30-3111-008-0120', 'Miami-Dade County (Unincorporated)', 'RU-2', 'Two-family Residential District, 7,500 ft2 net'),
  ('30-6927-032-0100', 'Miami-Dade County (Unincorporated)', 'NCUC', 'Naranja Urban Center'),
  ('30-2232-010-0120', 'Miami-Dade County (Unincorporated)', 'RU-3M', 'Minimum Apartment House 12.9 units/net acre'),
  ('01-4106-021-0300', 'Miami', 'T3-R', NULL),
  ('33-5022-008-0170', 'Palmetto Bay', 'E-M', NULL),
  ('34-2105-011-0150', 'Miami Gardens', 'R-1', NULL),
  ('35-3007-003-0250', 'Doral', 'MF-1', NULL)
) AS v(parcel_id, jurisdiction_name, zone_code, zone_name)
JOIN j ON j.name = v.jurisdiction_name
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id);

-- 3) multi_county_auctions geo + value backfill -- VERIFIED from fl_parcels
-- (FL DOR NAL live data: centroid_lat/centroid_lng, jv=market value,
-- av_sd=assessed value school district)
UPDATE multi_county_auctions a
SET latitude = v.lat, longitude = v.lng,
    assessed_value = v.av_sd, market_value = v.jv
FROM (VALUES
  ('30-4018-001-0860', 25.7426795515574::double precision, -80.3822568980762::double precision, 736931::numeric, 736931::numeric),
  ('30-5936-005-0500', 25.6090972904094, -80.3820329566495, 118860, 422320),
  ('30-3111-008-0120', 25.8476069911335, -80.212497446997, 379479, 379479),
  ('30-6927-032-0100', 25.5256179426461, -80.4183323441399, 327320, 327320),
  ('30-2232-010-0120', 25.8777003687918, -80.1710979878227, 421327, 421327),
  ('01-4106-021-0300', 25.7701322653581, -80.2744805197618, 542029, 542029),
  ('33-5022-008-0170', 25.6304357141939, -80.3236930331892, 374920, 829931),
  ('34-2105-011-0150', 25.9436664478327, -80.2744716337668, 129915, 394690),
  ('35-3007-003-0250', 25.846648, -80.3830925, 337324, 522850)
) AS v(parcel_id, lat, lng, av_sd, jv)
WHERE a.county = 'miami_dade' AND a.parcel_id = v.parcel_id;

-- 4) REVERT of 3 of the 8 step-2 parcel_zones inserts (NCUC / T3-R / E-M) --
-- applied and then immediately reverted live in this same session after
-- verification caught a regression: these 3 codes had no pre-existing
-- zoning_districts row, so v_zoning_district_applicability defaulted their
-- far_applicable/pk1000_applicable to true (COALESCE(...,true)) with no
-- zone_standards data behind them. That flipped v_zoning_gold_standard_kpi_v3
-- pct_far_of_applicable/pct_pk1000_of_applicable for miami_dade from
-- NULL-and-ignored-by-LEAST() to a real 0.0%, crashing criterion G from
-- PASS (100.0) to FAIL (0.0). The other 5 step-2 inserts (RU-1 x2, RU-2,
-- R-1, MF-1) join existing zoning_districts rows with correct
-- category/far_regulated/density_regulated data and do NOT regress G --
-- confirmed live: G=99.6 PASS after this revert, I=93.5 (up from 91.8,
-- still short of the 95% gate). Re-adding NCUC/T3-R/E-M requires real
-- ordinance-sourced category classification first (see follow-up session
-- research) -- guessing would risk repeating this exact regression.
DELETE FROM parcel_zones
WHERE parcel_id IN ('30-6927-032-0100', '01-4106-021-0300', '33-5022-008-0170')
  AND source = 'miamidade_gisweb_arcgis_live_query:shard11_miami_dade:2026-07-02';
