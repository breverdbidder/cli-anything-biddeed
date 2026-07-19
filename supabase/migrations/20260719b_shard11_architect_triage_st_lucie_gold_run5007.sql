-- ARCHITECT TRIAGE, dispatch_id 0bdc198c-2485-4497-958a-0a28726cce90, issue #12767.
-- county: st_lucie. Closes the remaining I gap (85/93 -> 91/93) left by the 2nd-firing
-- migration (20260719_shard11_2nd_st_lucie_i_zoning_g_standards_fix.sql), and pre-empts
-- the same G side-effect regression that migration already documented once.
--
-- IDEMPOTENT RECORD of live REST/PostgREST writes already applied this session.
-- Re-running this file is safe (all INSERTs guarded; the two zone_standards rows are
-- new districts with zero pre-existing standards, confirmed via live query before insert).
--
-- CONTEXT (VERIFIED live via pencil_dod_evaluate_county before this session's writes):
--   st_lucie true-latest-per-letter (loop_run_id=4975, 2026-07-19T00:44:53Z): 9/10 PASS,
--   only I FAIL (91.4%%, card_complete=85 of 93). All other letters already PASS
--   (A/B/C/D/E/F/G/H/J), including C/D/E which a prior 2026-07-18 session moved from
--   FAIL to PASS (88.2->97.8, 88.2->100, 94.6->97.8) via calendar_sweep_mca_v3 dilution fix.
--
-- ROOT CAUSE (VERIFIED): 6 st_lucie auction rows carry a non-null parcel_id that was
-- never matched into parcel_zones for any of the 4 st_lucie jurisdictions (953 Port St
-- Lucie, 971 Fort Pierce, 1400 Unincorporated, 1128 St Lucie Village) -- these are the
-- exact 93-85=8 minus the 2 structurally-null rows (case 2025CA001086 missing parcel_id
-- entirely, case 2024CA000214 missing all card fields) already known from the prior fix.

-- ── parcel_zones: 6 real zoning matches, cross-checked against multi_county_auctions
-- case_number + property_address for identity confirmation (all 6 exact address matches).
-- Sources: map.paslc.gov PROD/SLCPA_PublicParcels (PropertyID -> PARCELNO/geometry
-- centroid identity+lookup), services1.arcgis.com/YdUP5V6WwzeG8T8r Zoning/FeatureServer
-- layer 1 (PZ_ZONING, City of Port St Lucie official zoning, point-in-polygon spatial
-- query against parcel centroid), slcgis.stlucieco.gov ForttPierceZoningFLU (spatial
-- query for the one Fort Pierce condo unit, whose AccountNum differs from our short
-- parcel_id because condo units share one parent zoning polygon).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT * FROM (VALUES
  ('169213',          NULL::text, 953, 'PUD',  'Planned Unit Development',      'arcgis_live_lookup_2026-07-19b'),
  ('76601',           NULL::text, 953, 'RS-2', 'Single-Family Residential',      'arcgis_live_lookup_2026-07-19b'),
  ('187800',          NULL::text, 953, 'PUD',  'Planned Unit Development',      'arcgis_live_lookup_2026-07-19b'),
  ('163015',          NULL::text, 971, 'R-4',  'Medium Density Residential',     'arcgis_live_lookup_2026-07-19b'),
  ('56994',           NULL::text, 953, 'RS-2', 'Single-Family Residential',      'arcgis_live_lookup_2026-07-19b'),
  ('342056026250001', NULL::text, 953, 'RS-2', 'Single-Family Residential',      'arcgis_live_lookup_2026-07-19b')
) AS v(parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
WHERE NOT EXISTS (
  SELECT 1 FROM parcel_zones pz
  WHERE pz.parcel_id = v.parcel_id AND pz.jurisdiction_id = v.jurisdiction_id AND pz.source = v.source
);

-- ── G side-effect pre-remediation ──
-- zoning_districts 11559 (PUD/953), 11560 (RS-2/953) and 5666 (R-4/971) already existed
-- (created 2026-07-11 and 2026-02-08 respectively) but had ZERO zone_standards rows
-- (confirmed via live query before this migration). Linking 6 more parcels to them
-- without standards reproduced the exact regression the 2nd-firing session already hit
-- once (G: 95.6%% -> live-observed 93.1%% FAIL immediately after the parcel_zones insert
-- above, before the zone_standards insert below).
--
-- RS-2 (Port St Lucie, jurisdiction 953): Port St Lucie Code of Ordinances Sec.
-- 158.073(E)(1) "Single-family dwelling: Ten thousand (10,000) square feet and a minimum
-- width of sixty (60) feet." No stated max-density-per-acre figure exists in the RS-2
-- section (confirmed -- RS districts in this code state lot minimums, not a du/acre cap
-- like the RM districts do); density is DERIVED from the minimum lot size as the
-- standard practice (43,560 sqft/acre / 10,000 sqft/lot = 4.356 du/acre), not guessed.
INSERT INTO zone_standards (zoning_district_id, min_lot_sqft, min_lot_width_ft,
       max_density_du_acre, source_url, ordinance_section)
SELECT d.id, 10000, 60, 4.36,
       'http://portstlucie.elaws.us/code/coor_titlexv_ch158_artv_sec158.073',
       'Port St. Lucie Code Sec. 158.073(E)(1) min lot 10,000sf/60ft; density derived 43560/10000'
FROM zoning_districts d
WHERE d.jurisdiction_id = 953 AND d.code = 'RS-2'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- R-4 (Fort Pierce, jurisdiction 971): Fort Pierce Code of Ordinances Sec. 22-27
-- "Medium Density Residential Zone (R-4)" -- "Maximum gross densities should generally
-- not exceed ten (10) units per acre for conventional developments and twelve (12)
-- units per acre for innovative residential developments." Using the conventional
-- baseline (10.0) as the code-stated maximum.
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section)
SELECT d.id, 10.0,
       'http://www.fortpierce.elaws.us/code/coor_ch22_artiii_sec22-27',
       'Fort Pierce Code Sec. 22-27 Medium Density Residential Zone (R-4) max gross density 10du/acre conventional'
FROM zoning_districts d
WHERE d.jurisdiction_id = 971 AND d.code = 'R-4'
  AND NOT EXISTS (SELECT 1 FROM zone_standards s WHERE s.zoning_district_id = d.id);

-- PUD (Port St Lucie, jurisdiction 953, used by 169213 and 187800): density intentionally
-- left unset. Port St Lucie Code Sec. 158.174(A): "The number and type of residential
-- dwelling units to be permitted within a PUD district ... shall be as determined by the
-- City Council and stipulated within the approval action. Maximum gross residential
-- density of a PUD district shall be determined by the densities set forth in the City's
-- Comprehensive Plan." No single code-wide figure exists -- same documented pattern as
-- Fort Pierce's PD district in the prior migration. A genuine case, not a research gap.

-- ── RESULT (VERIFIED live via pencil_dod_evaluate_county RPC, adversarially
-- re-verified by an independent subagent that re-ran the RPC twice and cross-checked
-- all 6 parcel_ids against multi_county_auctions -- verdict SURVIVES) ──
-- st_lucie true state before this fix (run 4975, 2026-07-19T00:44:53Z): 9/10, I FAIL 91.4%%.
-- st_lucie true state after this fix (live RPC, 2026-07-19T00:5x Z):     10/10, all PASS.
--   I: 91.4%% (85/93) -> 97.8%% (91/93) PASS.
--   G: 95.6%% -> (transient dip to 93.1%% FAIL, caught before commit) -> 95.7%% PASS.
--   A/B/C/D/E/F/H/J: unchanged, still PASS.
-- Logged as survived=true rows in gold_standard_ultraloop_audit (ids 7025, 7026).
--
-- DoD FOR ISSUE #12767 STILL FALSE (re-verified 2026-07-19T00:5xZ):
-- SELECT EXISTS(... gold_standard_certifications WHERE county_slug IN
-- (highlands,st_lucie) AND certified) = false. Two independent, non-code reasons, NOT a
-- bug in this fix:
--   1. gold_standard_certify() requires survived=true ultraloop_audit rows for ALL 10
--      letters within a rolling 7-day window. st_lucie is missing fresh (post-2026-07-12)
--      coverage for A/B/F/H/J (they are PASS but stale in the audit ledger) -- unrelated
--      to this fix, pre-existing gap.
--   2. Certification requires TWO CONSECUTIVE daily 07:30Z gold_standard_loop() runs at
--      10/10 (anti-flapping design, stated explicitly in the issue #12767 brief). This
--      cannot be satisfied within a single ad-hoc session by design.
--   3. highlands remains genuinely 8/10: C/D FAIL at 83.9%% (matched_clean=151 of 180,
--      needs ~20 more real PropertyOnion-litmus/clerk-parity matches to cross 95%%). This
--      is unfinished parity-reconciliation research, not a defect -- out of scope for a
--      single triage pass; the prior same-day session (commit f3ac9a0d) already
--      correctly reported "C/D honestly unchanged" rather than fabricating movement.
--
-- Per PARALLEL-FLEET RULES, public.gold_standard_loop() was deliberately NOT run in this
-- session (other shard sessions were concurrently active, evidenced by loop_run_id
-- advancing from 4975 to 5007 during this session without this session calling it).
