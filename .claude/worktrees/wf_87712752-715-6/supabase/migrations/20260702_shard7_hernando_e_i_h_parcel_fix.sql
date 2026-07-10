-- SHARD-7: hernando E/I/H fix — parcel linkage + card enrichment via FL GIO cadastral
-- dispatch_id: 010a05ae-e4f8-488a-954f-6d0497384f23
-- Session: architect-20260702T080000 (gold standard shard-7: levy, bay, hernando)
--
-- CONTEXT: applied live via Supabase REST API (PATCH), since direct psql pooler auth
-- was unavailable to this session (password auth failure on both pooler ports).
-- This file documents the exact updates applied for audit/replay.
--
-- BUG FOUND + FIXED: case 22001005CA was carrying a WRONG parcel_id/address
-- ("30541 SATINLEAF RUN" / R32 122 21 1219 0130 0620) inherited from a prior
-- session's scrape. Cross-checked against fresh hernandoclerk.com sale-list PDFs
-- (plaintiff-vs-defendant line under each case) and the FL GIO Statewide Cadastral
-- OWNER_NAME field:
--   - 22001005CA is "Magerick LLC -vs- ROBERT BURNS" -> owner BURNS ROBERT P at
--     3407 DOW LN, Spring Hill (confirmed via services9.arcgis.com FL GIO CO_NO=37).
--   - 25000696CA is "NAVY FEDERAL CREDIT UNION -vs- ROLAND AMOUZOU" -> owner
--     AMOUZOU ROLAND at 30541 SATINLEAF RUN, Brooksville — the address that had been
--     mis-attached to 22001005CA.
-- The two records' parcel/address/value/geo were swapped to the verified-correct pairing.
--
-- 6 NEW parcel links (all confirmed via owner-name cross-check between the
-- hernandoclerk.com PDF plaintiff-vs-defendant line and FL GIO OWNER_NAME):
--   23001250CA, 25000637CA, 25000885CA, 25001269CA, 25000967CA, 25000696CA
--
-- market_value = FL GIO "JV" (DOR just value) field, CO_NO=37 (Hernando).
-- latitude/longitude = FL GIO parcel centroid (outSR=4326).
--
-- E impact (live-verified via pencil_dod_evaluate_county('hernando')):
--   parcel_linked 11/23 (47.8%) -> 17/23 (73.9%)
-- H impact: 95.8h -> 0.0h (tg_freshness_capture trigger fired on genuine content change)
-- I impact: card_complete 0/23 (0.0%) -> 7/23 (30.4%) — capped by v_zoning_gold_standard_card
--   only carrying 8 hernando parcels total (7 pre-existing TD links + 1 synthetic row);
--   the 6 newly-linked FC parcels are NOT yet in the zoning card substrate, so I cannot
--   move further without a zoning-coverage expansion for hernando (separate, larger effort
--   per brief's "G and I are not scraping problems" note — NOT attempted this session to
--   avoid guessed zoning values).
--
-- UNRESOLVED (left NULL, no guessing per HARD GUARDRAILS):
--   22000840CA - address "5187 GAINSBORO AVE" does not resolve in FL GIO/EPL Parcels
--     (only 6xxx house numbers exist on Gainsboro Ave); 5->6 OCR-corruption is plausible
--     (6187 Gainsboro, owner NICHOLSON MARIA, exists) but source PDF (28 JULY list) is a
--     scanned image with no text layer, so the plaintiff/defendant name could not be
--     cross-checked. Left unlinked rather than guess.
--   25000578CA, 25001007CA - same 28-JULY scanned-image PDF, no extractable text at all.
--   2026-011TD, 2026-018TD, 2026-030TD - previously-documented ambiguous TD parcels
--     (2/32/8 candidates respectively); no owner-name signal available for TD cases to
--     disambiguate. Left as-is from the 2026-06-24 migration.
--
-- Statements below are idempotent (case_number + county scoped) and reflect exactly what
-- was applied via REST PATCH; safe to re-run.

UPDATE multi_county_auctions
SET parcel_id = 'R32 323 17 5240 1628 0150',
    property_address = '3407  DOW LN',
    city = 'SPRING HILL',
    zip = '34609',
    market_value = 342792,
    latitude = 28.47760544407757,
    longitude = -82.49073424536559
WHERE county = 'hernando' AND case_number = '22001005CA';
-- CORRECTION: was wrongly linked to 25000696CA's parcel/address. Real case is
-- Magerick LLC -vs- Robert Burns, 3407 Dow Ln (owner match: BURNS ROBERT P).

UPDATE multi_county_auctions
SET parcel_id = 'R32 122 21 1219 0130 0620',
    property_address = '30541  SATINLEAF RUN',
    city = 'BROOKSVILLE',
    zip = '34602',
    market_value = 213978,
    latitude = 28.534541263980117,
    longitude = -82.23549211629754
WHERE county = 'hernando' AND case_number = '25000696CA';
-- NEW: Navy Federal Credit Union -vs- Roland Amouzou (owner match: AMOUZOU ROLAND).

UPDATE multi_county_auctions
SET parcel_id = 'R01 221 17 3340 0280 0110',
    property_address = '12201  HOUSE FINCH RD',
    city = 'WEEKI WACHEE',
    zip = '34614',
    market_value = 266943,
    latitude = 28.585738473190325,
    longitude = -82.52182726406336
WHERE county = 'hernando' AND case_number = '23001250CA';
-- NEW: Rocket Mortgage LLC -vs- Edward Chapel (owner match: CHAPEL EDWARD C JR).

UPDATE multi_county_auctions
SET parcel_id = 'R01 221 17 3350 0389 0150',
    property_address = '12546  MALEO RD',
    city = 'WEEKI WACHEE',
    zip = '34614',
    market_value = 269108,
    latitude = 28.610187129006096,
    longitude = -82.5364516454016
WHERE county = 'hernando' AND case_number = '25000637CA';
-- NEW: Lakeview Loan Servicing LLC -vs- Ramon Nelson (owner match: NELSON RAMON JR).

UPDATE multi_county_auctions
SET parcel_id = 'R32 323 17 5080 0401 0120',
    property_address = '9824  HORIZON DR',
    city = 'SPRING HILL',
    zip = '34608',
    market_value = 167953,
    latitude = 28.450280945873487,
    longitude = -82.56038775164998
WHERE county = 'hernando' AND case_number = '25000885CA';
-- NEW: United Wholesale Mortgage LLC -vs- Kayla O'Keefe (owner match: OKEEFE KAYLA MARY).

UPDATE multi_county_auctions
SET parcel_id = 'R04 123 21 1090 00C0 0010',
    property_address = '32350  MARCHMONT CIR',
    city = 'DADE CITY',
    zip = '33523',
    market_value = 203760,
    latitude = 28.513339367977096,
    longitude = -82.21106344636512
WHERE county = 'hernando' AND case_number = '25001269CA';
-- NEW: Freedom Mortgage Corporation -vs- Eddie Rios (owner match: RIOS EDDIE).

UPDATE multi_county_auctions
SET parcel_id = 'R36 223 18 2690 0180 0090',
    property_address = '237  BROAD ST',
    city = 'BROOKSVILLE',
    zip = '34604',
    market_value = 72714,
    latitude = 28.43806941929962,
    longitude = -82.4599676558399
WHERE county = 'hernando' AND case_number = '25000967CA';
-- NEW: US Bank National Association -vs- Cooper Knowles (owner match: KNOWLES COOPER B).
-- Also corrects zip from OCR-garbled 34504 -> real 34604.

-- ENRICHMENT ONLY (already-correct parcel links from the 2026-06-24 migration; add
-- market_value + lat/long so criterion I has the full card, pending zoning-card coverage).
UPDATE multi_county_auctions SET market_value = 81580,  latitude = 28.556529746058665, longitude = -82.39047846221642 WHERE county = 'hernando' AND case_number = '2024-077TD';
UPDATE multi_county_auctions SET market_value = 70211,  latitude = 28.487526157292912, longitude = -82.17081385820856 WHERE county = 'hernando' AND case_number = '2026-021TD';
UPDATE multi_county_auctions SET market_value = 395138, latitude = 28.514939519586616, longitude = -82.40635326110105 WHERE county = 'hernando' AND case_number = '2026-022TD';
UPDATE multi_county_auctions SET market_value = 143346, latitude = 28.56033061635302,  longitude = -82.49716800700304 WHERE county = 'hernando' AND case_number = '2026-023TD';
UPDATE multi_county_auctions SET market_value = 68083,  latitude = 28.537304490732776, longitude = -82.52920540696157 WHERE county = 'hernando' AND case_number = '2026-024TD';
UPDATE multi_county_auctions SET market_value = 72438,  latitude = 28.60243777089335,  longitude = -82.5163269616722  WHERE county = 'hernando' AND case_number = '2026-029TD';
UPDATE multi_county_auctions SET market_value = 112668, latitude = 28.55622833019289,  longitude = -82.48958087349146 WHERE county = 'hernando' AND case_number = '2026-032TD';
UPDATE multi_county_auctions SET market_value = 301810, latitude = 28.491707782891357, longitude = -82.46821507418989 WHERE county = 'hernando' AND case_number = '23001588CA';
UPDATE multi_county_auctions SET market_value = 291668, latitude = 28.496089568266555, longitude = -82.54532019942657 WHERE county = 'hernando' AND case_number = '25000736CA';
UPDATE multi_county_auctions SET market_value = 325772, latitude = 28.594795032766164, longitude = -82.52079094299572 WHERE county = 'hernando' AND case_number = '25000792CA';

-- VERIFICATION (run after apply):
-- SELECT public.pencil_dod_evaluate_county('hernando');
-- Expected: E metric 47.8 -> 73.9 (parcel_linked 11 -> 17 of 23)
--           H metric ~95.8h -> ~0h (PASS)
--           I metric 0.0 -> 30.4 (card_complete 0 -> 7 of 23; still FAIL, gated by
--             narrow zoning-card substrate, not by this migration's data quality)
