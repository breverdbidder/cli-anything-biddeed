-- Manatee county criterion G — density sub-metric fix for GC and VIL districts
-- dispatch_id: 7bcb4434-c068-4a5d-b140-0dcf65c8c87f (pair manatee-G, shard1 run11262)
--
-- Baseline (live, this dispatch): G FAIL 94.4% (density=94.4 far=100.0 pk1000=100.0)
-- v_zoning_gold_standard_kpi_v3: density_applicable_parcels=662, pct_density_of_applicable=94.4
--
-- Documents writes already applied live via PostgREST by
-- scripts/manatee_g_density_gc_vil_fix_7bcb4434.py (executed this session; this
-- migration is DDL-free, for schema-history parity only — see 20260813c sibling).
--
-- 1. GC (General Commercial), jurisdiction_id=1257 (Unincorporated Manatee),
--    zoning_districts.id=10894, zone_standards.id=3600. density_regulated=NULL,
--    max_density_du_acre was NULL despite an existing zone_standards row
--    (max_far=0.50). Source: Manatee County LDC Chapter 4 Zoning (official
--    mymanatee.org PDF "ldc-ch4-zoning-v64-comments.pdf", doc p.4-15, HTTP 200
--    verified live this session, 6.5MB):
--      "In the NC, GC and HC zoning districts, single family and duplex
--       dwellings may be allowed subject to the following criteria: ...
--       Shall not violate the maximum gross density requirement of nine (9)
--       dwelling units per acre."
--    -> max_density_du_acre = 9.0, confidence_score = 0.65 (draft/comments-
--       version LDC PDF, single document, explicit verbatim citable figure).
UPDATE zone_standards
SET max_density_du_acre = 9.0,
    source_url = 'https://www.mymanatee.org/media/docs/default-source/development-services-department-documents/development-services-department-documents/land-development-regulations/ldc-ch4-zoning-v64-comments.pdf',
    ordinance_section = 'LDC Ch.4 p.4-15, note on NC/GC/HC residential density cap',
    confidence_score = 0.65
WHERE zoning_district_id = 10894 AND max_density_du_acre IS NULL;

-- 2. VIL (Village: Myakka City, Parrish, Rubonia), jurisdiction_id=1257,
--    zoning_districts.id=11248. density_regulated was NULL, no zone_standards
--    row at all. Same LDC Ch.4 PDF (doc p.4-2 / PDF p.3) shows VIL cross-
--    referenced against THREE Future Land Use categories simultaneously
--    (RES-3, RES-6, RES-9) and PDF p.44 states for the analogous PR district:
--    "The underlying Future Land Use Category shall determine the maximum
--    density on each site" — VIL has no single fixed district-level density
--    figure; it is FLU-driven per parcel, matching the existing PD-R/PD-MU
--    precedent already marked density_regulated=false in this jurisdiction.
--    Filling a single number would be fabrication (Honesty Protocol
--    CRITICAL) — correct fix is density_regulated=false, excluding VIL from
--    the density-applicable denominator.
UPDATE zoning_districts
SET density_regulated = false
WHERE id = 11248 AND density_regulated IS NOT false;

-- NOT FIXED (left honestly unresolved): BR_T4-R (jurisdiction_id=888, City of
-- Bradenton, zoning_districts.id=11258, Form-Based Code "T4-R"). WebSearch +
-- WebFetch this session on library.municode.com/fl/bradenton returned HTTP 403
-- (confirmed live); no other verifiable T4-R-specific density source found.
-- Left density_regulated=NULL / max_density_du_acre=NULL. Does not block the
-- 95% PASS threshold (verified result: 96.0% with BR_T4-R's 9 parcels still
-- excluded from the passing count).
--
-- LIVE VERIFY after both writes, pencil_dod_evaluate_county('manatee'):
--   G: {"pass": true, "detail": "density=96.0 far=100.0 pk1000=100.0", "metric": 96.0}
-- v_zoning_gold_standard_kpi_v3: density_applicable_parcels=651 (662-11 VIL),
--   pct_density_of_applicable=96.0
