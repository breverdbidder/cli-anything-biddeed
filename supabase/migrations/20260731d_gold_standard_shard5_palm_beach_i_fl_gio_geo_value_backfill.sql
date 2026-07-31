-- Gold Standard shard-5 palm_beach letter I: FL GIO real-data backfill for the
-- 65 I-failing rows (card_complete=667 of 732, 91.1%).
--
-- ROOT-CAUSE INVESTIGATION (fresh-verified this session, REFUTES the dispatch
-- brief's "parcel ID format mismatch" hypothesis):
--   The brief hypothesized that mca.parcel_id (flat 12-digit PCN) and
--   parcel_zones.parcel_id (dashed PAPA-style PCN) were two DIFFERENT ID
--   conventions requiring a crosswalk. This was checked directly:
--     - Palm Beach County's own authoritative countywide ArcGIS layer
--       (PAO_PARCELS, services1.arcgis.com/ZWOoUZbtaYePLlPw) stores PARID as
--       a FLAT 17-digit string with confirmed segment boundaries
--       CTY(2)-RNG(2)-TWP(2)-SEC(2)-SUBD(2)-BLK(3)-LOT(4), matching the
--       PBC Property Appraiser's own published PCN glossary (pbcpao.gov/pcn-info.htm).
--     - Dash-inserting mca.parcel_id flat-17 values at exactly those
--       boundaries and testing the reconstructed dashed string against
--       parcel_zones for palm_beach: 0 of 95 matched.
--     - Conclusion: there is NO systematic format bug. parcel_zones for
--       palm_beach simply lacks a parcel_zones ROW at all (any format) for
--       these 56 specific parcels -- verified by testing both the flat and
--       correctly-reconstructed dashed form directly against parcel_zones
--       and finding zero rows in either format. This is a genuine parcel_zones
--       COVERAGE gap (real zoning ingestion never reached these 56 parcels),
--       not a joinable-but-misformatted value.
--   NOTE: parcel_zones for palm_beach itself contains a MIX of formats
--   (12/17/18/19/23/26-char values), so "the" dashed format assumed by the
--   brief was already an oversimplification from a small sample.
--
--   This migration does NOT attempt to fabricate parcel_zones rows for the
--   56 zone-coverage-gap parcels (a prior session, shard7_run757, already did
--   this once via a placeholder zone_code='R-1' insert -- that pre-existing
--   fabrication is left untouched/unextended per this session's zero-
--   fabrication mandate; it is flagged here for visibility only, not fixed
--   or removed since it is out of this session's narrow scope).
--
-- WHAT THIS MIGRATION DOES:
--   Of the 65 I-failing rows, 8 lacked property_address, 53 lacked lat/long,
--   46 lacked assessed/market value. These were looked up LIVE against the
--   FL GIO Florida Statewide Cadastral FeatureServer (CO_NO=60 = Palm Beach)
--   by flat 17-digit PARCEL_ID (dashes stripped from mca.parcel_id). 58 of 65
--   resolved to a real FL GIO record with real JV (just value) and a real
--   parcel-boundary-polygon centroid (NOT a county-wide fallback centroid --
--   computed per-parcel from the actual FL GIO geometry returned for that
--   specific PARCEL_ID). 51 of those 58 needed at least one NULL field filled
--   (7 already had complete address/geo/value and were failing purely on the
--   zone-coverage gap above, so no UPDATE was needed for them). Only NULL
--   fields are ever set -- no pre-existing real value is overwritten.
--
--   7 of 65 rows remain BLOCKED and were NOT touched: their mca.parcel_id
--   values are not usable parcel identifiers at all -- "MULTIPLE PARCELS"
--   (3 rows, litigation covers >1 parcel, cannot resolve to one PCN),
--   "Property Appraiser" / "ALCOHOLIC BEVERAGE LICENSE" (2 rows, clearly
--   mis-scraped non-parcel text), and two 12-digit values
--   (004245091200, 004246231800) that are ambiguous SUBID prefixes matching
--   dozens of FL GIO parcels with no way to disambiguate to one exact lot.
--   Several of these 7 rows already contain PRE-EXISTING fabricated
--   placeholder data from a prior session (latitude/longitude =
--   26.6515/-80.3082 Palm Beach County centroid, assessed_value = 150000
--   round-number placeholder) -- this migration does NOT repeat, extend, or
--   silently rely on that pattern, and does not remove it (out of scope).
--
-- VERIFICATION (live, this session, via pencil_dod_evaluate_county('palm_beach')):
--   BEFORE: I = {"pass": false, "metric": 91.1, "detail": "card_complete=667 of 732"}
--   AFTER:  I = {"pass": false, "metric": 91.4, "detail": "card_complete=669 of 732"}
--   Fresh SQL re-check of the 63 still-failing rows: 56 blocked solely by the
--   parcel_zones coverage gap (0 overlap with enrichment gaps), 7 blocked
--   solely by unusable parcel_id values. Zero rows blocked by both.
--
-- HONESTY PROTOCOL:
--   FL GIO JV/lat/lon values below: VERIFIED (live FeatureServer query per
--     row, this session; each value is a distinct, real, parcel-specific
--     result -- not a repeated placeholder).
--   parcel_zones coverage-gap conclusion: VERIFIED (direct query, 0/95 match
--     in both flat and reconstructed-dashed format).
--   Residual 56 + 7 rows: reported as structurally blocked, not fabricated.

UPDATE multi_county_auctions SET property_address = '2707 N OCEAN BLVD 6010, BOCA RATON, FL- 33431', latitude = 26.37585017148304, longitude = -80.07100252156363, assessed_value = 525000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '5dc90bef-44a8-4411-96da-47eb1a4c0551';
UPDATE multi_county_auctions SET latitude = 26.531264953074537, longitude = -80.1548081746732, assessed_value = 481150, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'c3ede603-d323-4963-9b72-fe1459e9f238';
UPDATE multi_county_auctions SET latitude = 26.908165806707082, longitude = -80.15031081180524, assessed_value = 1355468, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'c20a1b16-4ffc-49e1-892f-9ecd6df6ca56';
UPDATE multi_county_auctions SET latitude = 26.602515948306, longitude = -80.06055901359176, assessed_value = 276339, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'c533ba8f-0482-40f9-812c-1987467d2033';
UPDATE multi_county_auctions SET latitude = 26.67802011298624, longitude = -80.17348413765964, assessed_value = 487202, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '1c40b18b-850f-4a00-ab20-16f1473e6934';
UPDATE multi_county_auctions SET latitude = 26.479922874267288, longitude = -80.14053690275924, assessed_value = 263336, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'c218d9dc-84ef-432d-8724-3acd93db822a';
UPDATE multi_county_auctions SET latitude = 26.616828822115764, longitude = -80.11171100548752, assessed_value = 303280, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '3eb0e893-18ed-4bc8-8155-3bbb65c141fe';
UPDATE multi_county_auctions SET property_address = '773 JEFFERY ST 4-303, BOCA RATON, FL- 33487', latitude = 26.40326270283699, longitude = -80.07303693388853, assessed_value = 209000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '3e854b13-a905-4dc3-9e28-6a07239c7123';
UPDATE multi_county_auctions SET latitude = 26.74370373700786, longitude = -80.11110921588988, assessed_value = 289000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'f1de26ad-5de3-4864-8b7b-31521f5c2496';
UPDATE multi_county_auctions SET latitude = 26.66137325464695, longitude = -80.10600251092973 WHERE id = '5d0b54c4-465b-4dd9-93d2-f044d51e853a';
UPDATE multi_county_auctions SET latitude = 26.43335874863039, longitude = -80.07793805539917, assessed_value = 215000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'a7131a43-4544-4ed1-b5cd-cceaafd1f78f';
UPDATE multi_county_auctions SET latitude = 26.637133314438074, longitude = -80.11887733208813 WHERE id = '9f51f285-6929-4c69-9907-9647915d9733';
UPDATE multi_county_auctions SET latitude = 26.476061291554437, longitude = -80.10284365006765, assessed_value = 224500, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '7973739f-9c71-4ec6-96bc-c7c26a0eab8a';
UPDATE multi_county_auctions SET latitude = 26.610213654796837, longitude = -80.0651243098253 WHERE id = '37d0abe9-7018-453c-9f9d-bd6e58bfcf19';
UPDATE multi_county_auctions SET latitude = 26.57362264549071, longitude = -80.05713860163237, assessed_value = 85000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '704715c6-1bb5-4961-bd9c-a8babd6a0545';
UPDATE multi_county_auctions SET latitude = 26.57905485258784, longitude = -80.05572815621582 WHERE id = '7899e0be-cdb2-4844-9568-dfbad652fcc5';
UPDATE multi_county_auctions SET latitude = 26.616379097767275, longitude = -80.14175812147528, assessed_value = 305000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '7a938dc4-c59e-4cfb-8ba5-6957df8b03b8';
UPDATE multi_county_auctions SET latitude = 26.47957029742766, longitude = -80.0916579309985, assessed_value = 151944, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'd31ded92-b62a-4ae0-b2dd-7a7349ece5d2';
UPDATE multi_county_auctions SET latitude = 26.728370959644003, longitude = -80.08075117992686, assessed_value = 235000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'f76fb8ee-c82f-4cd0-bd8c-4e2a262706ff';
UPDATE multi_county_auctions SET latitude = 26.481320334886423, longitude = -80.13380417176008 WHERE id = '0f3399aa-99d8-4e99-adb4-26219ec11b12';
UPDATE multi_county_auctions SET latitude = 26.547151043264442, longitude = -80.19007327045324, assessed_value = 4319947, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '353db304-ac95-4378-af26-345ef5d4294a';
UPDATE multi_county_auctions SET latitude = 26.445253211223264, longitude = -80.13803769239865, assessed_value = 65407, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '22414212-1851-4598-a294-8fa6ddae21b5';
UPDATE multi_county_auctions SET latitude = 26.51043759050192, longitude = -80.08894062955237, assessed_value = 240797, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'd7295bce-1c22-4a3d-94b6-96a68ad3247b';
UPDATE multi_county_auctions SET latitude = 26.764532665121518, longitude = -80.06051704547065, assessed_value = 147605, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '8538ede0-52c7-4b13-a347-a84765274b7e';
UPDATE multi_county_auctions SET latitude = 26.522807912482396, longitude = -80.13363798744531, assessed_value = 244788, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'f832988d-71dc-4d49-bbbf-3391df621019';
UPDATE multi_county_auctions SET latitude = 26.556233823383785, longitude = -80.1561914902932 WHERE id = '97208e6e-f527-4f66-b046-ce10c477edbb';
UPDATE multi_county_auctions SET latitude = 26.49542305559463, longitude = -80.06155659324588, assessed_value = 1188716, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '873589a4-4c15-471d-9613-8fb769a8bd53';
UPDATE multi_county_auctions SET latitude = 26.72975372256422, longitude = -80.06172763791437, assessed_value = 154673, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '45441ac6-cfdf-49bb-a8e1-fa5144cdbbcc';
UPDATE multi_county_auctions SET latitude = 26.480122576738456, longitude = -80.13808021408256, assessed_value = 177500, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '693cf87f-840d-4df7-b6ff-3edfa0e1ebe4';
UPDATE multi_county_auctions SET latitude = 26.369261849024927, longitude = -80.17719720088539, assessed_value = 253000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '4af5bd1f-252c-41d9-a01d-a50f57ce73f2';
UPDATE multi_county_auctions SET latitude = 26.617947133756164, longitude = -80.19350045411643, assessed_value = 905532, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'b05bf90a-9e79-4302-aedb-4dbdb8b41c76';
UPDATE multi_county_auctions SET latitude = 26.36271420061692, longitude = -80.14755516840418 WHERE id = '6343c6e3-6fe2-471a-8199-c2f8ae100611';
UPDATE multi_county_auctions SET latitude = 26.440740372543452, longitude = -80.1503272649694, assessed_value = 71407, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'f560c1ec-5ac3-413d-b9ca-0efdf749813e';
UPDATE multi_county_auctions SET latitude = 26.928256161854836, longitude = -80.07613293261407, assessed_value = 482633, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '2db7414a-ed8e-496b-84c3-cec213ccee63';
UPDATE multi_county_auctions SET latitude = 26.65993777224748, longitude = -80.2012517169326, assessed_value = 543150, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '8374d654-f2df-4338-a207-c30003bef422';
UPDATE multi_county_auctions SET latitude = 26.696498770246286, longitude = -80.20392232024503, assessed_value = 312275, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '1e95c9fc-b86d-476b-a6d9-45e6a7ff8e20';
UPDATE multi_county_auctions SET latitude = 26.406862886927044, longitude = -80.08273378345527, assessed_value = 165000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'c1d2d638-2831-4b4c-9465-b88aaa4f0f88';
UPDATE multi_county_auctions SET latitude = 26.6421321781335, longitude = -80.08223460517785, assessed_value = 379468, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'bc392b6b-6d1a-47af-ae1c-384ea0472335';
UPDATE multi_county_auctions SET latitude = 26.889266441971643, longitude = -80.11509508060409, assessed_value = 202400, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '5c697a62-3eda-4236-9b73-a6a28ce4b307';
UPDATE multi_county_auctions SET latitude = 26.518525961586487, longitude = -80.11874876848665, assessed_value = 358461, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '48f917aa-8cd4-471c-b881-a235839b447f';
UPDATE multi_county_auctions SET latitude = 26.726026412303582, longitude = -80.13639525444049, assessed_value = 320227, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '5175ba37-1ddb-4c82-80cd-28a70d7f8097';
UPDATE multi_county_auctions SET latitude = 26.34668240478078, longitude = -80.20424262851068, assessed_value = 676669, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '348008e4-3038-4ce2-9604-c1cf5842e835';
UPDATE multi_county_auctions SET latitude = 26.640281493471964, longitude = -80.08209109708619, assessed_value = 460289, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '3cff1f3f-bd36-4786-be26-6f4d60d81912';
UPDATE multi_county_auctions SET latitude = 26.46187141203029, longitude = -80.14872256542981, assessed_value = 168112, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '88d04807-c697-47ff-b3dd-0c4c3963a8b1';
UPDATE multi_county_auctions SET latitude = 26.823691699027716, longitude = -80.65989228745661, assessed_value = 112911, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'dda39e73-d490-4a73-a4bc-1fbcab5eb1c4';
UPDATE multi_county_auctions SET latitude = 26.73829085530272, longitude = -80.09246620364844, assessed_value = 185000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'b74d6df3-bde8-44f3-ba0f-04125f451d1b';
UPDATE multi_county_auctions SET latitude = 26.655517266906934, longitude = -80.24998289912446, assessed_value = 444315, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'e67ef6b9-61e3-4a33-af9a-1c1e925c009b';
UPDATE multi_county_auctions SET latitude = 26.801388631157884, longitude = -80.06563697767436, assessed_value = 365171, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'c73d37f7-d128-4ecb-acaf-e8b57ef8fed9';
UPDATE multi_county_auctions SET latitude = 26.63238423198036, longitude = -80.08094046865294, assessed_value = 60243, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '18a791bf-5e4f-48b0-9a93-b07ba9d2d87f';
UPDATE multi_county_auctions SET latitude = 26.72724958508995, longitude = -80.10581441583683, assessed_value = 165000, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = '4e16f306-3679-40b3-bdb4-7bae05f2b8fe';
UPDATE multi_county_auctions SET latitude = 26.678420823390837, longitude = -80.06484054882011, assessed_value = 325869, assessed_value_source = 'fl_gio_cadastral_co60' WHERE id = 'fd9185dd-57e4-44b7-9d8d-7f983f587242';
