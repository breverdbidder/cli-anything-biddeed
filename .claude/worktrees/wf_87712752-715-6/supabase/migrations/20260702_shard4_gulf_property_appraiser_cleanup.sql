-- SHARD-4: gulf 'Property Appraiser' placeholder cleanup (E/G/I integrity fix)
-- dispatch_id: ee409c09-b216-44e6-a39c-756982dac777
-- Session: architect-20260702T080000 (gold standard shard-4: gulf, okeechobee, marion)
--
-- ROOT CAUSE (found by an independent ULTRALOOP adversarial-verify refuter agent,
-- confirmed live): multi_county_auctions row for gulf case_number='232024CC000157CCAXMX'
-- carries parcel_id='Property Appraiser' -- a literal UI-scrape artifact string, not a
-- real parcel folio. A prior session (source='shard5_gulf_pa_fix', 2026-06-19) had
-- already created a scoped, per-case synthetic replacement parcel_zones row
-- ('GULF-PA-000157CCAXMX-03', jurisdiction_id=952) for exactly this case -- the same
-- convention already completed and accepted for gulf's other two 'Property Appraiser'
-- cases (232024CA000072CAAXMX -> 'GULF-PA-000072CAAXMX-01', 232019CA000060CAAXMX ->
-- 'GULF-PA-000060CAAXMX-02', both already correctly wired in multi_county_auctions).
-- This third case's multi_county_auctions.parcel_id was simply never updated to point
-- at its already-created synthetic row -- the fix was half-applied.
--
-- Left as-is, the literal 'Property Appraiser' string spuriously resolves against 3
-- duplicate fabricated parcel_zones rows (source='shard5_gulf_all') that inflate
-- gulf's E/G/I metrics without a real parcel link. This is the same broken-placeholder
-- pattern found fleet-wide (42 rows across many counties/jurisdictions, out of this
-- shard's scope to touch) -- flagged for the AI Architect / other shards, not fixed
-- here beyond gulf's own 3 rows.
--
-- FIX: complete the pre-existing, already-accepted per-case synthetic-ID convention
-- for this one case, then remove the now-orphaned duplicate fabricated rows.

UPDATE multi_county_auctions
SET parcel_id = 'GULF-PA-000157CCAXMX-03', updated_at = NOW()
WHERE county = 'gulf'
  AND case_number = '232024CC000157CCAXMX'
  AND parcel_id = 'Property Appraiser';

DELETE FROM parcel_zones
WHERE parcel_id = 'Property Appraiser'
  AND jurisdiction_id = 952;
