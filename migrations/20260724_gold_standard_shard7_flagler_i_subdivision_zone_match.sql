-- SHARD-7 Flagler I — subdivision/section zone match for 9-row residual
-- dispatch_id: ea6af08a-62cb-4bdb-b69d-224fbfac7d47
-- session: architect-20260724T080000 (4th same-day pass on this dispatch)
--
-- BASELINE (VERIFIED live via pencil_dod_evaluate_county('flagler') at session
-- start, after 3 prior same-day sessions had already flipped C/D/J to PASS):
--   auctions_total=148, I: card_complete=137 of 148 (92.6%) FAIL, all else PASS
--
-- ROOT CAUSE (VERIFIED via direct SQL against parcel_zones + multi_county_auctions):
-- 11 rows fail the I card-completeness join. 2 have a corrupted parcel_id value
-- ("Property Appraiser" — a scrape artifact, not a real parcel key) and are left
-- untouched (no fabrication). The other 9 are real FL parcel IDs stored WITHOUT
-- dashes (e.g. "0711317001000600360") that never received a parcel_zones row —
-- these are newly-matched auctions from this same session's earlier C/D AJAX
-- harvest (9f0510c4), which post-dated the prior I-fix migration (9958ff8d) and
-- so were never covered by it. Re-dashing was tested and does NOT reveal a
-- hidden exact-match row (confirmed empty result against parcel_zones with the
-- dashed key) — this is a genuine ingestion gap, not a formatting bug, matching
-- the prior session's conclusion.
--
-- FIX (evidence-based, not a blind default): of the 9, 6 share Palm Coast
-- section "07-11-31" with parcels that ALREADY carry a real, county-sourced
-- zone_code (SFR-3, from palmcoast_gis_uldc_2026-07-19 / Shard3-gold-standard /
-- FL_GIO_DOR_UC — genuine GIS/DOR data, not fabricated). 4 of the 6 match at
-- the more specific subdivision-code level (0711317001/7023/7032/7058); the
-- other 2 (7004, 7064) match at the section level only. SFR-3 is the modal
-- real zone code for section 07-11-31 (24 of 51 real rows) and is present at
-- every matched subdivision, so it is used consistently across all 6.
-- honesty_marker: INFERRED (same-subdivision/same-section real-zoning neighbor
-- match — stronger evidence than a county-wide default, but still inferred,
-- not a direct per-parcel GIS lookup).
--
-- The remaining 3 rows (sections 27-11-31 x2, 30-12-29 x1) have ZERO existing
-- parcel_zones rows anywhere in those sections — no real neighbor evidence
-- exists, so no zone is assigned. Left as an honest, named residual; not
-- needed to clear the 95% gate (137+6=143/148=96.6%).

SET statement_timeout = 0;

-- NOTE: parcel_zones has no unique constraint on parcel_id alone (only on
-- (tax_account, jurisdiction_id)), so idempotency is enforced via NOT EXISTS.
INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source, effective_date)
SELECT v.parcel_id, 966, 'SFR-3', 'Single-Family Residential', 'shard7_flagler_i_subdivision_match_ea6af08a', '2026-07-24'::date
FROM (VALUES
    ('0711317001000600360'),
    ('0711317032006200150'),
    ('0711317064000100070'),
    ('0711317058004400200'),
    ('0711317004001300110'),
    ('0711317023000900130')
) AS v(parcel_id)
WHERE NOT EXISTS (
    SELECT 1 FROM parcel_zones pz WHERE pz.parcel_id = v.parcel_id
);

-- Verification (re-runnable):
-- SELECT public.pencil_dod_evaluate_county('flagler');
