-- Gold Standard letter G fix for miami_dade (architect triage, 2026-08-25)
--
-- SYMPTOM: G FAILED at 94.4% (density=98.8, far=94.4, pk1000=100.0; FAR was
-- binding constraint). FAR-applicable parcels for miami_dade = exactly 18
-- fleet-wide; 17/18 had max_far populated, 1 did not.
--
-- ROOT CAUSE: zoning_districts.id=4007 (code='IU-C', name='IU-C INDUSTRIAL
-- DISTRICT, CONDITIONAL', jurisdiction_id=1057 = Miami Lakes) had
-- far_regulated=NULL, so v_zoning_district_applicability's
-- CASE WHEN far_regulated IS NOT NULL THEN far_regulated ELSE
--   category IN ('commercial','industrial','mixed-use') AND name !~ 'pud' END
-- defaulted far_applicable=true for this Industrial-category district,
-- counting parcel 32-2024-034-0060 (zone_standards.id=2249) against the FAR
-- denominator even though max_far was (correctly) NULL.
--
-- RESEARCH (2026-08-25, WebSearch + WebFetch against library.municode.com
-- and the miamidade.elaws.us mirror -- Municode's own site returned 403 on
-- direct fetch, elaws.us mirrors the same statutory text and was used to
-- read full section text):
--
-- Miami Lakes' "IU-C" is NOT a Miami Lakes-authored zoning district. The
-- Town of Miami Lakes incorporated in 2000 and retained Miami-Dade County's
-- Chapter 33 zoning code, including Article XXXII "IU-C, INDUSTRIAL
-- DISTRICT, CONDITIONAL" (confirmed via Miami-Dade Municode Article XXXII
-- matching the exact same code + name string, and via web search results
-- describing Miami Lakes rezoning actions moving parcels "from IU-C ...
-- District" citing the county article).
--
-- Article XXXII section list (Secs. 33-267 through 33-278.4) contains NO
-- Floor Area Ratio section:
--   33-267  Intent
--   33-268  Permitted uses
--   33-269  Permit for use; issuance; denial; appeals
--   33-270  Uses confined to buildings or within wall enclosures
--   33-271  Platting of land before use
--   33-272  Frontage; depth and area   <- acreage/frontage/depth only, no FAR
--   33-273  Setbacks                    <- setbacks only, no FAR/coverage/height
--   33-274  Off-street parking
--   33-275  Water supply, sewage and waste disposal
--   33-276  Fire protection
--   33-277  Multiple industrial uses
--   33-278  Application of other provisions (incorporates other industrial
--           regs "not superseded or modified" by this article)
--   33-278.1 Minimum landscaped open space (20% net lot area) -- MINIMUM
--           open space, not a max lot coverage or FAR cap
--   33-278.2 Site plan review
--   33-278.4 Validity of site plan
--
-- Fetched full text of 33-272, 33-273, 33-278, 33-278.1 directly -- none
-- mention Floor Area Ratio. Contrast: Miami-Dade Article XXVI (BU-2 Special
-- Business District) Sec. 33-253.3 "Floor area ratio and lot coverage" DOES
-- have an explicit FAR formula (0.40 at 1 story, +0.11/story to 8 stories,
-- +0.06/story thereafter) -- proving Miami-Dade's code DOES use dedicated
-- FAR sections where a district is FAR-regulated, and IU-C's Article XXXII
-- simply has no such section. Further corroboration: Miami-Dade IU-1
-- (Article XXIX) Sec. 33-259(39b)(5), for a specific industrial mixed-use
-- provision, states verbatim "Floor area ratio: No limitation" -- Miami-Dade
-- affirmatively does not FAR-cap this zoning family; density/bulk in
-- industrial districts is controlled via lot coverage, setbacks, and
-- landscaping minimums instead.
--
-- CONCLUSION: max_far=NULL on zone_standards.id=2249 is honestly correct --
-- this is NOT a missing-data gap. The bug is in far_applicable classification
-- (Branch 2 of the investigation): far_regulated was NULL and defaulted to
-- true. Fix: explicitly set far_regulated=false so
-- v_zoning_district_applicability correctly excludes this district from the
-- FAR-applicable denominator, matching the same far_regulated override
-- pattern already used fleet-wide (see 20260623_brevard_g_zoning_fix.sql,
-- 20260724_gold_standard_shard5_volusia_g_remaining_municipalities.sql,
-- 20260718s_gold_standard_shard12_okeechobee_pk1000_regulated_override_column.sql).
--
-- VERIFIED LIVE via rpc/pencil_dod_evaluate_county (2026-08-25):
--   BEFORE: G {"pass": false, "detail": "density=98.8 far=94.4 pk1000=100.0", "metric": 94.4}
--   AFTER:  G {"pass": true,  "detail": "density=98.8 far=100.0 pk1000=100.0", "metric": 98.8}
-- Other letters (A,B,C,D,E,F,H,I,J) byte-identical before/after -- no
-- collateral regression. B, F, J remain independently FAILing (out of scope
-- for this fix, not touched).

UPDATE zoning_districts
   SET far_regulated = false,
       ordinance_section = 'Miami-Dade County Code of Ordinances Ch. 33, Art. XXXII (IU-C, Industrial District, Conditional), Secs. 33-267 through 33-278.4 -- no FAR section exists in this article (contrast Art. XXVI Sec. 33-253.3 BU-2 which has an explicit FAR formula). Dimensional controls for IU-C are acreage/frontage/depth (Sec. 33-272), setbacks (Sec. 33-273), and 20% min landscaped open space (Sec. 33-278.1); Sec. 33-278 incorporates other industrial-use regulations not superseded by this article, and Miami-Dade IU-1 Sec. 33-259(39b)(5) explicitly states "Floor area ratio: No limitation" for industrial uses, confirming FAR is not a regulated dimension for this zoning family. Miami Lakes IU-C is the retained legacy Miami-Dade County zoning classification (Town incorporated 2000, kept county zoning code).'
 WHERE id = 4007 AND code = 'IU-C' AND jurisdiction_id = 1057;

UPDATE zone_standards
   SET source_url = 'http://miamidade.elaws.us/code/coor_ch33_artxxxii (Miami-Dade County Code Ch. 33 Art. XXXII, IU-C Industrial District Conditional) + https://library.municode.com/fl/miami_-_dade_county/codes/code_of_ordinances/378609?nodeId=PTIIICOOR_CH33ZO_ARTXXXIIINDICO_S33-268PEUS (Miami Lakes retains this Miami-Dade legacy zoning classification)',
       ordinance_section = 'Secs. 33-267 to 33-278.4 (no FAR section in this article -- max_far correctly NULL; far_regulated=false set on zoning_districts.id=4007). max_lot_coverage_pct=70.00 and parking_per_1000sf=2.00 unchanged (pre-existing, not re-verified this pass).'
 WHERE id = 2249 AND zoning_district_id = 4007;
