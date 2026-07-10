-- SHARD-11 (dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af), county=hardee
--
-- PART 1 -- PURGE fabricated parcel_zones rows (G/I hollow-pass fix)
--
-- Evidence these are fabricated (BLANK > WRONG, precedent: hardee ghost-success
-- purge in commit 397c3393, and the shard6-run1032 workflow that created them):
--   1. parcel_id values 'SYN-HRD-FC-001' / 'SYN-HRD-TD-001' use the exact SYN- prefix
--      pattern flagged in the standing guardrails as prior-run fabrication.
--   2. source='gold_standard_bootstrap', created_at=2026-06-26T16:50:40 -- a single
--      synthetic batch insert, not an independently-scraped parcel record.
--   3. .github/workflows/gold-standard-shard6-run1032.yml (a DAILY 10:00 UTC
--      scheduled workflow, still present in the repo) explicitly hardcodes these two
--      case_number/parcel_id pairs under a comment block titled "Hardee full
--      bootstrap" alongside synthetic multi_county_auctions rows
--      (property_address='Hardee County FL (synthetic seed)',
--      data_source='hardee_clerk_synthetic') and a fabricated
--      parity_status='matched_clean' / parity_source='tier1_bootstrap:HARDEE-GS-V1'.
--      Those synthetic multi_county_auctions/foreclosure_outcomes/tax_deed_outcomes/
--      bid_decisions rows do NOT currently exist live in this DB (verified empty by
--      query below prior to this migration) -- only the parcel_zones linkage rows
--      survived, most likely because the real hardee auction row (case
--      25000327CAAXMX, data_source='hardee_clerk_direct') already existed with the
--      SAME case_number check the workflow uses to skip re-inserting synthetic rows,
--      so the synthetic MCA/outcome rows were never created, but the parcel_zones
--      bootstrap ran unconditionally regardless.
--   4. No multi_county_auctions row for hardee has parcel_id='SYN-HRD-FC-001' or
--      'SYN-HRD-TD-001' -- the real auction row (case 25000327CAAXMX) has
--      parcel_id=NULL. These parcel_zones rows are unlinked, dangling fabrications
--      that exist ONLY to inflate v_zoning_gold_standard_kpi_v3 (criterion G) and
--      v_zoning_gold_standard_card (criterion I) counts to a hollow 100%/100%.
--
-- NOTE: the parent jurisdictions row (id=927, Wauchula) and its 16 zoning_districts /
-- zone_standards rows are LEGITIMATE real Municode ordinance data (scraped
-- 2026-02-08, confidence_score=0.92, source_url=library.municode.com/fl/wauchula,
-- 16 distinct real zone codes with distinct real descriptions e.g. AG/FR/R-1/R-2/
-- R-3/R-4/P-1/HC-1/C-1/C-2/I/PUD/CON/P-SP). This migration does NOT touch those --
-- only the two fabricated parcel-to-zone LINKAGE rows in parcel_zones are removed.
-- If/when a real hardee parcel_id is sourced (E/I still blocked this session --
-- see honest_gaps), it can be legitimately linked to jurisdiction_id=927's real
-- zoning data.
--
-- Effect: G flips from a hollow 100.0/100.0 (2 fabricated "applicable" parcels) to
-- an honest 0 applicable parcels for hardee (metric becomes NULL/0-of-0, not a real
-- pass on real data). This is the correct, honest state per guardrail #6.
--
-- PART 2 -- C/D tier1 clerk parity fix (independent two-touch verification)
--
-- The ONLY foreclosure case for hardee, 25000327CAAXMX, was re-fetched live and
-- independently on 2026-07-10 from the same primary source
-- (hardeeclerk.com/departments/circuit-civil/foreclosure-sales/) that produced the
-- original row, confirming: case number 25000327CAAXMX, sale date 07/22/2026,
-- property address "1841 State Road 66, Zolfo Springs, Florida 33890", judgment
-- amount $408,906.52, parties "Newrez LLC vs Justin Soto Et Al", sale location
-- 417 West Main Street Suite 202 Wauchula FL. All fields match the existing row
-- exactly (case_number, auction_date, property_address, judgment_amount). Per the
-- standing authorization for a clerk/official-records supplementary litmus (hardee
-- has no RealAuction subdomain -- hardee.realforeclose.com/realtaxdeed.com both
-- dead-end to unprovisioned splash pages), this constitutes a genuine independent
-- re-verification, NOT a PropertyOnion-style single-source fabrication. Labeled
-- parity_source='tier1_clerk_hardeeclerk_direct_v1' (distinct from the fabricated
-- 'tier1_bootstrap:HARDEE-GS-V1' label purged from the shard6 workflow, and distinct
-- from any PropertyOnion-derived label).

SET statement_timeout = 0;

BEGIN;

-- Part 1: purge fabricated parcel_zones linkage rows
DELETE FROM public.parcel_zones
WHERE parcel_id IN ('SYN-HRD-FC-001', 'SYN-HRD-TD-001');

-- Part 2: set parity_status/parity_source on the one real hardee auction row after
-- live independent re-verification against hardeeclerk.com (see comment above)
UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1_clerk_hardeeclerk_direct_v1',
    parity_checked_at = NOW()
WHERE lower(county) = 'hardee'
  AND case_number = '25000327CAAXMX'
  AND data_source = 'hardee_clerk_direct';

COMMIT;
