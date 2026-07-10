-- Franklin County letter-G (zoning KPI) regression fix.
--
-- ROOT CAUSE: scripts/franklin_zoning_backfill.py (this shard, earlier session, commit
-- f155b7bf) created zoning_districts rows for R-2/R-5/R-6 and assigned zone_code on all
-- 9 franklin auction parcels (fixing letter I 0%->100%), but never populated zone_standards
-- dimensional values for those three new districts -- only the pre-existing R-1 district
-- (zoning_district_id=11163) had a max_density_du_acre value. This silently regressed
-- pencil_dod_evaluate_county('franklin').G from PASS 100.0 to FAIL 20.0 (density coverage),
-- an undisclosed side effect not caught by that session's own verification (which only
-- checked letter I). FAR and parking are correctly already marked not-applicable for these
-- residential districts via zoning_districts.far_regulated/... -- only density was missing.
--
-- SOURCING (HONESTY PROTOCOL -- two independent sources per value, no guessed numbers):
--   Source 1: https://zoning.franklincountyflorida.gov/pages/zoning-classifications
--   Source 2 (independent corroboration, different domain, official ordinance PDF):
--     https://www.franklincountyflorida.com/documents/planning_building/zoningcode.pdf
--     (Franklin County Zoning Code, Ordinance No. 2004-41, Aug 17 2004)
--   R-2 Single Family Residential/Mobile: min lot size 1 acre, 1 single-family dwelling
--     per lot (no explicit du/acre figure in the ordinance) -> INFERRED 1.0 du/acre.
--   R-5 Multi-Family: "one dwelling unit per 10,000 square feet" (explicit in both
--     sources, word-for-word) -> INFERRED 4.356 du/acre (43,560 sqft/acre / 10,000).
--   R-6 Rural Residential: "overall density ... one dwelling unit per 10 acres" (explicit
--     in both sources) -> VERIFIED 0.1 du/acre.

INSERT INTO public.zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score)
VALUES
  (11311, 1.000, 'https://www.franklincountyflorida.com/documents/planning_building/zoningcode.pdf',
   'R-2 Single Family Residential/Mobile District -- Development Standards, Minimum Lot Size: one acre, one single-family dwelling per lot (Ord. 2004-41); density INFERRED from min-lot-size, not an explicit du/acre figure in the ordinance', 0.85),
  (11315, 4.356, 'https://www.franklincountyflorida.com/documents/planning_building/zoningcode.pdf',
   'R-5 Multi-Family District -- Development Standards, Minimum Lot Size: one dwelling unit per 10,000 square feet (Ord. 2004-41); density INFERRED via 43,560 sqft/acre / 10,000 sqft/unit', 0.9),
  (11316, 0.100, 'https://www.franklincountyflorida.com/documents/planning_building/zoningcode.pdf',
   'R-6 Rural Residential District -- Development Standards: "the overall density on the property is one dwelling unit per 10 acres" (Ord. 2004-41); VERIFIED, explicit in ordinance text', 0.95);
