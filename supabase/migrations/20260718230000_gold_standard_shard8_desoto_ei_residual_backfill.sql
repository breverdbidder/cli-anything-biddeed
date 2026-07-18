-- Gold Standard shard-8 (db449ff0) desoto E/I residual gap closure
-- Session: architect-20260718T160000 (2nd firing, same dispatch), ultracode workflow wf_60c2c2af-950
-- Both findings adversarially verified (survived=true) before write.

-- Case 23CA362 (1549 SW WISTERIA ST, Arcadia FL): E gap (no parcel_id).
-- FL GIO Statewide Cadastral CO_NO=24 exact address+owner match (owner Ellen Wigmore,
-- independently corroborated against DeSoto Clerk foreclosure-sale notice PDF).
UPDATE multi_county_auctions
SET parcel_id = '123824038800000010',
    latitude = 27.194366,
    longitude = -81.867988,
    assessed_value = 191579,
    market_value = 191579,
    assessed_value_source = 'fl_gio_cadastral_2025_co24:shard8_db449ff0_desoto_23CA362',
    owner_name = COALESCE(owner_name, 'WIGMORE ELLEN'),
    updated_at = now()
WHERE county = 'desoto' AND case_number = '23CA362';

-- Case 26-06-TD (3785 NE BONANZA PARK AVE, Arcadia FL): I gap (missing geo/value).
-- On-file folio '20-37-25-00529-0000-015A' was a data-entry digit transposition;
-- corrected against DeSoto County Property Appraiser's live GIS record search
-- (desotopa.com/gis, S/T/R 20-37-25, use code VACANT). Lat/long cross-verified via
-- US Census Bureau geocoder on the exact site address (independent, reproducible match).
UPDATE multi_county_auctions
SET parcel_id = '20-37-25-0059-0000-015A',
    latitude = 27.25002513054,
    longitude = -81.826423250837,
    assessed_value = 10238,
    market_value = 13247,
    assessed_value_source = 'desoto_pa_gis:shard8_db449ff0_26-06-TD',
    updated_at = now()
WHERE county = 'desoto' AND case_number = '26-06-TD';
