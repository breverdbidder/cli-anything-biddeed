-- GOLD STANDARD shard-3 (dispatch 85a4f86f-993f-40c0-9095-47ac8d01a6e5) — clay G
-- density=91.9% (137/149 applicable parcels); 12 gap parcels sat on 3 districts with no
-- zone_standards row: BFPUD (8 parcels), AR-2 (2), RA (2). far/pk1000 show NULL in the KPI
-- view because 0 of clay's auction parcels sit on commercial/industrial land — this is
-- correct N/A flagging, not a bug (LEAST() skips NULL args, confirmed live).
--
-- BFPUD alone (8 of 12 gap parcels) was sufficient to clear the 95% threshold. Value sourced
-- from Clay County LDC Sec. 3-33A (Branan Field Master Plan Land Development Regulations,
-- adopted March 2004), corroborated via an independently-parsed novusagenda.com ordinance-
-- amendment PDF quoting live LDC page headers (3-280 to 3-284) for the same section number.
-- Stored value is the ceiling of the tiered density table (Traditional Neighborhood, 5 du/ac
-- gross), matching the ceiling-storage precedent already in production for the AR district
-- (Sec. 3-13(e), zone_standards id 4645, confidence_score 0.60).
--
-- AR-2 and RA (4 parcels) deferred — no verifiable ordinance section text could be retrieved
-- (claycountygov.com / library.municode.com / images1.showcase.com all 403'd) — NOT required
-- for PASS since BFPUD alone clears the threshold.
--
-- Result (adversarially verified): G density 91.9% -> 97.3%, PASS.

INSERT INTO public.zone_standards (
  zoning_district_id,
  max_density_du_acre,
  source_url,
  ordinance_section,
  confidence_score
)
SELECT
  11892,
  5.00,
  'https://www.claycountygov.com/home/showdocument?id=852',
  'Branan Field Master Plan Land Development Regulations (Adopted March 2004), codified as Clay County LDC Sec. 3-33A; residential density tiered by neighborhood type within the Branan Field Planned Unit Development (BFPUD): Rural Residential 1u/5ac to 1u/1ac, Master-Planned Community 3 du/ac gross, Traditional Neighborhood 5 du/ac gross; value stored is the ceiling of the tiered table (Traditional Neighborhood), consistent with the AR-district ceiling-storage precedent (Sec. 3-13(e))',
  0.55
WHERE NOT EXISTS (
  SELECT 1 FROM public.zone_standards WHERE zoning_district_id = 11892
);
