-- Gold Standard shard-12 (glades) — G fix: real zoning density backfill
--
-- dispatch_id: 68e27f69-a691-497f-b65e-c222c619ed8a
--
-- ROOT CAUSE (CONFIRMED live 2026-07-12): G regressed from a prior-session 100.0 PASS to
-- density=3.0 FAIL after legitimate, unrelated E/I work (real GIS parcel-zone linkage,
-- shard8 run3713) added 65 real glades parcels across 7 zoning districts (AR, OUA, RG,
-- RM, RS in unincorporated Glades County; R1, R2 in the City of Moore Haven) to
-- parcel_zones. Only zoning_districts.id=10685 (a shard9-synthetic "R-1" stub covering
-- just the 2 SYN-GLD-* placeholder parcels) had a zone_standards row. The 100.0 PASS was
-- therefore itself a ghost-success artifact of a 2-parcel synthetic denominator; the real
-- 65-parcel substrate was never backfilled. This migration backfills it with real,
-- adversarially-verified ordinance data — it does not touch the pre-existing synthetic
-- row (out of scope for this session; flagged as residual).
--
-- RESEARCH + ADVERSARIAL VERIFICATION (ULTRALOOP workflow, run wf_ceb2266f-476, this
-- session): 7 independent research agents (one per zoning district) + 1 independent
-- refuter agent per finding that reported a number, each refuter re-fetching the primary
-- source PDF itself (not trusting the researcher's read) and checking for dead links,
-- misquotes, wrong-row misattribution, and secondary-aggregator contamination.
--
-- RG, RM, RS, R1, R2: all 5 SURVIVED adversarial verification (refuted=false) against
-- live primary-source PDFs (Glades County BOCC agenda packets on cms2.revize.com for the
-- unincorporated county zones; moorehaven.org's own hosted Chapter 125/Ch.4 LDC PDFs for
-- Moore Haven). VERIFIED confidence.
--
-- AR: the primary source (Glades County Code Sec. 125-158, "Minimum Standards for
-- Principal Permitted Uses" table) shows a BLANK "Buildable Units/Acre" cell for the AR
-- row, alongside an explicit 5-acre minimum parcel area — the same "blank density cell +
-- explicit minimum lot size" pattern already established for st_johns RS-3
-- (20260711_shard11_st_johns_g_density_na_rs3_sab.sql). Per that precedent, this is
-- density NOT regulated by a du/acre figure, not a missing data point — density_regulated
-- is set false and the verified lot-area/setback/height/coverage standards are recorded
-- instead of fabricating a derived "0.2 du/acre" number.
--
-- OUA: genuinely could not locate primary-source evidence this session — Municode
-- returned HTTP 403 (Cloudflare-gated), gladesclerk elaws mirror returned HTTP 503 on 6+
-- retries, and Firecrawl escalation returned HTTP 402 (no credits). Left UNTOUCHED
-- (BLANK > WRONG) — see session report residual. Does not block G: even with OUA's 2
-- parcels still counted as applicable-and-unfilled, the metric clears the 95% threshold
-- (see arithmetic below).
--
-- EXPECTED ARITHMETIC (live parcel_zones distribution, VERIFIED via REST count 2026-07-12):
--   zone_code counts among glades' 67 parcel_zones rows: RS=30 RM=11 RG=10 AR=7 R2=4
--   OUA=2 R-1(synthetic)=2 R1=1
--   After AR (7) excluded via density_regulated=false: applicable denominator = 60
--   Filled: R-1 synthetic(2, pre-existing) + RG(10) + RM(11) + RS(30) + R2(4) + R1(1) = 58
--   58 / 60 = 96.7% >= 95% threshold -> PASS (OUA's 2 unfilled parcels remain a real,
--   honestly-reported gap but do not block certification at this ratio).
--
-- HONESTY PROTOCOL: RG/RM/RS/R1/R2 max_density_du_acre values are VERIFIED (adversarially
-- re-derived from live primary-source documents by an independent refuter agent). AR's
-- density_regulated=false + lot/setback standards are VERIFIED (the blank-cell/5-acre-
-- minimum table row itself, independently re-confirmed). No number in this migration was
-- derived/inferred and presented as a fact-in-database; the one candidate derived number
-- (AR "0.2 du/acre") was deliberately NOT written, per the st_johns precedent and BLANK >
-- WRONG.

SET statement_timeout = 0;

-- ═══════════════════════════════════════════════════════════════════════
-- AR (Agricultural Residential, unincorporated Glades, jurisdiction 1153,
-- zoning_districts.id=11767) — density NOT du/acre-regulated (5-acre min
-- lot size instead), per Sec. 125-158 table, blank Buildable Units/Acre
-- cell. Verified via cms2.revize.com BOCC agenda PDF (Apr 14 2020),
-- adversarially re-confirmed via direct PDF render (page 8 table image).
-- ═══════════════════════════════════════════════════════════════════════
UPDATE public.zoning_districts
SET density_regulated = false
WHERE id = 11767 AND code = 'AR';

INSERT INTO public.zone_standards
  (zoning_district_id, min_lot_sqft, min_lot_width_ft, front_setback_ft,
   rear_setback_ft, side_setback_ft, max_height_ft, max_lot_coverage_pct,
   source_url, ordinance_section, confidence_score, effective_date)
VALUES
  (11767, 217800, 220, 35, 25, 25, 35, 10.0,
   'http://cms2.revize.com/revize/gladescounty/2020_Agendas/2020_Agendas/14_April_2020_Agenda/2.%20Revisions%20to%20Chapter%20125-%20Land%20Development%20Regulations,%20Section%20125-9.pdf',
   'Glades County Code of Ordinances, Ch. 125, Art. IV, Sec. 125-158 (Minimum Standards for Principal Permitted Uses table, AR row)',
   0.85, '2020-04-14')
ON CONFLICT (zoning_district_id) DO UPDATE SET
   min_lot_sqft = EXCLUDED.min_lot_sqft,
   min_lot_width_ft = EXCLUDED.min_lot_width_ft,
   front_setback_ft = EXCLUDED.front_setback_ft,
   rear_setback_ft = EXCLUDED.rear_setback_ft,
   side_setback_ft = EXCLUDED.side_setback_ft,
   max_height_ft = EXCLUDED.max_height_ft,
   max_lot_coverage_pct = EXCLUDED.max_lot_coverage_pct,
   source_url = EXCLUDED.source_url,
   ordinance_section = EXCLUDED.ordinance_section,
   confidence_score = EXCLUDED.confidence_score,
   effective_date = EXCLUDED.effective_date;

-- ═══════════════════════════════════════════════════════════════════════
-- RG (Residential General, unincorporated Glades, jurisdiction 1153,
-- zoning_districts.id=11769) — max_density_du_acre=10.9 (Multifamily row,
-- the district's highest-density permitted use). Cross-corroborated by
-- TWO independent primary docs (ordinance table + Aug 2020 staff report
-- restating "10.9 unit per acre for multi-family").
-- ═══════════════════════════════════════════════════════════════════════
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section,
   confidence_score, effective_date)
VALUES
  (11769, 10.9,
   'http://cms2.revize.com/revize/gladescounty/2020_Agendas/2020_Agendas/14_April_2020_Agenda/2.%20Revisions%20to%20Chapter%20125-%20Land%20Development%20Regulations,%20Section%20125-9.pdf',
   'Glades County Code of Ordinances, Ch. 125, Art. IV, Sec. 125-158 (Minimum Standards for Principal Permitted Uses table, RG Multifamily row)',
   0.95, '2020-04-14')
ON CONFLICT (zoning_district_id) DO UPDATE SET
   max_density_du_acre = EXCLUDED.max_density_du_acre,
   source_url = EXCLUDED.source_url,
   ordinance_section = EXCLUDED.ordinance_section,
   confidence_score = EXCLUDED.confidence_score,
   effective_date = EXCLUDED.effective_date;

-- ═══════════════════════════════════════════════════════════════════════
-- RM (Residential Mixed, unincorporated Glades, jurisdiction 1153,
-- zoning_districts.id=11770) — max_density_du_acre=4.35 (Single-family /
-- Mobile Home sub-rows; Duplex/Multifamily sub-rows shown struck through
-- in the 2020 amendment, i.e. removed from RM's permitted density options).
-- ═══════════════════════════════════════════════════════════════════════
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft,
   front_setback_ft, side_setback_ft, rear_setback_ft, max_height_ft,
   max_lot_coverage_pct, source_url, ordinance_section, confidence_score,
   effective_date)
VALUES
  (11770, 4.35, 10000, 80, 25, 7, 10, 35, 75.0,
   'http://cms2.revize.com/revize/gladescounty/2020_Agendas/2020_Agendas/14_April_2020_Agenda/2.%20Revisions%20to%20Chapter%20125-%20Land%20Development%20Regulations,%20Section%20125-9.pdf',
   'Glades County Code of Ordinances, Ch. 125, Art. IV, Sec. 125-158 (Minimum Standards for Principal Permitted Uses table, RM Single-family/Mobile Home rows)',
   0.9, '2020-04-14')
ON CONFLICT (zoning_district_id) DO UPDATE SET
   max_density_du_acre = EXCLUDED.max_density_du_acre,
   min_lot_sqft = EXCLUDED.min_lot_sqft,
   min_lot_width_ft = EXCLUDED.min_lot_width_ft,
   front_setback_ft = EXCLUDED.front_setback_ft,
   side_setback_ft = EXCLUDED.side_setback_ft,
   rear_setback_ft = EXCLUDED.rear_setback_ft,
   max_height_ft = EXCLUDED.max_height_ft,
   max_lot_coverage_pct = EXCLUDED.max_lot_coverage_pct,
   source_url = EXCLUDED.source_url,
   ordinance_section = EXCLUDED.ordinance_section,
   confidence_score = EXCLUDED.confidence_score,
   effective_date = EXCLUDED.effective_date;

-- ═══════════════════════════════════════════════════════════════════════
-- RS (Residential Single-family, unincorporated Glades, jurisdiction 1153,
-- zoning_districts.id=11771) — max_density_du_acre=4.5.
-- ═══════════════════════════════════════════════════════════════════════
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, min_lot_sqft, min_lot_width_ft,
   front_setback_ft, rear_setback_ft, side_setback_ft, max_height_ft,
   max_lot_coverage_pct, source_url, ordinance_section, confidence_score,
   effective_date)
VALUES
  (11771, 4.5, 10000, 80, 25, 10, 7, 35, 40.0,
   'http://cms2.revize.com/revize/gladescounty/2020_Agendas/2020_Agendas/14_April_2020_Agenda/2.%20Revisions%20to%20Chapter%20125-%20Land%20Development%20Regulations,%20Section%20125-9.pdf',
   'Glades County Code of Ordinances, Ch. 125, Art. IV, Sec. 125-158 (Minimum Standards for Principal Permitted Uses table, RS row)',
   0.95, '2020-04-14')
ON CONFLICT (zoning_district_id) DO UPDATE SET
   max_density_du_acre = EXCLUDED.max_density_du_acre,
   min_lot_sqft = EXCLUDED.min_lot_sqft,
   min_lot_width_ft = EXCLUDED.min_lot_width_ft,
   front_setback_ft = EXCLUDED.front_setback_ft,
   rear_setback_ft = EXCLUDED.rear_setback_ft,
   side_setback_ft = EXCLUDED.side_setback_ft,
   max_height_ft = EXCLUDED.max_height_ft,
   max_lot_coverage_pct = EXCLUDED.max_lot_coverage_pct,
   source_url = EXCLUDED.source_url,
   ordinance_section = EXCLUDED.ordinance_section,
   confidence_score = EXCLUDED.confidence_score,
   effective_date = EXCLUDED.effective_date;

-- ═══════════════════════════════════════════════════════════════════════
-- R1 (Low Density Residential, City of Moore Haven, jurisdiction 899,
-- zoning_districts.id=11765) — max_density_du_acre=4.0. Sec. 125-48,
-- narrative text "density of up to four dwelling units per gross acre",
-- cross-confirmed via Min Gross Land Area/D.U.=10,890 sf (43,560/10,890=4.0).
-- ═══════════════════════════════════════════════════════════════════════
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, min_lot_sqft, source_url,
   ordinance_section, confidence_score, effective_date)
VALUES
  (11765, 4.0, 10890,
   'https://moorehaven.org/wp-content/uploads/2023/08/Chapter-125-ZONING-Ord-336-Sep-2018.pdf',
   'City of Moore Haven Code of Ordinances, Ch. 125 (Zoning), Art. IX, Sec. 125-48 "R-1, Single-Family Residential District"',
   0.95, '2018-09-01')
ON CONFLICT (zoning_district_id) DO UPDATE SET
   max_density_du_acre = EXCLUDED.max_density_du_acre,
   min_lot_sqft = EXCLUDED.min_lot_sqft,
   source_url = EXCLUDED.source_url,
   ordinance_section = EXCLUDED.ordinance_section,
   confidence_score = EXCLUDED.confidence_score,
   effective_date = EXCLUDED.effective_date;

-- ═══════════════════════════════════════════════════════════════════════
-- R2 (Medium Density Residential, City of Moore Haven, jurisdiction 899,
-- zoning_districts.id=11766) — max_density_du_acre=8.0. Sec. 9.3,
-- narrative "up to eight (8) dwelling units per gross acre", cross-
-- confirmed via Sec. 9.7.4 RPD density table "Medium Density Residential
-- FLUC ... 8 du/ac".
-- ═══════════════════════════════════════════════════════════════════════
INSERT INTO public.zone_standards
  (zoning_district_id, max_density_du_acre, source_url, ordinance_section,
   confidence_score, effective_date)
VALUES
  (11766, 8.0,
   'https://moorehaven.org/wp-content/uploads/2022/03/Moore-Haven-LDC-Ch4-10-5-2010.pdf',
   'City of Moore Haven Land Development Code, Ch. 4 (Zoning), Sec. 9.3 "R-2, Medium Density Residential District"',
   0.95, '2010-10-05')
ON CONFLICT (zoning_district_id) DO UPDATE SET
   max_density_du_acre = EXCLUDED.max_density_du_acre,
   source_url = EXCLUDED.source_url,
   ordinance_section = EXCLUDED.ordinance_section,
   confidence_score = EXCLUDED.confidence_score,
   effective_date = EXCLUDED.effective_date;

-- OUA (Open Use Agricultural, jurisdiction 1153, zoning_districts.id=11768)
-- deliberately NOT touched — Municode 403, elaws.us 503 (6+ retries),
-- Firecrawl 402 (no credits) all blocked primary-source access this
-- session. 2 parcels remain an honest, reported gap. See session report.
