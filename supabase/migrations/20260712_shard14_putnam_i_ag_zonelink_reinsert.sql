-- GOLD STANDARD shard-14 (putnam), dispatch b64fc10b-9ce5-494b-8ba6-505d0f19219c, run3885.
-- Putnam letter I: card_complete gap (405/450 = 90.0% FAIL) re-diagnosed live this session.
--
-- Re-derived the exact 45-row gap via pencil_dod_evaluate_county's own I-criterion SQL
-- (pg_get_functiondef): 37 rows fail only the zone-link join (36 real-format parcel_ids + 1
-- scraper-artifact literal parcel_id='Property Appraiser'), 8 rows have parcel_id IS NULL
-- entirely. Of the 36 real-format candidates, re-ran the proven Tax_Parcel_AGO ->
-- Zoning_Districts_AGO centroid-intersect method (identical to prior sessions
-- ae6ab7f9 / shard2_i2, 2026-07-11): 34/36 matched Tax_Parcel_AGO (same 2 absent:
-- 28-10-24-0000-0200-0000, 38-12-26-0000-0040-0002), 22/34 intersected a real zoning
-- polygon -- ALL 22 ZONECLASS='AG' (identical set the 2026-07-11 shard2/i2 session found
-- and had to revert).
--
-- WHY THIS IS SAFE NOW (it regressed letter G when the 2026-07-11 session tried it): a
-- separate, adversarially-verified session (dispatch d820c0b5, gold_standard_ultraloop_audit
-- id=5888, survived=true) inserted zone_standards id=4462 (zoning_district_id=11512,
-- jurisdiction 931, code='AG') with max_density_du_acre=0.10, sourced from the Putnam Comp
-- Plan FLU Element (https://www.putnam-fl.gov/wp-content/uploads/2025/05/Current_PutnamPlan.pdf,
-- Sec.9 Agriculture, PDF p.25/A22, confidence_score=0.55 INFERRED -- Municode zoning-code
-- text itself remains 403-blocked and was NOT independently confirmed, but the Comp Plan FLU
-- figure was verified live against the PDF and survived adversarial review). That row did not
-- exist when the 2026-07-11 session ran, so every AG parcel it linked counted as
-- density-applicable-with-no-data and dragged G's density ratio down (99.3 -> 94.3), forcing a
-- revert. With zone_standards.max_density_du_acre populated for AG, these 22 parcels now
-- count as density-applicable-AND-covered instead.
--
-- VERIFIED live before/after this session (pencil_dod_evaluate_county('putnam')):
--   BEFORE: I pass=false metric=90.0 (card_complete=405 of 450)   G pass=true metric=99.5
--   AFTER:  I pass=false metric=94.9 (card_complete=427 of 450)   G pass=true metric=99.5 (unchanged)
-- I remains FAIL (need >=95% i.e. >=428/450) -- 23 rows genuinely residual: 12 real
-- Tax_Parcel_AGO matches with zero zoning-polygon coverage at their centroid (source-layer
-- gap, includes the 2 known from 2026-07-11), 2 parcel_ids absent from Tax_Parcel_AGO entirely
-- (re-tried live incl. a LIKE-based fuzzy retry this session, still absent), 1 scraper-artifact
-- bad parcel_id ('Property Appraiser', source_url putnam.realforeclose.com detail page is
-- 403-blocked to WebFetch/curl), 8 parcel_id IS NULL rows (already exhaustively investigated
-- against tax_deed_outcomes/foreclosure_outcomes/property_documents/document_extractions by
-- the 2026-07-11 session with zero cross-reference matches; not re-litigated here).
--
-- Idempotent: guarded via NOT EXISTS on parcel_zones.parcel_id, safe to re-run.

INSERT INTO public.parcel_zones (parcel_id, tax_account, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT v.parcel_id, v.parcel_id, 931, v.zone_code, v.zone_name,
       'shard14_run3885/putnam_gis_live:Zoning_Districts_AGO+Tax_Parcel_AGO_centroid_intersect', '2026-07-12'
FROM (VALUES
  ('03-09-24-2600-0370-0010', 'AG', 'Agriculture'),
  ('04-10-25-4077-0210-0080', 'AG', 'Agriculture'),
  ('06-11-23-0000-0220-0370', 'AG', 'Agriculture'),
  ('06-11-26-0000-8888-1056', 'AG', 'Agriculture'),
  ('06-11-26-0000-8888-1083', 'AG', 'Agriculture'),
  ('06-11-26-0000-8888-1127', 'AG', 'Agriculture'),
  ('15-10-23-3930-0040-0100', 'AG', 'Agriculture'),
  ('15-10-23-3930-0040-0110', 'AG', 'Agriculture'),
  ('17-09-27-0000-0100-0010', 'AG', 'Agriculture'),
  ('22-10-26-5470-0050-0010', 'AG', 'Agriculture'),
  ('22-10-26-5470-0070-0100', 'AG', 'Agriculture'),
  ('23-10-23-0000-0450-0000', 'AG', 'Agriculture'),
  ('23-10-23-5300-0010-0340', 'AG', 'Agriculture'),
  ('28-10-26-0000-8888-0575', 'AG', 'Agriculture'),
  ('29-09-26-0000-0030-0000', 'AG', 'Agriculture'),
  ('30-10-24-4074-0930-0030', 'AG', 'Agriculture'),
  ('31-12-26-0000-0025-0030', 'AG', 'Agriculture'),
  ('31-12-28-0000-0590-0020', 'AG', 'Agriculture'),
  ('33-09-25-7600-0100-0010', 'AG', 'Agriculture'),
  ('34-09-25-2702-0030-0380', 'AG', 'Agriculture'),
  ('34-10-23-4520-0060-0030', 'AG', 'Agriculture'),
  ('49-09-27-0220-0030-0081', 'AG', 'Agriculture')
) AS v(parcel_id, zone_code, zone_name)
WHERE NOT EXISTS (
  SELECT 1 FROM public.parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);
