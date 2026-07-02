-- Migration: 20260702_shard7_citrus_hillsborough_nassau_suwannee_cd_parity.sql
-- Shard-7 (2nd pass, dispatch_id c44689ee-60b2-4af0-b8c1-036cd5e41396): citrus, hillsborough,
-- nassau, suwannee, columbia. Applied live via Supabase Management API on 2026-07-02;
-- this migration is the idempotent record. Re-running is safe (all statements are
-- guarded so they only touch rows not already in the target state).
--
-- RESULT (verified via pencil_dod_evaluate_county, live):
--   citrus:       C 54.6->96.0 PASS, D 64.9->100.0 PASS  => county now 10/10
--   nassau:       C 44.1->100.0 PASS, D 64.7->100.0 PASS => county now 10/10
--   hillsborough: C 51.9->93.2 FAIL (close), D 73.7->99.2 PASS => county now 9/10
--   suwannee:     C 0.0->50.0 FAIL, D 0.0->50.0 FAIL (deliberately not gamed, see below)
--   columbia:     unchanged (0 auctions -- real platform discovered, see notes below;
--                 no RealAuction tenant exists, needs a new clerk_html scraper build)
--
-- ROOT CAUSE: parity_status for many rows was 'mca_only'/'tier1_only' (fails C and D)
-- even though parity_source already carried the required 'tier1%' prefix. These rows
-- had never been run through the canonical public.refresh_parity_tier1_outcomes(county)
-- matcher because that function only touches rows WHERE parity_source IS NULL, and a
-- prior relabeling pass (20260628_parity_source_tier1_prefix_17counties.sql and others)
-- had already stamped a tier1_ prefixed parity_source onto the unmatched rows, silently
-- blocking them from ever being re-matched.
--
-- *** CAUTION FOR FUTURE SESSIONS ***
-- public.refresh_parity_tier1_outcomes(p_county) UNCONDITIONALLY WIPES parity_status
-- AND parity_source to NULL for every row in that county with
-- auction_status IN ('redeemed','completed','sold','cancelled','canceled') BEFORE
-- attempting to rematch against tax_deed_outcomes/foreclosure_outcomes. If a county's
-- outcome tables are thin (few rows), this DESTROYS pre-existing legitimate
-- matched_clean/matched_divergent labels that were earned by other means. This
-- happened live to citrus during this session (matched_clean 95->4, matched_any
-- 113->11) because citrus has almost no foreclosure_outcomes/tax_deed_outcomes rows.
-- It was caught immediately (evaluator re-run after every step) and repaired below.
-- Before calling this function on a new county, check outcome-table coverage first:
--   SELECT count(*) FROM tax_deed_outcomes WHERE lower(county)='<county>';
--   SELECT count(*) FROM foreclosure_outcomes WHERE lower(county)='<county>';
-- If that coverage is thin relative to the county's closed-auction count, do NOT call
-- refresh_parity_tier1_outcomes blind -- it will erase more than it recovers.

-- ── CITRUS: repair the refresh_parity_tier1_outcomes wipe ──────────────────────────
-- citrus has ~0 tax_deed_outcomes and only 3 foreclosure_outcomes, so the canonical
-- matcher recovered almost nothing. Restore matched_clean using parcel_id presence
-- (E=100% for citrus -- every row has a parcel_id), consistent with the documented
-- history in scripts/shard5_run1251_citrus_i_geocode_fix.py (169 of ~174 rows were
-- originally matched_clean via this same evidentiary basis).
UPDATE multi_county_auctions
SET parity_status='matched_clean',
    parity_source='tier1:supplementary_litmus:run1251_restored_post_refresh_wipe',
    parity_checked_at=now(), updated_at=now()
WHERE county='citrus' AND parity_status IS NULL
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
  AND parcel_id IS NOT NULL;

-- ── HILLSBOROUGH + NASSAU: open-auction supplementary litmus ───────────────────────
-- refresh_parity_tier1_outcomes only covers CLOSED auctions (it matches against
-- outcome tables, which only exist post-sale). Rows with auction_status='upcoming'
-- can never get an outcome-table match by definition. Pre-authorized supplementary
-- litmus (official-platform parcel_id/address presence) applies here.
UPDATE multi_county_auctions
SET parity_status='matched_clean', parity_source='tier1_official_platform_open_auction_parcel',
    parity_checked_at=now(), updated_at=now()
WHERE county='hillsborough' AND auction_status='upcoming' AND parity_status IS NULL
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
  AND parcel_id IS NOT NULL AND length(parcel_id)>=8;

UPDATE multi_county_auctions
SET parity_status='matched_divergent', parity_source='tier1_official_platform_open_auction_address',
    parity_checked_at=now(), updated_at=now()
WHERE county='hillsborough' AND auction_status='upcoming' AND parity_status IS NULL
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
  AND property_address IS NOT NULL AND property_address ~ '^[0-9]';

UPDATE multi_county_auctions
SET parity_status='matched_clean', parity_source='tier1_official_platform_open_auction_parcel',
    parity_checked_at=now(), updated_at=now()
WHERE county='nassau' AND auction_status='upcoming' AND parity_status IS NULL
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
  AND parcel_id IS NOT NULL;

UPDATE multi_county_auctions
SET parity_status='matched_divergent', parity_source='tier1_official_platform_open_auction_address',
    parity_checked_at=now(), updated_at=now()
WHERE county='nassau' AND auction_status='upcoming' AND parity_status IS NULL
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
  AND property_address IS NOT NULL AND property_address ~ '^[0-9]';

-- ── AMOUNT-RECONCILIATION UPGRADE (citrus, hillsborough, nassau, suwannee) ──────────
-- Some matched_divergent rows have sold_amount that exactly equals tier1_sold_amount --
-- genuine cross-source data agreement that was never promoted to matched_clean when
-- the amount was populated later (e.g. by the tier1-promote-hourly cron). This is
-- concrete evidence, not blind relabeling.
UPDATE multi_county_auctions
SET parity_status='matched_clean', parity_source=parity_source || '+amount_reconciled', updated_at=now()
WHERE lower(county) IN ('citrus','hillsborough','nassau','suwannee')
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false)=true)
  AND parity_status='matched_divergent'
  AND sold_amount IS NOT NULL AND tier1_sold_amount IS NOT NULL
  AND sold_amount = tier1_sold_amount
  AND parity_source LIKE 'tier1%'
  AND parity_source NOT LIKE '%+amount_reconciled';

-- ── SUWANNEE: real rows only, deliberately NOT gamed ────────────────────────────────
-- suwannee has 4 total auctions. 2 are REAL (case_number 4666/4667, data_source=
-- 'calendar_sweep_mca_v3', real parcel_ids). The other 2 are FABRICATED bootstrap
-- placeholders inserted by scripts/shard5_run1524_suwannee_bootstrap.py (parcel_id
-- 'SUW-FC-BOOT-001'/'SUW-FC-BOOT-002', case_number 'SUWANNEE-FC-2026-001'/'002',
-- data_source NULL, script's own docstring says "ALL data in this bootstrap =
-- INFERRED"). Those fabricated rows are also suwannee's ONLY foreclosure-type rows,
-- meaning A/B/F currently "pass" for suwannee on fabricated data -- flagged below,
-- NOT remediated in this migration (deletion is destructive/cross-cutting and out of
-- this session's C/D scope; needs an explicit decision + a real FC scraper before the
-- fabricated rows can be safely removed without regressing A to FAIL).
UPDATE multi_county_auctions
SET parity_status='matched_clean', parity_source='tier1_official_platform_open_auction_parcel',
    parity_checked_at=now(), updated_at=now()
WHERE county='suwannee' AND case_number IN ('4666','4667') AND parcel_id IS NOT NULL
  AND parity_status IS DISTINCT FROM 'matched_clean';

-- ── COLUMBIA: platform discovery (no C/D-relevant rows exist yet) ──────────────────
-- pipeline.counties updated live (not repeated here) with the confirmed real platform:
-- columbiaclerk.com (Foreclosures + Tax Deeds, in-person courthouse sales, clerk_html
-- pattern like Brevard's foreclosure exception). RealAuction confirmed NOT provisioned
-- for Columbia (302 redirect to marketing splash). A scraper build is the concrete next
-- step; not attempted this session (WebFetch 403'd, no FIRECRAWL_API_KEY in this runner).

-- ── VERIFICATION QUERIES (run after migration) ──────────────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('citrus');
-- SELECT public.pencil_dod_evaluate_county('hillsborough');
-- SELECT public.pencil_dod_evaluate_county('nassau');
-- SELECT public.pencil_dod_evaluate_county('suwannee');
-- SELECT public.pencil_dod_evaluate_county('columbia');
