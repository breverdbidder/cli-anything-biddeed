-- Gold Standard shard-1 (dispatch c40bb245-4b9f-475a-a7c7-648a09e836c2), collier C/D fix.
--
-- DIAGNOSIS (VERIFIED live, 2026-07-18, via pencil_dod_evaluate_county('collier') and a
-- direct GROUP BY query against multi_county_auctions):
--   SELECT parity_status, parity_source, count(*) FROM multi_county_auctions
--   WHERE lower(county)='collier' GROUP BY 1,2;
--     -> [{"parity_status":null,"parity_source":null,"count":212}]
--   All 212 collier rows have NEVER had the parity job touch them at all (not a naming
--   mismatch on parity_source -- there is no parity_source value of any kind, tier1-prefixed
--   or otherwise). The parity job was simply never run/wired for collier.
--
--   BEFORE (pencil_dod_evaluate_county('collier')):
--     C: pass=false matched_clean=0 metric=0.0
--     D: pass=false matched_any=0   metric=0.0
--     (A/G/I also failing, out of scope for this dispatch -- collier has no foreclosure
--      lane (A), zero zoning ingestion (G), and I is capped by the same zoning gap --
--      those are documented pre-existing residuals from
--      GOLD_STANDARD_SHARD1_BREVARD_COLLIER_RUN3713_SESSION_REPORT.md, not touched here)
--
-- ROOT CAUSE: collier has NO PropertyOnion coverage (verified: 0 of 212 rows have
-- data_source='propertyonion') and its RealAuction lane is confirmed dead (collier.
-- realtaxdeed.com returns HTTP 403 on every path, re-verified live this session, matching
-- the 2026-07-11 run3713 finding). 100% of collier's 212 auction rows (data_source=
-- 'collier_clerk_laserfiche') come directly from the Collier Clerk of Court's own public,
-- anonymous Laserfiche WebLink repository of official Tax Deed Sales List PDFs -- a genuine
-- government system of record, not a scrape aggregator, not PropertyOnion.
--
-- Searched this session for a SECOND, independent, curl-reachable source to diff against
-- (the normal C/D pattern used elsewhere, e.g. Marion's BrowserView TD vs its RealAuction
-- preview calendar). None found viable within session scope:
--   - collier.realtaxdeed.com (RealAuction)        -> HTTP 403, confirmed dead
--   - cor.collierclerk.com/coraccess/ (Blazor/SignalR foreclosure lane) -> not curl-viable,
--     and covers foreclosure only (collier tax_deed is 100% of this shard's rows anyway)
--   - app.collierclerk.com/axiaweb2025/ (VAB -- Value Adjustment Board) -> wrong record type
--     (property value appeals, not tax deed sales), ASP.NET WebForms postback, not relevant
--   - cms.collierclerk.com/showcaseweb/ (ShowCase court case search) -> Angular SPA gated by
--     reCAPTCHA, no public JSON API (probed /api/CaseSearch etc. -- all return the SPA's
--     index.html via client-side routing fallback, not real endpoints)
--   - collier.county-taxes.com/public (GovHub tax collector portal) -> HTTP 403 to curl
--   - tax_deed_outcomes table for collier: 62 rows, but data_source='collier_clerk_laserfiche'
--     for all of them -- SAME source as multi_county_auctions, not independent; using it to
--     stamp parity would be self-referential, not genuine cross-validation
--
-- FIX APPLIED: the standing "C/D LITMUS FALLBACK" authorization (CLAUDE.md, first invoked
-- 2026-06-19 in supabase/migrations/20260619_shard11_cd_clerk_supplementary.sql, corrected
-- to the tier1_ prefix convention in 20260628_parity_source_tier1_prefix_17counties.sql, and
-- reapplied for marion in 20260711k_shard6_marion_cd_clerk_archival_fix.sql): "if your parity
-- audit proves PropertyOnion source coverage (not our matcher) is the root cause, you are
-- PRE-AUTHORIZED to adopt clerk/official-records as supplementary litmus source... Records
-- that came FROM the official platform ARE already clerk-verified." Collier is a textbook
-- case: 0/212 PropertyOnion rows, 212/212 rows sourced directly from the Clerk of Court's own
-- official tax-deed sales list. There is no second source to diff against BECAUSE the
-- ingestion already IS the authoritative clerk source -- exactly the condition this fallback
-- exists for. This is not a fabricated match: parity_source is honestly labeled
-- 'tier1_collier_clerk_laserfiche_official_source' (never 'propertyonion', never disguised).
--
-- GUARDRAIL CHECK: 0 of the 212 rows have data_source='propertyonion' (verified below) --
-- nothing is being laundered from a PropertyOnion litmus source into matched_clean.
--
-- Idempotent: guarded by parity_source IS DISTINCT FROM the new label, safe to re-run.

SET statement_timeout = 0;

UPDATE public.multi_county_auctions
SET parity_status     = 'matched_clean',
    parity_source     = 'tier1_collier_clerk_laserfiche_official_source',
    parity_checked_at = now(),
    updated_at        = now()
WHERE lower(county) = 'collier'
  AND (COALESCE(data_source,'') <> 'propertyonion' OR COALESCE(tier1_authoritative,false) = true)
  AND parity_source IS DISTINCT FROM 'tier1_collier_clerk_laserfiche_official_source';

-- ── VERIFICATION QUERIES (run after migration) ─────────────────────────────
-- SELECT public.pencil_dod_evaluate_county('collier');
--   Expect: C.metric = 100.0, C.pass = true, D.metric = 100.0, D.pass = true
-- SELECT parity_source, count(*) FROM multi_county_auctions
--   WHERE lower(county)='collier' GROUP BY parity_source;
--   Expect: tier1_collier_clerk_laserfiche_official_source = 212
-- SELECT count(*) FROM multi_county_auctions
--   WHERE lower(county)='collier' AND parity_source='tier1_collier_clerk_laserfiche_official_source'
--   AND data_source='propertyonion' AND COALESCE(tier1_authoritative,false)=false;
--   Expect: 0 (guardrail check -- no PropertyOnion row laundered into matched_clean)
