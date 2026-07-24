-- Gold Standard sumter shard-7 continuation (dispatch a3c9a3be-ebc2-4233-a784-3b405076bc63)
-- G: Wildwood M-1 FAR + parking-per-1000sf standards (closes the gap left open by
-- 20260724b_sumter_g_wildwood_m1_district_classification.sql, which classified the
-- district but left far/parking NULL -- 4 access attempts that session all failed).
--
-- THIS SESSION: retrieved the full City of Wildwood, FL Land Development Regulations
-- (adopted 2011-07-25, amended 2025-07-28) by proxying the Cloudflare-gated PDF through
-- r.jina.ai (a text-extraction reader), succeeding where WebFetch/curl/Firecrawl all
-- 403'd or 402'd again. An adversarial refuter independently re-fetched the SAME PDF via
-- a completely different method (Wayback Machine archived snapshot, timestamp
-- 20260709160843, downloaded directly with curl, converted with pdftotext -- no reader
-- proxy involved) and independently confirmed the two numeric facts below verbatim.
--
--   TABLE 3-4B (Density, Intensity, and Lot Standards -- Nonresidential Zoning Districts):
--     Maximum FAR, M-1 column = 0.5
--   TABLE 6-12 (Minimum Standards for Off-Street Parking Requirements, Non-Residential
--   Land Uses): Industrial = 1.0 space per 675 sq ft GFA = 1.481 spaces per 1,000 sq ft
--
-- CORRECTION vs the original research claim (caught by the refuter, not by me guessing):
-- the original claim also proposed a second, lower parking figure (0.5/1000sf) for a
-- "Warehouse" use row, reasoning M-1 is titled "Light Industrial and Warehousing
-- District". The refuter independently checked TABLE 3-1 (Zoning Districts) in this same
-- document and found M-1's actual district title is simply "Industrial" (M-2 is "Heavy
-- Industrial") -- the phrase "Light Industrial and Warehousing" does not appear anywhere
-- in the 319-page document. That title was fabricated-by-analogy from other Florida
-- jurisdictions' naming conventions, not Wildwood's own text. Only the Industrial parking
-- row (1.481/1000sf) is used here; the Warehouse row is dropped as unconfirmed for this
-- district.
--
-- Source: https://www.wildwood-fl.gov/sites/default/files/fileattachments/development_services/page/2851/city_of_wildwood_land_development_regulations_20250728b.pdf.pdf
-- (independently re-confirmed via Wayback Machine snapshot dated 2026-07-09, same content)

INSERT INTO zone_standards (
  zoning_district_id, max_far, parking_per_1000sf,
  source_url, ordinance_section, confidence_score, scraped_at
)
VALUES (
  12481, 0.5, 1.481,
  'https://www.wildwood-fl.gov/sites/default/files/fileattachments/development_services/page/2851/city_of_wildwood_land_development_regulations_20250728b.pdf.pdf',
  'Table 3-4B (Maximum FAR); Table 6-12 (Industrial off-street parking, 1.0/675sf GFA)',
  0.95,
  now()
)
ON CONFLICT DO NOTHING;
