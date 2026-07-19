-- GTM-22j shard-6 (dispatch 1f302343, 2nd firing): hillsborough G regression fix
-- The 20260719m I-fix (parcel_zones backfill) introduced 238 new parcels under 20 zone
-- codes hillsborough had never seen zoning_districts rows for. v_zoning_gold_standard_kpi_v3
-- treats a missing zoning_districts row as "applicable, no value" by default (worst case),
-- which crashed G from PASS (density=98.7) to FAIL (density=79.3 far=0.0 pk1000=4.9) --
-- the exact "I-fix causes G regression" failure mode already seen once this campaign
-- (commit 838e9a53, santa_rosa+putnam). Root cause confirmed live: far/pk1000-applicable
-- parcel count went from 0 (NULL denominator, ignored by Postgres LEAST()) to 41 (real
-- denominator, no longer ignorable), almost all from missing-district codes.
--
-- Part A: create the missing zoning_districts rows with correct category classification,
-- so far_applicable/pk1000_applicable/density_applicable compute correctly via the same
-- category-based default logic already working for hillsborough's pre-existing districts
-- (ASC-1/R-1/RSC-6/AS-1/PD/CI). Residential and Agricultural codes get far_regulated=false,
-- pk1000_regulated=false explicitly (matches existing precedent for RSC-6/AS-1/PD -- these
-- categories genuinely don't carry a fixed FAR/parking standard in the LDC). PD-MU and
-- IPD-1/IPD-2 ("Planned Development" variants) get density_regulated=false too, same
-- reasoning already applied to the pre-existing PD/PD-A rows: Planned Development sets
-- density/FAR per individual development order, not a single ordinance-wide number.
-- CG/CN (Commercial General/Neighborhood) are deliberately left with NO explicit override --
-- these ARE genuinely FAR/parking-regulated commercial districts and this session could not
-- source their real Hillsborough LDC 6.01.01 table values live (Municode WAF 403, the
-- county's own PDF link stale/redirected, elaws.us mirror 503 throughout this session) --
-- left as a real, quantified residual (4 parcels total: CG+CN here, plus pre-existing
-- Tampa CN and Plant City C-1), not fabricated. BLANK > WRONG.
--
-- Part B: backfill max_density_du_acre using Hillsborough's own LDC naming convention --
-- "Residential [Single-Family|Multi-family|Duplex] Conventional-N" districts (RSC-N,
-- RMC-N, RDC-N) are named for their max density of N dwelling units/acre; "Agricultural
-- Single-family-N" (AS-N) districts are named for their minimum lot size of N acres, i.e.
-- max density = 1/N du/acre. RSC-6=6du/acre and AS-1=1du/acre (1-acre minimum lot) were each
-- independently confirmed live against the LDC via web search before this migration was
-- written (see session tool log); the other RSC-x/RMC-x/RDC-x codes and AS-0.4 apply the
-- identical, systematic LDC naming convention and are marked confidence_score accordingly
-- (0.95 for the two directly-confirmed codes, 0.70-0.85 for same-family pattern-inferred
-- codes) rather than claimed as independently verified for each one.

INSERT INTO public.zoning_districts (jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated, ordinance_section)
SELECT v.jurisdiction_id, v.code, v.name, v.category, v.far_regulated, v.pk1000_regulated, v.density_regulated, v.ordinance_section
FROM (VALUES
  (631, 'RSC-9', 'Residential Single-Family Conventional-9', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RSC-4', 'Residential Single-Family Conventional-4', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RSC-2', 'Residential Single-Family Conventional-2', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RSC-3', 'Residential Single-Family Conventional-3', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'AS-0.4', 'Agricultural Single-Family-0.4', 'Agricultural', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'AR', 'Agricultural Rural', 'Agricultural', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RMC-16', 'Residential Multi-family Conventional-16', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RMC-12', 'Residential Multi-family Conventional-12', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RMC-20', 'Residential Multi-family Conventional-20', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RDC-6', 'Residential Duplex Conventional-6', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'RDC-12', 'Residential Duplex Conventional-12', 'Residential', false, false, NULL::boolean, 'LDC 6.01.01'),
  (631, 'PD-MU', 'Planned Development Mixed Use', 'Planned Development', false, false, false, 'LDC Part 10'),
  (631, 'IPD-1', 'Industrial Planned Development-1', 'Industrial', false, false, false, 'LDC Part 10'),
  (631, 'IPD-2', 'Industrial Planned Development-2', 'Industrial', false, false, false, 'LDC Part 10'),
  (631, 'CG', 'Commercial General', 'Commercial', NULL::boolean, NULL::boolean, NULL::boolean, 'LDC 6.01.01'),
  (631, 'CN', 'Commercial Neighborhood', 'Commercial', NULL::boolean, NULL::boolean, NULL::boolean, 'LDC 6.01.01'),
  (867, 'SH-RS', 'Residential Single-Family (Special Historic)', 'Residential', false, false, NULL::boolean, 'Tampa Code Ch.27')
) AS v(jurisdiction_id, code, name, category, far_regulated, pk1000_regulated, density_regulated, ordinance_section)
WHERE NOT EXISTS (
  SELECT 1 FROM public.zoning_districts zd WHERE zd.jurisdiction_id = v.jurisdiction_id AND zd.code = v.code
);

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, confidence_score, ordinance_section, source_url)
SELECT zd.id, v.density, v.confidence, 'LDC 6.01.01 (district-name density convention)',
       'https://library.municode.com/fl/hillsborough_county/codes/land_development_code'
FROM public.zoning_districts zd
JOIN (VALUES
  (631, 'RSC-9', 9.0, 0.85),
  (631, 'RSC-4', 4.0, 0.85),
  (631, 'RSC-2', 2.0, 0.85),
  (631, 'RSC-3', 3.0, 0.85),
  (631, 'RSC-6', 6.0, 0.95),
  (631, 'AS-1', 1.0, 0.90),
  (631, 'AS-0.4', 2.5, 0.70),
  (631, 'RMC-16', 16.0, 0.85),
  (631, 'RMC-12', 12.0, 0.85),
  (631, 'RMC-20', 20.0, 0.85),
  (631, 'RDC-6', 6.0, 0.75),
  (631, 'RDC-12', 12.0, 0.75)
) AS v(jurisdiction_id, code, density, confidence)
  ON zd.jurisdiction_id = v.jurisdiction_id AND zd.code = v.code
ON CONFLICT (zoning_district_id) DO UPDATE SET
  max_density_du_acre = EXCLUDED.max_density_du_acre,
  confidence_score = EXCLUDED.confidence_score,
  ordinance_section = EXCLUDED.ordinance_section,
  source_url = EXCLUDED.source_url
WHERE zone_standards.max_density_du_acre IS NULL;
