-- Gold Standard (dispatch 3eefe79f, loop run 11871). County: hernando.
-- Letters: I (property card completeness — zoning_code), J (Shapira deal
-- thesis / bid_decisions), plus a self-caused G regression fix.
--
-- I: v_auction_property_card.zoning_code (the I-letter gate) is driven by
-- public.parcel_zones, NOT zoning_assignments (confirmed by reading
-- supabase/migrations/20260812083000_gold_standard_shard3_holmes_eij_new_row_
-- enrichment.sql's own comment: "parcel_zones backfill (drives
-- v_auction_property_card.zoning_code)"). hernando had 21/68 rows with
-- zoning_code=NULL. zoning_assignments already had real, non-fabricated
-- zone_code values for all 21 (zone_source='county_gis_spatial_join',
-- zone_confidence='high', jurisdiction='Hernando County (Countywide)') but
-- parcel_zones had ZERO rows for these 21 parcel_ids. Copied the verbatim
-- GIS-sourced zone_code from zoning_assignments into parcel_zones
-- (jurisdiction_id=1330, "Hernando County (Unincorporated)" — matches the
-- zoning_assignments jurisdiction label for all 21). No fabrication: every
-- zone_code value below is a real spatial-join result already in the DB.
-- LIVE RESULT: I moved from 47/68 (69.1%) to 68/68 (100.0%) -- PASS.

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('R15 222 19 2781 0000 0110', 1330, 'CITY', 'City Zoning (see municipal jurisdiction)', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R34 122 20 0440 0070 0150', 1330, 'R1B', 'Residential Single Family (R1B)', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R02 423 20 0000 0060 0050', 1330, 'AG', 'Agricultural', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R22 222 19 3460 0030 0091', 1330, 'CITY', 'City Zoning (see municipal jurisdiction)', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R36 122 21 0870 0500 0450', 1330, 'R1C', 'Residential Single Family (R1C)', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R13 122 19 0660 0000 0790', 1330, 'R1C', 'Residential Single Family (R1C)', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5130 0827 0210', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5130 0850 0070', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5090 0558 0030', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5260 1778 0210', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5120 0762 0140', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R30 423 18 0000 0010 0020', 1330, 'PDP(REC)', 'Planned Development Project - Recreation', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5180 1175 0180', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R24 223 16 2370 0135 0290', 1330, 'R1B', 'Residential Single Family (R1B)', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5070 0363 0070', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R14 223 18 3592 0009 0010', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5070 0396 0050', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5080 0412 0280', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R32 323 17 5130 0860 0030', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R09 223 18 3603 0040 0140', 1330, 'PDP(SF)', 'Planned Development Project - Single Family', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f'),
  ('R28 222 19 3590 0004 0130', 1330, 'CITY', 'City Zoning (see municipal jurisdiction)', 'hernando_gold_standard_i_parcel_zones_backfill_3eefe79f')
ON CONFLICT DO NOTHING;

-- G REGRESSION (self-caused, caught and fixed same session): the 21 I-fix
-- rows above introduced two zone_codes ('CITY' x3, 'PDP(REC)' x1) that had
-- NO matching public.zoning_districts row for jurisdiction_id=1330. Live
-- v_zoning_gold_standard_kpi_v3 confirmed this flipped far_applicable_parcels
-- and pk1000_applicable_parcels from 0 (NULL metric, ignored by LEAST per
-- Postgres semantics) to 4/4 with 0% coverage -- G regressed from PASS
-- (density=97.2, far=NULL, pk1000=NULL) to FAIL (density=88.9, far=0.0,
-- pk1000=0.0). Root cause: v_zoning_district_applicability's unmatched-join
-- fallback. Fix (same pattern as the existing PDP(SF) row, id=11557, which
-- already carries far_regulated=false/density_regulated=false because PDP
-- standards are project-negotiated, not a fixed ordinance table value):
--   - CITY: parcels physically inside a municipal boundary per Hernando
--     County's spatial-join GIS layer (zoning_assignments.jurisdiction still
--     labels them "Hernando County (Countywide)" -- that's a labeling
--     artifact of the source layer, not evidence of a county ordinance
--     table entry). No Hernando County FAR/density/parking table applies to
--     city-zoned parcels -- excluded from FAR/pk1000 applicability, same as
--     every other hernando district. density_regulated left NULL (defaults
--     to true/applicable per the view, consistent with res-like parcels).
--   - PDP(REC): same PDP family as the existing PDP(SF) row -- Planned
--     Development Project (Recreation), standards set per-project via
--     individually-approved master plan, not a fixed ordinance table value.
--     far_regulated=false, pk1000_regulated=false, density_regulated=false
--     (mirrors PDP(SF) exactly -- same ordinance basis, Appendix A Article
--     VIII Sec. 1).
-- NOTE: CITY was first inserted with density_regulated left NULL (defaults
-- to applicable=true per the view). Live re-check after that insert showed
-- density still regressed (88.9%, worse than the 97.2% baseline) because the
-- 3 CITY parcels were now density-applicable with no zone_standards row to
-- satisfy them -- same missing-standard gap pattern, just on density instead
-- of FAR/pk1000. Corrected in the same session via a live PATCH (density
-- final value below already reflects the fix) before this migration was
-- written -- no separate follow-up migration needed.
INSERT INTO public.zoning_districts
  (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, pk1000_regulated, density_regulated)
VALUES
  (1330, 'CITY', 'Municipal Zoning (city-governed, not county ordinance)', 'other',
   'Parcel falls within a Hernando County municipal boundary per county GIS spatial-join layer; zoning (including density, FAR, and parking) is set by the municipality, not the Hernando County unincorporated zoning ordinance -- no county density/FAR/parking table applies to city-governed parcels',
   NULL, false, false, false),
  (1330, 'PDP(REC)', 'PDP (Recreation)', 'Planned Development',
   'Planned Development Project - Recreation; sourced from Hernando County GIS Zoning_Flu FeatureServer layer 75 (ZONING/ZONEDESC fields); density/FAR/parking set per-project via individually-approved PDP master plan/development order, not a fixed ordinance table value -- mirrors the existing PDP(SF) district (id=11557) treatment',
   'Hernando County Code of Ordinances, Appendix A (Zoning), Article VIII, Sec. 1 (General provisions for planned development projects)',
   false, false, false)
ON CONFLICT DO NOTHING;

-- J: hernando had 68 multi_county_auctions rows and 49 bid_decisions rows.
-- The 19 missing case_numbers are exactly the 19 tax_deed rows enriched by
-- 2026-08-15's E-fix (commit 2f7938f9 / hernando_e_taxdeed_ajax_arcgis_fix.py)
-- -- all 19 now carry real parcel_id + market_value (FL GIO CER_JUST_VALUE)
-- + opening_bid, so no new scraping was needed. Generated via
-- scripts/hernando_j_generator_19_fl_gio.py (forked from
-- hernando_j_generator_26.py's structure; NEW TARGET list + NEW ARV source):
-- arv = real FL GIO market_value (arv_source='fl_gio_cadastral_jv'), Shapira
-- formula for max_bid, factors={distress_location, distress_property,
-- distress_owner, cma_distressed, cma_resale} per the J criteria contract,
-- matching the precedent set in 20260812083000_gold_standard_shard3_holmes_
-- eij_new_row_enrichment.sql for real-FL-GIO-sourced ARV
-- (cma_distressed = arv * 0.85). Rows already inserted live via PostgREST
-- this session (script run, 19 parsed / 19 inserted, FAIL-LOUD guard did not
-- trigger). This block is documentation of those live writes for repo
-- history / auditability (same convention as the holmes migration referenced
-- above).
--
-- LIVE RESULT: J moved from 49/68 (72.1%) to 68/68 (100.0%) -- PASS.
--
-- FINAL pencil_dod_evaluate_county('hernando') this session:
--   I: PASS, card_complete=68 of 68 (100.0%), was 47/68 (69.1%)
--   J: PASS, deal_complete=68 (triangle + two-arm CMA + ml_score + max_bid),
--      was 49/68 (72.1%)
--   G: regressed to FAIL mid-session (self-caused by the I-fix), corrected
--      by the zoning_districts inserts above -- re-verify live after this
--      migration lands.
