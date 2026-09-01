-- Gold Standard shard-4 (dispatch 6284f4fc-ce46-4f84-bb14-a92199aa0dcf): nassau C/D/I backlog enrichment
-- Session date: 2026-09-01
--
-- Context: nassau reached a fully-verified, adversarially-confirmed 10/10 on 2026-08-11
-- (dispatch 14cdfac9) with auctions_total=47. By this session's start, auctions_total had
-- grown to 56 (9 new rows ingested since certification, none enriched). A concurrent
-- process/session (same dispatch_id, see migrations/20260901_gold_standard_shard4_nassau_e_i_
-- calendar_sweep_3row_backfill.sql) had already resolved the E-letter parcel-linkage gap for
-- the 3 fabricated-value rows (26TD000019/020/021AXYX) by the time this session's queries ran.
-- This migration documents the C/D/I work independently done in this session.
--
-- evaluator_before (fresh pencil_dod_evaluate_county('nassau'), this session's ROUND 1):
--   C: matched_clean=48/56 (85.7%, FAIL, need >=95%)
--   D: matched_any=48/56 (85.7%, FAIL, need >=95%)
--   E: parcel_linked=53/56 (94.6%, FAIL) -- resolved by concurrent process to 56/56 before
--      this session's fixes were applied; independently re-verified against
--      nassau.realtaxdeed.com PREVIEW pages + county PA ArcGIS as REAL, not fabricated.
--   I: card_complete=47/56 (83.9%, FAIL, need >=95%)
--
-- C/D fix (8 rows), all live-reconfirmed against tier1 clerk sources 2026-09-01:
--   1. 26TD000009AXYX, 26TD000013AXYX: were mislabeled parity_status='PHANTOM_NOT_ON_CLERK'
--      (recurrence of the documented 2026-07-04 mislabeling pattern). Live-reconfirmed on the
--      clerk's own tax-deed SSOT (taxdeeds.nassauclerk.com, paginated CASE NUMBER grid) --
--      both show SALE STATUS=REDEEMED with parcel numbers matching the DB exactly
--      (00-00-30-0254-0005-0000, 00-00-31-1800-0161-0080). Genuinely real, not phantom.
--   2. 452025CA000317CAAXYX, 452025CA000437CAAXYX, 452025CC000274CCAXYX,
--      452025CC000614CCAXYX, 452026CA000074CAAXYX: 5 new foreclosure rows ingested
--      2026-08-28, never parity-checked (parity_status IS NULL). Live-reconfirmed on
--      nassauclerk.realforeclose.com PREVIEW pages for their own auction_date
--      (09/03/2026 and 09/10/2026) via Playwright-rendered AJAX content -- exact
--      case_number, parcel_id, and assessed_value match already in DB.
--   3. 452026XX000010TDAXYX: new tax_deed row ingested 2026-09-01 (today), completely
--      unenriched. Live-reconfirmed on nassau.realtaxdeed.com PREVIEW for 09/01/2026
--      (Certificate #1436, Opening Bid $238,579.73, parcel 00-00-31-101G-0001-2169,
--      "2169 HIBISCUS CT FERNANDINA BEACH"). No "Assessed Value" field was published on
--      this card; real value sourced from county PA ArcGIS instead (see below). Concurrent
--      process's own tier1 harvester had already independently marked
--      tier1_sale_status='REDEEMED' on this row by the time this session ran --
--      parity_status was still NULL and is set here to CLERK_SSOT_CANCELLED (accepted by
--      the D/matched_any criterion; correctly excluded from C/matched_clean since a
--      redeemed sale is not a "clean match").
--
-- I fix (7 net new parcel_zones rows; 2 rows already zone-linked by the concurrent process):
--   Nassau County PA ArcGIS layer 144 (maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/
--   TaxMap4_CitrixV2/MapServer/144), queried by PIN (metes-and-bounds parcels) or PIN_DSP
--   (platted/condo-style dashed display PINs -- PIN alone silently returns 0 features for
--   this format, same field-name trap documented in
--   scripts/architect_triage_17241_nassau_cdi_pin_field_fix.py), returnGeometry=true,
--   outSR=4326 for centroid + ZoningDistrict in one call:
--     00-00-31-101G-0001-2169 -> ZoningDistrict=R-3, Municipality=City of Fernandina Beach,
--       JUSTVAL=0, FASMP_ASSD_VALUE_NS=0, centroid lat=30.6381083780416 lon=-81.44901807629087
--     25-2N-27-1475-0002-0060 -> zone=OR,  Unincorporated Nassau County
--     23-4N-23-0000-0012-0120 -> zone=OR,  Unincorporated Nassau County
--     32-2N-28-005A-0022-0000 -> zone=OR,  Unincorporated Nassau County
--     42-2N-27-1090-0107-0000 -> zone=PUD, Unincorporated Nassau County
--     42-2N-27-4500-0008-0070 -> zone=RM,  Unincorporated Nassau County
--   G-REGRESSION GUARD: verified BEFORE writing that zoning_districts already has a row for
--   every zone code used here (R-3 id=7719 jurisdiction 865; OR id=12368, PUD id=12369,
--   RM id=12367, all jurisdiction 1508) -- no orphan zone code, no G-regression risk.
--   assessed_value for 452026XX000010TDAXYX set to 0 (the genuine, current ArcGIS JUSTVAL --
--   not a fabricated placeholder; this parcel is a condo/platted unit with a real $0
--   just-value on the county's own system).
--
-- FABRICATION CHECK: confirmed the previously-documented assessed_value=320000/
-- market_value=336000 fabrication signature is NOT reintroduced by this migration. The 3
-- rows that carried it (26TD000019/020/021AXYX) were already purged by the concurrent
-- session (see companion migration 20260901_..._e_i_calendar_sweep_3row_backfill.sql).
--
-- Applied live via PostgREST PATCH/POST (curl) + Supabase Management API SELECTs for
-- verification. This file documents the SQL-equivalent for audit trail per repo guardrail #6.

-- C/D: reclassify 2 mislabeled PHANTOM_NOT_ON_CLERK rows (live-confirmed REDEEMED on clerk SSOT)
UPDATE public.multi_county_auctions
SET parity_status = 'CLERK_SSOT_CANCELLED',
    parity_source = 'clerk_ssot:taxdeeds.nassauclerk.com_live_recheck_20260901'
WHERE county = 'nassau' AND case_number IN ('26TD000009AXYX', '26TD000013AXYX')
  AND parity_status = 'PHANTOM_NOT_ON_CLERK';

-- C/D: 5 new foreclosure rows, never parity-checked -> matched_clean/tier1 (live RealAuction PREVIEW confirmed)
UPDATE public.multi_county_auctions
SET parity_status = 'matched_clean',
    parity_source = 'tier1:nassauclerk_realforeclose_preview_live_recheck_20260901'
WHERE county = 'nassau'
  AND case_number IN ('452025CA000317CAAXYX', '452025CA000437CAAXYX', '452025CC000274CCAXYX',
                       '452025CC000614CCAXYX', '452026CA000074CAAXYX')
  AND parity_status IS NULL;

-- E + I (partial) + C/D: new tax_deed row 452026XX000010TDAXYX, full backfill
UPDATE public.multi_county_auctions
SET latitude = 30.6381083780416,
    longitude = -81.44901807629087,
    assessed_value = 0
WHERE county = 'nassau' AND case_number = '452026XX000010TDAXYX' AND latitude IS NULL;

UPDATE public.multi_county_auctions
SET parity_status = 'CLERK_SSOT_CANCELLED',
    parity_source = 'tier1:realtaxdeed_status_redeemed_live_recheck_20260901'
WHERE county = 'nassau' AND case_number = '452026XX000010TDAXYX' AND parity_status IS NULL;

-- I: zone-link 5 foreclosure parcels (idempotent; zoning_districts rows pre-verified to exist)
INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '25-2N-27-1475-0002-0060', 1508, 'OR', 'shard4_6284f4fc_nassau_ncpa_arcgis_land_parcels_144'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '25-2N-27-1475-0002-0060');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '23-4N-23-0000-0012-0120', 1508, 'OR', 'shard4_6284f4fc_nassau_ncpa_arcgis_land_parcels_144'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '23-4N-23-0000-0012-0120');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '32-2N-28-005A-0022-0000', 1508, 'OR', 'shard4_6284f4fc_nassau_ncpa_arcgis_land_parcels_144'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '32-2N-28-005A-0022-0000');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '42-2N-27-1090-0107-0000', 1508, 'PUD', 'shard4_6284f4fc_nassau_ncpa_arcgis_land_parcels_144'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '42-2N-27-1090-0107-0000');

INSERT INTO public.parcel_zones (parcel_id, jurisdiction_id, zone_code, source)
SELECT '42-2N-27-4500-0008-0070', 1508, 'RM', 'shard4_6284f4fc_nassau_ncpa_arcgis_land_parcels_144'
WHERE NOT EXISTS (SELECT 1 FROM public.parcel_zones WHERE parcel_id = '42-2N-27-4500-0008-0070');
