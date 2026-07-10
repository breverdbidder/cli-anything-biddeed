-- SHARD-1 (gold standard shard: alachua, gilchrist, liberty, putnam, manatee)
-- Fleet-wide (within shard): null out placeholder/fallback parcel_id values
-- that were falsely inflating criterion E (and downstream I) for alachua,
-- gilchrist, putnam, manatee.
-- dispatch_id: 837188e6-d219-4702-b1be-f646c3629feb
-- Session: architect-20260702T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02): 18 multi_county_auctions rows across
-- these 4 counties had parcel_id set to a non-parcel placeholder string instead
-- of a real parcel ID or NULL:
--   - 'SYN-<COUNTY>-<hex>'  (synthetic-linkage fallback; alachua=5) -- same
--     class of issue SHARD-7 found fleet-wide (118 SYN- rows across 10
--     counties, see 20260702_shard7_marion_syn_fabrication_cleanup.sql, which
--     explicitly flagged alachua's 5 SYN- rows as out-of-scope for shard-7 and
--     left them for the owning shard). Verified live: none of these 7 alachua
--     case numbers are duplicated (each case_number appears exactly once) --
--     these are standalone real auctions (real case numbers, real
--     data_source=realforeclose/realauction_http_v3/calendar_sweep_mca_v3)
--     with a fabricated parcel linkage, not duplicate rows to delete.
--   - 'PUT-<case>'  (putnam-specific synthetic-linkage fallback; putnam=5)
--   - literal 'MULTIPLE PARCEL'/'MULTIPLE PARCELS' (a real scraped calendar
--     value describing a case that legitimately spans more than one parcel --
--     correctly NOT a single linkable parcel_id; alachua=1, putnam=2, manatee=1)
--   - literal 'Property Appraiser' (alachua=1, gilchrist=1) -- a scraper bug
--     that captured a hyperlink's link-text instead of the parcel ID value
--     the link pointed to
--   - literal 'ALCOHOLIC BEVERAGE LICENSE' (putnam=1) -- a non-parcel case
--     type description, not a parcel ID
--
-- Because criterion E is `parcel_id IS NOT NULL`, all 18 rows were counted as
-- "linked" despite carrying no real parcel identifier -- inflating E (and I,
-- which requires E's parcel_id IS NOT NULL as one of its five conditions) for
-- all four counties. This flips E from PASS to FAIL for alachua (100%->82.5%)
-- and gilchrist (100%->80.0%), and drops putnam (97.0%->93.6%) and manatee
-- (95.7%->94.3%) further below the already-failing 95% threshold.
--
-- CORRECTIVE ACTION (already executed live via Management API before this file
-- was committed; idempotent -- WHERE clause matches zero rows on re-run since
-- parcel_id is already NULL): set parcel_id = NULL for the 18 affected rows.
-- The underlying auction rows are NOT deleted -- only the placeholder
-- parcel_id field is corrected, honestly exposing that these auctions are not
-- yet parcel-linked.

UPDATE multi_county_auctions
SET parcel_id = NULL, updated_at = now()
WHERE lower(county) IN ('alachua','gilchrist','putnam','manatee')
  AND COALESCE(data_source,'') <> 'propertyonion'
  AND (
    parcel_id ILIKE 'SYN-%' OR parcel_id ILIKE 'PUT-%' OR parcel_id ILIKE '%MULTIPLE PARCEL%'
    OR parcel_id = 'Property Appraiser' OR parcel_id ILIKE '%LICENSE%'
  );
