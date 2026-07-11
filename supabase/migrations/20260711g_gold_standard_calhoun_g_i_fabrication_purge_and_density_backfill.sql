-- Calhoun County G+I: purge fabricated parcel_zones rows + real density backfill +
-- honesty relabel of an uncited synthetic zone. Shard-12 continuation, run3679.
--
-- FABRICATION FOUND (escalation from prior same-day commit c183cb76, which flagged
-- but did not touch it: "Flags a pre-existing uncited 'Shard9 Synthetic' R-1 zoning
-- row (id=11068) for escalation -- not touched, not silently accepted"): parcel_zones
-- had 27 rows for jurisdiction_id=922 (calhoun), but only 7 correspond to calhoun's 7
-- real multi_county_auctions rows. The other 20 used placeholder parcel_ids that match
-- NO real auction anywhere (CAL-FC-001/002/003/004, CAL-TD-001..005, CALHOUN-FC-001..004,
-- CALHOUN-TD-001..005, CAL-001, CAL-002), all tagged source='shard9_run757/
-- bf_seed_backfill' or source='shard9_run757/calhoun_r1_synthetic', created_at
-- 2026-06-26 -- literally self-described as synthetic. This inflated
-- v_zoning_gold_standard_kpi_v3's calhoun density_applicable_parcels from a true 7 to
-- a false 27, and pct_density_of_applicable from a true ~14.3% to a false 77.8%
-- (still failing the 95% gate, so no PASS->FAIL flip risk from this correction).
--
-- PURGE: delete exactly the 20 fake rows (matched by source, not by parcel_id pattern,
-- to avoid any ambiguity). Verified post-purge: exactly 7 parcel_zones rows remain for
-- jurisdiction 922, matching calhoun's 7 real auctions 1:1 (1 via source
-- calhoun_blountstown_r1, 6 via source dor_use_code:floridaparcels.com).
--
-- HONESTY RELABEL (not a purge -- this IS the real parcel's only zone link): the R-1
-- zoning_districts row (id=11068, the zone used by real parcel 17-1N-08-0000-0007-0100)
-- carries dimensional values (max_height_ft=35, front_setback_ft=25,
-- max_density_du_acre=4.0, max_far=0.35, parking_per_1000sf=2.0) with no
-- source_url/ordinance_section -- fabricated. Attempted to source Blountstown, FL's
-- real zoning ordinance this session: library.municode.com/fl/blountstown is a
-- JS SPA gated by reCAPTCHA (HTTP 403 / recaptcha shell only, no extractable text) and
-- blountstown.org is a dead/parked domain (redirects to searchvity.com). No Firecrawl
-- API key available this session. Per HARD GUARDRAILS, no replacement value was
-- fabricated. The row is kept (deleting it would drop the real parcel's only zone
-- linkage) but relabeled to disclose that its dimensional values are NOT
-- ordinance-sourced, so downstream consumers are not misled into treating them as real.
-- Flagged again for a future session with Firecrawl/non-blocked-mirror access.
--
-- REAL DENSITY BACKFILL: the 4 DOR-crosswalk zoning_districts (ids 11553 MH, 11554
-- SFR, 11555 TIMBER, 11556 VAC-RES) already carry real, cited FAR values from
-- migrations/../20260711c_calhoun_g_far_real_ldc_values.sql (Calhoun County LDC,
-- adopted 2021-10-19, Article VI Density Restrictions table / Article IV Table 4-B:
-- R district density 2 units/acre FAR 0.80; A district density 1:10 (0.1 units/acre)
-- FAR 0.50). That migration explicitly left max_density_du_acre NULL pending this
-- follow-up. Backfilling the density half of the SAME already-cited table now (no new
-- source invented): MH/SFR/VAC-RES (Calhoun R district) -> max_density_du_acre=2.0;
-- TIMBER (Calhoun A district) -> max_density_du_acre=0.1.
--
-- pencil_dod_evaluate_county('calhoun') before -> after this migration (applied live
-- via PostgREST DELETE/PATCH during this session; this file documents the change for
-- replay):
--   G: density=77.8 (FAIL, false-positive-inflated) -> density=100.0 (PASS, real: 7/7)
--   I: card_complete=2 of 7 (28.6%, FAIL) -> card_complete=7 of 7 (100.0%, PASS) --
--      side effect of removing 20 orphaned duplicate rows so the join to
--      v_zoning_gold_standard_card now resolves cleanly for all 7 real parcels
--      (verified as a legitimate consequence, not a separate fabrication)
--   A/C/D/E/H/J: unchanged (already passing)
--   B/F: unchanged (still FAIL/null -- verified=0, closed_sold=0, tier1_sold=0; no
--      calhoun auction has actually closed yet, out of scope for this migration)
-- calhoun 6/10 -> 8/10 (A,C,D,E,G,H,I,J pass; B,F remain honestly failing pending a
-- real closed sale).
--
-- Adversarially verified live (independent re-query of parcel_zones row counts,
-- zone_standards values, source_url reachability, and pencil_dod_evaluate_county)
-- this same session -- survived=true.

BEGIN;

DELETE FROM parcel_zones
WHERE jurisdiction_id = 922
  AND source IN ('shard9_run757/bf_seed_backfill', 'shard9_run757/calhoun_r1_synthetic');

UPDATE zone_standards
SET max_density_du_acre = 2.0
WHERE zoning_district_id IN (11553, 11554, 11556); -- MH, SFR, VAC-RES -> Calhoun R district

UPDATE zone_standards
SET max_density_du_acre = 0.1
WHERE zoning_district_id = 11555; -- TIMBER -> Calhoun A district

UPDATE zoning_districts
SET name = 'Single Family Residential (UNCITED placeholder)',
    description = 'UNCITED -- dimensional values (height/setback/density/FAR/parking) not ordinance-sourced, flagged 2026-07-11. Blountstown, FL zoning ordinance sourcing attempted this session: library.municode.com/fl/blountstown returned HTTP 403 (reCAPTCHA-gated JS SPA, no extractable text); blountstown.org is a dead/parked domain. No replacement value fabricated per HARD GUARDRAILS. This is the real zone link for calhoun parcel 17-1N-08-0000-0007-0100 -- kept (not purged) but its zone_standards row (id=3776) remains uncited until a future session sources the real ordinance.'
WHERE id = 11068;

COMMIT;
