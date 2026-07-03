-- SHARD-14 (hendry/santa_rosa/alachua/liberty): liberty E criterion parcel linkage.
--
-- Liberty's only auction row (id=c7b7a994-47ee-4491-942a-8deb06e7101a, case_number
-- 24-CA-22, "20892 NE Burlington rd., Hosford, FL 32334") had parcel_id/lat/lon/
-- assessed_value all NULL. fl_parcels (co_no=49 in THIS dataset -- note fl_parcels'
-- co_no numbering does NOT match fl_counties' FL-DOR-standard numbering, where
-- Liberty=39; co_no=49 rows in fl_parcels are confirmed Liberty via Bristol/Hosford/
-- Sumatra/Telogia city names, a real discrepancy worth flagging separately, not a
-- county mix-up here) has an exact, unique street-address match:
--   parcel_id='0261S6W00725000', phy_addr1='20892 NE BURLINGTON RD', HOSFORD FL 32334
--   centroid_lat=30.3600103, centroid_lng=-84.8051394, jv=104221 (market_value),
--   av_sd=90150 (assessed_value).
--
-- Applied live via PostgREST PATCH (psql pooler auth fails in this sandbox, same
-- constraint prior shard sessions documented today). Equivalent SQL:

UPDATE public.multi_county_auctions
SET parcel_id = '0261S6W00725000',
    latitude = 30.3600103,
    longitude = -84.8051394,
    assessed_value = 90150,
    market_value = 104221,
    assessed_value_source = 'fl_parcels_nal_co49_exact_addr_match'
WHERE id = 'c7b7a994-47ee-4491-942a-8deb06e7101a'
  AND lower(county) = 'liberty';

-- VERIFIED live: pencil_dod_evaluate_county('liberty') E moved
--   0.0% (parcel_linked=0 of 1) -> 100.0% (parcel_linked=1 of 1)
--
-- I criterion for this same row does NOT flip: v_zoning_gold_standard_card requires
-- zone_code IS NOT NULL, and Liberty has zero parcel_zones/zoning_districts coverage
-- (only a Bristol jurisdiction row exists; this property is in unincorporated/Hosford,
-- not Bristol). Genuine blocker, not fixed here -- needs real ordinance-sourced
-- zoning ingestion for unincorporated Liberty County, out of scope for this session
-- (HARD GUARDRAIL: no fabricated/guessed zone_standards values).
