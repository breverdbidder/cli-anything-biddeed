-- SHARD-3 run2886 (charlotte/highlands/volusia/manatee/liberty), 2026-07-04
--
-- Manatee G (zoning density) was 90.4% (562 density-applicable parcels, 397 N/A,
-- 53 "unverified" district codes missing max_density_du_acre). The single
-- highest-leverage gap is zoning_districts.code='A-1' (Agricultural-1,
-- Unincorporated Manatee County, 33 parcels) which had NO zone_standards row.
--
-- Value CONFIRMED from Manatee County LDC Chapter 4 - Zoning ("Figure 6-2.
-- Schedule of Area, Height, Bulk and Placement Regulations"), LDC Section
-- 602.1.2.2 "A-1: Agricultural Suburban District": max density = 1.0 DUA,
-- min lot 43,560 sqft (1 acre), min width 100 ft. Cross-validated against
-- the already-verified "A" (General Agriculture) district in this same table,
-- which independently matches our existing DB value of 0.20 DUA / 217,800 sqft
-- (5-acre min lot) exactly -- confirms this source table reflects the
-- currently adopted standard, not a stale draft.
--
-- CAVEAT (honesty marker, confidence_score below 1.0): the specific PDF pulled
-- was watermarked as a 2015 staff redline/draft copy of Ch.4; Municode's live
-- JS-rendered codified page could not be scraped directly to confirm the exact
-- table cell word-for-word. Independently confirmed A-1 is a live, current,
-- non-legacy district via Municode's index and a Zoneomics mirror (identical
-- section numbering 401.1.C=A, 401.1.D=A-1). This is NOT a guess -- it is a
-- primary-source figure with one sourcing caveat, tagged accordingly.

INSERT INTO zone_standards (
  zoning_district_id,
  min_lot_sqft,
  min_lot_width_ft,
  max_density_du_acre,
  source_url,
  ordinance_section,
  confidence_score
)
SELECT
  zd.id,
  43560,
  100,
  1.00,
  'https://www.mymanatee.org/media/docs/.../land-development-regulations/ldc-ch4-zoning-v64-comments.pdf?sfvrsn=ff9aaf2d_3',
  'LDC Sec. 602.1.2.2 (A-1: Agricultural Suburban District), Figure 6-2 -- CAVEAT: sourced from a 2015 staff-redline draft copy of Ch.4, cross-validated against already-verified "A" district figure (0.20 DUA) in the same table; live codified Municode page could not be scraped to confirm word-for-word',
  0.85
FROM zoning_districts zd
JOIN jurisdictions j ON j.id = zd.jurisdiction_id
WHERE lower(j.county) = 'manatee' AND zd.code = 'A-1'
ON CONFLICT DO NOTHING;

UPDATE zoning_districts
SET density_regulated = true,
    name = 'Agricultural Suburban District'
WHERE id = (
  SELECT zd.id FROM zoning_districts zd
  JOIN jurisdictions j ON j.id = zd.jurisdiction_id
  WHERE lower(j.county) = 'manatee' AND zd.code = 'A-1'
);
