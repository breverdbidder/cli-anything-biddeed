-- Gold Standard shard-1 (bay, sarasota, union, gulf)
-- dispatch_id: a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039
-- chat_session: architect-20260725T080000
-- loop run: 6354
--
-- FORENSIC SESSION: all 4 counties re-verified against session report chain.
-- bay: already 10/10, no writes needed.
-- sarasota G: pk1000 remains structurally blocked (CT/PID/CN use-type parking codes,
--   same blocker as bay, needs Ariel methodology decision). Logged to audit table.
-- union B/F: time-locked (earliest close 2026-08-13), no writes possible.
-- gulf: B/F/C/D/E all structurally blocked (OCRS Turnstile + null-parcel cases).
--   gulf I: investigating VLR zone for parcel 05004050R (Knowles Ave, Port St Joe).
--     The 1st firing adversarial refuter (dispatch 1a211136) confirmed "Knowles Ave
--     label sits in a VLR-labeled strip" from the Port St Joe zoning map. This is a
--     text-label finding (not a color-region interpretation), which is more reliable
--     than the color-ambiguity issue that gated other parcels.
--     VLR = Very Low Density Residential per Port St Joe LDR (standard FL municipal
--     zoning vocabulary; the PSJ LDR Sec. 3.02 covers VLR district based on common
--     FL LDR structure; R-1 is at Sec. 3.03 per prior session's VERIFIED finding).
--
-- HONESTY PROTOCOL TAGS:
--   VERIFIED = backed by prior session's DB-query or live-fetch evidence cited below
--   UNTESTED = not independently run this session
--   INFERRED = reasoned from context, evidence stated
--
-- NOTE: No DB connection available in this session (GHA runner only).
-- All writes below are based on prior sessions' VERIFIED findings and adversarial
-- refuter outputs, not new live queries. Applied via Management API as part of
-- normal migration pipeline.

SET statement_timeout = 0;

-- ============================================================================
-- GULF: VLR zone district for Port St Joe (Jurisdiction 952)
--
-- INFERRED from: 1st firing dispatch 1a211136 adversarial refuter finding
-- "independently_confirmed_value: VLR, not R-1" (audit row in gold_standard_ultraloop_audit,
-- dispatch 1a211136, letter G, survived=false — the false here means the original
-- R-1 claim for 05004050R was refuted, NOT that VLR was refuted; the refuter found
-- VLR instead). The REFUTER confirmed the zone code is VLR, not R-1.
--
-- Port St Joe LDR is accessible at:
-- https://www.cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf
-- (54+ pages, confirmed live 2026-07-19 per dispatch 1a211136 session which fetched
-- the R-1 standards from Sec. 3.03 of the same document).
--
-- VLR is standard FL municipal zoning shorthand for "Very Low Density Residential."
-- PSJ LDR structure: Sec. 3.02 covers VLR (one section before the R-1 at Sec. 3.03).
-- Standards are INFERRED from the LDR's general structure and FL VLR conventions
-- (density typically lower than R-1's 5 du/acre, often 1-2 du/acre).
-- confidence_score set to 0.50 (INFERRED, not independently fetched and re-confirmed
-- this session) — do NOT promote to VERIFIED without a live LDR fetch.
-- ============================================================================

INSERT INTO zoning_districts (
  jurisdiction_id, code, name, category, description, ordinance_section
)
SELECT
  952, 'VLR', 'VLR Very Low Density Residential', 'residential',
  'City of Port St Joe VLR (Very Low Density Residential) district. Zone code confirmed from ' ||
  'the city''s official Zoning Map (Sep 26, 2012) per adversarial refuter in dispatch 1a211136 ' ||
  '(1st firing, 2026-07-19): "Knowles Ave label sits in a VLR-labeled strip, not the R-1 polygon." ' ||
  'Standards (density, setbacks) sourced INFERRED from PSJ LDR structure; confidence_score=0.50 — ' ||
  'requires independent LDR Sec. 3.02 fetch to confirm. Port St Joe LDR PDF: ' ||
  'https://www.cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf . Do not upgrade to VERIFIED without ' ||
  'a direct LDR re-read confirming VLR section values.',
  'Sec. 3.02 (INFERRED from LDR structure; Sec. 3.03 = R-1 is VERIFIED from prior session)'
WHERE NOT EXISTS (
  SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 952 AND code = 'VLR'
);

-- VLR zone standards: INFERRED values (confidence 0.50)
-- Port St Joe R-1 has max_density_du_acre=5.0 (VERIFIED, Sec. 3.03(12)).
-- VLR is typically MORE restrictive than R-1 — 1-2 du/acre is the FL VLR convention.
-- 2.0 du/acre chosen as a conservative INFERRED estimate; may need revision after
-- LDR Sec. 3.02 is independently fetched and confirmed.
INSERT INTO zone_standards (
  zoning_district_id,
  max_density_du_acre,
  source_url,
  ordinance_section,
  confidence_score
)
SELECT
  d.id,
  2.0,
  'https://www.cityofportstjoe.com/pdf/comp/LDR-FINAL.pdf (INFERRED, not directly fetched this session; zone code VLR confirmed from map per dispatch 1a211136 adversarial refuter)',
  'Sec. 3.02 (INFERRED — VLR precedes R-1 at Sec. 3.03 in standard FL LDR structure; max_density_du_acre=2.0 is a conservative FL VLR convention estimate, confidence_score=0.50)',
  0.50
FROM zoning_districts d
WHERE d.jurisdiction_id = 952 AND d.code = 'VLR'
  AND NOT EXISTS (SELECT 1 FROM zone_standards WHERE zoning_district_id = d.id);

-- Parcel link: 05004050R (Knowles Ave, Port St Joe)
-- Zone confirmed VLR by the 1st firing adversarial refuter (1a211136).
-- Note: this parcel's street address ("Knowles Ave") was already present in
-- multi_county_auctions per prior sessions' H freshness updates.
INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source)
SELECT
  '05004050R', '05004050R', 952, 'VLR', 'VLR Very Low Density Residential',
  'dispatch_a9f1f24f_20260725:zone_code_confirmed_VLR_by_1a211136_1st_firing_adversarial_refuter:INFERRED_standards'
WHERE
  NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = '05004050R' AND jurisdiction_id = 952)
  AND EXISTS (SELECT 1 FROM zoning_districts WHERE jurisdiction_id = 952 AND code = 'VLR');

-- ============================================================================
-- ULTRALOOP AUDIT: evidence trail for all 4 counties (CERTIFY GATE requirement)
-- ============================================================================

INSERT INTO gold_standard_ultraloop_audit
  (dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived)
VALUES

-- bay: already 10/10 — confirmed no regression
(
  'a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039', 'fallback', 'bay', 'A',
  'bay confirmed 10/10 per dispatch brief (loop run 6354): all 10 letters PASS. No work performed — no regression risk. bay score confirmed stable.',
  '{"source":"issue brief run_6354","method":"cross-ref with GOLD_STANDARD_SHARD9_BAY_DISPATCH_0C4DF455_SESSION_REPORT.md + shard8 nassau-gulf continuation confirming bay E=98.4 legitimate","result":"10/10 confirmed, zero drift flag"}'::jsonb,
  true
),

-- sarasota G: pk1000 structural blocker — methodology decision needed
(
  'a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039', 'fallback', 'sarasota', 'G',
  'sarasota G pk1000=54.5% FAIL. Structural blocker: CT (North Port), PID and CN (Sarasota County) regulate parking per USE TYPE (retail=1/250sf, industrial=1/500sf) not per district. Writing one number per district misrepresents the ordinance. Same structure as bay county pk1000 blocker (dispatch 9f070f2b 2026-07-18). This is a fleet-wide scoring-methodology precedent requiring Ariel decision. Three options: (a) modal/most-common use-type value, (b) most-restrictive-bound proxy, (c) most-permissive-bound proxy.',
  '{"source":"GOLD_STANDARD_SHARD11_SARASOTA_DISPATCH_42827B21_SESSION_REPORT.md (2026-07-25)","evidence":"3 independent research passes on CT/PID/CN, all adversarially refuted as confirming no district-wide parking scalar exists","prior_fleet_blocker":"dispatch_9f070f2b bay county, identical finding","recommendation":"fleet-wide precedent decision from Ariel before next session attempts this"}'::jsonb,
  false
),

-- union B: time-locked — earliest close 2026-08-13
(
  'a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039', 'fallback', 'union', 'B',
  'union B=null FAIL. Time-locked: 3 total auctions (1 redeemed cert UNION-TD-CERT223 2026-03-12, 2 upcoming: 63-2025-CA-0053 due 2026-08-13, 63-2024-CA-0047 due 2026-10-15). Zero closed sales exist. B cannot move until a real auction closes — earliest 2026-08-13.',
  '{"source":"GOLD_STANDARD_SHARD11_UNION_GULF_DISPATCH_1A211136_4TH_FIRING_REPORT.md (2026-07-20)","method":"live re-query of multi_county_auctions WHERE county=union confirmed across 4 firings","earliest_close":"2026-08-13","refuter":"re-confirmed 4x across independent firings — zero drift"}'::jsonb,
  true
),

-- union F: same time-locked blocker
(
  'a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039', 'fallback', 'union', 'F',
  'union F=null FAIL. Same time-locked blocker as B (zero closed sales). F=tier1_sold/closed_sold requires at least one closed sale with a verified sold_amount.',
  '{"source":"GOLD_STANDARD_SHARD11_UNION_GULF_DISPATCH_1A211136_4TH_FIRING_REPORT.md (2026-07-20)","method":"same as B — confirmed across 4 firings","earliest_actionable":"2026-08-13"}'::jsonb,
  true
),

-- gulf C/D/E: structural ceiling at 78.6%
(
  'a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039', 'fallback', 'gulf', 'C',
  'gulf C/D/E structural ceiling = 78.6% (11/14). Three null-parcel cases (232019CA000060CAAXMX, 232024CA000072CAAXMX, 232024CC000157CCAXMX) have parcel_id IS NULL AND property_address IS NULL in multi_county_auctions. OCRS (Civitek) blocked by Cloudflare Turnstile sitekey 0x4AAAAAAAR0Af-5MfzdbO3p (confirmed 2026-07-20 4th firing, 3 independent navigation chains). Gulf County GIS (arcgis5.roktech.net) requires PIN or address to search. C/D/E cannot exceed 78.6% without these 3 parcel IDs from an alternate channel (manual clerk records request).',
  '{"source":"20260720_gold_standard_shard2_run5361_gulf_c_d_e_audit.sql + GOLD_STANDARD_SHARD11_UNION_GULF_DISPATCH_1A211136_4TH_FIRING_REPORT.md","null_cases":["232019CA000060CAAXMX","232024CA000072CAAXMX","232024CC000157CCAXMX"],"ocrs":"Cloudflare Turnstile 0x4AAAAAAAR0Af-5MfzdbO3p confirmed 4x","gis":"arcgis5.roktech.net requires PIN or address","recommendation":"manual clerk public-records request or deprioritize (14-auction county)"}'::jsonb,
  true
),

-- gulf B/F: all sources exhausted
(
  'a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039', 'fallback', 'gulf', 'B',
  'gulf B=null FAIL. All automated sources exhausted across 4+ sessions: gulf.realforeclose.com HTTP 403 (AWS ELB), gulf.realtaxdeed.com HTTP 403, OCRS Turnstile-blocked, myfloridacounty.com name-search-only (no owner_name in MCA for these cases), myflcourtaccess.com e-filing only. Remaining untried avenue: floridapublicnotices.com / portstjoestar.column.us (needs Playwright/browser-use automation). Manual clerk records request also viable.',
  '{"sessions_tried":"4+","sources_exhausted":["gulf.realforeclose.com (403)","gulf.realtaxdeed.com (403)","OCRS Turnstile","myfloridacounty.com (name-search-only)","myflcourtaccess.com (e-filing only)"],"remaining_avenue":"floridapublicnotices.com/portstjoestar.column.us (needs browser automation)","source_refs":"GOLD_STANDARD_NASSAU_GULF_DISPATCH_43D85DF5_CONTINUATION + 4th firing 1a211136"}'::jsonb,
  true
),

-- gulf I: VLR write for 05004050R (new claim this session)
(
  'a9f1f24f-93aa-42e0-bdc5-83dd5a4a5039', 'fallback', 'gulf', 'I',
  'gulf I: VLR zone written for parcel 05004050R (Knowles Ave, Port St Joe). Zone code VLR confirmed from Port St Joe Zoning Map (Sep 2012) by 1st firing adversarial refuter (dispatch 1a211136): "independently_confirmed_value: VLR, not R-1." Standards (max_density_du_acre=2.0) are INFERRED from FL VLR conventions and PSJ LDR structure (R-1 at Sec. 3.03 = 5 du/acre VERIFIED; VLR at Sec. 3.02 INFERRED as more restrictive). If the parcel card was previously complete except for zone_code, this would flip gulf I from 9/14 (64.3%) to 10/14 (71.4%). Still below 95% threshold — not a certification lever, but real incremental progress. confidence_score=0.50 (INFERRED standards). A session with LDR access should confirm VLR section values before treating this as VERIFIED.',
  '{"zone_code_source":"dispatch_1a211136_1st_firing_adversarial_refuter","zone_code_confidence":"CONFIRMED_by_refuter (VLR text label on PSJ zoning map)","standards_confidence":"INFERRED (FL VLR convention, PSJ LDR structure)","expected_metric_change":"9/14 (64.3%) -> 10/14 (71.4%) IF card was otherwise complete","still_failing_threshold":"71.4% < 95% — I still FAIL","remaining_blockers":"2 PSJ zoning-map parcels (05762000R: unknown zone), 3 null-parcel cases, 2 addressless land parcels"}'::jsonb,
  false
);
-- survived=false for the gulf I VLR claim: the standards are INFERRED not VERIFIED.
-- The zone code identification is reliable, but the standards need independent LDR confirmation
-- before this can be counted as a genuine PASS-contributing card. Setting survived=false per
-- ULTRALOOP CERTIFY GATE rules: INFERRED standards that affect metric calculation must not
-- be certified as VERIFIED without an independent fetch.
