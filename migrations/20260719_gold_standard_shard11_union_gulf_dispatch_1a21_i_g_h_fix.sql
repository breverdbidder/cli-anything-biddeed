-- Gold Standard shard-11 (union/gulf), dispatch_id 1a211136-77c7-4125-b70c-06b26ad13ebe
-- 2026-07-19T16:00:00Z session
--
-- Scope: gulf I/G real fix (one Port St Joe parcel, ordinance-cited), gulf H honest
-- freshness refresh (9 rows re-confirmed live today). NO changes to union (8/10,
-- B/F genuinely accrual-blocked — confirmed live, see session report). NO changes
-- to gulf B/F (structurally blocked across 4 independent sessions now incl. this
-- one's fresh CAPTCHA re-confirmation on Gulf County OCRS Turnstile) or gulf C/D/E
-- for the 3 null-parcel cases (same CAPTCHA wall blocks case->parcel lookup).
--
-- Every value below is sourced from a primary document fetched and independently
-- re-derived by an adversarial refuter this session (see
-- public.gold_standard_ultraloop_audit rows inserted below for full evidence).
-- Two candidate zoning claims (05004050R -> R-1, 06248-410R -> outside PSJ) were
-- REFUTED by the adversarial pass and are deliberately NOT written here.

BEGIN;

-- ── G/I: real Port St Joe R-1 district, ordinance-cited ──────────────────────
-- Source: City of Port St Joe Land Development Regulation Code (adopted ~2008-10-09,
-- https://www.cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf), Sec. 3.03 "District R-1".
-- Parcel-to-district link verified against the City's official Zoning Map
-- (Sep 26, 2012, https://www.cityofportstjoe.com/pdf/maps/City%20Zoning%20Map%20September%2026,%202012%20(ZONING_2010-120926-V9).pdf)
-- by an independent adversarial refuter who re-extracted the PDF's text/vector
-- layers from scratch and confirmed the ROYAL ST label sits inside the R-1 polygon.
INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_section)
VALUES (
  952, 'R-1', 'R-1 Residential District', 'Residential',
  'City of Port St Joe R-1 residential district (LDR Sec. 3.03): single-family dwellings; ' ||
  'max height 35ft (Sec.3.03(6)); max lot coverage 40% (Sec.3.03(14)); density no more than ' ||
  '5 dwelling units/acre (Sec.3.03(12)); front yard >=25ft (Sec.3.03(8)); rear yard >=25ft ' ||
  '(Sec.3.03(10)); side yard is lot-width-conditional (15ft if lot width>=100ft, 10ft if ' ||
  '50-100ft, 7ft if <=50ft per Sec.3.03(9)) and therefore NOT written as a single scalar here. ' ||
  'LDR adopted ~2008-10-09 (PDF metadata "Final Adopted LDRs 100908").',
  'Sec. 3.03(6),(8),(9),(10),(12),(14)'
)
ON CONFLICT DO NOTHING;

INSERT INTO zone_standards (
  zoning_district_id, max_height_ft, front_setback_ft, rear_setback_ft,
  max_lot_coverage_pct, max_density_du_acre, parking_per_unit,
  source_url, ordinance_section, confidence_score
)
SELECT
  d.id, 35.0, 25.0, 25.0, 40.0, 5.0, 2.0,
  'https://www.cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf (City of Port St Joe LDR, Sec. 3.03 ' ||
  'District R-1: height Sec.3.03(6); front/rear setback Sec.3.03(8)/(10); lot coverage ' ||
  'Sec.3.03(14); density Sec.3.03(12); parking Sec.5.08(a) "Residential (single-family or ' ||
  'duplex): Two spaces per dwelling unit"). max_far and parking_per_1000sf intentionally NULL ' ||
  '-- this LDR does not regulate FAR or parking-per-1000sf for residential districts, only ' ||
  'lot coverage % and parking-per-unit.',
  'Sec. 3.03(6),(8),(10),(12),(14); Sec. 5.08(a)',
  0.85
FROM zoning_districts d
WHERE d.jurisdiction_id = 952 AND d.code = 'R-1'
ON CONFLICT DO NOTHING;

-- Parcel link: 06051-008R / case 232024CA000042CAAXMX / "114 Royal St, Port St Joe".
-- Zoning claim independently re-derived and CONFIRMED by adversarial refuter (see audit row).
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT '06051-008R', '06051-008R', 952, 'R-1', 'R-1 Residential District',
       'shard11_union_gulf_dispatch1a21_20260719_psj_ldr_map_adversarially_verified'
WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '06051-008R');

-- ── H: honest freshness refresh ───────────────────────────────────────────────
-- Re-fetched https://www.gulfclerk.com/courts/tax-deeds/ live today (2026-07-19) and
-- confirmed these 9 case numbers are still listed on the Clerk's current tax-deed
-- docket. Only these 9 rows are touched -- the 5 foreclosure-type cases were NOT
-- re-confirmed this session (Foreclosures Archive page returned no matches; the
-- live active-foreclosure listing page was not reached) and are deliberately left
-- with their prior last_seen_at.
UPDATE multi_county_auctions
SET last_seen_at = now()
WHERE county = 'gulf'
  AND case_number IN ('2025-023','2025-017','2025-001','2025-003','2025-011','2025-010','2025-022','2025-021','2025-018');

-- ── Adversarial audit log (CERTIFY GATE evidence, gold_standard_ultraloop_audit) ─
INSERT INTO gold_standard_ultraloop_audit (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES
  ('1a211136-77c7-4125-b70c-06b26ad13ebe', 'native', 'gulf', 'G',
   'Parcel 06051-008R (114 Royal St, case 232024CA000042CAAXMX) is zoned R-1 per City of Port St Joe LDR Sec. 3.03 / Zoning Map Sep 2012.',
   jsonb_build_object('survived', true, 'method', 'independent PDF re-extraction (PyMuPDF, text+vector layers) + high-res visual crop', 'note', 'coordinate-convention mismatch and yellow-fill-color reasoning both independently checked and resolved; R-1 label confirmed in-polygon at Royal St'),
   true),
  ('1a211136-77c7-4125-b70c-06b26ad13ebe', 'native', 'gulf', 'I',
   '06051-008R card completeness follows from the G fix above (address+geo+value already present; zoned parcel now added).',
   jsonb_build_object('survived', true, 'method', 'derived from G verdict, no independent card-specific re-check needed beyond the zoning link'),
   true),
  ('1a211136-77c7-4125-b70c-06b26ad13ebe', 'native', 'gulf', 'G',
   'REFUTED (not written): 05004050R (Knowles Ave) is zoned R-1.',
   jsonb_build_object('survived', false, 'independently_confirmed_value', 'VLR, not R-1', 'method', 'independent PDF re-extraction found Knowles Ave label sits in a VLR-labeled strip, not the R-1 polygon the original claim cited'),
   false),
  ('1a211136-77c7-4125-b70c-06b26ad13ebe', 'native', 'gulf', 'E',
   'REFUTED (not written): 06248-410R (112 Shallow Reed Dr) is outside Port St Joe city limits / unincorporated Gulf County.',
   jsonb_build_object('survived', false, 'method', 'independently fetched the cited source_url; it describes a different MLS listing/parcel and does not support the jurisdiction claim'),
   false),
  ('1a211136-77c7-4125-b70c-06b26ad13ebe', 'native', 'gulf', 'I',
   'Parcels 00469000R (case 2025-023) and 03426604R (case 2025-017) have NO street address on record anywhere -- confirmed VERIFIED via live FL DOR Statewide Cadastral FeatureServer (PHY_ADDR1=N/A) and live gulfclerk.com tax-deed docket (co-located legal description, case, certificate, owner match).',
   jsonb_build_object('survived', true, 'method', 'independent re-fetch of both cited primary sources from scratch', 'conclusion', 'genuinely blocked -- no address exists to fill in, not a data gap'),
   true);

COMMIT;
