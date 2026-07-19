-- Shard3: miami_dade letter G (pk1000) fix.
-- Root cause (verified this session): of all zoning_districts referenced by
-- miami_dade parcel_zones, only two are flagged pk1000_applicable=true by
-- v_zoning_district_applicability, and both had parking_per_1000sf = NULL:
--   - id=11833 Miami Beach CD-2 "Commercial, Medium Intensity District"
--   - id=11291 Miami-Dade County (Unincorporated) NCUC "Naranja Community
--     Urban Center District"
-- This migration inserts real, citable parking_per_1000sf values for both,
-- sourced from the actual current ordinance text (verified via pdftotext
-- extraction of the primary-source PDFs, not guessed).

SET statement_timeout = 0;

-- ---------------------------------------------------------------------
-- District 11291: Miami-Dade Unincorporated, NCUC (Naranja Community
-- Urban Center District).
--
-- Sec. 33-284.67(A) (Naranja Community Urban Center District Requirements):
--   "Except as provided herein, all developments within the NCUC shall
--   comply with the requirements provided in Article XXXIII(K), Standard
--   Urban Center District Regulations, of this code."
--
-- Sec. 33-284.86(F) (Article XXXIII(K), "Parking"), subsection F.2 table:
--   "General Retail/Personal Services and Entertainment Uses: 1 space/250
--   square feet of gross floor area" = 4.00 spaces / 1,000 sq ft.
--   (This also matches Miami-Dade's general Sec. 33-124 retail rate of
--   1 space/250 sq ft, which Sec. 33-284.86(F) explicitly falls back to
--   for uses not separately listed.)
--
-- Source: https://www.miamidade.gov/zoning/library/reports/naranja-district-regulations.pdf
--         (Sec. 33-284.67 text) cross-referencing Article XXXIII(K)
--         Standard Urban Center District Regulations, Sec. 33-284.86(F)(2)
--         table, https://www.miamidade.gov/zoning/library/reports/standard-urban.pdf
-- ---------------------------------------------------------------------
INSERT INTO zone_standards (
    zoning_district_id,
    parking_per_1000sf,
    ordinance_section,
    source_url,
    confidence_score,
    scraped_at
)
VALUES (
    11291,
    4.00,
    'Sec. 33-284.67(A) referencing Art. XXXIII(K) Sec. 33-284.86(F)(2) (General Retail/Personal Services: 1 space/250 sf)',
    'https://www.miamidade.gov/zoning/library/reports/standard-urban.pdf',
    0.85,
    now()
)
ON CONFLICT (zoning_district_id) DO UPDATE SET
    parking_per_1000sf = EXCLUDED.parking_per_1000sf,
    ordinance_section = EXCLUDED.ordinance_section,
    source_url = EXCLUDED.source_url,
    confidence_score = EXCLUDED.confidence_score,
    scraped_at = EXCLUDED.scraped_at
WHERE zone_standards.parking_per_1000sf IS NULL;

-- ---------------------------------------------------------------------
-- District 11833: Miami Beach CD-2 "Commercial, Medium Intensity District".
--
-- Sec. 130-31(a)(1): "Parking district no. 1 is that area not included in
-- parking districts nos. 2, 3, 4, 5, 6, and 7" -- i.e. Parking District
-- No. 1 is the citywide default that applies to CD-2 zoning generally
-- (districts 2-7 are narrow named geographic carve-outs: Lincoln Road,
-- Arthur Godfrey Rd CD-3, North Beach Town Center + specific CD-2 lot-line
-- segments, Sunset Harbour, Alton Court, Washington Ave).
--
-- Sec. 130-32(37): "Retail store, coin laundry, dry cleaning receiving
--   station, stock brokerage or personal service establishment: 1 space
--   per 300 square feet of floor area" = 3.33 spaces / 1,000 sq ft.
--   Used as the representative commercial baseline rate for the CD-2
--   district record (retail/personal service is the general commercial
--   use category; office is a lower 1/400sf=2.5/1000sf and general
--   service/repair is 1/1000sf=1.0/1000sf under the same section).
--
-- Source: Miami Beach Code Sec. 130-32, verified via pdftotext extraction
--         of https://miamibeach.novusagenda.com/agendapublic//AttachmentViewer.ashx?AttachmentID=7017&ItemID=2973
--         ("Parking District No. 1" ordinance, full codified text of
--         Sec. 130-32), cross-referenced with district boundary text of
--         Sec. 130-31 in https://www.ordinancewatch.com/files/82613/LocalGovernment115507.pdf
-- ---------------------------------------------------------------------
UPDATE zone_standards
SET
    parking_per_1000sf = 3.33,
    ordinance_section = 'Sec. 130-32(37) (Parking District No. 1, applicable citywide per Sec. 130-31(a)(1) default) — Retail store/personal service: 1 space/300 sf',
    source_url = 'https://miamibeach.novusagenda.com/agendapublic//AttachmentViewer.ashx?AttachmentID=7017&ItemID=2973',
    confidence_score = 0.75,
    scraped_at = now()
WHERE zoning_district_id = 11833
  AND parking_per_1000sf IS NULL;
