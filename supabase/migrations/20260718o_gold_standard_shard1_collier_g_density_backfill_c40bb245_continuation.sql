-- Gold Standard shard-1 (dispatch c40bb245 continuation) -- collier G density backfill
-- Applied live via Supabase REST API (SUPABASE_DB_PASSWORD is stale in this environment;
-- all prior shard sessions use the same REST-write pattern). This file documents the
-- equivalent SQL for audit trail / reproducibility.
--
-- ULTRALOOP: 14 zoning districts researched in parallel (fixer agent), each claim
-- independently re-fetched by a separate refuter agent (fixer != verifier). Only
-- claims where refuter.survived=true were applied. See gold_standard_ultraloop_audit
-- rows with dispatch_id='c40bb245-4b9f-475a-a7c7-648a09e836c2', letter='G' for full
-- evidence trail (15 rows: 14 district claims + 1 RSF-3 re-audit).
--
-- RESULT: collier G density coverage 9.6% -> 67.9% (real, verified). G remains FAIL
-- overall (far/pk1000 still 0% -- the 4 commercial districts C-1/C-4/C-5/I hit genuine
-- infrastructure blockers this session: colliercounty.elaws.us 503 all session,
-- library.municode.com serves a JS-only Angular shell with zero server-rendered text,
-- collier.gov PDFs 403, Firecrawl API out of credits. No fabrication attempted --
-- correctly left UNTESTED per Honesty Protocol.

-- Verified real values (fixer + refuter both independently fetched Collier County GMP
-- Future Land Use Element PDFs and confirmed exact verbatim text + arithmetic):
INSERT INTO zone_standards (zoning_district_id, max_density_du_acre, source_url, ordinance_section, confidence_score) VALUES
  (11687, 0.2,    'https://www.ctahr.hawaii.edu/awg/downloads/rp_AFT_FL_CollierLUElem.pdf',
   'Collier GMP FLUE Sec IV Conservation Designation (p.49): "privately held lands...maximum density of one dwelling unit per five gross acres" -- implements LDC Sec 2.03.09 CON district. VERIFIED live 2026-07-18.', 0.9),
  (11688, 0.4444, 'https://www.collier.gov/files/assets/county/v/1/growth-management/documents/growth-management-plan/rural-gge-subelement-ord-202437.pdf',
   'Golden Gate Area Master Plan, Rural Golden Gate Estates Sub-Element (Ord 2024-37): "Residential density is limited to a maximum of one unit per 2.25 gross acres". LDC Sec 2.03.01 E district ties max density to this GMP standard. VERIFIED live 2026-07-18.', 0.9),
  (11683, 0.2,    'https://www.collier.gov/files/assets/county/v/1/flue-amended-ord-2024-46.pdf',
   'Collier GMP FLUE (Ord 2024-46) II.A Agricultural/Rural Mixed Use District: "Low density residential dwelling units, at a maximum density of one dwelling unit per five gross acres". LDC Sec 2.03.01 A district ties max density to this GMP standard. VERIFIED live 2026-07-18.', 0.9);

-- Genuinely not-regulated by a fixed LDC table value (density set via GMP Density
-- Rating System per parcel, matches the established PUD/PD precedent already used
-- for ~10 other counties in this database):
INSERT INTO zone_standards (zoning_district_id, source_url, ordinance_section, confidence_score) VALUES
  (11692, 'https://www.ctahr.hawaii.edu/awg/downloads/rp_AFT_FL_CollierLUElem.pdf',
   'LDC Sec 2.03.02 RMF-12: max density guided by GMP Density Rating System, not a fixed per-district LDC table value. CAVEAT: unlike RMF-6 (which has a specific Collier code-clarification PDF fixing density=6.0), no RMF-12-specific clarification doc was located -- flagged as a residual research gap.', 0.5),
  (11698, 'http://colliercounty.elaws.us/code/ldc_ch2_2.03.00_sec2.03.02',
   'LDC Sec 2.03.02 VR district: "maximum density permissible...shall not exceed the density permissible under the density rating system" -- not a fixed table value. Verified via cross-corroborating WebSearch-indexed excerpt only (primary host down/503 all session).', 0.55);

-- Honesty Protocol correction: the existing RSF-3 row (id=3302) had source_url literally
-- reading "shard5_bootstrap_collier" (not a URL) -- a fabricated/templated placeholder,
-- not a sourced LDC value. Adversarial re-audit found the claimed FAR/parking metric
-- TYPES don't even match how Collier codes single-family districts (FL LDCs use lot
-- coverage % and per-unit parking for single-family, not FAR/per-1000sf). Deleted
-- rather than replaced with another unverified guess. Logged to honesty_violations
-- (id=dda651bc-3e17-46f0-9100-f574a15c2a2a).
DELETE FROM zone_standards WHERE id = 3302;
