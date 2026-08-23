-- Gold Standard shard-4 (dispatch 41bd7ce3, loop run 8166) -- osceola criterion I
-- Applied LIVE via PostgREST by scripts/shard4_run8166_osceola_i_gis_backfill_41bd7ce3.py
-- (direct psql is broken in this environment; documenting the equivalent SQL here
-- per campaign guardrail #5).
--
-- CONTEXT: osceola I was 90.7% (card_complete=136 of 150), need >=95%.
-- 13 population rows had full address/geo/value but zero parcel_zones row,
-- so they never resolved through v_zoning_gold_standard_card. 9 of the 13
-- have real, live-verified zone codes from gis.osceola.org
-- (Zoning_Parcels/FeatureServer/0, field PARCELNO/PRIM_ZON, jurisdiction_id=
-- 1186 = unincorporated Osceola County). The other 4 returned PRIM_ZON=
-- 'INCORP' (annexed into Kissimmee, outside county zoning jurisdiction) and
-- were deliberately SKIPPED -- no fallback/default value assigned (see
-- scripts/shard4_run5153_osceola_i_enrichment.py docstring: an earlier
-- session's blind 'PD' fallback for INCORP/unmatched parcels was flagged
-- and reverted as fabrication on 2026-07-19/07-31, 410 ghost rows).
--
-- RESULT (verified live via pencil_dod_evaluate_county('osceola')):
--   BEFORE: I=90.7 (card_complete=136 of 150)
--   AFTER:  I=96.7 (card_complete=145 of 150)  -- PASS (>=95)

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
VALUES
  ('142731000043110020', 1186, 'AC', 'shard4_run8166_osceola_gis_live_41bd7ce3:AC'),
  ('352630495000010480', 1186, 'R-2', 'shard4_run8166_osceola_gis_live_41bd7ce3:R-2'),
  ('182733272000011140', 1186, 'PD', 'shard4_run8166_osceola_gis_live_41bd7ce3:PD'),
  ('152529543000010100', 1186, 'CR', 'shard4_run8166_osceola_gis_live_41bd7ce3:CR'),
  ('082530289200010080', 1186, 'E-1', 'shard4_run8166_osceola_gis_live_41bd7ce3:E-1'),
  ('3627316000000L1050', 1186, 'AC', 'shard4_run8166_osceola_gis_live_41bd7ce3:AC'),
  ('3627316000000L1145', 1186, 'AC', 'shard4_run8166_osceola_gis_live_41bd7ce3:AC'),
  ('3627316000000L1240', 1186, 'AC', 'shard4_run8166_osceola_gis_live_41bd7ce3:AC'),
  ('3627316000000L1620', 1186, 'AC', 'shard4_run8166_osceola_gis_live_41bd7ce3:AC')
ON CONFLICT DO NOTHING;

-- NOTE: 4 parcels deliberately excluded (PRIM_ZON='INCORP', no county-zoning
-- jurisdiction, no fallback per anti-fabrication guardrail):
--   152529105000TL0040, 182529184900011105, 152529157000010890, 152529105000TL0010
-- These remain I-incomplete (genuine structural gap: inside Kissimmee city
-- limits, need Kissimmee's own zoning layer, not Osceola County's, to close).

-- NOTE: osceola C/D (89.3%, need >=95%) were investigated in the same session
-- (scripts/shard4_run8166_osceola_cd_parity_source_backfill_41bd7ce3.py) but
-- LEFT UNFIXED -- zero rows changed. 16 rows are matched_clean/
-- tier1_authoritative=true with parity_source IS NULL, but 4 different
-- parity_source conventions are in live use for osceola tax_deed rows with
-- no evidence tying the 16 gap rows (a distinct 2026-08-18 'redeemed' batch)
-- to any single one. Assigning a label would be a guess, not a verified fix.
-- BLANK > WRONG -- see that script's docstring for full reasoning.
