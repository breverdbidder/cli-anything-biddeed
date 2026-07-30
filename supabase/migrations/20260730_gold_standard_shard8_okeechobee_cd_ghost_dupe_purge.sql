-- Gold Standard shard-8 okeechobee (dispatch ed344dc4-9b86-4f5a-97af-26ea782adcbe)
-- C/D FAIL root cause (VERIFIED live 2026-07-30): 22 of 88 multi_county_auctions rows
-- for okeechobee are literal ghost duplicates -- sale_type='foreclosure', case_number
-- matches an FL clerk "TD" (tax deed) docket pattern that never legitimately carries
-- sale_type='foreclosure', every enrichment field NULL (parcel_id/data_source/
-- parity_status/sold_amount), and an exact-matching sale_type='tax_deed' sibling row
-- exists for the SAME case_number with parity_status='matched_clean' and real tier1
-- parity_source data. These are duplicate seed-insert junk, not real foreclosure cases.
--
-- Each of the 22 ids below was independently confirmed this session to have a
-- surviving tax_deed counterpart with parity_status='matched_clean' before deletion.
-- Deleting them removes zero real information (every field was already NULL) and
-- collapses the C/D denominator from 88 to 66, matching the already-matched 66
-- tax_deed rows -> C/D 75.0%% -> 100.0%%. bid_decisions/J is keyed by case_number,
-- not row id, so the real tax_deed row (same case_number) keeps J intact.

DELETE FROM multi_county_auctions
WHERE id IN (
  '2023c54c-e0a6-45cf-867e-1282e72a9f38', -- 2026TD041
  '16f2012a-3903-4983-a358-7a157f48740d', -- 2026TD042
  'e9fab0a8-942a-41e6-afd6-b034f31b2dcb', -- 2026TD044
  '4bf2a81d-bb56-4ddd-8409-f6655e118c0f', -- 2026TD049
  'dc2f03be-a0c4-44f0-82f6-7b5855b35284', -- 2026TD050
  '26074d28-6da0-481f-bfe1-f448c0ea6fba', -- 2026TD052
  '5c88066f-403d-4351-bf13-5647668d72b8', -- 2026TD053
  '58b26e4d-b812-4899-9300-15638b6d38c2', -- 2026TD054
  'a803e92f-99f7-4b60-b782-7828e6b31009', -- 2026TD055
  '9c5e9c1f-3fe5-42e1-b689-5ef74b171608', -- 2026TD056
  '1560e95f-910c-43e1-92dd-c95c46939cca', -- 2026TD057
  'ec8c7deb-1847-49d3-beb1-3a2a50430462', -- 2026TD058
  '60c7ccc0-954c-463c-a881-e179d0797385', -- 2026TD059
  '560e460e-aaab-4e3a-b1f0-8a8686445716', -- 2026TD060
  '8bb02d40-3dce-413e-9ade-95d1e3c70a69', -- 2026TD061
  '0ed617af-83e4-4ea7-96a7-e187ed237bca', -- 2026TD062
  '9b4b0c2e-d6ff-4919-8c26-2ec65e803870', -- 2026TD063
  '2e76e764-8074-467e-9a2b-a13d74c8613b', -- 2026TD070
  '61573114-e834-49f9-87d7-cc3bff53a9df', -- 2026TD072
  'aa18618b-e41e-4975-8023-2605184f782b', -- 2026TD079
  'e41a42a4-aff9-4c56-8595-51f21dd2e7f7', -- 2026TD080
  'd1b0d2ca-462e-4adc-8924-db833a2cd822'  -- 2026TD081
)
AND lower(county) = 'okeechobee'
AND sale_type = 'foreclosure'
AND sold_amount IS NULL
AND data_source IS NULL
AND parity_status IS NULL;
