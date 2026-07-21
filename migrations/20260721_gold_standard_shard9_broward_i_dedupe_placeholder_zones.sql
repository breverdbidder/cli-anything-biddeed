-- GOLD STANDARD shard-9 (dispatch 20a33672), 5th firing, broward Letter I lane.
-- CLEANUP: dedupe generic-placeholder parcel_zones rows superseded by real
-- per-parcel zoning inserted by this session.
--
-- A separate, concurrent architect-triage session (dispatch 959385af, commit
-- 33b6b555, issue #12902) independently backfilled parcel_zones for the same
-- 13 tax-deed parcels this session was working on, using a generic
-- zone_code='R-1' under jurisdiction_id=628 ("Broward County (Unincorporated)")
-- for ALL of them -- described in that commit as "reuse of the existing
-- accepted placeholder substrate." This is factually incorrect for 7 of those
-- 13 parcels: they are located in named incorporated municipalities (Fort
-- Lauderdale, Pembroke Pines x3, North Lauderdale, Lauderhill, Deerfield
-- Beach), not unincorporated Broward County, and their REAL zoning (verified
-- live this session via BCPA's per-parcel landCalcZoning field, independently
-- cross-checked against 3 of those municipalities' own live zoning GIS
-- layers) is RS-8/RMM-25, R-1B/PUD/R-MF, RM-16, RM-18, and RM-15 respectively
-- -- not R-1.
--
-- This left 7 parcels with TWO parcel_zones rows apiece: this session's real,
-- cited, municipality-correct entry, and the other session's generic R-1/
-- jurisdiction-628 placeholder. Both currently satisfy letter I's "zone_code
-- IS NOT NULL" check (v_zoning_gold_standard_card's zc CTE is DISTINCT
-- parcel_id, so the duplicate is harmless to I's metric either way) -- but
-- leaving the factually-wrong placeholder row in place is a real data defect
-- that would mislead any future zoning lookup, comp analysis, or G-letter
-- FAR/density/parking calculation keyed off jurisdiction 628 instead of the
-- parcel's real municipality.
--
-- This migration removes ONLY the 7 placeholder rows that are now duplicated
-- by a real, cited replacement from this session -- not the other 6 rows from
-- that same batch (514116020110 was ALSO one of these 7, correctly replaced;
-- the remaining 6 placeholder rows for parcels this session did NOT
-- independently re-verify, e.g. the 4 Coral Springs parcels, are left alone --
-- out of scope, no verified replacement zone exists for them yet).
--
-- Verified before removal: jurisdiction_id=628's R-1 district already carries
-- a real max_density_du_acre=4.00 (from an earlier firing), so removing these
-- 7 rows only reduces the density-applicable denominator by 7 (all of which
-- were already conforming) -- confirmed G-safe via
-- v_zoning_gold_standard_kpi_v3 re-check after this migration.

DELETE FROM parcel_zones
WHERE id IN (841487, 841491, 841495, 841496, 841497, 841498, 841499)
  AND jurisdiction_id = 628
  AND source = 'broward_county_unincorp_beta'
  AND parcel_id IN (
    '514116020110', '494206CK0280', '494126AB2090', '494212092690',
    '514119060741', '514024030181', '484203M10070'
  );
