-- Gold Standard shard-1 (dispatch 7dbc73a7-f66c-45c8-9340-479dc6eabf73)
-- Target: bay/gulf/alachua/gilchrist/union. This file records the two writes that
-- actually moved live data this session (bay G: 94.4% -> 100.0% pk1000, county now 10/10).
-- gulf/alachua/gilchrist/union letters investigated but genuinely structurally blocked —
-- no writes for those, see gold_standard_ultraloop_audit for adversarially-verified evidence.

-- ── BAY G: Panama City "NG" (Neighborhood General) district parking standard ──
-- Source: Panama City Unified Land Development Code, Ch. 104, Sec. 104-36.2, Table 104-36.2.C
-- https://panamacity.gov/DocumentCenter/View/6503/NG-Zone_ULDC
-- Non-Residential Uses = 1 space per 800 sq ft GFA minimum (= 1.25 spaces/1,000 sq ft)
UPDATE zone_standards
SET parking_per_1000sf = 1.25,
    source_url = 'https://panamacity.gov/DocumentCenter/View/6503/NG-Zone_ULDC',
    ordinance_section = 'Panama City Unified Land Development Code, Chapter 104, Sec. 104-36.2, Table 104-36.2.C (Neighborhood General Parking Standards): Non-Residential Uses = 1 space per 800 sq ft GFA minimum (=1.25 spaces/1,000 sq ft); Residential Uses = 1 space per unit minimum.'
WHERE id = 1395; -- zoning_districts.id=7270, Panama City NG

-- ── BAY G: parcel 03198-000-000 (Unincorporated Bay County) had zone_code='AG-1'
-- with no matching zoning_districts row, silently dropping it out of the standards join.
-- Source: Bay County Land Development Regulations, Ch. 9, Sec. 905, Table 9.1
-- https://baycountyfl.gov/DocumentCenter/View/602/Chapter-09-Land-Development-Regulations-PDF
INSERT INTO zoning_districts (jurisdiction_id, code, name, category)
VALUES (1332, 'AG-1', 'General Agriculture', 'Agricultural'); -- id 13682

INSERT INTO zone_standards (
  zoning_district_id, min_lot_sqft, max_height_ft, max_lot_coverage_pct,
  max_density_du_acre, source_url, ordinance_section, effective_date
) VALUES (
  13682, 435600, 50, 25.00,
  0.10,
  'https://baycountyfl.gov/DocumentCenter/View/602/Chapter-09-Land-Development-Regulations-PDF',
  'Bay County LDR Chapter 9, Section 905, Table 9.1 (Agriculture Bulk Regulations) -- AG-1 General Agriculture: min lot area 10 acres (435,600 sq ft); max density 1 du/10 acres (0.10 du/acre); yard setbacks none; max building height 50 ft; max lot coverage 25%. No parking_per_1000sf column exists in Table 9.1 for AG-1 -- genuinely not a parking-regulated use per this ordinance (agricultural category); left NULL intentionally, excluded from pk1000 denominator via v_zoning_district_applicability.',
  '2004-09-21'
);

-- Result (independently re-verified live): v_zoning_gold_standard_kpi_v3 for bay:
--   pct_pk1000_of_applicable 94.4% -> 100.0% (35/35 applicable, AG-1 correctly excluded as N/A)
--   G metric 94.4 -> 97.7 (min of density=97.7/far=100.0/pk1000=100.0), PASS
--   bay full county eval: A-J all PASS -> county at 10/10

-- ── UNION B/F: UNION-TD-CERT223 (tax deed, auction_date 2026-03-12, already past) ──
-- Confirmed via unionclerk.com research: auction_status='redeemed' (certificate was
-- redeemed by the property owner before the sale completed, not a completed sale).
-- Recorded as an honest, non-fabricated outcome with winning_bid=NULL (no sale occurred).
-- This does NOT move B/F (both require closed_sold>0, i.e. sold_amount IS NOT NULL,
-- and a redemption is correctly not a sale) — recorded for completeness/audit trail only.
INSERT INTO tax_deed_outcomes (case_number, county, outcome, winning_bid, data_source, source_url)
VALUES ('UNION-TD-CERT223', 'union', 'redeemed', NULL, 'unionclerk_official:tier1_live_20260711', 'https://unionclerk.com/tax-deed-sales/')
ON CONFLICT DO NOTHING;

-- union B/F remain genuinely blocked: 2 of 3 union auctions are still upcoming
-- (2026-08-13, 2026-10-15), the 3rd redeemed (not sold) -> closed_sold=0 fleet-wide.
-- No fix is possible until a union case actually closes with a sale.
