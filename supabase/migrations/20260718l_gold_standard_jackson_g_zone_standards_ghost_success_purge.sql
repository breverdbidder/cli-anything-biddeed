-- ============================================================
-- Gold Standard Jackson county: G ghost-success purge (dispatch bca41e8b,
-- ULTRALOOP audit of a prior session's refuter flag)
-- ============================================================
--
-- A prior session's refuter flagged Jackson B/F/G as possible ghost-success
-- (self-referential synthetic outcome rows, copy-pasted zoning template).
-- This session's ULTRALOOP audit (fan-out diagnosis + independent adversarial
-- refuter, survived=true) CONFIRMED the G flag: 3 of 15 queried zone_standards
-- rows (zoning_district_id 11196/C-1, 11197/C-2, 11198/A-1, jurisdiction_id
-- 833/Marianna) carried ordinance_section='INFERRED:typical_fl_rural_zoning/
-- shard3-jackson-g-v1' -- a self-admitted synthetic-template label, not a
-- real ordinance citation -- with source_url pointing only to the
-- library.municode.com/fl/marianna INDEX page, never a specific section,
-- proving no ordinance text was actually read for the FAR/density/height/
-- parking values on those 3 rows (created 2026-06-27, same batch as the
-- flagged rows). The B/F (foreclosure_outcomes) flag could NOT be confirmed
-- OR refuted this session -- every live verification source (jackson.
-- realforeclose.com, jacksonclerk.com, qpublic) returned HTTP 403 to
-- automated fetch and Firecrawl had zero API credits. B/F is left AS-IS,
-- neither reversed nor further flagged; deferred pending a working browser-
-- automation path or manual Clerk lookup (850-482-9552).
--
-- Applied live via PostgREST PATCH (Management API blocked by Cloudflare
-- WAF error 1010 for this payload in this sandbox). Post-purge live
-- pencil_dod_evaluate_county('jackson') confirms G still PASSes at 100.0 on
-- the remaining 20 real, ordinance-cited Marianna districts (5923-5947) plus
-- other jackson jurisdictions' real coverage -- the 3 fabricated rows were
-- not load-bearing for the metric, so this purge is a pure data-integrity
-- fix with zero letter regression. E/I/J unaffected (95.3/95.3/98.4, unchanged).
--
-- Idempotent: WHERE ordinance_section = '<exact template tag>' guard --
-- already-nulled rows no longer match on re-run.

UPDATE public.zone_standards
SET
  max_far = NULL,
  max_density_du_acre = NULL,
  max_height_ft = NULL,
  parking_per_1000sf = NULL,
  parking_per_unit = NULL,
  max_lot_coverage_pct = NULL,
  confidence_score = NULL,
  source_url = NULL,
  ordinance_section = NULL
WHERE zoning_district_id IN (11196, 11197, 11198)
  AND ordinance_section = 'INFERRED:typical_fl_rural_zoning/shard3-jackson-g-v1'
  AND EXISTS (
    SELECT 1 FROM public.zoning_districts zd
    WHERE zd.id = zone_standards.zoning_district_id
      AND zd.jurisdiction_id = 833
  );

-- NOTE (informational, NOT executed -- out of Jackson scope): the same
-- self-labeled INFERRED template pattern also exists on 4 unrelated rows
-- (zoning_district_id 11199 AG, 11200 R1, 11201 C1, 11202 IND;
-- ordinance_section LIKE 'INFERRED:standard_fl_zone:run1524:%') belonging to
-- a different county/jurisdiction batch -- flagged for a future dedicated
-- ghost-success sweep, not corrected here.
