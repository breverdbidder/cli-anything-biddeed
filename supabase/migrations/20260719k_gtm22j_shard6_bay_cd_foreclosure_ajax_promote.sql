-- GTM-22j shard-6 (hillsborough/flagler/bay, dispatch 1f302343): bay letters C/D
-- 9 of 127 bay rows had NULL parity_status/parity_source, all on the FORECLOSURE
-- track for 4 auction dates (2026-07-23, 07-30, 07-31, 08-03) that appeared in the
-- calendar after the last foreclosure AJAX harvest pass. The parallel tax_deed
-- track and all earlier foreclosure dates were already fully matched -- this is a
-- harvest-lag gap, not a matching-key bug or a PropertyOnion-exclusion artifact
-- (zero propertyonion rows in bay).
--
-- Verified 2026-07-19 by two independent agents: both re-ran the real
-- scripts/shard2_run2450_ajax_realforeclose_harvest.py logic live against
-- bay.realforeclose.com's AJAX endpoint (one imported the existing script
-- in-process, the other independently reimplemented the preview-fetch +
-- cookie-jar + paginated AJAX + retHTML decode flow from scratch) and both
-- got byte-identical case numbers across all 4 dates. This is a promotion of
-- already-verified real source data, not an invented value.
--
-- Idempotent: WHERE parity_status IS NULL guard, safe to re-run.

UPDATE public.multi_county_auctions
SET
  parity_status = 'matched_clean',
  parity_source = CASE case_number
    WHEN '20001459CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-23'
    WHEN '25000472CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-30'
    WHEN '25001147CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-30'
    WHEN '25001176CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-30'
    WHEN '25001344CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-30'
    WHEN '26000161CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-30'
    WHEN '25000291CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-31'
    WHEN '25001270CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-07-31'
    WHEN '25001266CA' THEN 'tier1:shard6_1f302343_ajax_harvest:foreclosure:2026-08-03'
  END
WHERE lower(county) = 'bay'
  AND case_number IN (
    '20001459CA','25000472CA','25001147CA','25001176CA','25001344CA',
    '26000161CA','25000291CA','25001270CA','25001266CA'
  )
  AND parity_status IS NULL;
