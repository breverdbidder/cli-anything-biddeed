-- Gold Standard shard-5 (run3713) continuation -- martin county E + I.
-- Note: this dispatch (shard-5) targeted the same county/letters as an already-landed shard-12
-- fix (commit 41d30fe1, migration 20260711h_gold_standard_martin_e_g_i_parcel_zoning_fix.sql).
-- Verified live via pencil_dod_evaluate_county('martin') before touching anything: state matched
-- that prior fix's after-state exactly (8/10, E FAIL 90.6%, I FAIL 40.6%), so this migration
-- continues from there rather than duplicating it.
--
-- Method: ULTRALOOP research fan-out (7 parallel research agents, one per unresolved zoning code
-- carried over as a residual gap from the prior session: R-2A, A-2, R-4, B-2, HR-2, PUD-WJ, and
-- the "Golden Gate Redevelopment Zoning District" / Ord. 1147 special district) + one independent
-- adversarial refuter per code, via the Workflow tool. All 7 findings + refuter verdicts logged to
-- gold_standard_ultraloop_audit ids 5704-5710.
--
-- RESULT: only 1 of 7 codes produced a safely shippable, adversarially-survived, CONFIRMED value.
-- The other 6 remain genuinely unresolved (primary sources 403/timeout-blocked in this session,
-- same wall the prior session hit) -- per HONESTY PROTOCOL (BLANK > WRONG) and HARD GUARDRAILS
-- (never fabricate), no zone_standards rows were written for R-2A/A-2/R-4/B-2/HR-2/Golden Gate.
--
-- IMPORTANT CORRECTION TO PRIOR SESSION'S RECORD: the prior session's residual-gap note treated
-- R-2A and R-4 as plausibly not-applicable/not-found. This session's adversarial refuter for R-2A
-- found it IS a real, current district (Sec. 3.405.1, Category "C", Division 7 -- simply not in
-- Table 3.12.1, which only covers Category A/B) and is almost certainly density-regulated, just
-- with an unlocated numeric value -- do NOT mark R-2A density_regulated=false in a future session
-- without first checking Division 7 directly. R-4 literally does not exist as a district name (the
-- real family is RM-3/RM-4/RM-5, Category A, Table 3.12.1, RM-4=4.00 du/acre) -- our live GIS
-- ZONING field returning literal "R-4" for parcel 48-38-41-180-015-54550-0 is therefore UNRESOLVED
-- (not confirmed to equal RM-4) and was deliberately NOT linked this session pending clarification.
--
-- ============================================================================
-- PART 1 -- PUD-WJ: new zoning district (I: 40.6% -> 46.9%, 13/32 -> 15/32)
-- ============================================================================
-- PUD-WJ = "West Jensen PUD" (Jensen Beach, unincorporated Martin County, TAX_DISTRICT_DESC=
-- "DISTRICT ONE MSTU"). CONFIRMED via live 2024 Martin County Development Review Staff Report
-- W038-108 (West Jensen PUD Phase 1B) -- pdftotext-verified, not just search snippets -- listing
-- "Existing zoning: PUD-WJ" for the immediately adjoining parcels in this corridor, and a Dec 2023
-- Residential Capacity Analysis listing "West Jensen PUD Parcels 6.1-6.4" at 169 approved units
-- (a negotiated, project-specific unit count, not a code-table figure). Same treatment as the
-- already-established PUD/PUD-R mechanism (LDR Policy 4.1E.6/4.1E.8: density negotiated per
-- individual PUD zoning agreement). density_regulated=false, far_regulated=false -- genuinely N/A
-- for this KPI's max_density_du_acre/max_far fields, not an oversight; excluded from G's
-- denominator by the same mechanism as PUD/PUD-R (does not move G, which was already PASS).

BEGIN;

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, density_regulated, far_regulated, ordinance_section, created_at)
VALUES (
  1331, 'PUD-WJ', 'West Jensen PUD (Martin County LDR)', 'residential', false, false,
  'LDR Policy 4.1E.6/4.1E.8 -- density negotiated per individual PUD zoning agreement, not a code table value (same mechanism as PUD/PUD-R). CONFIRMED via live 2024 Martin County Development Review Staff Report W038-108 (West Jensen PUD Phase 1B) listing Existing zoning: PUD-WJ for adjoining parcels in this corridor, and a Dec 2023 Residential Capacity Analysis listing West Jensen PUD Parcels 6.1-6.4 at 169 approved units (project-specific negotiated figure, not a code default).',
  now()
)
ON CONFLICT (jurisdiction_id, code) DO NOTHING;

INSERT INTO zone_standards (zoning_district_id, max_far, max_density_du_acre, source_url, ordinance_section, confidence_score, scraped_at)
SELECT id, NULL, NULL,
  'https://martin.legistar.com/View.ashx?GUID=DBD3FED0-6264-4056-AB46-8FA078B05C31&ID=13069058&M=F (Staff Report W038-108, West Jensen PUD Ph.1B, pdftotext-verified); https://martin.legistar.com/View.ashx?GUID=F6F410FD-EEE9-4EEF-8545-89FA03006C2E&ID=14883118&M=F (Residential Capacity Analysis, Dec 2023)',
  'West Jensen PUD Parcels 6.1-6.4: 169 approved residential units per the Dec 2023 Residential Capacity Analysis -- a negotiated, project-specific unit count under LDR Policy 4.1E.6/4.1E.8, not a code-table du/acre figure. No FAR value found or applicable.',
  0.75, now()
FROM zoning_districts WHERE jurisdiction_id = 1331 AND code = 'PUD-WJ';

-- ============================================================================
-- PART 2 -- E: fabricated parcel_id purge + real GIS-matched linkage (2 parcels)
-- ============================================================================
-- Found via live geoweb.martin.fl.us ArcGIS REST (Parcel Polygons MapServer/10) address search
-- (SITUS_HOUSE_ + SITUS_STREET) after PCN-exact lookup returned NO_PARCEL_MATCH for both. Both
-- addresses match exactly one real county parcel each; the stored parcel_ids were well-formed
-- (folio-shaped) but do not exist anywhere in Martin's own parcel dataset -- fabricated, distinct
-- from the "MARTIN-SYNTHETIC-" placeholders already purged in the prior session.
--
-- case 2024-001-TD-MARTIN, "4100 SE FEDERAL HWY, STUART, FL 34997": stored parcel_id
-- 27-38-41-008-000-01020-1 does not exist in the county parcel layer. Real PCN, address-matched:
-- 18-37-41-004-003-00020-0 (SITUS_CITY=JENSEN BEACH, TAX_DISTRICT_DESC=DISTRICT ONE MSTU) -- zoned
-- PUD-WJ per Part 1 above.
UPDATE multi_county_auctions
SET parcel_id = '18-37-41-004-003-00020-0'
WHERE lower(county) = 'martin' AND case_number = '2024-001-TD-MARTIN'
  AND parcel_id = '27-38-41-008-000-01020-1';

-- case 24000350CAAXMX, "2503 SE WASHINGTON ST, STUART, FL 34997": stored parcel_id
-- 04-38-41-019-010-00010-5 does not exist in the county parcel layer. Real PCN, address-matched:
-- 52-38-41-005-000-00580-8 (SITUS_CITY=STUART mailing / TAX_DISTRICT_DESC=DISTRICT TWO MSTU,
-- i.e. genuinely unincorporated county jurisdiction despite Stuart mailing address) -- zoned
-- R-2B, a district already established in the prior session's fix (density_regulated=false,
-- far_regulated=false), so only the parcel_zones link is new here, no new district/standards.
UPDATE multi_county_auctions
SET parcel_id = '52-38-41-005-000-00580-8'
WHERE lower(county) = 'martin' AND case_number = '24000350CAAXMX'
  AND parcel_id = '04-38-41-019-010-00010-5';

INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)
VALUES
  ('18-37-41-004-003-00020-0', 1331, 'PUD-WJ', 'West Jensen PUD (Martin County LDR)',
   'geoweb.martin.fl.us ArcGIS (Parcel Polygons MapServer/10 centroid -> Zoning MapServer/8 point-in-polygon, area-weighted centroid)'),
  ('52-38-41-005-000-00580-8', 1331, 'R-2B', 'Residential Estate Density (Martin County LDR)',
   'geoweb.martin.fl.us ArcGIS (Parcel Polygons MapServer/10 centroid -> Zoning MapServer/8 point-in-polygon, area-weighted centroid)')
ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================================
-- RESIDUAL GAPS (unchanged from prior session, re-confirmed this session, still not linked):
-- ============================================================================
-- - 5 Stuart-municipality-passthrough + 1 Village-of-Indiantown-passthrough parcels: need each
--   municipality's own zoning ordinance (separate jurisdiction from Martin County LDR), not
--   researched this session.
-- - R-2A (real Category C district, Sec 3.405.1): applicable, numeric value not located (Municode
--   403, elaws.us timeout, PDF 403 on every attempt).
-- - A-2 (agricultural, Sec 3.412): candidate value 0.2 du/acre (1 unit/5 acres, lot-area-derived)
--   conflicts with a separately-cited FLU cap of 0.05 du/acre (1 unit/20 acres) -- unresolved,
--   deliberately not inserted.
-- - R-4: no such district name exists in Table 3.12.1; real family is RM-3/RM-4/RM-5 (Category A).
--   Whether our live GIS "R-4" zone_code is a data-entry variant of RM-4 or a genuinely separate
--   legacy Category B/C code is UNRESOLVED -- do not assume equivalence without further research.
-- - B-2 (commercial, Div 7 Table 3.12.2): density likely N/A (commercial), FAR value not located.
-- - HR-2 (Category C, Sec 3.404, real district): applicable, numeric value not located.
-- - Golden Gate Redevelopment District: form-based CRA code (Article 12 Div 7), density governed
--   by place-type/regulating-plan rather than a single number; final adopted numeric density cap
--   not located (Municode 403, elaws.us timeout). "Ordinance 1147" citation itself could not be
--   independently confirmed as the enabling ordinance for this division.
-- - 2 NO_PARCEL_MATCH folios (distinct from the 2 fabricated ones fixed in Part 2 above) and
--   3 personal-property/timeshare liens with no assessable parcel: structurally unfixable, same
--   ceiling documented in the prior session.
-- All 7 codes researched this session logged to gold_standard_ultraloop_audit ids 5704-5710
-- (dispatch_id 9528efeb-cb38-4b1b-9b7f-54bf36b3a98a).
