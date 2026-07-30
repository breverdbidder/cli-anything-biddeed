-- GOLD STANDARD shard-7 gilchrist (dispatch 61f11933-122d-4474-acf3-65e71d7a707c,
-- loop run 7519, 3rd firing on this dispatch).
--
-- Context: the 2nd firing on this dispatch purged fabricated parcel_id/geo/value data on
-- multi_county_auctions for two case numbers (212025CA000069CAAXMX, 26-0005-TD), tracing the
-- source to two orphan parcel_zones rows tagged source='shard5_g_i_fix/shard5_gilchrist_auto'
-- (id=813717 parcel_id='11-10-16-0552-0010-0060', id=813719 parcel_id='171015'), both
-- jurisdiction_id=883 (Trenton), zone_code='R-1'. That firing deliberately left the
-- parcel_zones rows themselves untouched, flagging a future G-scoped session to first verify
-- whether removing them would regress letter G (zoning FAR/density coverage), which was
-- passing at 100.0 and driven by v_zoning_gold_standard_kpi_v3's parcel_zones-row count.
--
-- This (3rd) firing ran that G-integrity diagnosis live before touching anything:
--   - Confirmed gilchrist's real jurisdiction_ids (883 Trenton, 1008 Fanning Springs,
--     1009 Bell) rather than assuming.
--   - Confirmed both flagged rows are real, tagged with the exact source string named in
--     the task, both jurisdiction_id=883/zone_code='R-1'.
--   - Confirmed the full gilchrist parcel_zones set (8 rows total) are ALL zone_code='R-1'/
--     jurisdiction_id=883/density_applicable=true (district_id=10674, joined via
--     v_zoning_district_applicability on (jurisdiction_id, zone_code) -- no parcel_id-format
--     or STRAP-validity filter anywhere in that view's DDL).
--   - Concluded mathematically that removing the 2 flagged rows moves G's denominator/
--     numerator together (8/8 -> 6/6), so pct_density_of_applicable stays 100.0 regardless;
--     far/pk1000 are fully N/A either way (0 applicable parcels for both, unaffected by row
--     count). G's pass gate is a percentage threshold, not a raw-row-count minimum.
--
-- Applied live via Supabase REST DELETE (direct psql/pooler auth fails in this sandbox,
-- matching every prior gilchrist session's finding).

DELETE FROM parcel_zones
WHERE id IN (813717, 813719)
  AND source = 'shard5_g_i_fix/shard5_gilchrist_auto';

-- Result: gilchrist parcel_zones row count 8 -> 6, all remaining rows zone_code='R-1'/
-- jurisdiction_id=883/density_applicable=true. Live re-check of
-- pencil_dod_evaluate_county('gilchrist') immediately post-delete confirmed G UNCHANGED:
--   BEFORE: {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}
--   AFTER:  {"pass": true, "detail": "density=100.0 far= pk1000=", "metric": 100.0}
-- E and I were also re-checked in the same before/after pair and confirmed UNCHANGED at
-- 42.9% (6/14) each -- no silent movement, consistent with the fact that this delete only
-- touches parcel_zones (a zoning-districts substrate table), not multi_county_auctions
-- (the table E/I read from).
--
-- ULTRALOOP audit trail: 6 fresh survived=true rows written to gold_standard_ultraloop_audit
-- for audit-freshness letters A, B, F, G, H, J (dispatch_id
-- 61f11933-122d-4474-acf3-65e71d7a707c), plus 2 survived=false dead-end/closed-investigation
-- ledger rows for letters E (Firecrawl credit-balance re-check, still HTTP 402 / -2 credits,
-- 6th consecutive session confirming this channel dead until the 2026-08-28 billing reset)
-- and G (this parcel_zones cleanup, logged as an investigated-and-closed diagnostic/cleanup
-- action distinct from the certification claim).
