-- SHARD-2 Migration: Fix miami_dade bid_decisions county_slug = NULL
-- Session: architect-20260619T160001
-- Root cause: bid_decisions generator ran previously but didn't set county_slug
-- Impact: J evaluator counts by county_slug — NULL rows don't appear in J metric

UPDATE bid_decisions bd
SET county_slug = 'miami_dade'
WHERE bd.county_slug IS NULL
  AND EXISTS (
    SELECT 1 FROM multi_county_auctions mca
    WHERE mca.case_number = bd.case_number
      AND mca.county = 'miami_dade'
  );

-- Verify
SELECT county_slug, COUNT(*) AS decisions,
  COUNT(CASE WHEN ml_score IS NOT NULL AND factors ? 'distress_location'
             AND factors ? 'cma_resale' AND factors ? 'cma_distressed'
             AND factors ? 'distress_owner' AND factors ? 'distress_property'
             THEN 1 END) AS j_compliant
FROM bid_decisions
WHERE county_slug = 'miami_dade'
GROUP BY county_slug;
