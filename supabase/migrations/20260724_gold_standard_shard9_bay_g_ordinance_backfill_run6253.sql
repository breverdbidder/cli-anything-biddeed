-- Bay G fix: 11 real zoning districts sourced from live municipal ordinance text,
-- adversarially verified (7 survived as-cited, 4 survived with a refuter-corrected
-- citation -- same numeric values, wrong section number in the original citation).
-- Explicit far_regulated/density_regulated/pk1000_regulated overrides are used ONLY
-- where the real ordinance genuinely diverges from the category-based default
-- (e.g. Callaway regulates FAR but not density for single-family zones; Mexico
-- Beach's GC zone allows a residential density despite being a "Commercial"
-- category; several districts defer parking to a citywide use-based table with no
-- zone-specific per-1000sf figure, which is a genuine N/A, not an unknown).

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section, far_regulated, density_regulated, pk1000_regulated) VALUES
  (1332, 'SR-1', 'Seasonal/Resort Residential', 'Residential',
   'Bay County LDR Ch.5 Sec.503/506, Table 5.1. Max density 15 du/acre. Table 5.1 has no FAR or parking row for SR-1 (genuinely not regulated by this metric in this code).',
   'Bay County LDR Chapter 5, Section 506, Table 5.1', NULL, NULL, NULL),
  (1332, 'SR-2', 'Seasonal/Resort Commercial', 'Commercial',
   'Bay County LDR Ch.5 Sec.505/506, Table 5.1. Despite the Commercial category label, SR-2 inherits SR-1 uses and carries the same 15 du/acre max density in Table 5.1. Table 5.1 has no FAR or parking row for SR-2 (genuinely not regulated by this metric).',
   'Bay County LDR Chapter 5, Section 506, Table 5.1', false, true, false),
  (1332, 'C-3', 'General Commercial', 'Commercial',
   'Bay County LDR Ch.6 Sec.602/609, Table 6.1 (FAR=200%); Ch.25 Sec.2505 Table 25.1 (parking, use-based citywide, 4/1000sf for retail/office uses). No density figure for this commercial district (footnote-1 exception is Beaches Special Treatment Zone only, not C-3 generally).',
   'Bay County LDR Chapter 6 Section 609 Table 6.1; Chapter 25 Section 2505 Table 25.1', NULL, NULL, NULL),
  (907, 'R-3', 'Unlimited Multi-family', 'Residential',
   'Panama City Beach LDC Sec.2.02.01.A.9, Table 2.04.01. Density 40 du/acre. Table 2.04.01 FAR row = "None" for R-3 (confirmed: FAR applies only to non-residential uses per Note B).',
   'PCB LDC Sec. 2.04.01, Table 2.04.01', NULL, NULL, NULL),
  (983, 'R-6', 'Single-family residential', 'Residential',
   'Callaway LDR Sec.15.531. FAR=40% is an explicit, real bulk regulation for this residential district (unusual but genuine -- overriding the category default). No dwelling-units-per-acre figure exists anywhere in the section (density is controlled via 6,000 sf min lot size instead, not a stated du/acre standard) and no parking figure exists -- both genuinely not regulated by these metrics in this code, not merely unknown.',
   'Callaway LDR Sec. 15.531', true, false, false),
  (983, 'R-6M', 'Single-family residential (mobile homes)', 'Residential',
   'Callaway LDR Sec.15.532. Identical bulk regs to R-6: FAR=40% explicit. No density (du/acre) or parking figure exists in the section -- genuinely not regulated by these metrics.',
   'Callaway LDR Sec. 15.532', true, false, false),
  (983, 'R-8', 'Single-family residential', 'Residential',
   'Callaway LDR Sec.15.525. Identical bulk-reg template to R-6/R-6M (8,000 sf min lot instead of 6,000): FAR=40% explicit. No density (du/acre) or parking figure exists in the section.',
   'Callaway LDR Sec. 15.525', true, false, false),
  (884, 'MU 2', 'Mixed Use-2', 'Mixed-Use',
   'Panama City ULDC Sec.104-31. FAR<=0.65, density<=10 du/acre. Parking deferred to citywide Chapter 108 (use-based, no zone-specific per-1000sf figure) -- genuinely not a district-level standard. Citation note: adversarial verifier found the original source_url (DocumentCenter/View/6505) actually resolves to Sec.104-36.1 (a different, unrelated district); independently re-derived and confirmed the real Sec.104-31 MU-2 text via a third-party ordinance mirror (zoneomics.com/code/panama-city-FL/chapter_4) which reproduces the same purpose text and identical numeric values verbatim -- the figures themselves check out, the citation is corrected here.',
   'Panama City ULDC Sec. 104-31 (citation corrected during adversarial verification)', NULL, NULL, false),
  (884, 'UR 1', 'Urban Residential-1', 'Residential',
   'Panama City ULDC Sec.104-29. FAR<=0.75 is an explicit, real bulk regulation for this residential district (overriding the category default). Density<=15 du/acre. Parking deferred to citywide Chapter 108 -- genuinely not a district-level standard. Citation note: same as MU-2 -- original source_url (DocumentCenter/View/6505) is actually Sec.104-36.1, unrelated; independently re-derived and confirmed the real Sec.104-29 UR-1 text verbatim via panamacity.gov/AgendaCenter/ViewFile/Item/4181?fileID=11861 (full Chapter 104 ULDC packet, pages 9-10).',
   'Panama City ULDC Sec. 104-29 (citation corrected during adversarial verification)', true, NULL, false),
  (985, 'GC', 'General Commercial', 'Commercial',
   'Mexico Beach LDC allows single-family residential up to 18 du/acre within the GC district alongside commercial uses (real, applicable despite the Commercial category default excluding density) -- overriding the category default. This code uses Impervious Surface Ratio (0.90 for GC), not FAR, as its intensity metric -- FAR is genuinely not a concept in this code, not merely missing. Parking (Sec.6.03.00) is a citywide use-based matrix (e.g. 1 per 300sf retail), not a zone-specific per-1000sf figure -- genuinely not district-level. Citation note: original source_url/section (amlegal 0-0-0-239, "Sec.2.01.03(E)") is actually the introductory zoning-districts LIST page with no standards table; the real standards table is Sec.2.02.02(D) of the same code -- independently re-derived and confirmed verbatim via the city''s own official PDF (mexicobeachfl.gov/uploads/2022/06/Revised-LDR-August-2019.pdf).',
   'Mexico Beach LDC Sec. 2.02.02(D) (citation corrected during adversarial verification)', false, true, false),
  (985, 'RG', 'Residential General', 'Residential',
   'Mexico Beach LDC. Density<=6 du/acre. This code uses Impervious Surface Ratio (0.40 for RG), not FAR -- genuinely not a concept in this code. Parking (Sec.6.03.00) is stated per-dwelling-unit (2/unit), not per-1000sf -- a different, non-convertible metric, genuinely not expressed this way. Citation note: same as GC -- real standards table is Sec.2.02.02(B), not the originally-cited introductory list page; independently re-derived and confirmed verbatim via the city''s own official PDF.',
   'Mexico Beach LDC Sec. 2.02.02(B) (citation corrected during adversarial verification)', NULL, NULL, NULL)
ON CONFLICT DO NOTHING
RETURNING id, jurisdiction_id, code;

-- Callaway R-6/R-6M/R-8 already existed as zoning_districts rows (ids 6006/6008/6010)
-- so the INSERT above skipped them via ON CONFLICT; apply their overrides + fix a
-- pre-existing data bug via UPDATE instead (max_far was stored as 40.00 -- a FAR of
-- 40 is not physically plausible for single-family residential; the real ordinance
-- text confirms this is "Floor Area Ratio - 40%" misstored as a bare percentage
-- instead of a decimal fraction 0.40).
UPDATE zoning_districts SET far_regulated=true, density_regulated=false, pk1000_regulated=false,
  description='Callaway LDR: FAR=40% is an explicit, real bulk regulation for this residential district (overriding the category default). No dwelling-units-per-acre figure exists anywhere in the section (density controlled via min lot size instead) and no parking figure exists -- both genuinely not regulated by these metrics in this code.',
  ordinance_section = CASE code WHEN 'R-6' THEN 'Callaway LDR Sec. 15.531' WHEN 'R-6M' THEN 'Callaway LDR Sec. 15.532' WHEN 'R-8' THEN 'Callaway LDR Sec. 15.525' END
WHERE id IN (6006,6008,6010);

UPDATE zone_standards SET max_far = 0.40
WHERE zoning_district_id IN (6006,6008,6010) AND max_far = 40.00;

-- zone_standards for the 8 newly-inserted districts above (Callaway's 3 already had
-- zone_standards rows, only needed the max_far correction above).
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, max_far, parking_per_1000sf) VALUES
  (12783, 15, NULL, NULL),   -- Unincorp Bay SR-1
  (12784, 15, NULL, NULL),   -- Unincorp Bay SR-2
  (12785, NULL, 2.0, 4.0),   -- Unincorp Bay C-3
  (12786, 40, NULL, NULL),   -- PCB R-3
  (12790, 10, 0.65, NULL),   -- Panama City MU-2
  (12791, 15, 0.75, NULL),   -- Panama City UR-1
  (12792, 18, NULL, NULL),   -- Mexico Beach GC
  (12793, 6, NULL, NULL)     -- Mexico Beach RG
ON CONFLICT DO NOTHING;

-- RESULT: bay G 57.4% (mid-session regression low point) -> 100.0% (density=100.0
-- far=100.0 pk1000=100.0). Bay is now 10/10 on all pencil_dod_criteria letters.
-- gold_standard_ultraloop_audit id 9608 has the full survival-vote evidence.
