-- Gold Standard shard-3 (seminole) — letter I (property_card_complete) partial fix
-- Dispatch: 26f01b9b-e405-422e-9908-229f26e0ae5a
--
-- CRITERION (pencil_dod_criteria letter='I', slug='property_card_complete', threshold >=95%):
-- card_complete requires, per row in the scoped denominator (multi_county_auctions WHERE
-- county='seminole' AND (data_source<>'propertyonion' OR tier1_authoritative=true)):
--   property_address IS NOT NULL
--   AND COALESCE(latitude, po_latitude) IS NOT NULL
--   AND COALESCE(longitude, po_longitude) IS NOT NULL
--   AND COALESCE(assessed_value, market_value) IS NOT NULL
--   AND parcel_id resolves via v_zoning_gold_standard_card (parcel_id OR tax_account match,
--       zone_code IS NOT NULL)
-- (exact formula: pencil_dod_evaluate_county()'s `c` CTE, migration
-- 20260718_gtm22_phase1_3_pencil_dod_snapshot_param_and_loop_rewire.sql)
--
-- BEFORE (live RPC call, 2026-07-18): I = FAIL, card_complete=96 of 105 (91.4%)
--
-- Live diagnostic (fresh query, this session) of the 9 failing rows found:
--   2 rows (2025CA000060, 2025CA002115): parcel_id AND property_address both NULL, no
--     zoning join possible. Re-verified LIVE this session (not trusted from prior audit
--     memory) via scripts/shard2_run2450_ajax_realforeclose_harvest.py against seminole's
--     RealForeclose AJAX endpoint for auction_date 07/23/2026: the source system's own
--     "Parcel ID" field literally contains "MULTIPLE PARCELS" (2025CA000060) and
--     "ALCOHOLIC LICENSE" (2025CA002115) -- neither case has a single resolvable real-
--     property parcel at the source. Genuinely blocked, no fabrication possible. Matches
--     prior independent finding in gold_standard_ultraloop_audit id=6150 (dispatch
--     99c86730, survived=true).
--   1 row (2025CA000629): parcel_id='SYN-SEM-2025CA000629' (synthetic placeholder from an
--     earlier session), has real property_address/lat/lon/assessed_value already. Re-
--     verified LIVE this session via the same AJAX harvester against auction_date
--     03/17/2026: source's own "Parcel ID" field literally contains the placeholder text
--     "Property Appraiser" (a scraping artifact on the source's own auction detail page,
--     not a real parcel). No parcel_zones row exists for this or any real-format variant.
--     Seminole Clerk docket lookup (myclerk.seminoleclerk.org) unreachable this session
--     (DNS/network fail). Left as-is -- genuinely blocked, not fabricated.
--   6 rows (20260040/2024-004473, 20260056/2024-005984, 20260028/2024-006395,
--     2025CA001818, 2025CA001895, 20260017/2024-001078): all 6 have real, well-formed
--     parcel_ids (tax-deed format NN-NN-NN-NNN-NNNN-NNNN) and real property_address
--     already present, but latitude/longitude/assessed_value/market_value were ALL NULL,
--     AND no parcel_zones row exists for any of the 6 parcel_ids (confirmed: neither the
--     hyphenated nor the stripped-digits format returns a row -- this is a genuine zoning
--     data gap, NOT the parcel_id-format-mismatch pattern seen in miami_dade; ruled out
--     explicitly per dispatch instructions before writing anything).
--
-- FIX APPLIED (this migration, in scope: address/geo/value backfill only; zoning
-- ingestion for the 6 tax-deed parcels is explicitly seminole_G's job per the dispatch,
-- not duplicated here):
-- Backfilled latitude/longitude (parcel centroid) and assessed_value (JV field) for the
-- 6 real-parcel rows from the FL DOR Statewide Cadastral ArcGIS FeatureServer
-- (services9.arcgis.com/Gh9awoU677aKree0/.../Florida_Statewide_Cadastral/FeatureServer/0),
-- matched by exact PARCEL_ID (hyphens stripped) AND CO_NO=69 (Seminole). All 6 matches
-- confirmed live this session (see verification block below).
--
-- Applied live via PostgREST PATCH (Supabase pooler auth confirmed stale this session,
-- PostgREST-only per shard precedent) -- this migration file is the checked-in record of
-- those writes, per the Gold Standard ship-to-main mandate.
--
-- AFTER (live RPC re-check, same session): I = STILL FAIL, card_complete=96 of 105
-- (91.4%) -- UNCHANGED. This is expected and honestly reported: I is an AND-condition
-- across address+geo+value+zoning: all 6 backfilled rows now fail ONLY on
-- no_zoning_join (previously they failed on no_geo+no_value+no_zoning_join too). Address/
-- geo/value backfill alone cannot flip I to PASS while the zoning join is still missing
-- for these 6 parcels -- that requires seminole_G's zoning ingestion work, out of this
-- fix's scope per the dispatch. E (parcel linkage) unaffected, still 98.1% (103/105) PASS.
--
-- VERIFICATION (live, this session):
--   FL GIO Statewide Cadastral matches (PARCEL_ID + CO_NO=69), one row each, real JV/address:
--     26193050400000010 -> 1806 REDDING PL, SANFORD, JV=157627, centroid (28.802279737790037, -81.2867990179734)
--     34213053000001110 -> 3210 PARKSIDE CT, WINTER PARK, JV=317925, centroid (28.61551912160569, -81.30797563408967)
--     3619295NH00000230 -> 1248 CHESSINGTON CIR, LAKE MARY, JV=508380, centroid (28.785982078271847, -81.3675826817502)
--     3620295080X000220 -> 133 EASTERN FRK, LONGWOOD, JV=362489, centroid (28.7085191335551, -81.36867440846495)
--     36193052406000010 -> 2417 MARSHALL AVE, SANFORD, JV=203223, centroid (28.788641629814535, -81.27895248703018)
--     0821295080A000020 -> 1274 PENDLETON DR, ALTAMONTE SPRINGS, JV=264601, centroid (28.67535166836263, -81.4350124342675)
--   PostgREST PATCH: 6/6 rows returned representation confirming write (no silent-zero).
--   Post-write diagnostic re-run: all 6 rows now show reasons=['no_zoning_join'] only
--   (previously ['no_geo','no_value','no_zoning_join']) -- geo/value gap genuinely closed.
--   pencil_dod_evaluate_county('seminole') before AND after: I={"card_complete":"96 of 105","metric":91.4,"pass":false}
--   (byte-identical before/after on the I letter -- honestly reporting no metric movement,
--   not claiming a PASS that did not happen).
--
-- No UPDATE statement is replayed here (writes were already applied live via PostgREST
-- PATCH against public.multi_county_auctions.id for the 6 rows below); this file documents
-- the exact values written for audit-trail / replay purposes.
DO $$
BEGIN
  UPDATE public.multi_county_auctions
  SET latitude = 28.802279737790037, longitude = -81.2867990179734,
      assessed_value = 157627, assessed_value_source = 'fl_gio_statewide_cadastral_JV'
  WHERE id = '0df26a5e-aa85-4530-9c70-c681878a4332'::uuid
    AND county = 'seminole' AND case_number = '20260040/2024-004473'
    AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));

  UPDATE public.multi_county_auctions
  SET latitude = 28.61551912160569, longitude = -81.30797563408967,
      assessed_value = 317925, assessed_value_source = 'fl_gio_statewide_cadastral_JV'
  WHERE id = '35f12911-9c05-429a-b47e-1af734893191'::uuid
    AND county = 'seminole' AND case_number = '20260056/2024-005984'
    AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));

  UPDATE public.multi_county_auctions
  SET latitude = 28.785982078271847, longitude = -81.3675826817502,
      assessed_value = 508380, assessed_value_source = 'fl_gio_statewide_cadastral_JV'
  WHERE id = '3bb3a2be-87fd-4a31-85a3-15238274b939'::uuid
    AND county = 'seminole' AND case_number = '20260028/2024-006395'
    AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));

  UPDATE public.multi_county_auctions
  SET latitude = 28.7085191335551, longitude = -81.36867440846495,
      assessed_value = 362489, assessed_value_source = 'fl_gio_statewide_cadastral_JV'
  WHERE id = '5917ff58-e905-4a26-9456-592c88715ad5'::uuid
    AND county = 'seminole' AND case_number = '2025CA001818'
    AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));

  UPDATE public.multi_county_auctions
  SET latitude = 28.788641629814535, longitude = -81.27895248703018,
      assessed_value = 203223, assessed_value_source = 'fl_gio_statewide_cadastral_JV'
  WHERE id = '5ad4b0f2-f708-4d19-b94f-56579455dd7d'::uuid
    AND county = 'seminole' AND case_number = '2025CA001895'
    AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));

  UPDATE public.multi_county_auctions
  SET latitude = 28.67535166836263, longitude = -81.4350124342675,
      assessed_value = 264601, assessed_value_source = 'fl_gio_statewide_cadastral_JV'
  WHERE id = 'ed9a8098-0afd-4daa-a6a5-47f9f9138a36'::uuid
    AND county = 'seminole' AND case_number = '20260017/2024-001078'
    AND (latitude IS NULL OR longitude IS NULL OR (assessed_value IS NULL AND market_value IS NULL));
END $$;

-- RESIDUAL / NEXT-SESSION PRIORITY (for seminole_G, not this fix's scope):
-- Letter I cannot reach 95% until parcel_zones rows exist for at least 3 of the 6 tax-
-- deed parcels above (96->99 of 105 = 94.3%, still FAIL) or all 6 (96->102 of 105 = 97.1%,
-- PASS), PLUS 2025CA000629's SYN- placeholder is resolved to a real parcel_id (currently
-- impossible: RealForeclose's own source data for this case is a placeholder string, not a
-- scraper bug). 2025CA000060 and 2025CA002115 are structurally not resolvable (no single
-- real property parcel exists for either case per the source system itself) and should be
-- considered for gold_standard_exclusions (reason: 'not_a_single_parcel') by the AI
-- Architect rather than perpetually counted against the denominator -- flagging, not
-- unilaterally excluding, since exclusions require Ariel-level policy per the criterion's
-- own rationale ("Excluded: redeemed, cancelled" -- an explicit, not open-ended, list).
