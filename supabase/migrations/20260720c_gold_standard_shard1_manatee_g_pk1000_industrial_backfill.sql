-- Gold Standard shard-1 (manatee, dispatch 7abd0202-3b36-494c-bed2-9bdea65987e2): letter G
-- pk1000 (parking_per_1000sf coverage) was the binding constraint at 64.7%
-- (density=96.3, far=100.0 already pass, untouched here). Only 17
-- pk1000_applicable parcels county-wide; 6 NULL, resolving to exactly two
-- zoning_districts rows, both Unincorporated Manatee County
-- (jurisdiction_id=1257):
--   standard_id=3988, district HM "Heavy Manufacturing", 5 parcels
--   standard_id=3602, district LM "Light Manufacturing", 1 parcel
--     (previously carried a shard9_run651 INFERRED placeholder source_url,
--      not a real citation -- corrected here to a real one)
--
-- Source (live-fetched + pdftotext-extracted 2026-07-20, verified against
-- the primary document myself rather than trusting a prior citation):
--   Manatee County LDC Chapter 10, Transportation Management
--   (mymanatee.org/media/docs/.../land-development-regulations/
--    ldc-ch10-transportation-management-v53-comments.pdf)
--   Sec 1005.3 / 710.1.6, Table 10-2 "Parking Ratios", page 10-30.
--   The table's "Spaces/Sq. Ft. or Unit of Measure" column is BLANK for
--   both "Manufacturing: Heavy" and "Manufacturing: Light" rows (and for
--   "Industrial Service Establishment") -- the entire requirement for
--   these three industrial use rows is defined by footnote 8 (page 10-33):
--   "Or one (1) space per two hundred fifty (250) square feet of gross
--   office area, plus one (1) space per one thousand (1,000) square feet
--   of the remaining gross floor area." Footnote 11 ("plus one space per
--   company vehicle") also applies to all three rows; footnote 18 (up to
--   15% reduction for qualifying shared-parking programs on lots >100
--   spaces) additionally applies to Light only. Same one ratio (8+11, or
--   8+11+18 for Light) applies to BOTH Heavy and Light Manufacturing --
--   the LDC does not split HM/LM into different parking rates, which is
--   itself a genuine finding, not a simplification on our part.
--
-- DISCLOSED JUDGMENT CALL: parking_per_1000sf is a single ratio column
-- and footnote 8 is a two-component formula (1/250sf office + 1/1000sf
-- remaining GFA). We map the column to the "remaining gross floor area"
-- component (1.0 space/1,000 sq ft), which is the correct rate for the
-- non-office (manufacturing floor) portion of the building -- the
-- dominant use for HM/LM industrial space -- and record the office-area
-- component and the company-vehicle/reduction footnotes in full in
-- ordinance_section so the two-component nature of the real requirement
-- is not hidden.
--
-- Idempotent: parking_per_1000sf IS NULL guards, safe to re-run.

BEGIN;

UPDATE public.zone_standards
SET parking_per_1000sf = 1.0,
    source_url = 'https://www.mymanatee.org/media/docs/default-source/development-services-department-documents/development-services-department-documents/land-development-regulations/ldc-ch10-transportation-management-v53-comments.pdf',
    ordinance_section = ordinance_section || ' | Parking: Manatee LDC Ch.10, Sec 1005.3/710.1.6, Table 10-2 "Parking Ratios" p.10-30, row "Manufacturing: Heavy" (Spaces/Sq.Ft. column blank, ratio wholly defined by footnote 8+11). Footnote 8 (p.10-33): "Or one (1) space per two hundred fifty (250) square feet of gross office area, plus one (1) space per one thousand (1,000) square feet of the remaining gross floor area" -- remaining-GFA component = 1.0 space/1,000 sq ft (recorded here); office-area component is a separate 1/250sf rate not representable in this single-ratio column. Footnote 11: plus 1 space per company vehicle. Same rate applies to Manufacturing: Light (LDC does not split HM/LM parking rates).'
WHERE id = 3988
  AND zoning_district_id = 11249
  AND parking_per_1000sf IS NULL;

UPDATE public.zone_standards
SET parking_per_1000sf = 1.0,
    source_url = 'https://www.mymanatee.org/media/docs/default-source/development-services-department-documents/development-services-department-documents/land-development-regulations/ldc-ch10-transportation-management-v53-comments.pdf',
    ordinance_section = 'Parking: Manatee LDC Ch.10, Sec 1005.3/710.1.6, Table 10-2 "Parking Ratios" p.10-30, row "Manufacturing: Light" (Spaces/Sq.Ft. column blank, ratio wholly defined by footnote 8+11+18). Footnote 8 (p.10-33): "Or one (1) space per two hundred fifty (250) square feet of gross office area, plus one (1) space per one thousand (1,000) square feet of the remaining gross floor area" -- remaining-GFA component = 1.0 space/1,000 sq ft (recorded here); office-area component is a separate 1/250sf rate not representable in this single-ratio column. Footnote 11: plus 1 space per company vehicle. Footnote 18: up to 15% reduction allowed for facilities >100 spaces with a qualifying shared-parking program. Same base rate applies to Manufacturing: Heavy (LDC does not split HM/LM parking rates). Replaces prior placeholder source_url shard9_run651_INFERRED:standard_fl_ldr_pattern_manatee_lm, which was an inferred generic-pattern guess, not a real ordinance citation.'
WHERE id = 3602
  AND zoning_district_id = 10896
  AND parking_per_1000sf IS NULL;

COMMIT;
