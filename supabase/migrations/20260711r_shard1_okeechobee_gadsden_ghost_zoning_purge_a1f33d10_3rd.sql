-- GOLD STANDARD SHARD-1 (duval/gadsden/okeechobee/columbia) — dispatch a1f33d10, 3rd firing
-- CRITICAL HONESTY FIX: purge live ghost-success zoning assignments feeding G/I on
-- okeechobee and gadsden. Both were caught by an independent adversarial re-check
-- of parcel_zones.source at session start (a systemic sweep, not a targeted retest
-- of the prior firing's own claims — the prior two firings' ULTRALOOP audits never
-- checked provenance of pre-existing parcel_zones rows, only of new writes).
--
-- OKEECHOBEE: 28 of 53 parcel_zones rows (jurisdiction 943) were tagged
-- zone_code='AG', zone_name='Agricultural (Okeechobee Synthetic)',
-- source IN ('shard5-run651-synthetic','shard4-run2346-synthetic'). All 28
-- parcel_ids independently confirmed to be REAL okeechobee auction parcels
-- (multi_county_auctions) — i.e. these are fabricated zone ASSIGNMENTS on real
-- parcels, not fake parcel_ids. Because AG already has a real ordinance-sourced
-- density figure (0.10 du/acre, Sec 2.01.04 / 7.02.02(C) Note 6), these 28 fake
-- links were inflating G's density-coverage numerator without ever having been
-- independently confirmed against real GIS/property-appraiser zoning data, and
-- were also counting toward I's "zoned parcel" card-complete requirement.
-- Before purge (live, this session): G density=62.7% (FAIL, <95 either way — no
-- pass/fail flip), I card_complete=49 of 54 (90.7%, FAIL either way — no flip).
-- After purge: G density=17.4% far=0.0% (honest), I card_complete=22 of 54
-- (40.7%, honest — matches the ORIGINAL dispatch-brief I figure exactly, meaning
-- the "40.7%->90.7%" improvement claimed in the prior firing's report rested
-- partly on this pre-existing (not prior-firing-authored) fabrication rather than
-- solely on the STRAP address backfill it did perform).
-- gold_standard_county_status letter pass/fail: UNCHANGED for okeechobee (G and I
-- were already FAIL before this fix; the fix corrects the underlying number, not
-- the verdict).
--
-- GADSDEN: ALL 7 parcel_zones rows (jurisdiction 925, "Quincy") were tagged
-- zone_code='R-1', source='shard8_gadsden_bootstrap_synthetic', matching real
-- gadsden auction parcel_ids. This was flagged as an "unsourced" risk by at least
-- two prior sessions (shard10 run3534, shard1 dispatch a1f33d10 1st firing) but
-- never purged because it "currently causes no metric distortion" was asserted
-- for G only — it was NOT re-checked for I. Live re-check this session: gadsden G
-- was reading a FALSE PASS at 100.0% (density=100.0) resting ENTIRELY on these 7
-- fabricated rows (zero real zoning data exists for gadsden). This is a genuine
-- PASS -> FAIL correction: gadsden's honest score drops from a reported 8/10 to
-- 7/10 (G flips FAIL; E and I were already FAIL). I card_complete also corrects
-- from 7 of 23 (30.4%, already FAIL) to 0 of 23 (0.0%, still FAIL — no flip there).
-- The Quincy R-1 zoning_districts row (id=11102, zone_standards max_density_du_acre
-- =5.00, no source_url) is now fully orphaned (0 references) but left in place —
-- it may be legitimately re-populated if a real ordinance source and a real
-- parcel-to-district link are found in a future session; it causes zero metric
-- distortion while orphaned.

BEGIN;

DELETE FROM parcel_zones
WHERE jurisdiction_id = 943
  AND source IN ('shard5-run651-synthetic', 'shard4-run2346-synthetic');

DELETE FROM parcel_zones
WHERE jurisdiction_id = 925
  AND source = 'shard8_gadsden_bootstrap_synthetic';

COMMIT;
