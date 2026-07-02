-- SHARD-8: clay honesty-fix (PropertyOnion-derived matches mislabeled as tier1) +
--          holmes real independent-litmus C/D matches (holmesclerk.com)
-- dispatch_id: 6fa422cf-62b8-46c6-bdeb-99303f162f13
-- Session: architect-20260702T160000 (gold standard shard-8: clay, holmes, okaloosa, taylor, gadsden)
--
-- CLAY ROOT CAUSE (VERIFIED live 2026-07-02 via REST queries against
-- multi_county_auctions): all 21 'matched_divergent' rows and 12 of clay's 29
-- 'matched_clean' rows carry parity_po_id / po_market_value / po_sold_amount
-- (PropertyOnion litmus-comparison columns) yet their parity_source was
-- labeled 'tier1_clerk_supp_shard5_run651' -- i.e. PropertyOnion-derived
-- matches dressed up as an independent tier1 clerk verification. This is the
-- same false-tier1-label pattern the fleet-wide C/D fix (commit 652678dc,
-- migration 20260702_shard1_pencil_dod_cd_tier1_filter.sql) was built to
-- catch, just not yet applied to clay's own data. HARD GUARDRAIL #1
-- ("PropertyOnion = litmus ONLY") is not violated at the base-row level (no
-- data_source='propertyonion' rows exist for clay -- confirmed, distribution
-- is realforeclose/calendar_sweep_mca_v3/null only) but the parity_source
-- LABEL falsely claimed independent tier1 provenance for a PropertyOnion
-- comparison. The remaining 17 of 29 'matched_clean' rows carry NO
-- parity_po_id and are genuine independent tax-deed clerk matches -- left
-- untouched.
--
-- FIX: relabel the 33 PropertyOnion-derived rows' parity_source to an honest,
-- non-'tier1%'-prefixed value so they correctly stop counting toward C/D
-- (PropertyOnion litmus comparisons were never meant to satisfy the
-- independent-tier1 requirement). No parity_status changed -- matched_clean/
-- matched_divergent still accurately describes the PropertyOnion comparison
-- result itself, which remains a legitimate historical litmus record.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('clay'):
--   BEFORE: C matched_clean=29 (26.9%) FAIL | D matched_any=50 (46.3%) FAIL
--   AFTER:  C matched_clean=17 (15.7%) FAIL | D matched_any=17 (15.7%) FAIL
-- Both remain FAIL either way (threshold 95%) -- this is an honesty
-- correction, not a regression on certification status. No other letter
-- changed (A/B/E/F/G/H/I/J unaffected, confirmed identical before/after).
--
-- HOLMES: separately, a real independent litmus source was found and used
-- this session -- https://holmesclerk.com/courts/foreclosures-tax-deeds/tax-deeds/
-- (Holmes County Clerk of Court's own live tax-deed sale listing; Holmes has
-- no RealTaxDeed/RealForeclose presence, confirmed via 403 on
-- holmes.realtaxdeed.com). 8 of Holmes's 10 unmatched 'TD#YYYY-NNN' rows were
-- verified verbatim on that page (matching parcel ID, opening bid, sale
-- date) and are written below as genuine tier1_clerk matches. The remaining
-- 2 TD# numbers (TD#2023-496, TD#2020-589) are NOT on the current listing
-- and are left unmatched (mca_only) -- not claimed as fake, just not
-- confirmable against the current live page. 3 'HOLMES-LEGACY-<uuid>' rows
-- are synthetic placeholder case numbers with no case-number-level public
-- source to check against (Holmes's public foreclosure listing does not
-- expose case numbers) -- structurally unmatchable, left as-is.
--
-- VERIFIED live before/after via pencil_dod_evaluate_county('holmes'):
--   BEFORE: C matched_clean=0 (0.0%) FAIL  | D matched_any=0 (0.0%) FAIL
--   AFTER:  C matched_clean=8 (50.0%) FAIL | D matched_any=8 (50.0%) FAIL
-- Real, verified improvement; still below the 95% threshold (structural
-- ceiling given 3 legacy + remaining unmatchable rows in the 16-row total).
--
-- Applied live 2026-07-02 via the PostgREST PATCH endpoint (before this file
-- was committed) -- this migration documents and reproduces those changes.

-- Clay: relabel PropertyOnion-derived matched_divergent rows (21, 100% po-linked)
UPDATE multi_county_auctions
SET parity_source = 'propertyonion_litmus_source_not_tier1_shard8_20260702'
WHERE lower(county) = 'clay'
  AND parity_status = 'matched_divergent';

-- Clay: relabel the 12 PropertyOnion-linked matched_clean rows (leaves the
-- genuine 17 independent tax-deed clerk matches with their original label)
UPDATE multi_county_auctions
SET parity_source = 'propertyonion_litmus_source_not_tier1_shard8_20260702'
WHERE lower(county) = 'clay'
  AND parity_status = 'matched_clean'
  AND parity_po_id IS NOT NULL;

-- Holmes: write verified independent tier1 matches for the 8 confirmed TD# cases
UPDATE multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_clerk_holmes_shard8_20260702',
    parity_checked_at = '2026-07-02T16:30:00Z'
WHERE lower(county) = 'holmes'
  AND case_number IN (
    'TD#2023-225', 'TD#2023-185', 'TD#2023-330', 'TD#2023-509',
    'TD#2023-584', 'TD#2020-349', 'TD#2023-753', 'TD#2024-185'
  );
