-- Gold Standard shard-8 (marion, dispatch 0ddd603c-68ec-45c0-86b8-3b643c98faf3): letter G
-- density=100.0, far=100.0 already pass. pk1000=0.0 was the sole binding
-- constraint: exactly 1 of 10 marion zoning_districts is pk1000_applicable
-- (v_zoning_district_applicability), covering 6 parcels -- district id 11738,
-- code "B2" / "Community Business (B-2)", jurisdiction=Unincorporated Marion
-- County. parking_per_1000sf was NULL for that single district; every other
-- district is pk1000_applicable=false (residential/agricultural/admin
-- chapters) and correctly excluded from the denominator.
--
-- Source (live-fetched via Municode CodesContent API 2026-07-20, read
-- directly off the ordinance text, not inferred):
--   Marion County LDC Article 6, Technical Standards and Requirements,
--   Division 11 Traffic Management, Sec. 6.11.8 "Parking requirements",
--   Table 6.11-5 "Minimum Off-Street Parking Requirements for Nonresidential
--   Land Use".
--   https://library.municode.com/fl/marion_county/codes/land_development_code?nodeId=LADECO_ART6TESTRE_DIV11TRMA_S6.11.8PARE
--
-- DISCLOSED JUDGMENT CALL: Table 6.11-5 is keyed by LAND USE, not by zoning
-- district, so there is no single "B-2" row to copy verbatim. B-2 Community
-- Business (LDC Sec. 4.2.18 / Table 4.2-6) is the county's community-scale
-- commercial-center classification -- its permitted-use mix (grocery, drug
-- store, bank, restaurant, general retail, personal services) matches the
-- table's "Neighborhood or convenience center under 100,000 sq. ft. GLA"
-- row, not the narrower single-tenant "Retail store" row (1/300sf) or the
-- large-format "Shopping center" row (3.5/1,000sf GLA). We map to the
-- neighborhood/convenience-center rate: 4 spaces per 1,000 sq. ft. GLA.
-- This also matches the value already recorded for every other FL county's
-- B-2/C-2 "General Commercial"-class district in this database (Alachua,
-- Brevard, Broward, Collier, DeSoto, Duval, Escambia, Franklin, ...), so it
-- is consistent with this project's established category-mapping precedent,
-- not a novel guess.
--
-- Idempotent: parking_per_1000sf IS NULL guard, safe to re-run.

BEGIN;

UPDATE public.zone_standards
SET parking_per_1000sf = 4.00,
    source_url = 'https://library.municode.com/fl/marion_county/codes/land_development_code?nodeId=LADECO_ART6TESTRE_DIV11TRMA_S6.11.8PARE',
    ordinance_section = COALESCE(ordinance_section || ' | ', '') || 'Parking: Marion County LDC Sec. 6.11.8, Table 6.11-5 "Minimum Off-Street Parking Requirements for Nonresidential Land Use", row "Neighborhood or convenience center under 100,000 sq. ft. GLA" = 4 spaces per 1,000 sq. ft. GLA. Mapped to B-2 Community Business (LDC Sec. 4.2.18) as the closest matching land-use category for this district''s permitted-use mix; Table 6.11-5 is keyed by use type, not zoning district, so no exact B-2 row exists.'
WHERE zoning_district_id = 11738
  AND parking_per_1000sf IS NULL;

COMMIT;
