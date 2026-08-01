-- One-time backfill of auction_url for upcoming multi_county_auctions rows,
-- run live 2026-08-01 as part of the auction_url population brief. Root
-- finding: auction_url was NULL for 1917/1920 upcoming rows (100% of the
-- 192 live bad-parity rows re-derived this session, brief's snapshot said
-- 231). No AID was ever persisted on multi_county_auctions itself, but
-- public.realforeclose_aids (6582 rows, 42 counties, populated by earlier
-- harvest sessions e.g. scripts/realforeclose_aids_paginated_harvest.py)
-- already has verified (county_slug, case_number_norm) -> aid mappings.
--
-- Live-verified 2026-08-01: constructed URL for clay/AID=1510337 returned
-- HTTP 200 against clay.realforeclose.com.
--
-- Deviation from the issue brief: the brief's RealTaxDeed pattern included
-- "&savefore={county_id}". Every prior live-verified script in this repo
-- (backfill_opening_bid_312_jul30.py, realforeclose_aids_paginated_harvest.py,
-- and a dozen shard scripts) uses the bare
-- "/index.cfm?zaction=auction&zmethod=details&AID={aid}" pattern for BOTH
-- platforms with no savefore param, and that pattern is what resolved 200
-- live. Followed the evidence over the brief per CC_META_PROMPT §2.3.
--
-- Idempotent: WHERE auction_url IS NULL guards against re-touching rows a
-- later scrape (see .github/scripts/calendar_sweep_mca.py upsert_to_mca)
-- already populated; re-running this after that would just match 0 rows.
--
-- Result when applied live: 578 rows updated (verified via
-- COUNT(*) WHERE auction_url IS NOT NULL AND auction_status='upcoming'
-- AND auction_date >= CURRENT_DATE: 3 -> 581).
WITH ranked AS (
  SELECT county_slug, case_number_norm, aid,
         ROW_NUMBER() OVER (PARTITION BY county_slug, case_number_norm ORDER BY last_seen_at DESC) rn
  FROM public.realforeclose_aids
),
matched AS (
  SELECT mca.id AS mca_id,
    'https://' || rs.subdomain || '.' ||
      CASE mca.source_platform WHEN 'realforeclose' THEN 'realforeclose.com' WHEN 'realtaxdeed' THEN 'realtaxdeed.com' END
      || '/index.cfm?zaction=auction&zmethod=details&AID=' || r.aid AS new_url
  FROM public.multi_county_auctions mca
  JOIN ranked r ON r.rn = 1 AND r.county_slug = mca.county AND r.case_number_norm = public.normalize_case_number(mca.case_number)
  JOIN public.realauction_subdomains rs ON rs.county_slug = mca.county AND rs.platform = mca.source_platform
  WHERE mca.auction_date >= CURRENT_DATE
    AND mca.auction_status = 'upcoming'
    AND mca.auction_url IS NULL
    AND mca.source_platform IN ('realforeclose','realtaxdeed')
)
UPDATE public.multi_county_auctions mca
SET auction_url = matched.new_url,
    updated_at = NOW()
FROM matched
WHERE mca.id = matched.mca_id;
