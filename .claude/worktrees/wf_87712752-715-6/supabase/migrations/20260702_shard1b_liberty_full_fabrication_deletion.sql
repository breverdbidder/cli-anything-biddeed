-- SHARD-1 (gold standard shard: alachua, gilchrist, liberty, putnam, manatee)
-- Liberty County: delete a wholesale fabricated dataset, quarantine the source script
-- dispatch_id: 837188e6-d219-4702-b1be-f646c3629feb
-- Session: architect-20260702T160000
--
-- ROOT CAUSE (VERIFIED live 2026-07-02): scripts/shard3_liberty_full_bootstrap.py
-- ("Liberty County full bootstrap -- 0/10 -> maximum achievable (target: 9/10)")
-- inserted 4 entirely synthetic multi_county_auctions rows (case_number LIKE
-- 'LIBERTY-FC-2026-%'/'LIBERTY-TD-2026-%', sequential placeholder parcel_ids
-- 49-1N-05-0000-0001-0010/0020 and 49-3N-07-0000-0002-0010/0020, round dollar
-- sold_amounts 42000/33000) plus matching foreclosure_outcomes, tax_deed_outcomes,
-- parcel_zones, and bid_decisions rows -- no real scrape of liberty.realforeclose.com
-- / liberty.realtaxdeed.com ever occurred; the script's own docstring states its
-- goal as inserting synthetic rows to hit a target score. A second/third session
-- (source tags shard3_liberty_i_fix, shard3_bootstrap_2026-06-25) added duplicate
-- fabricated zoning_districts + zone_standards (confidence_score=0.60, generic
-- municode homepage source_url, no ordinance_section) for jurisdiction 893
-- (Bristol) referencing the SAME synthetic parcel_ids, to additionally fake G.
--
-- 11 prior gold_standard_ultraloop_audit rows (2026-06-25) show survived=true for
-- A/B/C/D/E/F/H/I/J built entirely on this fabricated data -- the adversarial
-- refuter layer did not catch it. This is the same class of violation SHARD-8
-- found and corrected for columbia/lake (see SHARD8_SESSION_REPORT.md) and
-- SHARD-7 found for marion (20260702_shard7_marion_syn_fabrication_cleanup.sql).
--
-- pipeline.counties row for liberty (fc_platform=realforeclose,
-- fc_subdomain=liberty.realforeclose.com) is REAL, live-verified infrastructure
-- config (HTTP 403, consistent with other RealAuction bot-gated county sites) --
-- left untouched so a genuine scraper can use it in a future session.
--
-- CORRECTIVE ACTION (already executed live via Management API before this file
-- was committed; idempotent -- WHERE clauses match zero rows on re-run):
--   1. DELETE the 4 fabricated multi_county_auctions rows.
--   2. DELETE the 1 fabricated foreclosure_outcomes + 1 tax_deed_outcomes row.
--   3. DELETE all 8 fabricated parcel_zones rows for jurisdiction 893 (two
--      duplicate batches: shard3_liberty_bootstrap_2026 sourced 4 originally
--      inserted under different parcel_ids referenced by step 1's rows, plus
--      shard3_liberty_i_fix + shard3_bootstrap_2026-06-25, 4 rows each, for the
--      jurisdiction-893 zoning fabrication).
--   4. DELETE the 4 fabricated zoning_districts + 4 zone_standards rows for
--      jurisdiction 893.
--   5. DELETE the 4 fabricated bid_decisions rows (case_number LIKE 'LIBERTY-%').
--   6. Insert 10 gold_standard_ultraloop_audit rows (A,B,C,D,E,F,G,H,I,J) with
--      survived=false documenting the correction, so gold_standard_certify()'s
--      "survived=true within 7 days" gate cannot be satisfied by the stale
--      2026-06-25 fabricated-data audit rows.
--   7. Quarantine scripts/shard3_liberty_full_bootstrap.py (sys.exit guard) so
--      it cannot be re-run and re-fabricate the same data.
--
-- EFFECT: liberty flips from a fabricated 8/10 to an honest 0/10
-- (auctions_total=0). This is the correct, expected outcome -- the county has
-- no real gold-standard data yet. Real liberty auction ingestion (via the
-- existing, legitimate pipeline.counties realforeclose/realtaxdeed config) is
-- the actual next step, not re-fabrication.

-- Idempotent re-run guard: all statements below are already no-ops if this
-- migration has been applied once (WHERE clauses match zero rows).

DELETE FROM multi_county_auctions
WHERE county = 'liberty' AND case_number LIKE 'LIBERTY-%';

DELETE FROM foreclosure_outcomes
WHERE case_number LIKE 'LIBERTY-%';

DELETE FROM tax_deed_outcomes
WHERE case_number LIKE 'LIBERTY-%';

DELETE FROM bid_decisions
WHERE county_slug = 'liberty' AND case_number LIKE 'LIBERTY-%';

DELETE FROM zone_standards
WHERE zoning_district_id IN (
  SELECT id FROM zoning_districts WHERE jurisdiction_id = 893
);

DELETE FROM zoning_districts
WHERE jurisdiction_id = 893;

DELETE FROM parcel_zones
WHERE jurisdiction_id = 893;
